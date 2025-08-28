from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
import time
from typing import Callable, Dict, Any, Optional

# --- FastMCP imports (official Python library) ---
# Docs/quickstart: modelcontextprotocol.io & gofastmcp.com
from fastmcp import FastMCP  # type: ignore


class FastMCPCompat:
    """
    A tiny wrapper around FastMCP that:
      1) Registers tools via FastMCP's decorator.
      2) Keeps a local registry so we can call tools by name from a plain HTTP endpoint.
    This lets us preserve the old /mcp POST contract while adopting FastMCP.
    """

    def __init__(self, name: str):
        self.name = name
        self.mcp = FastMCP(name)
        self._registry: Dict[str, Callable[..., Any]] = {}

    def tool(self):
        """
        Decorator that registers with FastMCP AND our local registry (by function name).
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            # Register with FastMCP
            self.mcp.tool()(func)
            # Register for our compatibility endpoint
            self._registry[func.__name__] = func
            return func

        return decorator

    def call_tool(self, tool_name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """
        Compatibility call that resolves and invokes the underlying Python function.
        Mirrors your original behavior: if args mismatch, try a no-arg call.
        """
        if tool_name not in self._registry:
            return {"error": f"Tool {tool_name} not found"}
        func = self._registry[tool_name]
        try:
            return func(**(args or {}))
        except TypeError:
            # Fallback for tools that take no arguments
            return func()


# --- Instantiate two FastMCP-compatible servers (COMMON and ATLAS) ---
common_server = FastMCPCompat("COMMON")
atlas_server = FastMCPCompat("ATLAS")

# -------------------- COMMON tools -------------------- #
@common_server.tool()
def parse_request_text(query: str = "") -> Dict[str, Any]:
    """Parse freeform request text and infer intent/urgency."""
    return {"intent": "billing_inquiry", "urgency": "medium"}


@common_server.tool()
def normalize_fields(priority: str = "", ticket_id: str = "") -> Dict[str, Any]:
    """Normalize inbound fields to internal schema."""
    return {"priority": "high", "ticket_id": "TKT-12345"}


@common_server.tool()
def add_flags_calculations() -> Dict[str, Any]:
    """Compute derived flags and scores for routing."""
    return {"sla_risk": "low", "priority_score": 65}


@common_server.tool()
def solution_evaluation() -> Dict[str, Any]:
    """Evaluate a proposed solution."""
    return {"score": 85, "confidence": "high"}


@common_server.tool()
def response_generation(customer_name: str = "Customer") -> Dict[str, Any]:
    """Draft a customer-facing response."""
    return {"response": f"Dear {customer_name}, inquiry resolved."}


# -------------------- ATLAS tools -------------------- #
@atlas_server.tool()
def extract_entities() -> Dict[str, Any]:
    """Extract key entities from the conversation."""
    return {"account_id": "ACC123456", "product": "Premium Plan"}


@atlas_server.tool()
def enrich_records() -> Dict[str, Any]:
    """Enrich entities with CRM data."""
    return {"customer_tier": "gold", "previous_tickets": 2}


@atlas_server.tool()
def clarify_question() -> Dict[str, Any]:
    """Generate a clarifying question for the user."""
    return {"question": "Please provide account number?"}


@atlas_server.tool()
def extract_answer() -> Dict[str, Any]:
    """Extract a direct answer from prior messages."""
    return {"answer": "ACC123456", "confidence": 0.95}


@atlas_server.tool()
def knowledge_base_search() -> Dict[str, Any]:
    """Search internal KB and return relevant hits."""
    return {"results": [{"title": "Billing FAQ", "relevance": 0.9}]}


@atlas_server.tool()
def escalation_decision(solution_score: int = 85) -> Dict[str, Any]:
    """Decide whether to escalate based on a score threshold."""
    return {"escalate": solution_score < 90, "reason": "Score threshold"}


@atlas_server.tool()
def update_ticket() -> Dict[str, Any]:
    """Update the active ticket with latest data."""
    return {"updated": True, "status": "in_progress"}


@atlas_server.tool()
def close_ticket() -> Dict[str, Any]:
    """Close the active ticket with a resolution."""
    return {"closed": True, "resolution": "Resolved"}


@atlas_server.tool()
def execute_api_calls() -> Dict[str, Any]:
    """Execute outbound API actions (idempotent)."""
    return {"api_calls": ["billing_update"], "status": "success"}


@atlas_server.tool()
def trigger_notifications() -> Dict[str, Any]:
    """Trigger customer and internal notifications."""
    return {"notifications": ["email_sent"], "status": "success"}


# -------------------- HTTP compatibility layer -------------------- #
class MCPHandler(BaseHTTPRequestHandler):
    """
    A minimal HTTP bridge that forwards POST /mcp calls to the appropriate
    FastMCPCompat instance (COMMON or ATLAS), preserving the old request/response shape.

    Expected request JSON:
      {
        "params": {
          "name": "<tool_name>",
          "arguments": { ... }   # optional
        }
      }
    """

    # Disable default noisy logging
    def log_message(self, format: str, *args) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        pass

    def do_POST(self):  # noqa: N802 (BaseHTTPRequestHandler API)
        if self.path != "/mcp":
            self.send_response(404)
            self.end_headers()
            return

        # Read body
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(content_length)

        try:
            request = json.loads(body.decode("utf-8"))
            params = request.get("params") or {}
            tool_name = params.get("name")
            args = params.get("arguments") or {}

            if not tool_name or not isinstance(tool_name, str):
                raise ValueError("Invalid or missing params.name")

            # Route to the correct FastMCPCompat instance
            target: FastMCPCompat = getattr(self.server, "mcp_server", None)  # type: ignore[attr-defined]
            if target is None:
                raise RuntimeError("Server misconfiguration: missing mcp_server")

            result = target.call_tool(tool_name, args)

            response = {"result": result}
            payload = json.dumps(response).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        except Exception as e:
            # Keep the shape simple, avoid leaking internals
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Internal Server Error"}).encode("utf-8"))


def start_server(port: int, mcp_server: FastMCPCompat, server_type: str):
    httpd = HTTPServer(("localhost", port), MCPHandler)
    # Attach which MCP instance this server should use
    httpd.mcp_server = mcp_server  # type: ignore[attr-defined]
    httpd.server_type = server_type  # for parity with your original logs
    print(f"[SERVER] {server_type} FastMCP server started on port {port}")
    httpd.serve_forever()


if __name__ == "__main__":
    common_thread = threading.Thread(
        target=start_server, args=(8001, common_server, "COMMON"), daemon=True
    )
    atlas_thread = threading.Thread(
        target=start_server, args=(8002, atlas_server, "ATLAS"), daemon=True
    )

    common_thread.start()
    atlas_thread.start()

    print("[SERVER] Both FastMCP-style servers running")
    print("[SERVER] POST /mcp with {'params': {'name': '<tool>', 'arguments': {...}}}")
    print("[SERVER] Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down servers")
