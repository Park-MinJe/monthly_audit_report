from __future__ import annotations
import json
import os
import requests
from typing import Any, Dict

def _truncate(s: str, max_chars: int = 12000) -> str:
    return s if len(s) <= max_chars else s[:max_chars] + "\n...[truncated]"

def summarize(provider: str, payload: Dict[str, Any]) -> str:
    provider = (provider or "none").lower()
    if provider == "none":
        print("(요약 미사용: SUMMARY_PROVIDER=none)")
        return "(요약 미사용: SUMMARY_PROVIDER=none)"

    text = _truncate(json.dumps(payload, ensure_ascii=False, indent=2))

    if provider == "openai":
        return _summarize_openai(text)

    return f"(알 수 없는 provider: {provider})"

def _summarize_openai(text: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip()
    if not api_key:
        return "(OpenAI 요약 실패: OPENAI_API_KEY 미설정)"

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    system = (
        "너는 기관 업무추진비 집행내역을 검토/요약하는 도우미야.\n"
        "입력은 엑셀 파싱 결과(JSON)이며, 다음 형식으로 한국어 요약을 작성해줘:\n"
        "1) 핵심 요약 3~6줄\n"
        "2) 이상/확인 포인트 bullet 3~8개(없으면 '없음')\n"
        "3) 데이터 품질 이슈 0~3개\n"
        "가능하면 구체적으로(반복 사용처, 큰 금액, 컬럼 불명확 등).\n"
    )

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
    }

    try:
        print("OpeaAI API 사용 시작")
        r = requests.post(url, headers=headers, json=body, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"(OpenAI 요약 실패: {e})"
    