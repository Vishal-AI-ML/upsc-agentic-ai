import { useState } from "react"
import { api, streamAgent, type LectureResult } from "../../lib/api"
import { Markdown } from "../../components/Markdown"
import { Button, Card, Spinner } from "../../components/ui"
import { Feedback } from "../../components/Feedback"

type Tab = "youtube" | "text" | "audio"
const MEDIUMS = ["English", "Hindi", "Hinglish"]

const TABS: { id: Tab; label: string }[] = [
  { id: "youtube", label: "YouTube" },
  { id: "text", label: "Paste transcript" },
  { id: "audio", label: "Audio file" },
]

interface Msg {
  role: "user" | "assistant"
  content: string
}

export function Lecture() {
  const [tab, setTab] = useState<Tab>("youtube")
  const [medium, setMedium] = useState("English")
  const [youtubeUrl, setYoutubeUrl] = useState("")
  const [transcript, setTranscript] = useState("")

  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState("")
  const [lecture, setLecture] = useState<LectureResult | null>(null)

  const [q, setQ] = useState("")
  const [messages, setMessages] = useState<Msg[]>([])
  const [streaming, setStreaming] = useState(false)

  async function process(kind: Tab, file?: File) {
    if (processing) return
    setProcessing(true)
    setError("")
    setLecture(null)
    setMessages([])
    try {
      let r: LectureResult
      if (kind === "youtube") {
        if (!youtubeUrl.trim()) throw new Error("Please paste a YouTube URL.")
        r = await api.lectureProcess({ youtube_url: youtubeUrl.trim(), medium })
      } else if (kind === "text") {
        if (!transcript.trim()) throw new Error("Please paste a transcript.")
        r = await api.lectureProcessText({ transcript: transcript.trim(), medium })
      } else {
        if (!file) return
        r = await api.lectureProcessAudio(file, medium)
      }
      setLecture(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not process the lecture.")
    } finally {
      setProcessing(false)
    }
  }

  async function ask() {
    if (streaming || !q.trim() || !lecture) return
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
      "/lecture/chat",
      {
        question,
        video_id: lecture.video_id,
        topic_info: lecture.topic_info,
        chat_history: history,
      },
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-fg">Lecture Notes</h1>
        <p className="text-sm text-muted">
          Turn a YouTube lecture, a pasted transcript, or an audio file into structured
          notes — then chat with the lecture.
        </p>
      </div>

      <Card className="space-y-4">
        <div className="flex gap-1 rounded-lg border border-border p-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`flex-1 rounded-md px-3 py-1.5 text-sm ${
                tab === t.id ? "bg-surface2 text-fg" : "text-muted hover:text-fg"
              }`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div>
          <label className="label">Notes language</label>
          <select
            className="input"
            value={medium}
            onChange={(e) => setMedium(e.target.value)}
          >
            {MEDIUMS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        {tab === "youtube" && (
          <div className="space-y-3">
            <div>
              <label className="label">YouTube URL</label>
              <input
                className="input"
                value={youtubeUrl}
                onChange={(e) => setYoutubeUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=…"
              />
            </div>
            <Button
              onClick={() => void process("youtube")}
              disabled={processing || !youtubeUrl.trim()}
            >
              {processing ? "Processing…" : "Generate notes"}
            </Button>
          </div>
        )}

        {tab === "text" && (
          <div className="space-y-3">
            <div>
              <label className="label">Transcript</label>
              <textarea
                className="input min-h-[160px] resize-y"
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                placeholder="Paste the lecture transcript here…"
              />
            </div>
            <Button
              onClick={() => void process("text")}
              disabled={processing || !transcript.trim()}
            >
              {processing ? "Processing…" : "Generate notes"}
            </Button>
          </div>
        )}

        {tab === "audio" && (
          <div className="space-y-3">
            <label className="btn btn-brand cursor-pointer">
              {processing ? "Processing…" : "Upload audio"}
              <input
                type="file"
                accept="audio/*"
                className="hidden"
                disabled={processing}
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) void process("audio", f)
                  e.target.value = ""
                }}
              />
            </label>
            <p className="text-xs text-muted">
              Works for caption-less lectures. Large files may take a while to
              transcribe.
            </p>
          </div>
        )}

        {processing && <Spinner label="Transcribing and summarising…" />}
        {error && <p className="text-sm text-danger">{error}</p>}
      </Card>

      {lecture && (
        <Card className="space-y-3">
          <h2 className="text-lg font-semibold text-fg">Notes</h2>
          <Markdown>{lecture.notes}</Markdown>
        </Card>
      )}

      {lecture && (
        <Card className="space-y-3">
          <h2 className="text-lg font-semibold text-fg">Chat with this lecture</h2>
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
                    ) : i === messages.length - 1 && streaming ? (
                      <span className="text-muted">Thinking…</span>
                    ) : (
                      <span className="text-muted">
                        No response — please ask again.
                      </span>
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
              placeholder="Ask something about this lecture…"
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
              agent="lecture"
              question={messages[messages.length - 2]?.content || ""}
              answer={messages[messages.length - 1]?.content || ""}
            />
          )}
        </Card>
      )}
    </div>
  )
}
