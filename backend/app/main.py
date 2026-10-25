import json
import uuid
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from app.config import settings
from app.models.schemas import (
    FileMetadata,
    OrganizeRequest,
    OrganizeResponse,
    DownloadZipRequest,
    HealthResponse
)
from app.services.ai_organizer import ai_organizer
from app.services.zip_service import zip_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("lazyflow.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing LazyFlow AI Backend...")
    # Clean up stale sessions on startup
    zip_service.cleanup_stale_sessions(max_age_seconds=settings.SESSION_EXPIRY_MINUTES * 60)
    logger.info(f"Loaded Backboard configuration: Model={settings.BACKBOARD_DEFAULT_MODEL}, Provider={settings.BACKBOARD_DEFAULT_PROVIDER}")
    yield
    logger.info("Shutting down LazyFlow AI Backend...")

app = FastAPI(
    title="LazyFlow AI API",
    description="AI-powered file organizer and smart renamer for the Hacktoberfest DEV Week challenge 'Slow and Steady'.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX if settings.CORS_ORIGIN_REGEX else None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

@app.get("/", tags=["General"])
async def root():
    return {
        "app": "LazyFlow AI",
        "tagline": "Upload the mess. Let AI do the rest.",
        "docs": "/docs",
        "health": "/api/health",
        "model_badge": "Open-Weight AI · Powered by Backboard"
    }

from app.services.ocr_service import ocr_service
from app.services.vision_service import vision_service

@app.get("/api/health", response_model=HealthResponse, tags=["Diagnostics"])
async def health_check():
    configured = ai_organizer.check_configuration()
    engine_info = ocr_service.get_engine_info()
    vis_info = vision_service.get_engine_info()
    return HealthResponse(
        status="healthy" if configured else "misconfigured",
        app_name="LazyFlow AI",
        backboard_configured=configured,
        model=settings.BACKBOARD_DEFAULT_MODEL,
        provider=settings.BACKBOARD_DEFAULT_PROVIDER,
        version="1.0.0",
        ocr_available=engine_info["available"],
        ocr_engine=f"Tesseract {engine_info.get('version', '')}".strip(),
        vision_available=vis_info["available"],
        vision_engine=f"{vis_info.get('model_family', 'MobileNetV3-Small')}".strip()
    )

from app.services.content_extractor import content_extractor

@app.get("/api/model-status", tags=["Diagnostics"])
async def model_status():
    configured = ai_organizer.check_configuration()
    engine_info = ocr_service.get_engine_info()
    vis_info = vision_service.get_engine_info()
    return {
        "configured": configured,
        "provider": settings.BACKBOARD_DEFAULT_PROVIDER,
        "model_name": settings.BACKBOARD_DEFAULT_MODEL,
        "model_family": "Llama 3.1 (Open-Weight)",
        "open_weight": True,
        "hosted_via": "Backboard API",
        "privacy_policy": "Zero file content transmission without user consent. With explicit consent, only minimal locally-extracted text snippets (up to 1KB) are analyzed. Ephemeral session storage.",
        "content_analysis_supported": True,
        "ocr_supported": True,
        "ocr_available": engine_info["available"],
        "ocr_engine": engine_info,
        "vision_supported": True,
        "vision_available": vis_info["available"],
        "vision_engine": vis_info,
        "max_batch_files": settings.MAX_BATCH_FILES,
        "max_file_size_mb": settings.MAX_FILE_SIZE_MB
    }

@app.post("/api/organize-metadata", response_model=OrganizeResponse, tags=["AI Organization"])
async def organize_metadata(request: OrganizeRequest):
    """
    Test or simulate organization without file uploads.
    Accepts list of file metadata items and runs Backboard AI.
    """
    return await ai_organizer.organize_files(
        files=request.files,
        custom_categories=request.custom_categories
    )

from app.utils.sample_fixtures import get_standard_sample_files
from fastapi import Response

@app.get("/api/sample-files", tags=["Sample Data"])
async def list_sample_files():
    """
    Returns list of genuine sample files with their metadata and hints.
    Allows frontend and automated tests to fetch real binary files.
    """
    samples = get_standard_sample_files()
    hints = {
        "document.pdf": "Generic name, contains full resume",
        "file.pdf": "Generic name, contains hosting invoice",
        "notes.docx": "Generic name, contains CS50 study notes",
        "ambiguous_data.bin": "Minimal binary data, ambiguous content",
        "apollo_mission_proposal.docx": "Apollo Project mission proposal",
        "apollo_budget.csv": "Apollo Project budget sheet",
        "Invoice_Oct_final_v2_FINAL.pdf": "October cloud hosting bill",
        "IMG_20231012_WA0004.jpg": "Team meetup photo",
        "draft_cs50_week3_notes.docx": "CS50 algorithms lecture notes",
        "Screenshot 2024-03-01 at 4.22.19 PM.png": "Checkout button UI bug",
        "w2_tax_return_2023.pdf": "Annual tax document",
        "q4_roadmap_presentation_team.pptx": "Quarterly company roadmap",
        "dump_users_export_v1_backup.csv": "Database user export",
    }
    mimes = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "png": "image/png",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "csv": "text/csv",
        "bin": "application/octet-stream",
    }

    result = []
    for filename, data in samples.items():
        ext = filename.split(".")[-1].lower()
        result.append({
            "name": filename,
            "size": len(data),
            "mime_type": mimes.get(ext, "application/octet-stream"),
            "hint": hints.get(filename, ""),
            "download_url": f"/api/sample-files/{filename}"
        })
    return result

@app.get("/api/sample-files/{filename}", tags=["Sample Data"])
async def get_sample_file(filename: str):
    """
    Serves genuine, valid binary content for the specified sample file.
    """
    samples = get_standard_sample_files()
    if filename not in samples:
        raise HTTPException(status_code=404, detail=f"Sample file '{filename}' not found.")

    data = samples[filename]
    ext = filename.split(".")[-1].lower()
    mimes = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "png": "image/png",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "csv": "text/csv",
        "bin": "application/octet-stream",
    }
    media_type = mimes.get(ext, "application/octet-stream")

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )

@app.post("/api/upload-and-organize", response_model=OrganizeResponse, tags=["AI Organization"])
async def upload_and_organize(
    files: List[UploadFile] = File(...),
    custom_categories: Optional[str] = Form(None),
    user_folder: Optional[str] = Form(None),
    descriptions: Optional[str] = Form(None),
    consent_content_analysis: bool = Form(True)
):
    """
    Primary workflow endpoint:
    1. Temporarily stores uploaded files under an ephemeral session directory.
    2. If consent_content_analysis is True, extracts minimal text snippets (up to 1KB).
    3. Sends filenames, extensions, hints, and minimal snippets to Backboard AI.
    4. Returns AI-generated organization structure (folders, clean filenames, reasons).
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    if len(files) > settings.MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files! Maximum allowed is {settings.MAX_BATCH_FILES} files per batch."
        )

    # Parse custom categories if provided
    parsed_custom: Optional[List[str]] = None
    if custom_categories:
        try:
            parsed_custom = [c.strip() for c in custom_categories.split(",") if c.strip()]
        except Exception:
            parsed_custom = None
    elif user_folder:
        parsed_custom = [user_folder.strip()]

    # Parse descriptions if provided as JSON string
    desc_map = {}
    if descriptions:
        try:
            desc_map = json.loads(descriptions)
        except Exception:
            desc_map = {}

    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    logger.info(
        f"[Diagnostic:Upload] Received {len(files)} uploaded file(s). "
        f"Session: '{session_id}'. Consent for content analysis: {consent_content_analysis}."
    )
    
    # Save files to session directory
    saved_files = await zip_service.save_uploaded_files(session_id, files)

    # Extract content snippets if user consented
    metadata_list: List[FileMetadata] = []
    for item in saved_files:
        content_snippet: Optional[str] = None
        extracted_meta: Optional[dict] = None

        if consent_content_analysis:
            ext_res = content_extractor.extract_file_content(
                file_path=item["stored_path"],
                filename=item["filename"],
                mime_type=item["mime_type"]
            )
            content_snippet = ext_res.get("content_snippet")
            extracted_meta = ext_res.get("extracted_metadata")

        metadata_list.append(
            FileMetadata(
                id=item["id"],
                filename=item["filename"],
                size=item["size"],
                mime_type=item["mime_type"],
                description=desc_map.get(item["filename"], ""),
                content_snippet=content_snippet,
                extracted_metadata=extracted_meta
            )
        )

    # Run Backboard AI categorization
    response = await ai_organizer.organize_files(
        files=metadata_list,
        custom_categories=parsed_custom,
        session_id=session_id
    )

    return response

@app.post("/api/download-zip", tags=["Export"])
async def download_zip(request: DownloadZipRequest):
    """
    Takes user-reviewed and approved file structure and session ID,
    generates a clean organized ZIP archive with folders and renamed files,
    and returns it as a streaming download.
    """
    zip_buffer, zip_filename = zip_service.build_organized_zip(
        session_id=request.session_id,
        items=request.items
    )

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

@app.delete("/api/session/{session_id}", tags=["Session"])
async def cleanup_session(session_id: str):
    zip_service.cleanup_session(session_id)
    return {"status": "success", "message": f"Session {session_id} cleaned up successfully."}
