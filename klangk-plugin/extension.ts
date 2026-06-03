import { Type } from "@sinclair/typebox";

const BRIDGE_URL = process.env.KLANGK_BRIDGE_URL;

async function bridgeRequest(action: string, params: Record<string, string> = {}): Promise<string> {
  const token = process.env.KLANGK_BRIDGE_TOKEN;
  const resp = await fetch(`${BRIDGE_URL}/api/browser-delegate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, token, ...params }),
  });
  if (!resp.ok) {
    if (resp.status === 401 || resp.status === 502) {
      return (
        "Temporary authentication error (HTTP " + resp.status + "). " +
        "The OIDC token may have expired and is being refreshed. " +
        "Retry this tool call — it is not permanently broken."
      );
    }
    return `Error: bridge returned ${resp.status}`;
  }
  const data = await resp.json();
  if (data.error) {
    return `Error: ${data.error}`;
  }
  return data.result ?? JSON.stringify(data);
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
      _onUpdate: any,
      _ctx: any,
    ) {
      const response = await bridgeRequest("soliplex_list_rooms");
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
      _onUpdate: any,
      _ctx: any,
    ) {
      const roomId = params.room_id || "search";
      const response = await bridgeRequest("soliplex_query", {
        room_id: roomId,
        question: params.question,
      });
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
