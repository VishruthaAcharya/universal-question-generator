from pathlib import Path
import pandas as pd
import fitz  # PyMuPDF
from typing import Any

try:
    import docx
except ImportError:
    docx = None

def read_source_pages(path: str) -> list[dict[str, Any]]:
    p = Path(path)
    suffix = p.suffix.lower()
    pages = []

    if suffix == ".pdf":
        doc = fitz.open(path)
        for i, page in enumerate(doc):
            text = page.get_text("text")
            page_num = i + 1
            if text.strip():
                pages.append({
                    "page_number": page_num,
                    "type": "text",
                    "content": text
                })
            else:
                # Scanned or image-based PDF page -> Render to PNG bytes
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                pages.append({
                    "page_number": page_num,
                    "type": "image",
                    "content": img_bytes
                })
        doc.close()

    elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}:
        img_bytes = p.read_bytes()
        pages.append({
            "page_number": 1,
            "type": "image",
            "content": img_bytes
        })

    elif suffix == ".txt":
        text = p.read_text(encoding="utf-8", errors="replace")
        pages.append({
            "page_number": 1,
            "type": "text",
            "content": text
        })

    elif suffix == ".csv":
        df = pd.read_csv(path)
        csv_text = df.to_csv(index=False)
        pages.append({
            "page_number": 1,
            "type": "text",
            "content": csv_text
        })

    elif suffix in {".xlsx", ".xls"}:
        sheets = pd.read_excel(path, sheet_name=None)
        for sheet_name, df in sheets.items():
            csv_text = df.to_csv(index=False)
            pages.append({
                "page_number": 1,
                "type": "text",
                "content": f"[Sheet: {sheet_name}]\n{csv_text}"
            })

    elif suffix == ".docx":
        if not docx:
            raise ImportError("python-docx is not installed.")
        doc = docx.Document(path)
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        pages.append({
            "page_number": 1,
            "type": "text",
            "content": text
        })

    else:
        raise ValueError(f"Unsupported source file type: {suffix}")

    return pages
