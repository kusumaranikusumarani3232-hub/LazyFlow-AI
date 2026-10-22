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
