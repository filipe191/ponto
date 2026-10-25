#!/usr/bin/env bash
# Testes das páginas num navegador de verdade, contra uma pilha descartável (Postgres, backend e nginx
# construídos do código atual, numa rede só deles, com certificado temporário). Nada encosta no banco
# nem nos containers de produção.
#
# Uso: e2e/rodar.sh        (o deploy.sh e o GitHub Actions rodam este mesmo script)
# Capturas de tela de cada aba (computador e celular, claro e escuro) ficam em e2e/resultados/.
set -euo pipefail

E2E="$(cd "$(dirname "$0")" && pwd)"
WEB="$(dirname "$E2E")"
ID="ponto-e2e-$$"
CERTS="$(mktemp -d)"

limpar() {
    docker rm -f "$ID-db" "$ID-backend" "$ID-frontend" >/dev/null 2>&1 || true
    docker network rm "$ID" >/dev/null 2>&1 || true
    rm -rf "$CERTS"
}
trap limpar EXIT

rm -rf "$E2E/resultados"
mkdir -p "$E2E/resultados"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=frontend \
    -keyout "$CERTS/server.key" -out "$CERTS/server.crt" 2>/dev/null
cp "$CERTS/server.crt" "$CERTS/ca.crt"
chmod 644 "$CERTS"/*

docker build -q -t ponto-backend-e2e "$WEB/backend" >/dev/null
docker build -q -t ponto-frontend-e2e "$WEB/frontend" >/dev/null
docker build -q -t ponto-e2e "$E2E" >/dev/null

docker network create "$ID" >/dev/null
docker run -d --name "$ID-db" --network "$ID" \
    -e POSTGRES_USER=ponto -e POSTGRES_PASSWORD=teste -e POSTGRES_DB=ponto_e2e postgres:18 >/dev/null
until docker exec "$ID-db" pg_isready -q -h 127.0.0.1 -U ponto -d ponto_e2e 2>/dev/null; do sleep 1; done
docker run -d --name "$ID-backend" --network "$ID" --network-alias backend \
    -e PGHOST="$ID-db" -e PGUSER=ponto -e PGPASSWORD=teste -e PGDATABASE=ponto_e2e \
    -e PIN_KEY=e2e -e SECRET_KEY=e2e -e COOKIE_SECURE=true -e ADMIN_2FA_REQUIRED=false \
    -e ADMIN_USER=admin -e ADMIN_PASSWORD=Inicial-Bem-Forte-E2E-2026 ponto-backend-e2e >/dev/null
docker run -d --name "$ID-frontend" --network "$ID" --network-alias frontend -e HTTPS_PORT=443 \
    -v "$CERTS:/etc/nginx/certs:ro" ponto-frontend-e2e >/dev/null

# Com o usuário de quem roda: as capturas e os relatórios ficam com o dono certo
docker run --rm --network "$ID" --ipc=host -u "$(id -u):$(id -g)" -e HOME=/tmp -e NPM_CONFIG_UPDATE_NOTIFIER=false \
    -v "$E2E/resultados:/e2e/resultados" ponto-e2e
