import { Suspense, lazy, useState } from "react"
import { Navigate, Route, Routes } from "react-router-dom"
import { Sidebar } from "../components/Sidebar"
import { Topbar } from "../components/Topbar"
import { Spinner } from "../components/ui"

// Route-level code splitting: each feature ships as its own lazy chunk, so the
// initial app bundle stays small and a feature's JS is only fetched the first
// time it is visited. Layout chrome (Sidebar/Topbar) stays eager.
const MentorChat = lazy(() =>
  import("../features/mentor/MentorChat").then((m) => ({ default: m.MentorChat })),
)
const Dashboard = lazy(() =>
  import("../features/dashboard/Dashboard").then((m) => ({ default: m.Dashboard })),
)
const History = lazy(() =>
  import("../features/history/History").then((m) => ({ default: m.History })),
)
const Evaluator = lazy(() =>
  import("../features/evaluator/Evaluator").then((m) => ({ default: m.Evaluator })),
)
const Cost = lazy(() =>
  import("../features/cost/Cost").then((m) => ({ default: m.Cost })),
)
const Experiments = lazy(() => import("../features/experiments/Experiments"))
const Monitoring = lazy(() =>
  import("../features/monitoring/Monitoring").then((m) => ({ default: m.Monitoring })),
)
const Planner = lazy(() =>
  import("../features/planner/Planner").then((m) => ({ default: m.Planner })),
)
const Pyq = lazy(() =>
  import("../features/pyq/Pyq").then((m) => ({ default: m.Pyq })),
)
const Ncert = lazy(() =>
  import("../features/ncert/Ncert").then((m) => ({ default: m.Ncert })),
)
const CurrentAffairs = lazy(() =>
  import("../features/current_affairs/CurrentAffairs").then((m) => ({
    default: m.CurrentAffairs,
  })),
)
const Lecture = lazy(() =>
  import("../features/lecture/Lecture").then((m) => ({ default: m.Lecture })),
)
const Upload = lazy(() =>
  import("../features/upload/Upload").then((m) => ({ default: m.Upload })),
)

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-h-screen flex-col lg:pl-64">
        <Topbar onMenuClick={() => setSidebarOpen(true)} />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
          <Suspense
            fallback={
              <div className="grid place-items-center py-20">
                <Spinner label="Loading…" />
              </div>
            }
          >
            <Routes>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="mentor" element={<MentorChat />} />
              <Route path="evaluator" element={<Evaluator />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="history" element={<History />} />
              <Route path="cost" element={<Cost />} />
              <Route path="experiments" element={<Experiments />} />
              <Route path="monitoring" element={<Monitoring />} />
              <Route path="planner" element={<Planner />} />
              <Route path="pyq" element={<Pyq />} />
              <Route path="ncert" element={<Ncert />} />
              <Route path="current-affairs" element={<CurrentAffairs />} />
              <Route path="lecture" element={<Lecture />} />
              <Route path="upload" element={<Upload />} />
              <Route path="*" element={<Navigate to="dashboard" replace />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </div>
  )
}
