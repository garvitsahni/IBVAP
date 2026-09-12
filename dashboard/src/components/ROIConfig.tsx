import { useState, useRef, useEffect } from "react";
import type { Camera } from "../types/api";

export function ROIConfig({ cameras }: { cameras: Camera[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [points, setPoints] = useState<number[][]>([]);
  const [selectedCam, setSelectedCam] = useState(cameras[0]?.camera_id || "cam1");

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / canvas.width;
    const y = (e.clientY - rect.top) / canvas.height;
    setPoints((prev) => [...prev, [x, y]]);
  };

  const handleDoubleClick = () => {
    if (points.length >= 3) {
      setPoints([]);
    }
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (points.length > 0) {
      ctx.strokeStyle = "#dc2626";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(points[0][0] * canvas.width, points[0][1] * canvas.height);
      for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i][0] * canvas.width, points[i][1] * canvas.height);
      }
      ctx.stroke();
      points.forEach(([x, y]) => {
        ctx.fillStyle = "#dc2626";
        ctx.beginPath();
        ctx.arc(x * canvas.width, y * canvas.height, 4, 0, Math.PI * 2);
        ctx.fill();
      });
    }
  }, [points]);

  return (
    <div className="p-3 bg-neutral-800 rounded">
      <h3 className="text-xs font-bold uppercase mb-2">ROI Configuration</h3>
      <div className="mb-2">
        <select value={selectedCam} onChange={(e) => setSelectedCam(e.target.value)} className="bg-neutral-700 text-sm px-2 py-1 rounded">
          {cameras.map((c) => <option key={c.camera_id} value={c.camera_id}>{c.name || c.camera_id}</option>)}
        </select>
      </div>
      <canvas
        ref={canvasRef}
        width={400}
        height={300}
        className="w-full bg-neutral-900 rounded cursor-crosshair"
        onClick={handleCanvasClick}
        onDoubleClick={handleDoubleClick}
      />
      <div className="flex gap-2 mt-2">
        <button onClick={() => setPoints([])} className="text-xs bg-neutral-700 px-2 py-1 rounded">Clear</button>
        <button disabled={points.length < 3} className="text-xs bg-alert-standard px-2 py-1 rounded disabled:opacity-40">Save ROI</button>
      </div>
      <p className="text-xs text-neutral-500 mt-1">Click to add vertices, double-click to close polygon</p>
    </div>
  );
}
