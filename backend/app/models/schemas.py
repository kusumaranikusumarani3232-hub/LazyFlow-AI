from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class FileMetadata(BaseModel):
    id: str
    filename: str
    size: int = 0
    mime_type: Optional[str] = None
    description: Optional[str] = Field(default="", description="Optional user note or hint about file contents")

class OrganizeRequest(BaseModel):
    files: List[FileMetadata]
    custom_categories: Optional[List[str]] = Field(default=None, description="Custom categories preferred by user")

class FileOrganizedItem(BaseModel):
    id: str
    original_filename: str
    folder: str
    category: str
    suggested_filename: str
    reason: str
    excluded: bool = False
    user_modified: bool = False

class OrganizeResponse(BaseModel):
    session_id: Optional[str] = None
    model_used: str
    provider: str
    total_files: int
    items: List[FileOrganizedItem]
    categories_summary: Dict[str, int]
    message: str

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
