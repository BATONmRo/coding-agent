import os
import subprocess
from pathlib import Path
from github import Github

def run(cmd):
    print(f"> {cmd}")
    subprocess.run(cmd, shell=True, check=True)

def main():
    issue_number = os.environ["ISSUE_NUMBER"]
    repo_name = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]

    branch = f"agent/issue-{issue_number}"

    print("=== CODE AGENT STARTED ===")
    print("Branch:", branch)

    # создаём ветку
    run(f"git checkout -b {branch}")

    # создаём файл (пока тестовый)
    Path("agent_was_here.txt").write_text(
        f"Hello from agent for issue #{issue_number}\n"
    )

    # git config
    run("git config user.name 'code-agent'")
    run("git config user.email 'code-agent@users.noreply.github.com'")

    run("git add agent_was_here.txt")
    run(f"git commit -m 'fix: automated change for issue #{issue_number}'")
    run(f"git push origin {branch}")

    # создаём PR
    gh = Github(token)
    repo = gh.get_repo(repo_name)

    pr = repo.create_pull(
        title=f"Auto-fix for issue #{issue_number}",
        body=f"Automated PR for issue #{issue_number}",
        head=branch,
        base="main",
    )

    print("PR created:", pr.html_url)
    print("=== CODE AGENT FINISHED ===")

if __name__ == "__main__":
    main()
