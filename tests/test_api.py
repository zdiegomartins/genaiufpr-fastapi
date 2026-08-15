from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_pontos_coleta_returns_nearest_points_without_google_key() -> None:
    response = client.get(
        "/pontos-coleta",
        params={"bairro": "Centro", "tipo": "eletronico", "limite": 3},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["criterio_distancia"] == "distancia_linha_reta"
    assert payload["total_encontrado"] == 3
    assert all("eletronico" in item["residuos_aceitos"] for item in payload["pontos"])


def test_parque_gomm_is_not_returned_for_eletronico() -> None:
    response = client.get(
        "/pontos-coleta",
        params={"bairro": "Batel", "tipo": "eletronico", "limite": 13},
    )
    assert response.status_code == 200
    names = [item["nome"] for item in response.json()["pontos"]]
    assert "Ecoponto Parque Gomm" not in names
