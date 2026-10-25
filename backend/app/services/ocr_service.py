import io
import logging
import os
import re
import shutil
import time
import unicodedata
from pathlib import Path
from typing import Dict, Any, Optional, Union, List

from PIL import Image

from app.config import settings

logger = logging.getLogger("lazyflow.ocr")


class OCRService:
    """
    OCR service for LazyFlow AI.
    Provides fast, reliable, privacy-preserving OCR recognition for scanned PDFs
    and certificate images using Tesseract OCR.
    """

    def __init__(self):
        self._tesseract_cmd: Optional[str] = None
        self._is_available: Optional[bool] = None
        self._version: Optional[str] = None
        self._initialize_engine()

    def _initialize_engine(self) -> None:
        """Locate and configure the Tesseract executable."""
        candidates = []

        # 1. Explicit configuration or environment variable
        if settings.TESSERACT_CMD:
            candidates.append(Path(settings.TESSERACT_CMD))
        env_cmd = os.environ.get("TESSERACT_CMD")
        if env_cmd:
            candidates.append(Path(env_cmd))

        # 2. System PATH (standard for Linux/Render and configured Windows systems)
        which_path = shutil.which("tesseract")
        if which_path:
            candidates.append(Path(which_path))

        # 3. Known Windows installation directories
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidates.append(Path(local_app_data) / "Programs" / "Tesseract-OCR" / "tesseract.exe")

        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            candidates.append(Path(user_profile) / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe")

        candidates.extend([
            Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
            Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
            Path("/usr/bin/tesseract"),
            Path("/usr/local/bin/tesseract"),
        ])

        for path in candidates:
            try:
                if path and path.exists() and path.is_file():
                    self._tesseract_cmd = str(path.resolve())
                    break
            except Exception:
                continue

        # If which found it directly
        if not self._tesseract_cmd and which_path:
            self._tesseract_cmd = which_path

        # Verify pytesseract availability
        try:
            import pytesseract
            if self._tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = self._tesseract_cmd
            ver = pytesseract.get_tesseract_version()
            self._version = str(ver)
            self._is_available = True
            logger.info(
                f"[Diagnostic:OCR] Tesseract OCR engine initialized successfully: "
                f"version={self._version}, binary='{self._tesseract_cmd or 'in PATH'}'"
            )
        except Exception as e:
            self._is_available = False
            self._version = None
            logger.info(
                f"[Diagnostic:OCR] Tesseract OCR engine is not currently available: {type(e).__name__}: {e}"
            )

    def is_available(self) -> bool:
        """Check if OCR engine is installed, configured, and responsive."""
        if not settings.OCR_ENABLED:
            return False
        if self._is_available is None:
            self._initialize_engine()
        return bool(self._is_available)

    def get_engine_info(self) -> Dict[str, Any]:
        """Return engine metadata for diagnostics and health reporting."""
        return {
            "available": self.is_available(),
            "engine": "tesseract",
            "version": self._version,
            "binary_path": self._tesseract_cmd,
            "enabled": settings.OCR_ENABLED,
            "max_pages": settings.OCR_MAX_PAGES,
            "max_image_dimension": settings.OCR_MAX_IMAGE_DIMENSION,
            "timeout_seconds": settings.OCR_TIMEOUT_SECONDS,
        }

    def normalize_text(self, text: str) -> str:
        """
        Normalize OCR text by resolving ligatures, whitespace, hyphenation, and line breaks.
        Preserves Privacy: does not log text contents.
        """
        if not text:
            return ""

        # 1. Unicode decomposition to separate accents and normalize characters
        normalized = unicodedata.normalize("NFKD", text)

        # 2. Expand common typographical ligatures
        ligatures = {
            "\ufb00": "ff",
            "\ufb01": "fi",
            "\ufb02": "fl",
            "\ufb03": "ffi",
            "\ufb04": "ffl",
            "\ufb05": "ft",
            "\ufb06": "st",
            "\u0152": "OE",
            "\u0153": "oe",
            "\u00c6": "AE",
            "\u00e6": "ae",
            "\u019f": "ti",
        }
        for lig, rep in ligatures.items():
            normalized = normalized.replace(lig, rep)

        # 3. Rejoin hyphenated line breaks (e.g. "certifi-\ncate" -> "certificate")
        normalized = re.sub(r"([A-Za-z0-9])[-–—]\s*\n\s*([A-Za-z0-9])", r"\1\2", normalized)

        # 4. Remove non-printable control characters (keep \n and \t)
        normalized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", normalized)

        # 5. Clean up excessive spaces while preserving line breaks for layout structure
        lines = []
        for line in normalized.splitlines():
            cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
            if cleaned_line:
                lines.append(cleaned_line)

        # Recombine with single line breaks
        result = "\n".join(lines)
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()

    def ocr_image(
        self,
        image_input: Union[Path, str, bytes, Image.Image],
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run OCR directly on an image input (file path, bytes, or PIL Image).
        Enforces image dimension caps, format conversions, and timeouts.
        Safe diagnostics log only character count and latency, never document text.
        """
        if not self.is_available():
            return {
                "success": False,
                "text": "",
                "char_count": 0,
                "error": "OCR engine (tesseract) not available",
                "engine": "tesseract",
            }

        start_time = time.time()
        img: Optional[Image.Image] = None
        should_close = False

        try:
            import pytesseract

            # Load image
            if isinstance(image_input, Image.Image):
                img = image_input
            elif isinstance(image_input, bytes):
                img = Image.open(io.BytesIO(image_input))
                should_close = True
            elif isinstance(image_input, (Path, str)):
                img = Image.open(str(image_input))
                should_close = True
            else:
                return {
                    "success": False,
                    "text": "",
                    "char_count": 0,
                    "error": f"Unsupported image input type: {type(image_input)}",
                    "engine": "tesseract",
                }

            # Safety 1: Normalize color mode & transparency
            if img.mode in ("RGBA", "LA", "P"):
                # Composite over white background to avoid dark transparent backgrounds
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Safety 2: Cap maximum image dimensions to prevent resource abuse
            max_dim = settings.OCR_MAX_IMAGE_DIMENSION
            w, h = img.size
            if max(w, h) > max_dim:
                scale = max_dim / float(max(w, h))
                new_size = (int(w * scale), int(h * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # Run Tesseract with configured timeout
            raw_text = pytesseract.image_to_string(
                img,
                lang="eng",
                timeout=settings.OCR_TIMEOUT_SECONDS
            )

            clean_text = self.normalize_text(raw_text)
            elapsed_ms = int((time.time() - start_time) * 1000)

            # Safe diagnostic logging (No text logged!)
            logger.info(
                f"[Diagnostic:OCR] Image OCR completed for '{filename or 'image'}': "
                f"extracted_chars={len(clean_text)}, size={w}x{h}, latency={elapsed_ms}ms"
            )

            return {
                "success": bool(clean_text),
                "text": clean_text,
                "char_count": len(clean_text),
                "error": None,
                "engine": "tesseract",
            }

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            err_msg = f"{type(e).__name__}: {e}"
            logger.warning(
                f"[Diagnostic:OCR] Image OCR error for '{filename or 'image'}' after {elapsed_ms}ms: {err_msg}"
            )
            return {
                "success": False,
                "text": "",
                "char_count": 0,
                "error": err_msg,
                "engine": "tesseract",
            }
        finally:
            if should_close and img:
                try:
                    img.close()
                except Exception:
                    pass

    def ocr_pdf(
        self,
        pdf_path: Union[Path, str],
        filename: Optional[str] = None,
        max_pages: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Render pages of a PDF to images and run OCR.
        Caps page count, resolution, and time to prevent resource exhaustion.
        Safe diagnostics log only page count and character count, never document text.
        """
        if not self.is_available():
            return {
                "success": False,
                "text": "",
                "char_count": 0,
                "pages_scanned": 0,
                "error": "OCR engine (tesseract) not available",
                "engine": "tesseract",
            }

        path = Path(pdf_path)
        if not path.exists():
            return {
                "success": False,
                "text": "",
                "char_count": 0,
                "pages_scanned": 0,
                "error": "PDF file not found",
                "engine": "tesseract",
            }

        page_limit = max_pages or settings.OCR_MAX_PAGES
        start_time = time.time()
        scanned_pages = 0
        collected_texts: List[str] = []

        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(path))
            total_pages = len(doc)
            pages_to_process = min(page_limit, total_pages)

            # Use 2.0 zoom factor (approx 144-150 DPI) for fast, accurate text reading
            mat = fitz.Matrix(2.0, 2.0)

            for page_idx in range(pages_to_process):
                page = doc[page_idx]
                pix = page.get_pixmap(matrix=mat, alpha=False)
                page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                page_res = self.ocr_image(
                    image_input=page_img,
                    filename=f"{filename or path.name}_p{page_idx + 1}"
                )
                scanned_pages += 1
                if page_res.get("success") and page_res.get("text"):
                    collected_texts.append(page_res["text"])

            doc.close()

            combined_text = "\n\n".join(collected_texts).strip()
            elapsed_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"[Diagnostic:OCR] PDF OCR completed for '{filename or path.name}': "
                f"pages_scanned={scanned_pages}/{total_pages}, "
                f"extracted_chars={len(combined_text)}, latency={elapsed_ms}ms"
            )

            return {
                "success": bool(combined_text),
                "text": combined_text,
                "char_count": len(combined_text),
                "pages_scanned": scanned_pages,
                "total_pages": total_pages,
                "error": None,
                "engine": "tesseract",
            }

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            err_msg = f"{type(e).__name__}: {e}"
            logger.warning(
                f"[Diagnostic:OCR] PDF OCR failed for '{filename or path.name}' after {elapsed_ms}ms: {err_msg}"
            )
            return {
                "success": False,
                "text": "",
                "char_count": 0,
                "pages_scanned": scanned_pages,
                "error": err_msg,
                "engine": "tesseract",
            }


ocr_service = OCRService()
