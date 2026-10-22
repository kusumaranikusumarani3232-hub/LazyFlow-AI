import io
import hashlib
import zipfile
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.zip_service import zip_service
from app.utils.sample_fixtures import (
    create_valid_pdf,
    create_valid_png,
    create_valid_pptx,
    create_valid_docx,
    create_valid_csv,
)

client = TestClient(app)

def test_full_upload_zip_content_sha256_integrity(tmp_path, monkeypatch):
    """
    Requirement 8 & 9:
    Upload real fixtures (valid PDF, PNG image, PPTX, DOCX, CSV).
    Generate the ZIP, extract the files, and compare each extracted file's
    SHA-256 hash with its original uploaded file's hash.
    All hashes must match exactly.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    # 1. Create real test fixtures
    fixtures = {
        "monthly_invoice_2023.pdf": (create_valid_pdf("Annual Cloud Infrastructure Invoice"), "application/pdf"),
        "screenshot_ui_bug.png": (create_valid_png(), "image/png"),
        "q4_team_roadmap.pptx": (create_valid_pptx("Quarterly Goals Presentation"), "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        "cs50_algorithms_notes.docx": (create_valid_docx("CS50 Week 3", "Binary search and sorting algorithms."), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        "financial_ledger_export.csv": (create_valid_csv(), "text/csv"),
    }

    # Pre-compute original SHA-256 hashes
    original_hashes = {
        name: hashlib.sha256(data).hexdigest()
        for name, (data, _) in fixtures.items()
    }

    # 2. Upload via multipart form
    upload_files = [
        ("files", (name, data, mime))
        for name, (data, mime) in fixtures.items()
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"custom_categories": "Finance,Study,Work,Images,Documents"}
    )
    assert response.status_code == 200, f"Upload failed: {response.text}"
    org_data = response.json()
    session_id = org_data["session_id"]
    items = org_data["items"]
    assert len(items) == len(fixtures)
    assert session_id is not None

    # Verify session manifest was written
    session_dir = zip_service.get_session_dir(session_id)
    manifest = zip_service._load_manifest(session_dir)
    assert len(manifest) == len(fixtures)

    # 3. Request organized ZIP download
    download_res = client.post(
        "/api/download-zip",
        json={"session_id": session_id, "items": items}
    )
    assert download_res.status_code == 200
    assert download_res.headers["content-type"] == "application/zip"

    # 4. Open and extract files from ZIP
    zip_bytes = download_res.content
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()
        assert len(namelist) == len(fixtures)

        # Map each approved item to its arcname in the ZIP
        for item in items:
            folder = item["folder"]
            suggested_name = item["suggested_filename"]
            orig_name = item["original_filename"]
            expected_arcname = f"{folder}/{suggested_name}"

            assert expected_arcname in namelist, f"Expected '{expected_arcname}' in ZIP, but found: {namelist}"

            # Read extracted bytes
            extracted_bytes = zf.read(expected_arcname)
            extracted_hash = hashlib.sha256(extracted_bytes).hexdigest()
            orig_hash = original_hashes[orig_name]

            # Byte-for-byte SHA-256 hash comparison
            assert extracted_hash == orig_hash, (
                f"SHA-256 mismatch for {orig_name} (saved as {expected_arcname})! "
                f"Original: {orig_hash}, Extracted: {extracted_hash}"
            )

            # File format-specific valid header verification
            if orig_name.endswith(".pdf"):
                assert extracted_bytes.startswith(b"%PDF-1.4")
                assert b"%%EOF" in extracted_bytes
            elif orig_name.endswith(".png"):
                assert extracted_bytes.startswith(b"\x89PNG\r\n\x1a\n")
            elif orig_name.endswith(".pptx") or orig_name.endswith(".docx"):
                assert zipfile.is_zipfile(io.BytesIO(extracted_bytes))
            elif orig_name.endswith(".csv"):
                assert b"TransactionID" in extracted_bytes

    # Cleanup session
    zip_service.cleanup_session(session_id)
    assert not session_dir.exists()


def test_zip_integrity_with_renaming_and_exclusions(tmp_path, monkeypatch):
    """
    Test that when user renames files or excludes files:
    - Excluded files are omitted from the ZIP archive completely.
    - Included and renamed files preserve their exact original binary bytes and SHA-256 hashes.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    pdf_bytes = create_valid_pdf("Important Tax Document")
    png_bytes = create_valid_png()
    csv_bytes = create_valid_csv()

    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    csv_hash = hashlib.sha256(csv_bytes).hexdigest()

    upload_files = [
        ("files", ("tax_doc.pdf", pdf_bytes, "application/pdf")),
        ("files", ("photo.png", png_bytes, "image/png")),
        ("files", ("ledger.csv", csv_bytes, "text/csv")),
    ]

    response = client.post("/api/upload-and-organize", files=upload_files)
    assert response.status_code == 200
    data = response.json()
    session_id = data["session_id"]
    items = data["items"]

    # Exclude photo.png and customize name of tax_doc.pdf
    for item in items:
        if item["original_filename"] == "photo.png":
            item["excluded"] = True
        elif item["original_filename"] == "tax_doc.pdf":
            item["suggested_filename"] = "custom-renamed-tax-2023.pdf"
            item["folder"] = "CustomTaxes"

    download_res = client.post(
        "/api/download-zip",
        json={"session_id": session_id, "items": items}
    )
    assert download_res.status_code == 200

    with zipfile.ZipFile(io.BytesIO(download_res.content), "r") as zf:
        namelist = zf.namelist()
        # Photo must be completely excluded
        for name in namelist:
            assert "photo.png" not in name

        # Tax doc must exist with custom name and exact original bytes
        assert "CustomTaxes/custom-renamed-tax-2023.pdf" in namelist
        extracted_pdf = zf.read("CustomTaxes/custom-renamed-tax-2023.pdf")
        assert hashlib.sha256(extracted_pdf).hexdigest() == pdf_hash

        # Ledger must match original bytes
        ledger_entry = [n for n in namelist if n.endswith(".csv")][0]
        extracted_csv = zf.read(ledger_entry)
        assert hashlib.sha256(extracted_csv).hexdigest() == csv_hash

    zip_service.cleanup_session(session_id)


def test_missing_file_rejected_without_fakes(tmp_path, monkeypatch):
    """
    Requirement 6:
    Verify bytes exist before writing entry; return a clear error
    if a file is missing instead of generating a fake file.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)
    session_id = "test_missing_file_session"

    session_dir = zip_service.get_session_dir(session_id)
    raw_dir = session_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    items = [
        {
            "id": "f_missing_999",
            "original_filename": "non_existent.pdf",
            "folder": "Documents",
            "category": "Documents",
            "suggested_filename": "non_existent.pdf",
            "reason": "Test missing",
            "excluded": False,
            "user_modified": False
        }
    ]

    response = client.post(
        "/api/download-zip",
        json={"session_id": session_id, "items": items}
    )
    # Must fail with 400 Bad Request indicating the file is missing
    assert response.status_code == 400
    assert "could not be found" in response.json()["detail"]
