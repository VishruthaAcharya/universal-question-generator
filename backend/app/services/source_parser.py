from typing import Any
from app.services.source_reader import read_source_pages
from app.services.azure_openai import extract_questions_from_text, extract_questions_from_image

def parse_source_document(path: str) -> list[dict[str, Any]]:
    """
    Parses the source document by:
    1. Performing deterministic text/image extraction page-by-page.
    2. Passing the structured page chunks to Azure OpenAI for semantic parsing/OCR.
    3. Combining all extracted questions.
    """
    pages = read_source_pages(path)
    all_questions = []
    
    for page in pages:
        page_num = page["page_number"]
        page_type = page["type"]
        content = page["content"]
        
        if page_type == "text":
            # If text is empty or only whitespace, skip or treat as image (already handled in source_reader)
            if not str(content).strip():
                continue
            questions = extract_questions_from_text(str(content), page_num)
        else:
            # Scanned document or image file
            questions = extract_questions_from_image(content, page_num)
            
        all_questions.extend(questions)
        
    return all_questions
