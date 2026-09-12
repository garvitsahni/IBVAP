import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

interface StatCardProps {
  icon: LucideIcon
  label: string
  value: string | number
  tone?: "default" | "success" | "muted" | "danger"
  className?: string
}

const TONE = {
  default: "text-accent",
  success: "text-status-online",
  muted: "text-text-muted",
  danger: "text-severity-critical",
}

export function StatCard({ icon: Icon, label, value, tone = "default", className }: StatCardProps) {
  return (
    <div className={cn(
      "rounded-lg border border-border bg-surface px-4 py-3",
      className
    )}>
      <div className="flex items-center gap-3">
        <Icon size={16} className={cn("shrink-0", TONE[tone])} />
        <div className="min-w-0 flex-1">
          <p className="font-display text-xl font-semibold tracking-tight text-text-primary">
            {value}
          </p>
          <p className="text-[11px] font-medium uppercase tracking-wider text-text-muted">
            {label}
          </p>
        </div>
      </div>
    </div>
  )
}
