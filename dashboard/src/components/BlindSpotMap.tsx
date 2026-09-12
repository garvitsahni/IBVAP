import { useState, useEffect, useRef } from "react";
import { api } from "../services/api";
import type { BlindSpotResult } from "../types/api";

export function BlindSpotMap() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [data, setData] = useState<Record<string, BlindSpotResult>>({});

  useEffect(() => { api.getBlindSpots().then(setData).catch(() => {}); }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    for (const [camId, result] of Object.entries(data)) {
      ctx.fillStyle = "rgba(22, 163, 74, 0.1)";
      ctx.strokeStyle = "rgba(22, 163, 74, 0.5)";
      ctx.lineWidth = 2;
      drawPoly(ctx, result.fov_polygon, w, h);
      ctx.fill();
      ctx.stroke();

      for (const blind of result.blind_spots) {
        ctx.fillStyle = "rgba(220, 38, 38, 0.15)";
        ctx.strokeStyle = "rgba(220, 38, 38, 0.7)";
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        drawPoly(ctx, blind, w, h);
        ctx.fill();
        ctx.stroke();
        ctx.setLineDash([]);
      }

      const fov = result.fov_polygon;
      if (fov.length > 0) {
        ctx.fillStyle = "rgba(255,255,255,0.6)";
        ctx.font = "12px monospace";
        ctx.fillText(camId, fov[0][0] * w + 4, fov[0][1] * h + 14);
      }
    }
  }, [data]);

  return (
    <div className="p-3 bg-neutral-800 rounded">
      <h3 className="text-xs font-bold uppercase mb-2">Blind-Spot Map</h3>
      <canvas ref={canvasRef} width={400} height={300} className="w-full bg-neutral-900 rounded" />
      <div className="flex gap-4 mt-2 text-xs text-neutral-400">
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-system-ok/30 rounded"></span> Covered</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-alert-critical/30 rounded border border-alert-critical/70"></span> Blind Spot</span>
      </div>
    </div>
  );
}

function drawPoly(ctx: CanvasRenderingContext2D, poly: number[][], w: number, h: number) {
  if (poly.length < 2) return;
  ctx.beginPath();
  ctx.moveTo(poly[0][0] * w, poly[0][1] * h);
  for (let i = 1; i < poly.length; i++) {
    ctx.lineTo(poly[i][0] * w, poly[i][1] * h);
  }
  ctx.closePath();
}
