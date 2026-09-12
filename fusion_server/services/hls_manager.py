"""HLS Manager — manages FFmpeg RTSP→HLS transcoding per camera."""
import os
import subprocess
import logging

logger = logging.getLogger(__name__)


class HLSManager:
    def __init__(self, hls_dir: str = "/tmp/ibvap_hls"):
        self.hls_dir = hls_dir
        self._processes: dict[str, subprocess.Popen] = {}
        self._running: dict[str, bool] = {}
        os.makedirs(hls_dir, exist_ok=True)

    def start(self, camera_id: str, rtsp_url: str) -> None:
        """Start FFmpeg transcoding for a camera."""
        if self.is_running(camera_id):
            return

        out_dir = os.path.join(self.hls_dir, camera_id)
        os.makedirs(out_dir, exist_ok=True)
        playlist = os.path.join(out_dir, "stream.m3u8")

        cmd = [
            "ffmpeg", "-y",
            "-i", rtsp_url,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-f", "hls",
            "-hls_time", "2",
            "-hls_list_size", "5",
            "-hls_flags", "delete_segments+append_list",
            playlist,
        ]

        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._processes[camera_id] = proc
            self._running[camera_id] = True
            logger.info("Started HLS for %s → %s", camera_id, rtsp_url)
        except FileNotFoundError:
            logger.warning("FFmpeg not found — HLS disabled for %s", camera_id)

    def stop(self, camera_id: str) -> None:
        """Stop FFmpeg transcoding for a camera."""
        proc = self._processes.pop(camera_id, None)
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        self._running.pop(camera_id, None)

    def stop_all(self) -> None:
        for cid in list(self._processes.keys()):
            self.stop(cid)

    def is_running(self, camera_id: str) -> bool:
        return self._running.get(camera_id, False)

    def get_playlist_path(self, camera_id: str) -> str | None:
        playlist = os.path.join(self.hls_dir, camera_id, "stream.m3u8")
        return playlist if os.path.isfile(playlist) else None
