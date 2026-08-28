import { useEffect, useMemo, useRef, useState } from "react";

import { sendChat } from "../services/api";
import { ApiError } from "../types/api";

interface ChatPanelProps {
  datasetId: string;
  numericColumns: string[];
  categoricalColumns: string[];
}

interface ChatTurn {
  id: number;
  role: "user" | "assistant";
  text: string;
  toolUsed?: string | null;
  toolsUsed?: string[];
  error?: boolean;
}

function buildExamples(numericColumns: string[], categoricalColumns: string[]): string[] {
  const examples = ["How many rows are in this dataset?"];
  const numeric = numericColumns[0];
  const numericB = numericColumns[1];
  const category = categoricalColumns[0];
  if (numeric) {
    examples.push(`What is the average ${numeric}?`);
    examples.push(`Are there outliers in ${numeric}?`);
  }
  if (category) {
    examples.push(`How many rows are in each ${category}?`);
  }
  if (numeric && numericB) {
    examples.push(`How are ${numeric} and ${numericB} correlated?`);
  }
  return examples.slice(0, 4);
}

function analysisLabel(turn: ChatTurn): string | null {
  if (turn.toolsUsed && turn.toolsUsed.length > 0) {
    return `Analysis: ${turn.toolsUsed.join(", ")}`;
  }
  if (turn.toolUsed) {
    return `Analysis: ${turn.toolUsed}`;
  }
  return null;
}

export function ChatPanel({
  datasetId,
  numericColumns,
  categoricalColumns,
}: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [sending, setSending] = useState(false);
  const [nextId, setNextId] = useState(1);
  const listRef = useRef<HTMLDivElement | null>(null);
  const canSend = draft.trim().length > 0 && !sending;
  const examples = useMemo(
    () => buildExamples(numericColumns, categoricalColumns),
    [numericColumns, categoricalColumns],
  );

  useEffect(() => {
    setTurns([]);
    setDraft("");
    setSending(false);
  }, [datasetId]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [turns, sending]);

  async function submit(text?: string) {
    const message = (text ?? draft).trim();
    if (!message || sending) {
      return;
    }
    const userTurn: ChatTurn = { id: nextId, role: "user", text: message };
    setNextId((value) => value + 2);
    setTurns((current) => [...current, userTurn]);
    setDraft("");
    setSending(true);
    try {
      const response = await sendChat(datasetId, message);
      setTurns((current) => [
        ...current,
        {
          id: userTurn.id + 1,
          role: "assistant",
          text: response.message,
          toolUsed: response.tool_used,
          toolsUsed: response.tools_used,
        },
      ]);
    } catch (error) {
      const detail =
        error instanceof ApiError
          ? error.message
          : "The chat request failed. Check that the analysis API is running, then try again.";
      setTurns((current) => [
        ...current,
        {
          id: userTurn.id + 1,
          role: "assistant",
          text: detail,
          error: true,
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="panel chat-panel" aria-labelledby="chat-heading">
      <div className="panel-header">
        <div>
          <h2 id="chat-heading">AI Data Analyst</h2>
          <p>Ask questions about your uploaded dataset.</p>
        </div>
      </div>
      <div className="chat-log" ref={listRef} aria-live="polite">
        {turns.length === 0 && !sending ? (
          <div className="chat-empty">
            <p className="muted">
              Numbers come from the Python analysis tools. The model requests a tool; pandas
              computes the result.
            </p>
            <p className="example-label">Example questions</p>
            <ul className="example-list">
              {examples.map((example) => (
                <li key={example}>
                  <button
                    type="button"
                    className="example-button"
                    disabled={sending}
                    onClick={() => {
                      setDraft(example);
                    }}
                  >
                    {example}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {turns.map((turn) => {
          const analysis = analysisLabel(turn);
          return (
            <article
              key={turn.id}
              className={`chat-bubble chat-${turn.role}${turn.error ? " chat-error" : ""}`}
            >
              <span className="chat-role">{turn.role === "user" ? "You" : "Analyst"}</span>
              <p>{turn.text}</p>
              {analysis ? <p className="chat-tool">{analysis}</p> : null}
            </article>
          );
        })}
        {sending ? (
          <article className="chat-bubble chat-assistant chat-pending" aria-busy="true">
            <span className="chat-role">Analyst</span>
            <p>
              <span className="spinner" aria-hidden="true" />
              Running analysis…
            </p>
          </article>
        ) : null}
      </div>
      <form
        className="chat-form"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <label htmlFor="chat-message">Question</label>
        <textarea
          id="chat-message"
          rows={3}
          maxLength={4000}
          value={draft}
          disabled={sending}
          placeholder="Ask a question about the uploaded CSV"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void submit();
            }
          }}
        />
        <div className="chat-actions">
          <button type="submit" className="button" disabled={!canSend}>
            {sending ? "Sending…" : "Ask"}
          </button>
          <span className="muted">Enter to send · Shift+Enter for a new line</span>
        </div>
      </form>
    </section>
  );
}
