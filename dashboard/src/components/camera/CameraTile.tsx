import { BorderBeam } from "@/registry/magicui/border-beam"
import { Camera, Wifi, WifiOff } from "lucide-react"
import { cn } from "@/lib/utils"

interface CameraTileProps {
  camera: { id: string; name: string; status: "online" | "offline" | "degraded"; lastSeen?: string }
  onClick?: () => void
}

export function CameraTile({ camera, onClick }: CameraTileProps) {
  const isOnline = camera.status === "online"
  return (
    <div
      onClick={onClick}
      className={cn(
        "relative cursor-pointer overflow-hidden rounded-xl border border-border bg-surface aspect-video",
        "transition-all hover:border-accent/50 hover:shadow-lg hover:shadow-accent/5",
      )}
    >
      {isOnline ? (
        <div className="absolute inset-0 bg-gradient-to-br from-surface-2 to-surface-3" />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center bg-surface-2">
          <WifiOff className="h-8 w-8 text-text-muted" />
          <span className="ml-2 text-sm text-text-muted">Signal lost</span>
        </div>
      )}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-bg/80 to-transparent p-3">
        <div className="flex items-center gap-2">
          <Camera className="h-4 w-4 text-text-secondary" />
          <span className="text-sm font-medium text-text">{camera.name}</span>
        </div>
        <span className="font-mono text-xs text-text-muted">{camera.id}</span>
      </div>
      {isOnline && (
        <div className="absolute top-3 right-3">
          <span className="flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-status-online opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-status-online" />
          </span>
        </div>
      )}
      {isOnline && <BorderBeam duration={6} size={200} className="from-transparent via-status-online/30 to-transparent" />}
    </div>
  )
}
