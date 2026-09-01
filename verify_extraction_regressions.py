import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from tests.test_layout_extractor_regressions import (
    test_mcq_with_metadata_numbered_stem,
    test_mcq_with_metadata_unnumbered_stem,
    test_normal_numbered_questions,
    test_questions_split_across_pages,
    test_coding_questions_without_options,
    test_multiple_questions_on_one_page,
    test_question_followed_by_options,
    test_metadata_before_stem_with_question_number
)
from app.services.source_parser import parse_source_document

def run_all():
    tests = [
        ("MCQ with metadata + numbered stem", test_mcq_with_metadata_numbered_stem),
        ("MCQ with metadata + unnumbered stem", test_mcq_with_metadata_unnumbered_stem),
        ("Normal numbered questions", test_normal_numbered_questions),
        ("Questions split across pages", test_questions_split_across_pages),
        ("Coding questions without options", test_coding_questions_without_options),
        ("Multiple questions on one page", test_multiple_questions_on_one_page),
        ("Question followed by options", test_question_followed_by_options),
        ("Metadata before stem with question number", test_metadata_before_stem_with_question_number),
    ]

    print("Running Regression Test Suite...")
    passed = 0
    for name, test_func in tests:
        try:
            test_func()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            raise

    # Test PDF fixtures if available
    pdf_fixtures = [
        ("questionsB2_assessment.pdf", 9),
        ("Amazon_MCQ_Set_1_Bulk_Upload.pdf", 30)
    ]
    for pdf_name, expected_count in pdf_fixtures:
        if os.path.exists(pdf_name):
            try:
                qs = parse_source_document(pdf_name)
                print(f"  [PDF FIXTURE] {pdf_name}: Extracted {len(qs)} questions (expected {expected_count})")
                assert len(qs) == expected_count, f"Expected {expected_count} questions, got {len(qs)}"
                print(f"  [PASS] PDF Fixture: {pdf_name}")
                passed += 1
            except Exception as e:
                print(f"  [FAIL] PDF Fixture {pdf_name}: {e}")
                raise

    print(f"\nAll {passed} tests passed successfully!")

if __name__ == "__main__":
    run_all()
