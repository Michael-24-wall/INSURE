import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Bot, Send, Sparkles, X } from "lucide-react";
import api, { getErrorMessage } from "../api/client";
import { Button, Spinner } from "./ui";

const suggestions = [
  "How do I file a claim?",
  "What does comprehensive cover?",
  "How long does a quotation take?",
];

export function AIAssistant({ open, onClose }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Hi, I’m your InsureConnect assistant. Ask me about cover, quotations, claims or payments. I provide guidance, not a policy decision.",
    },
  ]);
  const [input, setInput] = useState("");
  const endRef = useRef(null);
  const inputRef = useRef(null);

  const ask = useMutation({
    mutationFn: async (question) => (await api.post("/ai/assistant/", { question })).data,
    onSuccess: (data, question) => {
      setMessages((current) => [
        ...current,
        { role: "user", text: question },
        { role: "assistant", text: data.answer, disclaimer: data.disclaimer },
      ]);
      setInput("");
    },
    onError: (error, question) => {
      setMessages((current) => [
        ...current,
        { role: "user", text: question },
        { role: "assistant", text: getErrorMessage(error), error: true },
      ]);
      setInput("");
    },
  });

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  useEffect(() => {
    if (!open) return undefined;
    const previouslyFocused = document.activeElement;
    const onKey = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    document.addEventListener("keydown", onKey);
    window.requestAnimationFrame(() => inputRef.current?.focus());
    return () => {
      document.removeEventListener("keydown", onKey);
      if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus();
    };
  }, [open, onClose]);

  function submit(question = input) {
    const text = question.trim();
    if (!text || ask.isPending) return;
    ask.mutate(text);
  }

  if (!open) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-[80] flex justify-end p-0 sm:inset-auto sm:bottom-6 sm:right-6">
      <div role="dialog" aria-modal="true" aria-label="Insurance assistant" className="flex h-[85vh] w-full flex-col overflow-hidden rounded-t-3xl border border-ink-200 bg-white shadow-soft sm:h-[560px] sm:w-[400px] sm:rounded-3xl">
        <div className="flex items-center justify-between border-b border-ink-100 bg-ink-950 px-5 py-4 text-white">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-lime-300 text-ink-950">
              <Bot className="h-5 w-5" />
            </span>
            <div>
              <p className="text-sm font-bold">Insurance assistant</p>
              <p className="text-[11px] text-white/60">Guidance, not underwriting advice</p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-white/60 hover:bg-white/10 hover:text-white" aria-label="Close assistant">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {messages.map((message, index) => (
            <div key={index} className={message.role === "user" ? "flex justify-end" : "flex justify-start"}>
              <div
                className={
                  message.role === "user"
                    ? "max-w-[85%] rounded-2xl rounded-br-md bg-ink-950 px-4 py-2.5 text-sm text-white"
                    : `max-w-[90%] rounded-2xl rounded-bl-md px-4 py-3 text-sm ${message.error ? "bg-red-50 text-red-700" : "bg-ink-100 text-ink-800"}`
                }
              >
                <p className="whitespace-pre-line leading-relaxed">{message.text}</p>
                {message.disclaimer && <p className="mt-2 border-t border-ink-200/60 pt-2 text-[10px] leading-relaxed text-ink-400">{message.disclaimer}</p>}
              </div>
            </div>
          ))}
          {ask.isPending && (
            <div className="flex items-center gap-2 text-xs text-ink-400">
              <Spinner className="h-4 w-4" /> Thinking…
            </div>
          )}
          <div ref={endRef} />
        </div>

        {messages.length < 3 && (
          <div className="no-scrollbar flex gap-2 overflow-x-auto px-4 pb-2">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => submit(suggestion)}
                className="flex shrink-0 items-center gap-1.5 rounded-full border border-ink-200 px-3 py-1.5 text-[11px] font-semibold text-ink-600 hover:border-brand-300 hover:text-brand-700"
              >
                <Sparkles className="h-3 w-3" /> {suggestion}
              </button>
            ))}
          </div>
        )}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
          className="flex items-center gap-2 border-t border-ink-100 p-3"
        >
          <input
            ref={inputRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask a question…"
            aria-label="Ask the insurance assistant"
            className="control border-0 bg-ink-50 focus:ring-2"
          />
          <Button type="submit" size="icon" variant="brand" loading={ask.isPending} aria-label="Send">
            {!ask.isPending && <Send className="h-4 w-4" />}
          </Button>
        </form>
      </div>
    </div>
  );
}
