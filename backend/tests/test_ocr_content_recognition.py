import hashlib
import io
import os
import tempfile
import zipfile
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ocr_service import ocr_service
from app.services.content_extractor import content_extractor
from app.services.ai_organizer import ai_organizer
from app.services.zip_service import zip_service
from app.utils.sample_fixtures import (
    create_valid_pdf,
    create_image_with_text,
    create_scanned_pdf,
)

client = TestClient(app)


def test_ocr_engine_available_and_reports_status():
    """Verify OCR engine initializes and reports status correctly."""
    assert ocr_service.is_available() is True
    info = ocr_service.get_engine_info()
    assert info["available"] is True
    assert info["engine"] == "tesseract"
    assert info["version"] is not None


def test_ocr_text_normalization():
    """Verify Unicode ligatures, line breaks, and whitespace are normalized."""
    messy_text = "Certi\ufb01cate of\n  Completion\n\n\n\nThis is to certify that John Doe has success-\nfully completed the course."
    clean = ocr_service.normalize_text(messy_text)
    assert "Certificate of" in clean
    assert "successfully" in clean  # Re-joined hyphenated line break
    assert "\ufb01" not in clean


def test_ocr_directly_on_certificate_image():
    """Verify OCR extracts text directly from PNG and JPEG certificate images."""
    cert_text = (
        "Certificate of Completion\n"
        "TCS iON Career Edge - Knockdown the Lockdown\n"
        "This is to certify that Alex Morgan has successfully completed\n"
        "Course in Career Edge\n"
        "Date: 15-Oct-2023"
    )
    png_bytes = create_image_with_text(cert_text, width=900, height=450, format="PNG")

    ocr_res = ocr_service.ocr_image(png_bytes, filename="tcs_cert.png")
    assert ocr_res["success"] is True
    extracted = ocr_res["text"].lower()

    # Verify actual extracted words
    assert "career edge" in extracted
    assert "certificate" in extracted
    assert ocr_res["char_count"] >= 30


def test_content_extractor_image_certificate():
    """Verify ContentExtractor runs OCR on image files and returns image_ocr content_type."""
    cert_text = (
        "Certificate of Completion\n"
        "H2H Certification\n"
        "Awarded to Jordan Smith for completing Fintech Training Program\n"
        "Issued by H2H Academy"
    )
    png_bytes = create_image_with_text(cert_text, width=900, height=450, format="PNG")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tf.write(png_bytes)
        tf_path = tf.name

    try:
        res = content_extractor.extract_file_content(tf_path, "upload_cert.png", "image/png")
        assert res["has_content"] is True
        assert res["content_type"] == "image_ocr"
        assert "h2h" in res["content_snippet"].lower()
        assert res["extracted_metadata"]["ocr_used"] is True
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)


def test_content_extractor_scanned_pdf_certificate():
    """Verify ContentExtractor renders scanned PDF pages to images and runs OCR when text is absent."""
    cert_text = (
        "Certificate of Completion\n"
        "TCS iON Career Edge\n"
        "This is to certify that Morgan Lee has successfully completed the program"
    )
    scanned_pdf_bytes = create_scanned_pdf(cert_text, width=900, height=500)

    # First verify standard PDF extractors find zero text in this scanned document
    import fitz
    doc = fitz.open(stream=scanned_pdf_bytes, filetype="pdf")
    embedded_text = doc[0].get_text()
    doc.close()
    assert embedded_text.strip() == "", "Scanned PDF should not have extractable text stream"

    # Now verify ContentExtractor triggers OCR and reads visual text
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(scanned_pdf_bytes)
        tf_path = tf.name

    try:
        res = content_extractor.extract_file_content(tf_path, "scanned_doc.pdf", "application/pdf")
        assert res["has_content"] is True
        assert res["content_type"] == "pdf_scanned_ocr"
        assert "career edge" in res["content_snippet"].lower()
        assert res["extracted_metadata"]["ocr_used"] is True
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)


def test_normal_text_pdf_does_not_require_ocr():
    """Verify normal PDFs with embedded text use direct parser without unnecessary OCR."""
    normal_pdf = create_valid_pdf(
        "Quarterly Business Report",
        ["Financial results for Q3", "Revenue: $1.2M", "Operating margin: 24%"]
    )
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(normal_pdf)
        tf_path = tf.name

    try:
        res = content_extractor.extract_file_content(tf_path, "report.pdf", "application/pdf")
        assert res["has_content"] is True
        assert res["content_type"] == "pdf_text"
        assert res["extracted_metadata"]["ocr_used"] is False
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)


def test_end_to_end_tcs_ion_scanned_pdf_recognition(tmp_path, monkeypatch):
    """
    Requirement 3:
    Upload scanned PDF certificate -> Suggests TCS-iON-Career-Edge-Certificate.pdf in Career folder.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    cert_text = (
        "Certificate of Completion\n"
        "TCS iON Career Edge - Knockdown the Lockdown\n"
        "This is to certify that Candidate Name has successfully completed the course\n"
        "Date of completion: 15-May-2023"
    )
    pdf_bytes = create_scanned_pdf(cert_text, width=900, height=500)

    upload_files = [
        ("files", ("scan_001.pdf", pdf_bytes, "application/pdf")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["items"]) == 1

    item = data["items"][0]
    assert item["original_filename"] == "scan_001.pdf"
    assert item["folder"].lower() == "career"
    assert "tcs-ion" in item["suggested_filename"].lower()
    assert "career-edge" in item["suggested_filename"].lower()
    assert item["suggested_filename"].endswith(".pdf")
    assert item["is_ambiguous"] is False


def test_end_to_end_h2h_image_certificate_recognition(tmp_path, monkeypatch):
    """
    Requirement 3:
    Upload H2H image certificate -> Uses actual course/organization identified by OCR in Career folder.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    cert_text = (
        "Certificate of Completion\n"
        "H2H Certification\n"
        "Awarded to John Doe for completing Fintech Program\n"
        "HighRadius H2H"
    )
    png_bytes = create_image_with_text(cert_text, width=900, height=450, format="PNG")

    upload_files = [
        ("files", ("IMG_20230501.png", png_bytes, "image/png")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["items"]) == 1

    item = data["items"][0]
    assert item["original_filename"] == "IMG_20230501.png"
    assert item["folder"].lower() == "career"
    assert "h2h" in item["suggested_filename"].lower()
    assert "certificate" in item["suggested_filename"].lower()
    assert item["suggested_filename"].endswith(".png")
    assert item["is_ambiguous"] is False


def test_unidentifiable_certificate_fallback(tmp_path, monkeypatch):
    """
    Requirement 3:
    Unidentifiable certificate -> Certificate.pdf, without inventing a course or issuer.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    # Contains certificate language but completely unidentifiable organization and course
    generic_cert_text = (
        "Certificate of Training\n"
        "This is to certify that Participant Name has completed the requirements\n"
        "Authorized Signature"
    )
    pdf_bytes = create_scanned_pdf(generic_cert_text, width=900, height=500)

    upload_files = [
        ("files", ("unnamed_file.pdf", pdf_bytes, "application/pdf")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    item = data["items"][0]
    assert item["folder"].lower() == "career"
    assert item["suggested_filename"] == "Certificate.pdf"
    assert item["is_ambiguous"] is False


def test_preserve_user_selected_destination_folder(tmp_path, monkeypatch):
    """
    Requirement 3:
    Preserve the user's selected destination folder (e.g. 'Career' or custom) while refining filename.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    cert_text = (
        "Certificate of Completion\n"
        "TCS iON Career Edge\n"
        "Successfully completed by Student"
    )
    pdf_bytes = create_scanned_pdf(cert_text, width=900, height=500)

    upload_files = [
        ("files", ("my_cert.pdf", pdf_bytes, "application/pdf")),
    ]

    # User specifies custom destination folder "Professional Credentials"
    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true", "custom_categories": "Professional Credentials"}
    )
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["folder"] == "Professional Credentials"
    assert "tcs-ion" in item["suggested_filename"].lower()


def test_ambiguous_document_retains_original_filename(tmp_path, monkeypatch):
    """
    Requirement 4:
    If a file has ambiguous or minimal content, retain the original filename honestly.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    blank_pdf = create_scanned_pdf("", width=600, height=400)

    upload_files = [
        ("files", ("scan.pdf", blank_pdf, "application/pdf")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["is_ambiguous"] is True
    assert item["suggested_filename"] == "scan.pdf"
    assert "ambiguous" in item["reason"].lower() or "minimal" in item["reason"].lower()


def test_ocr_failure_fallback_honesty(tmp_path, monkeypatch):
    """
    Requirement 2 & 4:
    If OCR fails or is unavailable, report honestly and retain original filename without inventing content.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    # Force OCR failure
    def mock_ocr_image(*args, **kwargs):
        return {"success": False, "text": "", "error": "Simulated OCR Engine Failure", "char_count": 0}

    monkeypatch.setattr(ocr_service, "ocr_image", mock_ocr_image)

    cert_text = "Certificate of Completion TCS iON"
    png_bytes = create_image_with_text(cert_text, width=600, height=300)

    upload_files = [
        ("files", ("generic_photo.png", png_bytes, "image/png")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    # When OCR fails, original filename is retained or file is safely classified as Images
    assert item["suggested_filename"] == "generic_photo.png" or item["folder"] == "Images"


def test_file_integrity_preserved_in_zip(tmp_path, monkeypatch):
    """
    Requirement 4:
    Preserve original file bytes in downloaded ZIP. OCR must not alter uploaded files.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    original_bytes = create_scanned_pdf("Certificate of Completion TCS iON Career Edge", width=600, height=300)
    original_hash = hashlib.sha256(original_bytes).hexdigest()

    upload_files = [
        ("files", ("my_certificate.pdf", original_bytes, "application/pdf")),
    ]

    upload_res = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    session_id = upload_data["session_id"]
    items = upload_data["items"]

    # Download organized ZIP
    zip_res = client.post(
        "/api/download-zip",
        json={"session_id": session_id, "items": items}
    )
    assert zip_res.status_code == 200

    # Inspect ZIP content
    with zipfile.ZipFile(io.BytesIO(zip_res.content), "r") as zf:
        namelist = zf.namelist()
        assert len(namelist) == 1
        stored_bytes = zf.read(namelist[0])
        stored_hash = hashlib.sha256(stored_bytes).hexdigest()

        # SHA-256 hash must be identical to the uploaded bytes
        assert stored_hash == original_hash, "Original file bytes were altered by processing!"


def test_end_to_end_tcs_ion_jpeg_image_certificate_recognition(tmp_path, monkeypatch):
    """
    Requirement 1:
    A clearly recognized TCS iON Career Edge JPEG certificate becomes TCS-iON-Career-Edge-Certificate.jpeg
    in the Career folder while preserving the original .jpeg extension.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    cert_text = (
        "Certificate of Completion\n"
        "TCS iON Career Edge - Knockdown the Lockdown\n"
        "This is to certify that Jordan Lee has successfully completed the course\n"
        "Date: 20-Oct-2023"
    )
    jpeg_bytes = create_image_with_text(cert_text, width=900, height=450, format="JPEG")

    upload_files = [
        ("files", ("my_certificate.jpeg", jpeg_bytes, "image/jpeg")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    item = data["items"][0]

    assert item["original_filename"] == "my_certificate.jpeg"
    assert item["folder"] == "Career"
    assert item["suggested_filename"] == "TCS-iON-Career-Edge-Certificate.jpeg"
    assert item["suggested_filename"].endswith(".jpeg")
    assert item["is_ambiguous"] is False


def test_ordinary_photo_preserves_original_filename_into_images(tmp_path, monkeypatch):
    """
    Requirement 1 & 2:
    For ordinary photos or unclear images without readable text, preserve the original filename
    and organize into Images folder.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    # An ordinary photo (white canvas with no text)
    photo_bytes = create_image_with_text("", width=800, height=600, format="JPEG")

    upload_files = [
        ("files", ("IMG_20231012_WA0004.jpg", photo_bytes, "image/jpeg")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    item = data["items"][0]

    assert item["original_filename"] == "IMG_20231012_WA0004.jpg"
    assert item["folder"] == "Images"
    assert item["suggested_filename"] == "IMG_20231012_WA0004.jpg"


def test_dynamic_zip_download_career_and_study_end_to_end(tmp_path, monkeypatch):
    """
    Requirement 3:
    Download ZIP containing Career and Study files -> Career_and_Study_Files.zip.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    cert_bytes = create_valid_pdf("Certificate of Completion", ["Course Certificate"])
    notes_bytes = create_valid_pdf("Lecture Notes", ["CS50 Study Notes and Data Structures"])

    upload_files = [
        ("files", ("cert.pdf", cert_bytes, "application/pdf")),
        ("files", ("notes.pdf", notes_bytes, "application/pdf")),
    ]

    org_res = client.post("/api/upload-and-organize", files=upload_files)
    assert org_res.status_code == 200
    org_data = org_res.json()
    session_id = org_data["session_id"]
    items = org_data["items"]

    # Assign Career and Study
    items[0]["folder"] = "Career"
    items[1]["folder"] = "Study"

    dl_res = client.post(
        "/api/download-zip",
        json={"session_id": session_id, "items": items}
    )
    assert dl_res.status_code == 200
    disposition = dl_res.headers.get("content-disposition", "")
    assert 'filename="Career_and_Study_Files.zip"' in disposition

    zip_service.cleanup_session(session_id)


def test_images_only_zip_download_filename_end_to_end(tmp_path, monkeypatch):
    """
    Requirement 3:
    Download ZIP containing only images -> Photos_and_Images.zip.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    img1 = create_image_with_text("", width=400, height=300, format="JPEG")
    img2 = create_image_with_text("", width=400, height=300, format="PNG")

    upload_files = [
        ("files", ("photo1.jpg", img1, "image/jpeg")),
        ("files", ("photo2.png", img2, "image/png")),
    ]

    org_res = client.post("/api/upload-and-organize", files=upload_files)
    assert org_res.status_code == 200
    org_data = org_res.json()
    session_id = org_data["session_id"]
    items = org_data["items"]

    dl_res = client.post(
        "/api/download-zip",
        json={"session_id": session_id, "items": items}
    )
    assert dl_res.status_code == 200
    disposition = dl_res.headers.get("content-disposition", "")
    assert 'filename="Photos_and_Images.zip"' in disposition

    zip_service.cleanup_session(session_id)


def test_excluded_files_ignored_in_zip_download_end_to_end(tmp_path, monkeypatch):
    """
    Requirement 3:
    Excluded files are omitted from the ZIP archive and from the dynamic ZIP filename.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    career_pdf = create_valid_pdf("Career Resume", ["Experience as Engineer"])
    finance_pdf = create_valid_pdf("Invoice Doc", ["Invoice and billing receipt"])

    upload_files = [
        ("files", ("resume.pdf", career_pdf, "application/pdf")),
        ("files", ("invoice.pdf", finance_pdf, "application/pdf")),
    ]

    org_res = client.post("/api/upload-and-organize", files=upload_files)
    assert org_res.status_code == 200
    org_data = org_res.json()
    session_id = org_data["session_id"]
    items = org_data["items"]

    items[0]["folder"] = "Career"
    items[0]["excluded"] = False
    items[1]["folder"] = "Finance"
    items[1]["excluded"] = True

    dl_res = client.post(
        "/api/download-zip",
        json={"session_id": session_id, "items": items}
    )
    assert dl_res.status_code == 200
    disposition = dl_res.headers.get("content-disposition", "")
    # Since Finance is excluded, the ZIP filename should be Career_Files.zip
    assert 'filename="Career_Files.zip"' in disposition

    with zipfile.ZipFile(io.BytesIO(dl_res.content), "r") as zf:
        namelist = zf.namelist()
        assert len(namelist) == 1
        assert "Career" in namelist[0]
        assert "Finance" not in namelist[0]

    zip_service.cleanup_session(session_id)

