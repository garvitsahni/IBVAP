"use client"

import { cn } from "@/lib/utils"

interface GlobeProps {
  className?: string
}

export function Globe({ className }: GlobeProps) {
  return (
    <div className={cn("relative h-[400px] w-[400px]", className)}>
      <div className="absolute inset-0 rounded-full border border-border/30" />
      <div className="absolute inset-4 rounded-full border border-border/20" />
      <div className="absolute inset-8 rounded-full border border-border/10" />
      <div className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-border/20" />
      <div className="absolute left-0 top-1/2 h-px w-full -translate-y-1/2 bg-border/20" />
      <div className="absolute left-1/2 top-1/2 h-[60%] w-[60%] -translate-x-1/2 -translate-y-1/2 rounded-full border border-accent/20" />
      <div className="absolute left-1/2 top-1/2 h-[30%] w-[30%] -translate-x-1/2 -translate-y-1/2 rounded-full border border-accent/10" />
      <div className="absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent shadow-[0_0_20px_rgba(61,165,217,0.5)]" />
      <div className="absolute inset-0 animate-[spin_30s_linear_infinite]">
        <div className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-gradient-to-b from-transparent via-accent/30 to-transparent" />
      </div>
      <div className="absolute inset-0 animate-[spin_20s_linear_infinite_reverse]">
        <div className="absolute left-0 top-1/2 h-px w-full -translate-y-1/2 bg-gradient-to-r from-transparent via-accent/20 to-transparent" />
      </div>
    </div>
  )
}
