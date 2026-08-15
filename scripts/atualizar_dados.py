from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT_DIR / "data" / "ecopontos_curitiba.json"
INDEX_URL = "https://dadosabertos.c3sl.ufpr.br/curitiba/UnidadesAtendimentoCuritiba/"
GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"

RESIDUOS_MISTOS = [
    "reciclavel",
    "eletronico",
    "oleo_cozinha",
    "madeira",
    "moveis",
    "residuos_vegetais",
    "construcao_civil",
]


def slugify(value: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", "-", without_accents).strip("-")


def download_text(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def download_bytes(url: str) -> bytes:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.content


def latest_csv_url(index_html: str) -> str:
    matches = re.findall(r'href="([^"]+Base_de_Dados\.csv)"', index_html)
    if not matches:
        raise RuntimeError("Nenhum CSV de base de dados encontrado no indice.")
    latest = sorted(matches)[-1]
    return urljoin(INDEX_URL, latest)


def decode_csv(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise RuntimeError("Nao foi possivel detectar encoding do CSV.")


def load_existing() -> dict[str, dict[str, Any]]:
    if not DATA_PATH.exists():
        return {}
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {item["id"]: item for item in payload.get("items", [])}


def geocode(address: str, api_key: str) -> tuple[float, float] | None:
    params = {
        "address": address,
        "components": "country:BR|administrative_area:PR|locality:Curitiba",
        "language": "pt-BR",
        "region": "br",
        "key": api_key,
    }
    response = requests.get(GEOCODING_URL, params=params, timeout=20)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "OK" or not payload.get("results"):
        return None
    location = payload["results"][0]["geometry"]["location"]
    return location["lat"], location["lng"]


def build_item(
    row: dict[str, str],
    existing_by_id: dict[str, dict[str, Any]],
    use_geocode: bool,
    api_key: str | None,
) -> dict[str, Any]:
    name = row["NM_EQUI"].strip()
    item_id = f"ecoponto-{slugify(name)}"
    existing = existing_by_id.get(item_id, {})
    street = row["NM_RUA"].strip().title()
    number = row["NUMERO_EQUI"].strip()
    bairro = row["NM_BAIRRO"].strip().title()
    address = f"{street}, {number} - {bairro}, Curitiba - PR"

    latitude = existing.get("latitude")
    longitude = existing.get("longitude")
    if use_geocode and api_key:
        coordinates = geocode(address, api_key)
        if coordinates:
            latitude, longitude = coordinates

    residuos = RESIDUOS_MISTOS
    if slugify(name) == "parque-gomm":
        residuos = ["reciclavel", "oleo_cozinha", "gordura_pos_consumo"]

    return {
        "id": item_id,
        "nome": f"Ecoponto {name}",
        "bairro": bairro,
        "regional": row["NM_REGIONAL"].strip().title(),
        "endereco": address,
        "latitude": latitude,
        "longitude": longitude,
        "telefone": row["TELEFONE_EQUI"].strip() or "156",
        "email": row["EMAIL_EQUI"].strip() or "smma@curitiba.pr.gov.br",
        "funcionamento": "Segunda a sabado, das 8h as 12h e das 13h as 17h",
        "residuos_aceitos": residuos,
        "fonte_url": existing.get("fonte_url", row["SITE_EQUI"].strip()),
    }


def parse_items(
    csv_text: str, use_geocode: bool, api_key: str | None
) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(csv_text), delimiter=";")
    existing = load_existing()
    items = []
    for row in reader:
        if row.get("DS_TEMA", "").strip().upper() != "MEIO AMBIENTE":
            continue
        if row.get("DS_TP_EQUIPAMENTO", "").strip() != "Depósito de Resíduos Sólidos":
            continue
        if "ecoponto" not in row.get("DS_SUBTIPO_EQUIPAMENTO", "").lower():
            continue
        items.append(build_item(row, existing, use_geocode, api_key))
    return sorted(items, key=lambda item: item["nome"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Atualiza a base local de Ecopontos.")
    parser.add_argument(
        "--geocode",
        action="store_true",
        help="Usa GOOGLE_MAPS_API_KEY para geocodificar enderecos.",
    )
    args = parser.parse_args()

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if args.geocode and not api_key:
        raise RuntimeError("Defina GOOGLE_MAPS_API_KEY para usar --geocode.")

    index_html = download_text(INDEX_URL)
    csv_url = latest_csv_url(index_html)
    csv_text = decode_csv(download_bytes(csv_url))
    items = parse_items(csv_text, args.geocode, api_key)

    payload = {
        "metadata": {
            "descricao": "Ecopontos de Curitiba usados pela API Recicla Curitiba.",
            "base_principal": "Portal de Dados Abertos de Curitiba - Unidades de Atendimento de Curitiba - Ativas",
            "csv_url": csv_url,
            "gerado_em": datetime.now(timezone.utc).isoformat(),
        },
        "items": items,
    }
    DATA_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Atualizados {len(items)} Ecopontos em {DATA_PATH}")


if __name__ == "__main__":
    main()
