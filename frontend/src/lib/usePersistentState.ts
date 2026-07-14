import { useEffect, useState } from "react"

// A drop-in replacement for useState that transparently persists the value to
// localStorage. This keeps feature content (chat messages, generated notes,
// form inputs, etc.) alive across tab switches and page refreshes, since React
// Router unmounts route components when you navigate away.
//
// Only persist meaningful content/inputs with this hook. Do NOT persist
// transient flags like `loading` or `streaming` — otherwise a refresh mid-run
// could leave the UI stuck in a loading state.

const PREFIX = "upscai:state:"

function read<T>(key: string, initial: T): T {
  try {
    const raw = window.localStorage.getItem(PREFIX + key)
    return raw === null ? initial : (JSON.parse(raw) as T)
  } catch {
    // Corrupt JSON or storage unavailable — fall back to the initial value.
    return initial
  }
}

export function usePersistentState<T>(key: string, initial: T) {
  const [state, setState] = useState<T>(() => read(key, initial))

  useEffect(() => {
    try {
      window.localStorage.setItem(PREFIX + key, JSON.stringify(state))
    } catch {
      // Storage full or unavailable — persistence is best-effort, so ignore.
    }
  }, [key, state])

  return [state, setState] as const
}
