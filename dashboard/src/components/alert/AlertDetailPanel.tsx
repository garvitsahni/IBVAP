import { motion, AnimatePresence } from "framer-motion"
import { X, AlertTriangle, MapPin, Clock, Gauge } from "lucide-react"
import { Button } from "@/components/ui/Button"
import { StatusBadge } from "@/components/ui/StatusBadge"

interface AlertDetailPanelProps {
  alert: Alert | null
  onClose: () => void
  onAcknowledge?: (id: string) => void
  onEscalate?: (id: string) => void
  onFalsePositive?: (id: string) => void
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
            className="fixed inset-0 bg-black/50 z-40"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 bottom-0 w-[400px] bg-surface border-l border-border z-50 overflow-y-auto"
          >
            {/* Panel content */}
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-display font-semibold text-text">Alert Details</h2>
                <button onClick={onClose} className="text-text-muted hover:text-text">
                  <X className="h-5 w-5" />
                </button>
              </div>
              {/* ... rest of panel content */}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
