import json
import os


def load_tasks(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_tasks(path: str, tasks: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(tasks, file, ensure_ascii=False, indent=4)


def add_task(path: str, task: dict) -> None:
    if not task:
        raise ValueError("Task cannot be empty")
    tasks = load_tasks(path)
    tasks.append(task)
    save_tasks(path, tasks)
