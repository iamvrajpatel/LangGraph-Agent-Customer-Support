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
