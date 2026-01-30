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

    # Простое “ревью” для MVP:
    # 1) Если нет файлов — просим изменения
    # 2) Если изменены только agent_was_here...txt — считаем ок
    # 3) Иначе просим добавить описание/README (как пример требования)
    if len(files) == 0:
        verdict = "changes"
        notes = ["В PR нет изменённых файлов. Похоже, агент ничего не сделал — нужно добавить изменения."]
    else:
        changed_paths = [f.filename for f in files]
        only_markers = all(p.startswith("agent_was_here") and p.endswith(".txt") for p in changed_paths)

        if only_markers:
            verdict = "approved"
            notes = [
                "Изменения выглядят как маркер/проверка работы пайплайна — ок для MVP.",
                "Следующий шаг по ТЗ: агент должен изменять реальный код/файлы согласно Issue и добавлять summary."
            ]
        else:
            verdict = "changes"
            notes = [
                "Вижу изменения не только маркерных файлов.",
                "Пожалуйста добавь в PR summary: что сделано и как проверить (в README или в описании PR)."
            ]

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