import { cn } from "@/lib/utils";

interface BorderBeamProps {
  className?: string;
  size?: number;
  duration?: number;
  anchor?: number;
  borderWidth?: number;
  colorFrom?: string;
  colorTo?: string;
  delay?: number;
}

export function BorderBeam({
  className,
  size = 200,
  duration = 6,
  delay = 0,
  borderWidth = 1.5,
  colorFrom = "transparent",
  colorTo = "transparent",
}: BorderBeamProps) {
  return (
    <div
      className={cn("pointer-events-none absolute inset-0 overflow-hidden rounded-[inherit]", className)}
      style={{ "--border-beam-size": size, "--border-beam-duration": `${duration}s`, "--border-beam-delay": `${delay}s` } as React.CSSProperties}
    >
      <div
        className="absolute aspect-square animate-[border-beam-angle_var(--border-beam-duration)_linear_infinite]"
        style={{
          width: size,
          height: size,
          offsetPath: `border-box`,
          offsetDistance: "0%",
          offsetRotate: "0deg",
          background: `linear-gradient(to right, ${colorFrom}, ${colorTo})`,
          filter: "blur(4px)",
        }}
      />
    </div>
  );
}
