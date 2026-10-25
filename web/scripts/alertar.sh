#!/usr/bin/env bash
# Manda um alerta por e-mail a quem cuida do servidor (ALERTA_EMAIL no .env), pelo SMTP do .env.
#
# Uso: scripts/alertar.sh "Assunto" "Texto"     (sem o texto, lê da entrada padrão)
#
# Roda a imagem do backend à parte (python -m app.alerta), então funciona mesmo com o backend fora do
# ar. Sem SMTP_HOST ou ALERTA_EMAIL, só registra que não enviou. Nunca faz falhar quem chamou.
set -uo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
ASSUNTO="${1:-Ponto: alerta}"
if [[ $# -ge 2 ]]; then TEXTO="$2"; else TEXTO="$(cat)"; fi

printf '%s\n\nServidor: %s · %s\n' "$TEXTO" "$(hostname)" "$(date '+%d/%m/%Y %H:%M')" \
    | timeout 90 docker run --rm -i --env-file "$RAIZ/.env" ponto-backend python -m app.alerta "$ASSUNTO" \
    || echo "[$(date '+%F %T')] AVISO: não foi possível mandar o alerta \"$ASSUNTO\""
exit 0
