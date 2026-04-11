import { createHmac, createHash, randomBytes, timingSafeEqual } from "crypto";
import { OAUTH_HMAC_SECRET, CODE_EXPIRY_MS } from "./config";

export function generateCode(codeChallenge?: string): string {
  const timestamp = Date.now().toString(16);
  const payload = codeChallenge ? `${timestamp}:${codeChallenge}` : timestamp;
  const signature = createHmac("sha256", OAUTH_HMAC_SECRET)
    .update(payload)
    .digest("hex");
  return `${payload}.${signature}`;
}

export function verifyCode(
  code: string,
  codeVerifier?: string,
): {
  valid: boolean;
  reason?: string;
} {
  const dotIndex = code.lastIndexOf(".");
  if (dotIndex === -1) {
    return { valid: false, reason: "malformed code" };
  }

  const payload = code.slice(0, dotIndex);
  const signature = code.slice(dotIndex + 1);

  const expected = createHmac("sha256", OAUTH_HMAC_SECRET)
    .update(payload)
    .digest("hex");

  const sigBuffer = Buffer.from(signature, "hex");
  const expectedBuffer = Buffer.from(expected, "hex");

  if (sigBuffer.length !== expectedBuffer.length) {
    return { valid: false, reason: "invalid signature" };
  }

  if (!timingSafeEqual(sigBuffer, expectedBuffer)) {
    return { valid: false, reason: "invalid signature" };
  }

  // Parse timestamp (before optional :code_challenge)
  const colonIndex = payload.indexOf(":");
  const timestampHex = colonIndex === -1 ? payload : payload.slice(0, colonIndex);
  const embeddedChallenge = colonIndex === -1 ? null : payload.slice(colonIndex + 1);

  const issued = parseInt(timestampHex, 16);
  if (Date.now() - issued > CODE_EXPIRY_MS) {
    return { valid: false, reason: "code expired" };
  }

  // PKCE verification
  if (embeddedChallenge && codeVerifier) {
    const computedChallenge = createHash("sha256")
      .update(codeVerifier)
      .digest("base64url");
    if (!timingSafeCompare(computedChallenge, embeddedChallenge)) {
      return { valid: false, reason: "invalid code_verifier" };
    }
  } else if (embeddedChallenge && !codeVerifier) {
    return { valid: false, reason: "code_verifier required" };
  }

  return { valid: true };
}

export function timingSafeCompare(a: string, b: string): boolean {
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  if (bufA.length !== bufB.length) return false;
  return timingSafeEqual(bufA, bufB);
}

export function generateClientId(): string {
  const nonce = randomBytes(16).toString("hex");
  const sig = createHmac("sha256", OAUTH_HMAC_SECRET)
    .update(nonce)
    .digest("hex")
    .slice(0, 16);
  return `jimmy_${nonce}.${sig}`;
}

export function verifyClientId(clientId: string): boolean {
  if (!clientId.startsWith("jimmy_")) return false;
  const rest = clientId.slice(6);
  const dotIndex = rest.lastIndexOf(".");
  if (dotIndex === -1) return false;
  const nonce = rest.slice(0, dotIndex);
  const sig = rest.slice(dotIndex + 1);
  const expected = createHmac("sha256", OAUTH_HMAC_SECRET)
    .update(nonce)
    .digest("hex")
    .slice(0, 16);
  return timingSafeCompare(sig, expected);
}
