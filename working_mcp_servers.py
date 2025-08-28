from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
import time

class FastMCPServer:
    def __init__(self, name):
        self.name = name
        self.tools = {}
    
    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func
        return decorator
    
    def call_tool(self, tool_name, args):
        if tool_name in self.tools:
            try:
                return self.tools[tool_name](**args)
            except TypeError:
                return self.tools[tool_name]()
        return {"error": f"Tool {tool_name} not found"}

common_server = FastMCPServer("COMMON")
atlas_server = FastMCPServer("ATLAS")

@common_server.tool()
def parse_request_text(query=""):
    return {"intent": "billing_inquiry", "urgency": "medium"}

@common_server.tool()
def normalize_fields(priority="", ticket_id=""):
    return {"priority": "high", "ticket_id": "TKT-12345"}

@common_server.tool()
def add_flags_calculations():
    return {"sla_risk": "low", "priority_score": 65}

@common_server.tool()
def solution_evaluation():
    return {"score": 85, "confidence": "high"}

@common_server.tool()
def response_generation(customer_name="Customer"):
    return {"response": f"Dear {customer_name}, inquiry resolved."}

@atlas_server.tool()
def extract_entities():
    return {"account_id": "ACC123456", "product": "Premium Plan"}

@atlas_server.tool()
def enrich_records():
    return {"customer_tier": "gold", "previous_tickets": 2}

@atlas_server.tool()
def clarify_question():
    return {"question": "Please provide account number?"}

@atlas_server.tool()
def extract_answer():
    return {"answer": "ACC123456", "confidence": 0.95}

@atlas_server.tool()
def knowledge_base_search():
    return {"results": [{"title": "Billing FAQ", "relevance": 0.9}]}

@atlas_server.tool()
def escalation_decision(solution_score=85):
    return {"escalate": solution_score < 90, "reason": "Score threshold"}

@atlas_server.tool()
def update_ticket():
    return {"updated": True, "status": "in_progress"}

@atlas_server.tool()
def close_ticket():
    return {"closed": True, "resolution": "Resolved"}

@atlas_server.tool()
def execute_api_calls():
    return {"api_calls": ["billing_update"], "status": "success"}

@atlas_server.tool()
def trigger_notifications():
    return {"notifications": ["email_sent"], "status": "success"}

class MCPHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/mcp':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                request = json.loads(post_data.decode('utf-8'))
                tool_name = request['params']['name']
                args = request['params']['arguments']
                
                if self.server.server_type == 'COMMON':
                    result = common_server.call_tool(tool_name, args)
                else:
                    result = atlas_server.call_tool(tool_name, args)
                
                response = {"result": result}
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
                
            except Exception as e:
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def start_server(port, server_type):
    server = HTTPServer(('localhost', port), MCPHandler)
    server.server_type = server_type
    print(f"[SERVER] {server_type} FastMCP server started on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    common_thread = threading.Thread(target=start_server, args=(8001, 'COMMON'), daemon=True)
    atlas_thread = threading.Thread(target=start_server, args=(8002, 'ATLAS'), daemon=True)
    
    common_thread.start()
    atlas_thread.start()
    
    print("[SERVER] Both FastMCP-style servers running")
    print("[SERVER] Press Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down servers")