import { useRef, useEffect } from "react";
import type { FootprintChain } from "../types/api";
import { GitBranch } from "lucide-react";

export function TrajectoryMap({ chain }: { chain: FootprintChain }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, rect.width, rect.height);

    const cams = chain.entries.map((e, i) => ({
      x: 40 + (i * (rect.width - 80)) / Math.max(chain.entries.length - 1, 1),
      y: rect.height / 2,
      label: e.camera_id,
    }));

    if (cams.length > 1) {
      const grad = ctx.createLinearGradient(cams[0].x, 0, cams[cams.length - 1].x, 0);
      grad.addColorStop(0, "#52525b");
      grad.addColorStop(0.5, "#818cf8");
      grad.addColorStop(1, "#4ade80");
      ctx.strokeStyle = grad;
      ctx.lineWidth = 1.5;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(cams[0].x, cams[0].y);
      for (let i = 1; i < cams.length; i++) {
        ctx.lineTo(cams[i].x, cams[i].y);
      }
      ctx.stroke();
    }

    cams.forEach((c, i) => {
      const isLast = i === cams.length - 1;

      if (isLast) {
        ctx.fillStyle = "#4ade8015";
        ctx.beginPath();
        ctx.arc(c.x, c.y, 14, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.fillStyle = isLast ? "#4ade80" : "#52525b";
      ctx.beginPath();
      ctx.arc(c.x, c.y, isLast ? 6 : 4, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#52525b";
      ctx.font = "10px 'JetBrains Mono', monospace";
      ctx.textAlign = "center";
      ctx.fillText(c.label, c.x, c.y + 20);
    });
  }, [chain]);

  return (
    <div className="rounded-2xl border border-border-subtle bg-surface-1 p-5">
      <div className="flex items-center gap-2 mb-3">
        <GitBranch className="w-4 h-4 text-accent" strokeWidth={1.5} />
        <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-text-muted">
          Trajectory
        </span>
      </div>
      <canvas
        ref={canvasRef}
        className="w-full h-16 rounded-xl bg-surface-0 border border-border-subtle"
      />
    </div>
  );
}
