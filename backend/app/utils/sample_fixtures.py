import io
import struct
import zipfile
import zlib
from typing import Dict

def create_valid_png() -> bytes:
    """Generate a valid, openable 1x1 RGBA PNG file."""
    # PNG signature
    png = b"\x89PNG\r\n\x1a\n"
    
    # IHDR: 1x1, 8-bit depth, color type 6 (RGBA), compression 0, filter 0, interlace 0
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    png += struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    
    # IDAT: 1 scanline (filter type 0) + 4 bytes RGBA (34, 197, 94, 255 -> Forest Green)
    scanline = b"\x00\x22\xc5\x5e\xff"
    idat_data = zlib.compress(scanline)
    idat_crc = zlib.crc32(b"IDAT" + idat_data)
    png += struct.pack(">I", len(idat_data)) + b"IDAT" + idat_data + struct.pack(">I", idat_crc)
    
    # IEND
    iend_crc = zlib.crc32(b"IEND")
    png += struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    
    return png

def create_valid_jpeg() -> bytes:
    """Generate a valid, openable minimal JPEG image."""
    # 1x1 Forest green JPEG
    # SOI, APP0 (JFIF), DQT, SOF0, DHT, SOS, compressed data, EOI
    return bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x01, 0x00, 0x48, 0x00, 0x48, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F,
        0x00, 0x7F, 0x00, 0xFF, 0xD9
    ])

def create_valid_pdf(title: str = "LazyFlow Document", extra_lines: list[str] | None = None) -> bytes:
    """Generate a valid, fully conformant, openable PDF-1.4 document."""
    escaped_title = title.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream_ops = [f"BT /F1 12 Tf 50 720 Td ({escaped_title}) Tj"]
    if extra_lines:
        for l in extra_lines:
            esc = l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream_ops.append(f"0 -18 Td ({esc}) Tj")
    stream_ops.append("ET\n")
    stream_content = "\n".join(stream_ops)
    stream_len = len(stream_content.encode("ascii", errors="replace"))

    lines = [
        "%PDF-1.4",
        "1 0 obj",
        "<< /Type /Catalog /Pages 2 0 R >>",
        "endobj",
        "2 0 obj",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "endobj",
        "3 0 obj",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        "endobj",
        "4 0 obj",
        f"<< /Length {stream_len} >>",
        "stream",
        stream_content.strip(),
        "endstream",
        "endobj",
        "5 0 obj",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        "endobj",
    ]

    body = "\n".join(lines) + "\n"
    # Calculate xref offsets
    obj_offsets = []
    current_pos = 0
    for line in lines:
        if line.endswith(" obj"):
            obj_offsets.append(current_pos)
        current_pos += len(line) + 1

    xref_pos = len(body.encode("ascii"))
    xref = [
        "xref",
        f"0 {len(obj_offsets) + 1}",
        "0000000000 65535 f ",
    ]
    for offset in obj_offsets:
        xref.append(f"{offset:010d} 00000 n ")

    trailer = [
        "trailer",
        f"<< /Size {len(obj_offsets) + 1} /Root 1 0 R >>",
        "startxref",
        str(xref_pos),
        "%%EOF\n",
    ]

    pdf_full = body + "\n".join(xref) + "\n" + "\n".join(trailer)
    return pdf_full.encode("ascii")

def create_valid_docx(heading: str = "LazyFlow Document", text: str = "This is a genuine Word document.") -> bytes:
    """Generate a valid, fully conformant Microsoft Word .docx archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            '  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n'
            '</Types>'
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>\n'
            '</Relationships>'
        )
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
            '  <w:body>\n'
            f'    <w:p><w:r><w:rPr><w:b/></w:rPr><w:t>{heading}</w:t></w:r></w:p>\n'
            f'    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>\n'
            '  </w:body>\n'
            '</w:document>'
        )
    return buf.getvalue()

def create_valid_pptx(title: str = "LazyFlow Presentation") -> bytes:
    """Generate a valid, fully conformant Microsoft PowerPoint .pptx archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            '  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>\n'
            '  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>\n'
            '</Types>'
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>\n'
            '</Relationships>'
        )
        zf.writestr(
            "ppt/presentation.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
            '  <p:sldIdLst>\n'
            '    <p:sldId id="256" r:id="rId1"/>\n'
            '  </p:sldIdLst>\n'
            '</p:presentation>'
        )
        zf.writestr(
            "ppt/_rels/presentation.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>\n'
            '</Relationships>'
        )
        zf.writestr(
            "ppt/slides/slide1.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">\n'
            '  <p:cSld>\n'
            '    <p:spTree>\n'
            '      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>\n'
            '      <p:grpSpPr/>\n'
            '    </p:spTree>\n'
            '  </p:cSld>\n'
            '</p:sld>'
        )
    return buf.getvalue()

def create_valid_csv() -> bytes:
    """Generate a valid, structured CSV file."""
    csv_text = (
        "TransactionID,Date,Description,Amount,Currency,Category\n"
        "TX-1001,2023-10-12,Cloud Server Hosting - Pro Tier,149.00,USD,Infrastructure\n"
        "TX-1002,2023-10-15,Domain DNS Services,18.50,USD,Domains\n"
        "TX-1003,2023-10-18,Database Automated Backups,42.00,USD,Storage\n"
        "TX-1004,2023-10-20,SSL Wildcard Certificate,79.00,USD,Security\n"
    )
    return csv_text.encode("utf-8")

def get_standard_sample_files() -> Dict[str, bytes]:
    """Returns a dictionary of filename -> valid file bytes for realistic sample dataset."""
    return {
        "document.pdf": create_valid_pdf(
            "Alex Morgan - Curriculum Vitae",
            [
                "Summary: Senior Full-Stack Software Engineer with 6+ years experience.",
                "Experience: Tech Lead at Acme Corp building scalable microservices.",
                "Education: B.S. in Computer Science - Honors.",
                "Skills: Python, TypeScript, React, PostgreSQL, Docker."
            ]
        ),
        "file.pdf": create_valid_pdf(
            "INVOICE #INV-2024-889",
            [
                "Vendor: Cloud Infrastructure & Hosting Services",
                "Bill To: Acme Technologies Inc.",
                "Amount Due: $450.00 USD - Due Date: Nov 15, 2024",
                "Services: Dedicated GPU compute and managed Redis cluster"
            ]
        ),
        "notes.docx": create_valid_docx(
            "CS50 Algorithms & Data Structures Study Notes",
            "Comprehensive lecture notes on binary search trees, time complexity O(log n), and asymptotic runtime analysis."
        ),
        "ambiguous_data.bin": b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09",
        "apollo_mission_proposal.docx": create_valid_docx(
            "Project Apollo - Mission Proposal and Architecture",
            "Detailed technical proposal, system architecture diagrams, and milestone schedule for Project Apollo."
        ),
        "apollo_budget.csv": (
            "Category,Phase,Item,EstimatedCost,Currency\n"
            "Hardware,Phase 1,Server Cluster Rack,12000,USD\n"
            "Software,Phase 1,Enterprise Licenses,4500,USD\n"
            "Testing,Phase 2,Security Audit,8000,USD\n"
        ).encode("utf-8"),
        "Invoice_Oct_final_v2_FINAL.pdf": create_valid_pdf("Monthly Cloud Hosting Invoice - October 2023"),
        "IMG_20231012_WA0004.jpg": create_valid_jpeg(),
        "draft_cs50_week3_notes.docx": create_valid_docx("CS50 Lecture 3: Algorithms and Binary Search", "Overview of search and sorting complexity."),
        "Screenshot 2024-03-01 at 4.22.19 PM.png": create_valid_png(),
        "w2_tax_return_2023.pdf": create_valid_pdf("Form W-2 Wage and Tax Statement 2023"),
        "q4_roadmap_presentation_team.pptx": create_valid_pptx("Q4 Product Roadmap & Goals"),
        "dump_users_export_v1_backup.csv": create_valid_csv(),
    }


def create_image_with_text(text: str, width: int = 900, height: int = 400, format: str = "PNG") -> bytes:
    """Generate a valid image with rendered visible text on a white canvas."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    y = 40
    for line in text.split("\n"):
        line_clean = line.strip()
        if line_clean:
            draw.text((40, y), line_clean, fill=(0, 0, 0))
            y += 35
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


def create_scanned_pdf(text: str, width: int = 900, height: int = 600) -> bytes:
    """Generate a valid PDF containing ONLY an image of the text without any extractable text stream."""
    import fitz
    img_bytes = create_image_with_text(text, width=width, height=height, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=float(width), height=float(height))
    rect = fitz.Rect(0, 0, float(width), float(height))
    page.insert_image(rect, stream=img_bytes)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_tshirt_image(format: str = "JPEG") -> bytes:
    """Generate a valid image depicting a recognizable T-shirt shape."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (320, 320), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    # T-shirt silhouette in navy blue with collar
    shirt_poly = [
        (110, 60), (140, 80), (180, 80), (210, 60),
        (260, 95), (235, 140), (205, 125), (205, 260),
        (115, 260), (115, 125), (85, 140), (60, 95)
    ]
    draw.polygon(shirt_poly, fill=(20, 40, 160), outline=(10, 20, 100))
    draw.arc([130, 50, 190, 85], start=0, end=180, fill=(240, 240, 240), width=3)
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


def create_abstract_noise_image(format: str = "JPEG") -> bytes:
    """Generate an abstract gradient pattern with no recognizable object."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (320, 320), color=(140, 140, 140))
    draw = ImageDraw.Draw(img)
    draw.ellipse([80, 80, 240, 240], fill=(155, 145, 150))
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()
