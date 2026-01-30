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
