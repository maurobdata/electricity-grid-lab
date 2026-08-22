/**
 * The agent, with its working shown.
 *
 * Tool calls and their results are rendered inline, in the order they happened. That is
 * the whole design: an agent whose reasoning is a black box has to be trusted, while one
 * whose tool calls are visible can be *checked* — every number it quotes corresponds to a
 * request you could make yourself against the API on port 8000.
 *
 * It is also the most useful debugging surface in the lab. When an answer looks wrong, the
 * trace usually shows why in one glance: the wrong zone, a refused signal, a window that
 * came back shorter than asked for.
 */

import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const AGENT = import.meta.env.VITE_AGENT_URL ?? "http://localhost:8001";

interface ToolTrace {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  ok?: boolean;
  durationMs?: number;
  result?: unknown;
}

interface Turn {
  question: string;
  text: string;
  tools: ToolTrace[];
  error?: string;
  done?: boolean;
  rounds?: number;
}

const SUGGESTIONS = [
  "How clean is the grid right now?",
  "Where is this zone's electricity actually coming from?",
  "When is the cleanest hour in the next 24?",
  "Compare the zones available and explain the spread.",
];

export function AgentPanel({ zone }: { zone: string | undefined }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [hasKey, setHasKey] = useState<boolean | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${AGENT}/api/v1/healthz`)
      .then((r) => r.json())
      .then((body) => setHasKey(Boolean(body.has_anthropic_key)))
      .catch(() => setHasKey(false));
  }, []);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    setInput("");
    setBusy(true);

    const index = turns.length;
    setTurns((current) => [...current, { question, text: "", tools: [] }]);

    const patch = (fn: (turn: Turn) => Turn) =>
      setTurns((current) => current.map((turn, i) => (i === index ? fn(turn) : turn)));

    try {
      const response = await fetch(`${AGENT}/api/v1/chat`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          // The zone in focus is prepended so "how clean is it right now" resolves without
          // the user restating context the screen already shows.
          message: zone ? `${question}\n\n(The zone currently in focus is ${zone}.)` : question,
          history: turns.flatMap((turn) => [
            { role: "user", content: turn.question },
            { role: "assistant", content: turn.text },
          ]),
        }),
      });

      if (!response.ok || !response.body) {
        patch((turn) => ({ ...turn, error: `The agent returned ${response.status}.` }));
        return;
      }

      // Hand-parsed SSE rather than EventSource, because EventSource cannot POST and the
      // request carries the conversation history.
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";

        for (const frame of frames) {
          let name = "";
          let data = "";
          for (const line of frame.split("\n")) {
            if (line.startsWith("event:")) name = line.slice(6).trim();
            else if (line.startsWith("data:")) data += line.slice(5).trim();
          }
          if (!name || !data) continue;

          const payload = JSON.parse(data);
          patch((turn) => apply(turn, name, payload));
        }
      }
    } catch (error) {
      patch((turn) => ({
        ...turn,
        error: error instanceof Error ? error.message : String(error),
      }));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Agent</CardTitle>
          <p className="mt-0.5 text-[0.7rem] text-muted-foreground">
            Seven read-only tools. Its working is shown, so its answers can be checked.
          </p>
        </div>
        {hasKey === false && <Badge variant="warn">no API key</Badge>}
      </CardHeader>

      <CardContent>
        <div ref={scroller} className="max-h-[26rem] space-y-4 overflow-y-auto pr-1">
          {turns.length === 0 && (
            <div className="space-y-2 py-2">
              <p className="text-xs text-muted-foreground">
                Ask about the zones in the current scenario. The agent can only see what the
                API can see, and will say so when something is unavailable.
              </p>
              <div className="flex flex-wrap gap-1.5">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => void ask(suggestion)}
                    disabled={busy || hasKey === false}
                    className="rounded-md border border-border px-2 py-1 text-[0.7rem] text-muted-foreground transition-colors hover:bg-accent disabled:opacity-40"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((turn, index) => (
            <div key={index} className="space-y-2">
              <p className="rounded-lg bg-muted/60 px-2.5 py-1.5 text-xs">
                {turn.question.split("\n\n(The zone")[0]}
              </p>

              {turn.tools.map((tool) => (
                <ToolTraceRow key={tool.id} tool={tool} />
              ))}

              {turn.text && (
                <div className="text-sm whitespace-pre-wrap">{turn.text}</div>
              )}

              {turn.error && (
                <p className="rounded-md border border-destructive/40 bg-destructive/10 px-2.5 py-2 text-xs text-destructive">
                  {turn.error}
                </p>
              )}

              {turn.done && turn.rounds !== undefined && (
                <p className="text-[0.65rem] text-muted-foreground">
                  {turn.tools.length} tool call{turn.tools.length === 1 ? "" : "s"} over{" "}
                  {turn.rounds} round{turn.rounds === 1 ? "" : "s"}
                </p>
              )}
            </div>
          ))}
        </div>

        <form
          className="mt-3 flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            void ask(input);
          }}
        >
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            disabled={busy || hasKey === false}
            placeholder={
              hasKey === false
                ? "Set ANTHROPIC_API_KEY in .env to enable the agent"
                : "Ask about the grid…"
            }
            className="h-8 flex-1 rounded-md border border-border bg-muted px-2.5 text-xs focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-40"
          />
          <Button type="submit" variant="default" disabled={busy || !input.trim()}>
            {busy ? "…" : "Ask"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function ToolTraceRow({ tool }: { tool: ToolTrace }) {
  const [open, setOpen] = useState(false);
  const pending = tool.ok === undefined;

  return (
    <div className="rounded-md border border-border bg-muted/30 text-[0.7rem]">
      <button
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left"
      >
        <span
          className={cn(
            "h-1.5 w-1.5 shrink-0 rounded-full",
            pending
              ? "animate-pulse bg-primary"
              : tool.ok
                ? "bg-[var(--color-live)]"
                : "bg-destructive",
          )}
        />
        <span className="numeric font-medium">{tool.name}</span>
        <span className="truncate text-muted-foreground">
          {Object.entries(tool.arguments)
            .map(([key, value]) => `${key}=${JSON.stringify(value)}`)
            .join(" ")}
        </span>
        {tool.durationMs !== undefined && (
          <span className="numeric ml-auto shrink-0 text-muted-foreground">
            {Math.round(tool.durationMs)}ms
          </span>
        )}
      </button>

      {open && tool.result !== undefined && (
        <pre className="numeric max-h-56 overflow-auto border-t border-border px-2.5 py-2 text-[0.65rem] text-muted-foreground">
          {JSON.stringify(tool.result, null, 2)}
        </pre>
      )}
    </div>
  );
}

/**
 * The SSE contract, mirrored from `gridlab/agent/app.py`.
 *
 * Written as a discriminated union rather than a loose record so that a change on the
 * server surfaces here as a type error instead of an `undefined` in a trace row.
 */
type SseEvent =
  | { event: "text"; data: { text: string } }
  | { event: "tool_call"; data: { id: string; name: string; arguments: Record<string, unknown> } }
  | {
      event: "tool_result";
      data: { id: string; name: string; ok: boolean; content: unknown; duration_ms: number };
    }
  | { event: "done"; data: { stop_reason: string | null; rounds: number } }
  | { event: "error"; data: { message: string; kind: string } };

function apply(turn: Turn, event: string, data: unknown): Turn {
  const frame = { event, data } as SseEvent;

  switch (frame.event) {
    case "text":
      return { ...turn, text: turn.text + frame.data.text };

    case "tool_call":
      return {
        ...turn,
        tools: [
          ...turn.tools,
          {
            id: frame.data.id,
            name: frame.data.name,
            arguments: frame.data.arguments ?? {},
          },
        ],
      };

    case "tool_result":
      return {
        ...turn,
        tools: turn.tools.map((tool) =>
          tool.id === frame.data.id
            ? {
                ...tool,
                ok: frame.data.ok,
                durationMs: frame.data.duration_ms,
                result: frame.data.content,
              }
            : tool,
        ),
      };

    case "done":
      return { ...turn, done: true, rounds: frame.data.rounds };

    case "error":
      return { ...turn, error: frame.data.message, done: true };

    default:
      return turn;
  }
}
