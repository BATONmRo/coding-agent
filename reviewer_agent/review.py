import os
from github import Github


LABEL_REVIEW_REQUESTED = "ai-review-requested"
LABEL_CHANGES_REQUESTED = "ai-changes-requested"
LABEL_APPROVED = "ai-approved"


def ensure_label(repo, name: str, color: str = "ededed"):
    """Создаёт label если его нет."""
    try:
        repo.get_label(name)
    except Exception:
        repo.create_label(name=name, color=color)


def add_label(pr, name: str):
    existing = {l.name for l in pr.get_labels()}
    if name not in existing:
        pr.add_to_labels(name)


def remove_label(pr, name: str):
    existing = {l.name for l in pr.get_labels()}
    if name in existing:
        pr.remove_from_labels(name)


def pr_body_has_sections(pr_body: str) -> bool:
    """
    Проверяем наличие секций "Agent summary" и "How to verify" в теле PR.
    Допускаем разные регистры и заголовки Markdown.
    """
    text = (pr_body or "").lower()
    has_summary = "agent summary" in text
    has_verify = "how to verify" in text
    return has_summary and has_verify


def get_ci_status(repo, pr):
    """
    Возвращает (is_green, details_list)
    details_list — список строк по неуспешным статусам CI.
    Используем combined status — он совпадает с тем, что видно в GitHub UI.
    """
    commits = list(pr.get_commits())
    if not commits:
        return False, ["Нет коммитов в PR — CI проверить невозможно."]

    last_sha = commits[-1].sha
    commit = repo.get_commit(last_sha)

    combined = commit.get_combined_status()
    state = getattr(combined, "state", None) or combined.raw_data.get("state")

    # success / failure / pending / error
    if state != "success":
        details = [f"combined status: {state}"]
        for s in combined.statuses:
            st = getattr(s, "state", None) or s.raw_data.get("state")
            if st != "success":
                ctx = getattr(s, "context", None) or s.raw_data.get("context") or "unknown"
                details.append(f"{ctx}: {st}")
        return False, details

    return True, []


def main():
    token = os.environ["GITHUB_TOKEN"]
    repo_name = os.environ["GITHUB_REPOSITORY"]
    pr_number = int(os.environ["PR_NUMBER"])

    gh = Github(token)
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    # гарантируем, что labels существуют
    ensure_label(repo, LABEL_REVIEW_REQUESTED, "cfd3d7")
    ensure_label(repo, LABEL_CHANGES_REQUESTED, "fbca04")
    ensure_label(repo, LABEL_APPROVED, "0e8a16")

    files = list(pr.get_files())
    pr_body = pr.body or ""

    # 0) CI обязателен: если CI не зелёный — changes
    ci_green, ci_details = get_ci_status(repo, pr)

    notes = []
    verdict = "changes"

    # 1) Если PR пустой — changes
    if len(files) == 0:
        verdict = "changes"
        notes.append("В PR нет изменённых файлов. Похоже, агент ничего не сделал — нужны изменения в коде.")

    # 2) Если CI не зелёный — changes (даже если есть summary)
    elif not ci_green:
        verdict = "changes"
        notes.append("CI не зелёный — сначала нужно починить проверки.")
        for d in ci_details:
            notes.append(f"CI fail: {d}")

    # 3) CI зелёный: проверяем наличие summary/how-to-verify
    else:
        if pr_body_has_sections(pr_body):
            verdict = "approved"
            notes.append("CI зелёный и в PR body есть секции `Agent summary` и `How to verify` — можно принимать.")
        else:
            verdict = "changes"
            notes.append("CI зелёный, но не вижу в PR body секции `Agent summary` и `How to verify`.")
            notes.append("Добавь краткое описание: что сделано и как проверить (в PR description).")

    # Пишем комментарий в PR
    body_lines = [
        "## 🤖 AI Reviewer report",
        f"PR: #{pr.number}",
        "",
        "### Результат:",
        "- ✅ Approved" if verdict == "approved" else "- ❌ Changes requested",
        "",
        "### Замечания / что сделать:",
        *[f"- {n}" for n in notes],
        "",
        "### Что дальше будет делать автоматика:",
        "- Если стоит `ai-changes-requested`, Code Agent должен внести правки и снова поставить `ai-review-requested`.",
        "- Если стоит `ai-approved`, цикл завершён.",
    ]
    pr.create_issue_comment("\n".join(body_lines))

    # Обновляем labels по вердикту
    remove_label(pr, LABEL_REVIEW_REQUESTED)

    if verdict == "approved":
        remove_label(pr, LABEL_CHANGES_REQUESTED)
        add_label(pr, LABEL_APPROVED)
    else:
        remove_label(pr, LABEL_APPROVED)
        add_label(pr, LABEL_CHANGES_REQUESTED)

    print(f"Reviewer finished: verdict={verdict} PR={pr.html_url}")


if __name__ == "__main__":
    main()