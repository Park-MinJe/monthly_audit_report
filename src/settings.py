from __future__ import annotations
import os
from dataclasses import dataclass

def _get_int(name: str, default: int) -> int:
    v = os.getenv(name, str(default)).strip()
    try:
        return int(v)
    except Exception:
        return default

def _get_str(name: str, default: str) -> str:
    return os.getenv(name, default).strip()

@dataclass(frozen=True)
class Settings:
    orgs_xlsx_path: str
    state_seen_path: str
    state_cache_docs_path: str
    report_dir: str

    opengov_max_pages: int
    opengov_stop_after_empty: int
    opengov_http_timeout_sec: int

    quarter_buffer_days: int
    quarter_lookback_count: int

    summary_provider: str

    report_base_url: str

def load_settings() -> Settings:
    return Settings(
        orgs_xlsx_path=_get_str("ORGS_XLSX_PATH", "config/managed_orgs.xlsx"),
        state_seen_path=_get_str("STATE_SEEN_PATH", "state/seen.json"),
        state_cache_docs_path=_get_str("STATE_CACHE_DOCS_PATH", "state/cache_docs.json"),
        report_dir=_get_str("REPORT_DIR", "reports"),

        opengov_max_pages=_get_int("OPENGOV_MAX_PAGES", 300),
        opengov_stop_after_empty=_get_int("OPENGOV_STOP_AFTER_EMPTY", 2),
        opengov_http_timeout_sec=_get_int("OPENGOV_HTTP_TIMEOUT_SEC", 30),

        quarter_buffer_days=_get_int("QUARTER_BUFFER_DAYS", 30),
        quarter_lookback_count=_get_int("QUARTER_LOOKBACK_COUNT", 8),

        summary_provider=_get_str("SUMMARY_PROVIDER", "none").lower(),

        report_base_url=_get_str("REPORT_BASE_URL", ""),
    )
