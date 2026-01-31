from __future__ import annotations
import re
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional

def norm_text(s: str) -> str:
    s = s or ""
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s).lower()

@dataclass(frozen=True)
class Org:
    name: str
    norm: str

def load_orgs_from_xlsx(xlsx_path: str) -> List[Org]:
    df = pd.read_excel(xlsx_path)
    if "orgs_nm" not in df.columns:
        raise ValueError("managed_orgs.xlsx must have 'orgs_nm' column")
    orgs: List[Org] = []
    for v in df["orgs_nm"].dropna().astype(str).tolist():
        v = v.strip()
        if v:
            orgs.append(Org(name=v, norm=norm_text(v)))
    if not orgs:
        raise ValueError("No orgs found in orgs_nm column")
    return orgs

def match_org(orgs: List[Org], text: str) -> Optional[str]:
    """
    orgs_nm only: use normalized substring match.
    Guard: only allow org norms length >= 4 to reduce false positives.
    """
    t = norm_text(text)
    for org in orgs:
        if len(org.norm) >= 4 and org.norm in t:
            return org.name
    return None
