export interface Env {
  AI: any;
  AI_GATEWAY_URL?: string;
  DEFAULT_MODEL?: string;
  LARGE_MODEL?: string;
}

const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, x-api-key, X-Requested-With, cf-aig-authorization",
  "Access-Control-Max-Age": "86400",
};

const SUPPORTED_MODELS = [
  { id: "mistral-large-latest", owned_by: "mistralai" },
  { id: "codestral-latest", owned_by: "mistralai" },
  { id: "mistral-small-latest", owned_by: "mistralai" },
  { id: "mistral-7b-instruct", owned_by: "mistralai" },
  { id: "open-mistral-7b", owned_by: "mistralai" },
  { id: "@cf/mistralai/mistral-small-3.1-24b-instruct", owned_by: "cloudflare" },
  { id: "@cf/mistral/mistral-7b-instruct-v0.2-lora", owned_by: "cloudflare" },
  { id: "@cf/meta/llama-3.3-70b-instruct-fp8-fast", owned_by: "cloudflare" },
];

function resolveWorkersAiModel(requestedModel?: string, env?: Env): string {
  if (!requestedModel) return env?.DEFAULT_MODEL || "@cf/mistralai/mistral-small-3.1-24b-instruct";
  const m = requestedModel.toLowerCase();
  if (m === "mistral-7b-instruct" || m === "open-mistral-7b" || m.includes("7b")) {
    return "@cf/mistral/mistral-7b-instruct-v0.2-lora";
  }
  if (m.startsWith("@cf/")) {
    return requestedModel;
  }
  return env?.DEFAULT_MODEL || "@cf/mistralai/mistral-small-3.1-24b-instruct";
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    if (req.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const url = new URL(req.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    // 1. Health & Root Information
    if (path === "" || path === "/" || path === "/health") {
      return new Response(
        JSON.stringify(
          {
            status: "active",
            service: "mistral.leaksnipe.win",
            provider: "Cloudflare Workers AI + AI Gateway",
            compatibility: "Mistral AI / OpenAI v1",
            default_model: env.DEFAULT_MODEL || "@cf/mistral/mistral-7b-instruct-v0.2",
            large_model: env.LARGE_MODEL || "@cf/mistralai/mistral-large-2407",
            models_endpoint: "https://mistral.leaksnipe.win/v1/models",
            chat_endpoint: "https://mistral.leaksnipe.win/v1/chat/completions",
            timestamp: new Date().toISOString(),
          },
          null,
          2
        ),
        {
          headers: {
            "Content-Type": "application/json",
            ...CORS_HEADERS,
          },
        }
      );
    }

    // 2. Models List (/v1/models or /models)
    if (path === "/v1/models" || path === "/models") {
      const modelList = {
        object: "list",
        data: SUPPORTED_MODELS.map((m) => ({
          id: m.id,
          object: "model",
          created: Math.floor(Date.now() / 1000),
          owned_by: m.owned_by,
          permission: [],
          root: m.id,
          parent: null,
        })),
      };
      return new Response(JSON.stringify(modelList, null, 2), {
        headers: {
          "Content-Type": "application/json",
          ...CORS_HEADERS,
        },
      });
    }

    // 3. Chat Completions (/v1/chat/completions or /chat/completions)
    if (path === "/v1/chat/completions" || path === "/chat/completions") {
      if (req.method !== "POST") {
        return new Response(JSON.stringify({ error: { message: "Method not allowed" } }), {
          status: 405,
          headers: { "Content-Type": "application/json", ...CORS_HEADERS },
        });
      }

      let body: any;
      try {
        body = await req.json();
      } catch (err: any) {
        return new Response(JSON.stringify({ error: { message: "Invalid JSON body" } }), {
          status: 400,
          headers: { "Content-Type": "application/json", ...CORS_HEADERS },
        });
      }

      const stream = Boolean(body.stream);
      const targetModel = resolveWorkersAiModel(body.model, env);
      const chatId = "chatcmpl-" + crypto.randomUUID().slice(0, 12);
      const created = Math.floor(Date.now() / 1000);

      // If auth token provided and user explicitly prefers external gateway proxy
      const authHeader = req.headers.get("Authorization");
      const useGateway = req.headers.get("x-use-gateway") === "true";
      if (useGateway && authHeader && env.AI_GATEWAY_URL) {
        try {
          const gwUrl = `${env.AI_GATEWAY_URL}/mistral/v1/chat/completions`;
          const gwRes = await fetch(gwUrl, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: authHeader,
            },
            body: JSON.stringify(body),
          });
          if (gwRes.ok) {
            const gwOut = new Response(gwRes.body, gwRes);
            for (const [k, v] of Object.entries(CORS_HEADERS)) {
              gwOut.headers.set(k, v);
            }
            return gwOut;
          }
        } catch (_) {
          // Fall back to Workers AI
        }
      }

      // Format messages for Workers AI
      const messages = (body.messages || []).map((m: any) => ({
        role: m.role || "user",
        content: typeof m.content === "string" ? m.content : JSON.stringify(m.content),
      }));

      // Workers AI Execution
      try {
        if (stream) {
          const aiStream = await env.AI.run(targetModel, {
            messages,
            stream: true,
            max_tokens: body.max_tokens || 2048,
            temperature: body.temperature ?? 0.7,
          });

          // Transform Cloudflare AI stream to OpenAI/Mistral SSE format
          const { readable, writable } = new TransformStream();
          const writer = writable.getWriter();
          const encoder = new TextEncoder();
          const decoder = new TextDecoder();

          (async () => {
            try {
              const reader = (aiStream as ReadableStream).getReader();
              let buffer = "";

              while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                  const trimmed = line.trim();
                  if (!trimmed || !trimmed.startsWith("data:")) continue;
                  const dataStr = trimmed.slice(5).trim();
                  if (dataStr === "[DONE]") continue;

                  try {
                    const parsed = JSON.parse(dataStr);
                    const token = parsed.response || "";
                    if (token) {
                      const chunk = {
                        id: chatId,
                        object: "chat.completion.chunk",
                        created,
                        model: body.model || targetModel,
                        choices: [
                          {
                            index: 0,
                            delta: { content: token },
                            finish_reason: null,
                          },
                        ],
                      };
                      await writer.write(encoder.encode(`data: ${JSON.stringify(chunk)}\n\n`));
                    }
                  } catch (_) {}
                }
              }

              // Final stop chunk and DONE
              const stopChunk = {
                id: chatId,
                object: "chat.completion.chunk",
                created,
                model: body.model || targetModel,
                choices: [
                  {
                    index: 0,
                    delta: {},
                    finish_reason: "stop",
                  },
                ],
              };
              await writer.write(encoder.encode(`data: ${JSON.stringify(stopChunk)}\n\n`));
              await writer.write(encoder.encode("data: [DONE]\n\n"));
            } catch (err: any) {
              const errPayload = { error: { message: err?.message || "Stream error" } };
              await writer.write(encoder.encode(`data: ${JSON.stringify(errPayload)}\n\n`));
            } finally {
              await writer.close();
            }
          })();

          return new Response(readable, {
            headers: {
              "Content-Type": "text/event-stream; charset=utf-8",
              "Cache-Control": "no-cache, no-transform",
              Connection: "keep-alive",
              ...CORS_HEADERS,
            },
          });
        } else {
          const aiRes = await env.AI.run(targetModel, {
            messages,
            stream: false,
            max_tokens: body.max_tokens || 2048,
            temperature: body.temperature ?? 0.7,
          });

          const content = aiRes.response || "";
          const responsePayload = {
            id: chatId,
            object: "chat.completion",
            created,
            model: body.model || targetModel,
            choices: [
              {
                index: 0,
                message: {
                  role: "assistant",
                  content,
                },
                finish_reason: "stop",
              },
            ],
            usage: {
              prompt_tokens: 0,
              completion_tokens: 0,
              total_tokens: 0,
            },
          };

          return new Response(JSON.stringify(responsePayload), {
            headers: {
              "Content-Type": "application/json",
              ...CORS_HEADERS,
            },
          });
        }
      } catch (err: any) {
        return new Response(
          JSON.stringify({
            error: {
              message: err?.message || "Workers AI execution error",
              model: targetModel,
            },
          }),
          {
            status: 500,
            headers: { "Content-Type": "application/json", ...CORS_HEADERS },
          }
        );
      }
    }

    // 4. Embeddings (/v1/embeddings or /embeddings)
    if (path === "/v1/embeddings" || path === "/embeddings") {
      let body: any = {};
      try {
        body = await req.json();
      } catch (_) {}

      const input = Array.isArray(body.input) ? body.input : [body.input || ""];
      try {
        const embeddingsRes = await env.AI.run("@cf/baai/bge-base-en-v1.5", {
          text: input,
        });
        const vectors = embeddingsRes.data || [];
        const payload = {
          object: "list",
          data: vectors.map((vec: any, idx: number) => ({
            object: "embedding",
            embedding: vec,
            index: idx,
          })),
          model: body.model || "@cf/baai/bge-base-en-v1.5",
          usage: { prompt_tokens: 0, total_tokens: 0 },
        };
        return new Response(JSON.stringify(payload), {
          headers: { "Content-Type": "application/json", ...CORS_HEADERS },
        });
      } catch (err: any) {
        return new Response(
          JSON.stringify({ error: { message: err?.message || "Embedding error" } }),
          {
            status: 500,
            headers: { "Content-Type": "application/json", ...CORS_HEADERS },
          }
        );
      }
    }

    return new Response(JSON.stringify({ error: { message: "Not found", path } }), {
      status: 404,
      headers: { "Content-Type": "application/json", ...CORS_HEADERS },
    });
  },
};
