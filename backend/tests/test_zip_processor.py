import pytest
import tempfile
import os
import zipfile
from pathlib import Path
from app.services.zip_processor import process_and_extract_zip, ZipValidationError
from app.config import settings

def test_zip_safe_path_traversal():
    """Verify that Zip Slip path traversal attempts are rejected."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a malicious zip file structure in memory
        zip_path = Path(temp_dir) / "malicious.zip"
        extract_dir = Path(temp_dir) / "extract"
        
        with zipfile.ZipFile(zip_path, "w") as zf:
            # Attempt a relative path traversal
            zf.writestr("../../traversal.txt", b"malicious content")
            
        with pytest.raises(ZipValidationError) as exc_info:
            process_and_extract_zip(str(zip_path), str(extract_dir))
        
        assert "Security Warning: Unsafe file path" in str(exc_info.value)

def test_zip_size_limits():
    """Verify that excessive decompressed sizes are rejected."""
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = Path(temp_dir) / "oversized.zip"
        extract_dir = Path(temp_dir) / "extract"
        
        # Override settings for tests
        original_limit = settings.max_zip_extracted_size_mb
        settings.max_zip_extracted_size_mb = 1 # 1 MB limit
        
        try:
            with zipfile.ZipFile(zip_path, "w") as zf:
                # Write 2 MB of data
                large_data = b"0" * (2 * 1024 * 1024)
                zf.writestr("large.txt", large_data)
                
            with pytest.raises(ZipValidationError) as exc_info:
                process_and_extract_zip(str(zip_path), str(extract_dir))
            
            assert "Uncompressed size exceeds limit" in str(exc_info.value)
        finally:
            settings.max_zip_extracted_size_mb = original_limit

def test_nested_zip_bomb():
    """Verify that excessive nested zip archives are rejected."""
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = Path(temp_dir) / "bomb.zip"
        extract_dir = Path(temp_dir) / "extract"
        
        # Create level 3 nested zips
        level3_path = Path(temp_dir) / "level3.zip"
        with zipfile.ZipFile(level3_path, "w") as z3:
            z3.writestr("test.txt", b"hello")
            
        level2_path = Path(temp_dir) / "level2.zip"
        with zipfile.ZipFile(level2_path, "w") as z2:
            z2.write(level3_path, "level3.zip")
            
        with zipfile.ZipFile(zip_path, "w") as z1:
            z1.write(level2_path, "level2.zip")
            
        with pytest.raises(ZipValidationError) as exc_info:
            process_and_extract_zip(str(zip_path), str(extract_dir))
            
        assert "Maximum zip depth" in str(exc_info.value)
