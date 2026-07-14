import { useState } from "react"
import { usePersistentState } from "../../lib/usePersistentState"
import { api, streamAgent, type UploadResult } from "../../lib/api"
import { Markdown } from "../../components/Markdown"
import { Button, Card, Spinner } from "../../components/ui"
import { Feedback } from "../../components/Feedback"

interface Msg {
  role: "user" | "assistant"
  content: string
}

export function Upload() {
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState("")
  const [doc, setDoc] = usePersistentState<UploadResult | null>("upload:doc", null)

  const [q, setQ] = useState("")
  const [messages, setMessages] = usePersistentState<Msg[]>("upload:messages", [])
  const [streaming, setStreaming] = useState(false)

  async function upload(file: File) {
    setProcessing(true)
    setError("")
    setDoc(null)
    setMessages([])
    try {
      const r = await api.uploadProcess(file)
      setDoc(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not process the PDF.")
    } finally {
      setProcessing(false)
    }
  }

  async function ask() {
    if (streaming || !q.trim() || !doc) return
    const question = q.trim()
    const history = messages
    setQ("")
    setMessages([
      ...history,
      { role: "user", content: question },
      { role: "assistant", content: "" },
    ])
    setStreaming(true)
    await streamAgent(
      "/upload/chat?pdf_hash=" + encodeURIComponent(doc.hash),
      { request: { question, chat_history: history } },
      (piece) =>
        setMessages((prev) => {
          const next = [...prev]
          const last = next[next.length - 1]
          if (last && last.role === "assistant") {
            next[next.length - 1] = { ...last, content: last.content + piece }
          }
          return next
        }),
    )
    setStreaming(false)
  }

  const bookTitle =
    doc && typeof doc.book_info?.title === "string"
      ? (doc.book_info.title as string)
      : doc?.filename

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-fg">Document Upload</h1>
        <p className="text-sm text-muted">
          Upload a PDF (book chapter, notes, or report) to get clean study notes, then
          chat with the document to clear your doubts.
        </p>
      </div>

      <Card className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <label className="btn btn-brand cursor-pointer">
            {processing ? "Processing…" : "Upload PDF"}
            <input
              type="file"
              accept="application/pdf"
              className="hidden"
              disabled={processing}
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void upload(f)
                e.target.value = ""
              }}
            />
          </label>
          {processing && <Spinner label="Reading and summarising your PDF…" />}
          {doc && !processing && (
            <span className="text-sm text-muted">Loaded: {bookTitle}</span>
          )}
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
      </Card>

      {doc && (
        <Card className="space-y-3">
          <h2 className="text-lg font-semibold text-fg">Study notes</h2>
          <Markdown>{doc.notes}</Markdown>
        </Card>
      )}

      {doc && (
        <Card className="space-y-3">
          <h2 className="text-lg font-semibold text-fg">Chat with this document</h2>
          <div className="space-y-3">
            {messages.map((m, i) => (
              <div
                key={i}
                className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                    m.role === "user"
                      ? "bg-brand text-white"
                      : "border border-border bg-surface"
                  }`}
                >
                  {m.role === "assistant" ? (
                    m.content ? (
                      <Markdown>{m.content}</Markdown>
                    ) : (
                      <span className="text-muted">Thinking…</span>
                    )
                  ) : (
                    <span className="whitespace-pre-wrap">{m.content}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="flex items-end gap-2">
            <textarea
              className="input max-h-40 min-h-[48px] flex-1 resize-y"
              placeholder="Ask something about this document…"
              value={q}
              rows={1}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  void ask()
                }
              }}
            />
            <Button onClick={() => void ask()} disabled={streaming || !q.trim()}>
              {streaming ? "…" : "Ask"}
            </Button>
          </div>
          {messages.length > 0 && !streaming && (
            <Feedback
              agent="upload"
              question={messages[messages.length - 2]?.content || ""}
              answer={messages[messages.length - 1]?.content || ""}
            />
          )}
        </Card>
      )}
    </div>
  )
}
