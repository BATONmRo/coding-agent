import json
from typing import cast


def load_data() -> list[dict]:
    return cast(list[dict], json.loads("[]"))
