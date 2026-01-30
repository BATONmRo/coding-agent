import os
import subprocess
from pathlib import Path
from github import Github


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
    # Ищем PR из head ветки (owner:branch)
    for pr in repo.get_pulls(state="open", base=base):
        if pr.head.ref == head_full.split(":")[-1]:
            # pr.head.ref это только branch, а head_full может быть owner:branch
            # поэтому сравниваем по branch
            return pr
    return None


def main():
    issue_number = os.environ["ISSUE_NUMBER"]
    repo_name = os.environ["GITHUB_REPOSITORY"]

    git_token = os.environ["GITHUB_TOKEN"]
    api_token = os.environ.get("GH_API_TOKEN", git_token)

    issue_title = os.environ.get("ISSUE_TITLE", "")
    issue_body = os.environ.get("ISSUE_BODY", "")

    gh = Github(api_token)
    repo = gh.get_repo(repo_name)

    ensure_label(repo, LABEL_REVIEW_REQUESTED, "cfd3d7")
    ensure_label(repo, LABEL_CHANGES_REQUESTED, "fbca04")
    ensure_label(repo, LABEL_APPROVED, "0e8a16")

    branch = f"agent/issue-{issue_number}"

    # 1) Ветку делаем идемпотентно
    run(f"git checkout -B {branch}")

    # 2) Пишем файл, который не будет конфликтовать между разными issue
    marker_path = Path(f"agent_was_here_issue_{issue_number}.txt")
    marker_path.write_text(
        "Hello from agent!\n"
        f"Issue #{issue_number}\n"
        f"Title: {issue_title}\n"
        f"Body:\n{issue_body}\n"
    )

    run("git config user.name 'code-agent'")
    run("git config user.email 'code-agent@users.noreply.github.com'")

    run(f"git add {marker_path.as_posix()}")

    # Если изменений нет — не коммитим (иначе git commit упадёт)
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

    # 3) Создаём PR, либо находим существующий (для итераций)
    pr_title = f"Auto-fix for issue #{issue_number}"
    pr_body = (
        f"Automated PR for issue #{issue_number}\n\n"
        f"### Issue title\n{issue_title}\n\n"
        f"### Issue body\n{issue_body}\n"
    )

    # head в формате owner:branch
    owner = repo_name.split("/")[0]
    head_full = f"{owner}:{branch}"

    pr = get_existing_pr(repo, head_full=head_full, base="main")
    if pr is None:
        pr = repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=branch,
            base="main",
        )
        print("PR created:", pr.html_url)
    else:
        # обновим body, чтобы держать контекст
        pr.edit(body=pr_body)
        print("PR already exists:", pr.html_url)

    # 4) Ставим label "нужно ревью"
    # Снимаем changes_requested/approved (агент сделал новую попытку)
    existing = {l.name for l in pr.get_labels()}
    if LABEL_CHANGES_REQUESTED in existing:
        pr.remove_from_labels(LABEL_CHANGES_REQUESTED)
    if LABEL_APPROVED in existing:
        pr.remove_from_labels(LABEL_APPROVED)

    if LABEL_REVIEW_REQUESTED not in existing:
        pr.add_to_labels(LABEL_REVIEW_REQUESTED)

    pr.create_issue_comment("🤖 Code Agent: изменения отправлены, запрашиваю AI review (`ai-review-requested`).")


if __name__ == "__main__":
    main()