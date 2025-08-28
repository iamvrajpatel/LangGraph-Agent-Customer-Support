from typing import Dict, Any
try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal
from state_models import CustomerSupportState, InputPayload
from mcp_client import MCPClientManager
import yaml
import json

class LangGraphAgent:
    """LangGraph-style Agent with graph structure and conditional routing"""
    
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.mcp_manager = MCPClientManager()
        
        # Graph structure definition
        self.graph = {
            "START": ["intake"],
            "intake": ["understand"],
            "understand": ["prepare"],
            "prepare": ["ask"],
            "ask": ["wait"],
            "wait": ["retrieve"],
            "retrieve": ["decide"],
            "decide": ["route_decision"],
            "route_decision": ["escalate", "auto_resolve"],
            "escalate": ["create_response"],
            "auto_resolve": ["update_close"],
            "create_response": ["complete"],
            "update_close": ["complete"],
            "complete": ["END"]
        }
        
        # Node functions mapping
        self.nodes = {
            "intake": self.intake_node,
            "understand": self.understand_node,
            "prepare": self.prepare_node,
            "ask": self.ask_node,
            "wait": self.wait_node,
            "retrieve": self.retrieve_node,
            "decide": self.decide_node,
            "route_decision": self.route_decision_node,
            "escalate": self.escalate_node,
            "auto_resolve": self.auto_resolve_node,
            "create_response": self.create_response_node,
            "update_close": self.update_close_node,
            "complete": self.complete_node
        }
    
    def _log_stage(self, state: CustomerSupportState, stage: str, message: str):
        """Add log entry to state"""
        if "execution_log" not in state:
            state["execution_log"] = []
        state["execution_log"].append(f"[{stage}] {message}")
        print(f"[{stage}] {message}")
    
    def _execute_ability(self, server: str, ability: str, state: CustomerSupportState) -> Dict[str, Any]:
        """Execute ability via MCP client"""
        if server == "internal":
            return {"result": f"Internal {ability} executed"}
        
        payload = {
            "customer_name": state.get("customer_name"),
            "email": state.get("email"),
            "query": state.get("query"),
            "priority": state.get("priority"),
            "ticket_id": state.get("ticket_id"),
            "solution_score": state.get("solution_score")
        }
        
        result = self.mcp_manager.call_ability(server, ability, payload)
        self._log_stage(state, "MCP", f"Called {ability} on {server} server")
        return result
    
    # Graph Nodes
    def intake_node(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "INTAKE", "[NODE] Accepting payload")
        state["current_stage"] = "intake"
        state["completed_stages"] = state.get("completed_stages", []) + ["intake"]
        return state
    
    def understand_node(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "UNDERSTAND", "[NODE] Parsing request and extracting entities")
        
        parse_result = self._execute_ability("COMMON", "parse_request_text", state)
        state["parsed_request"] = parse_result
        
        entities_result = self._execute_ability("ATLAS", "extract_entities", state)
        state["extracted_entities"] = entities_result
        
        state["current_stage"] = "understand"
        state["completed_stages"] = state.get("completed_stages", []) + ["understand"]
        return state
    
    def prepare_node(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "PREPARE", "[NODE] Normalizing, enriching, and calculating flags")
        
        normalize_result = self._execute_ability("COMMON", "normalize_fields", state)
        state["normalized_data"] = normalize_result
        
        enrich_result = self._execute_ability("ATLAS", "enrich_records", state)
        state["enriched_data"] = enrich_result
        
        flags_result = self._execute_ability("COMMON", "add_flags_calculations", state)
        state["flags_calculations"] = flags_result
        
        state["current_stage"] = "prepare"
        state["completed_stages"] = state.get("completed_stages", []) + ["prepare"]
        return state
    
    def ask_node(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "ASK", "[NODE] Asking clarification question")
        
        clarify_result = self._execute_ability("ATLAS", "clarify_question", state)
        state["clarification_question"] = clarify_result.get("question")
        state["clarification_needed"] = True
        
        state["current_stage"] = "ask"
        state["completed_stages"] = state.get("completed_stages", []) + ["ask"]
        return state
    
    def wait_node(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "WAIT", "[NODE] Extracting and storing answer")
        
        answer_result = self._execute_ability("ATLAS", "extract_answer", state)
        state["customer_response"] = answer_result.get("answer")
        
        self._execute_ability("internal", "store_answer", state)
        state["clarification_needed"] = False
        
        state["current_stage"] = "wait"
        state["completed_stages"] = state.get("completed_stages", []) + ["wait"]
        return state
    
    def retrieve_node(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "RETRIEVE", "[NODE] Searching knowledge base")
        
        kb_result = self._execute_ability("ATLAS", "knowledge_base_search", state)
        state["kb_results"] = kb_result.get("results")
        
        self._execute_ability("internal", "store_data", state)
        
        state["current_stage"] = "retrieve"
        state["completed_stages"] = state.get("completed_stages", []) + ["retrieve"]
        return state
    
    def decide_node(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "DECIDE", "[NODE] Evaluating solutions (NON-DETERMINISTIC)")
        
        eval_result = self._execute_ability("COMMON", "solution_evaluation", state)
        state["solution_score"] = eval_result.get("score", 85)
        
        escalation_result = self._execute_ability("ATLAS", "escalation_decision", state)
        state["escalation_required"] = escalation_result.get("escalate", False)
        state["decision_rationale"] = escalation_result.get("reason")
        
        state["current_stage"] = "decide"
        state["completed_stages"] = state.get("completed_stages", []) + ["decide"]
        return state
    
    def route_decision_node(self, state: CustomerSupportState) -> Literal["escalate", "auto_resolve"]:
        """CONDITIONAL ROUTING - Graph decision point"""
        escalation_required = state.get("escalation_required", False)
        solution_score = state.get("solution_score", 85)
        
        if escalation_required or solution_score < 90:
            self._log_stage(state, "ROUTER", f"[GRAPH] ROUTING -> escalate (score: {solution_score})")
            return "escalate"
        else:
            self._log_stage(state, "ROUTER", f"[GRAPH] ROUTING -> auto_resolve (score: {solution_score})")
            return "auto_resolve"
    
    def escalate_node(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "ESCALATE", "[NODE] Escalating to human agent")
        
        update_result = self._execute_ability("ATLAS", "update_ticket", state)
        state["ticket_updated"] = update_result.get("updated", False)
        state["escalation_path"] = True
        
        state["current_stage"] = "escalate"
        state["completed_stages"] = state.get("completed_stages", []) + ["escalate"]
        return state
    
    def auto_resolve_node(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "AUTO_RESOLVE", "[NODE] Auto-resolving ticket")
        
        update_result = self._execute_ability("ATLAS", "update_ticket", state)
        state["ticket_updated"] = update_result.get("updated", False)
        state["escalation_path"] = False
        
        state["current_stage"] = "auto_resolve"
        state["completed_stages"] = state.get("completed_stages", []) + ["auto_resolve"]
        return state
    
    def create_response_node(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "CREATE_RESPONSE", "[NODE] Creating escalation response")
        
        response_result = self._execute_ability("COMMON", "response_generation", state)
        state["generated_response"] = response_result.get("response")
        
        state["current_stage"] = "create_response"
        state["completed_stages"] = state.get("completed_stages", []) + ["create_response"]
        return state
    
    def update_close_node(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "UPDATE_CLOSE", "[NODE] Updating and closing ticket")
        
        response_result = self._execute_ability("COMMON", "response_generation", state)
        state["generated_response"] = response_result.get("response")
        
        close_result = self._execute_ability("ATLAS", "close_ticket", state)
        state["ticket_closed"] = close_result.get("closed", False)
        
        api_result = self._execute_ability("ATLAS", "execute_api_calls", state)
        state["api_calls_executed"] = api_result.get("api_calls", [])
        
        notif_result = self._execute_ability("ATLAS", "trigger_notifications", state)
        state["notifications_sent"] = notif_result.get("notifications", [])
        
        state["current_stage"] = "update_close"
        state["completed_stages"] = state.get("completed_stages", []) + ["update_close"]
        return state
    
    def complete_node(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "COMPLETE", "[NODE] Outputting final payload")
        
        self._execute_ability("internal", "output_payload", state)
        
        state["final_payload"] = {
            "ticket_id": state.get("ticket_id"),
            "customer_name": state.get("customer_name"),
            "status": "closed" if state.get("ticket_closed") else "escalated",
            "resolution": state.get("generated_response"),
            "escalated": state.get("escalation_path", False),
            "solution_score": state.get("solution_score"),
            "path_taken": "escalation" if state.get("escalation_path") else "auto_resolution",
            "completed_stages": state.get("completed_stages", [])
        }
        
        state["current_stage"] = "complete"
        state["completed_stages"] = state.get("completed_stages", []) + ["complete"]
        return state
    
    def run(self, input_payload: InputPayload) -> Dict[str, Any]:
        """Execute LangGraph workflow with conditional routing"""
        print("[LANGGRAPH] Starting Customer Support Graph Workflow")
        print("=" * 60)
        
        # Initialize state
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
            "execution_log": []
        }
        
        # Graph execution with conditional routing
        current_node = "START"
        
        while current_node != "END":
            print(f"[GRAPH] Executing node: {current_node}")
            
            if current_node == "START":
                current_node = "intake"
            elif current_node in self.nodes:
                if current_node == "route_decision":
                    # Conditional routing
                    next_path = self.route_decision_node(state)
                    current_node = next_path
                else:
                    # Execute node function
                    state = self.nodes[current_node](state)
                    # Get next node from graph
                    next_nodes = self.graph.get(current_node, ["END"])
                    current_node = next_nodes[0] if next_nodes else "END"
            else:
                current_node = "END"
        
        print("=" * 60)
        print("[LANGGRAPH] Graph execution complete!")
        return state