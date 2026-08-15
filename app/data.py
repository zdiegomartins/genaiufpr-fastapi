from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
ECOPONTOS_PATH = DATA_DIR / "ecopontos_curitiba.json"
BAIRROS_PATH = DATA_DIR / "bairros_curitiba_fallback.json"


def normalize_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", "-", without_accents).strip("-")


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache
def load_ecopontos() -> list[dict[str, Any]]:
    payload = _read_json(ECOPONTOS_PATH)
    items = payload["items"] if isinstance(payload, dict) else payload

    for item in items:
        item["normalized_bairro"] = normalize_key(item["bairro"])
        item["normalized_nome"] = normalize_key(item["nome"])

    return items


@lru_cache
def load_bairros_fallback() -> dict[str, dict[str, Any]]:
    payload = _read_json(BAIRROS_PATH)
    items = payload["items"] if isinstance(payload, dict) else payload
    return {normalize_key(item["nome"]): item for item in items}
