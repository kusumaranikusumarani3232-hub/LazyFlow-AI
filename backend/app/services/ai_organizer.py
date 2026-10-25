import json
import logging
import re
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from backboard import BackboardClient

from app.config import settings
from app.models.schemas import FileMetadata, FileOrganizedItem, OrganizeResponse
from app.utils.sanitizer import sanitize_filename, sanitize_folder_name, resolve_duplicate_names

logger = logging.getLogger("lazyflow.ai")

SYSTEM_PROMPT = """You are LazyFlow AI, an intelligent content-aware file organization and naming assistant powered by open-weight AI.
Your task is to analyze file contents, structures, metadata, and filenames to classify messy files into purpose-based folders and suggest clean, descriptive, readable filenames.

STANDARD PURPOSE-BASED FOLDERS:
- "Career": Resumes, CVs, cover letters, portfolios, job applications, interview materials, certificates of completion, course/professional certificates, credentials, achievements.
- "Finance": Invoices, bills, receipts, tax returns, payment statements, budgets, financial ledgers.
- "Study": Lecture notes, homework, study guides, coursework, reading summaries, exam prep.
- "Work": Corporate documents, meeting minutes, project roadmaps, client proposals, architecture specs, status updates, project/quarterly/annual reports.
- "Documents": General official letters, forms, agreements, contracts, policy documents, miscellaneous documents.
- "Images": Photos, screenshots, wallpapers, artwork, graphic designs.
- "Code": Source code, scripts, configs, database dumps/exports.
- "Other": Miscellaneous files or ambiguous files not fitting above.

RULES FOR CLASSIFICATION AND NAMING:
1. CONTENT-AWARE PURPOSE INFERENCE (CONTENT ALWAYS DICTATES PURPOSE OVER FILENAME):
   - The file's internal readable text/content dictates its true purpose, NOT generic or arbitrary filenames (like 'document.pdf', 'pdf.pdf', 'file.pdf', 'scrape verse.pdf', 'upload1.pdf', 'notes.docx').
   - Common Document Types and Naming Rules:
     * Resumes / CVs: If content contains resume sections (Summary, Experience, Education, Skills, Work History), place in "Career", suggested filename: "Resume.pdf" (or "<Candidate_Name>-Resume.pdf" if the person's name is clearly evident in the content).
     * Certificates: If content indicates a certificate (e.g. Certificate of Completion, Certificate of Achievement, "This is to certify that", "has successfully completed", course name, or issuing organization):
       - Place in "Career" (or user's selected destination folder if specified, or "Documents").
       - Suggest a meaningful filename based strictly on evidence in the content: "<Organization>-<Course>-Certificate.pdf", "<Course>-Certificate.pdf", or "<Organization>-Certificate.pdf" (e.g. 'TCS-iON-Career-Edge-Certificate.pdf', 'ScrapeVerse-Web-Scraping-Certificate.pdf').
       - If only generic certificate heading is present without identifiable org or course, suggest 'Certificate-of-Completion.pdf' or 'Certificate.pdf'.
       - NEVER invent an organization, course name, or person name not present in the extracted text.
     * Invoices: If content contains invoice markers (Invoice #, Bill To, Amount Due, Due Date), place in "Finance", suggested filename: "<Vendor>-Invoice.pdf" or "Invoice.pdf".
     * Receipts: If content contains payment confirmation, receipt number, total paid, or merchant details, place in "Finance", suggested filename: "<Merchant>-Receipt.pdf" or "Receipt.pdf".
     * Reports: If content contains project reports, audit reports, quarterly/annual reports, or status reports, place in "Work" (or "Documents"), suggested filename: "<Topic>-Report.pdf" or "Report.pdf".
     * Study Notes: If content contains lecture notes, coursework, syllabus, exam prep, or study notes, place in "Study", suggested filename: "<Course>-Study-Notes.docx" or "Study Notes.docx".
     * Spreadsheets / Ledgers: Place in "Finance" if financial transactions, suggested filename: "Financial_Transactions.csv".
     * Visual Images (Clothing, Animals, Products, Nature, Screenshots):
       - If content snippet indicates visual classification (e.g. "Visual classification: identified T-Shirt (Clothing)"):
         * Suggest a clean, descriptive filename reflecting the recognized concept: e.g. "T-Shirt.<ext>" (e.g. "T-Shirt.jpeg").
         * Place in "Images" (or user's selected destination folder).
         * Set "is_ambiguous": false, "confidence": "high".
         * Do NOT label an image as a certificate unless verified certificate text is explicitly present in extracted content.
       - If an image is ordinary, abstract, or visual classification is uncertain/minimal:
         * Retain the exact original filename.
         * Place in "Images" (or user's selected destination folder).
         * Set "is_ambiguous": true, "confidence": "ambiguous".

2. PRESERVE USER'S SELECTED DESTINATION FOLDER:
   - If the user has a selected destination folder (e.g. "Career") or specified preferred categories, keep that destination folder unchanged unless explicitly conflicting. Improve the suggested filename independently based on content evidence.

3. MIXED UPLOADS & SHARED CONTEXTUAL GROUPING:
   - When multiple files across different formats share an evident relationship to a specific project, event, or topic (e.g., 'Project Apollo Proposal.docx', 'apollo_budget.xlsx', 'apollo_architecture.png'), group them together into a shared descriptive folder named after that project (e.g., "Project Apollo").
   - If files do not share an evident contextual project relationship, place each file in its sensible short category folder (Career, Finance, Study, Work, etc.).

4. AMBIGUOUS FILES & ANTI-HALLUCINATION (CRITICAL):
   - NEVER invent content or confidently label an ambiguous file.
   - If a file has minimal, missing, corrupt, random bytes, or inconclusive content, or if extraction failed:
     * RETAIN THE EXACT ORIGINAL FILENAME for 'suggested_filename' (e.g. keep 'pdf.pdf', do NOT change to 'Pdf.pdf' or invent a purpose).
     * Place the file in "Documents" or "Other".
     * Set 'reason' to honestly explain: "Ambiguous or minimal content detected; retained original filename for user review."
     * Set "is_ambiguous": true and "confidence": "ambiguous".
     * Do NOT guess or hallucinate corporate roadmap, certificate, or any imaginary purpose without clear textual proof.

5. PRESERVE FILE EXTENSION:
   - ALWAYS preserve the exact original file extension (.pdf, .docx, .csv, .png, etc.). Never change or remove it.

6. OUTPUT SCHEMA:
   Return ONLY a valid JSON array of objects conforming to this schema:
   [
     {
       "id": "<file_id>",
       "original_filename": "<original_filename>",
       "folder": "<folder_name>",
       "category": "<category_name>",
       "suggested_filename": "<clean_suggested_filename_with_extension>",
       "reason": "<short 1-sentence reason explaining classification>",
       "is_ambiguous": false,
       "confidence": "high"
     }
   ]
No preamble, no markdown code block wrapping, raw JSON array only.
"""

GENERIC_STEMS = {
    "pdf", "doc", "docs", "document", "file", "files", "untitled",
    "test", "scan", "data", "upload", "temp", "new", "image", "download"
}


def _flatten_json_array(decoded: Any) -> List[Dict[str, Any]]:
    """Flatten any nested list structures and ensure only dict objects are returned."""
    items: List[Dict[str, Any]] = []
    if isinstance(decoded, dict):
        items.append(decoded)
    elif isinstance(decoded, list):
        for sub in decoded:
            if isinstance(sub, dict):
                items.append(sub)
            elif isinstance(sub, list):
                for sub_item in sub:
                    if isinstance(sub_item, dict):
                        items.append(sub_item)
    return items


def extract_json_array(text: str) -> Optional[List[Dict[str, Any]]]:
    """
    Robustly extract a JSON array of objects from LLM responses, handling markdown code fences,
    introductory preambles, conversational postscripts, and nested list structures.
    """
    if not text:
        return None
    raw = text.strip()

    # 1. Direct JSON parse
    try:
        decoded = json.loads(raw)
        items = _flatten_json_array(decoded)
        if items:
            return items
    except Exception:
        pass

    # 2. Extract from markdown code fence ```json ... ``` or ``` ... ```
    fence_pattern = r"```(?:json)?\s*(\[\s*\{.*?\}\s*\])\s*```"
    match = re.search(fence_pattern, raw, re.DOTALL)
    if match:
        try:
            decoded = json.loads(match.group(1).strip())
            items = _flatten_json_array(decoded)
            if items:
                return items
        except Exception:
            pass

    # 3. Outer bracket search ([ ... ])
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1 and end > start:
        candidate = raw[start:end + 1].strip()
        try:
            decoded = json.loads(candidate)
            items = _flatten_json_array(decoded)
            if items:
                return items
        except Exception:
            pass

    return None


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

        # Build payload with safe character limits
        file_payload = []
        files_with_content = 0
        for f in files:
            entry: Dict[str, Any] = {
                "id": f.id,
                "filename": f.filename,
                "size_bytes": f.size,
                "mime_type": f.mime_type or "unknown",
                "description": f.description or ""
            }
            if f.content_snippet and f.content_snippet.strip():
                entry["content_snippet"] = f.content_snippet.strip()[:1200]
                files_with_content += 1
            if f.extracted_metadata:
                entry["extracted_metadata"] = f.extracted_metadata
            file_payload.append(entry)

        system_prompt = SYSTEM_PROMPT
        if custom_categories:
            custom_list_str = ", ".join([f'"{c.strip()}"' for c in custom_categories if c.strip()])
            system_prompt += f"\nUser Preferred Custom Categories: {custom_list_str}. Prefer these if applicable."

        shared_project = self._detect_shared_project(files)
        user_content = f"Analyze and organize these files with content awareness:\n{json.dumps(file_payload, indent=2)}"
        if shared_project:
            user_content += f"\n\nNote: A shared project relationship '{shared_project}' was detected among these files. Group the related files into folder '{shared_project}'."

        parsed_items: Optional[List[Dict[str, Any]]] = None
        inference_source = "backboard_ai"

        # Attempt inference with Backboard AI
        if self.check_configuration():
            client = BackboardClient(api_key=self.api_key, base_url=self.base_url)
            assistant = None
            thread = None
            try:
                logger.info(
                    f"[Diagnostic:AI_Request] Submitting {len(files)} file(s) to Backboard AI "
                    f"(model='{self.model}', provider='{self.provider}'). "
                    f"Files with extracted content: {files_with_content}/{len(files)}."
                )
                assistant = await client.create_assistant(
                    name="LazyFlow Content Organizer",
                    description="Classifies files and suggests clean filenames based on content and metadata",
                    system_prompt=system_prompt
                )
                thread = await client.create_thread(assistant_id=assistant.assistant_id)

                response = await client.send_message(
                    content=user_content,
                    thread_id=thread.thread_id,
                    assistant_id=assistant.assistant_id,
                    llm_provider=self.provider,
                    model_name=self.model,
                    stream=False
                )

                content = getattr(response, "content", None)
                if not content and getattr(response, "messages", None):
                    last_msg = response.messages[-1]
                    content = last_msg.get("content") if isinstance(last_msg, dict) else getattr(last_msg, "content", "")

                if content:
                    parsed_items = extract_json_array(content)
                    if parsed_items:
                        logger.info(
                            f"[Diagnostic:AI_Response] Successfully parsed {len(parsed_items)} item(s) from Backboard AI "
                            f"(raw_response_len={len(content)})."
                        )
                    else:
                        logger.warning(
                            f"[Diagnostic:AI_Response] Backboard AI returned unparseable text format "
                            f"(raw_chars={len(content)}). Falling back to cautious local heuristic."
                        )
            except Exception as e:
                logger.warning(
                    f"[Diagnostic:AI_Response] Backboard AI service call failed: {type(e).__name__}: {e}. "
                    f"Falling back to cautious local heuristic."
                )
            finally:
                if assistant:
                    try:
                        await client.delete_assistant(assistant.assistant_id)
                    except Exception:
                        pass
                await client.aclose()

        # If Backboard AI was unconfigured or failed, use rule-based cautious fallback
        if parsed_items is None:
            inference_source = "cautious_local_heuristic"
            logger.info("[Diagnostic:AI_Response] Activating cautious local content-aware heuristic engine.")
            parsed_items = self._infer_heuristic(files, custom_categories)

        # Match results back to original files
        orig_by_id = {str(f.id): f for f in files}
        orig_by_num = {str(f.id).replace("f_", ""): f for f in files}
        orig_by_name = {f.filename.lower(): f for f in files}

        matched_file_ids = set()
        processed_items: List[Dict[str, Any]] = []

        for idx, raw in enumerate(parsed_items):
            if not isinstance(raw, dict):
                continue
            raw_id = str(raw.get("id", "")).strip()
            raw_orig_name = raw.get("original_filename", "").strip()

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
            stem = orig_name.rsplit(".", 1)[0].lower() if "." in orig_name else orig_name.lower()
            ext = orig_name.split(".")[-1].lower() if "." in orig_name else ""
            meta = orig.extracted_metadata or {}
            is_empty_or_minimal = meta.get("is_empty_or_minimal", False)
            has_snippet = bool(orig.content_snippet and orig.content_snippet.strip())

            raw_folder = raw.get("folder") or "Other"
            raw_category = raw.get("category") or raw_folder
            folder = sanitize_folder_name(raw_folder)
            category = sanitize_folder_name(raw_category)
            suggested = sanitize_filename(raw.get("suggested_filename") or orig_name, original_name=orig_name)
            reason = raw.get("reason") or "Organized by AI based on content and metadata."
            is_ambiguous = bool(raw.get("is_ambiguous", False))
            confidence = raw.get("confidence", "high")

            # Check for user-selected destination folder (e.g. Career, Finance, Study, or custom category)
            user_selected_folder = getattr(orig, "folder", None)
            if not user_selected_folder and custom_categories and len(custom_categories) == 1:
                user_selected_folder = custom_categories[0]

            snippet = (orig.content_snippet or "").strip()
            desc = (orig.description or "").strip()
            full_context = f"{orig_name} {desc} {snippet}".strip()

            # CRITICAL ANTI-HALLUCINATION SAFEGUARD:
            # If extraction fails or evidence is insufficient (empty/minimal snippet and no description),
            # or if the classification is marked ambiguous, preserve the exact original filename
            # and use a cautious fallback instead of inventing a document purpose.
            if (is_empty_or_minimal or not has_snippet) and not orig.description:
                suggested = orig_name
                is_ambiguous = True
                confidence = "ambiguous"
                if not user_selected_folder:
                    if ext in ("png", "jpg", "jpeg", "webp", "bmp", "gif"):
                        folder = "Images"
                    elif ext in ("py", "js", "ts", "html", "css", "json", "sql", "sh", "java", "cpp", "c", "rs", "go"):
                        folder = "Code"
                    elif ext in ("pdf", "docx", "txt", "doc", "rtf", "odt"):
                        folder = "Documents"
                    else:
                        folder = "Other"
                    category = folder
                reason = "Preserved original filename for image in Images folder." if ext in ("png", "jpg", "jpeg", "webp", "bmp", "gif") else "Ambiguous or minimal content detected; retained original filename for user review."
            elif is_ambiguous:
                suggested = orig_name
            else:
                # Content evidence refinement:
                # If content contains clear evidence for a document type or visual concept,
                # ensure suggested filename and category reflect the evidence regardless of original filename.
                vis_concept = (orig.extracted_metadata or {}).get("visual_concept")
                vis_cat = (orig.extracted_metadata or {}).get("visual_category")
                vis_folder = (orig.extracted_metadata or {}).get("visual_folder", "Images")
                vis_conf = (orig.extracted_metadata or {}).get("visual_confidence", "high")

                if vis_concept and ext in ("png", "jpg", "jpeg", "webp", "bmp", "gif"):
                    is_ambiguous = False
                    confidence = vis_conf
                    suggested = f"{vis_concept}.{ext}"
                    if not user_selected_folder:
                        folder = vis_folder or "Images"
                        category = folder
                    reason = f"Identified visual image of {vis_concept} ({vis_cat}); organized into {folder}."
                else:
                    cert_name = self._name_certificate(orig_name, ext, desc, snippet)
                    if cert_name:
                        is_ambiguous = False
                        confidence = "high"
                        suggested = cert_name
                        reason = "Identified certificate of completion/achievement; suggested descriptive certificate filename."
                        if not user_selected_folder:
                            folder = "Career"
                            category = "Career"
                    elif self._is_resume(full_context):
                        is_ambiguous = False
                        confidence = "high"
                        is_generic_resume = any(k in stem.lower() for k in ("resume", "cv", "vitae", "candidate")) or stem in GENERIC_STEMS
                        has_id_or_secret = bool(re.search(r'[\d_]{4,}|passport|secret|id', suggested, re.IGNORECASE))
                        if is_generic_resume or has_id_or_secret or suggested.lower() in (orig_name.lower(), f"{stem}.{ext}") or "resume" not in suggested.lower():
                            suggested = f"Resume.{ext}" if ext else "Resume.pdf"
                            reason = "Identified resume/CV content (experience, education, skills); organized into Career."
                        if not user_selected_folder:
                            folder = "Career"
                            category = "Career"
                    elif self._is_invoice(full_context, ext):
                        is_ambiguous = False
                        confidence = "high"
                        if stem in GENERIC_STEMS or suggested.lower() in (orig_name.lower(), f"{stem}.{ext}") or "invoice" not in suggested.lower():
                            suggested = self._name_financial(orig_name, ext, desc, snippet)
                            reason = "Identified financial/billing/invoice data; organized into Finance."
                        if not user_selected_folder:
                            folder = "Finance"
                            category = "Finance"
                    elif self._is_receipt(full_context, ext):
                        is_ambiguous = False
                        confidence = "high"
                        if stem in GENERIC_STEMS or suggested.lower() in (orig_name.lower(), f"{stem}.{ext}") or "receipt" not in suggested.lower():
                            suggested = self._name_receipt(orig_name, ext, desc, snippet)
                            reason = "Identified payment receipt/transaction confirmation; organized into Finance."
                        if not user_selected_folder:
                            folder = "Finance"
                            category = "Finance"
                    elif self._is_study(full_context, ext):
                        is_ambiguous = False
                        confidence = "high"
                        if stem in GENERIC_STEMS or suggested.lower() in (orig_name.lower(), f"{stem}.{ext}") or ("study" not in suggested.lower() and "notes" not in suggested.lower()):
                            suggested = self._name_study(orig_name, ext, desc, snippet)
                            reason = "Identified lecture/coursework study notes; organized into Study."
                        if not user_selected_folder:
                            folder = "Study"
                            category = "Study"
                    elif ext in ("py", "js", "ts", "html", "css", "json", "sql", "sh", "java", "cpp", "c", "rs", "go"):
                        is_ambiguous = False
                        confidence = "high"
                        if not user_selected_folder:
                            folder = "Code"
                            category = "Code"
                        reason = "Classified source code or configuration into Code."
                    elif ext in ("png", "jpg", "jpeg", "webp", "bmp", "gif"):
                        if not user_selected_folder:
                            folder = "Images"
                            category = "Images"
                        # For ordinary photos or unclear images, preserve original filename
                        suggested = orig_name
                        is_ambiguous = True
                        confidence = "ambiguous"
                        reason = "Preserved original filename for ordinary/unclear image into Images."
                    elif self._is_report(full_context, ext):
                        is_ambiguous = False
                        confidence = "high"
                        if stem in GENERIC_STEMS or suggested.lower() in (orig_name.lower(), f"{stem}.{ext}") or "report" not in suggested.lower():
                            suggested = self._name_report(orig_name, ext, desc, snippet)
                            reason = "Identified project/status/annual report document; organized into Documents."
                        if not user_selected_folder and folder in ("Other", "General"):
                            folder = "Documents"
                            category = "Documents"

            # Requirement 5: Keep the user's selected destination folder unchanged unless explicitly changed
            if user_selected_folder:
                folder = sanitize_folder_name(user_selected_folder)
                category = folder

            # Ensure suggested filename has correct extension preserved
            if not suggested.lower().endswith(f".{ext}") and ext:
                suggested = f"{suggested.rsplit('.', 1)[0]}.{ext}"

            # If not ambiguous, ensure suggested filename is sanitized consistently with zip export
            if not is_ambiguous:
                suggested = sanitize_filename(suggested, original_name=orig_name)

            # If the suggested filename is merely the generic stem title-cased (e.g. 'Pdf.pdf', 'Document.pdf'),
            # and no specific evidence was found, retain exact original filename
            if suggested.lower() == f"{stem}.{ext}" and is_ambiguous:
                suggested = orig_name

            # Shared project grouping across mixed files (e.g. Apollo)
            if shared_project and not is_empty_or_minimal:
                if shared_project.lower() in (orig_name.lower() + " " + (orig.content_snippet or "").lower()):
                    if folder in ("Work", "Documents", "Other", "General"):
                        folder = shared_project
                        category = shared_project

            item_dict = {
                "id": orig.id,
                "original_filename": orig_name,
                "folder": folder,
                "category": category,
                "suggested_filename": suggested,
                "reason": reason,
                "excluded": False,
                "user_modified": False,
                "is_ambiguous": is_ambiguous,
                "confidence": confidence
            }
            processed_items.append(item_dict)

            logger.info(
                f"[Diagnostic:Classification] File '{orig_name}' -> Folder: '{folder}', "
                f"Suggested: '{suggested}', Ambiguous: {is_ambiguous}, Source: '{inference_source}'."
            )

        # Fallback for any missing files
        for f in files:
            if f.id not in matched_file_ids:
                safe_folder = "Documents"
                item_dict = {
                    "id": f.id,
                    "original_filename": f.filename,
                    "folder": safe_folder,
                    "category": safe_folder,
                    "suggested_filename": sanitize_filename(f.filename, original_name=f.filename),
                    "reason": "Retained original filename (automatic safe fallback).",
                    "excluded": False,
                    "user_modified": False,
                    "is_ambiguous": True,
                    "confidence": "low"
                }
                processed_items.append(item_dict)
                matched_file_ids.add(f.id)
                logger.info(f"[Diagnostic:Classification] File '{f.filename}' (unmatched fallback) -> '{safe_folder}/{f.filename}'")

        # Resolve duplicate filenames in the same destination folder
        resolved = resolve_duplicate_names(processed_items)

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
            message="Files successfully categorized and renamed by Backboard AI.",
            content_analysis_used=(files_with_content > 0)
        )

    def _infer_heuristic(
        self,
        files: List[FileMetadata],
        custom_categories: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Cautious, deterministic content-aware fallback.
        Infers purpose from extracted content snippets and metadata.
        Never invents content or document purpose when evidence is insufficient.
        """
        results = []
        shared_project = self._detect_shared_project(files)

        for f in files:
            orig_name = f.filename
            name_lower = orig_name.lower()
            stem = orig_name.rsplit(".", 1)[0].lower() if "." in orig_name else orig_name.lower()
            snippet = (f.content_snippet or "").strip()
            desc = (f.description or "").strip()
            meta = f.extracted_metadata or {}
            ext = orig_name.split(".")[-1].lower() if "." in orig_name else ""
            full_context = f"{name_lower} {desc.lower()} {snippet.lower()}".strip()

            is_minimal = meta.get("is_empty_or_minimal", False) or len(snippet) < 15

            # User selected folder
            user_selected_folder = getattr(f, "folder", None)
            if not user_selected_folder and custom_categories and len(custom_categories) == 1:
                user_selected_folder = custom_categories[0]

            # 0. Ambiguous, Minimal, Corrupted, or Failed Extraction -> Cautious fallback
            if (is_minimal and not desc) or meta.get("error"):
                safe_folder = "Other"
                if ext in ("png", "jpg", "jpeg", "webp", "bmp", "gif"):
                    safe_folder = "Images"
                elif ext in ("py", "js", "ts", "html", "css", "json", "sql", "sh", "java", "cpp", "c", "rs", "go"):
                    safe_folder = "Code"
                elif ext in ("pdf", "docx", "txt", "doc", "rtf", "odt"):
                    safe_folder = "Documents"

                results.append({
                    "id": f.id,
                    "original_filename": orig_name,
                    "folder": user_selected_folder or safe_folder,
                    "category": user_selected_folder or safe_folder,
                    "suggested_filename": orig_name,
                    "reason": "Preserved original filename for image in Images folder." if ext in ("png", "jpg", "jpeg", "webp", "bmp", "gif") else "Ambiguous or minimal content detected; retained original filename for user review.",
                    "is_ambiguous": True,
                    "confidence": "ambiguous"
                })
                continue

            # Check for shared project context across mixed files (e.g. "Apollo")
            if shared_project and not is_minimal:
                if shared_project.lower() in full_context or (len(files) > 1 and all(shared_project.lower() in (cf.filename.lower() + " " + (cf.content_snippet or "").lower()) for cf in files if cf.filename.lower().startswith(shared_project.lower()[:4]))):
                    folder = user_selected_folder or shared_project
                    suggested = self._clean_suggested_name(orig_name, ext, desc, snippet, is_resume=False)
                    results.append({
                        "id": f.id,
                        "original_filename": orig_name,
                        "folder": folder,
                        "category": folder,
                        "suggested_filename": suggested,
                        "reason": f"Grouped into shared contextual folder '{folder}' based on project relationship.",
                        "is_ambiguous": False,
                        "confidence": "high"
                    })
                    continue

            # 0. Visual Image Classification -> Images (or user_selected_folder)
            vis_concept = (f.extracted_metadata or {}).get("visual_concept")
            if vis_concept and ext in ("png", "jpg", "jpeg", "webp", "bmp", "gif"):
                vis_cat = (f.extracted_metadata or {}).get("visual_category")
                vis_folder = (f.extracted_metadata or {}).get("visual_folder", "Images")
                vis_conf = (f.extracted_metadata or {}).get("visual_confidence", "high")
                folder = user_selected_folder or vis_folder or "Images"
                suggested = f"{vis_concept}.{ext}"
                results.append({
                    "id": f.id,
                    "original_filename": orig_name,
                    "folder": folder,
                    "category": folder,
                    "suggested_filename": suggested,
                    "reason": f"Identified visual image of {vis_concept} ({vis_cat}); organized into {folder}.",
                    "is_ambiguous": False,
                    "confidence": vis_conf
                })
                continue

            # 1. Certificate -> Career (or user_selected_folder)
            cert_name = self._name_certificate(orig_name, ext, desc, snippet)
            if cert_name:
                folder = user_selected_folder or "Career"
                results.append({
                    "id": f.id,
                    "original_filename": orig_name,
                    "folder": folder,
                    "category": folder,
                    "suggested_filename": cert_name,
                    "reason": "Identified certificate of completion/achievement; suggested descriptive certificate filename.",
                    "is_ambiguous": False,
                    "confidence": "high"
                })
                continue

            # 2. Resume / CV -> Career
            if self._is_resume(full_context):
                folder = user_selected_folder or "Career"
                suggested = f"Resume.{ext}" if ext else "Resume.pdf"
                results.append({
                    "id": f.id,
                    "original_filename": orig_name,
                    "folder": folder,
                    "category": folder,
                    "suggested_filename": suggested,
                    "reason": "Identified resume/CV content (experience, education, skills); organized into Career.",
                    "is_ambiguous": False,
                    "confidence": "high"
                })
                continue

            # 3. Invoice / Bill / Tax / Financial Ledger -> Finance
            if self._is_invoice(full_context, ext):
                folder = user_selected_folder or "Finance"
                suggested = self._name_financial(orig_name, ext, desc, snippet)
                results.append({
                    "id": f.id,
                    "original_filename": orig_name,
                    "folder": folder,
                    "category": folder,
                    "suggested_filename": suggested,
                    "reason": "Identified financial/billing/invoice data; organized into Finance.",
                    "is_ambiguous": False,
                    "confidence": "high"
                })
                continue

            # 4. Receipt -> Finance
            if self._is_receipt(full_context, ext):
                folder = user_selected_folder or "Finance"
                suggested = self._name_receipt(orig_name, ext, desc, snippet)
                results.append({
                    "id": f.id,
                    "original_filename": orig_name,
                    "folder": folder,
                    "category": folder,
                    "suggested_filename": suggested,
                    "reason": "Identified payment receipt/transaction confirmation; organized into Finance.",
                    "is_ambiguous": False,
                    "confidence": "high"
                })
                continue

            # 5. Report -> Work
            if self._is_report(full_context, ext):
                folder = user_selected_folder or "Work"
                suggested = self._name_report(orig_name, ext, desc, snippet)
                results.append({
                    "id": f.id,
                    "original_filename": orig_name,
                    "folder": folder,
                    "category": folder,
                    "suggested_filename": suggested,
                    "reason": "Identified project/status/annual report document; organized into Work.",
                    "is_ambiguous": False,
                    "confidence": "high"
                })
                continue

            # 6. Study Notes / Lecture / Coursework -> Study
            if self._is_study(full_context, ext):
                folder = user_selected_folder or "Study"
                suggested = self._name_study(orig_name, ext, desc, snippet)
                results.append({
                    "id": f.id,
                    "original_filename": orig_name,
                    "folder": folder,
                    "category": folder,
                    "suggested_filename": suggested,
                    "reason": "Identified lecture/coursework study notes; organized into Study.",
                    "is_ambiguous": False,
                    "confidence": "high"
                })
                continue

            # 7. Specific Work / Corporate Projects (requires explicit work project markers)
            if self._is_work(full_context, ext):
                folder = user_selected_folder or "Work"
                suggested = self._clean_suggested_name(orig_name, ext, desc, snippet, is_resume=False)
                results.append({
                    "id": f.id,
                    "original_filename": orig_name,
                    "folder": folder,
                    "category": folder,
                    "suggested_filename": suggested,
                    "reason": "Identified corporate/project roadmap document; organized into Work.",
                    "is_ambiguous": False,
                    "confidence": "high"
                })
                continue

            # 8. Images / Photos / Screenshots
            if ext in ("png", "jpg", "jpeg", "webp", "bmp", "gif"):
                folder = user_selected_folder or "Images"
                if "screenshot" in orig_name.lower():
                    results.append({
                        "id": f.id,
                        "original_filename": orig_name,
                        "folder": folder,
                        "category": folder,
                        "suggested_filename": f"UI_Screenshot.{ext}",
                        "reason": "Classified UI screenshot into Images.",
                        "is_ambiguous": False,
                        "confidence": "high"
                    })
                    continue
                # For ordinary photos or unclear images, preserve original filename
                results.append({
                    "id": f.id,
                    "original_filename": orig_name,
                    "folder": folder,
                    "category": folder,
                    "suggested_filename": orig_name,
                    "reason": "Ambiguous or ordinary visual content; preserved original filename in Images.",
                    "is_ambiguous": True,
                    "confidence": "ambiguous"
                })
                continue

            # 9. Source Code & Data Dumps
            if ext in ("py", "js", "ts", "html", "css", "json", "sql", "sh"):
                folder = user_selected_folder or "Code"
                suggested = self._clean_suggested_name(orig_name, ext, desc, snippet, is_resume=False)
                results.append({
                    "id": f.id,
                    "original_filename": orig_name,
                    "folder": folder,
                    "category": folder,
                    "suggested_filename": suggested,
                    "reason": "Classified source code or configuration into Code.",
                    "is_ambiguous": False,
                    "confidence": "high"
                })
                continue

            # 10. Ambiguous, Minimal, or Generic File -> Cautious Fallback (No hallucination!)
            if is_minimal or stem in GENERIC_STEMS:
                results.append({
                    "id": f.id,
                    "original_filename": orig_name,
                    "folder": user_selected_folder or "Documents",
                    "category": user_selected_folder or "Documents",
                    "suggested_filename": orig_name,
                    "reason": "Ambiguous or minimal content detected; retained original filename for user review.",
                    "is_ambiguous": True,
                    "confidence": "ambiguous"
                })
                continue

            # 11. General Document fallback
            folder = user_selected_folder or "Documents"
            suggested = self._clean_suggested_name(orig_name, ext, desc, snippet, is_resume=False)
            results.append({
                "id": f.id,
                "original_filename": orig_name,
                "folder": folder,
                "category": folder,
                "suggested_filename": suggested,
                "reason": "Organized into Documents based on file characteristics.",
                "is_ambiguous": False,
                "confidence": "medium"
            })

        return results

    def _is_certificate(self, text: str) -> bool:
        """
        Check if text content represents a certificate of completion, achievement, or credential.
        Handles OCR variations, formatting differences, and issuing organization cues.
        """
        t = text.lower()
        strong_cues = (
            "certificate of achievement",
            "certificate of completion",
            "certificate of participation",
            "certificate of excellence",
            "certificate of appreciation",
            "certificate of merit",
            "course certificate",
            "professional certificate",
            "specialization certificate",
            "completion certificate",
            "training certificate",
            "this is to certify that",
            "this is to certify",
            "certifies that",
            "certify that",
            "has successfully completed",
            "successfully completed",
            "completion of the course",
            "completed the course",
            "for successfully completing",
            "for completing the course",
            "is hereby awarded",
            "awarded to",
            "presented to",
            "in recognition of",
            "has completed the requirements",
            "has met all requirements",
        )
        if any(cue in t for cue in strong_cues):
            return True

        # Recognized certificate programs or issuers
        if any(k in t for k in ("tcs ion", "tcs-ion", "tcsion", "tosion", "career edge")):
            if any(w in t for w in ("certificate", "certify", "completed", "completion", "course", "edge")):
                return True

        if any(k in t for k in ("h2h", "highradius", "high radius")):
            if any(w in t for w in ("certificate", "certification", "completed", "completion", "training", "course", "internship", "awarded")):
                return True

        if "certificate" in t and any(w in t for w in ("completed", "completion", "cert id", "credential id", "course", "passed", "awarded", "verify")):
            return True

        return False

    def _name_certificate(self, orig_name: str, ext: str, desc: str, snippet: str) -> Optional[str]:
        """
        Suggest a clean, evidence-based certificate filename such as
        TCS-iON-Career-Edge-Certificate.pdf, H2H-Certificate.pdf, or Certificate.pdf.
        Strictly relies on identifiable evidence; never invents organizations or course names.
        """
        if ext.lower() in ("png", "jpg", "jpeg", "webp", "bmp", "gif"):
            # For image files, OCR text in snippet must explicitly verify certificate content.
            # Filename or image EXIF metadata alone NEVER justifies labeling an image as a certificate.
            if not snippet or not self._is_certificate(snippet) or "visual classification" in snippet.lower():
                return None

        full_text = f"{desc}\n{snippet}"
        if not self._is_certificate(full_text):
            return None

        t_lower = full_text.lower()
        target_ext = ext if ext else "pdf"

        # 1. Detect Issuing Organization from content evidence
        org: Optional[str] = None
        if any(k in t_lower for k in ("tcs ion", "tcs-ion", "tcsion", "tosion", "tcs iön", "tata consultancy services")):
            org = "TCS-iON"
        elif any(k in t_lower for k in ("h2h", "h 2 h", "h-2-h", "highradius", "high radius")):
            org = "H2H"
        elif "scrapeverse" in t_lower:
            org = "ScrapeVerse"
        elif "coursera" in t_lower:
            org = "Coursera"
        elif "udemy" in t_lower:
            org = "Udemy"
        elif "edx" in t_lower:
            org = "edX"
        elif "google cloud" in t_lower:
            org = "Google-Cloud"
        elif "google" in t_lower:
            org = "Google"
        elif "aws" in t_lower or "amazon web services" in t_lower:
            org = "AWS"
        elif "microsoft" in t_lower:
            org = "Microsoft"
        elif "stanford" in t_lower:
            org = "Stanford"
        elif "harvard" in t_lower:
            org = "Harvard"
        elif "mit" in t_lower:
            org = "MIT"
        elif "deeplearning.ai" in t_lower:
            org = "DeepLearning.AI"
        elif "ibm" in t_lower:
            org = "IBM"
        elif "hackerrank" in t_lower:
            org = "HackerRank"
        elif "leetcode" in t_lower:
            org = "LeetCode"
        elif "simplilearn" in t_lower:
            org = "Simplilearn"
        elif "upgrad" in t_lower:
            org = "upGrad"
        elif "nptel" in t_lower:
            org = "NPTEL"
        else:
            m_org = re.search(
                r'(?:issued by|offered by|authorized by|academy|organization)[:\s]+([A-Za-z0-9\s&]{2,30}?)(?:\n|\.|\,|$)',
                full_text,
                re.IGNORECASE
            )
            if m_org:
                c_org = m_org.group(1).strip()
                if c_org and len(c_org.split()) <= 3 and not any(k in c_org.lower() for k in ("certificate", "completion", "date", "id", "this", "that")):
                    org = re.sub(r'[\s_]+', '-', c_org).strip('-')

        # 2. Detect Course or Program Name from content evidence
        course: Optional[str] = None
        if "career edge" in t_lower:
            course = "Career-Edge"
        elif "web scraping" in t_lower:
            course = "Web-Scraping"
        elif "machine learning" in t_lower:
            course = "Machine-Learning"
        elif "data science" in t_lower:
            course = "Data-Science"
        elif "python" in t_lower and ("programming" in t_lower or "course" in t_lower or "for beginners" in t_lower):
            course = "Python-Programming"
        elif "fintech" in t_lower or "financial technology" in t_lower:
            course = "Fintech"
        else:
            m_course = re.search(
                r'(?:completing|completed|completion of|course in|course on|specialization in|training in)\s+(?:the\s+)?([A-Za-z0-9\s:&–—\-]{3,60}?)(?:\s+(?:course|training|specialization|program|curriculum|on\s+[A-Z0-9]|dated|\n|$))',
                full_text,
                re.IGNORECASE
            )
            if m_course:
                raw_course = m_course.group(1).strip()
                if org:
                    clean_org_text = org.replace('-', ' ')
                    raw_course = re.sub(re.escape(clean_org_text), '', raw_course, flags=re.IGNORECASE)
                    raw_course = re.sub(r'^(?:tcs|ion|h2h|scrapeverse|coursera|udemy)\s*', '', raw_course, flags=re.IGNORECASE)
                raw_course = re.sub(r'[\s:–—\-]+', ' ', raw_course).strip(' :–—-\t\n')
                words = [w for w in raw_course.split() if w.lower() not in ("that", "which", "cover", "covers", "and", "the", "a", "an", "for", "with")]
                if words and len(words) <= 4:
                    course = '-'.join(w.capitalize() for w in words[:3])

        # 3. Assemble descriptive filename strictly supported by evidence
        parts = []
        if org:
            parts.append(org)
        if course:
            if not any(course.lower() in p.lower() for p in parts):
                parts.append(course)
        parts.append("Certificate")

        if len(parts) > 1:
            return f"{'-'.join(parts)}.{target_ext}"

        if "achievement" in t_lower:
            return f"Certificate-of-Achievement.{target_ext}"
        if "completion" in t_lower:
            return f"Certificate-of-Completion.{target_ext}"
        if "participation" in t_lower:
            return f"Certificate-of-Participation.{target_ext}"

        # If neither org, course, nor specific heading could be identified, do NOT invent course or issuer
        return f"Certificate.{target_ext}"

    def _is_resume(self, text: str) -> bool:
        """
        Check if text content represents a resume or curriculum vitae.
        Handles standard section headings with or without colons.
        """
        t = text.lower()
        if "curriculum vitae" in t or "resume" in t or "c.v." in t:
            return True

        # Check for standard resume sections
        section_cues = (
            "professional summary", "career summary", "executive summary",
            "work experience", "professional experience", "employment history", "experience",
            "education", "academic background", "academic history",
            "technical skills", "core competencies", "skills & abilities", "skills"
        )
        matches = sum(1 for cue in section_cues if cue in t)
        return matches >= 2

    def _is_invoice(self, text: str, ext: str) -> bool:
        """Check for financial invoice content."""
        return self._is_financial(text, ext)

    def _is_receipt(self, text: str, ext: str) -> bool:
        """Check for payment receipt or transaction confirmation."""
        t = text.lower()
        receipt_keywords = (
            "receipt #", "receipt no", "payment received", "total paid",
            "cashier", "transaction receipt", "payment confirmation",
            "order receipt", "sales receipt", "merchant", "amount charged",
            "card ending in", "payment method"
        )
        return any(kw in t for kw in receipt_keywords)

    def _name_receipt(self, orig_name: str, ext: str, desc: str, snippet: str) -> str:
        t = f"{desc} {snippet}".lower()
        target_ext = ext if ext else "pdf"
        for merchant in ("uber", "amazon", "apple", "starbucks", "walmart", "target", "lyft", "stripe", "paypal"):
            if merchant in t:
                return f"{merchant.title()}-Receipt.{target_ext}"
        return f"Receipt.{target_ext}"

    def _is_report(self, text: str, ext: str) -> bool:
        """Check for formal project, quarterly, annual, or status reports."""
        t = text.lower()
        report_keywords = (
            "project report", "annual report", "quarterly report", "status report",
            "audit report", "research report", "evaluation report", "progress report",
            "technical report", "final report", "executive summary"
        )
        return any(kw in t for kw in report_keywords)

    def _name_report(self, orig_name: str, ext: str, desc: str, snippet: str) -> str:
        t = f"{desc} {snippet}".lower()
        target_ext = ext if ext else "pdf"
        for topic in ("annual", "quarterly", "project", "audit", "research", "status", "progress"):
            if topic in t:
                return f"{topic.title()}-Report.{target_ext}"
        return f"Report.{target_ext}"

    def _is_financial(self, text: str, ext: str) -> bool:
        """Check for financial, invoice, or tax content."""
        t = text.lower()
        fin_keywords = (
            "invoice", "bill to", "amount due", "payment due", "total due",
            "subtotal", "tax invoice", "statement of account", "tax return",
            "form w-2", "w-2", "w2", "1099-misc", "1099", "irs", "transactionid",
            "transaction id", "ledger"
        )
        return any(kw in t for kw in fin_keywords)

    def _is_study(self, text: str, ext: str) -> bool:
        """Check for study, course, or lecture notes."""
        t = text.lower()
        study_keywords = (
            "study notes", "lecture notes", "coursework", "syllabus",
            "homework", "lecture", "cs50", "chapter", "exam prep",
            "binary search", "data structures", "algorithms"
        )
        return any(kw in t for kw in study_keywords)

    def _is_work(self, text: str, ext: str) -> bool:
        """
        Check for explicit corporate/project planning content.
        Requires multi-word corporate phrases to prevent false positives on resumes.
        """
        t = text.lower()
        work_markers = (
            "meeting minutes", "sprint planning", "sprint retrospective",
            "project roadmap", "quarterly business review", "statement of work",
            "scope of work", "q4 roadmap", "q3 roadmap", "product roadmap"
        )
        return any(marker in t for marker in work_markers)

    def _detect_shared_project(self, files: List[FileMetadata]) -> Optional[str]:
        """Detect shared project prefix or name across mixed upload files."""
        if len(files) < 2:
            return None
        names = [f.filename.lower() for f in files]
        for candidate in ("apollo", "roadmap", "tax_2023", "hackathon"):
            count = sum(1 for n in names if candidate in n)
            if count >= 2:
                return candidate.replace("_", " ").title()
        return None

    def _name_financial(self, orig_name: str, ext: str, desc: str, snippet: str) -> str:
        context = f"{desc} {snippet}".lower()
        if "w-2" in context or "w2" in context or "tax return" in context:
            return f"Tax_Return.{ext}" if ext else "Tax_Return.pdf"
        if "invoice" in context or "bill" in context:
            return f"Invoice.{ext}" if ext else "Invoice.pdf"
        if "transactionid" in context or "ledger" in context:
            return f"Financial_Transactions.{ext}" if ext else "Financial_Transactions.csv"
        return f"Financial_Document.{ext}" if ext else "Financial_Document.pdf"

    def _name_study(self, orig_name: str, ext: str, desc: str, snippet: str) -> str:
        return f"Study-Notes.{ext}" if ext else "Study-Notes.docx"

    def _name_image(self, orig_name: str, ext: str, desc: str, snippet: str) -> str:
        """
        For ordinary photos or unclear images, preserve the original filename
        when a meaningful rename cannot be justified.
        """
        target_ext = ext if ext else "jpg"
        if desc:
            clean_desc = re.sub(r"[^\w\s-]", "", desc).strip().replace(" ", "_")
            if clean_desc:
                return f"{clean_desc}.{target_ext}"
        if "screenshot" in orig_name.lower():
            return f"UI_Screenshot.{target_ext}"
        # For ordinary photos or unclear images, preserve the original filename
        return orig_name

    def _clean_suggested_name(self, orig_name: str, ext: str, desc: str, snippet: str, is_resume: bool = False) -> str:
        if is_resume:
            return f"Resume.{ext}" if ext else "Resume.pdf"
        if desc:
            clean = re.sub(r"[^\w\s-]", "", desc).strip().replace(" ", "_")
            if clean:
                return f"{clean}.{ext}"
        base = orig_name.rsplit(".", 1)[0]
        if base.lower() in GENERIC_STEMS:
            return orig_name
        cleaned = re.sub(r"[_\-\.]+", " ", base).strip().title().replace(" ", "_")
        return f"{cleaned}.{ext}" if cleaned else orig_name


ai_organizer = AIOrganizerService()
