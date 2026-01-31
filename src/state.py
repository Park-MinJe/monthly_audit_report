from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, Set, List

def load_seen(path: str) -> Set[str]:
    p = Path(path)
    if not p.exists():
        return set()
    data = json.loads(p.read_text(encoding="utf-8"))
    return set(data.get("seen_keys", []))

def save_seen(path: str, seen: Set[str]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {"seen_keys": sorted(seen)}
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
