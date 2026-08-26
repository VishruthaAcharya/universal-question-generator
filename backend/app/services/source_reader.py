from pathlib import Path
import pandas as pd
import fitz  # PyMuPDF
from typing import Any

try:
    import docx
except ImportError:
    docx = None

def read_source_pages(path: str) -> list[dict[str, Any]]:
    """
    Reads document pages preserving layout, text blocks, embedded vector drawings, and raster images.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    pages = []

    if suffix == ".pdf":
        doc = fitz.open(path)
        for i, page in enumerate(doc):
            text = page.get_text("text")
            page_num = i + 1
            blocks = page.get_text("blocks")
            images = page.get_images()
            drawings = page.get_drawings()
            has_visual = (len(images) > 0) or (len(drawings) > 0)

            if text and text.strip():
                pages.append({
                    "page_number": page_num,
                    "type": "text",
                    "content": text,
                    "blocks": blocks,
                    "has_visual": has_visual,
                    "images_count": len(images),
                    "drawings_count": len(drawings)
                })
            else:
                # Scanned or image-based PDF page -> Render to PNG bytes
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                pages.append({
                    "page_number": page_num,
                    "type": "image",
                    "content": img_bytes,
                    "has_visual": True,
                    "images_count": len(images) or 1,
                    "drawings_count": 0
                })
        doc.close()

    elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}:
        img_bytes = p.read_bytes()
        pages.append({
            "page_number": 1,
            "type": "image",
            "content": img_bytes,
            "has_visual": True,
            "images_count": 1,
            "drawings_count": 0
        })

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
