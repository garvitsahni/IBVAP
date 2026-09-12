"use client"

import { cn } from "@/lib/utils"

interface ShimmerButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  shimmerColor?: string
  shimmerSize?: string
  shimmerDuration?: string
  background?: string
}

export function ShimmerButton({
  children,
  className,
  shimmerColor = "rgba(255,255,255,0.1)",
  shimmerSize = "200px",
  shimmerDuration = "2s",
  background = "linear-gradient(110deg, #1a2230 30%, #222d3d 50%, #1a2230 70%)",
  ...props
}: ShimmerButtonProps) {
  return (
    <button
      className={cn(
        "relative overflow-hidden rounded-lg border border-border px-6 py-3 font-medium text-text transition-all hover:border-accent/30 hover:shadow-lg hover:shadow-accent/5",
        className
      )}
      style={{ background }}
      {...props}
    >
      <div
        className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite]"
        style={{
          background: `linear-gradient(90deg, transparent, ${shimmerColor}, transparent)`,
          width: shimmerSize,
        }}
      />
      <span className="relative z-10">{children}</span>
    </button>
  )
}
