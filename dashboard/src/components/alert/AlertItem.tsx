import { BorderBeam } from "@/registry/magicui/border-beam"
import { StatusBadge } from "@/components/ui/StatusBadge"
import { Camera } from "lucide-react"
import { cn } from "@/lib/utils"

interface AlertItemProps {
  alert: {
    id: string
    type: string
    severity: "critical" | "high" | "medium" | "low" | "info"
    cameraId: string
    timestamp: string
    status: string
  }
  isSelected?: boolean
  onClick?: () => void
}

function timeAgo(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export function AlertItem({ alert, isSelected, onClick }: AlertItemProps) {
  const isCritical = alert.severity === "critical"
  return (
    <div
      onClick={onClick}
      className={cn(
        "relative cursor-pointer border-l-4 p-3 transition-colors hover:bg-surface-2",
        {
          "border-l-severity-critical": alert.severity === "critical",
          "border-l-severity-high": alert.severity === "high",
          "border-l-severity-medium": alert.severity === "medium",
          "border-l-severity-low": alert.severity === "low",
          "border-l-severity-info": alert.severity === "info",
        },
        isSelected && "bg-surface-2",
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-text">{alert.type}</span>
        <StatusBadge severity={alert.severity} />
      </div>
      <div className="mt-1 flex items-center gap-2 text-xs text-text-muted">
        <Camera className="h-3 w-3" />
        <span className="font-mono">{alert.cameraId}</span>
        <span>·</span>
        <span>{timeAgo(alert.timestamp)}</span>
      </div>
      {isCritical && (
        <BorderBeam duration={4} size={100} className="from-transparent via-severity-critical/30 to-transparent" />
      )}
    </div>
  )
}
