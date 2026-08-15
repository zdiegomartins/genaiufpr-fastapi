from __future__ import annotations

import math
import os
from dotenv import load_dotenv
from typing import Any

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.data import load_bairros_fallback, load_ecopontos, normalize_key
from app.google_maps import GoogleMapsClient, GoogleMapsError

TIPOS_VALIDOS = {"todos", "reciclavel", "eletronico"}
MODOS_VALIDOS = {"driving", "walking", "bicycling", "transit"}

load_dotenv()

app = FastAPI(
    title="Recicla Curitiba API",
    description=(
        "Consulta pontos de coleta de residuos reciclaveis e eletroeletronicos "
        "em Curitiba a partir do bairro informado."
    ),
    version="1.0.0",
)


def haversine_meters(
    origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float
) -> int:
    radius_meters = 6_371_000
    lat1 = math.radians(origin_lat)
    lat2 = math.radians(dest_lat)
    delta_lat = math.radians(dest_lat - origin_lat)
    delta_lng = math.radians(dest_lng - origin_lng)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(radius_meters * c)


def format_distance(meters: int) -> str:
    if meters < 1000:
        return f"{meters} m"
    return f"{meters / 1000:.1f} km".replace(".", ",")


def maps_search_url(latitude: float, longitude: float) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"


def maps_directions_url(
    origin: dict[str, Any], destination: dict[str, Any], mode: str
) -> str:
    return (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={origin['latitude']},{origin['longitude']}"
        f"&destination={destination['latitude']},{destination['longitude']}"
        f"&travelmode={mode}"
    )


def filter_by_tipo(items: list[dict[str, Any]], tipo: str) -> list[dict[str, Any]]:
    if tipo == "todos":
        return items
    return [item for item in items if tipo in item["residuos_aceitos"]]


def resolve_origin(
    bairro: str, google_client: GoogleMapsClient
) -> tuple[dict[str, Any], str | None]:
    google_error: str | None = None

    if google_client.enabled:
        try:
            return google_client.geocode_bairro(bairro), None
        except (GoogleMapsError, requests.RequestException, KeyError) as exc:
            google_error = str(exc)

    bairros = load_bairros_fallback()
    fallback = bairros.get(normalize_key(bairro))
    if fallback:
        return {
            "descricao": f"{fallback['nome']}, Curitiba - PR",
            "latitude": fallback["latitude"],
            "longitude": fallback["longitude"],
            "metodo": "fallback_local",
        }, google_error

    bairros_disponiveis = ", ".join(sorted(item["nome"] for item in bairros.values()))
    detail = (
        "Bairro nao encontrado no fallback local. Configure GOOGLE_MAPS_API_KEY "
        "para consultar qualquer bairro de Curitiba. "
        f"Bairros locais disponiveis: {bairros_disponiveis}"
    )
    if google_error:
        detail += f". Erro do Google Maps: {google_error}"
    raise HTTPException(status_code=422, detail=detail)


def rank_points(
    origin: dict[str, Any],
    points: list[dict[str, Any]],
    mode: str,
    google_client: GoogleMapsClient,
) -> tuple[list[dict[str, Any]], str, str | None]:
    google_error: str | None = None
    matrix: list[dict[str, Any] | None] | None = None

    if google_client.enabled:
        try:
            matrix = google_client.distance_matrix(
                (origin["latitude"], origin["longitude"]), points, mode
            )
        except (GoogleMapsError, requests.RequestException, KeyError) as exc:
            google_error = str(exc)

    ranked: list[dict[str, Any]] = []
    used_google = bool(matrix)

    for index, point in enumerate(points):
        point_result = dict(point)
        point_result["maps_url"] = maps_search_url(point["latitude"], point["longitude"])
        point_result["directions_url"] = maps_directions_url(origin, point, mode)

        distance_data = matrix[index] if matrix else None
        if distance_data:
            point_result.update(distance_data)
        else:
            meters = haversine_meters(
                origin["latitude"],
                origin["longitude"],
                point["latitude"],
                point["longitude"],
            )
            point_result["distancia_metros"] = meters
            point_result["distancia_texto"] = format_distance(meters)
            point_result["duracao_texto"] = None
            used_google = False

        ranked.append(point_result)

    criterio = "google_distance_matrix" if used_google else "distancia_linha_reta"
    return sorted(ranked, key=lambda item: item["distancia_metros"]), criterio, google_error


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "nome": "Recicla Curitiba API",
        "descricao": "Informe um bairro e receba os pontos de coleta mais proximos.",
        "documentacao": "/docs",
        "exemplo": "/pontos-coleta?bairro=Centro&tipo=eletronico&limite=5",
        "mapa": "/mapa?bairro=Centro&tipo=reciclavel",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/pontos")
def listar_pontos(
    tipo: str = Query("todos", description="todos, reciclavel ou eletronico")
) -> dict[str, Any]:
    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(
            status_code=422,
            detail=f"tipo invalido. Use um destes valores: {sorted(TIPOS_VALIDOS)}",
        )

    pontos = filter_by_tipo(load_ecopontos(), tipo)
    return {"total": len(pontos), "items": pontos}


@app.get("/bairros")
def listar_bairros() -> dict[str, Any]:
    bairros = sorted(item["nome"] for item in load_bairros_fallback().values())
    return {
        "total": len(bairros),
        "observacao": (
            "Sem GOOGLE_MAPS_API_KEY, apenas estes bairros usam coordenadas locais. "
            "Com a chave configurada, qualquer bairro de Curitiba pode ser geocodificado."
        ),
        "items": bairros,
    }


@app.get("/pontos-coleta")
def pontos_coleta(
    bairro: str = Query(..., min_length=2, description="Bairro de Curitiba"),
    tipo: str = Query("todos", description="todos, reciclavel ou eletronico"),
    limite: int = Query(5, ge=1, le=13, description="Quantidade maxima de pontos"),
    modo: str = Query("driving", description="driving, walking, bicycling ou transit"),
) -> dict[str, Any]:
    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(
            status_code=422,
            detail=f"tipo invalido. Use um destes valores: {sorted(TIPOS_VALIDOS)}",
        )
    if modo not in MODOS_VALIDOS:
        raise HTTPException(
            status_code=422,
            detail=f"modo invalido. Use um destes valores: {sorted(MODOS_VALIDOS)}",
        )

    google_client = GoogleMapsClient()
    origin, geocode_error = resolve_origin(bairro, google_client)
    points = filter_by_tipo(load_ecopontos(), tipo)
    ranked, criterio, distance_error = rank_points(origin, points, modo, google_client)

    warnings = []
    if geocode_error:
        warnings.append(f"Geocoding API indisponivel; fallback local usado: {geocode_error}")
    if distance_error:
        warnings.append(
            f"Distance Matrix API indisponivel; distancia em linha reta usada: {distance_error}"
        )
    if criterio == "distancia_linha_reta":
        warnings.append("Distancia calculada em linha reta; nao representa rota viaria.")

    return {
        "bairro_consultado": bairro,
        "tipo_residuo": tipo,
        "modo": modo,
        "criterio_distancia": criterio,
        "origem": origin,
        "total_encontrado": min(limite, len(ranked)),
        "avisos": warnings,
        "pontos": ranked[:limite],
    }


@app.get("/mapa", response_class=HTMLResponse)
def mapa(
    bairro: str = Query("Centro", min_length=2),
    tipo: str = Query("todos"),
    limite: int = Query(5, ge=1, le=13),
    modo: str = Query("driving"),
) -> HTMLResponse:
    browser_key = os.getenv("GOOGLE_MAPS_BROWSER_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    if not browser_key:
        return HTMLResponse(
            """
            <html lang="pt-BR">
              <body style="font-family: Arial, sans-serif; margin: 32px">
                <h1>Google Maps nao configurado</h1>
                <p>Defina GOOGLE_MAPS_BROWSER_KEY para visualizar o mapa interativo.</p>
                <p>A consulta JSON continua disponivel em <a href="/docs">/docs</a>.</p>
              </body>
            </html>
            """,
            status_code=200,
        )

    api_url = (
        f"/pontos-coleta?bairro={bairro}&tipo={tipo}&limite={limite}&modo={modo}"
    )
    html = f"""
    <!doctype html>
    <html lang="pt-BR">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Mapa Recicla Curitiba</title>
        <style>
          html, body {{ height: 100%; margin: 0; font-family: Arial, sans-serif; }}
          #app {{ display: grid; grid-template-columns: minmax(280px, 360px) 1fr; height: 100%; }}
          #panel {{ overflow: auto; padding: 16px; border-right: 1px solid #ddd; }}
          #map {{ height: 100%; min-height: 420px; }}
          .point {{ padding: 12px 0; border-bottom: 1px solid #eee; }}
          .point a {{ color: #0b57d0; }}
          .badge {{ display: inline-block; padding: 2px 7px; border-radius: 999px; background: #e8f0fe; margin-top: 6px; }}
          @media (max-width: 720px) {{ #app {{ grid-template-columns: 1fr; grid-template-rows: 45% 55%; }} #panel {{ border-right: 0; border-bottom: 1px solid #ddd; }} }}
        </style>
        <script>
          const API_URL = {api_url!r};

          async function initMap() {{
            const response = await fetch(API_URL);
            const data = await response.json();
            if (!response.ok) {{
              document.getElementById("panel").innerHTML = "<h1>Erro</h1><p>" + JSON.stringify(data.detail || data) + "</p>";
              return;
            }}

            const {{ Map }} = await google.maps.importLibrary("maps");
            const {{ AdvancedMarkerElement, PinElement }} = await google.maps.importLibrary("marker");

            const center = {{ lat: data.origem.latitude, lng: data.origem.longitude }};
            const map = new Map(document.getElementById("map"), {{
              zoom: 12,
              center,
              mapId: "DEMO_MAP_ID"
            }});

            new AdvancedMarkerElement({{
              map,
              position: center,
              title: "Origem: " + data.bairro_consultado,
              content: new PinElement({{ background: "#185abc", glyphColor: "#fff", glyph: "B" }}).element
            }});

            const bounds = new google.maps.LatLngBounds();
            bounds.extend(center);

            const list = document.getElementById("results");
            list.innerHTML = "";
            data.pontos.forEach((point, index) => {{
              const position = {{ lat: point.latitude, lng: point.longitude }};
              bounds.extend(position);
              new AdvancedMarkerElement({{
                map,
                position,
                title: point.nome,
                content: new PinElement({{ background: "#188038", glyphColor: "#fff", glyph: String(index + 1) }}).element
              }});

              const item = document.createElement("div");
              item.className = "point";
              item.innerHTML = `
                <strong>${{index + 1}}. ${{point.nome}}</strong><br>
                ${{point.endereco}}<br>
                <span class="badge">${{point.distancia_texto}}</span>
                ${{point.duracao_texto ? `<span class="badge">${{point.duracao_texto}}</span>` : ""}}<br>
                <a href="${{point.directions_url}}" target="_blank" rel="noopener">Abrir rota</a>
              `;
              list.appendChild(item);
            }});

            map.fitBounds(bounds);
            document.getElementById("summary").textContent =
              `${{data.total_encontrado}} pontos encontrados para ${{data.bairro_consultado}}`;
          }}
        </script>
        <script async src="https://maps.googleapis.com/maps/api/js?key={browser_key}&callback=initMap&v=weekly&libraries=marker"></script>
      </head>
      <body>
        <main id="app">
          <aside id="panel">
            <h1>Recicla Curitiba</h1>
            <p id="summary">Carregando pontos...</p>
            <div id="results"></div>
          </aside>
          <section id="map"></section>
        </main>
      </body>
    </html>
    """
    return HTMLResponse(html)
