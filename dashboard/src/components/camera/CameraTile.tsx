import { WifiOff } from "lucide-react"
import { cn } from "@/lib/utils"

interface CameraTileProps {
  camera: { id: string; name: string; status: "online" | "offline" | "degraded"; lastSeen?: string }
  onClick?: () => void
}

export function CameraTile({ camera, onClick }: CameraTileProps) {
  const isOnline = camera.status === "online"
  const isDegraded = camera.status === "degraded"

  return (
    <div
      onClick={onClick}
      className={cn(
        "relative overflow-hidden rounded-lg border bg-surface aspect-video",
        "transition-all duration-200",
        isOnline && "border-border hover:border-accent/30",
        !isOnline && "border-border opacity-60",
      )}
    >
      {isOnline ? (
        <div className="absolute inset-0 bg-surface-2">
          <div className="absolute inset-0 opacity-[0.03]" style={{
            backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.05) 2px, rgba(255,255,255,0.05) 4px)"
          }} />
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
            <div className="h-px w-8 bg-accent/20" />
            <div className="absolute left-1/2 top-1/2 h-8 w-px -translate-x-1/2 -translate-y-1/2 bg-accent/20" />
          </div>
        </div>
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-surface-2">
          <WifiOff className="mb-1 h-5 w-5 text-text-muted/50" />
          <span className="text-[10px] text-text-muted">No Signal</span>
        </div>
      )}

      {/* Bottom info bar */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-bg/90 to-transparent p-2.5 pt-6">
        <div className="flex items-center justify-between">
          <div className="min-w-0">
            <p className="truncate text-[12px] font-medium text-text-primary">{camera.name}</p>
            <p className="font-mono text-[10px] text-text-muted">{camera.id}</p>
          </div>
          <div className={cn(
            "h-1.5 w-1.5 rounded-full shrink-0",
            isOnline && "bg-status-online",
            isDegraded && "bg-status-degraded",
            !isOnline && "bg-text-muted",
          )} />
        </div>
      </div>

      {/* Top-left camera index */}
      <div className="absolute left-2 top-2">
        <span className="font-mono text-[10px] text-text-muted/60">
          CAM-{camera.id.slice(-2).toUpperCase()}
        </span>
      </div>
    </div>
  )
}
