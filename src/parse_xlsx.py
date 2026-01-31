from __future__ import annotations
import io
import pandas as pd
from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass
class ParsedXlsx:
    sheets: Dict[str, List[Dict[str, Any]]]
    stats: Dict[str, Any]

def parse_xlsx_bytes(xlsx_bytes: bytes, max_rows_per_sheet: int = 2000) -> ParsedXlsx:
    buf = io.BytesIO(xlsx_bytes)
    xls = pd.ExcelFile(buf, engine="openpyxl")

    sheets: Dict[str, List[Dict[str, Any]]] = {}
    total_rows = 0

    for name in xls.sheet_names:
        df = xls.parse(name)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.fillna("")
        df_limited = df.head(max_rows_per_sheet)

        rows = df_limited.astype(str).to_dict(orient="records")
        sheets[name] = rows
        total_rows += len(rows)

    stats = {
        "sheet_count": len(sheets),
        "total_rows_loaded": total_rows,
        "max_rows_per_sheet": max_rows_per_sheet,
    }
    return ParsedXlsx(sheets=sheets, stats=stats)
