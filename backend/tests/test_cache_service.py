from app.services.cache_service import (
    compute_file_hash,
    get_cached_extraction,
    save_cached_extraction,
)

def test_cache_roundtrip(tmp_path):
    test_file = tmp_path / "sample.txt"
    test_file.write_text("Hello Question Generator", encoding="utf-8")

    file_hash = compute_file_hash(test_file)
    assert len(file_hash) == 64

    # Initial cache miss
    cached = get_cached_extraction("non_existent_hash")
    assert cached is None

    mock_questions = [
        {"question": "What is x?", "options": ["1", "2"], "correct_answer": "1"}
    ]

    save_cached_extraction(file_hash, mock_questions)
    retrieved = get_cached_extraction(file_hash)
    assert retrieved is not None
    assert len(retrieved) == 1
    assert retrieved[0]["question"] == "What is x?"
