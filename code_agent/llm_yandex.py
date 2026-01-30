import json
import os
import urllib.request
from typing import Any, Dict, Optional


YANDEX_ENDPOINT = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


def _post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


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
    """
    Возвращает text ответа модели (строкой).
    Использует env:
      YANDEX_IAM_TOKEN, YANDEX_FOLDER_ID, YANDEX_MODEL
    """
    iam_token = iam_token or os.environ.get("YANDEX_IAM_TOKEN", "")
    folder_id = folder_id or os.environ.get("YANDEX_FOLDER_ID", "")
    model = model or os.environ.get("YANDEX_MODEL", "yandexgpt-lite")

    if not iam_token:
        raise RuntimeError("Missing YANDEX_IAM_TOKEN")
    if not folder_id:
        raise RuntimeError("Missing YANDEX_FOLDER_ID")

    headers = {
        "Authorization": f"Bearer {iam_token}",
        "x-folder-id": folder_id,
        "Content-Type": "application/json",
    }

    payload = {
        "modelUri": f"gpt://{folder_id}/{model}",
        "completionOptions": {
            "temperature": temperature,
            "maxTokens": max_tokens,
        },
        "messages": [
            {"role": "system", "text": system},
            {"role": "user", "text": user},
        ],
    }

    resp = _post_json(YANDEX_ENDPOINT, headers, payload)
    try:
        return resp["result"]["alternatives"][0]["message"]["text"]
    except Exception as e:
        raise RuntimeError(f"Unexpected YandexGPT response shape: {resp}") from e