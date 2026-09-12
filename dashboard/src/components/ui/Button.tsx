import { type ButtonHTMLAttributes, forwardRef } from "react"
import { cn } from "@/lib/utils"

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger"
  fullWidth?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", fullWidth, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
          "disabled:pointer-events-none disabled:opacity-50",
          {
            "bg-accent text-bg hover:bg-accent-hover": variant === "primary",
            "bg-surface-2 text-text border border-border hover:bg-surface-3": variant === "secondary",
            "text-text-secondary hover:text-text hover:bg-surface-2": variant === "ghost",
            "bg-severity-critical text-white hover:bg-red-600": variant === "danger",
          },
          fullWidth && "w-full",
          className,
        )}
        {...props}
      >
        {children}
      </button>
    )
  }
)
