import { NavLink } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "../lib/api"
import { useAuth } from "../lib/auth"
import { getApiBase, setApiBase } from "../lib/config"

const TOOLS: { to: string; icon: string; label: string }[] = [
  { to: "/app/mentor", icon: "\u{1F9E0}", label: "Mentor" },
  { to: "/app/planner", icon: "\u{1F5D3}\u{FE0F}", label: "Planner" },
  { to: "/app/pyq", icon: "\u2753", label: "PYQ Practice" },
  { to: "/app/ncert", icon: "\u{1F4DA}", label: "NCERT Library" },
  { to: "/app/upload", icon: "\u{1F4CE}", label: "Notes & Uploads" },
  { to: "/app/lecture", icon: "\u{1F3A7}", label: "Lecture Notes" },
  { to: "/app/current-affairs", icon: "\u{1F4F0}", label: "Current Affairs" },
  { to: "/app/evaluator", icon: "\u{1F4DD}", label: "Evaluator" },
]

const SPACE: { to: string; icon: string; label: string }[] = [
  { to: "/app/dashboard", icon: "\u{1F4CA}", label: "Dashboard" },
  { to: "/app/history", icon: "\u{1F550}", label: "History" },
]

const itemBase =
  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors"

function linkClass({ isActive }: { isActive: boolean }): string {
  return (
    itemBase +
    (isActive
      ? " bg-brand text-white"
      : " text-muted hover:bg-surface2 hover:text-fg")
  )
}

function SectionLabel({ children }: { children: string }) {
  return (
    <p className="px-3 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wider text-muted/70">
      {children}
    </p>
  )
}

export function Sidebar({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const { logout } = useAuth()
  const { data: access } = useQuery({
    queryKey: ["cost-access"],
    queryFn: () => api.costAccess(),
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
  const { data: expAccess } = useQuery({
    queryKey: ["experiments-access"],
    queryFn: () => api.experimentsAccess(),
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
  const { data: monAccess } = useQuery({
    queryKey: ["monitoring-access"],
    queryFn: () => api.monitoringAccess(),
    staleTime: 5 * 60 * 1000,
    retry: false,
  })

  const space = [
    ...SPACE,
    ...(access?.admin ? [{ to: "/app/cost", icon: "\u{1F4B0}", label: "Cost" }] : []),
    ...(expAccess?.admin
      ? [{ to: "/app/experiments", icon: "\u{1F9EA}", label: "Experiments" }]
      : []),
    ...(monAccess?.admin
      ? [{ to: "/app/monitoring", icon: "\u{1F4E1}", label: "Monitoring" }]
      : []),
  ]

  function changeBackend() {
    const v = window.prompt("Backend API base URL:", getApiBase())
    if (v) {
      setApiBase(v)
      window.location.reload()
    }
  }

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}
      <aside
        className={
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-border bg-surface transition-transform duration-200 lg:translate-x-0 " +
          (open ? "translate-x-0" : "-translate-x-full")
        }
      >
        {/* Brand */}
        <div className="flex items-center gap-2 border-b border-border px-4 py-4">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-brand text-lg font-extrabold text-white">
            U
          </span>
          <div className="leading-tight">
            <div className="font-extrabold">
              UPSC<span className="text-brand-400">AI</span>
            </div>
            <div className="text-[11px] text-muted">Your Personal Mentor</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-2 pb-4 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          <SectionLabel>Study Tools</SectionLabel>
          {TOOLS.map((t) => (
            <NavLink key={t.to} to={t.to} onClick={onClose} className={linkClass}>
              <span className="w-5 text-center">{t.icon}</span>
              <span>{t.label}</span>
            </NavLink>
          ))}

          <SectionLabel>My Space</SectionLabel>
          {space.map((t) => (
            <NavLink key={t.to} to={t.to} onClick={onClose} className={linkClass}>
              <span className="w-5 text-center">{t.icon}</span>
              <span>{t.label}</span>
            </NavLink>
          ))}

          <SectionLabel>Account</SectionLabel>
          <button
            onClick={changeBackend}
            className={itemBase + " w-full text-muted hover:bg-surface2 hover:text-fg"}
          >
            <span className="w-5 text-center">{"\u2699\u{FE0F}"}</span>
            <span>Settings</span>
          </button>
          <button
            onClick={() => void logout()}
            className={itemBase + " w-full text-muted hover:bg-surface2 hover:text-fg"}
          >
            <span className="w-5 text-center">{"\u{1F6AA}"}</span>
            <span>Logout</span>
          </button>
        </nav>
      </aside>
    </>
  )
}
