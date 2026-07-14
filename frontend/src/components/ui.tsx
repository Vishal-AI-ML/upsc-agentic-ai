import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react"

export function Button({
  variant = "brand",
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "brand" | "ghost" }) {
  const v = variant === "brand" ? "btn-brand" : "btn-ghost"
  return (
    <button className={`btn ${v} ${className}`} {...props}>
      {children}
    </button>
  )
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className="input" {...props} />
}

export function Card({
  children,
  className = "",
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={`card p-5 ${className}`}>{children}</div>
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-brand-400" />
      {label}
    </span>
  )
}
