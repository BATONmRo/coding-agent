from typing import cast


def load_data() -> list[dict]:
    import json

    return cast(list[dict], json.loads("[]"))
