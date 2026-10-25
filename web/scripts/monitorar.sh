#!/usr/bin/env bash
# Confere se o ponto responde (/api/health, pelo nginx) e avisa por e-mail quando cai e quando volta.
#
# Cron: */5 * * * * /home/filipe/ponto/web/scripts/monitorar.sh >> /home/filipe/ponto/web/backups/monitor.log 2>&1
#
# Só avisa depois de 2 falhas seguidas (10 minutos), para um deploy ou reinício rápido não virar alerta,
# e uma vez só por queda. O estado fica em backups/.monitor ("ok", número de falhas, ou "fora").
# Variável opcional: MONITOR_URL (padrão: https://127.0.0.1:<HTTPS_PORT>/api/health).
set -uo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
ESTADO="$RAIZ/backups/.monitor"
PORTA="$(grep -E '^HTTPS_PORT=' "$RAIZ/.env" 2>/dev/null | tail -1 | cut -d= -f2-)"
URL="${MONITOR_URL:-https://127.0.0.1:${PORTA:-9443}/api/health}"
FALHAS_PARA_AVISAR=2

log() { echo "[$(date '+%F %T')] $*"; }
alertar() { "$RAIZ/scripts/alertar.sh" "$@"; }
containers() { docker ps -a --filter name=ponto- --format '{{.Names}}: {{.Status}}' 2>&1; }

mkdir -p "$RAIZ/backups"
anterior="$(cat "$ESTADO" 2>/dev/null || echo ok)"
codigo="$(curl -sk --max-time 15 -o /dev/null -w '%{http_code}' "$URL" 2>/dev/null)"

if [[ "$codigo" == "200" ]]; then
    if [[ "$anterior" == "fora" ]]; then
        log "O sistema voltou a responder"
        alertar "Ponto: o sistema voltou" "O ponto voltou a responder em $URL."
    fi
    echo ok > "$ESTADO"
    exit 0
fi

case "$anterior" in
    fora) exit 0 ;;  # já avisou desta queda
    ok) falhas=1 ;;
    *) falhas=$((anterior + 1)) ;;
esac
log "Sem resposta de $URL (código ${codigo:-nenhum}), falha $falhas seguida"
if ((falhas >= FALHAS_PARA_AVISAR)); then
    echo fora > "$ESTADO"
    alertar "Ponto: o sistema está fora do ar" "O ponto não responde em $URL há $falhas verificações seguidas (de 5 em 5 minutos).
Os relógios guardam as batidas sem conexão por algumas horas, mas confira logo.

Containers:
$(containers)"
else
    echo "$falhas" > "$ESTADO"
fi
