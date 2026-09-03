import pytest
from app.services.answer_key_detector import extract_answer_key_entries
from app.services.reconciliation_engine import reconcile_questions_and_answers, are_groups_compatible

def test_cross_image_answer_key_extraction():
    """
    Verifies that answer key text containing explicit IMAGE 1, IMAGE 2, IMAGE 3 headers
    is correctly parsed into grouped answer key entries preserving section headers.
    """
    answer_text = """
    IMAGE 1
    Q1 = 60 km/h
    Q2 = 180
    Q3 = 120 cm²
    Q4 = 4590
    Q5 = 25%

    IMAGE 2
    Q1 = 40 years
    Q2 = No change
    Q3 = 7.2 days
    Q4 = 210
    Q5 = 11
    Q6 = 10%
    Q7 = 24 seconds
    Q8 = 47.142857 (≈ 47.14)

    IMAGE 3
    Q1 = 5% decrease
    Q2 = 18
    Q3 = 4 km/h
    Q4 = 40
    Q5 = ₹1050
    Q6 = All squares are rectangles.
    """
    entries = extract_answer_key_entries(answer_text, page_number=4, chapter_name="answer_key.png")
    assert len(entries) == 19, f"Expected 19 total answer entries across 3 images, got {len(entries)}"

    img1_entries = [e for e in entries if "IMAGE 1" in str(e.get("source_chapter") or e.get("answer_key_group"))]
    img2_entries = [e for e in entries if "IMAGE 2" in str(e.get("source_chapter") or e.get("answer_key_group"))]
    img3_entries = [e for e in entries if "IMAGE 3" in str(e.get("source_chapter") or e.get("answer_key_group"))]

    assert len(img1_entries) == 5, f"Expected 5 entries in IMAGE 1, got {len(img1_entries)}"
    assert len(img2_entries) == 8, f"Expected 8 entries in IMAGE 2, got {len(img2_entries)}"
    assert len(img3_entries) == 6, f"Expected 6 entries in IMAGE 3, got {len(img3_entries)}"

    # Check distinct Q1 answers across the 3 groups
    q1_img1 = next(e for e in img1_entries if e["question_number"] == 1)
    q1_img2 = next(e for e in img2_entries if e["question_number"] == 1)
    q1_img3 = next(e for e in img3_entries if e["question_number"] == 1)

    assert q1_img1["answer"] == "60 km/h"
    assert q1_img2["answer"] == "40 years"
    assert q1_img3["answer"] == "5% decrease"


def test_cross_image_grouped_reconciliation():
    """
    Verifies that when multiple question images contain repeated question numbers (Q1, Q2, etc.),
    the reconciliation engine maps each question to its corresponding IMAGE section
    and never globally mixes or overwrites them.
    """
    # 1. Question Image 1 -> Q1 to Q6
    img1_questions = [
        {
            "question_id": f"IMG1_Q{i}",
            "question_number": i,
            "question": f"Question Image 1 Stem {i}?",
            "source_file": "question_image_1.png",
            "question_source_image": "question_image_1.png",
            "question_group": "IMAGE 1",
            "source_page": 1,
            "options": ["Opt A", "Opt B", "Opt C", "Opt D"]
        }
        for i in range(1, 7)
    ]

    # 2. Question Image 2 -> Q1 to Q5
    img2_questions = [
        {
            "question_id": f"IMG2_Q{i}",
            "question_number": i,
            "question": f"Question Image 2 Stem {i}?",
            "source_file": "question_image_2.png",
            "question_source_image": "question_image_2.png",
            "question_group": "IMAGE 2",
            "source_page": 1,
            "options": ["Opt A", "Opt B", "Opt C", "Opt D"]
        }
        for i in range(1, 6)
    ]

    # 3. Question Image 3 -> Q1 to Q8
    img3_questions = [
        {
            "question_id": f"IMG3_Q{i}",
            "question_number": i,
            "question": f"Question Image 3 Stem {i}?",
            "source_file": "question_image_3.png",
            "question_source_image": "question_image_3.png",
            "question_group": "IMAGE 3",
            "source_page": 1,
            "options": ["Opt A", "Opt B", "Opt C", "Opt D"]
        }
        for i in range(1, 9)
    ]

    all_questions = img1_questions + img2_questions + img3_questions

    # 4. Answers with explicit IMAGE 1, IMAGE 2, IMAGE 3 sections
    answers = [
        # IMAGE 1
        {"question_number": 1, "answer": "60 km/h", "source_file": "answer_key.png", "answer_key_group": "IMAGE 1", "source_chapter": "IMAGE 1"},
        {"question_number": 2, "answer": "180", "source_file": "answer_key.png", "answer_key_group": "IMAGE 1", "source_chapter": "IMAGE 1"},
        {"question_number": 3, "answer": "120 cm²", "source_file": "answer_key.png", "answer_key_group": "IMAGE 1", "source_chapter": "IMAGE 1"},
        {"question_number": 4, "answer": "4590", "source_file": "answer_key.png", "answer_key_group": "IMAGE 1", "source_chapter": "IMAGE 1"},
        {"question_number": 5, "answer": "25%", "source_file": "answer_key.png", "answer_key_group": "IMAGE 1", "source_chapter": "IMAGE 1"},
        
        # IMAGE 2
        {"question_number": 1, "answer": "40 years", "source_file": "answer_key.png", "answer_key_group": "IMAGE 2", "source_chapter": "IMAGE 2"},
        {"question_number": 2, "answer": "No change", "source_file": "answer_key.png", "answer_key_group": "IMAGE 2", "source_chapter": "IMAGE 2"},
        {"question_number": 3, "answer": "7.2 days", "source_file": "answer_key.png", "answer_key_group": "IMAGE 2", "source_chapter": "IMAGE 2"},
        {"question_number": 4, "answer": "210", "source_file": "answer_key.png", "answer_key_group": "IMAGE 2", "source_chapter": "IMAGE 2"},
        {"question_number": 5, "answer": "11", "source_file": "answer_key.png", "answer_key_group": "IMAGE 2", "source_chapter": "IMAGE 2"},
        {"question_number": 6, "answer": "10%", "source_file": "answer_key.png", "answer_key_group": "IMAGE 2", "source_chapter": "IMAGE 2"},
        {"question_number": 7, "answer": "24 seconds", "source_file": "answer_key.png", "answer_key_group": "IMAGE 2", "source_chapter": "IMAGE 2"},
        {"question_number": 8, "answer": "47.142857 (≈ 47.14)", "source_file": "answer_key.png", "answer_key_group": "IMAGE 2", "source_chapter": "IMAGE 2"},

        # IMAGE 3
        {"question_number": 1, "answer": "5% decrease", "source_file": "answer_key.png", "answer_key_group": "IMAGE 3", "source_chapter": "IMAGE 3"},
        {"question_number": 2, "answer": "18", "source_file": "answer_key.png", "answer_key_group": "IMAGE 3", "source_chapter": "IMAGE 3"},
        {"question_number": 3, "answer": "4 km/h", "source_file": "answer_key.png", "answer_key_group": "IMAGE 3", "source_chapter": "IMAGE 3"},
        {"question_number": 4, "answer": "40", "source_file": "answer_key.png", "answer_key_group": "IMAGE 3", "source_chapter": "IMAGE 3"},
        {"question_number": 5, "answer": "₹1050", "source_file": "answer_key.png", "answer_key_group": "IMAGE 3", "source_chapter": "IMAGE 3"},
        {"question_number": 6, "answer": "All squares are rectangles.", "source_file": "answer_key.png", "answer_key_group": "IMAGE 3", "source_chapter": "IMAGE 3"},
    ]

    reconciled = reconcile_questions_and_answers(all_questions, answers)
    assert len(reconciled) == 19

    # Verify 3 separate Q1 records
    q1_records = [q for q in reconciled if q["question_number"] == 1]
    assert len(q1_records) == 3

    # Check each Q1 received its own group's answer
    q1_1 = next(q for q in q1_records if q["source_file"] == "question_image_1.png")
    q1_2 = next(q for q in q1_records if q["source_file"] == "question_image_2.png")
    q1_3 = next(q for q in q1_records if q["source_file"] == "question_image_3.png")

    assert q1_1["source_answer_text"] == "60 km/h"
    assert q1_1["answer_key_group"] == "IMAGE 1"
    assert q1_1["mapping_method"] in ("EXPLICIT", "EXPLICIT_GROUPED")
    assert q1_1["mapping_confidence"] == "HIGH"
    assert q1_1["question_source_image"] == "question_image_1.png"

    assert q1_2["source_answer_text"] == "40 years"
    assert q1_2["answer_key_group"] == "IMAGE 2"
    assert q1_2["mapping_method"] in ("EXPLICIT", "EXPLICIT_GROUPED")
    assert q1_2["mapping_confidence"] == "HIGH"

    assert q1_3["source_answer_text"] == "5% decrease"
    assert q1_3["answer_key_group"] == "IMAGE 3"
    assert q1_3["mapping_method"] in ("EXPLICIT", "EXPLICIT_GROUPED")
    assert q1_3["mapping_confidence"] == "HIGH"

    # Check Q2 records
    q2_records = [q for q in reconciled if q["question_number"] == 2]
    assert len(q2_records) == 3
    q2_1 = next(q for q in q2_records if q["source_file"] == "question_image_1.png")
    q2_2 = next(q for q in q2_records if q["source_file"] == "question_image_2.png")
    q2_3 = next(q for q in q2_records if q["source_file"] == "question_image_3.png")

    assert q2_1["source_answer_text"] == "180"
    assert q2_2["source_answer_text"] == "No change"
    assert q2_3["source_answer_text"] == "18"

    # Check Q6 records (Image 1 has Q6, but Image 1 answer key only had Q1-Q5. Image 3 has Q6 = All squares are rectangles.)
    # Image 1 Q6 must NOT steal Image 3 Q6!
    q6_1 = next(q for q in reconciled if q["question_id"] == "IMG1_Q6")
    q6_3 = next(q for q in reconciled if q["question_id"] == "IMG3_Q6")

    assert q6_3["source_answer_text"] == "All squares are rectangles."
    assert q6_3["answer_key_group"] == "IMAGE 3"

    # Image 1 Q6 has no answer in IMAGE 1 answer key -> must NOT steal Image 2 or Image 3 Q6!
    assert q6_1["source_answer_key"] is None or q6_1["answer_mapping_method"] in ("AMBIGUOUS", "UNRESOLVED")
    assert q6_1["review_required"] is True
