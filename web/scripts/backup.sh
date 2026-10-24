#!/usr/bin/env bash
# Backup do banco do ponto (pg_dump), CRIPTOGRAFADO: diários dos últimos N dias e um por mês
# guardado por 5 anos (registros de ponto devem ser guardados por 5 anos).
#
# Uso:  scripts/backup.sh
# Cron: 15 3 * * * /home/filipe/ponto/web/scripts/backup.sh >> /home/filipe/ponto/web/backups/backup.log 2>&1
#
# Criptografia: cada dump é cifrado com a chave pública de backups/chave-publica.asc (criada por
# scripts/backup-chave.sh). Só a chave privada, guardada FORA do servidor, decifra. O dump em texto
# aberto só existe na memória (/dev/shm) durante a conferência e é apagado em seguida.
#
# Variáveis opcionais (ambiente ou .env):
#   BACKUP_PG_CONTAINER  container do Postgres          (padrão: postgres_db)
#   BACKUP_MANTER        quantos backups diários manter (padrão: 14)
#   BACKUP_MESES         quantos backups mensais manter (padrão: 60)
#   BACKUP_REMOTO        destino rsync da cópia fora do servidor, ex.: "usuario@maquina:/backups/ponto/"
#                        (vazio = sem cópia remota). Os arquivos já vão cifrados.
# O usuário do banco vem do .env (PGUSER). A PIN_KEY NÃO vai no backup: guarde-a à parte
# (gerenciador de senhas); sem ela os PINs do backup restaurado não funcionam.
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="$RAIZ/backups"
PUBLICA="$DESTINO/chave-publica.asc"
DB_NOME="ponto"
DATA="$(date +%Y%m%d-%H%M%S)"
MES="$(date +%Y%m)"

# Lê só as variáveis necessárias, sem executar o .env (que tem segredos).
ler_env() { grep -E "^$1=" "$RAIZ/.env" 2>/dev/null | tail -1 | cut -d= -f2- || true; }
DB_USUARIO="$(ler_env PGUSER)"
: "${DB_USUARIO:?PGUSER ausente no .env}"
PG_CONTAINER="${BACKUP_PG_CONTAINER:-postgres_db}"
MANTER="${BACKUP_MANTER:-14}"
MESES="${BACKUP_MESES:-60}"
REMOTO="${BACKUP_REMOTO:-$(ler_env BACKUP_REMOTO)}"

log() { echo "[$(date '+%F %T')] $*"; }

mkdir -p "$DESTINO"
chmod 700 "$DESTINO" # contém dados pessoais
umask 077

if [[ ! -f "$PUBLICA" ]]; then
    log "ERRO: falta a chave $PUBLICA. Crie com: scripts/backup-chave.sh" >&2
    exit 1
fi

# Chaveiro temporário só para cifrar (não mexe no ~/.gnupg do usuário)
GNUPGHOME="$(mktemp -d)"
export GNUPGHOME
TMP="$(mktemp -p /dev/shm ponto-backup.XXXXXX)"
trap 'shred -u "$TMP" 2>/dev/null || rm -f "$TMP"; rm -rf "$GNUPGHOME"' EXIT

cifrar() { # cifrar <origem> <destino>
    gpg --batch --yes --quiet --trust-model always --recipient-file "$PUBLICA" --encrypt --output "$2" "$1"
}

# Backups antigos em texto aberto (antes da criptografia): cifra e destrói o original
for antigo in "$DESTINO"/ponto-*.dump "$DESTINO"/mensal-ponto-*.dump; do
    [[ -f "$antigo" ]] || continue
    cifrar "$antigo" "$antigo.gpg.parcial" && mv "$antigo.gpg.parcial" "$antigo.gpg"
    shred -u "$antigo" 2>/dev/null || rm -f "$antigo"
    log "Backup antigo cifrado: $(basename "$antigo").gpg"
done

log "Iniciando backup de '$DB_NOME'"

# O dump em texto aberto fica só na memória; o arquivo cifrado é gravado com nome temporário
# e só renomeado no fim: um backup interrompido nunca fica com cara de backup válido.
docker exec "$PG_CONTAINER" pg_dump -U "$DB_USUARIO" -d "$DB_NOME" -Fc > "$TMP"
docker exec -i "$PG_CONTAINER" pg_restore --list < "$TMP" > /dev/null # confere se o dump é legível
ARQ="$DESTINO/ponto-$DATA.dump.gpg"
cifrar "$TMP" "$ARQ.parcial"
mv "$ARQ.parcial" "$ARQ"

# O primeiro backup de cada mês vira o mensal
if [[ ! -f "$DESTINO/mensal-ponto-$MES.dump.gpg" ]]; then
    cp "$ARQ" "$DESTINO/mensal-ponto-$MES.dump.gpg"
    log "Cópia mensal: mensal-ponto-$MES.dump.gpg"
fi

# Rotação: mantém os N diários e os M mensais mais recentes
ls -1t "$DESTINO"/ponto-*.dump.gpg 2>/dev/null | tail -n +"$((MANTER + 1))" | xargs -r rm --
ls -1t "$DESTINO"/mensal-ponto-*.dump.gpg 2>/dev/null | tail -n +"$((MESES + 1))" | xargs -r rm --

log "OK: $(du -h "$ARQ" | cut -f1) cifrado ($(ls -1 "$DESTINO"/ponto-*.dump.gpg | wc -l) diários, $(ls -1 "$DESTINO"/mensal-ponto-*.dump.gpg | wc -l) mensais)"

# Cópia fora do servidor (opcional). Falhar aqui não invalida o backup local.
if [[ -n "$REMOTO" ]]; then
    if rsync -a --timeout=60 "$DESTINO"/*.dump.gpg "$PUBLICA" "$REMOTO"; then
        log "Cópia remota OK: $REMOTO"
    else
        log "AVISO: falhou a cópia remota para $REMOTO (tenta de novo no próximo backup)"
    fi
else
    log "AVISO: sem cópia fora do servidor (defina BACKUP_REMOTO no .env)"
fi
