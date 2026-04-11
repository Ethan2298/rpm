import { NextRequest, NextResponse } from "next/server";
import { generateClientId } from "@/lib/oauth/hmac";

export async function POST(request: NextRequest) {
  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "invalid_client_metadata", error_description: "invalid JSON" },
      { status: 400 },
    );
  }

  const redirectUris = body.redirect_uris;
  if (!Array.isArray(redirectUris) || redirectUris.length === 0) {
    return NextResponse.json(
      { error: "invalid_client_metadata", error_description: "redirect_uris required" },
      { status: 400 },
    );
  }

  for (const uri of redirectUris) {
    if (typeof uri !== "string") {
      return NextResponse.json(
        { error: "invalid_client_metadata", error_description: "redirect_uris must be strings" },
        { status: 400 },
      );
    }
    const parsed = new URL(uri);
    const isLocalhost = parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1";
    if (!isLocalhost && parsed.protocol !== "https:") {
      return NextResponse.json(
        { error: "invalid_client_metadata", error_description: "redirect_uris must be localhost or HTTPS" },
        { status: 400 },
      );
    }
  }

  const clientId = generateClientId();

  return NextResponse.json({
    client_id: clientId,
    client_name: (body.client_name as string) || "MCP Client",
    redirect_uris: redirectUris,
    token_endpoint_auth_method: "none",
  });
}
