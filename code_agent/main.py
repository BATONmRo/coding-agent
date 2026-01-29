import subprocess
from pathlib import Path

def run(cmd):
    print(f"> {cmd}")
    subprocess.run(cmd, shell=True, check=True)

def main():
    print("=== CODE AGENT STARTED ===")

    # создаём тестовый файл
    path = Path("agent_was_here.txt")
    path.write_text("Hello from Code Agent\n")

    # git config
    run("git config user.name 'code-agent'")
    run("git config user.email 'code-agent@users.noreply.github.com'")

    # commit & push
    run("git add agent_was_here.txt")
    run("git commit -m 'chore: agent test commit'")
    run("git push")

    print("=== CODE AGENT FINISHED ===")

if __name__ == "__main__":
    main()
