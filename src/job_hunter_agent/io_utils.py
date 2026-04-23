from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def dump_json(path: str | Path, payload: Any) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def dataclass_list_to_dicts(items: list[Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in items:
        if is_dataclass(item):
            output.append(asdict(item))
        else:
            output.append(dict(item.__dict__))
    return output
