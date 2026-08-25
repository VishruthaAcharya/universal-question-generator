import pytest
from app.services.layout_extractor import (
    extract_questions_from_page_layout,
    parse_subparts,
    extract_section_and_marks
)
from app.services.option_extractor import extract_options_and_stem
from app.services.question_classifier import classify_question_type
from app.services.source_parser import compute_extraction_statistics

# 1. Test MCQ with 4 Horizontal Options (Tollens Reagent)
def test_tollens_reagent_mcq_extraction():
    text = """
    PART - A (MCQs)
    1. Tollens reagent is a
    (a) Silver nitrate solution (b) Ammonical silver nitrate solution
    (c) Ammonium nitrate solution (d) Silver chloride solution
    """
    questions, section, marks = extract_questions_from_page_layout(text, page_number=1)
    assert len(questions) == 1
    q = questions[0]
    assert q["question_number"] == 1
    assert q["sequence_id"] == "MCQ-001"
    assert q["question_type"] == "MCQ"
    assert "Tollens reagent is a" in q["question"]
    assert len(q["options"]) == 4
    assert q["option_a"] == "Silver nitrate solution"
    assert q["option_b"] == "Ammonical silver nitrate solution"
    assert q["option_c"] == "Ammonium nitrate solution"
    assert q["option_d"] == "Silver chloride solution"
    assert q["extraction_completeness"] == 1.0

# 2. Test Multiline Vertically Formatted MCQ
def test_multiline_vertical_mcq_extraction():
    text = """
    2. Cannizzaro's reaction is not given by
    (a) Formaldehyde
    (b) Benzaldehyde
    (c) Acetaldehyde
    (d) Trimethyl acetaldehyde
    """
    questions, section, marks = extract_questions_from_page_layout(text, page_number=1, current_section="PART-A (MCQs)")
    assert len(questions) == 1
    q = questions[0]
    assert q["question_number"] == 2
    assert q["sequence_id"] == "MCQ-002"
    assert len(q["options"]) == 4
    assert q["option_c"] == "Acetaldehyde"

# 3. Test Repeated Question Numbers Across Sections (MCQs vs 2 Marks vs 5 Marks)
def test_repeated_numbering_across_sections():
    # Page 1: MCQs
    page1_text = """
    SECTION A: MCQs (1 Mark each)
    1. Reagent used in Stephen reaction is
    (a) SnCl2 + HCl (b) NaBH4 (c) LiAlH4 (d) H2/Pd
    2. Which of the following has highest boiling point?
    (a) CH3CHO (b) CH3CH2OH (c) CH3COOH (d) CH3OCH3
    """
    qs_p1, sec1, marks1 = extract_questions_from_page_layout(page1_text, page_number=1)
    assert len(qs_p1) == 2
    assert qs_p1[0]["sequence_id"] == "MCQ-001"
    assert qs_p1[1]["sequence_id"] == "MCQ-002"

    # Page 3: 2 Marks Questions (Numbers reset to 1, 2)
    page3_text = """
    PART - C (2 MARKS QUESTIONS)
    1. Explain Rosenmund's reduction of benzoyl chloride.
    2. Write the IUPAC name of CH3-CH=CH-CHO.
    """
    qs_p3, sec3, marks3 = extract_questions_from_page_layout(page3_text, page_number=3, current_section=sec1, current_marks=marks1)
    assert len(qs_p3) == 2
    assert qs_p3[0]["question_number"] == 1
    assert qs_p3[0]["sequence_id"] == "2M-001"
    assert qs_p3[0]["question_type"] == "SHORT_ANSWER"
    assert qs_p3[0]["marks"] == "2"
    assert qs_p3[1]["sequence_id"] == "2M-002"
    assert qs_p3[1]["question_type"] == "SHORT_ANSWER"

    # Page 5: 5 Marks Questions (Numbers reset to 1)
    page5_text = """
    PART - D (5 MARKS QUESTIONS)
    1. a) How is benzoyl chloride converted into benzaldehyde?
       b) Write a general equation for Hell-Volhard-Zelinsky (HVZ) reaction.
       c) Complete the reaction: CH3CHO + HCN -> ?
    """
    qs_p5, sec5, marks5 = extract_questions_from_page_layout(page5_text, page_number=5, current_section=sec3, current_marks=marks3)
    assert len(qs_p5) == 1
    q5 = qs_p5[0]
    assert q5["question_number"] == 1
    assert q5["sequence_id"] == "5M-001"
    assert q5["question_type"] == "LONG_ANSWER"
    assert q5["marks"] == "5"
    assert len(q5["subparts"]) == 3
    assert q5["subparts"][0]["label"] == "a"
    assert q5["subparts"][1]["label"] == "b"
    assert q5["subparts"][2]["label"] == "c"

# 4. Test Reaction Completion Question Classification
def test_reaction_completion_classification():
    text = "Complete the following reaction: C6H5CHO + H2N-NH2 -> ?"
    q_type, completeness, status = classify_question_type(text, options=[], marks=2)
    assert q_type == "REACTION_COMPLETION"
    assert status == "COMPLETE"
    assert completeness >= 0.90

# 5. Test Non-MCQ Short Answer Question (Explain Cannizzaro Reaction)
def test_short_answer_question_no_options():
    text = "Explain Cannizzaro's reaction with an example."
    q_type, completeness, status = classify_question_type(text, options=[], marks=2)
    assert q_type == "SHORT_ANSWER"
    assert completeness >= 0.85

# 6. Test Fill in the Blanks Question
def test_fill_in_the_blanks():
    text = "Formalin is a 40% aqueous solution of _______."
    q_type, completeness, status = classify_question_type(text, options=[], section_name="FILL IN THE BLANKS")
    assert q_type == "FILL_IN_THE_BLANK"

# 7. Test Extraction Statistics Aggregation
def test_extraction_statistics_calculation():
    sample_questions = [
        {"question_type": "MCQ", "extraction_completeness": 1.0, "status": "COMPLETE"},
        {"question_type": "MCQ", "extraction_completeness": 1.0, "status": "COMPLETE"},
        {"question_type": "SHORT_ANSWER", "extraction_completeness": 0.9, "status": "COMPLETE"},
        {"question_type": "LONG_ANSWER", "extraction_completeness": 0.95, "status": "COMPLETE"},
        {"question_type": "REACTION_COMPLETION", "extraction_completeness": 0.9, "status": "COMPLETE"},
    ]
    stats = compute_extraction_statistics(
        questions=sample_questions,
        pages_count=7,
        elapsed_ms=320.5,
        visual_pages_count=2
    )
    assert stats["pages_processed"] == 7
    assert stats["total_questions_detected"] == 5
    assert stats["mcqs_detected"] == 2
    assert stats["short_answer"] == 1
    assert stats["long_answer"] == 1
    assert stats["diagram_reaction_questions"] == 1
    assert stats["average_extraction_confidence"] >= 0.90
