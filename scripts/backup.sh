#!/usr/bin/env bash
# Backup do banco do ponto (pg_dump): diários dos últimos N dias e um por mês guardado por 5 anos
# (registros de ponto devem ser guardados por 5 anos).
#
# Uso:  scripts/backup.sh
# Cron: 15 3 * * * /home/filipe/ponto/scripts/backup.sh >> /home/filipe/ponto/backups/backup.log 2>&1
#
# Variáveis opcionais:
#   BACKUP_PG_CONTAINER  container do Postgres          (padrão: postgres_db)
#   BACKUP_MANTER        quantos backups diários manter (padrão: 14)
#   BACKUP_MESES         quantos backups mensais manter (padrão: 60)
# O usuário do banco vem do .env (PGUSER). A PIN_KEY NÃO vai no backup: guarde-a à parte
# (gerenciador de senhas); sem ela os PINs do backup restaurado não funcionam.
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="$RAIZ/backups"
PG_CONTAINER="${BACKUP_PG_CONTAINER:-postgres_db}"
MANTER="${BACKUP_MANTER:-14}"
MESES="${BACKUP_MESES:-60}"
DB_NOME="ponto"
DATA="$(date +%Y%m%d-%H%M%S)"
MES="$(date +%Y%m)"

# Lê só a variável necessária, sem executar o .env (que tem segredos).
ler_env() { grep -E "^$1=" "$RAIZ/.env" | tail -1 | cut -d= -f2-; }
DB_USUARIO="$(ler_env PGUSER)"
: "${DB_USUARIO:?PGUSER ausente no .env}"

mkdir -p "$DESTINO"
chmod 700 "$DESTINO" # contém dados pessoais
umask 077

echo "[$(date '+%F %T')] Iniciando backup de '$DB_NOME'"

# Grava em arquivo temporário e só renomeia no fim: um backup interrompido
# nunca fica com cara de backup válido.
ARQ="$DESTINO/ponto-$DATA.dump"
docker exec "$PG_CONTAINER" pg_dump -U "$DB_USUARIO" -d "$DB_NOME" -Fc > "$ARQ.parcial"
docker exec -i "$PG_CONTAINER" pg_restore --list < "$ARQ.parcial" > /dev/null # confere se o dump é legível
mv "$ARQ.parcial" "$ARQ"

# O primeiro backup de cada mês vira o mensal
if [[ ! -f "$DESTINO/mensal-ponto-$MES.dump" ]]; then
    cp "$ARQ" "$DESTINO/mensal-ponto-$MES.dump"
    echo "[$(date '+%F %T')] Cópia mensal: mensal-ponto-$MES.dump"
fi

# Rotação: mantém os N diários e os M mensais mais recentes
ls -1t "$DESTINO"/ponto-*.dump 2>/dev/null | tail -n +"$((MANTER + 1))" | xargs -r rm --
ls -1t "$DESTINO"/mensal-ponto-*.dump 2>/dev/null | tail -n +"$((MESES + 1))" | xargs -r rm --

echo "[$(date '+%F %T')] OK: $(du -h "$ARQ" | cut -f1) ($(ls -1 "$DESTINO"/ponto-*.dump | wc -l) diários, $(ls -1 "$DESTINO"/mensal-ponto-*.dump | wc -l) mensais)"
