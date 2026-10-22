import os
import re
from pathlib import Path
from typing import List, Dict, Any

# Windows reserved device names
RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}

# Dangerous characters for files and directories
ILLEGAL_CHARS_PATTERN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

def sanitize_folder_name(folder: str, default: str = "Other") -> str:
    """
    Sanitize folder name to prevent path traversal and illegal filesystem characters.
    Disallows directory traversal, leading dots, and reserved names.
    Flattens subdirectories with underscores (e.g. Work/Projects -> Work_Projects).
    """
    if not folder or not folder.strip():
        return default
    
    clean = folder.replace("\\", "/").strip()
    # Remove traversal segments like '..' or '.'
    parts = [p.strip() for p in clean.split("/") if p.strip() and p.strip() not in (".", "..")]
    if not parts:
        return default

    # Join remaining safe parts with underscore
    clean = "_".join(parts)

    # Strip illegal characters
    clean = ILLEGAL_CHARS_PATTERN.sub("_", clean).strip()
    
    # Remove leading/trailing dots or underscores
    clean = clean.strip(". _-")
    
    # Collapse multiple spaces or underscores
    clean = re.sub(r'[\s]+', ' ', clean)
    clean = re.sub(r'_+', '_', clean).strip()
    
    # Disallow empty or traversal names
    if not clean or clean in (".", ".."):
        return default
        
    # Check reserved device names
    base_upper = clean.upper()
    if base_upper in RESERVED_NAMES:
        clean = f"Folder_{clean}"
        
    # Limit folder length
    return clean[:60] if len(clean) > 60 else clean


def sanitize_filename(name: str, original_name: str = "") -> str:
    """
    Sanitize a filename while preserving its valid extension.
    Guarantees no directory separators, no reserved words, and clean characters.
    """
    if not name or not name.strip():
        name = original_name or "unnamed_file"

    # Normalize slashes and take basename only to prevent directory traversal
    name = name.replace("\\", "/").split("/")[-1].strip()

    # Separate stem and extension
    path_obj = Path(name)
    stem = path_obj.stem
    ext = path_obj.suffix

    # If suggested filename lost extension, restore original's extension
    if not ext and original_name:
        orig_ext = Path(original_name).suffix
        if orig_ext:
            ext = orig_ext

    # Clean illegal characters (preserve underscores and letters/numbers)
    clean_stem = ILLEGAL_CHARS_PATTERN.sub("-", stem).strip()
    # Normalize spaces to hyphens or underscores, collapse consecutive dashes
    clean_stem = re.sub(r'[\s]+', '-', clean_stem)
    clean_stem = re.sub(r'-{2,}', '-', clean_stem)
    clean_stem = clean_stem.strip(".- ")
    
    if not clean_stem:
        clean_stem = "file"

    # Check for reserved name
    if clean_stem.upper() in RESERVED_NAMES:
        clean_stem = f"{clean_stem}-doc"

    # Sanitize extension
    clean_ext = ILLEGAL_CHARS_PATTERN.sub("", ext).lower().strip()
    if clean_ext and not clean_ext.startswith("."):
        clean_ext = f".{clean_ext}"

    # Limit stem length so total filename is <= 150 chars
    max_stem_len = 150 - len(clean_ext)
    clean_stem = clean_stem[:max_stem_len]

    return f"{clean_stem}{clean_ext}"


def resolve_duplicate_names(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Given a list of items having 'folder' and 'suggested_filename',
    ensure no two items in the same folder share the exact same filename.
    Appends ' (1)', ' (2)', etc. before extension if duplicates exist.
    """
    seen_in_folder: Dict[str, Dict[str, int]] = {}
    resolved_items = []

    for item in items:
        item_copy = dict(item)
        folder = item_copy.get("folder", "Other")
        filename = item_copy.get("suggested_filename", "unnamed_file")

        if folder not in seen_in_folder:
            seen_in_folder[folder] = {}

        name_lower = filename.lower()
        if name_lower in seen_in_folder[folder]:
            seen_in_folder[folder][name_lower] += 1
            count = seen_in_folder[folder][name_lower]
            
            p = Path(filename)
            stem, ext = p.stem, p.suffix
            new_filename = f"{stem} ({count}){ext}"
            item_copy["suggested_filename"] = new_filename
        else:
            seen_in_folder[folder][name_lower] = 0

        resolved_items.append(item_copy)

    return resolved_items
