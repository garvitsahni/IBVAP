import { cn } from "@/lib/utils"

interface StatusBadgeProps {
  severity: "critical" | "high" | "medium" | "low" | "info"
  className?: string
}

const SEVERITY_CONFIG = {
  critical: { label: "Critical", className: "bg-severity-critical/15 text-severity-critical" },
  high: { label: "High", className: "bg-severity-high/15 text-severity-high" },
  medium: { label: "Medium", className: "bg-severity-medium/15 text-severity-medium" },
  low: { label: "Low", className: "bg-severity-low/15 text-severity-low" },
  info: { label: "Info", className: "bg-severity-info/15 text-severity-info" },
}

export function StatusBadge({ severity, className }: StatusBadgeProps) {
  const config = SEVERITY_CONFIG[severity]
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", config.className, className)}>
      {config.label}
    </span>
  )
}
