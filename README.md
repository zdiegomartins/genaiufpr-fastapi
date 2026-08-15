# Recicla Curitiba API

API em FastAPI para consultar os Ecopontos de Curitiba mais proximos a partir de um bairro informado pelo usuario.

## O que a API faz

- Recebe um bairro de Curitiba.
- Retorna os pontos de coleta mais proximos para residuos reciclaveis e/ou eletroeletronicos.
- Usa Google Maps quando `GOOGLE_MAPS_API_KEY` estiver configurada.
- Funciona sem chave usando coordenadas locais de apoio e distancia em linha reta.
- Serve uma pagina de mapa em `/mapa`.

## Como executar localmente

```bash
conda create --name recicla_api python=3.10
conda activate recicla_api
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Acesse:

- API: http://127.0.0.1:8000
- Documentacao Swagger: http://127.0.0.1:8000/docs
- Mapa: http://127.0.0.1:8000/mapa?bairro=Centro&tipo=reciclavel

## Exemplo de consulta

```bash
curl "http://127.0.0.1:8000/pontos-coleta?bairro=Centro&tipo=eletronico&limite=5"
```

## Google Maps

Crie um arquivo `.env` ou defina variaveis de ambiente:

```bash
GOOGLE_MAPS_API_KEY=sua-chave-de-servidor
GOOGLE_MAPS_BROWSER_KEY=sua-chave-de-navegador
```

Ative no Google Cloud:

- Geocoding API
- Distance Matrix API ou, em producao, Routes API / Compute Route Matrix
- Maps JavaScript API

## Docker

```bash
docker build -t recicla-curitiba-api .
docker run -p 8000:8000 recicla-curitiba-api
```

O passo a passo completo esta em [MATERIAL_PASSO_A_PASSO.md](MATERIAL_PASSO_A_PASSO.md).
