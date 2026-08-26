from typing import Any
from app.services.template import normalize_field_name

INFERRABLE_FIELDS = {"topic", "subtopic", "difficulty", "score"}

def validate_compatibility(template_schema: dict[str, Any], parsed_questions: list[dict[str, Any]]) -> dict[str, Any]:
    errors = []
    warnings = []
    
    # Get all columns from template
    columns = template_schema.get("column_schema", [])
    
    # Gather all fields present in the source (both original and normalized)
    source_fields = set()
    if parsed_questions:
        for q in parsed_questions:
            for k, v in q.items():
                if k not in ("options", "source_page"):
                    # We add the field regardless of whether the cell value is empty or not
                    # to validate structure separately from cell-value validation
                    source_fields.add(k)
                    source_fields.add(normalize_field_name(k))

    for col in columns:
        orig = col["original_name"]
        norm = col["normalized_name"]
        is_required = col["required"]
        
        # Check if the source contains this field (fully normalized case-insensitive match)
        if norm not in source_fields and normalize_field_name(orig) not in source_fields:
            if is_required:
                # If it's a field we can't infer, it's a blocking error
                if norm not in INFERRABLE_FIELDS:
                    errors.append({
                        "field": orig,
                        "message": f"'{orig}' is required by the template but was not found in the source document."
                    })
                else:
                    warnings.append({
                        "field": orig,
                        "message": f"'{orig}' is required but not found in the source. AI will attempt to infer it."
                    })
            else:
                warnings.append({
                    "field": orig,
                    "message": f"Optional field '{orig}' was not found in the source document."
                })
                
    return {
        "compatible": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }

def validate_question_row(q: dict[str, Any], template_schema: dict[str, Any]) -> list[str]:
    errors = []
    columns = template_schema.get("column_schema", [])
    
    # Extract values mapped by either original or normalized names
    data = {}
    for col in columns:
        orig = col["original_name"]
        norm = col["normalized_name"]
        val = q.get(orig, q.get(norm, ""))
        data[norm] = str(val).strip() if val is not None else ""

    # 1. Required fields
    for col in columns:
        orig = col["original_name"]
        norm = col["normalized_name"]
        is_required = col["required"]
        if is_required and not data.get(norm):
            errors.append(f"Required field '{orig}' is missing or empty.")

    # 2. Options uniqueness (for options normalized to option_1, option_2, option_3, option_4)
    option_keys = ["option_1", "option_2", "option_3", "option_4"]
    options = [data[k] for k in option_keys if k in data and data[k]]
    if len(options) > 1 and len(set(options)) != len(options):
        errors.append("Options must be unique.")

    # 3. Correct answer matches options if present
    if "correct_answer" in data and data["correct_answer"]:
        ca = data["correct_answer"].strip()
        defined_options = [data[k] for k in option_keys if k in data and data[k]]
        if defined_options:
            # Check if correct_answer matches any defined options directly,
            # or if correct_answer is an index/key (like "A", "B", "1", "2")
            # We map standard labels to indices
            label_map = {"A": 0, "B": 1, "C": 2, "D": 3, "1": 0, "2": 1, "3": 2, "4": 3}
            ca_upper = ca.upper()
            
            matches_direct = ca in defined_options
            matches_label = False
            if ca_upper in label_map:
                idx = label_map[ca_upper]
                if idx < len(defined_options):
                    matches_label = True
                    
            if not (matches_direct or matches_label):
                errors.append("Correct Answer must match one of the option values or option labels (A/B/C/D).")

    # 4. Difficulty validation
    if "difficulty" in data and data["difficulty"]:
        diff = data["difficulty"].lower()
        if diff not in ["easy", "medium", "hard", "auto"]:
            errors.append("Difficulty must be one of: Easy, Medium, Hard, Auto.")

    return errors

def validate_questions_batch(questions: list[dict[str, Any]], template_schema: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for i, q in enumerate(questions, start=1):
        errors = validate_question_row(q, template_schema)
        results.append({
            "index": i,
            "valid": len(errors) == 0,
            "errors": errors
        })
    return results
