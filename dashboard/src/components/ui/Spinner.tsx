import { cn } from "@/lib/utils"

interface SpinnerProps {
  label?: string
  className?: string
  size?: "sm" | "md" | "lg"
}

const SIZE_MAP = {
  sm: "h-4 w-4 border-2",
  md: "h-6 w-6 border-2",
  lg: "h-8 w-8 border-[3px]",
}

export function Spinner({ label = "Loading", className, size = "md" }: SpinnerProps) {
  return (
    <div className={cn("flex items-center gap-2", className)} role="status" aria-live="polite">
      <span
        className={cn(
          "animate-spin rounded-full border-surface-3 border-t-accent",
          SIZE_MAP[size],
        )}
        aria-hidden="true"
      />
      <span className="text-sm text-text-muted">{label}</span>
    </div>
  )
}
