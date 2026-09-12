import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { NumberTicker } from "@/registry/magicui/number-ticker"

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
    <div className={cn(
      "group relative overflow-hidden rounded-xl border border-border bg-surface p-4 shadow-card",
      "transition-all duration-300 hover:border-accent/30 hover:shadow-lg hover:shadow-accent/5",
      "hover:-translate-y-0.5",
      className
    )}>
      <div className="absolute inset-0 bg-gradient-to-br from-accent/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
      <div className="relative flex items-center gap-3">
        <div className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-xl", ICON_BG[tone])}>
          <Icon size={20} />
        </div>
        <div className="min-w-0">
          <p className="text-2xl font-bold leading-tight text-text">
            {typeof value === "number" ? (
              <NumberTicker value={value} />
            ) : (
              value
            )}
          </p>
          <p className="truncate text-xs text-text-muted">{label}</p>
        </div>
        {hint && <span className="ml-auto shrink-0 text-[11px] text-text-muted">{hint}</span>}
      </div>
    </div>
  )
}
