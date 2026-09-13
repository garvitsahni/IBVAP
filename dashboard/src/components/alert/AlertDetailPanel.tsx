import { motion, AnimatePresence } from "framer-motion"
import { X, MapPin, Clock, AlertTriangle, Camera, Hash } from "lucide-react"
import { StatusBadge } from "@/components/ui/StatusBadge"

interface Alert {
  id: string
  type: string
  severity: "critical" | "high" | "medium" | "low" | "info"
  cameraId: string
  timestamp: string
  status: string
  plateText?: string | null
}

interface AlertDetailPanelProps {
  alert: Alert | null
  onClose: () => void
  onAcknowledge?: (id: string) => void
  onEscalate?: (id: string) => void
  onFalsePositive?: (id: string) => void
}

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function AlertDetailPanel({ alert, onClose, onAcknowledge, onEscalate, onFalsePositive }: AlertDetailPanelProps) {
  return (
    <AnimatePresence>
      {alert && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 bg-black/40 z-40"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 bottom-0 w-[420px] bg-surface border-l border-border z-50 overflow-y-auto"
          >
            {/* Header */}
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-surface px-5 py-4">
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-text-primary">Alert Detail</h2>
                <p className="text-[11px] text-text-muted font-mono">{alert.id}</p>
              </div>
              <button
                onClick={onClose}
                className="rounded-md p-1.5 text-text-muted transition-colors hover:bg-surface-2 hover:text-text"
              >
                <X size={16} />
              </button>
            </div>

            {/* Content */}
            <div className="p-5 space-y-5">
              {/* Severity + Status */}
              <div className="flex items-center gap-3">
                <StatusBadge severity={alert.severity} />
                <span className="text-[11px] text-text-muted capitalize">{alert.status}</span>
              </div>

              {/* Alert Type */}
              <div>
                <p className="text-[10px] font-medium uppercase tracking-wider text-text-muted mb-1">Type</p>
                <p className="text-sm text-text-primary">{alert.type}</p>
              </div>

              {/* Metadata */}
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-[13px]">
                  <Camera size={14} className="text-text-muted shrink-0" />
                  <span className="text-text-muted">Camera</span>
                  <span className="ml-auto font-mono text-text-primary">{alert.cameraId}</span>
                </div>
                <div className="flex items-center gap-2 text-[13px]">
                  <Clock size={14} className="text-text-muted shrink-0" />
                  <span className="text-text-muted">Time</span>
                  <span className="ml-auto text-text-primary">{formatTime(alert.timestamp)}</span>
                </div>
                {alert.plateText && (
                  <div className="flex items-center gap-2 text-[13px]">
                    <Hash size={14} className="text-text-muted shrink-0" />
                    <span className="text-text-muted">Plate</span>
                    <span className="ml-auto font-mono text-severity-high font-semibold tracking-wider">
                      {alert.plateText}
                    </span>
                  </div>
                )}
              </div>

              {/* Divider */}
              <div className="border-t border-border" />

              {/* Snapshot placeholder */}
              <div>
                <p className="text-[10px] font-medium uppercase tracking-wider text-text-muted mb-2">Snapshot</p>
                <div className="aspect-video rounded-md border border-border bg-surface-2 flex items-center justify-center">
                  <div className="text-center">
                    <AlertTriangle size={20} className="mx-auto mb-1 text-text-muted/40" />
                    <p className="text-[11px] text-text-muted">No snapshot available</p>
                  </div>
                </div>
              </div>

              {/* Divider */}
              <div className="border-t border-border" />

              {/* Actions */}
              <div>
                <p className="text-[10px] font-medium uppercase tracking-wider text-text-muted mb-3">Actions</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => onAcknowledge?.(alert.id)}
                    className="flex-1 rounded-md border border-border bg-surface-2 py-2 text-[12px] font-medium text-text-secondary transition-colors hover:bg-surface-3 hover:text-text"
                  >
                    Acknowledge
                  </button>
                  <button
                    onClick={() => onEscalate?.(alert.id)}
                    className="flex-1 rounded-md border border-severity-high/20 bg-severity-high/5 py-2 text-[12px] font-medium text-severity-high transition-colors hover:bg-severity-high/10"
                  >
                    Escalate
                  </button>
                  <button
                    onClick={() => onFalsePositive?.(alert.id)}
                    className="flex-1 rounded-md border border-border py-2 text-[12px] font-medium text-text-muted transition-colors hover:bg-surface-2 hover:text-text-secondary"
                  >
                    False Positive
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
