from typing import Dict, Any, List, Optional
from pydantic import BaseModel

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict

class CustomerSupportState(TypedDict):
    """State model for customer support workflow"""
    # Input payload
    customer_name: str
    email: str
    query: str
    priority: str
    ticket_id: str
    
    # Stage tracking
    current_stage: str
    completed_stages: List[str]
    
    # Processed data
    parsed_request: Optional[Dict[str, Any]]
    extracted_entities: Optional[Dict[str, Any]]
    normalized_data: Optional[Dict[str, Any]]
    enriched_data: Optional[Dict[str, Any]]
    flags_calculations: Optional[Dict[str, Any]]
    
    # Human interaction
    clarification_needed: bool
    clarification_question: Optional[str]
    customer_response: Optional[str]
    
    # Knowledge retrieval
    kb_results: Optional[List[Dict[str, Any]]]
    
    # Decision making
    solution_score: Optional[int]
    escalation_required: bool
    decision_rationale: Optional[str]
    
    # Updates and actions
    ticket_updated: bool
    ticket_closed: bool
    generated_response: Optional[str]
    api_calls_executed: List[str]
    notifications_sent: List[str]
    
    # Final output
    final_payload: Optional[Dict[str, Any]]
    
    # Logs
    execution_log: List[str]

class InputPayload(BaseModel):
    customer_name: str
    email: str
    query: str
    priority: str
    ticket_id: str