from pathlib import Path
import pandas as pd
import fitz

def read_source(path: str) -> str:
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix == ".pdf":
        doc = fitz.open(path)
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                pages.append(f"[Page {i+1}]\n{text}")
        doc.close()
        if not pages:
            raise ValueError("Could not extract readable text from this PDF. It may be scanned or image-based.")
        return "\n\n".join(pages)

    if suffix == ".txt":
        return p.read_text(encoding="utf-8", errors="replace")

    if suffix == ".csv":
        return pd.read_csv(path).to_csv(index=False)

    if suffix in {".xlsx", ".xls"}:
        sheets = pd.read_excel(path, sheet_name=None)
        return "\n\n".join(
            f"[Sheet: {name}]\n{df.to_csv(index=False)}"
            for name, df in sheets.items()
        )

    raise ValueError(f"Unsupported source file type: {suffix}")
