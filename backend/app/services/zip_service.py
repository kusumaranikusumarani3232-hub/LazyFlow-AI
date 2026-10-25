import io
import json
import os
import re
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
        zip_filename = self.determine_zip_filename(active_items)
        return zip_buffer, zip_filename

    def determine_zip_filename(self, items: List[FileOrganizedItem]) -> str:
        """
        Generate the ZIP filename dynamically from the actual files selected for export
        and their final destination folders:
        - Career files only -> Career_Files.zip
        - Study files only -> Study_Files.zip
        - Finance files only -> Finance_Files.zip
        - Images only -> Photos_and_Images.zip
        - Career and Study files -> Career_and_Study_Files.zip
        - Several categories -> combine the main category names when practical (e.g. Career_and_Finance_Files.zip);
          if there are too many categories, use Organized_Mixed_Files.zip.
        Exclude unchecked/excluded files from the ZIP and from filename generation.
        Sanitizes the filename to prevent invalid filesystem characters.
        """
        active_items = [i for i in items if not i.excluded]
        if not active_items:
            return "Organized_Mixed_Files.zip"

        folder_counts: Dict[str, int] = {}
        for item in active_items:
            raw_folder = (item.folder or "").strip()
            if raw_folder:
                folder_counts[raw_folder] = folder_counts.get(raw_folder, 0) + 1

        if not folder_counts:
            return "Organized_Mixed_Files.zip"

        def _clean_category(name: str) -> str:
            clean = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', name).strip()
            clean = re.sub(r'[\s\-]+', '_', clean).strip('_')
            clean = re.sub(r'_files$', '', clean, flags=re.IGNORECASE)
            return clean

        folders_list = list(folder_counts.keys())

        # Canonical category order for consistent naming
        canonical_order = {
            "career": 1,
            "study": 2,
            "finance": 3,
            "work": 4,
            "images": 5,
            "code": 6,
            "documents": 7,
            "other": 99
        }

        # 1. Single category
        if len(folders_list) == 1:
            raw_folder = folders_list[0]
            clean_name = _clean_category(raw_folder)
            if not clean_name or clean_name.lower() in ("other", "miscellaneous", "default", "files"):
                return "Organized_Files.zip"
            if clean_name.lower() in ("images", "photos", "pictures"):
                return "Photos_and_Images.zip"
            return f"{clean_name}_Files.zip"

        # Sort categories by count (descending), then by canonical priority
        sorted_folders = sorted(
            folders_list,
            key=lambda f: (-folder_counts[f], canonical_order.get(f.lower(), 50), f.lower())
        )

        # 2. Exactly two categories
        if len(sorted_folders) == 2:
            # Sort the 2 categories by canonical order if counts are equal
            if folder_counts[sorted_folders[0]] == folder_counts[sorted_folders[1]]:
                sorted_folders = sorted(
                    sorted_folders,
                    key=lambda f: (canonical_order.get(f.lower(), 50), f.lower())
                )

            cat1 = _clean_category(sorted_folders[0])
            cat2 = _clean_category(sorted_folders[1])

            # If both are generic/other
            if cat1.lower() in ("other", "files") and cat2.lower() in ("other", "files"):
                return "Organized_Mixed_Files.zip"
            if cat1.lower() in ("other", "files"):
                return "Photos_and_Images.zip" if cat2.lower() in ("images", "photos") else f"{cat2}_Files.zip"
            if cat2.lower() in ("other", "files"):
                return "Photos_and_Images.zip" if cat1.lower() in ("images", "photos") else f"{cat1}_Files.zip"

            # Combine: e.g. Career_and_Study_Files.zip, Career_and_Finance_Files.zip
            return f"{cat1}_and_{cat2}_Files.zip"

        # 3. Three categories - combine if practical, otherwise Organized_Mixed_Files.zip
        if len(sorted_folders) == 3:
            # If 3rd category is small/insignificant Other, combine top 2
            top2_count = folder_counts[sorted_folders[0]] + folder_counts[sorted_folders[1]]
            if sorted_folders[2].lower() in ("other", "documents") and top2_count >= 2:
                cat1 = _clean_category(sorted_folders[0])
                cat2 = _clean_category(sorted_folders[1])
                return f"{cat1}_and_{cat2}_Files.zip"

            cat1 = _clean_category(sorted_folders[0])
            cat2 = _clean_category(sorted_folders[1])
            cat3 = _clean_category(sorted_folders[2])
            combined = f"{cat1}_{cat2}_and_{cat3}_Files.zip"
            if len(combined) <= 45 and not any(c.lower() in ("other", "files") for c in (cat1, cat2, cat3)):
                return combined
            return "Organized_Mixed_Files.zip"

        # 4. Too many categories (> 3 categories)
        return "Organized_Mixed_Files.zip"

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
