import os
import json
import re
import subprocess
from pathlib import Path
from github import Github
from code_agent.llm_yandex import yandexgpt_complete

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


def run_issue_to_pr(
    *,
    issue_number: str,
    repo_name: str,
    git_token: str,
    api_token: str,
    base_branch: str = "main",
    issue_title: str = "",
    issue_body: str = "",
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

    branch = f"agent/issue-{issue_number}"

    run(f"git checkout -B {branch}")

    # --- LLM: просим вернуть JSON с патчем ---
    system = "Ты агент-разработчик. Возвращай только валидный JSON без пояснений."
    user = f"""
    Задача (Issue):
    TITLE: {issue_title}
    BODY:
    {issue_body}

    Сгенерируй изменения для репозитория.
    Верни JSON строго в формате:
    {{
    "summary": "коротко что сделано",
    "changes": [
        {{"path": "путь/к/файлу", "action": "create|update|delete", "content": "текст файла (для create/update)"}}
    ]
    }}

    Правила (строго):
    - Запрещено использовать заглушки: "...", "…", "TODO", "TBD", "<...>", "[...]".
    - Никакого текста вне JSON.
    - Если изменяешь README.md:
    - переписывай файл ЦЕЛИКОМ
    - минимальный размер README — 30 строк
    - README должен быть самодостаточным
    - README ОБЯЗАН содержать:
    1) Описание проекта
    2) Как работает агент (Issue → PR → Review → Iteration)
    3) Список workflow с названиями файлов и триггерами
    4) Secrets и зачем они нужны
    5) Локальный запуск (pip install, python -m code_agent.cli run)
    6) Как проверить работу (пошагово)
    - Пиши конкретные команды и шаги, не описания в общем виде.
    """

    raw = yandexgpt_complete(system=system, user=user, temperature=0.2, max_tokens=1800).strip()
    print("LLM raw (first 200 chars):", raw[:200].replace("\n", "\\n"))

    def extract_json(text: str) -> str:
        # 1) Если уже начинается с { - пробуем как есть
        if text.lstrip().startswith("{"):
            return text
        # 2) Вырезаем первый JSON-объект из текста (если модель добавила пояснения)
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return m.group(0)
        return ""

    json_text = extract_json(raw)

    # Если пусто — пробуем ещё раз с более строгой формулировкой
    if not json_text:
        repair_user = f"""
    Ты вернул ответ не в JSON. Верни ТОЛЬКО валидный JSON без текста вокруг.
    Формат:
    {{
    "summary": "коротко что сделано",
    "changes": [
        {{"path": "README.md", "action": "update", "content": "полный текст файла"}}
    ]
    }}
    Задача:
    TITLE: {issue_title}
    BODY:
    {issue_body}
    """
        raw2 = yandexgpt_complete(system=system, user=repair_user, temperature=0.2, max_tokens=1800).strip()
        print("LLM raw2 (first 200 chars):", raw2[:200].replace("\n", "\\n"))
        json_text = extract_json(raw2)

    if not json_text:
        raise RuntimeError("LLM did not return JSON. See logs for raw output.")

    patch = json.loads(json_text)

    def contains_placeholders(s: str) -> bool:
        bad = ["...", "…", "TODO", "TBD", "<...>", "[...]"]
        s_up = s.upper()
        return any(b in s for b in bad) or any(b in s_up for b in ["TODO", "TBD"])

    # проверяем все create/update content
    bad_files = []
    for ch in patch.get("changes", []):
        if ch.get("action") in ("create", "update"):
            content = ch.get("content", "")
            if contains_placeholders(content):
                bad_files.append(ch.get("path", "unknown"))

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
        raw3 = yandexgpt_complete(system=system, user=repair_user, temperature=0.2, max_tokens=2200).strip()
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
        p = Path(path)

        if action == "delete":
            if p.exists():
                p.unlink()
            continue

        content = ch.get("content")
        if content is None:
            raise RuntimeError(f"Missing content for {action} {path}")

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    run("git config user.name 'code-agent'")
    run("git config user.email 'code-agent@users.noreply.github.com'")

    run("git add -A")

    # Если изменений нет — не коммитим
    try:
        run("git diff --cached --quiet || echo 'has_changes=1' > /tmp/has_changes")
        has_changes = Path("/tmp/has_changes").exists()
    except Exception:
        has_changes = True

    if not has_changes:
        print("No staged changes. Exiting without commit/push.")
        return

    run(f"git commit -m 'chore: agent update for issue #{issue_number}'")
    run(f"git push origin {branch}")

    pr_title = f"Auto-fix for issue #{issue_number}"
    pr_body = (
        f"Automated PR for issue #{issue_number}\n\n"
        f"### Issue title\n{issue_title}\n\n"
        f"### Issue body\n{issue_body}\n"
        f"### Agent summary\n{summary}\n"
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

    existing = {l.name for l in pr.get_labels()}
    if LABEL_CHANGES_REQUESTED in existing:
        pr.remove_from_labels(LABEL_CHANGES_REQUESTED)
    if LABEL_APPROVED in existing:
        pr.remove_from_labels(LABEL_APPROVED)
    if LABEL_REVIEW_REQUESTED not in existing:
        pr.add_to_labels(LABEL_REVIEW_REQUESTED)

    pr.create_issue_comment(
        "🤖 Code Agent: изменения отправлены, запрашиваю AI review (`ai-review-requested`)."
    )