// Resolve the backend API base URL. Priority:
//   1. localStorage override (set via the ⚙️ settings button) — handy for testing
//   2. VITE_API_BASE from the build/env
//   3. Render production default
const DEFAULT_API = "https://upsc-agentic-ai.onrender.com/api/v1"
const LS_API = "upscai-api"

export function getApiBase(): string {
  const override = localStorage.getItem(LS_API)
  if (override) return override.replace(/\/$/, "")
  const env = import.meta.env.VITE_API_BASE
  return (env || DEFAULT_API).replace(/\/$/, "")
}

export function setApiBase(url: string): void {
  localStorage.setItem(LS_API, url.replace(/\/$/, ""))
}

export function healthUrl(): string {
  return getApiBase().replace(/\/api\/v1\/?$/, "") + "/health"
}
