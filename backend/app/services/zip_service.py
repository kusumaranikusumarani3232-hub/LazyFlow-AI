import io
import json
import os
import shutil
import time
import zipfile
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from fastapi import HTTPException, UploadFile

from app.config import settings
from app.models.schemas import FileOrganizedItem
from app.utils.sanitizer import sanitize_filename, sanitize_folder_name, resolve_duplicate_names

logger = logging.getLogger("lazyflow.zip")

class ZipService:
    def __init__(self):
        self.temp_root = Path(settings.TEMP_DIR)
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def get_session_dir(self, session_id: str) -> Path:
        """Sanitize session_id to prevent directory traversal and get path."""
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
        if not safe_id:
            raise HTTPException(status_code=400, detail="Invalid session identifier.")
        session_dir = self.temp_root / safe_id
        return session_dir

    def _get_manifest_path(self, session_dir: Path) -> Path:
        return session_dir / "manifest.json"

    def _load_manifest(self, session_dir: Path) -> Dict[str, Any]:
        manifest_file = self._get_manifest_path(session_dir)
        if not manifest_file.exists():
            return {}
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading manifest: {e}")
            return {}

    def _save_manifest(self, session_dir: Path, manifest: Dict[str, Any]):
        manifest_file = self._get_manifest_path(session_dir)
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    async def save_uploaded_files(self, session_id: str, files: List[UploadFile]) -> List[Dict[str, Any]]:
        """
        Securely retain the actual uploaded bytes in temporary session storage.
        Computes SHA-256 hash for integrity tracking and persists a session manifest.
        """
        session_dir = self.get_session_dir(session_id)
        raw_dir = session_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        saved_metadata: List[Dict[str, Any]] = []
        manifest: Dict[str, Any] = {}
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024

        for idx, file in enumerate(files):
            file_id = f"f_{idx+1}"
            raw_filename = file.filename or f"upload_{idx+1}"
            safe_orig_name = sanitize_filename(raw_filename)
            stored_filename = f"{file_id}_{safe_orig_name}"
            target_path = raw_dir / stored_filename

            sha256_hasher = hashlib.sha256()
            size = 0

            # Stream chunks directly from upload to disk to maintain byte-for-byte fidelity
            with open(target_path, "wb") as buffer:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        self.cleanup_session(session_id)
                        raise HTTPException(
                            status_code=413,
                            detail=f"File '{raw_filename}' exceeds the maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB."
                        )
                    sha256_hasher.update(chunk)
                    buffer.write(chunk)

            file_hash = sha256_hasher.hexdigest()

            entry = {
                "id": file_id,
                "filename": raw_filename,
                "stored_filename": stored_filename,
                "stored_path": str(target_path.resolve()),
                "size": size,
                "sha256": file_hash,
                "mime_type": file.content_type or "application/octet-stream",
            }

            saved_metadata.append(entry)
            manifest[file_id] = entry

        # Save manifest
        self._save_manifest(session_dir, manifest)
        return saved_metadata

    def save_bytes_direct(self, session_id: str, file_id: str, filename: str, data: bytes, mime_type: str = "application/octet-stream") -> Dict[str, Any]:
        """Directly save bytes into session storage (useful for fixtures, tests, and programmatic uploads)."""
        session_dir = self.get_session_dir(session_id)
        raw_dir = session_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        safe_orig_name = sanitize_filename(filename)
        stored_filename = f"{file_id}_{safe_orig_name}"
        target_path = raw_dir / stored_filename

        with open(target_path, "wb") as f:
            f.write(data)

        file_hash = hashlib.sha256(data).hexdigest()
        manifest = self._load_manifest(session_dir)

        entry = {
            "id": file_id,
            "filename": filename,
            "stored_filename": stored_filename,
            "stored_path": str(target_path.resolve()),
            "size": len(data),
            "sha256": file_hash,
            "mime_type": mime_type,
        }
        manifest[file_id] = entry
        self._save_manifest(session_dir, manifest)
        return entry

    def build_organized_zip(self, session_id: str, items: List[FileOrganizedItem]) -> Tuple[io.BytesIO, str]:
        """
        Builds the organized ZIP archive.
        Ensures each entry contains the exact original uploaded file bytes,
        verifies bytes exist on disk before writing, and rejects missing files.
        """
        session_dir = self.get_session_dir(session_id)
        raw_dir = session_dir / "raw"

        if not session_dir.exists() or not raw_dir.exists():
            raise HTTPException(
                status_code=404,
                detail="Session expired or not found in temporary storage. Please re-upload files."
            )

        manifest = self._load_manifest(session_dir)

        # Filter out excluded items
        active_items = [item for item in items if not item.excluded]
        if not active_items:
            raise HTTPException(status_code=400, detail="All files have been excluded. Nothing to download.")

        # Convert to dict for duplicate-name resolution
        dict_items = [
            {
                "id": item.id,
                "original_filename": item.original_filename,
                "folder": sanitize_folder_name(item.folder),
                "suggested_filename": sanitize_filename(item.suggested_filename, original_name=item.original_filename)
            }
            for item in active_items
        ]

        resolved_items = resolve_duplicate_names(dict_items)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in resolved_items:
                file_id = item["id"]
                folder = item["folder"]
                final_name = item["suggested_filename"]
                orig_name = item["original_filename"]

                # 1. Resolve source file from manifest or fallback
                source_file: Optional[Path] = None

                if file_id in manifest:
                    cand_path = Path(manifest[file_id]["stored_path"])
                    if cand_path.exists():
                        source_file = cand_path

                # Fallback: lookup by original filename if ID differs
                if not source_file:
                    for m_id, m_entry in manifest.items():
                        if m_entry.get("filename") == orig_name:
                            cand_path = Path(m_entry["stored_path"])
                            if cand_path.exists():
                                source_file = cand_path
                                break

                # Fallback 2: glob by ID prefix in raw directory
                if not source_file:
                    matching_files = list(raw_dir.glob(f"{file_id}_*"))
                    if matching_files and matching_files[0].exists():
                        source_file = matching_files[0]

                # Fallback 3: check if ID was numeric without prefix or with f_ prefix
                if not source_file:
                    alt_id = f"f_{file_id}" if not file_id.startswith("f_") else file_id.replace("f_", "")
                    alt_matches = list(raw_dir.glob(f"{alt_id}_*"))
                    if alt_matches and alt_matches[0].exists():
                        source_file = alt_matches[0]

                # Strict Verification: File MUST exist on disk
                if not source_file or not source_file.is_file():
                    raise HTTPException(
                        status_code=400,
                        detail=f"Original uploaded file for '{orig_name}' (ID: {file_id}) could not be found in session storage. Aborting ZIP generation to prevent corrupted archives."
                    )

                # Check file size matches expectations
                file_size = source_file.stat().st_size
                manifest_expected = manifest.get(file_id, {}).get("size")
                if manifest_expected is not None and manifest_expected > 0 and file_size == 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Original file '{orig_name}' on disk is empty (0 bytes). Expected {manifest_expected} bytes."
                    )

                # Safe arcname inside ZIP: "Folder/filename.ext"
                # Strip leading slashes to prevent root-level or traversal ZIP attacks
                safe_folder = sanitize_folder_name(folder)
                safe_name = sanitize_filename(final_name, original_name=orig_name)
                arcname = f"{safe_folder}/{safe_name}".lstrip("/")

                # Write exact original bytes into ZIP entry
                zf.write(source_file, arcname=arcname)

        zip_buffer.seek(0)
        zip_filename = f"lazyflow_organized_{int(time.time())}.zip"
        return zip_buffer, zip_filename

    def cleanup_session(self, session_id: str):
        try:
            session_dir = self.get_session_dir(session_id)
            if session_dir.exists():
                shutil.rmtree(session_dir, ignore_errors=True)
                logger.info(f"Cleaned up session {session_id}")
        except Exception as e:
            logger.warning(f"Error during session cleanup: {e}")

    def cleanup_stale_sessions(self, max_age_seconds: int = 3600):
        now = time.time()
        if not self.temp_root.exists():
            return
        for session_dir in self.temp_root.iterdir():
            if session_dir.is_dir():
                try:
                    mtime = session_dir.stat().st_mtime
                    if now - mtime > max_age_seconds:
                        shutil.rmtree(session_dir, ignore_errors=True)
                except Exception:
                    pass

zip_service = ZipService()
