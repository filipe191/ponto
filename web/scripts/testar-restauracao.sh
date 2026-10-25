#!/usr/bin/env bash
# Teste de restauração: prova que um backup cifrado volta de verdade, sem tocar no banco do ponto.
#
# Uso:  scripts/testar-restauracao.sh <chave-privada.asc> [backup.dump.gpg]
#       (sem o backup, usa o diário mais recente de backups/)
#
# Rode uma vez por mês, com a chave privada trazida de fora do servidor (ex.: do Vaultwarden) e apagada
# depois (shred -u). O script:
#   1. importa a chave num chaveiro temporário e decifra o backup na memória (/dev/shm);
#   2. restaura num Postgres descartável, sem rede, que é apagado no fim;
#   3. compara a contagem das tabelas principais com o banco atual (o atual pode ter mais linhas:
#      o que entrou depois do backup) e mostra a versão do banco do backup.
# O resultado vai para backups/restauracao.log; uma falha manda e-mail a ALERTA_EMAIL (scripts/alertar.sh).
set -Eeuo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
CHAVE="${1:?Uso: scripts/testar-restauracao.sh <chave-privada.asc> [backup.dump.gpg]}"
BACKUP="${2:-$(ls -1t "$RAIZ"/backups/ponto-*.dump.gpg 2>/dev/null | head -1)}"
LOG="$RAIZ/backups/restauracao.log"
PG_CONTAINER="${BACKUP_PG_CONTAINER:-postgres_db}"
TESTE="ponto-restauracao-$$"
TABELAS=(companies employees employee_schedules punches punch_changes absences month_closures company_rules
         admin_account audit_log)

ler_env() { grep -E "^$1=" "$RAIZ/.env" 2>/dev/null | tail -1 | cut -d= -f2- || true; }
DB_USUARIO="$(ler_env PGUSER)"
: "${DB_USUARIO:?PGUSER ausente no .env}"

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
falhou() {
    log "FALHOU o teste de restauração de $(basename "${BACKUP:-?}") na linha $1 ($2)"
    "$RAIZ/scripts/alertar.sh" "Ponto: o teste de restauração do backup falhou" \
        "O backup $(basename "${BACKUP:-?}") não pôde ser restaurado (linha $1 do testar-restauracao.sh: $2). Veja $LOG."
}
trap 'falhou $LINENO "$BASH_COMMAND"' ERR

[[ -f "$CHAVE" ]] || { echo "Chave privada não encontrada: $CHAVE" >&2; exit 1; }
[[ -n "$BACKUP" && -f "$BACKUP" ]] || { echo "Nenhum backup encontrado em $RAIZ/backups" >&2; exit 1; }

umask 077
GNUPGHOME="$(mktemp -d)"
export GNUPGHOME
TMP="$(mktemp -p /dev/shm ponto-restauracao.XXXXXX)"
limpar() {
    shred -u "$TMP" 2>/dev/null || rm -f "$TMP"
    rm -rf "$GNUPGHOME"
    docker rm -f "$TESTE" >/dev/null 2>&1 || true
}
trap limpar EXIT

log "Testando $(basename "$BACKUP")"
gpg --batch --quiet --import "$CHAVE"
gpg --batch --quiet --decrypt --output "$TMP" --yes "$BACKUP"

# Postgres descartável e sem rede: nada do teste sai do servidor nem encosta no banco do ponto
docker run -d --name "$TESTE" --network none -e POSTGRES_USER=teste -e POSTGRES_PASSWORD=teste \
    -e POSTGRES_DB=restaurado postgres:18 >/dev/null
for _ in $(seq 60); do
    docker exec "$TESTE" pg_isready -U teste -d restaurado -q 2>/dev/null && break
    sleep 1
done
docker exec "$TESTE" pg_isready -U teste -d restaurado -q
sleep 2 # o primeiro "pronto" é o do initdb; espera a subida definitiva
docker exec -i "$TESTE" pg_restore -U teste -d restaurado --no-owner --no-acl --exit-on-error < "$TMP"

contar() { # contar <container> <usuário> <banco> <tabela>
    docker exec "$1" psql -U "$2" -d "$3" -tAc "SELECT count(*) FROM $4"
}
versao="$(docker exec "$TESTE" psql -U teste -d restaurado -tAc 'SELECT version_num FROM alembic_version')"
atual="$(docker exec "$PG_CONTAINER" psql -U "$DB_USUARIO" -d ponto -tAc 'SELECT version_num FROM alembic_version')"
log "Versão do banco no backup: $versao (atual: $atual)"
for tabela in "${TABELAS[@]}"; do
    if ! docker exec "$TESTE" psql -U teste -d restaurado -tAc "SELECT to_regclass('$tabela')" | grep -q .; then
        log "  $tabela: não existe no backup (backup de uma versão anterior)"
        continue
    fi
    log "  $tabela: $(contar "$TESTE" teste restaurado "$tabela") no backup, $(contar "$PG_CONTAINER" "$DB_USUARIO" ponto "$tabela") hoje"
done
log "OK: o backup $(basename "$BACKUP") foi restaurado num banco descartável"
