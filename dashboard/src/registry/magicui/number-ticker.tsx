import { cn } from "@/lib/utils";

interface NumberTickerProps {
  value: number;
  className?: string;
  duration?: number;
}

export function NumberTicker({ value, className }: NumberTickerProps) {
  return (
    <span className={cn("tabular-nums", className)}>
      {value}
    </span>
  );
}
