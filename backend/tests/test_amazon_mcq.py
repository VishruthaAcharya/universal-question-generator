import os
import sys
from pprint import pprint

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.source_parser import parse_source_document

import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.source_reader import read_source_pages
from app.services.layout_extractor import extract_questions_from_page_layout
from app.services.source_parser import parse_source_document

def run_amazon_test():
    pdf_path = os.path.join(os.path.dirname(__file__), "..", "storage", "uploads", "Amazon_MCQ_Set_1_Bulk_Upload(1).pdf")
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found.")
        return

    print("=== Per Page Diagnostic ===")
    pages = read_source_pages(pdf_path)
    active_section = "General"
    active_marks = None
    for p in pages:
        p_num = p["page_number"]
        if p["type"] == "text":
            qs, active_section, active_marks = extract_questions_from_page_layout(p["content"], p_num, active_section, active_marks)
            print(f"Page {p_num}: Deterministic extracted = {len(qs)}")
        else:
            print(f"Page {p_num}: Visual / Image page")

    print("\nParsing full document...")
    questions = parse_source_document(pdf_path)
    print(f"Total questions detected: {len(questions)}")

    inspect_indices = [1, 8, 17, 24, 27, 30]
    for idx in inspect_indices:
        if idx <= len(questions):
            q = questions[idx - 1]
            print("=" * 60)
            print(f"QUESTION {idx}: (ID: {q.get('question_id')}, Number: {q.get('question_number')})")
            print(f"Page: {q.get('source_page')}")
            print(f"Stem: {q.get('question')[:200]}...")
            print("Options:")
            print(f"  A: {q.get('option_a')}")
            print(f"  B: {q.get('option_b')}")
            print(f"  C: {q.get('option_c')}")
            print(f"  D: {q.get('option_d')}")
            print(f"Source Answer: {q.get('source_answer')} (Key: {q.get('source_answer_key')}, Text: {q.get('source_answer_text')})")
            print(f"Correct Answer: {q.get('correct_answer')}")
            print(f"Validation Status: {q.get('status')}")
            if "extraction_defects" in q:
                print(f"Defects: {q.get('extraction_defects')}")
        else:
            print(f"Question {idx} out of range.")

if __name__ == "__main__":
    run_amazon_test()


if __name__ == "__main__":
    run_amazon_test()
