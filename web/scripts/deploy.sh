#!/usr/bin/env bash
# Coloca a versão atual no ar com segurança: confere a configuração, roda os testes,
# faz backup do banco (as migrações rodam na subida) e só então sobe os containers.
#
# Uso:  scripts/deploy.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"
passo() { echo; echo "==> $*"; }

passo "Conferindo o .env"
for var in PGPASSWORD SECRET_KEY PIN_KEY; do
    valor="$(grep -E "^$var=" .env | tail -1 | cut -d= -f2- || true)"
    if [[ -z "$valor" || "$valor" == "troque-aqui" ]]; then
        echo "Defina $var no .env (gere com: openssl rand -hex 32)" >&2
        exit 1
    fi
done

passo "Certificado HTTPS"
[[ -f certs/server.crt ]] || scripts/gerar-certificado.sh
# Uma CA sem restrição de nomes serviria para qualquer site nos aparelhos que a instalaram
if ! openssl x509 -noout -ext nameConstraints -in certs/ca.crt 2>/dev/null | grep -qi permitted; then
    echo "A CA não tem restrição de nomes. Troque-a com: scripts/gerar-certificado.sh --nova-ca" >&2
    exit 1
fi
openssl x509 -checkend $((30 * 86400)) -noout -in certs/server.crt >/dev/null \
    || echo "AVISO: o certificado vence em menos de 30 dias. Rode: scripts/gerar-certificado.sh --renovar"

passo "Testes automatizados"
docker build -q -t ponto-backend-testes ./backend >/dev/null
docker run --rm -u root -e PYTHONDONTWRITEBYTECODE=1 \
    -v "$RAIZ/backend/tests:/app/tests:ro" -v "$RAIZ/backend/requirements-dev.txt:/app/requirements-dev.txt:ro" \
    ponto-backend-testes sh -c "pip install -q --root-user-action=ignore -r requirements-dev.txt && python -m pytest -q -p no:cacheprovider tests"

passo "Vulnerabilidades conhecidas nas dependências"
# Backend: falha conhecida interrompe o deploy (atualize a versão em backend/requirements.txt).
# Em emergência (ex.: sem internet), pule com PULAR_AUDITORIA=1 scripts/deploy.sh
if [[ "${PULAR_AUDITORIA:-}" == "1" ]]; then
    echo "AVISO: auditoria de dependências pulada (PULAR_AUDITORIA=1)"
else
    docker run --rm -v "$RAIZ/backend/requirements.txt:/r/requirements.txt:ro" python:3.13-slim sh -c \
        "pip install -q --root-user-action=ignore --disable-pip-version-check pip-audit >/dev/null \
         && pip-audit -r /r/requirements.txt --progress-spinner off" \
        || { echo "Há dependências do backend com falhas conhecidas (lista acima). Deploy interrompido." >&2; exit 1; }
    # App de celular: não é publicado por este script, então só avisa (as falhas restantes
    # estão nas ferramentas de build do Expo e saem com a atualização do Expo SDK)
    if [[ -f ../app/package-lock.json ]]; then
        docker run --rm -v "$RAIZ/../app:/app:ro" -w /app node:22-alpine \
            npm audit --omit=dev --audit-level=critical >/dev/null 2>&1 \
            || echo "AVISO: o app de celular tem dependências com falha crítica. Veja: cd app && npm audit --omit=dev"
    fi
fi

passo "Backup do banco antes de atualizar"
scripts/backup.sh

passo "Subindo os containers"
docker compose up -d --build

passo "Aguardando o backend ficar saudável"
for _ in $(seq 1 60); do
    estado="$(docker inspect -f '{{.State.Health.Status}}' ponto-backend 2>/dev/null || true)"
    [[ "$estado" == "healthy" ]] && break
    sleep 2
done
if [[ "$estado" != "healthy" ]]; then
    echo "O backend não ficou saudável. Últimas linhas do log:" >&2
    docker logs --tail 40 ponto-backend >&2
    exit 1
fi
docker image rm ponto-backend-testes >/dev/null 2>&1 || true

porta="$(grep -E '^HTTPS_PORT=' .env | cut -d= -f2- || true)"
echo
echo "Pronto: https://$(ip -4 route get 1.1.1.1 | sed -n 's/.* src \([0-9.]*\).*/\1/p'):${porta:-9443}"
