import { useRef, useEffect } from "react";
import type { FootprintChain } from "../types/api";
import { GitBranch } from "lucide-react";
import { formatTime } from "../lib/time";

export function TrajectoryMap({ chain }: { chain: FootprintChain }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const draw = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, rect.width, rect.height);

      // subtle dot grid
      ctx.fillStyle = "#ffffff08";
      for (let x = 12; x < rect.width; x += 18) {
        for (let y = 12; y < rect.height; y += 18) {
          ctx.beginPath();
          ctx.arc(x, y, 0.7, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      const entries = chain.entries;
      if (entries.length === 0) {
        ctx.fillStyle = "#52525b";
        ctx.font = "11px ui-monospace, monospace";
        ctx.textAlign = "center";
        ctx.fillText("No hops recorded", rect.width / 2, rect.height / 2 + 4);
        return;
      }

      const midY = rect.height * 0.42;
      const padX = entries.length === 1 ? rect.width / 2 : 46;
      const nodes = entries.map((e, i) => ({
        x: entries.length === 1 ? rect.width / 2 : padX + (i * (rect.width - padX * 2)) / Math.max(entries.length - 1, 1),
        y: midY,
        label: e.camera_id,
        time: formatTime(e.timestamp),
        isLast: i === entries.length - 1,
      }));

      // path with arrows between hops
      if (nodes.length > 1) {
        const grad = ctx.createLinearGradient(nodes[0].x, 0, nodes[nodes.length - 1].x, 0);
        grad.addColorStop(0, "#52525b");
        grad.addColorStop(0.5, "#818cf8");
        grad.addColorStop(1, "#4ade80");
        ctx.strokeStyle = grad;
        ctx.lineWidth = 1.5;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(nodes[0].x, nodes[0].y);
        for (let i = 1; i < nodes.length; i++) ctx.lineTo(nodes[i].x, nodes[i].y);
        ctx.stroke();

        // arrowheads at segment midpoints
        ctx.fillStyle = "#818cf8";
        for (let i = 1; i < nodes.length; i++) {
          const mx = (nodes[i - 1].x + nodes[i].x) / 2;
          ctx.beginPath();
          ctx.moveTo(mx + 4, midY);
          ctx.lineTo(mx - 3, midY - 4);
          ctx.lineTo(mx - 3, midY + 4);
          ctx.closePath();
          ctx.fill();
        }
      }

      nodes.forEach((n) => {
        if (n.isLast) {
          ctx.fillStyle = "#4ade8018";
          ctx.beginPath();
          ctx.arc(n.x, n.y, 14, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.fillStyle = n.isLast ? "#4ade80" : "#818cf8";
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.isLast ? 6 : 4.5, 0, Math.PI * 2);
        ctx.fill();
        if (n.isLast) {
          ctx.strokeStyle = "#4ade8055";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(n.x, n.y, 10, 0, Math.PI * 2);
          ctx.stroke();
        }

        ctx.font = "600 10px ui-monospace, monospace";
        ctx.textAlign = "center";
        ctx.fillStyle = "#fafafa";
        ctx.fillText(n.label, n.x, n.y + 22);
        ctx.font = "9px ui-monospace, monospace";
        ctx.fillStyle = "#52525b";
        ctx.fillText(n.time, n.x, n.y + 34);
      });
    };

    draw();
    const onResize = () => draw();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [chain]);

  return (
    <div className="card rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <GitBranch className="w-4 h-4 text-accent" strokeWidth={1.5} />
        <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-text-muted">
          Trajectory
        </span>
        <span className="text-[10px] text-text-muted ml-auto font-mono">
          {chain.entries.length} hop{chain.entries.length !== 1 ? "s" : ""}
        </span>
      </div>
      <canvas
        ref={canvasRef}
        className="w-full h-24 rounded-xl bg-bg-primary border border-border-hairline"
      />
    </div>
  );
}
