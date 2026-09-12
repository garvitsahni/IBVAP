"use client"

import { cn } from "@/lib/utils"

interface DotPatternProps {
  className?: string
  dotColor?: string
}

export function DotPattern({ className, dotColor = "rgba(61,165,217,0.15)" }: DotPatternProps) {
  return (
    <div
      className={cn("pointer-events-none absolute inset-0", className)}
      style={{
        backgroundImage: `radial-gradient(${dotColor} 1px, transparent 1px)`,
        backgroundSize: "24px 24px",
      }}
    />
  )
}
