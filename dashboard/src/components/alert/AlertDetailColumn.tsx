import { useState } from "react"
import { MapPin, Clock, AlertTriangle, Camera, Hash, Sparkles } from "lucide-react"
import { StatusBadge } from "@/components/ui/StatusBadge"
import { api } from "@/services/api"
import { labelForReason, type FeedAlert } from "@/lib/alerts"

interface AlertDetailColumnProps {
  alert: FeedAlert | null
  onChanged: (updated: FeedAlert) => void
}

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

export function AlertDetailColumn({ alert, onChanged }: AlertDetailColumnProps) {
  const [error, setError] = useState<string | null>(null)
  const [snapshotFailed, setSnapshotFailed] = useState(false)

  if (!alert) {
    return (
      <div className="flex h-full min-h-[320px] items-center justify-center rounded-lg border border-border bg-surface">
        <p className="text-sm text-text-muted">Select an alert to view details</p>
      </div>
    )
  }

  const runAction = async (
    action: 'acknowledge' | 'escalate' | 'false-positive',
    nextStatus: string,
  ) => {
    const prev = alert.status
    setError(null)
    onChanged({ ...alert, status: nextStatus }) // optimistic
    try {
      if (action === 'acknowledge') await api.acknowledgeAlert(alert.id)
      else if (action === 'escalate') await api.escalateAlert(alert.id)
      else await api.falsePositiveAlert(alert.id)
    } catch (e) {
      onChanged({ ...alert, status: prev }) // revert
      setError(`Failed to update status (${String(e)})`)
    }
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto rounded-lg border border-border bg-surface">
      {/* Header */}
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-surface px-5 py-4">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-text-primary">Alert Detail</h2>
          <p className="text-[11px] text-text-muted font-mono">{alert.id}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge severity={alert.severity} />
          <span className="text-[11px] text-text-muted capitalize">{alert.status}</span>
        </div>
      </div>

      <div className="space-y-5 p-5">
        {/* Snapshot */}
        <div>
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-text-muted">Snapshot</p>
          <div className="flex aspect-video items-center justify-center overflow-hidden rounded-md border border-border bg-surface-2">
            {alert.snapshotPath && !snapshotFailed ? (
              <img
                src={api.alertSnapshotUrl(alert.id)}
                alt="Alert snapshot"
                className="h-full w-full object-contain"
                onError={() => setSnapshotFailed(true)}
              />
            ) : (
              <div className="text-center">
                <AlertTriangle size={20} className="mx-auto mb-1 text-text-muted/40" />
                <p className="text-[11px] text-text-muted">
                  {alert.snapshotPath ? "Snapshot failed to load" : "No snapshot captured"}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Severity + score */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-primary">{labelForReason(alert.type)}</span>
          <span className="font-mono text-[13px] text-text-secondary">
            score {alert.threatScore.toFixed(2)}
          </span>
        </div>

        {/* Reason detail */}
        {alert.reasonDetail && (
          <p className="rounded-md border border-border bg-surface-2 px-3 py-2 text-[13px] text-text-secondary">
            {alert.reasonDetail}
          </p>
        )}

        {/* Plate */}
        {alert.plateText && (
          <div className="flex items-center gap-2 text-[13px]">
            <Hash size={14} className="shrink-0 text-text-muted" />
            <span className="text-text-muted">Plate</span>
            <span className="ml-auto font-mono font-semibold tracking-wider text-severity-high">
              {alert.plateText}
            </span>
          </div>
        )}

        {/* Metadata */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-[13px]">
            <Camera size={14} className="shrink-0 text-text-muted" />
            <span className="text-text-muted">Camera</span>
            <span className="ml-auto font-mono text-text-primary">{alert.cameraId}</span>
          </div>
          <div className="flex items-center gap-2 text-[13px]">
            <Clock size={14} className="shrink-0 text-text-muted" />
            <span className="text-text-muted">Time</span>
            <span className="ml-auto text-text-primary">{formatTime(alert.timestamp)}</span>
          </div>
          <div className="flex items-center gap-2 text-[13px]">
            <MapPin size={14} className="shrink-0 text-text-muted" />
            <span className="text-text-muted">Status</span>
            <span className="ml-auto text-text-primary capitalize">{alert.status}</span>
          </div>
        </div>

        {/* AI explanation (only when backend provided it — never faked) */}
        {alert.aiExplanation && (
          <div className="rounded-md border border-border bg-surface-2 p-3">
            <p className="mb-1 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-text-muted">
              <Sparkles size={11} />
              AI · {alert.aiSource || "local"}
            </p>
            <p className="text-[13px] leading-relaxed text-text-secondary">{alert.aiExplanation}</p>
          </div>
        )}

        {/* Actions */}
        <div>
          <p className="mb-3 text-[10px] font-medium uppercase tracking-wider text-text-muted">Actions</p>
          <div className="flex gap-2">
            <button
              onClick={() => runAction('acknowledge', 'acknowledged')}
              disabled={alert.status === 'false_positive'}
              className="flex-1 rounded-md border border-border bg-surface-2 py-2 text-[12px] font-medium text-text-secondary transition-colors hover:bg-surface-3 hover:text-text disabled:cursor-not-allowed disabled:opacity-40"
            >
              Acknowledge
            </button>
            <button
              onClick={() => runAction('escalate', 'escalated')}
              disabled={alert.status === 'false_positive'}
              className="flex-1 rounded-md border border-severity-high/20 bg-severity-high/5 py-2 text-[12px] font-medium text-severity-high transition-colors hover:bg-severity-high/10 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Escalate
            </button>
            <button
              onClick={() => runAction('false-positive', 'false_positive')}
              disabled={alert.status === 'false_positive'}
              className="flex-1 rounded-md border border-border py-2 text-[12px] font-medium text-text-muted transition-colors hover:bg-surface-2 hover:text-text-secondary disabled:cursor-not-allowed disabled:opacity-40"
            >
              False Positive
            </button>
          </div>
          {error && <p className="mt-2 text-[11px] text-severity-critical">{error}</p>}
        </div>
      </div>
    </div>
  )
}
