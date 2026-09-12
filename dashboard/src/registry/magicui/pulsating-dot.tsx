"use client"

import { cn } from "@/lib/utils"

interface PulsatingDotProps {
  className?: string
  color?: string
  size?: number
}

export function PulsatingDot({ className, color = "#22c55e", size = 8 }: PulsatingDotProps) {
  return (
    <span className={cn("relative inline-flex", className)}>
      <span
        className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75"
        style={{ backgroundColor: color }}
      />
      <span
        className="relative inline-flex rounded-full"
        style={{ width: size, height: size, backgroundColor: color }}
      />
    </span>
  )
}
