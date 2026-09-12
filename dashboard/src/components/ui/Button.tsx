import { cn } from "@/lib/utils"
import { forwardRef } from "react"

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger"
  size?: "sm" | "md" | "lg"
}

const VARIANT_CLASSES = {
  primary: "bg-accent text-bg hover:bg-accent-hover",
  secondary: "border border-border bg-surface-2 text-text-secondary hover:bg-surface-3 hover:text-text",
  ghost: "text-text-secondary hover:bg-surface-2 hover:text-text",
  danger: "bg-severity-critical/10 text-severity-critical border border-severity-critical/20 hover:bg-severity-critical/20",
}

const SIZE_CLASSES = {
  sm: "h-7 px-2.5 text-xs",
  md: "h-8 px-3 text-sm",
  lg: "h-9 px-4 text-sm",
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none",
          VARIANT_CLASSES[variant],
          SIZE_CLASSES[size],
          className
        )}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button }
