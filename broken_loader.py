import json
from typing import Dict, List, cast


def load_data() -> List[Dict]:
    return cast(List[Dict], json.loads("[]"))
