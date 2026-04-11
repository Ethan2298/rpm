import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";
import { registerTools } from "@/lib/ghl/tools";
import { NextRequest } from "next/server";

const MCP_AUTH_TOKEN = process.env.MCP_AUTH_TOKEN!;

function authenticate(request: NextRequest): boolean {
  if (!MCP_AUTH_TOKEN) return false;
  const auth = request.headers.get("authorization");
  if (!auth) return false;
  const token = auth.replace(/^Bearer\s+/i, "");
  return token === MCP_AUTH_TOKEN;
}

async function handleMCP(request: NextRequest): Promise<Response> {
  if (!authenticate(request)) {
    const origin = new URL(request.url).origin;
    return new Response(
      JSON.stringify({
        error: "unauthorized",
        hint: MCP_AUTH_TOKEN ? "token_mismatch" : "token_not_configured",
      }),
      {
        status: 401,
        headers: {
          "Content-Type": "application/json",
          "WWW-Authenticate": `Bearer resource_metadata="${origin}/.well-known/oauth-protected-resource"`,
        },
      },
    );
  }

  const server = new McpServer({
    name: "Jimmy — Dealership Operations",
    version: "1.0.0",
  });
  registerTools(server);

  // Stateless mode: fresh transport per request, no session tracking needed
  const transport = new WebStandardStreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  await server.connect(transport);

  return transport.handleRequest(request);
}

export async function POST(request: NextRequest) {
  return handleMCP(request);
}

export async function GET(request: NextRequest) {
  return handleMCP(request);
}

export async function DELETE(request: NextRequest) {
  return handleMCP(request);
}
