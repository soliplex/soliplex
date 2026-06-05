import { Type } from "@sinclair/typebox";

const BRIDGE_URL = process.env.KLANGK_BRIDGE_URL;

type ToolUpdate = (partial: {
  content: { type: "text"; text: string }[];
  details: Record<string, unknown>;
}) => void;

/**
 * Call a browser-delegate action over the streaming bridge.
 *
 * POSTs to /api/browser-delegate/stream and reads the NDJSON the backend
 * relays from the browser: zero or more {"type":"chunk","delta":...} as the
 * answer streams in, then a terminal {"type":"done","result":...} or
 * {"type":"error","error":...}. Each chunk is surfaced to the agent via
 * [onUpdate] so the user sees tokens live, and there is no single bounded
 * round-trip — the only limit is the backend's per-chunk idle timeout, so a
 * long RAG+LLM query no longer times out mid-stream.
 */
async function bridgeStream(
  action: string,
  params: Record<string, string>,
  onUpdate?: ToolUpdate,
): Promise<string> {
  const token = process.env.KLANGK_BRIDGE_TOKEN;
  const resp = await fetch(`${BRIDGE_URL}/api/browser-delegate/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, token, ...params }),
  });
  if (!resp.ok) {
    // 403 = bad/expired bridge token; 502 = no browser connected. These are
    // real conditions, not the "OIDC refresh, retry" the old code claimed.
    return `Error: bridge returned HTTP ${resp.status}`;
  }
  if (!resp.body) {
    return "Error: bridge returned no response body";
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let accumulated = "";

  const handle = (line: string): string | null => {
    let evt: { type?: string; delta?: string; result?: any; error?: string };
    try {
      evt = JSON.parse(line);
    } catch {
      return null; // ignore non-JSON keepalive/blank lines
    }
    if (evt.type === "chunk") {
      accumulated += evt.delta ?? "";
      if (onUpdate) {
        try {
          onUpdate({
            content: [{ type: "text", text: accumulated }],
            details: {},
          });
        } catch {
          // onUpdate is best-effort progress; never fail the tool on it.
        }
      }
      return null;
    }
    if (evt.type === "done") {
      const r = evt.result ?? {};
      return r.result ?? (accumulated || JSON.stringify(r));
    }
    if (evt.type === "error") {
      return `Error: ${evt.error}`;
    }
    return null;
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let nl: number;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (!line) continue;
      const final = handle(line);
      if (final !== null) return final;
    }
  }
  // Stream closed without an explicit done/error.
  return accumulated || "(no response from Soliplex)";
}

export default function (pi: any) {
  if (!BRIDGE_URL || !process.env.KLANGK_BRIDGE_TOKEN) return;

  pi.registerTool({
    name: "soliplex_list_rooms",
    description:
      "List available Soliplex knowledge base rooms. Returns room IDs, names, and descriptions. " +
      "Only use this tool when the user explicitly mentions 'soliplex' or asks to list Soliplex knowledge bases. ",
    promptSnippet: "soliplex_list_rooms: List Soliplex knowledge base rooms",
    parameters: Type.Object({}),
    async execute(
      _toolCallId: string,
      _params: {},
      _signal: AbortSignal | undefined,
      onUpdate: ToolUpdate | undefined,
      _ctx: any,
    ) {
      const response = await bridgeStream("soliplex_list_rooms", {}, onUpdate);
      return {
        content: [{ type: "text", text: response || "No rooms available." }],
        details: {},
      };
    },
  });

  pi.registerTool({
    name: "soliplex_query",
    description:
      "Query a Soliplex knowledge base room with a natural language question. " +
      "The room contains indexed documents searched using RAG (Retrieval-Augmented Generation). " +
      "Only use this tool when the user explicitly mentions 'soliplex' or asks about Soliplex knowledge bases.",
    promptSnippet:
      "soliplex_query(room_id, question): Query a Soliplex knowledge base room",
    promptGuidelines: [
      "If the user's message contains the word 'soliplex', and appears to be a question that is not explicitly asking for a rooms list, use soliplex_query.",
      "Before using soliplex_query, call soliplex_list_rooms to see available rooms and their descriptions.",
      "Choose the room whose description best matches the user's question — different rooms have different knowledge bases.",
      "If no room is an obvious match, use the room that is best suited to general-purpose queries."
    ],
    parameters: Type.Object({
      room_id: Type.String({
        description: "The room ID to query (from soliplex_list_rooms)",
      }),
      question: Type.String({
        description: "The natural language question to ask",
      }),
    }),
    async execute(
      _toolCallId: string,
      params: { room_id?: string; question: string },
      _signal: AbortSignal | undefined,
      onUpdate: ToolUpdate | undefined,
      _ctx: any,
    ) {
      const roomId = params.room_id || "search";
      const response = await bridgeStream(
        "soliplex_query",
        { room_id: roomId, question: params.question },
        onUpdate,
      );
      return {
        content: [
          {
            type: "text",
            text: response || "(No response from Soliplex)",
          },
        ],
        details: {},
      };
    },
  });
}
