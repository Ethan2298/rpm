"use client";

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { readUIMessageStream, type UIMessageChunk } from "ai";
import { Bug, Code2, PanelLeft, Plus, ShieldCheck } from "lucide-react";

/** Parse SSE response body into a stream of UIMessageChunk objects */
function sseToJsonStream(body: ReadableStream<Uint8Array>): ReadableStream<UIMessageChunk> {
  const textStream = body.pipeThrough(new TextDecoderStream() as unknown as ReadableWritablePair<string, Uint8Array>);
  let buffer = "";
  return textStream.pipeThrough(
    new TransformStream<string, UIMessageChunk>({
      transform(text, controller) {
        buffer += text;
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data: ")) continue;
          const payload = trimmed.slice(6);
          if (payload === "[DONE]") return;
          try {
            controller.enqueue(JSON.parse(payload));
          } catch {
            // skip malformed chunks
          }
        }
      },
      flush(controller) {
        if (buffer.trim().startsWith("data: ")) {
          const payload = buffer.trim().slice(6);
          if (payload !== "[DONE]") {
            try { controller.enqueue(JSON.parse(payload)); } catch { /* skip */ }
          }
        }
      },
    })
  );
}
import { AppShell, DEFAULT_SIDEBAR_WIDTH } from "@/components/magi/app-shell";
import { LeftSidebar } from "@/components/magi/left-sidebar";
import { ComposerDock } from "@/components/magi/composer-dock";
import type { PermissionMode } from "@/components/magi/permission-picker";
import { Message } from "@/components/magi/message";
import { StreamMetrics, type StreamUsage } from "@/components/magi/stream-metrics";
import { SettingsModal } from "@/components/magi/settings-modal";
import { useScrollOverlay } from "@/lib/magi/scroll-overlay";
import type { ChatMessage } from "@/lib/magi/ai";
import {
  buildDefaultChatState,
  createThread,
  deriveThreadTitle,
  normalizeChatState,
  serializeChatState,
  searchThreads,
  sortThreads,
  type ChatState,
  type ChatThread,
} from "@/lib/magi/chat-threads";
import {
  getAllModelOptions,
  DEFAULT_PROVIDER,
  getDefaultModel,
  getProviderForModel,
  type AIProvider,
} from "@/lib/magi/ai-provider";

const STORAGE_KEY = "magi:chat-v3";
const SIDEBAR_WIDTH_KEY = "magi:sidebar-width";
const MODEL_KEY = "magi:model";
const API_KEYS_KEY = "magi:api-keys";

function nowISO(): string {
  return new Date().toISOString();
}

function getActiveThread(state: ChatState): ChatThread | undefined {
  return state.threads.find((t) => t.id === state.activeThreadId);
}

function loadChatState(): ChatState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return buildDefaultChatState(nowISO());
    return normalizeChatState(JSON.parse(raw), nowISO());
  } catch {
    return buildDefaultChatState(nowISO());
  }
}

function loadModel(): string {
  try {
    const raw = localStorage.getItem(MODEL_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (typeof parsed.model === "string" && getProviderForModel(parsed.model)) {
        return parsed.model;
      }
    }
  } catch { /* ignore */ }
  return getDefaultModel(DEFAULT_PROVIDER);
}

function loadSidebarWidth(): number {
  try {
    const raw = localStorage.getItem(SIDEBAR_WIDTH_KEY);
    if (raw) {
      const n = Number(raw);
      if (Number.isFinite(n) && n >= 200 && n <= 400) return Math.round(n);
    }
  } catch { /* ignore */ }
  return DEFAULT_SIDEBAR_WIDTH;
}

function getStoredApiKey(provider: AIProvider): string | null {
  try {
    const raw = localStorage.getItem(API_KEYS_KEY);
    if (!raw) return null;
    const keys = JSON.parse(raw);
    return keys[provider] || null;
  } catch {
    return null;
  }
}

function setStoredApiKey(provider: AIProvider, key: string) {
  try {
    const raw = localStorage.getItem(API_KEYS_KEY);
    const keys = raw ? JSON.parse(raw) : {};
    keys[provider] = key;
    localStorage.setItem(API_KEYS_KEY, JSON.stringify(keys));
  } catch { /* ignore */ }
}

function createTextMessage(role: "user" | "assistant", text: string): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role,
    parts: [{ type: "text", text }],
  };
}

function appendMessageToThread(
  state: ChatState,
  threadId: string,
  message: ChatMessage,
  nextTitle?: string,
  updatedAt = nowISO()
): ChatState {
  const threads = state.threads.map((thread) => {
    if (thread.id !== threadId) return thread;
    return {
      ...thread,
      title: nextTitle ?? thread.title,
      messages: [...thread.messages, message],
      updatedAt,
    };
  });
  return { ...state, threads: sortThreads(threads) };
}

function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-1.5 h-5" aria-label="Assistant is thinking">
      <span className="thinking-spinner" />
      <span className="thinking-text">Thinking</span>
    </div>
  );
}

const STARTER_PROMPTS = [
  {
    title: "Trace a bug",
    description: "Find the source of a regression and fix it cleanly.",
    prompt: "Trace the bug in this codebase, explain the root cause, and patch it.",
    Icon: Bug,
  },
  {
    title: "Refactor a feature",
    description: "Tighten a flow without changing the product direction.",
    prompt: "Refactor this feature to simplify the code and keep the behavior stable.",
    Icon: Code2,
  },
  {
    title: "Review access",
    description: "Check safety, assumptions, and operational gaps.",
    prompt: "Review this project for risky assumptions, missing checks, and broken edge cases.",
    Icon: ShieldCheck,
  },
] as const;

export default function MagiPage() {
  const [mounted, setMounted] = useState(false);
  const [chatState, setChatState] = useState<ChatState>(() => buildDefaultChatState(nowISO()));
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState<ChatMessage | null>(null);
  const [streamingThreadId, setStreamingThreadId] = useState<string | null>(null);
  const [streamStartTime, setStreamStartTime] = useState<number | null>(null);
  const [lastStreamUsage, setLastStreamUsage] = useState<StreamUsage | null>(null);
  const [composerInput, setComposerInput] = useState("");
  const [model, setModel] = useState<string>(getDefaultModel(DEFAULT_PROVIDER));
  const [permMode, setPermMode] = useState<PermissionMode>("ask");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState<number>(DEFAULT_SIDEBAR_WIDTH);
  const [threadSearchQuery, setThreadSearchQuery] = useState("");

  // Hydrate from localStorage after mount
  useEffect(() => {
    setChatState(loadChatState());
    setModel(loadModel());
    setSidebarWidth(loadSidebarWidth());
    setMounted(true);
  }, []);

  const chatStateRef = useRef(chatState);
  const activeAbortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const orderedThreads = useMemo(() => sortThreads(chatState.threads), [chatState.threads]);
  const filteredThreads = useMemo(
    () => threadSearchQuery ? searchThreads(orderedThreads, threadSearchQuery) : orderedThreads,
    [orderedThreads, threadSearchQuery]
  );
  const activeThread = useMemo(
    () => orderedThreads.find((t) => t.id === chatState.activeThreadId),
    [orderedThreads, chatState.activeThreadId]
  );
  const activeMessages = activeThread?.messages ?? [];
  const showStreaming = isStreaming && streamingThreadId === chatState.activeThreadId;
  const provider = useMemo(() => getProviderForModel(model) ?? DEFAULT_PROVIDER, [model]);
  const mainScrollOverlay = useScrollOverlay(scrollRef);

  useEffect(() => { chatStateRef.current = chatState; }, [chatState]);

  // Persist chat state
  useEffect(() => {
    const timer = setTimeout(() => {
      localStorage.setItem(STORAGE_KEY, serializeChatState(chatState));
    }, 250);
    return () => clearTimeout(timer);
  }, [chatState]);

  // Persist sidebar width
  useEffect(() => {
    try { localStorage.setItem(SIDEBAR_WIDTH_KEY, String(sidebarWidth)); } catch { /* ignore */ }
  }, [sidebarWidth]);

  // Persist model
  useEffect(() => {
    try { localStorage.setItem(MODEL_KEY, JSON.stringify({ model })); } catch { /* ignore */ }
  }, [model]);

  // Auto-scroll
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distFromBottom < 100) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [activeMessages.length, showStreaming, streamingMessage]);

  const handleSelectThread = useCallback((id: string) => {
    setChatState((prev) => ({ ...prev, activeThreadId: id }));
  }, []);

  const handleNewThread = useCallback(() => {
    const thread = createThread(nowISO());
    setChatState((prev) => ({
      ...prev,
      threads: sortThreads([thread, ...prev.threads]),
      activeThreadId: thread.id,
    }));
    setComposerInput("");
  }, []);

  const handleDeleteThread = useCallback((id: string) => {
    setChatState((prev) => {
      const remaining = prev.threads.filter((t) => t.id !== id);
      if (remaining.length === 0) {
        const thread = createThread(nowISO());
        return { ...prev, threads: [thread], activeThreadId: thread.id };
      }
      const activeThreadId = prev.activeThreadId === id ? remaining[0].id : prev.activeThreadId;
      return { ...prev, threads: remaining, activeThreadId };
    });
  }, []);

  const ensureActiveThread = useCallback((): string => {
    const current = getActiveThread(chatStateRef.current);
    if (current) return current.id;
    const thread = createThread(nowISO());
    setChatState((prev) => ({
      ...prev,
      threads: sortThreads([thread, ...prev.threads]),
      activeThreadId: thread.id,
    }));
    return thread.id;
  }, []);

  const handleModelChange = useCallback((nextModel: string) => {
    if (!getProviderForModel(nextModel)) return;
    setModel(nextModel);
  }, []);

  const handleSaveApiKey = useCallback((targetProvider: AIProvider, key: string) => {
    setStoredApiKey(targetProvider, key);
  }, []);

  const clearStreamingState = useCallback(() => {
    setIsStreaming(false);
    setStreamingThreadId(null);
    setStreamingMessage(null);
    activeAbortRef.current = null;
  }, []);

  const handleCancelStream = useCallback(() => {
    const abort = activeAbortRef.current;
    if (!abort) return;
    const threadId = streamingThreadId;
    const partial = streamingMessage;
    if (threadId && partial) {
      setChatState((prev) => appendMessageToThread(prev, threadId, partial, undefined, nowISO()));
    }
    abort.abort();
    clearStreamingState();
  }, [clearStreamingState, streamingMessage, streamingThreadId]);

  const handleChatScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const opacity = Math.min(el.scrollTop / 50, 1);
    el.style.setProperty("--chat-fade-opacity", String(opacity));
  }, []);

  const startStream = useCallback(async (threadId: string, messages: ChatMessage[]) => {
    const apiKey = getStoredApiKey(provider);

    setIsStreaming(true);
    setStreamingThreadId(threadId);
    setStreamingMessage(null);
    setStreamStartTime(Date.now());
    setLastStreamUsage(null);

    const abortController = new AbortController();
    activeAbortRef.current = abortController;

    try {
      const res = await fetch("/api/magi/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider,
          model,
          messages,
          apiKey: apiKey || undefined,
        }),
        signal: abortController.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Request failed" }));
        setChatState((prev) =>
          appendMessageToThread(prev, threadId, createTextMessage("assistant", `Error: ${err.error}`))
        );
        clearStreamingState();
        return;
      }

      const stream = res.body;
      if (!stream) {
        clearStreamingState();
        return;
      }

      let latestMessage: ChatMessage | null = null;
      let streamError: string | null = null;

      const uiStream = sseToJsonStream(stream);

      try {
        for await (const uiMessage of readUIMessageStream<ChatMessage>({
          stream: uiStream,
          terminateOnError: false,
          onError: (error) => {
            if (!streamError) {
              streamError = error instanceof Error ? error.message : String(error);
            }
          },
        })) {
          if (activeAbortRef.current !== abortController) return;
          latestMessage = uiMessage;
          setStreamingMessage(uiMessage);
        }
      } catch (error) {
        if (abortController.signal.aborted) return;
        if (!streamError) {
          streamError = error instanceof Error ? error.message : String(error);
        }
      } finally {
        if (activeAbortRef.current !== abortController) return;

        if (latestMessage) {
          const messageToPersist = streamError
            ? {
                ...latestMessage,
                parts: [
                  ...latestMessage.parts,
                  { type: "text" as const, text: `\n\nError: ${streamError}` },
                ],
              }
            : latestMessage;
          setChatState((prev) =>
            appendMessageToThread(prev, threadId, messageToPersist as ChatMessage, undefined, nowISO())
          );
        } else if (streamError) {
          setChatState((prev) =>
            appendMessageToThread(prev, threadId, createTextMessage("assistant", `Error: ${streamError}`))
          );
        }

        clearStreamingState();
      }
    } catch (err) {
      if (abortController.signal.aborted) return;
      setChatState((prev) =>
        appendMessageToThread(
          prev,
          threadId,
          createTextMessage("assistant", `Error: ${err instanceof Error ? err.message : "Unknown error"}`)
        )
      );
      clearStreamingState();
    }
  }, [clearStreamingState, model, provider]);

  const handleSend = useCallback(async () => {
    const text = composerInput.trim();
    if (!text || isStreaming) return;

    const threadId = ensureActiveThread();
    const thread = chatStateRef.current.threads.find((t) => t.id === threadId);

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      parts: [{ type: "text", text }],
    };

    const nextTitle =
      thread && thread.messages.some((msg) => msg.role === "user")
        ? undefined
        : deriveThreadTitle(text);

    const updatedMessages = [...(thread?.messages ?? []), userMsg];
    setChatState((prev) => appendMessageToThread(prev, threadId, userMsg, nextTitle));
    setComposerInput("");

    await startStream(threadId, updatedMessages);
  }, [composerInput, ensureActiveThread, isStreaming, startStream]);

  const handleRegenerate = useCallback(async () => {
    if (isStreaming) return;
    const thread = getActiveThread(chatStateRef.current);
    if (!thread || thread.messages.length === 0) return;
    const lastMsg = thread.messages[thread.messages.length - 1];
    if (lastMsg.role !== "assistant") return;

    const messagesWithoutLast = thread.messages.slice(0, -1);
    setChatState((prev) => ({
      ...prev,
      threads: prev.threads.map((t) =>
        t.id === thread.id ? { ...t, messages: messagesWithoutLast, updatedAt: nowISO() } : t
      ),
    }));
    setLastStreamUsage(null);
    await startStream(thread.id, messagesWithoutLast);
  }, [isStreaming, startStream]);

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((prev) => !prev);
  }, []);

  const handleStarterPrompt = useCallback((prompt: string) => {
    setComposerInput(prompt);
  }, []);

  const permissionLabel = permMode === "ask"
    ? "Approval required"
    : permMode === "edits"
      ? "Auto-approve edits"
      : "Full access";

  const showWelcome = mounted && activeMessages.length === 0 && !showStreaming;

  return (
    <>
      <AppShell
        sidebarOpen={sidebarOpen}
        sidebarWidth={sidebarWidth}
        onSidebarWidthChange={setSidebarWidth}
        header={
          <div className="flex items-center gap-3">
            <button
              onClick={toggleSidebar}
              className="flex h-10 w-10 items-center justify-center rounded-[14px] border border-white/[0.08] bg-white/[0.04] text-white/75 transition-colors hover:bg-white/[0.08] hover:text-white"
              title={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
            >
              <PanelLeft size={17} />
            </button>

            <div className="min-w-0">
              <p className="text-[10px] font-medium uppercase tracking-[0.24em] text-white/34">
                Workspace
              </p>
              <h1 className="truncate text-[15px] font-medium text-white">
                {activeThread?.title ?? "New thread"}
              </h1>
            </div>

            <div className="ml-auto hidden items-center gap-2 md:flex">
              <span className="rounded-full border border-white/[0.08] bg-white/[0.04] px-3 py-1 text-[11px] text-white/60">
                {model}
              </span>
              <span className="rounded-full border border-white/[0.08] bg-white/[0.04] px-3 py-1 text-[11px] text-white/60">
                {permissionLabel}
              </span>
            </div>

            <button
              onClick={handleNewThread}
              className="flex h-10 items-center gap-2 rounded-[14px] border border-white/[0.08] bg-white px-3 text-[13px] font-medium text-black transition-opacity hover:opacity-90"
            >
              <Plus size={15} />
              <span className="hidden sm:inline">New thread</span>
            </button>
          </div>
        }
        sidebar={
          <LeftSidebar
            threads={filteredThreads}
            activeThreadId={chatState.activeThreadId}
            searchQuery={threadSearchQuery}
            onSearchChange={setThreadSearchQuery}
            onNewThread={handleNewThread}
            onSelectThread={handleSelectThread}
            onDeleteThread={handleDeleteThread}
            onOpenSettings={() => setSettingsOpen(true)}
          />
        }
        stream={
          <div className="relative h-full">
            <div
              ref={scrollRef}
              onScroll={handleChatScroll}
              className="main-chat-scroll h-full overflow-y-auto px-5 pt-6 pb-10"
            >
              <div className="mx-auto w-full max-w-[760px] space-y-5">
                {showWelcome && (
                  <div className="flex min-h-full flex-col justify-center py-10">
                    <div className="mx-auto max-w-[620px] text-center">
                      <p className="text-[11px] font-medium uppercase tracking-[0.28em] text-white/34">
                        Jimmy Console
                      </p>
                      <h2 className="mt-4 text-[40px] font-medium tracking-[-0.04em] text-white">
                        What should we work on?
                      </h2>
                      <p className="mx-auto mt-4 max-w-[520px] text-[15px] leading-7 text-white/46">
                        This shell is tuned for the same dense, low-noise workflow as Codex:
                        threads on the left, code-focused chat in the center, controls docked at the bottom.
                      </p>
                    </div>

                    <div className="mt-8 grid gap-3 md:grid-cols-3">
                      {STARTER_PROMPTS.map(({ title, description, prompt, Icon }) => (
                        <button
                          key={title}
                          onClick={() => handleStarterPrompt(prompt)}
                          className="group rounded-[22px] border border-white/[0.08] bg-white/[0.03] p-4 text-left transition-all duration-150 hover:border-white/[0.14] hover:bg-white/[0.06]"
                        >
                          <div className="flex h-10 w-10 items-center justify-center rounded-[14px] border border-white/[0.08] bg-white/[0.04] text-white/75 transition-colors group-hover:bg-white/[0.08] group-hover:text-white">
                            <Icon size={18} />
                          </div>
                          <h3 className="mt-4 text-[15px] font-medium text-white">{title}</h3>
                          <p className="mt-2 text-[13px] leading-6 text-white/42">{description}</p>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {activeMessages.map((msg, idx) => (
                  <Message
                    key={msg.id || `msg-${idx}`}
                    message={msg}
                    isLast={idx === activeMessages.length - 1 && msg.role === "assistant"}
                    onRegenerate={handleRegenerate}
                  />
                ))}

                {showStreaming && (
                  <>
                    {streamingMessage && streamingMessage.parts.length > 0 ? (
                      <Message message={streamingMessage} isStreaming />
                    ) : (
                      <div className="flex justify-start animate-msg-enter">
                        <div className="px-4 py-3">
                          <ThinkingIndicator />
                        </div>
                      </div>
                    )}
                    <StreamMetrics isStreaming startTime={streamStartTime} usage={null} />
                  </>
                )}

                {!showStreaming && lastStreamUsage && activeMessages.length > 0 &&
                  activeMessages[activeMessages.length - 1].role === "assistant" && (
                  <StreamMetrics isStreaming={false} startTime={streamStartTime} usage={lastStreamUsage} />
                )}
              </div>
            </div>
            {mainScrollOverlay.hasOverflow && (
              <div className="pointer-events-none absolute top-0 right-[6px] h-full w-[7px]">
                <div
                  className={`scroll-fade-thumb ${mainScrollOverlay.visible ? "is-visible" : ""}`}
                  style={{
                    height: `${mainScrollOverlay.thumbHeight}px`,
                    transform: `translateY(${mainScrollOverlay.thumbTop}px)`,
                  }}
                />
              </div>
            )}
          </div>
        }
        composer={
          <ComposerDock
            input={composerInput}
            isStreaming={isStreaming}
            permMode={permMode}
            model={model}
            modelOptions={getAllModelOptions()}
            onInputChange={setComposerInput}
            onPermModeChange={setPermMode}
            onModelChange={handleModelChange}
            onSend={handleSend}
            onCancel={handleCancelStream}
          />
        }
      />

      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSaveApiKey={handleSaveApiKey}
      />
    </>
  );
}
