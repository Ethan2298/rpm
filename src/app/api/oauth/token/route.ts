import { NextRequest, NextResponse } from "next/server";
import {
  OAUTH_CLIENT_ID,
  OAUTH_CLIENT_SECRET,
  MCP_AUTH_TOKEN,
} from "@/lib/oauth/config";
import { verifyCode, timingSafeCompare } from "@/lib/oauth/hmac";

export async function POST(request: NextRequest) {
  const contentType = request.headers.get("content-type") || "";

  let grantType: string | null = null;
  let code: string | null = null;
  let clientId: string | null = null;
  let clientSecret: string | null = null;
  let codeVerifier: string | null = null;

  if (contentType.includes("application/x-www-form-urlencoded")) {
    const formData = await request.formData();
    grantType = formData.get("grant_type") as string | null;
    code = formData.get("code") as string | null;
    clientId = formData.get("client_id") as string | null;
    clientSecret = formData.get("client_secret") as string | null;
    codeVerifier = formData.get("code_verifier") as string | null;
  } else {
    const body = await request.json();
    grantType = body.grant_type;
    code = body.code;
    clientId = body.client_id;
    clientSecret = body.client_secret;
    codeVerifier = body.code_verifier;
  }

  // Client credentials grant — server-to-server auth (e.g. Claude.ai connector)
  if (grantType === "client_credentials") {
    if (
      !clientId ||
      !clientSecret ||
      !timingSafeCompare(clientSecret, OAUTH_CLIENT_SECRET)
    ) {
      return NextResponse.json({ error: "invalid_client" }, { status: 401 });
    }

    return NextResponse.json({
      access_token: MCP_AUTH_TOKEN,
      token_type: "bearer",
      expires_in: 31536000,
    });
  }

  if (grantType !== "authorization_code") {
    return NextResponse.json(
      { error: "unsupported_grant_type" },
      { status: 400 },
    );
  }

  if (!clientId) {
    return NextResponse.json({ error: "invalid_client" }, { status: 401 });
  }

  if (!code) {
    return NextResponse.json(
      { error: "invalid_request", error_description: "code required" },
      { status: 400 },
    );
  }

  const result = verifyCode(code, codeVerifier || undefined);
  if (!result.valid) {
    return NextResponse.json(
      { error: "invalid_grant", error_description: result.reason },
      { status: 400 },
    );
  }

  return NextResponse.json({
    access_token: MCP_AUTH_TOKEN,
    token_type: "bearer",
    expires_in: 31536000,
  });
}
