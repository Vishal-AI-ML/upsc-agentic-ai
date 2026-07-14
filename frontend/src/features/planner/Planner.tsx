import { useState } from "react"
import { usePersistentState } from "../../lib/usePersistentState"
import { streamAgent } from "../../lib/api"
import { Markdown } from "../../components/Markdown"
import { Button, Card } from "../../components/ui"
import { Feedback } from "../../components/Feedback"

const ATTEMPTS = ["1", "2", "3", "4+"]

export function Planner() {
  const [goal, setGoal] = usePersistentState("planner:goal", "UPSC 2026")
  const [hours, setHours] = usePersistentState("planner:hours", "6")
  const [optional, setOptional] = usePersistentState("planner:optional", "")
  const [weak, setWeak] = usePersistentState("planner:weak", "")
  const [attempt, setAttempt] = usePersistentState("planner:attempt", "1")

  const [streaming, setStreaming] = useState(false)
  const [plan, setPlan] = usePersistentState("planner:plan", "")
  const [lastGoal, setLastGoal] = usePersistentState("planner:lastGoal", "")

  async function generate() {
    if (streaming || !goal.trim()) return
    setStreaming(true)
    setPlan("")
    setLastGoal(goal.trim())
    await streamAgent(
      "/planner/generate",
      {
        goal: goal.trim(),
        hours: hours.trim() || "6",
        optional: optional.trim() || "Not decided",
        weak: weak.trim() || "Not specified",
        attempt_number: attempt,
      },
      (piece) => setPlan((p) => p + piece),
    )
    setStreaming(false)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-fg">Study Planner</h1>
        <p className="text-sm text-muted">
          Generate a personalised UPSC preparation timeline. Leave weak areas blank and
          they are auto-filled from your recent evaluations.
        </p>
      </div>

      <Card className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label">Goal</label>
            <input
              className="input"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="e.g. UPSC 2026"
            />
          </div>
          <div>
            <label className="label">Daily study hours</label>
            <input
              className="input"
              value={hours}
              onChange={(e) => setHours(e.target.value)}
              placeholder="e.g. 6"
            />
          </div>
          <div>
            <label className="label">Optional subject</label>
            <input
              className="input"
              value={optional}
              onChange={(e) => setOptional(e.target.value)}
              placeholder="e.g. Sociology (or leave blank)"
            />
          </div>
          <div>
            <label className="label">Attempt number</label>
            <select
              className="input"
              value={attempt}
              onChange={(e) => setAttempt(e.target.value)}
            >
              {ATTEMPTS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <label className="label">Weak areas (optional)</label>
          <input
            className="input"
            value={weak}
            onChange={(e) => setWeak(e.target.value)}
            placeholder="e.g. Economy, Environment — or leave blank to auto-fill"
          />
        </div>
        <Button onClick={() => void generate()} disabled={streaming || !goal.trim()}>
          {streaming ? "Generating…" : "Generate plan"}
        </Button>
      </Card>

      {plan && (
        <Card className="space-y-3">
          <Markdown>{plan}</Markdown>
          {!streaming && <Feedback agent="planner" question={lastGoal} answer={plan} />}
        </Card>
      )}
    </div>
  )
}
