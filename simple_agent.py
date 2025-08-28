# langgraph_agent.py
from __future__ import annotations

from typing import Dict, Any, Optional, Literal
try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict

import yaml

# Your existing types / clients
from state_models import CustomerSupportState, InputPayload
from mcp_client import MCPClientManager

# LangGraph
from langgraph.graph import StateGraph, START, END


class LangGraphAgent:
    """
    LangGraph-based implementation of your customer-support workflow.
    - Mirrors your original graph structure and node logic
    - Uses MCPClientManager to call abilities on COMMON / ATLAS servers
    - Preserves logs, fields, and final payload shape
    """

    def __init__(self, config_path: str = "config.yaml"):
        # Load config (kept for parity with original)
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        # External clients (same as before)
        self.mcp_manager = MCPClientManager()

        # Build the LangGraph
        self.app = self._build_graph()

    # -----------------------------
    # Internal utilities
    # -----------------------------
    def _log_stage(self, state: CustomerSupportState, stage: str, message: str) -> None:
        """Append a log entry and print it (side-effect kept for parity)."""
        logs = state.get("execution_log") or []
        logs.append(f"[{stage}] {message}")
        state["execution_log"] = logs
        print(f"[{stage}] {message}")

    def _execute_ability(
        self, server: str, ability: str, state: CustomerSupportState
    ) -> Dict[str, Any]:
        """
        Execute an ability via MCP client, passing a payload assembled from state.
        Mirrors original behavior including the 'internal' short-circuit.
        """
        if server == "internal":
            return {"result": f"Internal {ability} executed"}

        payload = {
            "customer_name": state.get("customer_name"),
            "email": state.get("email"),
            "query": state.get("query"),
            "priority": state.get("priority"),
            "ticket_id": state.get("ticket_id"),
            "solution_score": state.get("solution_score"),
        }

        result = self.mcp_manager.call_ability(server, ability, payload)
        self._log_stage(state, "MCP", f"Called {ability} on {server} server")
        return result

    # -----------------------------
    # Node functions
    # Each returns a dict of updates that LangGraph merges into state.
    # -----------------------------
    def intake_node(self, state: CustomerSupportState) -> Dict[str, Any]:
        self._log_stage(state, "INTAKE", "[NODE] Accepting payload")
        completed = state.get("completed_stages", []) + ["intake"]
        return {"current_stage": "intake", "completed_stages": completed}

    def understand_node(self, state: CustomerSupportState) -> Dict[str, Any]:
        self._log_stage(state, "UNDERSTAND", "[NODE] Parsing request and extracting entities")

        parse_result = self._execute_ability("COMMON", "parse_request_text", state)
        entities_result = self._execute_ability("ATLAS", "extract_entities", state)

        completed = state.get("completed_stages", []) + ["understand"]
        return {
            "parsed_request": parse_result,
            "extracted_entities": entities_result,
            "current_stage": "understand",
            "completed_stages": completed,
        }

    def prepare_node(self, state: CustomerSupportState) -> Dict[str, Any]:
        self._log_stage(state, "PREPARE", "[NODE] Normalizing, enriching, and calculating flags")

        normalize_result = self._execute_ability("COMMON", "normalize_fields", state)
        enrich_result = self._execute_ability("ATLAS", "enrich_records", state)
        flags_result = self._execute_ability("COMMON", "add_flags_calculations", state)

        completed = state.get("completed_stages", []) + ["prepare"]
        return {
            "normalized_data": normalize_result,
            "enriched_data": enrich_result,
            "flags_calculations": flags_result,
            "current_stage": "prepare",
            "completed_stages": completed,
        }

    def ask_node(self, state: CustomerSupportState) -> Dict[str, Any]:
        self._log_stage(state, "ASK", "[NODE] Asking clarification question")

        clarify_result = self._execute_ability("ATLAS", "clarify_question", state)
        question = clarify_result.get("question")

        completed = state.get("completed_stages", []) + ["ask"]
        return {
            "clarification_question": question,
            "clarification_needed": True,
            "current_stage": "ask",
            "completed_stages": completed,
        }

    def wait_node(self, state: CustomerSupportState) -> Dict[str, Any]:
        self._log_stage(state, "WAIT", "[NODE] Extracting and storing answer")

        answer_result = self._execute_ability("ATLAS", "extract_answer", state)
        self._execute_ability("internal", "store_answer", state)

        completed = state.get("completed_stages", []) + ["wait"]
        return {
            "customer_response": answer_result.get("answer"),
            "clarification_needed": False,
            "current_stage": "wait",
            "completed_stages": completed,
        }

    def retrieve_node(self, state: CustomerSupportState) -> Dict[str, Any]:
        self._log_stage(state, "RETRIEVE", "[NODE] Searching knowledge base")

        kb_result = self._execute_ability("ATLAS", "knowledge_base_search", state)
        self._execute_ability("internal", "store_data", state)

        completed = state.get("completed_stages", []) + ["retrieve"]
        return {
            "kb_results": kb_result.get("results"),
            "current_stage": "retrieve",
            "completed_stages": completed,
        }

    def decide_node(self, state: CustomerSupportState) -> Dict[str, Any]:
        self._log_stage(state, "DECIDE", "[NODE] Evaluating solutions (NON-DETERMINISTIC)")

        eval_result = self._execute_ability("COMMON", "solution_evaluation", state)
        score = eval_result.get("score", 85)

        # Note: route decision also calls ATLAS.escalation_decision,
        # but we call it here to preserve your original behavior.
        escalation_result = self._execute_ability("ATLAS", "escalation_decision", state)
        escalate = escalation_result.get("escalate", False)
        rationale = escalation_result.get("reason")

        completed = state.get("completed_stages", []) + ["decide"]
        return {
            "solution_score": score,
            "escalation_required": escalate,
            "decision_rationale": rationale,
            "current_stage": "decide",
            "completed_stages": completed,
        }

    # Conditional router: returns the NEXT node's name
    def route_decision_node(self, state: CustomerSupportState) -> Literal["escalate", "auto_resolve"]:
        escalation_required = state.get("escalation_required", False)
        solution_score = state.get("solution_score", 85)

        if escalation_required or solution_score < 90:
            self._log_stage(state, "ROUTER", f"[GRAPH] ROUTING -> escalate (score: {solution_score})")
            return "escalate"
        else:
            self._log_stage(state, "ROUTER", f"[GRAPH] ROUTING -> auto_resolve (score: {solution_score})")
            return "auto_resolve"

    def escalate_node(self, state: CustomerSupportState) -> Dict[str, Any]:
        self._log_stage(state, "ESCALATE", "[NODE] Escalating to human agent")

        update_result = self._execute_ability("ATLAS", "update_ticket", state)
        completed = state.get("completed_stages", []) + ["escalate"]

        return {
            "ticket_updated": update_result.get("updated", False),
            "escalation_path": True,
            "current_stage": "escalate",
            "completed_stages": completed,
        }

    def auto_resolve_node(self, state: CustomerSupportState) -> Dict[str, Any]:
        self._log_stage(state, "AUTO_RESOLVE", "[NODE] Auto-resolving ticket")

        update_result = self._execute_ability("ATLAS", "update_ticket", state)
        completed = state.get("completed_stages", []) + ["auto_resolve"]

        return {
            "ticket_updated": update_result.get("updated", False),
            "escalation_path": False,
            "current_stage": "auto_resolve",
            "completed_stages": completed,
        }

    def create_response_node(self, state: CustomerSupportState) -> Dict[str, Any]:
        self._log_stage(state, "CREATE_RESPONSE", "[NODE] Creating escalation response")

        response_result = self._execute_ability("COMMON", "response_generation", state)
        completed = state.get("completed_stages", []) + ["create_response"]

        return {
            "generated_response": response_result.get("response"),
            "current_stage": "create_response",
            "completed_stages": completed,
        }

    def update_close_node(self, state: CustomerSupportState) -> Dict[str, Any]:
        self._log_stage(state, "UPDATE_CLOSE", "[NODE] Updating and closing ticket")

        response_result = self._execute_ability("COMMON", "response_generation", state)
        close_result = self._execute_ability("ATLAS", "close_ticket", state)
        api_result = self._execute_ability("ATLAS", "execute_api_calls", state)
        notif_result = self._execute_ability("ATLAS", "trigger_notifications", state)

        completed = state.get("completed_stages", []) + ["update_close"]

        return {
            "generated_response": response_result.get("response"),
            "ticket_closed": close_result.get("closed", False),
            "api_calls_executed": api_result.get("api_calls", []),
            "notifications_sent": notif_result.get("notifications", []),
            "current_stage": "update_close",
            "completed_stages": completed,
        }

    def complete_node(self, state: CustomerSupportState) -> Dict[str, Any]:
        self._log_stage(state, "COMPLETE", "[NODE] Outputting final payload")

        self._execute_ability("internal", "output_payload", state)

        status = "closed" if state.get("ticket_closed") else "escalated"
        path_taken = "escalation" if state.get("escalation_path") else "auto_resolution"

        final_payload = {
            "ticket_id": state.get("ticket_id"),
            "customer_name": state.get("customer_name"),
            "status": status,
            "resolution": state.get("generated_response"),
            "escalated": state.get("escalation_path", False),
            "solution_score": state.get("solution_score"),
            "path_taken": path_taken,
            "completed_stages": state.get("completed_stages", []),
        }

        completed = state.get("completed_stages", []) + ["complete"]

        return {
            "final_payload": final_payload,
            "current_stage": "complete",
            "completed_stages": completed,
        }

    # -----------------------------
    # Graph assembly
    # -----------------------------
    def _build_graph(self):
        """
        Create a StateGraph with your nodes and edges, including the conditional edge.
        """
        graph = StateGraph(CustomerSupportState)

        # Register nodes
        graph.add_node("intake", self.intake_node)
        graph.add_node("understand", self.understand_node)
        graph.add_node("prepare", self.prepare_node)
        graph.add_node("ask", self.ask_node)
        graph.add_node("wait", self.wait_node)
        graph.add_node("retrieve", self.retrieve_node)
        graph.add_node("decide", self.decide_node)
        # 'route_decision' is declared via conditional edge function
        graph.add_node("escalate", self.escalate_node)
        graph.add_node("auto_resolve", self.auto_resolve_node)
        graph.add_node("create_response", self.create_response_node)
        graph.add_node("update_close", self.update_close_node)
        graph.add_node("complete", self.complete_node)

        # Entry
        graph.add_edge(START, "intake")

        # Linear path
        graph.add_edge("intake", "understand")
        graph.add_edge("understand", "prepare")
        graph.add_edge("prepare", "ask")
        graph.add_edge("ask", "wait")
        graph.add_edge("wait", "retrieve")
        graph.add_edge("retrieve", "decide")

        # Conditional routing from a virtual "route_decision" step
        # LangGraph uses a callable to determine the next node label.
        graph.add_conditional_edges(
            "decide",
            self.route_decision_node,
            {
                "escalate": "escalate",
                "auto_resolve": "auto_resolve",
            },
        )

        # Branches reconverge toward completion
        graph.add_edge("escalate", "create_response")
        graph.add_edge("create_response", "complete")

        graph.add_edge("auto_resolve", "update_close")
        graph.add_edge("update_close", "complete")

        # End
        graph.add_edge("complete", END)

        return graph.compile()

    # -----------------------------
    # Public API
    # -----------------------------
    def run(self, input_payload: InputPayload) -> Dict[str, Any]:
        """
        Execute the compiled LangGraph with your initial state and return the final state.
        """
        print("[LANGGRAPH] Starting Customer Support Graph Workflow")
        print("=" * 60)

        # Initialize state (parity with your original)
        state: CustomerSupportState = {
            "customer_name": input_payload.customer_name,
            "email": input_payload.email,
            "query": input_payload.query,
            "priority": input_payload.priority,
            "ticket_id": input_payload.ticket_id,
            "current_stage": "",
            "completed_stages": [],
            "parsed_request": None,
            "extracted_entities": None,
            "normalized_data": None,
            "enriched_data": None,
            "flags_calculations": None,
            "clarification_needed": False,
            "clarification_question": None,
            "customer_response": None,
            "kb_results": None,
            "solution_score": None,
            "escalation_required": False,
            "escalation_path": None,
            "decision_rationale": None,
            "ticket_updated": False,
            "ticket_closed": False,
            "generated_response": None,
            "api_calls_executed": [],
            "notifications_sent": [],
            "final_payload": None,
            "execution_log": [],
        }

        # Invoke the graph synchronously and obtain the final aggregated state
        final_state: CustomerSupportState = self.app.invoke(state)

        print("=" * 60)
        print("[LANGGRAPH] Graph execution complete!")
        return final_state


if __name__ == "__main__":
    agent = LangGraphAgent(config_path="config.yaml")
    payload = InputPayload(
        customer_name="Alex Doe",
        email="alex@example.com",
        query="I was double-charged last month.",
        priority="medium",
        ticket_id="TKT-12345",
    )
    final = agent.run(payload)
    print("\n=== FINAL STATE ===")
    from pprint import pprint
    pprint(final)
    print("\n=== FINAL PAYLOAD ===")
    pprint(final.get("final_payload"))
