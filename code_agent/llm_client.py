import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

OPENAI_ENDPOINT = "https://api.vsegpt.ru/v1/chat/completions"

def _post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI HTTPError {e.code}: {body}") from e


def openai_complete(
    *,
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = 1200,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """
    Возвращает текст ответа модели.
    Использует env:
      OPENAI_API_KEY, OPENAI_MODEL
    """
    api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
    model = model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }

    resp = _post_json(OPENAI_ENDPOINT, headers, payload)
    try:
        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Unexpected OpenAI response shape: {resp}") from e


# Временная совместимость со старым кодом, чтобы не ломать agent.py сразу.
def yandexgpt_complete(
    *,
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = 1200,
    model: Optional[str] = None,
    iam_token: Optional[str] = None,
    folder_id: Optional[str] = None,
) -> str:
    return openai_complete(
        system=system,
        user=user,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
        api_key=iam_token,
    )