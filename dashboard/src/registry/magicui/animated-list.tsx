import type { ReactNode } from "react"

interface AnimatedListProps {
  children: ReactNode
  className?: string
}

export function AnimatedList({ children, className }: AnimatedListProps) {
  return <div className={className}>{children}</div>
}
