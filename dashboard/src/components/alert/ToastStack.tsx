import { motion, AnimatePresence } from "framer-motion"
import { StatusBadge } from "@/components/ui/StatusBadge"
import { Camera } from "lucide-react"

interface Toast {
  id: string
  type: string
  severity: "critical" | "high" | "medium" | "low" | "info"
  cameraId: string
}

interface ToastStackProps {
  toasts: Toast[]
  onDismiss?: (id: string) => void
}

export function ToastStack({ toasts, onDismiss }: ToastStackProps) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="w-80 rounded-lg border border-border bg-surface p-4 shadow-lg"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-text">{toast.type}</span>
              <StatusBadge severity={toast.severity} />
            </div>
            <div className="mt-1 flex items-center gap-1 text-xs text-text-muted">
              <Camera className="h-3 w-3" />
              <span className="font-mono">{toast.cameraId}</span>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
