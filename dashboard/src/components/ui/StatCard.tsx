import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

interface StatCardProps {
  icon: LucideIcon
  label: string
  value: string | number
  tone?: "primary" | "success" | "muted" | "danger"
  hint?: string
  className?: string
}

const ICON_BG = {
  primary: "bg-accent/10 text-accent",
  success: "bg-severity-low/10 text-severity-low",
  muted: "bg-surface-2 text-text-muted",
  danger: "bg-severity-critical/10 text-severity-critical",
}

export function StatCard({ icon: Icon, label, value, tone = "primary", hint, className }: StatCardProps) {
  return (
    <div className={cn("flex items-center gap-3 rounded-lg border border-border bg-surface p-4 shadow-card", className)}>
      <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-full", ICON_BG[tone])}>
        <Icon size={18} />
      </div>
      <div className="min-w-0">
        <p className="text-xl font-semibold leading-tight text-text">{value}</p>
        <p className="truncate text-xs text-text-muted">{label}</p>
      </div>
      {hint && <span className="ml-auto shrink-0 text-[11px] text-text-muted">{hint}</span>}
    </div>
  )
}
