from code_agent.cli import build_parser


def test_cli_has_run_command():
    parser = build_parser()
    args = parser.parse_args(["run", "--base", "main"])
    assert args.command == "run"
    assert args.base_branch == "main"