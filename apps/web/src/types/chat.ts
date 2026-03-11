export type ConfidenceLevel = "high" | "medium" | "low"

export interface AskRequest {
  question: string
}

export interface SourceItem {
  title: string
  source_url: string
  authority: string
  excerpt: string
  legal_ref: string
}

export interface AskResponse {
  answer: string
  sources: SourceItem[]
  disclaimer: string
  confidence: ConfidenceLevel
  cannot_answer_reason: string | null
}

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  text: string
  createdAt: string
  response?: AskResponse
  error?: string
}
