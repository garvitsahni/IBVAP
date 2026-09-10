"""
Clip Storage - Local filesystem / MinIO for event-triggered clips
Per ARCHITECTURE.md: only short event-triggered clips cross boundaries, never raw video
"""
import os
import shutil
from pathlib import Path
from typing import Optional, BinaryIO
from dataclasses import dataclass
from minio import Minio
from minio.error import S3Error


@dataclass
class ClipInfo:
    """Metadata for stored clip."""
    path: str
    size_bytes: int
    duration_seconds: float
    camera_id: str
    timestamp: str
    object_id: str


class ClipStore:
    """
    Unified clip storage interface.
    Supports local filesystem (dev) and MinIO (production).
    """

    def __init__(
        self,
        use_minio: bool = False,
        local_path: str = "./clips",
        minio_endpoint: str = "localhost:9000",
        minio_access_key: str = "minioadmin",
        minio_secret_key: str = "minioadmin",
        minio_bucket: str = "ibvap-clips",
        minio_secure: bool = False,
    ):
        self.use_minio = use_minio
        self.local_path = Path(local_path)
        self.minio_bucket = minio_bucket

        if use_minio:
            self.minio_client = Minio(
                minio_endpoint,
                access_key=minio_access_key,
                secret_key=minio_secret_key,
                secure=minio_secure,
            )
            self._ensure_bucket()
        else:
            self.local_path.mkdir(parents=True, exist_ok=True)

    def _ensure_bucket(self):
        """Ensure MinIO bucket exists."""
        try:
            if not self.minio_client.bucket_exists(self.minio_bucket):
                self.minio_client.make_bucket(self.minio_bucket)
        except S3Error as e:
            print(f"MinIO bucket error: {e}")

    def save_clip(
        self,
        camera_id: str,
        object_id: str,
        timestamp: str,
        clip_data: bytes,
    ) -> ClipInfo:
        """Save clip and return metadata."""
        filename = f"{camera_id}_{object_id}_{timestamp}.mp4"
        timestamp_clean = timestamp.replace(":", "-").replace(".", "-")

        if self.use_minio:
            object_name = f"{camera_id}/{object_id}/{filename}"
            self.minio_client.put_object(
                self.minio_bucket,
                object_name,
                io.BytesIO(clip_data),
                length=len(clip_data),
                content_type="video/mp4",
            )
            path = f"s3://{self.minio_bucket}/{object_name}"
        else:
            # Local filesystem: organize by camera/date
            date_str = timestamp.split("T")[0] if "T" in timestamp else timestamp[:10]
            save_dir = self.local_path / camera_id / date_str
            save_dir.mkdir(parents=True, exist_ok=True)
            file_path = save_dir / filename
            file_path.write_bytes(clip_data)
            path = str(file_path)

        return ClipInfo(
            path=path,
            size_bytes=len(clip_data),
            duration_seconds=0.0,  # Would need ffprobe to get actual duration
            camera_id=camera_id,
            timestamp=timestamp,
            object_id=object_id,
        )

    def get_clip(self, clip_path: str) -> Optional[bytes]:
        """Retrieve clip data by path."""
        if self.use_minio and clip_path.startswith("s3://"):
            # Parse s3://bucket/object
            parts = clip_path[5:].split("/", 1)
            if len(parts) == 2:
                bucket, object_name = parts
                try:
                    response = self.minio_client.get_object(bucket, object_name)
                    return response.read()
                except S3Error:
                    return None
        else:
            # Local file
            try:
                return Path(clip_path).read_bytes()
            except FileNotFoundError:
                return None
        return None

    def delete_clip(self, clip_path: str) -> bool:
        """Delete clip by path."""
        if self.use_minio and clip_path.startswith("s3://"):
            parts = clip_path[5:].split("/", 1)
            if len(parts) == 2:
                bucket, object_name = parts
                try:
                    self.minio_client.remove_object(bucket, object_name)
                    return True
                except S3Error:
                    return False
        else:
            try:
                Path(clip_path).unlink(missing_ok=True)
                return True
            except Exception:
                return False

    def clip_exists(self, clip_path: str) -> bool:
        """Check if clip exists."""
        if self.use_minio and clip_path.startswith("s3://"):
            parts = clip_path[5:].split("/", 1)
            if len(parts) == 2:
                bucket, object_name = parts
                try:
                    self.minio_client.stat_object(bucket, object_name)
                    return True
                except S3Error:
                    return False
        else:
            return Path(clip_path).exists()


import io  # moved here to avoid circular import issue at module level