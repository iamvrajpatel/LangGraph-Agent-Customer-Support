from typing import Dict, Any
from state_models import CustomerSupportState, InputPayload
from mcp_client import MCPClientManager
import yaml
import json

class LangieSimpleAgent:
    """Simplified Langie Agent demonstrating the workflow without LangGraph dependency"""
    
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.mcp_manager = MCPClientManager()
        self.stages = [
            ("INTAKE", self.intake_stage),
            ("UNDERSTAND", self.understand_stage),
            ("PREPARE", self.prepare_stage),
            ("ASK", self.ask_stage),
            ("WAIT", self.wait_stage),
            ("RETRIEVE", self.retrieve_stage),
            ("DECIDE", self.decide_stage),
            ("UPDATE", self.update_stage),
            ("CREATE", self.create_stage),
            ("DO", self.do_stage),
            ("COMPLETE", self.complete_stage)
        ]
    
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
    
    # Stage implementations (same as LangGraph version)
    def intake_stage(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "INTAKE", "[INTAKE] Accepting payload")
        state["current_stage"] = "INTAKE"
        state["completed_stages"] = state.get("completed_stages", []) + ["INTAKE"]
        return state
    
    def understand_stage(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "UNDERSTAND", "[UNDERSTAND] Parsing request and extracting entities")
        
        parse_result = self._execute_ability("COMMON", "parse_request_text", state)
        state["parsed_request"] = parse_result
        
        entities_result = self._execute_ability("ATLAS", "extract_entities", state)
        state["extracted_entities"] = entities_result
        
        state["current_stage"] = "UNDERSTAND"
        state["completed_stages"] = state.get("completed_stages", []) + ["UNDERSTAND"]
        return state
    
    def prepare_stage(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "PREPARE", "[PREPARE] Normalizing, enriching, and calculating flags")
        
        normalize_result = self._execute_ability("COMMON", "normalize_fields", state)
        state["normalized_data"] = normalize_result
        
        enrich_result = self._execute_ability("ATLAS", "enrich_records", state)
        state["enriched_data"] = enrich_result
        
        flags_result = self._execute_ability("COMMON", "add_flags_calculations", state)
        state["flags_calculations"] = flags_result
        
        state["current_stage"] = "PREPARE"
        state["completed_stages"] = state.get("completed_stages", []) + ["PREPARE"]
        return state
    
    def ask_stage(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "ASK", "[ASK] Asking clarification question")
        
        clarify_result = self._execute_ability("ATLAS", "clarify_question", state)
        state["clarification_question"] = clarify_result.get("question")
        state["clarification_needed"] = True
        
        state["current_stage"] = "ASK"
        state["completed_stages"] = state.get("completed_stages", []) + ["ASK"]
        return state
    
    def wait_stage(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "WAIT", "[WAIT] Extracting and storing answer")
        
        answer_result = self._execute_ability("ATLAS", "extract_answer", state)
        state["customer_response"] = answer_result.get("answer")
        
        self._execute_ability("internal", "store_answer", state)
        state["clarification_needed"] = False
        
        state["current_stage"] = "WAIT"
        state["completed_stages"] = state.get("completed_stages", []) + ["WAIT"]
        return state
    
    def retrieve_stage(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "RETRIEVE", "[RETRIEVE] Searching knowledge base")
        
        kb_result = self._execute_ability("ATLAS", "knowledge_base_search", state)
        state["kb_results"] = kb_result.get("results")
        
        self._execute_ability("internal", "store_data", state)
        
        state["current_stage"] = "RETRIEVE"
        state["completed_stages"] = state.get("completed_stages", []) + ["RETRIEVE"]
        return state
    
    def decide_stage(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "DECIDE", "[DECIDE] Evaluating solutions and making decisions (NON-DETERMINISTIC)")
        
        eval_result = self._execute_ability("COMMON", "solution_evaluation", state)
        state["solution_score"] = eval_result.get("score")
        
        # Non-deterministic decision based on score
        escalation_result = self._execute_ability("ATLAS", "escalation_decision", state)
        state["escalation_required"] = escalation_result.get("escalate", False)
        state["decision_rationale"] = escalation_result.get("reason")
        
        self._execute_ability("internal", "update_payload", state)
        
        state["current_stage"] = "DECIDE"
        state["completed_stages"] = state.get("completed_stages", []) + ["DECIDE"]
        return state
    
    def update_stage(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "UPDATE", "[UPDATE] Updating and closing ticket")
        
        update_result = self._execute_ability("ATLAS", "update_ticket", state)
        state["ticket_updated"] = update_result.get("updated", False)
        
        if not state.get("escalation_required", False):
            close_result = self._execute_ability("ATLAS", "close_ticket", state)
            state["ticket_closed"] = close_result.get("closed", False)
        
        state["current_stage"] = "UPDATE"
        state["completed_stages"] = state.get("completed_stages", []) + ["UPDATE"]
        return state
    
    def create_stage(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "CREATE", "[CREATE] Generating response")
        
        response_result = self._execute_ability("COMMON", "response_generation", state)
        state["generated_response"] = response_result.get("response")
        
        state["current_stage"] = "CREATE"
        state["completed_stages"] = state.get("completed_stages", []) + ["CREATE"]
        return state
    
    def do_stage(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "DO", "[DO] Executing API calls and notifications")
        
        api_result = self._execute_ability("ATLAS", "execute_api_calls", state)
        state["api_calls_executed"] = api_result.get("api_calls", [])
        
        notif_result = self._execute_ability("ATLAS", "trigger_notifications", state)
        state["notifications_sent"] = notif_result.get("notifications", [])
        
        state["current_stage"] = "DO"
        state["completed_stages"] = state.get("completed_stages", []) + ["DO"]
        return state
    
    def complete_stage(self, state: CustomerSupportState) -> CustomerSupportState:
        self._log_stage(state, "COMPLETE", "[COMPLETE] Outputting final payload")
        
        self._execute_ability("internal", "output_payload", state)
        
        state["final_payload"] = {
            "ticket_id": state.get("ticket_id"),
            "customer_name": state.get("customer_name"),
            "status": "closed" if state.get("ticket_closed") else "escalated",
            "resolution": state.get("generated_response"),
            "escalated": state.get("escalation_required", False),
            "solution_score": state.get("solution_score"),
            "completed_stages": state.get("completed_stages", [])
        }
        
        state["current_stage"] = "COMPLETE"
        state["completed_stages"] = state.get("completed_stages", []) + ["COMPLETE"]
        return state
    
    def run(self, input_payload: InputPayload) -> Dict[str, Any]:
        """Execute the customer support workflow sequentially"""
        print("[AGENT] Langie Agent Starting Customer Support Workflow")
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
            "decision_rationale": None,
            "ticket_updated": False,
            "ticket_closed": False,
            "generated_response": None,
            "api_calls_executed": [],
            "notifications_sent": [],
            "final_payload": None,
            "execution_log": []
        }
        
        # Execute stages sequentially
        for stage_name, stage_func in self.stages:
            state = stage_func(state)
        
        print("=" * 60)
        print("[COMPLETE] Workflow Complete!")
        return state