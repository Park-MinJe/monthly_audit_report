from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

@dataclass(frozen=True)
class YearMonth:
    year: int
    month: int

@dataclass(frozen=True)
class YearQuarter:
    year: int
    quarter: int

def now_kst() -> datetime:
    return datetime.now(tz=KST)

def prev_month(when: datetime) -> YearMonth:
    y, m = when.year, when.month
    if m == 1:
        return YearMonth(y - 1, 12)
    return YearMonth(y, m - 1)

def ym_to_str(ym: YearMonth) -> str:
    return f"{ym.year:04d}-{ym.month:02d}"

def month_range(ym: YearMonth) -> tuple[date, date]:
    # inclusive start, exclusive end
    start = date(ym.year, ym.month, 1)
    if ym.month == 12:
        end = date(ym.year + 1, 1, 1)
    else:
        end = date(ym.year, ym.month + 1, 1)
    return start, end

def quarter_of_month(month: int) -> int:
    return (month - 1) // 3 + 1

def yq_from_date(d: date) -> YearQuarter:
    return YearQuarter(d.year, quarter_of_month(d.month))

def quarter_end_date(year: int, quarter: int) -> date:
    if quarter == 1:
        return date(year, 3, 31)
    if quarter == 2:
        return date(year, 6, 30)
    if quarter == 3:
        return date(year, 9, 30)
    if quarter == 4:
        return date(year, 12, 31)
    raise ValueError("quarter must be 1..4")

def quarter_deadline(year: int, quarter: int, buffer_days: int) -> date:
    return quarter_end_date(year, quarter) + timedelta(days=buffer_days)

def iter_last_n_quarters(today: date, n: int) -> list[YearQuarter]:
    # returns most recent first, including current quarter
    yq = yq_from_date(today)
    res: list[YearQuarter] = []
    y, q = yq.year, yq.quarter
    for _ in range(n):
        res.append(YearQuarter(y, q))
        q -= 1
        if q == 0:
            q = 4
            y -= 1
    return res

def report_quarters(today: date) -> list[YearQuarter]:
    """
    Reporting rule:
      - Use current year (today.year)
      - Show Q1..Q(current_quarter-1)
      - If current_quarter == 1, show previous year Q1..Q4
    Example:
      today=2026-11-01 -> current_quarter=4 -> previous year=2025 -> Q1..Q3
    """
    target_year = today.year
    if today.month <= 2:
        target_year = target_year-1

    count = 4
    return [YearQuarter(target_year, q) for q in range(1, count + 1)]
