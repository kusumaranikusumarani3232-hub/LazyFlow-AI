import pytest
from app.utils.sanitizer import sanitize_filename, sanitize_folder_name, resolve_duplicate_names

def test_sanitize_filename_traversal():
    dirty = "../../../secret_passwords.txt"
    clean = sanitize_filename(dirty)
    assert "/" not in clean
    assert ".." not in clean
    assert clean.endswith(".txt")
    assert "secret-passwords.txt" in clean or "passwords.txt" in clean

def test_sanitize_filename_illegal_chars():
    dirty = 'my*invoice:final<v2>?".pdf'
    clean = sanitize_filename(dirty)
    for char in [':', '*', '?', '"', '<', '>', '|']:
        assert char not in clean
    assert clean.endswith(".pdf")

def test_sanitize_filename_reserved_windows_name():
    dirty = "CON.pdf"
    clean = sanitize_filename(dirty)
    assert clean.upper() != "CON.PDF"
    assert "CON-doc" in clean
    assert clean.endswith(".pdf")

def test_sanitize_filename_preserves_extension():
    # If suggested filename omitted extension, original extension must be restored
    clean = sanitize_filename("clean-report-name", original_name="messy_scan.docx")
    assert clean == "clean-report-name.docx"

def test_sanitize_folder_name():
    assert sanitize_folder_name("Documents") == "Documents"
    assert sanitize_folder_name("../../Finance") == "Finance"
    assert sanitize_folder_name("Work/Projects") == "Work_Projects"
    assert sanitize_folder_name("") == "Other"
    assert sanitize_folder_name("   ") == "Other"
    assert sanitize_folder_name("NUL") == "Folder_NUL"

def test_resolve_duplicate_names():
    items = [
        {"id": "1", "folder": "Finance", "suggested_filename": "invoice.pdf"},
        {"id": "2", "folder": "Finance", "suggested_filename": "invoice.pdf"},
        {"id": "3", "folder": "Finance", "suggested_filename": "invoice.pdf"},
        {"id": "4", "folder": "Work", "suggested_filename": "invoice.pdf"}  # different folder
    ]
    resolved = resolve_duplicate_names(items)
    
    assert resolved[0]["suggested_filename"] == "invoice.pdf"
    assert resolved[1]["suggested_filename"] == "invoice (1).pdf"
    assert resolved[2]["suggested_filename"] == "invoice (2).pdf"
    assert resolved[3]["suggested_filename"] == "invoice.pdf"  # in Work folder, so unchanged
