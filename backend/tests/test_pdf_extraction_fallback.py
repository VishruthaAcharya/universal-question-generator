import os
import pytest
import fitz
from app.services.source_reader import (
    evaluate_text_quality,
    read_source_pages,
    extract_page_with_ocr_fallback
)
from app.services.layout_extractor import extract_questions_from_page_layout
from app.services.source_parser import parse_source_document, compute_extraction_statistics

# 1. Test Quality Evaluation Logic
def test_text_quality_evaluation():
    # Good text
    usable, score, metrics = evaluate_text_quality(
        "1. What is the output of the following Python expression?\n"
        "(a) 10 (b) 20 (c) 30 (d) 40\n"
        "Topic: Python Programming | Difficulty: Medium"
    )
    assert usable is True
    assert score >= 0.80
    assert metrics["word_count"] >= 5
    assert metrics["alphanumeric_ratio"] >= 0.60

    # Empty / whitespace text
    usable_empty, score_empty, _ = evaluate_text_quality("   \n\t  ")
    assert usable_empty is False
    assert score_empty == 0.0

    # CID / corrupted glyph garbage
    usable_garbage, score_garbage, _ = evaluate_text_quality(
        "(cid:12)(cid:45)(cid:88)(cid:90)(cid:11)(cid:22)\ufffd\ufffd\ufffd\x00\x01\x02"
    )
    assert usable_garbage is False
    assert score_garbage < 0.30

# 2. Test Working Text-Based PDF (Native Extraction)
def test_working_text_pdf(tmp_path):
    pdf_path = str(tmp_path / "text_sample.pdf")
    doc = fitz.open()
    
    # Page 1: Text MCQ
    page1 = doc.new_page()
    page1.insert_text(
        (50, 72),
        "QUANTITATIVE APTITUDE\n"
        "General Aptitude\n"
        "MEDIUM\n\n"
        "1. A train running at 72 km/h crosses a 200m platform in 25 seconds. What is the length of the train?\n"
        "(a) 300m\n"
        "(b) 400m\n"
        "(c) 500m\n"
        "(d) 250m\n\n"
        "Answer: (a)\n"
    )
    
    # Page 2: Text MCQ
    page2 = doc.new_page()
    page2.insert_text(
        (50, 72),
        "TECHNICAL APTITUDE\n"
        "Computer Science\n"
        "EASY\n\n"
        "2. Which data structure uses FIFO (First In First Out) ordering?\n"
        "(a) Stack\n"
        "(b) Queue\n"
        "(c) Tree\n"
        "(d) Graph\n\n"
        "Answer: (b)\n"
    )
    doc.save(pdf_path)
    doc.close()

    pages = read_source_pages(pdf_path)
    assert len(pages) == 2
    
    # Verify both pages used native text extraction
    for p in pages:
        assert p["type"] == "text"
        assert p["extraction_method"] == "native_text"
        assert p["text_quality_score"] >= 0.80
        assert p["character_count"] > 50

    # Extract questions
    qs1, sec1, _ = extract_questions_from_page_layout(
        pages[0]["content"],
        page_number=1,
        extraction_method=pages[0]["extraction_method"],
        text_quality_score=pages[0]["text_quality_score"],
        character_count=pages[0]["character_count"]
    )
    assert len(qs1) == 1
    q1 = qs1[0]
    assert q1["question_number"] == 1
    # Verify header metadata was NOT added to stem
    assert "QUANTITATIVE APTITUDE" not in q1["question"]
    assert "General Aptitude" not in q1["question"]
    assert "MEDIUM" not in q1["question"]
    assert q1["question"].startswith("A train running at 72 km/h")
    assert len(q1["options"]) == 4
    assert q1["option_a"] == "300m"
    assert q1["extraction_method"] == "native_text"

# 3. Test Scanned/Image PDF (OCR Fallback)
def test_scanned_image_pdf(tmp_path):
    pdf_path = str(tmp_path / "scanned_sample.pdf")
    
    # Create an image-only PDF page by rendering a bitmap with no text stream
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    # Draw a rectangle to ensure there are image/drawings but zero text
    page.draw_rect(fitz.Rect(50, 50, 350, 250), color=(0.2, 0.4, 0.8), fill=(0.9, 0.9, 0.9))
    doc.save(pdf_path)
    doc.close()

    pages = read_source_pages(pdf_path)
    assert len(pages) == 1
    p = pages[0]
    assert p["page_number"] == 1
    assert p["extraction_method"] == "OCR"

# 4. Test Mixed PDF (Page 1 Text, Page 2 Scanned Image, Page 3 Text)
def test_mixed_pdf(tmp_path):
    pdf_path = str(tmp_path / "mixed_sample.pdf")
    doc = fitz.open()
    
    # Page 1: Native text
    p1 = doc.new_page()
    p1.insert_text(
        (50, 72),
        "1. What is the time complexity of binary search in a sorted array?\n"
        "(a) O(1) (b) O(log n) (c) O(n) (d) O(n log n)\nAnswer: B"
    )
    
    # Page 2: Scanned image only (no text layer)
    p2 = doc.new_page(width=400, height=300)
    p2.draw_rect(fitz.Rect(20, 20, 380, 280), color=(0.1, 0.1, 0.1), fill=(0.95, 0.95, 0.95))
    
    # Page 3: Native text
    p3 = doc.new_page()
    p3.insert_text(
        (50, 72),
        "3. Which protocol is used for secure communication over the web?\n"
        "(a) HTTP (b) HTTPS (c) FTP (d) SMTP\nAnswer: B"
    )
    doc.save(pdf_path)
    doc.close()

    pages = read_source_pages(pdf_path)
    assert len(pages) == 3
    
    # Page 1: native_text
    assert pages[0]["page_number"] == 1
    assert pages[0]["type"] == "text"
    assert pages[0]["extraction_method"] == "native_text"
    assert pages[0]["text_quality_score"] >= 0.80

    # Page 2: OCR
    assert pages[1]["page_number"] == 2
    assert pages[1]["extraction_method"] == "OCR"

    # Page 3: native_text
    assert pages[2]["page_number"] == 3
    assert pages[2]["type"] == "text"
    assert pages[2]["extraction_method"] == "native_text"
    assert pages[2]["text_quality_score"] >= 0.80

# 5. Test Multi-Page MCQ PDF Header & Option Integrity
def test_multipage_mcq_header_isolation(tmp_path):
    pdf_path = str(tmp_path / "mcq_headers.pdf")
    doc = fitz.open()
    
    p1 = doc.new_page()
    p1.insert_text(
        (50, 50),
        "SECTION - A (GENERAL APTITUDE)\n"
        "QUANTITATIVE REASONING\n"
        "DIFFICULTY: HARD\n"
        "Marks: 2\n\n"
        "Question 1:\n"
        "Two pipes A and B can fill a tank in 20 and 30 minutes respectively. Both pipes are opened together. After how much time should pipe B be closed so that the tank is full in 15 minutes?\n"
        "A. 6 minutes\n"
        "B. 7.5 minutes\n"
        "C. 8 minutes\n"
        "D. 10 minutes\n\n"
        "Answer: B. 7.5 minutes\n"
    )
    doc.save(pdf_path)
    doc.close()

    pages = read_source_pages(pdf_path)
    assert len(pages) == 1
    qs, sec, marks = extract_questions_from_page_layout(pages[0]["content"], page_number=1)
    assert len(qs) == 1
    q = qs[0]
    
    # Verify stem starts at the actual question and headers are stripped
    assert "SECTION - A" not in q["question"]
    assert "QUANTITATIVE REASONING" not in q["question"]
    assert "DIFFICULTY: HARD" not in q["question"]
    assert "Question 1:" not in q["question"]
    assert q["question"].startswith("Two pipes A and B can fill a tank")
    
    # Verify options are correctly attached
    assert len(q["options"]) == 4
    assert q["option_a"] == "6 minutes"
    assert q["option_b"] == "7.5 minutes"
    assert q["option_c"] == "8 minutes"
    assert q["option_d"] == "10 minutes"
    assert "7.5 minutes" in q["correct_answer"]
    assert q["difficulty"] == "HARD"
    assert q["marks"] == "2"

# 6. Test Amazon Coding PDF Diagnostics
def test_amazon_coding_pdf_page_diagnostics():
    pdf_path = os.path.join("storage", "uploads", "Amazon_MCQ_Set_1_Bulk_Upload(1).pdf")
    if not os.path.exists(pdf_path):
        pytest.skip(f"Amazon test file {pdf_path} not found")

    pages = read_source_pages(pdf_path)
    assert len(pages) == 10
    
    # Verify expected methods per page for mixed PDF
    text_pages = [1, 2, 3, 5, 6, 7, 9]
    ocr_pages = [4, 8, 10]

    for p in pages:
        p_num = p["page_number"]
        if p_num in text_pages:
            assert p["extraction_method"] == "native_text"
            assert p["text_quality_score"] >= 0.80
            assert p["character_count"] > 500
        elif p_num in ocr_pages:
            assert p["extraction_method"] == "OCR"
