from __future__ import annotations

import os
from typing import Any

import requests


class GoogleMapsError(RuntimeError):
    """Raised when a Google Maps API call cannot be used."""


class GoogleMapsClient:
    GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

    def __init__(self, api_key: str | None = None, timeout: int = 8) -> None:
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY")
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def geocode_bairro(self, bairro: str) -> dict[str, Any]:
        if not self.api_key:
            raise GoogleMapsError("GOOGLE_MAPS_API_KEY nao configurada.")

        params = {
            "address": f"{bairro}, Curitiba, PR, Brasil",
            "components": "country:BR|administrative_area:PR|locality:Curitiba",
            "language": "pt-BR",
            "region": "br",
            "key": self.api_key,
        }
        response = requests.get(self.GEOCODING_URL, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()

        if payload.get("status") != "OK" or not payload.get("results"):
            raise GoogleMapsError(
                f"Geocoding API nao retornou resultado valido: {payload.get('status')}"
            )

        result = payload["results"][0]
        location = result["geometry"]["location"]
        return {
            "descricao": result["formatted_address"],
            "latitude": location["lat"],
            "longitude": location["lng"],
            "metodo": "google_geocoding",
        }

    def distance_matrix(
        self,
        origin: tuple[float, float],
        destinations: list[dict[str, Any]],
        mode: str,
    ) -> list[dict[str, Any] | None]:
        if not self.api_key:
            raise GoogleMapsError("GOOGLE_MAPS_API_KEY nao configurada.")

        destination_values = "|".join(
            f"{item['latitude']},{item['longitude']}" for item in destinations
        )
        params = {
            "origins": f"{origin[0]},{origin[1]}",
            "destinations": destination_values,
            "mode": mode,
            "language": "pt-BR",
            "units": "metric",
            "key": self.api_key,
        }
        response = requests.get(
            self.DISTANCE_MATRIX_URL, params=params, timeout=self.timeout
        )
        response.raise_for_status()
        payload = response.json()

        if payload.get("status") != "OK":
            raise GoogleMapsError(
                f"Distance Matrix API nao retornou resultado valido: {payload.get('status')}"
            )

        elements = payload["rows"][0]["elements"]
        distances: list[dict[str, Any] | None] = []
        for element in elements:
            if element.get("status") != "OK":
                distances.append(None)
                continue

            distances.append(
                {
                    "distancia_metros": element["distance"]["value"],
                    "distancia_texto": element["distance"]["text"],
                    "duracao_texto": element["duration"]["text"],
                }
            )

        return distances
