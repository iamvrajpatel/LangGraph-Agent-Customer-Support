import asyncio
import aiohttp
from typing import Dict, Any

class FastMCPClient:
    """FastMCP Client for real MCP server communication"""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
    
    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call tool on FastMCP server"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": kwargs
                    }
                }
                async with session.post(f"{self.server_url}/mcp", json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("result", {})
                    else:
                        return {"error": f"HTTP {response.status}"}
        except Exception as e:
            # Fallback to mock data for demo
            raise Exception("Connect MCP Server Firrst!!")
            # return self._mock_response(tool_name, kwargs)
    
    def _mock_response(self, tool_name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback mock responses when servers unavailable"""
        mock_responses = {
            "parse_request_text": {"intent": "billing_inquiry", "urgency": "medium"},
            "normalize_fields": {"priority": "high", "ticket_id": "TKT-12345"},
            "add_flags_calculations": {"sla_risk": "low", "priority_score": 65},
            "solution_evaluation": {"score": 85, "confidence": "high"},
            "response_generation": {"response": f"Dear {kwargs.get('customer_name', 'Customer')}, inquiry resolved."},
            "extract_entities": {"account_id": "ACC123456", "product": "Premium Plan"},
            "enrich_records": {"customer_tier": "gold", "previous_tickets": 2},
            "clarify_question": {"question": "Please provide account number?"},
            "extract_answer": {"answer": "ACC123456", "confidence": 0.95},
            "knowledge_base_search": {"results": [{"title": "Billing FAQ", "relevance": 0.9}]},
            "escalation_decision": {"escalate": (kwargs.get('solution_score') or 85) < 90, "reason": "Score threshold"},
            "update_ticket": {"updated": True, "status": "in_progress"},
            "close_ticket": {"closed": True, "resolution": "Resolved"},
            "execute_api_calls": {"api_calls": ["billing_update"], "status": "success"},
            "trigger_notifications": {"notifications": ["email_sent"], "status": "success"}
        }
        return mock_responses.get(tool_name, {"result": f"{tool_name} executed"})
    
    
class MCPClientManager:
    """Manages FastMCP clients for different servers"""
    
    def __init__(self):
        self.clients = {
            "COMMON": FastMCPClient("http://localhost:8001"),
            "ATLAS": FastMCPClient("http://localhost:8002")
        }
    
    def call_ability(self, server_name: str, ability_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Call ability on specified server"""
        client = self.clients.get(server_name)
        if not client:
            return {"error": f"Server {server_name} not found"}
        
        # Run async call in sync context
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(client.call_tool(ability_name, **payload))