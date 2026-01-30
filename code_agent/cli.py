import argparse
import os
import sys

from code_agent.agent import run_issue_to_pr


def env_or(value: str | None, env_name: str, required: bool = True) -> str:
    if value:
        return value
    v = os.environ.get(env_name)
    if v:
        return v
    if required:
        raise SystemExit(f"Missing {env_name}. Provide --{env_name.lower()} or set env {env_name}.")
    return ""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="code-agent")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Create/update PR for a GitHub Issue")
    run.add_argument("--issue", dest="issue_number", help="Issue number, e.g. 17")
    run.add_argument("--repo", dest="repo_name", help="owner/repo, e.g. BATONmRo/coding-agent")
    run.add_argument("--base", dest="base_branch", default="main", help="Base branch (default: main)")

    run.add_argument("--issue-title", dest="issue_title", default="", help="Issue title")
    run.add_argument("--issue-body", dest="issue_body", default="", help="Issue body")

    run.add_argument("--pr", dest="pr_number", help="Pull request number for iteration mode")

    run.add_argument(
        "--git-token",
        dest="git_token",
        help="Token used for git operations (fallback env: GITHUB_TOKEN)",
    )
    run.add_argument(
        "--api-token",
        dest="api_token",
        help="Token used for GitHub API (fallback env: GH_API_TOKEN then GITHUB_TOKEN)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "run":
        issue_number = env_or(args.issue_number, "ISSUE_NUMBER")
        repo_name = env_or(args.repo_name, "GITHUB_REPOSITORY")
        base_branch = args.base_branch

        issue_title = args.issue_title or os.environ.get("ISSUE_TITLE", "")
        issue_body = args.issue_body or os.environ.get("ISSUE_BODY", "")

        git_token = args.git_token or os.environ.get("GITHUB_TOKEN", "")
        api_token = args.api_token or os.environ.get("GH_API_TOKEN") or os.environ.get("GITHUB_TOKEN", "")

        if not git_token:
            raise SystemExit("Missing git token: provide --git-token or set GITHUB_TOKEN")
        if not api_token:
            raise SystemExit("Missing api token: provide --api-token or set GH_API_TOKEN/GITHUB_TOKEN")

        pr_number = args.pr_number or os.environ.get("PR_NUMBER", "")

        run_issue_to_pr(
            issue_number=issue_number,
            repo_name=repo_name,
            git_token=git_token,
            api_token=api_token,
            base_branch=base_branch,
            issue_title=issue_title,
            issue_body=issue_body,
            pr_number=pr_number,
        )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())