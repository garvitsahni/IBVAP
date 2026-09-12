import { cn } from "@/lib/utils"

interface StatusBadgeProps {
  severity: "critical" | "high" | "medium" | "low" | "info"
  className?: string
}

const SEVERITY_CONFIG = {
  critical: { label: "Critical", className: "bg-severity-critical/10 text-severity-critical border border-severity-critical/20" },
  high: { label: "High", className: "bg-severity-high/10 text-severity-high border border-severity-high/20" },
  medium: { label: "Medium", className: "bg-severity-medium/10 text-severity-medium border border-severity-medium/20" },
  low: { label: "Low", className: "bg-severity-low/10 text-severity-low border border-severity-low/20" },
  info: { label: "Info", className: "bg-severity-info/10 text-severity-info border border-severity-info/20" },
}

export function StatusBadge({ severity, className }: StatusBadgeProps) {
  const config = SEVERITY_CONFIG[severity]
  return (
    <span className={cn("inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide", config.className, className)}>
      {config.label}
    </span>
  )
}
