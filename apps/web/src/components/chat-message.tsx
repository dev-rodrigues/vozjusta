import { motion } from "motion/react"
import { AlertTriangle, BookMarked, Gavel, Link as LinkIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import type { ChatMessage, ConfidenceLevel } from "@/types/chat"

interface ChatMessageProps {
  message: ChatMessage
}

const confidenceMap: Record<ConfidenceLevel, { label: string; variant: "success" | "warning" | "low" }> = {
  high: { label: "Confianca alta", variant: "success" },
  medium: { label: "Confianca media", variant: "warning" },
  low: { label: "Confianca baixa", variant: "low" },
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value))
}

export function ChatMessageItem({ message }: ChatMessageProps) {
  if (message.role === "user") {
    return (
      <motion.article
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.24 }}
        className="ml-auto max-w-[92%] sm:max-w-[78%]"
      >
        <div className="cut-corner-sm magenta-glow border border-[#ff0074]/35 bg-[#ff0074] px-3 py-3 text-sm leading-6 text-white sm:px-4 sm:py-4 sm:leading-7">
          <p className="whitespace-pre-wrap break-words">{message.text}</p>
          <p className="mt-2 text-right text-[10px] font-semibold uppercase tracking-[0.18em] text-white/70">
            {formatDate(message.createdAt)}
          </p>
        </div>
      </motion.article>
    )
  }

  const confidence = message.response ? confidenceMap[message.response.confidence] : null

  return (
    <motion.article
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28 }}
      className="max-w-[96%] sm:max-w-[88%]"
    >
      <Card className="border-[#2a2a2b] bg-[#f2f2f3] text-[#040405] shadow-[0_24px_70px_rgba(0,0,0,0.28)]">
        <CardContent className="space-y-4 pt-4 sm:pt-5">
          <div className="flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#55565a]">
            <Gavel className="size-3.5 text-[#ff0074]" />
            <span>Assistente juridico</span>
            <span className="text-[#8a8b8f]">|</span>
            <span>{formatDate(message.createdAt)}</span>
          </div>

          <div className="space-y-3">
            <p className="whitespace-pre-wrap break-words text-[14px] leading-7 text-[#18181b] sm:text-[15px] sm:leading-8">
              {message.text}
            </p>
            {message.error ? (
              <div className="cut-corner-sm flex items-start gap-3 border border-[#ff5f7d]/35 bg-[#fff0f3] p-4 text-sm text-[#8b2142]">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                <p className="leading-6">{message.error}</p>
              </div>
            ) : null}
          </div>

          {message.response ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                {confidence ? <Badge variant={confidence.variant}>{confidence.label}</Badge> : null}
              </div>

              <div className="text-[11px] leading-6 text-[#66676c]">
                {message.response.disclaimer}
              </div>

              {message.response.sources.length > 0 ? (
                <div className="space-y-2">
                  <h3 className="inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.22em] text-[#55565a]">
                    <BookMarked className="size-3.5" />
                    Fontes citadas
                  </h3>
                  <ul className="grid gap-2">
                    {message.response.sources.map((source, index) => (
                      <li
                        key={`${source.title}-${index}`}
                        className="cut-corner-sm border border-[#d7d7d9] bg-white px-3 py-3 text-xs sm:px-4"
                      >
                        <p className="break-words font-semibold uppercase tracking-[0.08em] text-[#040405]">{source.title}</p>
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px] font-medium uppercase tracking-[0.18em] text-[#6d6e73]">
                          <span>{source.authority}</span>
                          <span>|</span>
                          <span>{source.legal_ref}</span>
                        </div>
                        <a
                          href={source.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-2 inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#ff0074] transition-colors hover:text-[#d00061]"
                        >
                          <LinkIcon className="size-3.5" />
                          Abrir fonte oficial
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          ) : null}
        </CardContent>
      </Card>
    </motion.article>
  )
}
