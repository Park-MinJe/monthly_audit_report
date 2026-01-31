from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .timeutil import YearMonth, ym_to_str, iter_last_n_quarters, quarter_deadline, YearQuarter, report_quarters

@dataclass
class DocReport:
    org: Optional[str]
    nid: str
    title: str
    pub_date: Optional[date]
    doc_url: str
    attachments: List[Dict[str, Any]]  # filename,url,kind,summary

def is_xlsx(filename: str) -> bool:
    return filename.lower().endswith(".xlsx")

def build_quarter_section(
    orgs: List[str],
    quarter_status: Dict[Tuple[str, int, int], str],
    today: date,
    buffer_days: int,
    lookback_count: int,
) -> str:
    out = "## 분기별 업로드 상태(기관별)\n\n"
    # quarters = iter_last_n_quarters(today, lookback_count)
    quarters = report_quarters(today)

    out += "|**기관명**|"
    for yq in quarters:
        dl = quarter_deadline(yq.year, yq.quarter, buffer_days).isoformat()
        out += f"**{yq.year} Q{yq.quarter}** (마감 {dl})|"
    out += "\n|-|"
    for yq in quarters:
        out += "-|"
    
    for org in sorted(orgs):
        out += f"\n|{org}|"
        for yq in quarters:
            st = quarter_status.get((org, yq.year, yq.quarter), "UNKNOWN")
            if st in ["LATE", "MISSING"]:
                out += f"***{st}***|"
            else:
                out += f"{st}|"
    out += "\n"
    return out

def build_monthly_markdown(
    ym: YearMonth,
    docs: List[DocReport],
    orgs: List[str],
    quarter_status: Dict[Tuple[str, int, int], str],
    today: date,
    buffer_days: int,
    lookback_count: int,
) -> str:
    content = f"# OpenGov 업로드 점검 리포트 ({ym_to_str(ym)})\n\n"
    content += "- 실행: 매월 1일 09:00(KST)\n"
    content += "- 월별 리포트는 **직전 월** 기준으로 생성\n"
    content += f"- 분기 누락 집계: **분기 종료 + {buffer_days}일 버퍼**\n\n"

    content += build_quarter_section(orgs, quarter_status, today, buffer_days, lookback_count)

    content += "## 이번 리포트에 포함된 문서/첨부(직전 월 공개 기준)\n\n"
    if not docs:
        content += "- (해당 월 공개 문서 없음)\n"
        return content

    for d in docs:
        org_line = d.org if d.org else "(기관 매칭 실패)"
        pd = d.pub_date.isoformat() if d.pub_date else "unknown"
        content += f"### {org_line}\n\n"
        content += f"- 문서: [{d.title}]({d.doc_url})\n"
        content += f"- 공개일: {pd}\n"
        content += f"- nid: `{d.nid}`\n\n"
        content += "#### 첨부\n\n"
        if not d.attachments:
            content += "- (첨부 없음)\n\n"
            continue

        for a in d.attachments:
            fname = a["filename"]
            url = a["url"]
            kind = a["kind"]
            summary = (a.get("summary") or "").strip()

            # 요구사항 반영: 파일명에 다운로드 링크
            line = f"- [{fname}]({url})"
            if kind == "unsupported":
                content += line + " — 지원하지 않는 파일입니다\n"
                continue

            content += line + "\n"
            if summary:
                content += f"  - 요약:\n\n```\n{summary}\n```\n"

        content += "\n"

    return content

def write_report(report_dir: str, ym: YearMonth, content: str) -> str:
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    path = Path(report_dir) / f"{ym_to_str(ym)}.md"
    path.write_text(content, encoding="utf-8")
    return str(path)
