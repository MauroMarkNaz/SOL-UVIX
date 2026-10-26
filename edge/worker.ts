/**
 * Cloudflare Edge Worker for SOL-UVIX Protocol (uvix.leaksnipe.win)
 * Ingests, validates, verifies payload hashes, and routes Solana UVIX slugs.
 */

export interface Env {
  WECRYPTO_D1: D1Database;
  SCALPER_D1: D1Database;
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
        if (env.WECRYPTO_D1) {
          ctx.waitUntil(
            env.WECRYPTO_D1.prepare(
              "INSERT OR IGNORE INTO spot_bars_1s (token, price, volume, timestamp) VALUES (?, ?, ?, ?)"
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
