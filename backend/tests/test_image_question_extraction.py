import os
import io
import zipfile
import pytest
from PIL import Image, ImageDraw
import fitz
from app.services.source_reader import read_source_pages, extract_image_with_ocr_fallback
from app.services.source_parser import parse_source_document, parse_source_batch
from app.services.layout_extractor import extract_questions_from_page_layout
from app.services.zip_processor import process_and_extract_zip

def create_sample_mcq_image(format="PNG") -> bytes:
    """Creates a sample MCQ image in memory."""
    img = Image.new("RGB", (800, 600), color="white")
    draw = ImageDraw.Draw(img)
    text = (
        "1. What is the primary function of an operating system kernel?\n"
        "A. Managing hardware resources and system calls\n"
        "B. Providing user graphical interface\n"
        "C. Compiling source code to machine binaries\n"
        "D. Formatting hard drive disks\n\n"
        "2. Which protocol operates at the Transport Layer of the OSI model?\n"
        "A. IP\n"
        "B. TCP\n"
        "C. HTTP\n"
        "D. DNS\n"
    )
    draw.text((40, 40), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()

# 1. Test One Direct PNG Image
def test_direct_png_extraction(tmp_path):
    img_bytes = create_sample_mcq_image("PNG")
    img_path = str(tmp_path / "test_question.png")
    with open(img_path, "wb") as f:
        f.write(img_bytes)

    pages = read_source_pages(img_path)
    assert len(pages) == 1
    p = pages[0]
    assert p["page_number"] == 1
    assert p["extraction_method"] == "OCR"
    assert p["has_visual"] is True

    # If local OCR is available, content is text; if not, image bytes are queued for vision OCR
    if p["type"] == "text":
        qs, _, _ = extract_questions_from_page_layout(p["content"], page_number=1)
        assert len(qs) >= 1
        assert len(qs[0]["options"]) == 4

# 2. Test One Direct JPG Image
def test_direct_jpg_extraction(tmp_path):
    img_bytes = create_sample_mcq_image("JPEG")
    img_path = str(tmp_path / "sample_test.jpg")
    with open(img_path, "wb") as f:
        f.write(img_bytes)

    pages = read_source_pages(img_path)
    assert len(pages) == 1
    p = pages[0]
    assert p["page_number"] == 1
    assert p["extraction_method"] == "OCR"
    assert p["has_visual"] is True

# 3. Test ZIP Containing Multiple PNGs
def test_zip_multiple_pngs(tmp_path):
    zip_path = str(tmp_path / "questions_png_bundle.zip")
    extract_dir = str(tmp_path / "extracted_pngs")
    
    img1_bytes = create_sample_mcq_image("PNG")
    img2_bytes = create_sample_mcq_image("PNG")

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("page1.png", img1_bytes)
        zf.writestr("page2.png", img2_bytes)

    res = process_and_extract_zip(zip_path, extract_dir, parent_zip_name="questions_png_bundle.zip")
    assert len(res["extracted_files"]) == 2
    
    for item in res["extracted_files"]:
        pages = read_source_pages(item["absolute_path"])
        assert len(pages) == 1
        assert pages[0]["extraction_method"] == "OCR"

# 4. Test ZIP Containing Mixed PNG/JPG
def test_zip_mixed_png_jpg(tmp_path):
    zip_path = str(tmp_path / "mixed_images.zip")
    extract_dir = str(tmp_path / "extracted_mixed")

    png_bytes = create_sample_mcq_image("PNG")
    jpg_bytes = create_sample_mcq_image("JPEG")

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("question_sheet_1.png", png_bytes)
        zf.writestr("question_sheet_2.jpg", jpg_bytes)

    res = process_and_extract_zip(zip_path, extract_dir, parent_zip_name="mixed_images.zip")
    assert len(res["extracted_files"]) == 2
    for item in res["extracted_files"]:
        pages = read_source_pages(item["absolute_path"])
        assert len(pages) == 1
        assert pages[0]["extraction_method"] == "OCR"

# 5. Test ZIP Containing Mixed PDF + Images
def test_zip_pdf_and_images(tmp_path):
    zip_path = str(tmp_path / "pdf_and_images.zip")
    extract_dir = str(tmp_path / "extracted_pdf_images")

    # Create a small text PDF
    pdf_doc = fitz.open()
    page = pdf_doc.new_page()
    page.insert_text((50, 50), "1. What is Python?\nA. A snake\nB. A language\nC. A car\nD. A planet\nAnswer: B")
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()

    png_bytes = create_sample_mcq_image("PNG")

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("assessment_part1.pdf", pdf_bytes)
        zf.writestr("assessment_part2.png", png_bytes)

    res = process_and_extract_zip(zip_path, extract_dir, parent_zip_name="pdf_and_images.zip")
    assert len(res["extracted_files"]) == 2

    # Verify both the PDF and Image are read properly
    files_by_name = {os.path.basename(f["absolute_path"]): f for f in res["extracted_files"]}
    
    pdf_pages = read_source_pages(files_by_name["assessment_part1.pdf"]["absolute_path"])
    assert len(pdf_pages) == 1
    assert pdf_pages[0]["extraction_method"] == "native_text"

    img_pages = read_source_pages(files_by_name["assessment_part2.png"]["absolute_path"])
    assert len(img_pages) == 1
    assert img_pages[0]["extraction_method"] == "OCR"

# 6. Test Question Boundary Detection on Standard MCQ Format
def test_mcq_format_without_literal_word_question():
    """Verify that question detection does not require the literal word 'Question' and does not rely solely on '?'."""
    text = (
        "1. Identify the primary sorting algorithm with average O(n log n) complexity\n"
        "A. Quick Sort\n"
        "B. Bubble Sort\n"
        "C. Insertion Sort\n"
        "D. Selection Sort\n\n"
        "2. State the default port used by HTTP web traffic\n"
        "A. 22\n"
        "B. 80\n"
        "C. 443\n"
        "D. 8080\n"
    )
    questions, _, _ = extract_questions_from_page_layout(text, page_number=1)
    assert len(questions) == 2
    
    q1 = questions[0]
    assert q1["question_number"] == 1
    assert q1["question"].startswith("Identify the primary sorting algorithm")
    assert len(q1["options"]) == 4
    assert q1["option_a"] == "Quick Sort"
    assert q1["option_b"] == "Bubble Sort"
    
    q2 = questions[1]
    assert q2["question_number"] == 2
    assert q2["question"].startswith("State the default port used by HTTP web traffic")
    assert len(q2["options"]) == 4
    assert q2["option_b"] == "80"
