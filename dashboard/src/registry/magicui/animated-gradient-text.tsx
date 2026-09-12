"use client"

import { cn } from "@/lib/utils"
import { ReactNode } from "react"

interface AnimatedGradientTextProps {
  children: ReactNode
  className?: string
}

export function AnimatedGradientText({ children, className }: AnimatedGradientTextProps) {
  return (
    <span
      className={cn(
        "bg-gradient-to-r from-accent via-severity-critical to-accent bg-[length:200%_auto] bg-clip-text text-transparent animate-[gradient_3s_linear_infinite]",
        className
      )}
    >
      {children}
    </span>
  )
}
