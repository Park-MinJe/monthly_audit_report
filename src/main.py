from __future__ import annotations
import os
import requests
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from .settings import load_settings
from .timeutil import now_kst, prev_month, month_range, quarter_deadline, report_quarters
from .orgs import load_orgs_from_xlsx, match_org, Org
from .opengov import fetch_docs_all, fetch_attachments, extract_year_quarter, DocItem, Attachment
from .parse_xlsx import parse_xlsx_bytes
from .summarize import summarize
from .report import DocReport, build_monthly_markdown, write_report, is_xlsx
from .state import load_seen, save_seen

def download_bytes(url: str, session: requests.Session, timeout_sec: int) -> bytes:
    r = session.get(url, timeout=timeout_sec)
    r.raise_for_status()
    return r.content

def build_report_link(report_base_url: str, report_path: str) -> Optional[str]:
    base = (report_base_url or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/{report_path.replace(os.sep, '/')}"

def compute_quarter_status(
    orgs: List[Org],
    docs: List[DocItem],
    today: date,
    buffer_days: int,
    lookback_count: int,
) -> Dict[Tuple[str, int, int], str]:
    """
    Status per (org, year, quarter):
      OK: found & pub_date <= deadline
      LATE: found & pub_date > deadline
      PENDING: not found but today <= deadline
      MISSING: not found and today > deadline
    """
    found: Dict[Tuple[str, int, int], str] = {}

    for d in docs:
        org = match_org(orgs, d.title)
        if not org:
            continue
        y, q = extract_year_quarter(d.title)
        if y is None or q is None:
            continue

        deadline = quarter_deadline(y, q, buffer_days)
        if d.pub_date is None:
            st = "OK"
        else:
            st = "OK" if d.pub_date <= deadline else "LATE"

        key = (org, y, q)
        # if multiple, keep "LATE" only if no OK exists
        if key not in found:
            found[key] = st
        else:
            if found[key] != "OK" and st == "OK":
                found[key] = "OK"

    result: Dict[Tuple[str, int, int], str] = {}
    # quarters = iter_last_n_quarters(today, lookback_count)
    quarters = report_quarters(today)

    for org in orgs:
        for yq in quarters:
            key = (org.name, yq.year, yq.quarter)
            if key in found:
                result[key] = found[key]
            else:
                dl = quarter_deadline(yq.year, yq.quarter, buffer_days)
                result[key] = "PENDING" if today <= dl else "MISSING"

    return result

def is_doc_in_month(d: DocItem, start: date, end: date) -> bool:
    if d.pub_date is None:
        return False
    return start <= d.pub_date < end

def main() -> None:
    s = load_settings()
    kst_now = now_kst()
    target_ym = prev_month(kst_now)
    month_start, month_end = month_range(target_ym)

    orgs = load_orgs_from_xlsx(s.orgs_xlsx_path)
    org_names = [o.name for o in orgs]

    session = requests.Session()
    session.headers.update({"User-Agent": "opengov-monitor/1.0 (+github-actions)"})

    # Load state
    seen = load_seen(s.state_seen_path)

    docs: List[DocItem] = []
    
    print("##########크롤링 시작##########")
    docs = fetch_docs_all(
        target_ym=target_ym,
        session=session,
        max_pages_fallback=s.opengov_max_pages,
        stop_after_empty=s.opengov_stop_after_empty,
        timeout_sec=s.opengov_http_timeout_sec,
    )
    print("##########크롤링 끝##########")

    # Month docs: only those with pub_date in previous month
    month_docs = [d for d in docs if is_doc_in_month(d, month_start, month_end)]

    # Quarter status: compute from all crawled docs (title-based year/quarter)
    quarter_status = compute_quarter_status(
        orgs=orgs,
        docs=docs,
        today=kst_now.date(),
        buffer_days=s.quarter_buffer_days,
        lookback_count=s.quarter_lookback_count,
    )

    doc_reports: List[DocReport] = []

    for d in month_docs:
        org_name = match_org(orgs, d.title)
        if not org_name:
            continue
        
        atts = fetch_attachments(d.nid, session, s.opengov_http_timeout_sec)

        att_reports: List[Dict[str, Any]] = []
        for a in atts:
            key = f"{d.nid}|{a.url}"

            if not is_xlsx(a.filename):
                # 요구사항: 파일명 링크 + 지원하지 않음
                att_reports.append({"filename": a.filename, "url": a.url, "kind": "unsupported", "summary": ""})
                seen.add(key)
                continue

            # xlsx: parse + summarize only once per (nid,url)
            if key in seen:
                att_reports.append({"filename": a.filename, "url": a.url, "kind": "xlsx", "summary": ""})
                continue

            summary_text = ""
            try:
                raw = download_bytes(a.url, session, timeout_sec=max(60, s.opengov_http_timeout_sec))
                parsed = parse_xlsx_bytes(raw, max_rows_per_sheet=2000)

                payload = {
                    "org": org_name,
                    "nid": d.nid,
                    "title": d.title,
                    "pub_date": d.pub_date.isoformat() if d.pub_date else None,
                    "attachment": {"filename": a.filename, "url": a.url},
                    "stats": parsed.stats,
                    "sheets": parsed.sheets,  # may be large; summarize() truncates
                }
                summary_text = summarize(s.summary_provider, payload)
            except Exception as e:
                summary_text = f"(xlsx 처리 실패: {e})"
            finally:
                seen.add(key)

            att_reports.append({"filename": a.filename, "url": a.url, "kind": "xlsx", "summary": summary_text})

        doc_reports.append(
            DocReport(
                org=org_name,
                nid=d.nid,
                title=d.title,
                pub_date=d.pub_date,
                doc_url=d.url,
                attachments=att_reports,
            )
        )

    # Build + write report
    md = build_monthly_markdown(
        ym=target_ym,
        docs=doc_reports,
        orgs=org_names,
        quarter_status=quarter_status,
        today=kst_now.date(),
        buffer_days=s.quarter_buffer_days,
        lookback_count=s.quarter_lookback_count,
    )
    report_path = write_report(s.report_dir, target_ym, md)

    # Save state
    save_seen(s.state_seen_path, seen)

    # Notify via Kakao "to me"
    link = build_report_link(s.report_base_url, report_path)
    msg = f"[OpenGov 점검] {report_path} 생성 완료"
    print(f'최종 처리 결과 : {msg}')
    # ok = send_to_me(text=msg, link_url=link)

    # if ok:
    #     print("Kakao notified.")
    # else:
    #     print("Kakao notify failed. Check KAKAO_* secrets and consent scopes.")

if __name__ == "__main__":
    main()
