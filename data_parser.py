from typing import cast


def parse_items() -> list[dict]:
    import json

    return cast(list[dict], json.loads("[]"))
