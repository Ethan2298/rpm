import { NextRequest, NextResponse } from "next/server";
import { timingSafeCompare } from "@/lib/oauth/hmac";

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const clientId = params.get("client_id");
  const redirectUri = params.get("redirect_uri");
  const responseType = params.get("response_type");
  const state = params.get("state");
  const codeChallenge = params.get("code_challenge");
  const codeChallengeMethod = params.get("code_challenge_method");

  if (responseType !== "code") {
    return NextResponse.json(
      { error: "unsupported_response_type" },
      { status: 400 },
    );
  }

  if (!clientId) {
    return NextResponse.json({ error: "invalid_client" }, { status: 400 });
  }

  if (!redirectUri) {
    return NextResponse.json(
      { error: "invalid_request", error_description: "redirect_uri required" },
      { status: 400 },
    );
  }

  const loginUrl = new URL("/oauth/authorize", request.url);
  loginUrl.searchParams.set("redirect_uri", redirectUri);
  if (state) loginUrl.searchParams.set("state", state);
  if (codeChallenge) loginUrl.searchParams.set("code_challenge", codeChallenge);
  if (codeChallengeMethod) loginUrl.searchParams.set("code_challenge_method", codeChallengeMethod);

  return NextResponse.redirect(loginUrl);
}
