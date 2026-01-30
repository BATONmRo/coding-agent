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