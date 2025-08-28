
import json
from simple_agent import LangieSimpleAgent
from state_models import InputPayload

def main():
    """Run demo with sample customer support request"""
    
    # Sample input payload
    sample_input = InputPayload(
        customer_name="John Smith",
        email="john.smith@email.com",
        query="I have a billing issue with my premium account. The charge seems incorrect for last month.",
        priority="high",
        ticket_id="12345"
    )
    
    print("[DEMO] Langie Customer Support Agent Demo (Simplified)")
    print("=" * 60)
    print("[INPUT] Input Payload:")
    print(f"   Customer: {sample_input.customer_name}")
    print(f"   Email: {sample_input.email}")
    print(f"   Query: {sample_input.query}")
    print(f"   Priority: {sample_input.priority}")
    print(f"   Ticket ID: {sample_input.ticket_id}")
    print("=" * 60)
    
    # Initialize and run agent
    agent = LangieSimpleAgent()
    result = agent.run(sample_input)
    
    # Display results
    print("\n[RESULTS] Final Results:")
    print("=" * 60)
    
    final_payload = result.get("final_payload", {})
    print("[PAYLOAD] Final Payload:")
    print(json.dumps(final_payload, indent=2))
    
    print(f"\n[SUMMARY] Execution Summary:")
    print(f"   Stages Completed: {len(result.get('completed_stages', []))}/11")
    print(f"   Current Stage: {result.get('current_stage', 'Unknown')}")
    print(f"   Escalation Required: {result.get('escalation_required', False)}")
    print(f"   Solution Score: {result.get('solution_score', 'N/A')}")
    print(f"   Ticket Status: {'Closed' if result.get('ticket_closed') else 'Open/Escalated'}")
    
    print(f"\n[LOG] Execution Log:")
    for log_entry in result.get("execution_log", []):
        print(f"   {log_entry}")
    
    print(f"\n[DETAILS] Stage Details:")
    print(f"   Parsed Request: {result.get('parsed_request')}")
    print(f"   Extracted Entities: {result.get('extracted_entities')}")
    print(f"   Flags Calculations: {result.get('flags_calculations')}")
    print(f"   Decision Rationale: {result.get('decision_rationale')}")
    
    print("\n[COMPLETE] Demo Complete!")

if __name__ == "__main__":
    main()