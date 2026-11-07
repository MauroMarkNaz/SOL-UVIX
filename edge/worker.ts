/**
 * Cloudflare Edge Worker for SOL-UVIX Protocol
 * Ingests, validates, verifies payload hashes, and routes Solana UVIX slugs.
 */

export interface Env {
  UVIX_TELEMETRY_D1?: D1Database;
  UVIX_STATE_D1?: D1Database;
  WECRYPTO_D1?: D1Database;
  AUTH_SECRET?: string;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // Health check
    if (url.pathname === "/health" || url.pathname === "/") {
      return new Response(JSON.stringify({ status: "online", protocol: "UVIX-RI-1.0", network: "solana-mainnet" }), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // Slug ingestion endpoint
    if (url.pathname === "/uvix" || url.pathname === "/uvix/solana") {
      if (request.method !== "POST") {
        return new Response("Method Not Allowed", { status: 405 });
      }

      if (!env.AUTH_SECRET?.trim()) {
        return new Response(JSON.stringify({
          error: "Ingestion authentication is not configured"
        }), { status: 503, headers: { "Content-Type": "application/json" } });
      }

      if (!await hasValidBearerToken(request, env.AUTH_SECRET)) {
        return new Response(JSON.stringify({ error: "Unauthorized" }), {
          status: 401,
          headers: {
            "Content-Type": "application/json",
            "WWW-Authenticate": "Bearer"
          }
        });
      }

      try {
        const body = await request.json() as { envelope?: string };
        const envelope = body.envelope;
        if (!envelope || !envelope.startsWith("UVIX::") || !envelope.endsWith("::END")) {
          return new Response(JSON.stringify({ error: "Invalid UVIX envelope framing" }), {
            status: 400,
            headers: { "Content-Type": "application/json" }
          });
        }

        // Extract base64 and parse
        const b64 = envelope.slice(6, -5);
        const jsonStr = atob(b64);
        const slug = JSON.parse(jsonStr);

        // Verify SHA-256 payload integrity hash
        const canonicalJson = canonicalStringify(slug.raw_payload);
        const hashBuf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonicalJson));
        const hashHex = Array.from(new Uint8Array(hashBuf))
          .map(b => b.toString(16).padStart(2, "0"))
          .join("");

        if (hashHex !== slug.payload_hash) {
          return new Response(JSON.stringify({
            error: "Integrity hash mismatch",
            expected: hashHex,
            received: slug.payload_hash
          }), { status: 422, headers: { "Content-Type": "application/json" } });
        }

        // Log or buffer to D1 if available
        const d1Db = env.UVIX_TELEMETRY_D1 || env.WECRYPTO_D1;
        if (d1Db) {
          ctx.waitUntil(
            d1Db.prepare(
              "INSERT OR IGNORE INTO telemetry_slugs (token, price, volume, timestamp) VALUES (?, ?, ?, ?)"
            ).bind(
              slug.raw_payload?.mint || "SOL",
              slug.raw_payload?.data?.price_in_sol || 0,
              slug.raw_payload?.data?.virtual_sol_reserves || 0,
              Math.floor(Date.now() / 1000)
            ).run().catch(console.error)
          );
        }

        return new Response(JSON.stringify({
          success: true,
          status: "ACCEPTED",
          payload_hash: slug.payload_hash,
          source_platform: slug.source_platform,
          target_platform: slug.target_platform,
          timestamp: Date.now()
        }), {
          headers: { "Content-Type": "application/json" }
        });

      } catch (err: any) {
        return new Response(JSON.stringify({ error: err.message || "Failed to process slug" }), {
          status: 500,
          headers: { "Content-Type": "application/json" }
        });
      }
    }

    return new Response("Not Found", { status: 404 });
  }
};

async function hasValidBearerToken(request: Request, secret: string): Promise<boolean> {
  const authorization = request.headers.get("Authorization");
  if (!authorization?.startsWith("Bearer ")) return false;

  const token = authorization.slice("Bearer ".length);
  if (!token || token.length > 1024) return false;

  const encoder = new TextEncoder();
  const [expectedDigest, tokenDigest] = await Promise.all([
    crypto.subtle.digest("SHA-256", encoder.encode(secret)),
    crypto.subtle.digest("SHA-256", encoder.encode(token))
  ]);
  const expected = new Uint8Array(expectedDigest);
  const actual = new Uint8Array(tokenDigest);
  let difference = 0;
  for (let index = 0; index < expected.length; index++) {
    difference |= expected[index] ^ actual[index];
  }
  return difference === 0;
}

/**
 * Deterministic JSON stringify matching Python sort_keys=True, separators=(',', ':')
 */
function canonicalStringify(obj: any): string {
  if (obj === null || typeof obj !== "object") {
    return JSON.stringify(obj);
  }
  if (Array.isArray(obj)) {
    return "[" + obj.map(canonicalStringify).join(",") + "]";
  }
  const keys = Object.keys(obj).sort();
  const pairs = keys.map(k => JSON.stringify(k) + ":" + canonicalStringify(obj[k]));
  return "{" + pairs.join(",") + "}";
}
