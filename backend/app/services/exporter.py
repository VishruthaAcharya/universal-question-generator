import os
from io import BytesIO
import pandas as pd
from pathlib import Path
import openpyxl

def export_to_csv(questions: list[dict], columns: list[str]) -> BytesIO:
    # questions is a list of question data dicts (original column names as keys)
    rows = []
    for q in questions:
        rows.append({col: q.get(col, "") for col in columns})
    df = pd.DataFrame(rows, columns=columns)
    buf = BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)
    return buf

def export_to_xlsx(questions: list[dict], columns: list[str], template_path: str | None = None, sheet_name: str | None = None) -> BytesIO:
    buf = BytesIO()
    
    # If we have the original template XLSX file, we load it to preserve styling
    if template_path and os.path.exists(template_path) and template_path.lower().endswith(('.xlsx', '.xls')):
        try:
            wb = openpyxl.load_workbook(template_path)
            if sheet_name and sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
            else:
                ws = wb.active
            
            # Clear all rows below header (row 1)
            max_row = ws.max_row
            if max_row > 1:
                ws.delete_rows(2, max_row)
                
            # Write new questions
            for r_idx, q in enumerate(questions, start=2):
                for c_idx, col in enumerate(columns, start=1):
                    val = q.get(col, "")
                    ws.cell(row=r_idx, column=c_idx, value=val)
                    
            wb.save(buf)
            buf.seek(0)
            return buf
        except Exception:
            # Fallback to pandas if template loading fails
            pass
            
    # Fallback/standard pandas generation
    rows = []
    for q in questions:
        rows.append({col: q.get(col, "") for col in columns})
    df = pd.DataFrame(rows, columns=columns)
    s_name = sheet_name or "Questions"
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=s_name)
        ws = writer.book[s_name]
        ws.freeze_panes = "A2"
        for cell in ws[1]:
            cell.font = cell.font.copy(bold=True)
    buf.seek(0)
    return buf
