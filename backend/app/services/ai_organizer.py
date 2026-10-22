import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from backboard import BackboardClient

from app.config import settings
from app.models.schemas import FileMetadata, FileOrganizedItem, OrganizeResponse
from app.utils.sanitizer import sanitize_filename, sanitize_folder_name, resolve_duplicate_names

logger = logging.getLogger("lazyflow.ai")

SYSTEM_PROMPT = """You are LazyFlow AI, an intelligent file organization and naming assistant powered by open-weight AI.
Your task is to classify messy files into appropriate folders and suggest clean, descriptive, readable filenames.

STANDARD FOLDERS & CATEGORIES:
- "Documents": Reports, forms, letters, PDF documents, sheets, presentations
- "Images": Photos, screenshots, artwork, graphics, wallpapers
- "Work": Resumes, meeting notes, project plans, sprints, corporate files
- "Study": Lecture slides, coursework, study guides, homework, notes
- "Finance": Invoices, receipts, tax returns, bills, bank statements
- "Code": Scripts, source code, config files, data dumps
- "Other": Miscellaneous files not fitting above

RULES:
1. Preserve the EXACT original file extension. Never omit or change the file extension.
2. Select the most fitting folder from the standard categories or any user-provided custom categories.
3. Suggest a clear, descriptive filename in kebab-case or readable format (e.g., 'invoice-october-2023.pdf', 'cs50-lecture-3-notes.docx'). If the original filename is obscure (like 'IMG_9921.jpg' or 'Scan_001.pdf') and user gave a description, prioritize the user description.
4. Give a brief, helpful 1-sentence reason.
5. Return ONLY a valid JSON array of objects conforming to this schema:
[
  {
    "id": "<file_id>",
    "original_filename": "<original_filename>",
    "folder": "<folder_name>",
    "category": "<category_name>",
    "suggested_filename": "<clean_suggested_filename_with_extension>",
    "reason": "<short explanation>"
  }
]
No other text, markdown formatting, or preamble. Return raw JSON array only.
"""

class AIOrganizerService:
    @property
    def api_key(self) -> str:
        return settings.BACKBOARD_API_KEY

    @property
    def base_url(self) -> str:
        return settings.BACKBOARD_BASE_URL

    @property
    def model(self) -> str:
        return settings.BACKBOARD_DEFAULT_MODEL

    @property
    def provider(self) -> str:
        return settings.BACKBOARD_DEFAULT_PROVIDER

    def check_configuration(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your_backboard"))

    async def organize_files(
        self,
        files: List[FileMetadata],
        custom_categories: Optional[List[str]] = None,
        session_id: Optional[str] = None
    ) -> OrganizeResponse:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided for organization.")

        if len(files) > settings.MAX_BATCH_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"Batch size limit exceeded. Maximum {settings.MAX_BATCH_FILES} files allowed per request."
            )

        if not self.check_configuration():
            raise HTTPException(
                status_code=503,
                detail="Backboard AI service is not configured. Please set a valid BACKBOARD_API_KEY in the backend environment."
            )

        # Prepare payload - ONLY metadata (filenames, extensions, sizes, hints) - NEVER file content!
        file_payload = [
            {
                "id": f.id,
                "filename": f.filename,
                "size_bytes": f.size,
                "mime_type": f.mime_type or "unknown",
                "description": f.description or ""
            }
            for f in files
        ]

        system_prompt = SYSTEM_PROMPT
        if custom_categories:
            custom_list_str = ", ".join([f'"{c.strip()}"' for c in custom_categories if c.strip()])
            system_prompt += f"\nUser Preferred Custom Categories: {custom_list_str}. Prefer these if applicable."

        user_content = f"Organize and suggest clean names for these files:\n{json.dumps(file_payload, indent=2)}"

        client = BackboardClient(api_key=self.api_key, base_url=self.base_url)
        assistant = None
        thread = None

        try:
            # Create assistant and thread with Backboard SDK
            assistant = await client.create_assistant(
                name="LazyFlow Organizer",
                description="Classifies files and suggests clean filenames",
                system_prompt=system_prompt
            )
            thread = await client.create_thread(assistant_id=assistant.assistant_id)

            # Request inference with open-weight model
            response = await client.send_message(
                content=user_content,
                thread_id=thread.thread_id,
                assistant_id=assistant.assistant_id,
                llm_provider=self.provider,
                model_name=self.model,
                stream=False
            )

            if not response or not getattr(response, "messages", None):
                raise HTTPException(
                    status_code=502,
                    detail="Backboard AI returned an empty response."
                )

            last_msg = response.messages[-1]
            content = last_msg.get("content") if isinstance(last_msg, dict) else getattr(last_msg, "content", "")
            
            if not content:
                raise HTTPException(
                    status_code=502,
                    detail="Backboard AI message contains no text content."
                )

            # Strip possible markdown fences
            cleaned = content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            try:
                parsed_items = json.loads(cleaned)
            except json.JSONDecodeError as je:
                logger.error(f"Failed to parse model JSON: {je}. Raw output was: {content}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Backboard AI returned malformed JSON: {str(je)}"
                )

            if not isinstance(parsed_items, list):
                raise HTTPException(
                    status_code=502,
                    detail="Backboard AI output was expected to be a JSON array of file items."
                )

            # Create robust lookup maps for original files
            orig_by_id = {str(f.id): f for f in files}
            orig_by_num = {str(f.id).replace("f_", ""): f for f in files}
            orig_by_name = {f.filename.lower(): f for f in files}

            matched_file_ids = set()
            processed_items: List[Dict[str, Any]] = []

            for idx, raw in enumerate(parsed_items):
                raw_id = str(raw.get("id", "")).strip()
                raw_orig_name = raw.get("original_filename", "").strip()

                # Robust lookup: exact ID -> num ID -> filename -> index
                orig = orig_by_id.get(raw_id)
                if not orig and raw_id in orig_by_num:
                    orig = orig_by_num[raw_id]
                if not orig and raw_orig_name.lower() in orig_by_name:
                    orig = orig_by_name[raw_orig_name.lower()]
                if not orig and idx < len(files) and files[idx].id not in matched_file_ids:
                    orig = files[idx]

                if not orig or orig.id in matched_file_ids:
                    continue
                matched_file_ids.add(orig.id)

                orig_name = orig.filename
                # Sanitize folder and filename
                folder = sanitize_folder_name(raw.get("folder", "Other"))
                category = sanitize_folder_name(raw.get("category", folder))
                suggested = sanitize_filename(raw.get("suggested_filename", orig_name), original_name=orig_name)
                reason = raw.get("reason", "Organized by AI based on filename and metadata.")

                processed_items.append({
                    "id": orig.id,  # CRITICAL: Always preserve exact session file ID
                    "original_filename": orig_name,
                    "folder": folder,
                    "category": category,
                    "suggested_filename": suggested,
                    "reason": reason,
                    "excluded": False,
                    "user_modified": False
                })

            # Check if any original files were missed by the model
            for f in files:
                if f.id not in matched_file_ids:
                    safe_folder = "Documents"
                    processed_items.append({
                        "id": f.id,
                        "original_filename": f.filename,
                        "folder": safe_folder,
                        "category": safe_folder,
                        "suggested_filename": sanitize_filename(f.filename, original_name=f.filename),
                        "reason": "Retained original filename (automatic safe fallback).",
                        "excluded": False,
                        "user_modified": False
                    })
                    matched_file_ids.add(f.id)

            # Resolve duplicate filenames in the same folder
            resolved = resolve_duplicate_names(processed_items)

            # Calculate summary categories
            category_counts: Dict[str, int] = {}
            for item in resolved:
                cat = item["folder"]
                category_counts[cat] = category_counts.get(cat, 0) + 1

            file_items = [FileOrganizedItem(**item) for item in resolved]

            return OrganizeResponse(
                session_id=session_id,
                model_used=self.model,
                provider=self.provider,
                total_files=len(file_items),
                items=file_items,
                categories_summary=category_counts,
                message="Files successfully categorized and renamed by Backboard AI."
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Backboard API invocation failed")
            raise HTTPException(
                status_code=502,
                detail=f"Backboard API communication error: {str(e)}"
            )
        finally:
            if assistant:
                try:
                    await client.delete_assistant(assistant.assistant_id)
                except Exception:
                    pass
            await client.aclose()

ai_organizer = AIOrganizerService()
