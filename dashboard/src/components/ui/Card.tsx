import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

interface CardProps {
  title?: string
  eyebrow?: string
  footer?: ReactNode
  className?: string
  children?: ReactNode
}

export function Card({ title, eyebrow, footer, className, children }: CardProps) {
  return (
    <div className={cn("rounded-xl border border-border bg-surface p-4 shadow-card", className)}>
      {eyebrow && (
        <p className="mb-1 text-xs font-medium uppercase tracking-wider text-text-muted">{eyebrow}</p>
      )}
      {title && (
        <h3 className="mb-3 text-base font-semibold text-text">{title}</h3>
      )}
      <div className="text-sm text-text-secondary">{children}</div>
      {footer && (
        <div className="mt-4 border-t border-border pt-3">{footer}</div>
      )}
    </div>
  )
}
