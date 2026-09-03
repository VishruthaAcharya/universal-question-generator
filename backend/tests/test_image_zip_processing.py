import io
import os
import tempfile
import zipfile
import pytest
from PIL import Image
from app.services.source_parser import parse_source_batch
from app.services.zip_processor import process_and_extract_zip
from app.services.source_reader import read_source_pages

def test_four_image_zip_processing():
    """
    Verifies that a ZIP archive containing 4 PNG images processes without
    PIL / Image import errors and passes all images into the extraction pipeline.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, "batch_images.zip")
        extract_dir = os.path.join(temp_dir, "extracted")

        # 1. Create 4 PNG images in memory and save into ZIP
        with zipfile.ZipFile(zip_path, "w") as zf:
            for i in range(1, 5):
                img = Image.new("RGB", (300, 100), color=(255, 255, 255))
                img_buf = io.BytesIO()
                img.save(img_buf, format="PNG")
                zf.writestr(f"question_{i}.png", img_buf.getvalue())

        # 2. Extract files using zip_processor
        result = process_and_extract_zip(zip_path, extract_dir)
        extracted_files = result["extracted_files"]
        assert len(extracted_files) == 4, f"Expected 4 extracted files, got {len(extracted_files)}"

        # 3. Read pages for each extracted image
        units = []
        for f_info in extracted_files:
            fpath = f_info["absolute_path"]
            pages = read_source_pages(fpath)
            assert len(pages) == 1, f"Expected 1 page for image {fpath}, got {len(pages)}"
            units.extend(pages)

        assert len(units) == 4, f"Expected 4 image units total, got {len(units)}"
        for idx, u in enumerate(units, start=1):
            assert u.get("has_visual") is True
            assert u.get("type") in ("text", "image")
