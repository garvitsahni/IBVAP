import { useState, useEffect } from "react";
import { api, type CameraCreate } from "../services/api";
import { type Camera } from "../types/api";
import { X, Plus, Trash2, Pencil, Save, Monitor, Cctv, Radio } from "lucide-react";

interface CameraManagerProps {
  open: boolean;
  onClose: () => void;
}

const SOURCE_TYPES = ["rtsp", "usb", "webcam", "hls", "unknown"] as const;

export function CameraManager({ open, onClose }: CameraManagerProps) {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [editing, setEditing] = useState<Camera | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [formCameraId, setFormCameraId] = useState("");
  const [formName, setFormName] = useState("");
  const [formSourceType, setFormSourceType] = useState<string>("unknown");
  const [formRtspUrl, setFormRtspUrl] = useState("");
  const [formLocation, setFormLocation] = useState("");
  const [formZone, setFormZone] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      setCameras(await api.getCameras());
    } catch {
      setError("Failed to load cameras");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      load();
      setEditing(null);
      setShowForm(false);
      setError(null);
    }
  }, [open]);

  const resetForm = () => {
    setFormCameraId("");
    setFormName("");
    setFormSourceType("unknown");
    setFormRtspUrl("");
    setFormLocation("");
    setFormZone("");
    setEditing(null);
    setShowForm(false);
  };

  const startEdit = (cam: Camera) => {
    setEditing(cam);
    setFormCameraId(cam.camera_id);
    setFormName(cam.name);
    setFormSourceType(cam.source_type);
    setFormRtspUrl(cam.rtsp_url || "");
    setFormLocation(cam.location || "");
    setFormZone(cam.zone || "");
    setShowForm(true);
  };

  const startAdd = () => {
    resetForm();
    setShowForm(true);
  };

  const handleSubmit = async () => {
    if (!formCameraId.trim() || !formName.trim()) {
      setError("Camera ID and Name are required");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      if (editing) {
        await api.updateCamera(editing.camera_id, {
          name: formName,
          source_type: formSourceType,
          rtsp_url: formRtspUrl || undefined,
          location: formLocation || undefined,
          zone: formZone || undefined,
        });
      } else {
        const payload: CameraCreate = {
          camera_id: formCameraId,
          name: formName,
          source_type: formSourceType,
          rtsp_url: formRtspUrl || undefined,
          location: formLocation || undefined,
          zone: formZone || undefined,
        };
        await api.createCamera(payload);
      }
      await load();
      resetForm();
    } catch (e: any) {
      setError(e.message || "Failed to save camera");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (cameraId: string) => {
    if (!confirm(`Delete camera "${cameraId}"?`)) return;
    setLoading(true);
    try {
      await api.deleteCamera(cameraId);
      await load();
    } catch (e: any) {
      setError(e.message || "Failed to delete camera");
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative w-full max-w-2xl mx-4 rounded-2xl border border-border-strong bg-surface-1 shadow-2xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-subtle">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-accent/[0.06] border border-accent/10">
              <Cctv className="w-4 h-4 text-accent" strokeWidth={1.5} />
            </div>
            <div>
              <h3 className="text-[15px] font-semibold text-text-primary tracking-tight">Manage Cameras</h3>
              <p className="text-[11px] text-text-muted mt-0.5">{cameras.length} registered</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-surface-2 text-text-muted hover:text-text-primary transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {error && (
            <div className="px-4 py-2.5 rounded-xl bg-severity-critical/[0.08] border border-severity-critical/15 text-severity-critical text-[12px]">
              {error}
            </div>
          )}

          {/* Camera List */}
          <div className="space-y-2">
            {cameras.length === 0 && !loading && (
              <div className="flex flex-col items-center py-12 text-text-muted">
                <Cctv className="w-8 h-8 mb-3 opacity-20" strokeWidth={1.5} />
                <p className="text-[13px] font-medium">No cameras registered</p>
                <p className="text-[11px] mt-1">Add a camera to get started</p>
              </div>
            )}

            {cameras.map((cam) => (
              <div
                key={cam.camera_id}
                className="flex items-center justify-between p-3.5 rounded-xl border border-border-subtle bg-surface-0 hover:border-border-strong transition-colors group"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-2 rounded-lg bg-surface-2 border border-border-subtle shrink-0">
                    {cam.source_type === "webcam" || cam.source_type === "usb" ? (
                      <Monitor className="w-3.5 h-3.5 text-accent" strokeWidth={1.5} />
                    ) : (
                      <Radio className="w-3.5 h-3.5 text-accent" strokeWidth={1.5} />
                    )}
                  </div>
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium text-text-primary truncate">{cam.name}</p>
                    <p className="text-[10px] text-text-muted font-mono">{cam.camera_id} &middot; {cam.source_type}</p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <div className={`px-2 py-0.5 rounded-md text-[9px] font-semibold uppercase tracking-wider ${
                    cam.status === "ok" || cam.status === "online"
                      ? "bg-status-ok/[0.08] text-status-ok"
                      : "bg-severity-critical/[0.08] text-severity-critical"
                  }`}>
                    {cam.status}
                  </div>
                  <button
                    onClick={() => startEdit(cam)}
                    className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-surface-2 text-text-muted hover:text-text-primary transition-all"
                  >
                    <Pencil className="w-3.5 h-3.5" strokeWidth={1.5} />
                  </button>
                  <button
                    onClick={() => handleDelete(cam.camera_id)}
                    className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-severity-critical/10 text-text-muted hover:text-severity-critical transition-all"
                  >
                    <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Add / Edit Form */}
          {showForm && (
            <div className="rounded-xl border border-accent/20 bg-accent/[0.03] p-5 space-y-4">
              <p className="text-[13px] font-semibold text-text-primary">
                {editing ? `Edit ${editing.camera_id}` : "Register New Camera"}
              </p>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-medium text-text-muted uppercase tracking-wider mb-1 block">Camera ID</label>
                  <input
                    value={formCameraId}
                    onChange={(e) => setFormCameraId(e.target.value)}
                    disabled={!!editing}
                    placeholder="e.g. front-gate-01"
                    className="w-full px-3 py-2 rounded-lg border border-border-subtle bg-surface-0 text-text-primary text-[13px] placeholder:text-text-muted/40 disabled:opacity-50 focus:outline-none focus:border-accent/40"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-medium text-text-muted uppercase tracking-wider mb-1 block">Name</label>
                  <input
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder="e.g. Front Gate Camera"
                    className="w-full px-3 py-2 rounded-lg border border-border-subtle bg-surface-0 text-text-primary text-[13px] placeholder:text-text-muted/40 focus:outline-none focus:border-accent/40"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-medium text-text-muted uppercase tracking-wider mb-1 block">Source Type</label>
                  <select
                    value={formSourceType}
                    onChange={(e) => setFormSourceType(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-border-subtle bg-surface-0 text-text-primary text-[13px] focus:outline-none focus:border-accent/40"
                  >
                    {SOURCE_TYPES.map((st) => (
                      <option key={st} value={st}>{st}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] font-medium text-text-muted uppercase tracking-wider mb-1 block">RTSP URL</label>
                  <input
                    value={formRtspUrl}
                    onChange={(e) => setFormRtspUrl(e.target.value)}
                    placeholder="rtsp://..."
                    className="w-full px-3 py-2 rounded-lg border border-border-subtle bg-surface-0 text-text-primary text-[13px] placeholder:text-text-muted/40 focus:outline-none focus:border-accent/40"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-medium text-text-muted uppercase tracking-wider mb-1 block">Location</label>
                  <input
                    value={formLocation}
                    onChange={(e) => setFormLocation(e.target.value)}
                    placeholder="e.g. Building A, Entrance"
                    className="w-full px-3 py-2 rounded-lg border border-border-subtle bg-surface-0 text-text-primary text-[13px] placeholder:text-text-muted/40 focus:outline-none focus:border-accent/40"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-medium text-text-muted uppercase tracking-wider mb-1 block">Zone</label>
                  <input
                    value={formZone}
                    onChange={(e) => setFormZone(e.target.value)}
                    placeholder="perimeter / entry / interior"
                    className="w-full px-3 py-2 rounded-lg border border-border-subtle bg-surface-0 text-text-primary text-[13px] placeholder:text-text-muted/40 focus:outline-none focus:border-accent/40"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2">
                <button
                  onClick={resetForm}
                  className="px-4 py-2 rounded-lg border border-border-subtle text-[12px] font-medium text-text-muted hover:text-text-primary hover:border-border-strong transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={loading}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-black text-[12px] font-semibold hover:brightness-110 transition-all disabled:opacity-40"
                >
                  <Save className="w-3.5 h-3.5" strokeWidth={2} />
                  {editing ? "Save Changes" : "Register Camera"}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {!showForm && (
          <div className="px-6 py-4 border-t border-border-subtle flex justify-end">
            <button
              onClick={startAdd}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-accent text-black text-[12px] font-semibold hover:brightness-110 transition-all"
            >
              <Plus className="w-3.5 h-3.5" strokeWidth={2} />
              Add Camera
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
