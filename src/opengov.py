from __future__ import annotations
import re
import time
import requests
import math
from bs4 import BeautifulSoup
from dataclasses import dataclass
from datetime import date
from typing import Optional, List, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, unquote

from .timeutil import YearMonth

BASE = "https://opengov.seoul.go.kr"

@dataclass(frozen=True)
class DocItem:
    nid: str
    title: str
    pub_date: Optional[date]
    url: str

@dataclass(frozen=True)
class Attachment:
    nid: str
    filename: str
    url: str

_Q_RE = re.compile(r"(\d{4})\s*년.*?([1-4])\s*분기")

def extract_year_quarter(text: str) -> Tuple[Optional[int], Optional[int]]:
    m = _Q_RE.search(text or "")
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))

def parse_date_loose(s: str) -> Optional[date]:
    # accept YYYY-MM-DD / YYYY.MM.DD / YYYY/MM/DD
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", s or "")
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d)
    except Exception:
        return None

def get_soup(url: str, session: requests.Session, timeout_sec: int) -> BeautifulSoup:
    r = session.get(url, timeout=timeout_sec)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def list_page_url(target_y: int, page: int, items_per_page: int = 50) -> str:
    # reflect user's example: dept[0]=delegation, ym year/month all, page=N
    return (
        f"{BASE}/expense/list"
        f"?items_per_page={items_per_page}"
        f"&dept%5B0%5D=delegation"
        f"&ym%5Byear%5D=all"
        f"&ym%5Bmonth%5D=all"
        f"&searchKeyword={target_y}%EB%85%84"
        f"&page={page}"
    )

_TOTAL_STRONG_CSS = (
    "html > body > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div > "
    "div > div > div:nth-of-type(3) > div > div:nth-of-type(1) > div:nth-of-type(1) > strong"
)

def _parse_int_from_text(text: str) -> Optional[int]:
    if not text:
        return None
    # extract first number (handles commas)
    m = re.search(r"([\d,]+)", text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except Exception:
        return None

def fetch_total_count(
    session: requests.Session, 
    timeout_sec: int, 
    items_per_page: int, 
    target_y: int
) -> Optional[int]:
    """
    Fetch page=1 and parse total count from the strong element.
    If the CSS selector fails (DOM changes), fallback to a heuristic search.
    """
    url = list_page_url(page=1, items_per_page=items_per_page, target_y=target_y)
    soup = get_soup(url, session, timeout_sec)

    # 1) Primary: exact CSS corresponding to the xpath you gave
    el = soup.select_one(_TOTAL_STRONG_CSS)
    if el:
        total = _parse_int_from_text(el.get_text(strip=True))
        if total is not None:
            print("success to fetch total count")
            return total

    # 2) Fallback : scan whole page text for a "검색결과:N" pattern
    page_text = soup.get_text(" ", strip=True)
    m = re.search(r"검색결과\s*:\s*([\d,]+)", page_text)
    if m:
        print("success to fetch total count by fallback")
        return _parse_int_from_text(m.group(1))

    return None

def compute_max_pages(total_count: int, items_per_page: int) -> int:
    return max(1, math.ceil(total_count / max(1, items_per_page)))

def fetch_docs_all(
    target_ym: YearMonth,
    session: requests.Session,
    max_pages_fallback: int,
    stop_after_empty: int = 2,
    timeout_sec: int = 30,
    polite_sleep_sec: float = 0.2,
    items_per_page: int = 50,
) -> List[DocItem]:
    """
    Crawl list pages by increasing page=1..N. Stop when we see N consecutive pages with 0 rows.
    """
    target_y = target_ym.year
    if target_ym.month <= 2:
        target_y = target_y-1

    total = None
    try:
        total = fetch_total_count(session, timeout_sec, items_per_page, target_y)
    except Exception:
        print("Failed to fetch total count")
        total = None
        return
    print(f'# Total elements {total}')

    max_pages = max_pages_fallback
    if total is not None:
        max_pages = compute_max_pages(total, items_per_page)
    print(f'# Total pages is {max_pages}')

    docs_by_nid: dict[str, DocItem] = {}
    empty_streak = 0

    for page in range(1, max_pages + 1):
        print(f'페이지 {page} 시작')
        url = list_page_url(page=page, target_y=target_y)
        try:
            soup = get_soup(url, session, timeout_sec)
        except Exception:
            # transient network: wait and continue
            time.sleep(1.0)
            continue

        rows = soup.select("table tbody tr")
        if not rows:
            empty_streak += 1
            if empty_streak >= stop_after_empty:
                break
            continue
        empty_streak = 0

        for tr in rows:
            a = tr.select_one("a[href*='/public/']")
            if not a:
                continue

            href = a.get("href", "")
            m = re.search(r"/public/(\d+)", href)
            if not m:
                continue

            nid = m.group(1)
            title = (a.get_text(strip=True) or "").strip()
            doc_url = urljoin(BASE, href)
            pub = parse_date_loose(tr.get_text(" ", strip=True))

            if nid not in docs_by_nid:
                docs_by_nid[nid] = DocItem(nid=nid, title=title, pub_date=pub, url=doc_url)

        time.sleep(polite_sleep_sec)

    return list(docs_by_nid.values())

def fetch_attachments(nid: str, session: requests.Session, timeout_sec: int) -> List[Attachment]:
    """
    On detail page /public/{nid}, collect all /og/com/download.php links.
    Filename extracted from dname (best), else from uri tail.
    """
    url = f"{BASE}/public/{nid}"
    soup = get_soup(url, session, timeout_sec)
    out: List[Attachment] = []

    for a in soup.select("a[href*='/og/com/download.php']"):
        href = a.get("href", "")
        full = urljoin(BASE, href)

        qs = parse_qs(urlparse(href).query)
        filename = ""
        if "dname" in qs and qs["dname"]:
            filename = unquote(qs["dname"][0])
        elif "uri" in qs and qs["uri"]:
            filename = qs["uri"][0].split("/")[-1]
        else:
            # fallback: link text
            filename = (a.get_text(strip=True) or "attachment").strip()

        out.append(Attachment(nid=nid, filename=filename, url=full))

    # Dedup by url
    seen = set()
    dedup: List[Attachment] = []
    for att in out:
        if att.url in seen:
            continue
        seen.add(att.url)
        dedup.append(att)
    return dedup
