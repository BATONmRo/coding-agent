import json
import subprocess
from pathlib import Path
from typing import List, Tuple

from github import Github

from code_agent.llm_client import yandexgpt_complete

LABEL_REVIEW_REQUESTED = "ai-review-requested"
LABEL_CHANGES_REQUESTED = "ai-changes-requested"
LABEL_APPROVED = "ai-approved"


def run(cmd: str):
    print(f"> {cmd}")
    subprocess.run(cmd, shell=True, check=True)


def ensure_label(repo, name: str, color: str = "ededed"):
    try:
        repo.get_label(name)
    except Exception:
        repo.create_label(name=name, color=color)


def get_existing_pr(repo, head_full: str, base: str = "main"):
    for pr in repo.get_pulls(state="open", base=base):
        if pr.head.ref == head_full.split(":")[-1]:
            return pr
    return None


def is_safe_relative_path(path: str) -> bool:
    p = Path(path)
    return not p.is_absolute() and ".." not in p.parts


ALLOWED_ACTIONS = {"create", "update", "delete"}


def extract_json(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""

    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    if start == -1:
        return ""

    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return ""


def get_last_reviewer_comment(pr) -> str:
    """
    Берём последний комментарий бота github-actions со словами 'AI Reviewer report' (если есть).
    """
    comments = list(pr.get_issue_comments())
    comments.reverse()
    for c in comments:
        body = c.body or ""
        if c.user and c.user.login == "github-actions[bot]" and "AI Reviewer report" in body:
            return body
    return ""


def get_ci_failures(repo, pr) -> List[Tuple[str, str]]:
    """
    Возвращает список (check_name, details_text) только для упавших checks на последнем коммите PR.
    """
    commits = list(pr.get_commits())
    if not commits:
        return []
    last_sha = commits[-1].sha
    commit = repo.get_commit(last_sha)

    failures: List[Tuple[str, str]] = []
    try:
        check_runs = list(commit.get_check_runs())
    except Exception:
        check_runs = []

    for cr in check_runs:
        # conclusion может быть failure/cancelled/success
        conclusion = getattr(cr, "conclusion", None) or cr.raw_data.get("conclusion")
        name = getattr(cr, "name", None) or cr.raw_data.get("name") or "unknown-check"

        if conclusion in ("failure", "cancelled", "timed_out", "action_required"):
            out = cr.raw_data.get("output", {}) if hasattr(cr, "raw_data") else {}
            title = out.get("title") or ""
            summary = out.get("summary") or ""
            text = out.get("text") or ""
            details = "\n".join([title, summary, text]).strip()

            # ограничим размер, чтобы не спалить токены
            if len(details) > 4000:
                details = details[:4000] + "\n...(truncated)..."

            if not details:
                details = f"{name} failed (no output text available)."

            failures.append((name, details))

    return failures


def run_issue_to_pr(
    *,
    issue_number: str,
    repo_name: str,
    api_token: str,
    base_branch: str = "main",
    issue_title: str = "",
    issue_body: str = "",
    pr_number: str = "",
):
    """
    Главная бизнес-логика code-agent:
    - создает/обновляет ветку agent/issue-N
    - делает коммит (с маркерным файлом пока)
    - создает/обновляет PR
    - ставит ai-review-requested
    """
    gh = Github(api_token)
    repo = gh.get_repo(repo_name)

    ensure_label(repo, LABEL_REVIEW_REQUESTED, "cfd3d7")
    ensure_label(repo, LABEL_CHANGES_REQUESTED, "fbca04")
    ensure_label(repo, LABEL_APPROVED, "0e8a16")

    # --- ITERATION MODE: если пришли из PR Fix, у нас есть PR_NUMBER ---
    pr = None
    branch = f"agent/issue-{issue_number}"

    if pr_number:
        pr = repo.get_pull(int(pr_number))
        branch = pr.head.ref  # ветка PR
        issue_title = issue_title or pr.title or ""
        issue_body = issue_body or (pr.body or "")

    # checkout нужной ветки
    run(f"git checkout {base_branch}")
    run(f"git pull origin {base_branch}")
    run(f"git checkout -B {branch}")

    reviewer_comment = ""
    ci_failures = []

    if pr is not None:
        reviewer_comment = get_last_reviewer_comment(pr)
        ci_failures = get_ci_failures(repo, pr)

    ci_block = ""
    if ci_failures:
        parts = []
        for name, details in ci_failures:
            parts.append(f"## CHECK FAILED: {name}\n{details}")
        ci_block = "\n\n".join(parts)

    system = "Ты агент-разработчик. Верни только валидный JSON без пояснений."

    user = f"""
    Задача (Issue/PR контекст):
    TITLE: {issue_title}

    BODY:
    {issue_body}

    Замечания ревьюера (если есть):
    {reviewer_comment}

    Ошибки CI (если есть):
    {ci_block}

    Сгенерируй изменения, чтобы:
    - выполнить требования задачи
    - исправить замечания ревьюера
    - сделать CI зелёным (ruff/black/mypy/pytest)

    Верни JSON строго в формате:
    {{
    "summary": "что сделано (1-3 предложения)",
    "changes": [
        {{"path":"...", "action":"create|update|delete", "content":"полный новый контент файла для create/update"}}
    ]
    }}

    Правила (строго):
    - Никакого текста вне JSON.
    - Запрещено использовать заглушки: "...", "…", "TODO", "TBD", "<...>", "[...]".
    - Не меняй README.md, если задача явно не про документацию.
    - Не изменяй файлы внутри папок code_agent/ и reviewer_agent/.
    - Для Python-кода сразу соблюдай стиль, совместимый с ruff и black.
    - Если CI упал — приоритет исправить CI.
    """

    raw = yandexgpt_complete(system=system, user=user, temperature=0.2, max_tokens=2200)
    json_text = extract_json(raw)
    if not json_text:
        raise RuntimeError(f"LLM did not return JSON. Raw (first 200): {raw[:200]!r}")

    patch = json.loads(json_text)
    summary = (patch.get("summary") or "").strip()
    changes = patch.get("changes") or []
    if not changes:
        raise RuntimeError("LLM returned no changes")

    def contains_placeholders(s: str) -> bool:
        bad = ["...", "…", "TODO", "TBD", "<...>", "[...]"]
        s_up = s.upper()
        return any(b in s for b in bad) or any(b in s_up for b in ["TODO", "TBD"])

    # проверяем все create/update content
    bad_files = []
    for ch in patch.get("changes", []):
        action = ch.get("action")
        path = ch.get("path", "unknown")

        if action not in ALLOWED_ACTIONS:
            raise RuntimeError(f"Unsupported action from LLM: {action}")

        if not is_safe_relative_path(path):
            raise RuntimeError(f"Unsafe path from LLM: {path}")

        if action in ("create", "update"):
            content = ch.get("content", "")
            if contains_placeholders(content):
                bad_files.append(path)

    if bad_files:
        # повторный запрос: "перепиши без заглушек"
        repair_user = f"""
    Ты вернул заглушки в файлах: {bad_files}.
    Нужно переписать контент БЕЗ плейсхолдеров ("...", "…", "TODO", "TBD", "<...>", "[...]").

    Верни ТОЛЬКО валидный JSON формата:
    {{"summary": "...", "changes":[{{"path":"...", "action":"update|create|delete", "content":"..."}}]}}

    Задача:
    TITLE: {issue_title}
    BODY:
    {issue_body}
    """
        raw3 = yandexgpt_complete(
            system=system, user=repair_user, temperature=0.2, max_tokens=2200
        ).strip()
        json_text3 = extract_json(raw3)
        if not json_text3:
            raise RuntimeError("LLM retry did not return JSON")
        patch = json.loads(json_text3)

    summary = patch.get("summary", "").strip()
    changes = patch.get("changes", [])
    if not isinstance(changes, list) or not changes:
        raise RuntimeError(f"LLM returned no changes. Raw: {raw}")

    # --- применяем изменения ---
    for ch in changes:
        path = ch["path"]
        action = ch["action"]

        if action not in ALLOWED_ACTIONS:
            raise RuntimeError(f"Unsupported action from LLM: {action}")
        if not is_safe_relative_path(path):
            raise RuntimeError(f"Unsafe path from LLM: {path}")

        p = Path(path)

        if action == "delete":
            if p.exists():
                p.unlink()
            continue

        content = ch.get("content")
        if content is None:
            raise RuntimeError(f"Missing content for {action} {path}")
        if contains_placeholders(content):
            raise RuntimeError(f"Refusing to write placeholder content for {path}")

        if path.startswith("code_agent/") or path.startswith("reviewer_agent/"):
            raise RuntimeError(f"Refusing to modify agent internals directly: {path}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    # --- автофикс стиля и линтера перед коммитом ---
    try:
        run("python -m ruff check . --fix")
    except Exception as e:
        print(f"ruff --fix failed: {e}")

    try:
        run("python -m black .")
    except Exception as e:
        print(f"black failed: {e}")

    run("git config user.name 'code-agent'")
    run("git config user.email 'code-agent@users.noreply.github.com'")

    run("git add -A")

    result = subprocess.run("git diff --cached --quiet", shell=True)
    has_changes = result.returncode != 0

    if not has_changes:
        print("No staged changes. Exiting without commit/push.")
        return

    run(f"git commit -m 'chore: agent update for issue #{issue_number}'")
    run(f"git push origin {branch}")

    pr_title = f"Auto-fix for issue #{issue_number}"
    pr_body = (
        f"Automated PR for issue #{issue_number}\n\n"
        f"### Issue title\n{issue_title}\n\n"
        f"### Issue body\n{issue_body}\n\n"
        f"### Agent summary\n{summary}\n\n"
        f"### How to verify\n"
        f"- Открой PR и убедись, что CI зелёный (ruff/black/mypy/pytest).\n"
        f"- Посмотри вкладку Files changed и проверь, что правки соответствуют Issue.\n"
        f"- Локально (опционально): `pytest -q`.\n"
    )

    owner = repo_name.split("/")[0]
    head_full = f"{owner}:{branch}"

    pr = get_existing_pr(repo, head_full=head_full, base=base_branch)
    if pr is None:
        pr = repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=branch,
            base=base_branch,
        )
        print("PR created:", pr.html_url)
    else:
        pr.edit(body=pr_body)
        print("PR already exists:", pr.html_url)

        # --- labels: после любых изменений всегда запрашиваем новое ревью ---
    labels_now = {label.name for label in pr.get_labels()}

    # если были запрошены изменения — мы сделали новую попытку
    if LABEL_CHANGES_REQUESTED in labels_now:
        pr.remove_from_labels(LABEL_CHANGES_REQUESTED)

    # если вдруг был approved — новая попытка отменяет approved
    if LABEL_APPROVED in labels_now:
        pr.remove_from_labels(LABEL_APPROVED)

    # пересчитываем после removals
    labels_now = {label.name for label in pr.get_labels()}
    if LABEL_REVIEW_REQUESTED not in labels_now:
        pr.add_to_labels(LABEL_REVIEW_REQUESTED)

    pr.create_issue_comment(
        "🤖 Code Agent: изменения отправлены, запрашиваю AI review (`ai-review-requested`)."
    )
