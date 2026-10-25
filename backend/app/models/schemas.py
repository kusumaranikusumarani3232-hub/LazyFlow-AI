from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class FileMetadata(BaseModel):
    id: str
    filename: str
    size: int = 0
    mime_type: Optional[str] = None
    description: Optional[str] = Field(default="", description="Optional user note or hint about file contents")
    content_snippet: Optional[str] = Field(default=None, description="Concise locally-extracted content text or structure")
    extracted_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Extracted file structural metadata")
    folder: Optional[str] = Field(default=None, description="Pre-selected or user-specified destination folder")

class OrganizeRequest(BaseModel):
    files: List[FileMetadata]
    custom_categories: Optional[List[str]] = Field(default=None, description="Custom categories preferred by user")
    consent_content_analysis: bool = Field(default=True, description="Whether user consented to content-aware analysis")

class FileOrganizedItem(BaseModel):
    id: str
    original_filename: str
    folder: str
    category: str
    suggested_filename: str
    reason: str
    excluded: bool = False
    user_modified: bool = False
    is_ambiguous: bool = False
    confidence: Optional[str] = "high"

class OrganizeResponse(BaseModel):
    session_id: Optional[str] = None
    model_used: str
    provider: str
    total_files: int
    items: List[FileOrganizedItem]
    categories_summary: Dict[str, int]
    message: str
    content_analysis_used: bool = True

class DownloadZipRequest(BaseModel):
    session_id: str
    items: List[FileOrganizedItem]

class HealthResponse(BaseModel):
    status: str
    app_name: str = "LazyFlow AI"
    backboard_configured: bool
    model: str
    provider: str
    version: str = "1.0.0"
    ocr_available: Optional[bool] = None
    ocr_engine: Optional[str] = None
    vision_available: Optional[bool] = None
    vision_engine: Optional[str] = None
