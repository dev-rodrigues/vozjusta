import { useEffect, useMemo, useRef, useState, type FormEvent } from "react"
import axios from "axios"
import { AnimatePresence, motion } from "motion/react"
import { useMutation } from "@tanstack/react-query"
import { Loader2, RefreshCw, Scale, SendHorizontal } from "lucide-react"

import { ChatMessageItem } from "@/components/chat-message"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { askQuestion, getApiTimeoutMs } from "@/lib/api"
import type { AskResponse, ChatMessage } from "@/types/chat"

const STORAGE_KEY = "vozjusta-public-chat-history"
const MIN_QUESTION_LENGTH = 3
const MAX_QUESTION_LENGTH = 1800
const HISTORY_LIMIT = 60

const starterQuestions = [
  "Discriminacao racial no trabalho e crime no Brasil?",
  "Como denunciar assedio moral com seguranca?",
  "Quais canais oficiais posso procurar para orientacao?",
]

function toMessageId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function restoreHistory(): ChatMessage[] {
  if (typeof window === "undefined") {
    return []
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return []
    }

    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) {
      return []
    }

    return parsed
      .filter((item): item is ChatMessage => {
        return (
          item &&
          typeof item === "object" &&
          (item.role === "user" || item.role === "assistant") &&
          typeof item.text === "string" &&
          typeof item.createdAt === "string"
        )
      })
      .slice(-HISTORY_LIMIT)
  } catch {
    return []
  }
}

function trimHistory(messages: ChatMessage[]): ChatMessage[] {
  return messages.slice(-HISTORY_LIMIT)
}

function buildAssistantMessageFromResponse(response: AskResponse): ChatMessage {
  return {
    id: toMessageId(),
    role: "assistant",
    text: response.answer,
    createdAt: new Date().toISOString(),
    response,
  }
}

function buildAssistantErrorMessage(errorMessage: string): ChatMessage {
  return {
    id: toMessageId(),
    role: "assistant",
    text: "Nao foi possivel concluir a consulta agora.",
    createdAt: new Date().toISOString(),
    error: errorMessage,
  }
}

export default function App() {
  const [question, setQuestion] = useState("")
  const [messages, setMessages] = useState<ChatMessage[]>(() => restoreHistory())
  const [validationError, setValidationError] = useState<string | null>(null)
  const scrollViewportRef = useRef<HTMLDivElement>(null)

  const mutation = useMutation({
    mutationFn: askQuestion,
    onSuccess: (response) => {
      setMessages((current) => trimHistory([...current, buildAssistantMessageFromResponse(response)]))
    },
    onError: (error) => {
      const fallbackMessage = "A API parece indisponivel no momento. Tente novamente em alguns instantes."
      const timeoutMessage = `A resposta demorou mais que ${Math.round(getApiTimeoutMs() / 1000)}s. Tente novamente em alguns instantes.`

      if (axios.isAxiosError(error)) {
        if (error.code === "ECONNABORTED") {
          setMessages((current) => trimHistory([...current, buildAssistantErrorMessage(timeoutMessage)]))
          return
        }

        const data = error.response?.data
        const detail =
          typeof data === "object" &&
          data !== null &&
          "detail" in data &&
          typeof (data as { detail?: unknown }).detail === "string"
            ? (data as { detail: string }).detail
            : fallbackMessage
        setMessages((current) => trimHistory([...current, buildAssistantErrorMessage(detail)]))
        return
      }

      setMessages((current) => trimHistory([...current, buildAssistantErrorMessage(fallbackMessage)]))
    },
  })

  useEffect(() => {
    if (typeof window === "undefined") {
      return
    }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
  }, [messages])

  useEffect(() => {
    const viewport = scrollViewportRef.current
    if (!viewport) {
      return
    }
    viewport.scrollTo({ top: viewport.scrollHeight, behavior: "smooth" })
  }, [messages, mutation.isPending])

  const remainingChars = MAX_QUESTION_LENGTH - question.length

  const canSubmit = useMemo(() => {
    const size = question.trim().length
    return size >= MIN_QUESTION_LENGTH && size <= MAX_QUESTION_LENGTH && !mutation.isPending
  }, [mutation.isPending, question])

  function appendUserMessage(value: string) {
    const userMessage: ChatMessage = {
      id: toMessageId(),
      role: "user",
      text: value,
      createdAt: new Date().toISOString(),
    }

    setMessages((current) => trimHistory([...current, userMessage]))
  }

  function handlePrefillQuestion(value: string) {
    setQuestion(value)
    setValidationError(null)
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (mutation.isPending) {
      return
    }

    const normalized = question.trim()

    if (normalized.length < MIN_QUESTION_LENGTH) {
      setValidationError(`A pergunta precisa ter pelo menos ${MIN_QUESTION_LENGTH} caracteres.`)
      return
    }

    if (normalized.length > MAX_QUESTION_LENGTH) {
      setValidationError(`A pergunta deve ter no maximo ${MAX_QUESTION_LENGTH} caracteres.`)
      return
    }

    setValidationError(null)
    appendUserMessage(normalized)
    setQuestion("")
    mutation.mutate({ question: normalized })
  }

  function handleResetConversation() {
    setMessages([])
    setValidationError(null)
  }

  return (
    <main className="relative h-[100dvh] overflow-hidden px-2 py-2 text-[#f2f2f3] sm:px-4 sm:py-4 lg:px-6">
      <div className="pointer-events-none absolute inset-0 diagonal-rail opacity-[0.04]" />

      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.42, ease: "easeOut" }}
        className="relative mx-auto flex h-full max-w-5xl flex-col overflow-hidden border border-[#2a2a2b] bg-[#040405]/94 backdrop-blur-xl"
      >
        <div className="grid-skin absolute inset-0 opacity-20" />

        <header className="relative flex shrink-0 items-center justify-between gap-3 border-b border-[#2a2a2b] px-3 py-3 sm:px-5">
          <div className="flex min-w-0 items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.22em] text-[#9c9da3] sm:gap-3 sm:tracking-[0.28em]">
            <span className="inline-flex h-2.5 w-2.5 rounded-full bg-[#14c8a8] shadow-[0_0_0_6px_rgba(20,200,168,0.14)]" />
            <span className="truncate">VozJusta</span>
            <span className="hidden text-[#505156] sm:inline">/</span>
            <span className="truncate hidden sm:inline">Chat publico</span>
            <span className="truncate sm:hidden">Chat</span>
          </div>

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleResetConversation}
            disabled={messages.length === 0}
            className="border-[#3e3e40] px-3 text-[#f2f2f3] hover:bg-white/5 sm:px-4"
            aria-label="Limpar conversa"
          >
            <RefreshCw className="size-3.5" />
            <span className="hidden min-[380px]:inline">Limpar</span>
          </Button>
        </header>

        <section className="relative shrink-0 border-b border-[#2a2a2b] px-3 py-3 sm:px-5 sm:py-5">
          <div className="absolute right-0 top-0 h-full w-20 diagonal-rail opacity-20" />

          <p className="mb-3 inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.22em] text-[#14c8a8]">
            <Scale className="size-4" />
            Orientacao juridica inicial
          </p>

          <h1 className="font-display max-w-[12ch] text-[clamp(1.6rem,8vw,3.2rem)] leading-[0.96] tracking-[-0.05em] text-[#f2f2f3]">
            Pergunte. Leia. Abra a fonte.
          </h1>

          <p className="mt-2 max-w-xl text-[13px] leading-6 text-[#b7b8bd] sm:mt-3 sm:text-sm">
            Chat publico para duvidas sobre discriminacao no trabalho, assedio moral, igualdade salarial e denuncia.
          </p>
        </section>

        <section className="relative flex min-h-0 flex-1 flex-col">
          <ScrollArea viewportRef={scrollViewportRef} className="min-h-0 flex-1 bg-[#040405]">
            <div className="grid-skin min-h-full space-y-4 bg-[#040405] px-3 py-3 sm:px-5 sm:py-4">
              {messages.length === 0 ? (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="cut-corner border border-[#2a2a2b] bg-[#0d0e11]/92 p-4 text-[#f2f2f3] sm:p-5"
                >
                  <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[#ff0074]">Pronto para conversar</p>
                  <h2 className="font-display mt-2 text-[1.35rem] leading-none tracking-[-0.04em] sm:text-[1.7rem]">
                    Comece com uma pergunta.
                  </h2>
                  <div className="-mx-1 mt-4 flex gap-2 overflow-x-auto px-1 pb-1 no-scrollbar sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0">
                    {starterQuestions.map((sample) => (
                      <Button
                        key={sample}
                        type="button"
                        variant="ghost"
                        className="shrink-0 border-[#2a2a2b] bg-[#111216] px-3 py-2.5 text-left text-[12px] normal-case tracking-[-0.01em] text-[#f2f2f3] hover:bg-[#17181d] sm:shrink"
                        onClick={() => handlePrefillQuestion(sample)}
                      >
                        {sample}
                      </Button>
                    ))}
                  </div>
                </motion.div>
              ) : null}

              <AnimatePresence initial={false}>
                {messages.map((message) => (
                  <ChatMessageItem key={message.id} message={message} />
                ))}
              </AnimatePresence>

              {mutation.isPending ? (
                <motion.article
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="cut-corner-sm max-w-[94%] border border-[#2a2a2b] bg-[#101115] px-4 py-4 text-sm text-[#d9d9dd]"
                >
                  <span className="inline-flex items-center gap-2 uppercase tracking-[0.18em] text-[#ff0074]">
                    <Loader2 className="size-4 animate-spin" />
                    Consultando base juridica
                  </span>
                </motion.article>
              ) : null}
            </div>
          </ScrollArea>

          <div className="shrink-0 border-t border-[#2a2a2b] bg-[#0c0c0f] px-3 py-3 sm:px-5">
            <form onSubmit={handleSubmit} className="space-y-3">
              <div className="flex flex-col gap-3 sm:flex-row">
                <Input
                  value={question}
                  onChange={(event) => {
                    setQuestion(event.target.value)
                    if (validationError) {
                      setValidationError(null)
                    }
                  }}
                  minLength={MIN_QUESTION_LENGTH}
                  maxLength={MAX_QUESTION_LENGTH}
                  placeholder="Ex.: Meu chefe pode me humilhar em publico?"
                  disabled={mutation.isPending}
                  aria-invalid={Boolean(validationError)}
                  className="sm:flex-1"
                />

                <Button type="submit" size="lg" className="sm:min-w-[13rem]" disabled={!canSubmit}>
                  {mutation.isPending ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="size-4 animate-spin" />
                      Enviando
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-2">
                      <SendHorizontal className="size-4" />
                      Perguntar
                    </span>
                  )}
                </Button>
              </div>

              <div className="flex min-h-[1rem] flex-col gap-2 text-[11px] sm:flex-row sm:items-center sm:justify-between">
                <span className={remainingChars < 0 ? "font-semibold text-[#ff5f7d]" : "text-[#8e8f95]"}>
                  {remainingChars} caracteres restantes
                </span>

                {validationError ? (
                  <span className="font-semibold text-[#ff5f7d]">{validationError}</span>
                ) : null}
              </div>
            </form>
          </div>
        </section>
      </motion.div>
    </main>
  )
}
