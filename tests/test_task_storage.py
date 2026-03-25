import os

import pytest

from task_storage import add_task, load_tasks, save_tasks

task_file = "test_tasks.json"


def test_load_tasks_missing_file():
    assert load_tasks(task_file) == []


def test_save_and_load_tasks():
    tasks = [{"name": "Task 1"}, {"name": "Task 2"}]
    save_tasks(task_file, tasks)
    loaded_tasks = load_tasks(task_file)
    assert loaded_tasks == tasks


def test_add_task():
    add_task(task_file, {"name": "Task 3"})
    loaded_tasks = load_tasks(task_file)
    assert len(loaded_tasks) == 3
    assert loaded_tasks[-1] == {"name": "Task 3"}


def test_add_empty_task():
    with pytest.raises(ValueError, match="Task cannot be empty"):
        add_task(task_file, {})


@pytest.fixture(autouse=True)
def cleanup():
    yield
    if os.path.exists(task_file):
        os.remove(task_file)
