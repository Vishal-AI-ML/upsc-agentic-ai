import { Link } from "react-router-dom"

const AGENTS: { icon: string; title: string; desc: string }[] = [
  {
    icon: "\u{1F9E0}",
    title: "AI Mentor",
    desc: "Ask doubts, get strategy and grounded answers with a personal UPSC coach.",
  },
  {
    icon: "\u{1F5D3}\u{FE0F}",
    title: "Study Planner",
    desc: "A personalized timeline to Prelims with daily and weekly targets.",
  },
  {
    icon: "\u2753",
    title: "PYQ Practice",
    desc: "Previous-year style questions plus your own personal question bank.",
  },
  {
    icon: "\u{1F4DA}",
    title: "NCERT Notes",
    desc: "Chapter-wise notes and a RAG chat grounded strictly in the text.",
  },
  {
    icon: "\u{1F4F0}",
    title: "Current Affairs",
    desc: "Daily headlines, editorial frameworks and honest monthly digests.",
  },
  {
    icon: "\u{1F3A7}",
    title: "Lecture Notes",
    desc: "Turn YouTube or audio lectures into clean, structured revision notes.",
  },
  {
    icon: "\u{1F4CE}",
    title: "Upload & Study",
    desc: "Drop your own PDFs and get notes, chat and spaced revision cards.",
  },
  {
    icon: "\u{1F4DD}",
    title: "Answer Evaluator",
    desc: "Mains answer scoring with rubric feedback and a model answer.",
  },
]

const TRUST: { icon: string; title: string; desc: string }[] = [
  {
    icon: "\u{1F517}",
    title: "Grounded & cited",
    desc: "Answers stay tied to your material, with sources you can verify.",
  },
  {
    icon: "\u2705",
    title: "Continuously evaluated",
    desc: "Automated eval pipelines check faithfulness and retrieval quality.",
  },
  {
    icon: "\u{1F6E1}\u{FE0F}",
    title: "Safe by design",
    desc: "Prompt-injection defence and per-user private data isolation.",
  },
  {
    icon: "\u26A1",
    title: "Fast & reliable",
    desc: "Cached responses and automatic model fallback keep it running.",
  },
]

const STEPS: { n: string; t: string; d: string }[] = [
  { n: "1", t: "Create your account", d: "Sign up free with your email." },
  { n: "2", t: "Pick an agent", d: "Start with a plan, a doubt or NCERT notes." },
  { n: "3", t: "Learn and revise", d: "Track progress and revise with spaced cards." },
]

function Brand() {
  return (
    <div className="flex items-center gap-2 font-extrabold">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand text-white">
        U
      </span>
      <span>
        UPSC<span className="text-brand-400">AI</span>
      </span>
    </div>
  )
}

export function Landing() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-border bg-bg/80 backdrop-blur">
        <div className="mx-auto flex max-w-screen-xl items-center justify-between px-4 py-3">
          <Brand />
          <div className="flex items-center gap-2">
            <Link to="/login" className="btn btn-ghost text-sm">
              Sign in
            </Link>
            <Link to="/login" className="btn btn-brand text-sm">
              Get started
            </Link>
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[420px] opacity-40 bg-[radial-gradient(600px_300px_at_50%_-10%,#7c3aed55,transparent_70%)]" />
        <div className="relative mx-auto max-w-screen-xl px-4 py-20 text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface2 px-3 py-1 text-xs font-medium text-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Built for UPSC Civil Services aspirants
          </span>
          <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-extrabold leading-tight sm:text-5xl">
            Your entire UPSC prep,
            <br />
            powered by <span className="text-brand-400">AI agents</span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-muted">
            Mentor, planner, PYQ practice, NCERT notes, current affairs and
            answer evaluation - all grounded in real material, cited, and built
            to get you exam-ready.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link to="/login" className="btn btn-brand px-6 py-3 text-base">
              Start free
            </Link>
            <Link to="/login" className="btn btn-ghost px-6 py-3 text-base">
              Sign in
            </Link>
          </div>
          <p className="mt-4 text-xs text-muted">
            No credit card &middot; Free to start &middot; Answers you can
            verify
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-screen-xl px-4 py-12">
        <div className="mb-8 text-center">
          <h2 className="text-2xl font-bold">Ten agents. One workflow.</h2>
          <p className="mt-2 text-muted">
            Each agent is focused on a real part of your preparation.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {AGENTS.map((a) => (
            <div
              key={a.title}
              className="card p-5 transition-colors hover:border-brand-400"
            >
              <div className="mb-3 grid h-10 w-10 place-items-center rounded-lg bg-surface2 text-xl">
                {a.icon}
              </div>
              <h3 className="font-semibold">{a.title}</h3>
              <p className="mt-1 text-sm text-muted">{a.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-y border-border bg-surface/40">
        <div className="mx-auto max-w-screen-xl px-4 py-12">
          <div className="mb-8 text-center">
            <h2 className="text-2xl font-bold">Built to be trusted</h2>
            <p className="mt-2 text-muted">
              Exam prep needs accuracy. This is engineered for it.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {TRUST.map((t) => (
              <div key={t.title} className="flex gap-3">
                <div className="text-2xl">{t.icon}</div>
                <div>
                  <h3 className="font-semibold">{t.title}</h3>
                  <p className="mt-1 text-sm text-muted">{t.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-screen-xl px-4 py-12">
        <div className="mb-8 text-center">
          <h2 className="text-2xl font-bold">Get going in minutes</h2>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {STEPS.map((s) => (
            <div key={s.n} className="card p-5">
              <div className="grid h-8 w-8 place-items-center rounded-full bg-brand font-bold text-white">
                {s.n}
              </div>
              <h3 className="mt-3 font-semibold">{s.t}</h3>
              <p className="mt-1 text-sm text-muted">{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-screen-xl px-4 pb-16">
        <div className="card overflow-hidden p-10 text-center">
          <h2 className="text-2xl font-bold sm:text-3xl">
            Ready to start your preparation?
          </h2>
          <p className="mx-auto mt-2 max-w-xl text-muted">
            Join and let your AI agents handle the heavy lifting.
          </p>
          <div className="mt-6 flex justify-center">
            <Link to="/login" className="btn btn-brand px-6 py-3 text-base">
              Start free
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-screen-xl flex-col items-center justify-between gap-3 px-4 py-6 text-sm text-muted sm:flex-row">
          <Brand />
          <p>&copy; {new Date().getFullYear()} UPSC AI Pro. For aspirants, by design.</p>
        </div>
      </footer>
    </div>
  )
}
