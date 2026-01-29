import os

def main():
    issue_title = os.getenv("ISSUE_TITLE")
    issue_body = os.getenv("ISSUE_BODY")

    print("=== CODE AGENT STARTED ===")
    print("Issue title:", issue_title)
    print("Issue body:", issue_body)
    print("=== CODE AGENT FINISHED ===")

if __name__ == "__main__":
    main()

