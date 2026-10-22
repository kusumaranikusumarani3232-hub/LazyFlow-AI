import io
import json
import os
import sys
import hashlib
import zipfile
import urllib.request

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath('backend'))
from app.utils.sample_fixtures import (
    create_valid_pdf,
    create_valid_png,
    create_valid_pptx,
    create_valid_docx,
    create_valid_csv,
)

print("=== LazyFlow AI End-to-End Workflow & Integrity Verification ===")

# 1. Health check
res = urllib.request.urlopen('http://127.0.0.1:8000/api/health')
health = json.loads(res.read())
print('1. Health Status:', health['status'], '| Model:', health['model'])

# 2. Model Status
res = urllib.request.urlopen('http://127.0.0.1:8000/api/model-status')
model = json.loads(res.read())
print('2. Model Name:', model['model_name'], '| Open Weight:', model['open_weight'])

# 3. Multipart Upload with Real Binary Fixtures
fixtures = {
    "Invoice_Oct_final_v2_FINAL.pdf": (create_valid_pdf("October Cloud Hosting Invoice"), "application/pdf"),
    "IMG_20231012_WA0004.png": (create_valid_png(), "image/png"),
    "draft_cs50_week3_notes.docx": (create_valid_docx("CS50 Lecture 3", "Binary search and sorting algorithms."), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "q4_roadmap_presentation_team.pptx": (create_valid_pptx("Quarterly Goals"), "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    "dump_users_export_v1_backup.csv": (create_valid_csv(), "text/csv"),
}

# Pre-compute original SHA-256 hashes
original_hashes = {
    name: hashlib.sha256(data).hexdigest()
    for name, (data, _) in fixtures.items()
}

# Build multipart/form-data body
boundary = "----WebKitFormBoundaryLazyFlowTest7MA4YWxkTrZu0gW"
body_parts = []

for filename, (data, mime) in fixtures.items():
    body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
    body_parts.append(f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'.encode("utf-8"))
    body_parts.append(f"Content-Type: {mime}\r\n\r\n".encode("utf-8"))
    body_parts.append(data)
    body_parts.append(b"\r\n")

# Add custom categories
body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
body_parts.append(b'Content-Disposition: form-data; name="custom_categories"\r\n\r\n')
body_parts.append(b"Finance,Study,Work,Images,Documents\r\n")
body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))

body_bytes = b"".join(body_parts)

upload_req = urllib.request.Request(
    'http://127.0.0.1:8000/api/upload-and-organize',
    data=body_bytes,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
)

res = urllib.request.urlopen(upload_req)
org_data = json.loads(res.read())
session_id = org_data["session_id"]
items = org_data["items"]
print(f"3. Uploaded & AI Organized {len(items)} files successfully (Session: {session_id}):")

for it in items:
    print(f"   [{it['folder']}] {it['original_filename']} -> {it['suggested_filename']} (Reason: {it['reason'][:50]}...)")

# 4. Request Organized ZIP Download
download_req = urllib.request.Request(
    'http://127.0.0.1:8000/api/download-zip',
    data=json.dumps({
        'session_id': session_id,
        'items': items
    }).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
res = urllib.request.urlopen(download_req)
zip_bytes = res.read()
print(f"4. Downloaded ZIP archive: {len(zip_bytes)} bytes")

# 5. Verify byte-for-byte SHA-256 hash integrity of all extracted files
with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
    namelist = zf.namelist()
    print("   ZIP Archive Hierarchy & Hash Verification:")
    for it in items:
        expected_arcname = f"{it['folder']}/{it['suggested_filename']}"
        assert expected_arcname in namelist, f"Missing {expected_arcname} in ZIP!"

        extracted_data = zf.read(expected_arcname)
        extracted_hash = hashlib.sha256(extracted_data).hexdigest()
        orig_hash = original_hashes[it['original_filename']]

        assert extracted_hash == orig_hash, f"Hash mismatch for {it['original_filename']}!"
        print(f"     [OK] {expected_arcname} (SHA-256: {extracted_hash[:16]}... MATCHED)")

# 6. Cleanup Session
cleanup_req = urllib.request.Request(
    f'http://127.0.0.1:8000/api/session/{session_id}',
    method='DELETE'
)
res = urllib.request.urlopen(cleanup_req)
print("5. Ephemeral session purged.")

print("\n>>> ALL WORKFLOW PHASES & SHA-256 CONTENT INTEGRITY VERIFIED! <<<")
