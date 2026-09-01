import re
import io
from pathlib import Path
import pandas as pd
import fitz  # PyMuPDF
from typing import Any

try:
    import docx
except ImportError:
    docx = None

def evaluate_text_quality(text: str) -> tuple[bool, float, dict[str, Any]]:
    """
    Evaluates the quality of extracted text from a PDF page.
    Returns (is_usable, quality_score, metrics_dict).
    
    Treats text as usable only if:
    - sufficient character count (>= 30 chars unless dense with valid words)
    - reasonable alphanumeric ratio (>= 0.45)
    - not mostly whitespace or non-text symbols
    - contains meaningful words (>= 3 multi-letter words)
    - does not consist primarily of PDF layout/CID/control character garbage
    """
    if not text or not isinstance(text, str) or not text.strip():
        return False, 0.0, {
            "character_count": 0,
            "alphanumeric_count": 0,
            "alphanumeric_ratio": 0.0,
            "word_count": 0,
            "garbage_count": 0,
            "garbage_ratio": 0.0,
            "text_quality_score": 0.0,
            "reason": "Empty or whitespace-only text"
        }

    raw = text.strip()
    char_count = len(raw)

    # 1. Alphanumeric metrics
    alnum_chars = sum(1 for c in raw if c.isalnum())
    alnum_ratio = alnum_chars / max(1, char_count)

    # 2. Meaningful words check (tokens with at least 2 alphabetic characters)
    words = re.findall(r"\b[A-Za-z]{2,}\b", raw)
    word_count = len(words)

    # 3. Detect PDF extraction garbage:
    # - CID codes e.g. (cid:123)
    # - Unicode replacement chars \ufffd
    # - Non-printable control characters (excluding standard \n, \r, \t)
    cid_matches = len(re.findall(r"\(cid:\d+\)", raw))
    replacement_chars = raw.count("\ufffd")
    control_chars = len(re.findall(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", raw))

    garbage_count = (cid_matches * 6) + replacement_chars + control_chars
    garbage_ratio = garbage_count / max(1, char_count)

    # 4. Check for repetitive single-character gibberish (e.g. "......", "//////", "_____")
    non_space_chars = [c for c in raw if not c.isspace()]
    unique_non_space = len(set(non_space_chars)) if non_space_chars else 0
    unique_ratio = unique_non_space / max(1, len(non_space_chars))

    # Calculate text quality score (0.0 to 1.0)
    score = 1.0

    if char_count < 25:
        score *= (char_count / 25.0) * 0.5
    elif char_count < 50:
        score *= 0.8

    if alnum_ratio < 0.40:
        score *= (alnum_ratio / 0.40) * 0.4
    elif alnum_ratio < 0.60:
        score *= (alnum_ratio / 0.60)

    if word_count < 3:
        score *= 0.3
    elif word_count < 6:
        score *= 0.7

    if garbage_ratio > 0.05:
        score -= min(0.9, garbage_ratio * 4.0)
    score = max(0.0, score)
    if unique_ratio < 0.05 and len(non_space_chars) > 20:
        score *= 0.3

    quality_score = max(0.0, min(1.0, round(score, 3)))

    is_usable = (
        char_count >= 30
        and alnum_ratio >= 0.45
        and word_count >= 3
        and garbage_ratio < 0.08
        and quality_score >= 0.60
    )

    metrics = {
        "character_count": char_count,
        "alphanumeric_count": alnum_chars,
        "alphanumeric_ratio": round(alnum_ratio, 3),
        "word_count": word_count,
        "garbage_count": garbage_count,
        "garbage_ratio": round(garbage_ratio, 3),
        "text_quality_score": quality_score
    }

    return is_usable, quality_score, metrics

def extract_page_with_ocr_fallback(page, page_num: int) -> dict[str, Any]:
    """
    Independently extracts a PDF page:
    1. Attempts native PDF text extraction first.
    2. Evaluates text quality.
    3. If usable, returns native text.
    4. If empty or unusable, renders page to image and runs OCR.
    """
    native_text = page.get_text("text") or ""
    blocks = page.get_text("blocks")
    images = page.get_images()
    drawings = page.get_drawings()
    has_visual = (len(images) > 0) or (len(drawings) > 0)

    is_usable, quality_score, metrics = evaluate_text_quality(native_text)

    if is_usable:
        return {
            "page_number": page_num,
            "type": "text",
            "content": native_text,
            "blocks": blocks,
            "has_visual": has_visual,
            "images_count": len(images),
            "drawings_count": len(drawings),
            "extraction_method": "native_text",
            "text_quality_score": quality_score,
            "character_count": len(native_text.strip()),
            "quality_metrics": metrics
        }

    # Fallback: Render page as image and attempt OCR
    pix = page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")

    ocr_text = ""
    # Try PyMuPDF OCR if Tesseract data is available
    try:
        tp = page.get_textpage_ocr(language="eng", dpi=150)
        if tp:
            ocr_text = page.get_text(textpage=tp) or ""
    except Exception:
        pass

    # Try pytesseract if available
    if not ocr_text:
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(io.BytesIO(img_bytes))
            ocr_text = pytesseract.image_to_string(img) or ""
        except Exception:
            pass

    if ocr_text and ocr_text.strip():
        ocr_usable, ocr_quality, ocr_metrics = evaluate_text_quality(ocr_text)
        if ocr_usable:
            return {
                "page_number": page_num,
                "type": "text",
                "content": ocr_text,
                "blocks": blocks,
                "has_visual": True,
                "images_count": len(images) or 1,
                "drawings_count": len(drawings),
                "extraction_method": "OCR",
                "text_quality_score": ocr_quality,
                "character_count": len(ocr_text.strip()),
                "quality_metrics": ocr_metrics
            }

    # Queue image bytes for vision-based OCR extraction
    return {
        "page_number": page_num,
        "type": "image",
        "content": img_bytes,
        "has_visual": True,
        "images_count": len(images) or 1,
        "drawings_count": 0,
        "extraction_method": "OCR",
        "text_quality_score": 0.0,
        "character_count": 0,
        "quality_metrics": metrics
    }

def log_image_stage_diagnostics(stage: int, stage_name: str, details: dict[str, Any]) -> None:
    """Logs diagnostic information for each stage of the image question extraction pipeline."""
    import logging
    logger = logging.getLogger("image_extraction")
    diag_line = f"[IMAGE_DIAGNOSTICS] Stage {stage}: {stage_name} | " + " | ".join(f"{k}={v}" for k, v in details.items())
    logger.info(diag_line)
    print(diag_line)

def extract_image_with_ocr_fallback(
    img_path_or_bytes: str | Path | bytes,
    filename: str = "image.png",
    page_num: int = 1
) -> dict[str, Any]:
    """
    Extracts an image file (PNG/JPG/JPEG/WEBP/BMP/TIFF) with OCR fallback and diagnostics.
    Logs diagnostics across stages 1 to 4.
    """
    import mimetypes
    from PIL import Image

    if isinstance(img_path_or_bytes, (str, Path)):
        p = Path(img_path_or_bytes)
        img_bytes = p.read_bytes()
        actual_fn = p.name
        ext = p.suffix.lower()
        file_size = len(img_bytes)
    else:
        img_bytes = img_path_or_bytes
        actual_fn = filename
        ext = Path(filename).suffix.lower() if "." in filename else ".png"
        file_size = len(img_bytes)

    mime_type = mimetypes.guess_type(actual_fn)[0] or f"image/{ext.lstrip('.')}"

    # Stage 1: File received
    log_image_stage_diagnostics(1, "File received", {
        "filename": actual_fn,
        "extension": ext,
        "mime_type": mime_type,
        "file_size_bytes": file_size
    })

    # Stage 2: Image loading
    img_width, img_height, img_format = 0, 0, "UNKNOWN"
    can_open = False
    pil_img = None
    try:
        pil_img = Image.open(io.BytesIO(img_bytes))
        img_width, img_height = pil_img.size
        img_format = pil_img.format or ext.lstrip(".").upper()
        can_open = True
    except Exception as e:
        log_image_stage_diagnostics(2, "Image loading failed", {
            "can_open": False,
            "error": str(e)
        })

    if can_open:
        log_image_stage_diagnostics(2, "Image loading", {
            "can_open": True,
            "width": img_width,
            "height": img_height,
            "format": img_format
        })

    # Stage 3: OCR invocation
    ocr_engine = "None"
    ocr_text = ""

    # Attempt PyMuPDF OCR
    try:
        img_doc = fitz.open()
        p_fitz = img_doc.new_page(width=float(img_width or 800), height=float(img_height or 600))
        p_fitz.insert_image(p_fitz.rect, stream=img_bytes)
        tp = p_fitz.get_textpage_ocr(language="eng", dpi=150)
        if tp:
            ocr_text = p_fitz.get_text(textpage=tp) or ""
            if ocr_text.strip():
                ocr_engine = "PyMuPDF_OCR"
        img_doc.close()
    except Exception:
        pass

    # Attempt pytesseract OCR
    if not ocr_text.strip() and can_open and pil_img:
        try:
            import pytesseract
            ocr_text = pytesseract.image_to_string(pil_img) or ""
            if ocr_text.strip():
                ocr_engine = "pytesseract"
        except Exception:
            pass

    log_image_stage_diagnostics(3, "OCR invocation", {
        "ocr_called": True,
        "ocr_engine_used": ocr_engine if ocr_text.strip() else "queued_for_vision_ocr"
    })

    # Stage 4: OCR result
    char_count = len(ocr_text.strip())
    preview_300 = repr(ocr_text.strip()[:300]) if ocr_text.strip() else "EMPTY"
    log_image_stage_diagnostics(4, "OCR result", {
        "character_count": char_count,
        "first_300_chars": preview_300
    })

    if ocr_text and ocr_text.strip():
        ocr_usable, ocr_quality, ocr_metrics = evaluate_text_quality(ocr_text)
        if ocr_usable:
            return {
                "page_number": page_num,
                "type": "text",
                "content": ocr_text,
                "has_visual": True,
                "images_count": 1,
                "drawings_count": 0,
                "extraction_method": "OCR",
                "text_quality_score": ocr_quality,
                "character_count": char_count,
                "quality_metrics": ocr_metrics
            }

    return {
        "page_number": page_num,
        "type": "image",
        "content": img_bytes,
        "has_visual": True,
        "images_count": 1,
        "drawings_count": 0,
        "extraction_method": "OCR",
        "text_quality_score": 0.0,
        "character_count": 0,
        "quality_metrics": {
            "character_count": 0,
            "reason": "Image queued for vision-based OCR"
        }
    }

def read_source_pages(path: str) -> list[dict[str, Any]]:
    """
    Reads document pages preserving layout, text blocks, embedded vector drawings, and raster images.
    Implements a robust per-page fallback from native text to OCR.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    pages = []

    if suffix == ".pdf":
        doc = fitz.open(path)
        for i, page in enumerate(doc):
            page_data = extract_page_with_ocr_fallback(page, page_num=i + 1)
            pages.append(page_data)
        doc.close()

    elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}:
        page_data = extract_image_with_ocr_fallback(p, filename=p.name, page_num=1)
        pages.append(page_data)

    elif suffix == ".txt":
        text = p.read_text(encoding="utf-8", errors="replace")
        pages.append({
            "page_number": 1,
            "type": "text",
            "content": text,
            "has_visual": False,
            "images_count": 0,
            "drawings_count": 0
        })

    elif suffix == ".csv":
        df = pd.read_csv(path, encoding="utf-8-sig")
        df.columns = [str(c).lstrip("\ufeff").strip() for c in df.columns]
        csv_text = df.to_csv(index=False)
        pages.append({
            "page_number": 1,
            "type": "dataframe",
            "df": df,
            "content": csv_text,
            "has_visual": False,
            "images_count": 0,
            "drawings_count": 0
        })

    elif suffix in {".xlsx", ".xls"}:
        sheets = pd.read_excel(path, sheet_name=None)
        for sheet_name, df in sheets.items():
            df.columns = [str(c).lstrip("\ufeff").strip() for c in df.columns]
            csv_text = df.to_csv(index=False)
            pages.append({
                "page_number": 1,
                "type": "dataframe",
                "df": df,
                "content": f"[Sheet: {sheet_name}]\n{csv_text}",
                "has_visual": False,
                "images_count": 0,
                "drawings_count": 0
            })

    elif suffix == ".docx":
        if not docx:
            raise ImportError("python-docx is not installed.")
        doc = docx.Document(path)
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        pages.append({
            "page_number": 1,
            "type": "text",
            "content": text,
            "has_visual": False,
            "images_count": 0,
            "drawings_count": 0
        })

    else:
        raise ValueError(f"Unsupported source file type: {suffix}")

    return pages
