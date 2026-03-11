import axios from "axios"

import type { AskRequest, AskResponse } from "@/types/chat"

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() || "http://localhost:8000"
const defaultApiTimeoutMs = 180_000

function parseTimeoutMs(rawValue: string | undefined): number {
  if (!rawValue) {
    return defaultApiTimeoutMs
  }

  const parsed = Number.parseInt(rawValue, 10)
  if (Number.isFinite(parsed) && parsed > 0) {
    return parsed
  }

  return defaultApiTimeoutMs
}

const apiTimeoutMs = parseTimeoutMs(import.meta.env.VITE_API_TIMEOUT_MS?.trim())

export const apiClient = axios.create({
  baseURL: apiBaseUrl,
  timeout: apiTimeoutMs,
  headers: {
    "Content-Type": "application/json",
  },
})

export async function askQuestion(payload: AskRequest): Promise<AskResponse> {
  const { data } = await apiClient.post<AskResponse>("/api/v1/ask", payload)
  return data
}

export function getApiBaseUrl() {
  return apiBaseUrl
}

export function getApiTimeoutMs() {
  return apiTimeoutMs
}
