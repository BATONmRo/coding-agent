import json
from typing import Any, Dict, List, cast


def load_data() -> List[Dict[str, Any]]:
    return cast(List[Dict[str, Any]], json.loads("[]"))
