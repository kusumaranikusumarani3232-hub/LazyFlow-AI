import io
import hashlib
import zipfile
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.zip_service import zip_service
from app.services.content_extractor import content_extractor
from app.utils.sample_fixtures import (
    create_valid_pdf,
    create_valid_docx,
    create_valid_csv,
    create_valid_png,
)

client = TestClient(app)


def test_content_extractor_pdf_resume():
    """Requirement 1: Extract readable text from PDF files."""
    pdf_bytes = create_valid_pdf(
        "Jane Doe - Resume",
        [
            "Summary: Senior Backend Engineer with 5+ years experience.",
            "Experience: Tech Lead at Acme Inc building Python APIs.",
            "Education: B.S. Computer Science from State University.",
            "Skills: Python, FastAPI, Docker, PostgreSQL."
        ]
    )
    # Save to buffer and extract
    with io.BytesIO(pdf_bytes) as buf:
        # Write to temporary file for extractor
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            tf.write(pdf_bytes)
            tf_path = tf.name

        try:
            res = content_extractor.extract_file_content(tf_path, "document.pdf", "application/pdf")
            assert res["has_content"] is True
            assert res["content_type"] == "pdf_text"
            assert "Jane Doe" in res["content_snippet"]
            assert "Resume" in res["content_snippet"]
            assert "Skills" in res["content_snippet"]
            assert len(res["content_snippet"]) <= 1200
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)


def test_content_extractor_docx_study_notes():
    """Requirement 1: Extract readable text from DOCX files."""
    docx_bytes = create_valid_docx(
        "CS50 Algorithms Lecture Notes",
        "Binary search trees, big-O complexity, and dynamic programming exam preparation."
    )
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tf:
        tf.write(docx_bytes)
        tf_path = tf.name

    try:
        res = content_extractor.extract_file_content(tf_path, "notes.docx")
        assert res["has_content"] is True
        assert res["content_type"] == "docx_text"
        assert "CS50 Algorithms" in res["content_snippet"]
        assert "Binary search" in res["content_snippet"]
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)


def test_content_extractor_csv_headers_and_rows():
    """Requirement 1: Read spreadsheet headers and sample rows from CSV files."""
    csv_bytes = (
        "InvoiceNo,Date,Client,Amount,Status\n"
        "INV-101,2024-01-10,Acme Corp,1250.00,Paid\n"
        "INV-102,2024-01-15,Beta LLC,850.00,Pending\n"
        "INV-103,2024-01-20,Gamma Inc,3200.00,Paid\n"
    ).encode("utf-8")

    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        tf.write(csv_bytes)
        tf_path = tf.name

    try:
        res = content_extractor.extract_file_content(tf_path, "invoices_export.csv", "text/csv")
        assert res["has_content"] is True
        assert res["content_type"] == "csv_data"
        assert "InvoiceNo" in res["content_snippet"]
        assert "Amount" in res["content_snippet"]
        assert "INV-101" in res["content_snippet"]
        assert "Columns" in res["content_snippet"]
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)


def test_content_extractor_ambiguous_minimal_file():
    """Requirement 6: Handle ambiguous or minimal files without failing."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tf:
        tf.write(b"\x00\x01\x02\x03\x04")
        tf_path = tf.name

    try:
        res = content_extractor.extract_file_content(tf_path, "ambiguous_data.bin")
        assert res["has_content"] is False
        assert res["extracted_metadata"].get("is_empty_or_minimal") is True
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)


def test_content_aware_organization_resume_in_career(tmp_path, monkeypatch):
    """
    Requirements 1, 2, 3:
    document.pdf containing a resume -> Resume.pdf in Career folder.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    resume_pdf = create_valid_pdf(
        "Alex Morgan - Curriculum Vitae",
        [
            "Summary: Senior Full-Stack Engineer with 6+ years experience.",
            "Experience: Tech Lead building distributed web services.",
            "Education: B.S. in Computer Science.",
            "Skills: Python, TypeScript, React, Docker, FastAPI."
        ]
    )

    upload_files = [
        ("files", ("document.pdf", resume_pdf, "application/pdf")),
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
    assert item["original_filename"] == "document.pdf"
    # Destination folder must be Career
    assert item["folder"].lower() == "career"
    # Suggested filename must be Resume or include candidate name
    assert "resume" in item["suggested_filename"].lower()
    assert item["suggested_filename"].endswith(".pdf")
    assert item["is_ambiguous"] is False


def test_content_aware_organization_invoice_in_finance(tmp_path, monkeypatch):
    """
    Requirements 1, 2, 3:
    file.pdf containing an invoice -> Invoice.pdf in Finance folder.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    invoice_pdf = create_valid_pdf(
        "INVOICE #INV-2024-889",
        [
            "Vendor: Cloud Infrastructure & Hosting Services",
            "Bill To: Acme Technologies Inc.",
            "Amount Due: $450.00 USD - Due Date: Nov 15, 2024",
            "Description: Dedicated cloud servers and database backups"
        ]
    )

    upload_files = [
        ("files", ("file.pdf", invoice_pdf, "application/pdf")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()

    item = data["items"][0]
    assert item["original_filename"] == "file.pdf"
    assert item["folder"].lower() == "finance"
    assert "invoice" in item["suggested_filename"].lower()
    assert item["suggested_filename"].endswith(".pdf")


def test_content_aware_organization_notes_in_study(tmp_path, monkeypatch):
    """
    Requirements 1, 2, 3:
    notes.docx containing study notes -> Study Notes.docx in Study folder.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    study_docx = create_valid_docx(
        "CS50 Algorithms Study Notes",
        "Lecture on binary search trees, time complexity O(log n), and sorting algorithms."
    )

    upload_files = [
        ("files", ("notes.docx", study_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()

    item = data["items"][0]
    assert item["original_filename"] == "notes.docx"
    assert item["folder"].lower() == "study"
    assert ("study" in item["suggested_filename"].lower() or "notes" in item["suggested_filename"].lower())
    assert item["suggested_filename"].endswith(".docx")


def test_mixed_uploads_shared_project_grouping(tmp_path, monkeypatch):
    """
    Requirement 4:
    For mixed uploads, group related files across different file types
    into shared folders when evidence supports the relationship.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    proposal_docx = create_valid_docx(
        "Project Apollo Mission Proposal",
        "Architecture specifications and system requirements for Project Apollo."
    )
    budget_csv = (
        "Phase,Item,Cost,Currency\n"
        "Phase 1,Servers,12000,USD\n"
        "Phase 2,Testing,8000,USD\n"
    ).encode("utf-8")
    diagram_png = create_valid_png()

    upload_files = [
        ("files", ("apollo_proposal.docx", proposal_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
        ("files", ("apollo_budget.csv", budget_csv, "text/csv")),
        ("files", ("apollo_diagram.png", diagram_png, "image/png")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    items = data["items"]
    assert len(items) == 3

    # All files share the 'Apollo' project relationship
    folders = [item["folder"].lower() for item in items]
    assert any("apollo" in f for f in folders), f"Expected Apollo project folder, got: {folders}"


def test_ambiguous_content_retains_original_filename(tmp_path, monkeypatch):
    """
    Requirement 6:
    Never invent content or confidently label an ambiguous file.
    Keep its original filename when uncertain and let user edit suggestions.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    # 10 bytes of arbitrary unidentifiable binary data
    ambiguous_bytes = b"\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99"

    upload_files = [
        ("files", ("mystery_data.bin", ambiguous_bytes, "application/octet-stream")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    item = data["items"][0]

    # Must retain original filename exactly
    assert item["suggested_filename"] == "mystery_data.bin"
    assert item["is_ambiguous"] is True
    assert "ambiguous" in item["reason"].lower() or "minimal" in item["reason"].lower()


def test_zip_integrity_preserves_exact_bytes(tmp_path, monkeypatch):
    """
    Requirement 7 & 9:
    Preserve original file bytes in the ZIP; suggested names and folder paths
    must not modify file contents.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    resume_pdf = create_valid_pdf("Resume Document", ["Experience: Software Engineer"])
    invoice_csv = create_valid_csv()
    doc_docx = create_valid_docx("Document Heading", "Document Body Text")

    pdf_sha = hashlib.sha256(resume_pdf).hexdigest()
    csv_sha = hashlib.sha256(invoice_csv).hexdigest()
    docx_sha = hashlib.sha256(doc_docx).hexdigest()

    upload_files = [
        ("files", ("document.pdf", resume_pdf, "application/pdf")),
        ("files", ("invoice.csv", invoice_csv, "text/csv")),
        ("files", ("notes.docx", doc_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
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
    assert dl_res.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(dl_res.content), "r") as zf:
        namelist = zf.namelist()
        assert len(namelist) == 3

        for item in items:
            arcname = f"{item['folder']}/{item['suggested_filename']}"
            assert arcname in namelist

            extracted = zf.read(arcname)
            extracted_sha = hashlib.sha256(extracted).hexdigest()

            if item["original_filename"] == "document.pdf":
                assert extracted_sha == pdf_sha
            elif item["original_filename"] == "invoice.csv":
                assert extracted_sha == csv_sha
            elif item["original_filename"] == "notes.docx":
                assert extracted_sha == docx_sha

    zip_service.cleanup_session(session_id)


def test_privacy_consent_disabled_mode(tmp_path, monkeypatch):
    """
    Requirement 8:
    Protect privacy: when user does not consent, do not extract or send content.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    resume_pdf = create_valid_pdf("Resume Document", ["Experience: Software Engineer"])

    upload_files = [
        ("files", ("document.pdf", resume_pdf, "application/pdf")),
    ]

    # Submit with consent_content_analysis=false
    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "false"}
    )
    assert response.status_code == 200
    data = response.json()
    # Still organizes cleanly without content snippets
    assert len(data["items"]) == 1


def test_synthetic_pdf_named_pdf_pdf_with_resume_sections(tmp_path, monkeypatch):
    """
    User Regression Test:
    A file named 'pdf.pdf' containing obvious resume text
    (Professional Summary, Work Experience, Education, Skills)
    must be classified into Folder: 'Career' with Suggested Filename: 'Resume.pdf'.
    Must NOT produce generic 'Pdf.pdf' or 'corporate/project roadmap'.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    resume_pdf = create_valid_pdf(
        "John Doe - Senior Software Engineer",
        [
            "Professional Summary: Dedicated backend engineer specializing in distributed systems.",
            "Work Experience: Senior Software Engineer at CloudCorp (2020 - Present).",
            "- Built high-throughput microservices using Python, FastAPI, and Docker.",
            "Education: B.S. in Computer Science, Magna Cum Laude.",
            "Skills: Python, TypeScript, React, PostgreSQL, Docker, AWS."
        ]
    )

    upload_files = [
        ("files", ("pdf.pdf", resume_pdf, "application/pdf")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    item = data["items"][0]

    assert item["original_filename"] == "pdf.pdf"
    assert item["folder"] == "Career", f"Expected folder 'Career', got '{item['folder']}'"
    assert item["suggested_filename"] == "Resume.pdf", f"Expected 'Resume.pdf', got '{item['suggested_filename']}'"
    assert item["is_ambiguous"] is False
    assert "corporate/project roadmap" not in item["reason"].lower()


def test_ambiguous_pdf_named_pdf_pdf_retains_original_filename(tmp_path, monkeypatch):
    """
    User Test:
    A file named 'pdf.pdf' with minimal / ambiguous content
    must retain its exact original filename 'pdf.pdf' (not 'Pdf.pdf'),
    place it in Documents or Other, mark is_ambiguous=True,
    and never invent a document purpose like 'corporate/project roadmap'.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    # Minimal ambiguous PDF with no clear purpose
    ambiguous_pdf = create_valid_pdf("Draft 1")

    upload_files = [
        ("files", ("pdf.pdf", ambiguous_pdf, "application/pdf")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    item = data["items"][0]

    # Must preserve exact original filename, never invent roadmap or change to Pdf.pdf
    assert item["suggested_filename"] == "pdf.pdf"
    assert item["folder"] in ("Documents", "Other")
    assert item["is_ambiguous"] is True
    assert "ambiguous" in item["reason"].lower() or "minimal" in item["reason"].lower()
    assert "corporate/project roadmap" not in item["reason"].lower()


def test_corrupted_pdf_extraction_failure_retains_original_filename(tmp_path, monkeypatch):
    """
    User Test:
    When extraction fails on a corrupted PDF, LazyFlow must not crash,
    must preserve the original filename, and use a cautious fallback
    instead of inventing a document purpose.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    corrupted_bytes = b"%PDF-1.4\nBROKEN_UNREADABLE_GARBAGE_BYTES_NO_PAGES"

    upload_files = [
        ("files", ("corrupted_doc.pdf", corrupted_bytes, "application/pdf")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    item = data["items"][0]

    assert item["suggested_filename"] == "corrupted_doc.pdf"
    assert item["is_ambiguous"] is True
    assert item["folder"] in ("Documents", "Other")


def test_full_pipeline_diagnostics_logging(tmp_path, monkeypatch, caplog):
    """
    User Test:
    Verify safe diagnostics trace the full pipeline:
    [Diagnostic:Upload] -> [Diagnostic:Extraction] -> [Diagnostic:AI_Request] -> [Diagnostic:Classification]
    Never prints sensitive extracted document text into logs.
    """
    import logging
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    secret_text = "SECRET_CANDIDATE_PASSPORT_998877"
    resume_pdf = create_valid_pdf(
        "Confidential Resume",
        [
            f"Professional Summary: Software Engineer with id {secret_text}",
            "Work Experience: 4 years backend development.",
            "Education: B.S. Computer Science."
        ]
    )

    with caplog.at_level(logging.INFO):
        response = client.post(
            "/api/upload-and-organize",
            files=[("files", ("candidate_resume.pdf", resume_pdf, "application/pdf"))],
            data={"consent_content_analysis": "true"}
        )

    assert response.status_code == 200
    log_output = caplog.text

    # Diagnostic trace markers must be present
    assert "[Diagnostic:Upload]" in log_output
    assert "[Diagnostic:Extraction]" in log_output
    assert "[Diagnostic:AI_Request]" in log_output
    assert "[Diagnostic:Classification]" in log_output

    # Crucial privacy requirement: Sensitive document text must NEVER appear in logs
    assert secret_text not in log_output


def test_certificate_pdf_named_scrape_verse_suggests_meaningful_certificate_name(tmp_path, monkeypatch):
    """
    User Regression Test (Requirement 1, 2, 3, 4):
    A certificate PDF named 'scrape verse.pdf' must be recognized from content evidence
    as a certificate and given a meaningful suggested filename like
    'ScrapeVerse-Web-Scraping-Certificate.pdf' (or 'ScrapeVerse-Web-Scraping-Mastery-Certificate.pdf')
    in folder 'Career', regardless of the original filename.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    scrapeverse_cert_pdf = create_valid_pdf(
        "Certificate of Completion",
        [
            "This is to certify that Alex Mercer has successfully completed",
            "the ScrapeVerse Web Scraping Mastery course on October 15, 2024.",
            "Issued by ScrapeVerse Academy.",
            "Credential ID: SV-88921-2024"
        ]
    )

    upload_files = [
        ("files", ("scrape verse.pdf", scrapeverse_cert_pdf, "application/pdf")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    item = data["items"][0]

    assert item["original_filename"] == "scrape verse.pdf"
    assert item["folder"] == "Career"
    assert "scrapeverse" in item["suggested_filename"].lower()
    assert "certificate" in item["suggested_filename"].lower()
    assert item["suggested_filename"].endswith(".pdf")
    assert item["is_ambiguous"] is False


def test_certificate_pdf_tcs_ion_career_edge_suggests_meaningful_certificate_name(tmp_path, monkeypatch):
    """
    User Regression Test (Requirement 4):
    A PDF containing TCS iON Career Edge content must suggest a meaningful filename
    like 'TCS-iON-Career-Edge-Certificate.pdf' supported by the extracted text.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    tcs_cert_pdf = create_valid_pdf(
        "Certificate of Achievement",
        [
            "Congratulations to Jana Kusumarani",
            "for successfully completing TCS iON Career Edge - AI Foundation course",
            "Global Delivery Head - TCS iON, Tata Consultancy Services",
            "Cert ID: 279243-33218227-1016"
        ]
    )

    upload_files = [
        ("files", ("random_download_8892.pdf", tcs_cert_pdf, "application/pdf")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    item = data["items"][0]

    assert item["original_filename"] == "random_download_8892.pdf"
    assert item["folder"] == "Career"
    assert item["suggested_filename"] == "TCS-iON-Career-Edge-Certificate.pdf"
    assert item["is_ambiguous"] is False


def test_certificate_preserves_user_selected_destination_folder(tmp_path, monkeypatch):
    """
    Requirement 5:
    Keep the user's selected destination folder (such as Career) unchanged unless
    the user explicitly changes it; improve the suggested filename independently.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    scrapeverse_cert_pdf = create_valid_pdf(
        "Certificate of Completion",
        [
            "This certifies that Jane Doe successfully completed the ScrapeVerse Web Scraping course.",
            "Issued by ScrapeVerse Academy."
        ]
    )

    upload_files = [
        ("files", ("scrape verse.pdf", scrapeverse_cert_pdf, "application/pdf")),
    ]

    # User explicitly selected destination category 'Career'
    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true", "custom_categories": "Career"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    item = data["items"][0]

    assert item["folder"] == "Career"
    assert "scrapeverse" in item["suggested_filename"].lower()
    assert "certificate" in item["suggested_filename"].lower()


def test_certificate_insufficient_evidence_never_invents_org_or_course(tmp_path, monkeypatch):
    """
    Requirement 6:
    Never invent a certificate name, organization, or document purpose.
    If the content has only a generic heading, use evidenced heading only.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    generic_cert_pdf = create_valid_pdf(
        "Certificate of Completion",
        [
            "This is to certify that the participant has fulfilled all requirements."
        ]
    )

    upload_files = [
        ("files", ("cert_generic.pdf", generic_cert_pdf, "application/pdf")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    item = data["items"][0]

    # Must NOT invent TCS, ScrapeVerse, Coursera, or any imaginary course
    assert "tcs" not in item["suggested_filename"].lower()
    assert "scrapeverse" not in item["suggested_filename"].lower()
    assert item["suggested_filename"] == "Certificate-of-Completion.pdf"


def test_receipt_and_report_content_aware_recognition(tmp_path, monkeypatch):
    """
    Requirement 3:
    Recognize common document types from evidence in the content, including receipts and reports.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    receipt_pdf = create_valid_pdf(
        "Uber Trip Receipt #UB-99212",
        [
            "Payment Confirmation: Card ending in 4022",
            "Total Paid: $24.50 USD",
            "Merchant: Uber Technologies Inc."
        ]
    )

    report_pdf = create_valid_pdf(
        "Annual Project Report 2024",
        [
            "Executive Summary: Evaluation of core infrastructure scaling.",
            "Key Findings and System Performance Metrics across all clusters.",
            "Technical Report and Final Recommendations."
        ]
    )

    upload_files = [
        ("files", ("receipt_doc.pdf", receipt_pdf, "application/pdf")),
        ("files", ("project_doc.pdf", report_pdf, "application/pdf")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        files=upload_files,
        data={"consent_content_analysis": "true"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    items = {item["original_filename"]: item for item in data["items"]}

    assert items["receipt_doc.pdf"]["folder"] == "Finance"
    assert "receipt" in items["receipt_doc.pdf"]["suggested_filename"].lower()

    assert items["project_doc.pdf"]["folder"] in ("Work", "Documents")
    assert "report" in items["project_doc.pdf"]["suggested_filename"].lower()


def test_download_zip_filename_reflects_organization_purpose(tmp_path, monkeypatch):
    """
    Part 2 Requirement:
    Downloaded ZIP filename reflects the selected organization purpose (e.g. Career_Files.zip)
    or LazyFlow_Organized_Files.zip for mixed categories.
    """
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)

    cert_pdf = create_valid_pdf("Certificate of Completion", ["ScrapeVerse Web Scraping Course Certificate"])
    resume_pdf = create_valid_pdf("Resume", ["Professional Experience: Senior Software Engineer"])

    upload_files = [
        ("files", ("cert.pdf", cert_pdf, "application/pdf")),
        ("files", ("resume.pdf", resume_pdf, "application/pdf")),
    ]

    org_res = client.post("/api/upload-and-organize", files=upload_files)
    assert org_res.status_code == 200
    org_data = org_res.json()
    session_id = org_data["session_id"]
    items = org_data["items"]

    # All items are in Career folder
    for item in items:
        item["folder"] = "Career"

    dl_res = client.post(
        "/api/download-zip",
        json={"session_id": session_id, "items": items}
    )
    assert dl_res.status_code == 200
    disposition = dl_res.headers.get("content-disposition", "")
    assert 'filename="Career_Files.zip"' in disposition

    # Mixed folders test
    items[0]["folder"] = "Career"
    items[1]["folder"] = "Finance"

    dl_res_mixed = client.post(
        "/api/download-zip",
        json={"session_id": session_id, "items": items}
    )
    assert dl_res_mixed.status_code == 200
    disposition_mixed = dl_res_mixed.headers.get("content-disposition", "")
    assert 'filename="Career_and_Finance_Files.zip"' in disposition_mixed

    zip_service.cleanup_session(session_id)


