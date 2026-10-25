import io
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.vision_service import vision_service
from app.services.content_extractor import content_extractor
from app.services.ai_organizer import ai_organizer
from app.utils.sample_fixtures import (
    create_tshirt_image,
    create_abstract_noise_image,
    create_image_with_text,
)

client = TestClient(app)


def test_vision_service_engine_available_and_reports_status():
    """Verify MobileNetV3-Small vision classifier is initialized and available."""
    assert vision_service.is_available() is True
    info = vision_service.get_engine_info()
    assert info["available"] is True
    assert "MobileNetV3-Small" in info["model_family"]
    assert info["classes_supported"] == 1000
    assert info["enabled"] is True


def test_vision_service_classify_tshirt_image():
    """Verify vision service identifies a T-shirt shape as T-Shirt / Clothing with high confidence."""
    tshirt_bytes = create_tshirt_image(format="JPEG")
    res = vision_service.classify_image(tshirt_bytes, filename="tback.jpeg")

    assert res["success"] is True
    assert res["concept"] == "T-Shirt"
    assert res["category"] == "Clothing"
    assert res["folder"] == "Images"
    assert res["is_ambiguous"] is False
    assert res["confidence_score"] >= 0.18


def test_vision_service_uncertain_abstract_image():
    """Verify abstract texture with no recognizable object is marked ambiguous."""
    noise_bytes = create_abstract_noise_image(format="JPEG")
    res = vision_service.classify_image(noise_bytes, filename="abstract_art.jpeg")

    assert res["is_ambiguous"] is True
    assert res["concept"] is None
    assert res["confidence_level"] == "ambiguous"


def test_content_extractor_distinguishes_visual_vs_ocr_vs_ambiguous():
    """
    Verify ContentExtractor pipeline:
    1. Text certificate image -> image_ocr
    2. T-shirt photo -> image_visual
    3. Abstract image -> image_metadata (ambiguous)
    """
    # 1. Certificate image
    cert_text = (
        "Certificate of Completion\n"
        "TCS iON Career Edge\n"
        "This is to certify that Alex Morgan has completed the course"
    )
    cert_bytes = create_image_with_text(cert_text, width=800, height=400, format="PNG")
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tf.write(cert_bytes)
        cert_path = tf.name

    try:
        res_cert = content_extractor.extract_file_content(cert_path, "cert.png", "image/png")
        assert res_cert["content_type"] == "image_ocr"
        assert res_cert["has_content"] is True
        assert "career edge" in res_cert["content_snippet"].lower()
    finally:
        if os.path.exists(cert_path):
            os.remove(cert_path)

    # 2. T-shirt photo
    tshirt_bytes = create_tshirt_image(format="JPEG")
    with tempfile.NamedTemporaryFile(suffix=".jpeg", delete=False) as tf:
        tf.write(tshirt_bytes)
        tshirt_path = tf.name

    try:
        res_tshirt = content_extractor.extract_file_content(tshirt_path, "tback.jpeg", "image/jpeg")
        assert res_tshirt["content_type"] == "image_visual"
        assert res_tshirt["has_content"] is True
        assert res_tshirt["extracted_metadata"]["visual_concept"] == "T-Shirt"
        assert res_tshirt["extracted_metadata"]["visual_category"] == "Clothing"
        assert res_tshirt["extracted_metadata"]["is_empty_or_minimal"] is False
    finally:
        if os.path.exists(tshirt_path):
            os.remove(tshirt_path)

    # 3. Abstract image
    noise_bytes = create_abstract_noise_image(format="JPEG")
    with tempfile.NamedTemporaryFile(suffix=".jpeg", delete=False) as tf:
        tf.write(noise_bytes)
        noise_path = tf.name

    try:
        res_noise = content_extractor.extract_file_content(noise_path, "unknown_photo.jpeg", "image/jpeg")
        assert res_noise["content_type"] == "image_metadata"
        assert res_noise["has_content"] is False
        assert res_noise["extracted_metadata"]["is_empty_or_minimal"] is True
    finally:
        if os.path.exists(noise_path):
            os.remove(noise_path)


def test_tshirt_upload_end_to_end_organize():
    """
    Trace real upload-to-result workflow for a T-shirt photo:
    - POST /api/upload-and-organize with tback.jpeg
    - Suggested filename becomes T-Shirt.jpeg
    - Placed into Images folder
    - is_ambiguous is False
    - Confidence is high
    """
    tshirt_bytes = create_tshirt_image(format="JPEG")
    upload_files = [
        ("files", ("tback.jpeg", tshirt_bytes, "image/jpeg")),
    ]

    response = client.post("/api/upload-and-organize", files=upload_files)
    assert response.status_code == 200
    data = response.json()

    assert data["total_files"] == 1
    item = data["items"][0]
    assert item["original_filename"] == "tback.jpeg"
    assert item["suggested_filename"] == "T-Shirt.jpeg"
    assert item["folder"] == "Images"
    assert item["is_ambiguous"] is False
    assert item["confidence"] in ("high", "medium")
    assert "T-Shirt" in item["reason"]


def test_tshirt_with_user_selected_folder():
    """Verify user-selected destination folder is respected for visual classification."""
    tshirt_bytes = create_tshirt_image(format="JPEG")
    upload_files = [
        ("files", ("photo_shirt.png", tshirt_bytes, "image/png")),
    ]

    response = client.post(
        "/api/upload-and-organize",
        data={"user_folder": "Apparel"},
        files=upload_files
    )
    assert response.status_code == 200
    data = response.json()

    item = data["items"][0]
    assert item["suggested_filename"] == "T-Shirt.png"
    assert item["folder"] == "Apparel"
    assert item["is_ambiguous"] is False


def test_misleading_name_not_labeled_as_certificate():
    """
    Do not label an image a certificate just because metadata or filename suggests it.
    An image named 'certificate_photo.jpg' without OCR certificate text must NOT be labeled a certificate.
    """
    tshirt_bytes = create_tshirt_image(format="JPEG")
    upload_files = [
        ("files", ("certificate_award.jpeg", tshirt_bytes, "image/jpeg")),
    ]

    response = client.post("/api/upload-and-organize", files=upload_files)
    assert response.status_code == 200
    data = response.json()

    item = data["items"][0]
    assert item["folder"] != "Career"
    assert "Certificate" not in item["suggested_filename"]
    assert item["suggested_filename"] == "T-Shirt.jpeg"


def test_uncertain_ordinary_photo_preserves_original_filename():
    """
    For uncertain/abstract images, preserve the exact original filename
    rather than guessing.
    """
    noise_bytes = create_abstract_noise_image(format="JPEG")
    upload_files = [
        ("files", ("IMG_20241025_camera.jpeg", noise_bytes, "image/jpeg")),
    ]

    response = client.post("/api/upload-and-organize", files=upload_files)
    assert response.status_code == 200
    data = response.json()

    item = data["items"][0]
    assert item["original_filename"] == "IMG_20241025_camera.jpeg"
    assert item["suggested_filename"] == "IMG_20241025_camera.jpeg"
    assert item["folder"] == "Images"
    assert item["is_ambiguous"] is True
    assert item["confidence"] == "ambiguous"


def test_health_and_model_status_endpoints_report_vision():
    """Verify /api/health and /api/model-status report vision capability."""
    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    h_data = health_res.json()
    assert h_data["vision_available"] is True
    assert "MobileNetV3" in h_data["vision_engine"]

    status_res = client.get("/api/model-status")
    assert status_res.status_code == 200
    s_data = status_res.json()
    assert s_data["vision_supported"] is True
    assert s_data["vision_available"] is True
    assert s_data["vision_engine"]["enabled"] is True
