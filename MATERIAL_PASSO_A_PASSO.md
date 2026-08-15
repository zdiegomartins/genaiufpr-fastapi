# Material passo a passo - API Recicla Curitiba

Este material segue a estrutura do PDF da aula: criar repositorio, preparar ambiente, construir uma API simples, versionar, criar Dockerfile e deixar o projeto pronto para deploy.

## 1. Objetivo do projeto

Construir uma API que recebe o nome de um bairro de Curitiba e retorna os Ecopontos mais proximos para descarte de residuos reciclaveis e eletroeletronicos.

Exemplo de uso:

```text
Entrada: Centro
Saida: lista dos Ecopontos mais proximos, com endereco, residuos aceitos, distancia estimada e link do Google Maps.
```

## 2. Fontes de dados recomendadas

Use sempre fontes oficiais primeiro:

- Portal de Dados Abertos de Curitiba: conjunto "Unidades de Atendimento de Curitiba - Ativas". Ele descreve unidades publicas, enderecos e metadados, com atualizacao mensal.
- IPPUC / SEUC: pagina de equipamentos urbanos filtrada por "Meio Ambiente" e "Deposito de Residuos Solidos", util para validar Ecopontos mistos.
- Portal Locais da Prefeitura de Curitiba: paginas individuais dos Ecopontos, com endereco, contato, horario e link de mapa.
- Site Coleta Lixo Curitiba: pagina de lixo eletroeletronico, util para validar quais canais recebem eletronicos.
- Google Maps Platform: Geocoding API para transformar bairro em coordenadas, Distance Matrix API para distancia de rota e Maps JavaScript API para visualizacao interativa.

## 3. Tratamento dos dados

Fluxo sugerido:

1. Baixar o CSV mais recente de `https://dadosabertos.c3sl.ufpr.br/curitiba/UnidadesAtendimentoCuritiba/`.
2. Ler o arquivo com separador `;` e encoding `cp1252`.
3. Filtrar registros com `DS_TEMA = MEIO AMBIENTE` e `DS_TP_EQUIPAMENTO = Deposito de Residuos Solidos`.
4. Manter apenas subtipo com "Ecoponto".
5. Padronizar campos: nome, endereco, bairro, regional, telefone, email e site.
6. Enriquecer coordenadas por Google Geocoding ou validar pelos links do Portal Locais.
7. Classificar os residuos aceitos:
   - Ecopontos mistos: reciclavel, eletronico, oleo de cozinha, madeira, moveis, residuos vegetais e construcao civil.
   - Ecoponto Parque Gomm: reciclaveis e oleo/gordura pos-consumo.
8. Salvar o resultado em `data/ecopontos_curitiba.json`.

O script `scripts/atualizar_dados.py` automatiza os passos de download e limpeza. Se `GOOGLE_MAPS_API_KEY` estiver configurada, ele tambem pode geocodificar enderecos.

## 4. Criar o ambiente

```bash
conda create --name recicla_api python=3.10
conda activate recicla_api
pip install -r requirements.txt
```

Opcionalmente, exporte o ambiente para entregar junto ao projeto:

```bash
conda env export --from-history > environment.yml
```

## 5. Executar a API

```bash
uvicorn app.main:app --reload
```

Endpoints principais:

- `GET /health`: verifica se a API esta ativa.
- `GET /bairros`: lista bairros conhecidos pelo fallback local.
- `GET /pontos`: lista todos os pontos de coleta cadastrados.
- `GET /pontos-coleta?bairro=Centro&tipo=eletronico&limite=5`: retorna os pontos mais proximos.
- `GET /mapa?bairro=Centro&tipo=reciclavel`: abre visualizacao interativa com Google Maps.

## 6. Integracao com Google Maps em Python

A API usa duas chamadas quando ha chave configurada:

1. Geocoding API:
   - Entrada: `"Centro, Curitiba, PR, Brasil"`.
   - Saida: latitude e longitude do bairro.

2. Distance Matrix API:
   - Entrada: coordenada do bairro e coordenadas dos Ecopontos.
   - Saida: distancia e tempo de deslocamento por carro, caminhada, bicicleta ou transporte publico.

Configure:

```bash
GOOGLE_MAPS_API_KEY=sua-chave-de-servidor
```

Para a pagina `/mapa`, use preferencialmente uma chave separada e restrita por HTTP referrer:

```bash
GOOGLE_MAPS_BROWSER_KEY=sua-chave-de-navegador
```

## 7. Testar rapidamente

```bash
curl "http://127.0.0.1:8000/pontos-coleta?bairro=Batel&tipo=reciclavel&limite=3"
curl "http://127.0.0.1:8000/pontos-coleta?bairro=Alto%20Boqueirao&tipo=eletronico&limite=3"
```

## 8. Docker

Crie a imagem:

```bash
docker build -t recicla-curitiba-api .
```

Execute:

```bash
docker run -p 8000:8000 recicla-curitiba-api
```

Com Google Maps:

```bash
docker run -p 8000:8000 -e GOOGLE_MAPS_API_KEY=sua-chave recicla-curitiba-api
```

## 9. Deploy em servidor

Seguindo o material da aula:

1. Fazer commit e push para o GitHub.
2. Criar uma VM simples no Oracle Cloud.
3. Instalar Docker na VM.
4. Copiar a imagem com `docker save`/`docker load` ou clonar o repositorio e fazer build no servidor.
5. Liberar a porta `8000` nas regras de rede.
6. Testar `http://IP_DA_VM:8000/docs`.
7. Apagar a VM ao final dos testes para evitar custos e riscos.
