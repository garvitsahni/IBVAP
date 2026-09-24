import { StatusBadge } from "@/components/ui/StatusBadge"
import { Camera, ImageOff } from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/services/api"
import type { FeedAlert } from "@/lib/alerts"

interface AlertItemProps {
  alert: FeedAlert
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

function statusDotColor(status: string): string {
  switch (status) {
    case "fired": return "bg-severity-critical"
    case "enriched": return "bg-severity-high"
    case "acknowledged": return "bg-status-online"
    case "escalated": return "bg-severity-critical animate-pulse"
    case "false_positive": return "bg-text-muted"
    default: return "bg-text-muted"
  }
}

export function AlertItem({ alert, isSelected, onClick }: AlertItemProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "flex cursor-pointer gap-3 border-l-2 px-3 py-2.5 transition-colors",
        {
          "border-l-severity-critical bg-severity-critical/5": alert.severity === "critical" && !isSelected,
          "border-l-severity-high bg-severity-high/5": alert.severity === "high" && !isSelected,
          "border-l-severity-medium": alert.severity === "medium" && !isSelected,
          "border-l-severity-low": alert.severity === "low" && !isSelected,
          "border-l-severity-info": alert.severity === "info" && !isSelected,
        },
        isSelected && "bg-surface-3 border-l-accent",
        !isSelected && "hover:bg-surface-2"
      )}
    >
      {/* Thumbnail */}
      <div className="h-12 w-16 shrink-0 overflow-hidden rounded border border-border bg-surface-2">
        {alert.snapshotPath ? (
          <img
            src={api.alertSnapshotUrl(alert.id)}
            alt=""
            loading="lazy"
            className="h-full w-full object-cover"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none" }}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <ImageOff size={14} className="text-text-muted/40" />
          </div>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 truncate text-[13px] font-medium text-text-primary">
            <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", statusDotColor(alert.status))} />
            {alert.type}
          </span>
          <StatusBadge severity={alert.severity} />
        </div>
        <div className="mt-1 flex items-center gap-1.5 text-[11px] text-text-muted">
          <Camera size={11} />
          <span className="font-mono">{alert.cameraId}</span>
          <span className="text-border-subtle">·</span>
          <span>{timeAgo(alert.timestamp)}</span>
        </div>
        {alert.plateText && (
          <div className="mt-1 inline-block rounded bg-severity-high/10 px-1.5 py-0.5 text-[11px] font-mono font-semibold tracking-wider text-severity-high">
            {alert.plateText}
          </div>
        )}
        {alert.reasonDetail && (
          <p className="mt-1 truncate text-[11px] text-text-muted" title={alert.reasonDetail}>
            {alert.reasonDetail}
          </p>
        )}
      </div>
    </div>
  )
}
