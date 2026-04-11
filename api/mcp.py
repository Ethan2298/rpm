"""
Vercel serverless function — serves the GHL MCP server over Streamable HTTP.

Claude Desktop / claude.ai connect to: https://<your-app>.vercel.app/api/mcp
"""

import os
import sys

# Project root on sys.path so mcp_servers package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from mcp.server.transport_security import TransportSecuritySettings
from mcp_servers.ghl.server import mcp

# --- Serverless-friendly settings ---
mcp.settings.stateless_http = True
mcp.settings.streamable_http_path = "/api/mcp"

# Disable DNS rebinding protection — Vercel handles host validation at the edge.
mcp.settings.transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
)

def _normalize_token(value: str | None) -> str | None:
    if value is None:
        return None
    token = value.strip()
    return token or None


MCP_AUTH_TOKEN = _normalize_token(os.environ.get("MCP_AUTH_TOKEN"))


class BearerAuthMiddleware:
    def __init__(self, app: ASGIApp, token: str | None):
        self.app = app
        self.token = _normalize_token(token)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http" and self.token:
            request = Request(scope)
            auth = request.headers.get("authorization", "")
            incoming_token = auth[7:].strip() if auth.startswith("Bearer ") else ""
            if incoming_token != self.token:
                response = JSONResponse(
                    {"error": "Unauthorized"}, status_code=401
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


# --- Build the Starlette ASGI app with auth ---
app = BearerAuthMiddleware(mcp.streamable_http_app(), MCP_AUTH_TOKEN)
