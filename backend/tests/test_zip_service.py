import io
import zipfile
import pytest
from app.services.zip_service import zip_service
from app.models.schemas import FileOrganizedItem

def test_zip_generation_and_safe_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)
    session_id = "test_sess_123"

    # Set up mock uploaded files in session directory
    session_dir = zip_service.get_session_dir(session_id)
    raw_dir = session_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy raw files
    (raw_dir / "f_1_test_file.txt").write_text("Hello world")
    (raw_dir / "f_2_receipt.pdf").write_bytes(b"%PDF-1.4 dummy")

    items = [
        FileOrganizedItem(
            id="f_1",
            original_filename="test_file.txt",
            folder="Documents",
            category="Documents",
            suggested_filename="clean_test_file.txt",
            reason="Clear text document"
        ),
        FileOrganizedItem(
            id="f_2",
            original_filename="receipt.pdf",
            folder="Finance",
            category="Finance",
            suggested_filename="october_receipt.pdf",
            reason="Financial document"
        )
    ]

    zip_buffer, zip_filename = zip_service.build_organized_zip(session_id, items)
    assert zip_filename.endswith(".zip")

    # Verify contents of generated zip
    with zipfile.ZipFile(zip_buffer, "r") as zf:
        namelist = zf.namelist()
        assert "Documents/clean_test_file.txt" in namelist
        assert "Finance/october_receipt.pdf" in namelist
        # Verify no directory traversal or root slashes
        for name in namelist:
            assert not name.startswith("/")
            assert not name.startswith("\\")
            assert ".." not in name

        # Verify content
        assert zf.read("Documents/clean_test_file.txt").decode() == "Hello world"
        assert zf.read("Finance/october_receipt.pdf") == b"%PDF-1.4 dummy"

    # Test cleanup
    zip_service.cleanup_session(session_id)
    assert not session_dir.exists()

def test_zip_generation_excludes_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(zip_service, "temp_root", tmp_path)
    session_id = "test_sess_456"

    session_dir = zip_service.get_session_dir(session_id)
    raw_dir = session_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    (raw_dir / "f_1_included.txt").write_text("Included")
    (raw_dir / "f_2_excluded.txt").write_text("Excluded")

    items = [
        FileOrganizedItem(
            id="f_1",
            original_filename="included.txt",
            folder="Documents",
            category="Documents",
            suggested_filename="keep_me.txt",
            reason="User kept",
            excluded=False
        ),
        FileOrganizedItem(
            id="f_2",
            original_filename="excluded.txt",
            folder="Documents",
            category="Documents",
            suggested_filename="skip_me.txt",
            reason="User excluded",
            excluded=True
        )
    ]

    zip_buffer, _ = zip_service.build_organized_zip(session_id, items)
    with zipfile.ZipFile(zip_buffer, "r") as zf:
        namelist = zf.namelist()
        assert "Documents/keep_me.txt" in namelist
        assert "Documents/skip_me.txt" not in namelist

    zip_service.cleanup_session(session_id)


def test_determine_zip_filename_single_purpose():
    """Verify zip naming matches organization purpose for single category archives."""
    # Career files
    career_items = [
        FileOrganizedItem(
            id="f_1",
            original_filename="resume.pdf",
            folder="Career",
            category="Career",
            suggested_filename="Resume.pdf",
            reason="Resume"
        ),
        FileOrganizedItem(
            id="f_2",
            original_filename="cert.pdf",
            folder="Career",
            category="Career",
            suggested_filename="Certificate.pdf",
            reason="Certificate"
        )
    ]
    assert zip_service.determine_zip_filename(career_items) == "Career_Files.zip"

    # Study files
    study_items = [
        FileOrganizedItem(
            id="f_1",
            original_filename="notes.docx",
            folder="Study",
            category="Study",
            suggested_filename="Study_Notes.docx",
            reason="Study notes"
        )
    ]
    assert zip_service.determine_zip_filename(study_items) == "Study_Files.zip"

    # Project files
    project_items = [
        FileOrganizedItem(
            id="f_1",
            original_filename="specs.docx",
            folder="Project",
            category="Project",
            suggested_filename="Specifications.docx",
            reason="Project specs"
        )
    ]
    assert zip_service.determine_zip_filename(project_items) == "Project_Files.zip"

    # Named project
    apollo_items = [
        FileOrganizedItem(
            id="f_1",
            original_filename="proposal.docx",
            folder="Project Apollo",
            category="Project Apollo",
            suggested_filename="Mission_Proposal.docx",
            reason="Apollo proposal"
        ),
        FileOrganizedItem(
            id="f_2",
            original_filename="budget.csv",
            folder="Project Apollo",
            category="Project Apollo",
            suggested_filename="Budget.csv",
            reason="Apollo budget"
        )
    ]
    assert zip_service.determine_zip_filename(apollo_items) == "Project_Apollo_Files.zip"


def test_determine_zip_filename_mixed_categories():
    """Verify combining two categories produces {Cat1}_and_{Cat2}_Files.zip."""
    mixed_items = [
        FileOrganizedItem(
            id="f_1",
            original_filename="resume.pdf",
            folder="Career",
            category="Career",
            suggested_filename="Resume.pdf",
            reason="Resume"
        ),
        FileOrganizedItem(
            id="f_2",
            original_filename="invoice.pdf",
            folder="Finance",
            category="Finance",
            suggested_filename="Invoice.pdf",
            reason="Invoice"
        )
    ]
    assert zip_service.determine_zip_filename(mixed_items) == "Career_and_Finance_Files.zip"


def test_determine_zip_filename_career_and_study():
    """Verify Career and Study files produce Career_and_Study_Files.zip."""
    items = [
        FileOrganizedItem(
            id="f_1",
            original_filename="cert.pdf",
            folder="Career",
            category="Career",
            suggested_filename="Certificate.pdf",
            reason="Certificate"
        ),
        FileOrganizedItem(
            id="f_2",
            original_filename="notes.docx",
            folder="Study",
            category="Study",
            suggested_filename="Study_Notes.docx",
            reason="Study notes"
        )
    ]
    assert zip_service.determine_zip_filename(items) == "Career_and_Study_Files.zip"


def test_determine_zip_filename_images_only():
    """Verify images-only folder produces Photos_and_Images.zip."""
    items = [
        FileOrganizedItem(
            id="f_1",
            original_filename="vacation.jpg",
            folder="Images",
            category="Images",
            suggested_filename="vacation.jpg",
            reason="Photo"
        ),
        FileOrganizedItem(
            id="f_2",
            original_filename="screenshot.png",
            folder="Images",
            category="Images",
            suggested_filename="UI_Screenshot.png",
            reason="Screenshot"
        )
    ]
    assert zip_service.determine_zip_filename(items) == "Photos_and_Images.zip"


def test_determine_zip_filename_too_many_categories():
    """Verify more than 3 categories produces Organized_Mixed_Files.zip."""
    items = [
        FileOrganizedItem(id="f_1", original_filename="a.pdf", folder="Career", category="Career", suggested_filename="a.pdf", reason=""),
        FileOrganizedItem(id="f_2", original_filename="b.pdf", folder="Study", category="Study", suggested_filename="b.pdf", reason=""),
        FileOrganizedItem(id="f_3", original_filename="c.pdf", folder="Finance", category="Finance", suggested_filename="c.pdf", reason=""),
        FileOrganizedItem(id="f_4", original_filename="d.py", folder="Code", category="Code", suggested_filename="d.py", reason="")
    ]
    assert zip_service.determine_zip_filename(items) == "Organized_Mixed_Files.zip"


def test_determine_zip_filename_empty_selection():
    """Verify empty or all-excluded selection falls back cleanly."""
    assert zip_service.determine_zip_filename([]) == "Organized_Mixed_Files.zip"


def test_determine_zip_filename_sanitization():
    """Verify invalid filesystem characters in destination folders are sanitized."""
    illegal_folder_items = [
        FileOrganizedItem(
            id="f_1",
            original_filename="report.pdf",
            folder='Project: Apollo/2024*?"<>|',
            category="Project",
            suggested_filename="Report.pdf",
            reason="Report"
        )
    ]
    zip_name = zip_service.determine_zip_filename(illegal_folder_items)
    assert zip_name.endswith(".zip")
    for bad_char in (':', '*', '?', '"', '<', '>', '|', '/', '\\'):
        assert bad_char not in zip_name


def test_determine_zip_filename_ignores_excluded_items():
    """Verify excluded items do not affect purpose determination."""
    items = [
        FileOrganizedItem(
            id="f_1",
            original_filename="resume.pdf",
            folder="Career",
            category="Career",
            suggested_filename="Resume.pdf",
            reason="Resume",
            excluded=False
        ),
        FileOrganizedItem(
            id="f_2",
            original_filename="tax.pdf",
            folder="Finance",
            category="Finance",
            suggested_filename="Tax.pdf",
            reason="Tax",
            excluded=True
        )
    ]
    assert zip_service.determine_zip_filename(items) == "Career_Files.zip"

