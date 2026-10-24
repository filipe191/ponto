#!/usr/bin/env bash
# Cria o par de chaves que protege os backups (rodar uma única vez).
#
# - A chave PÚBLICA fica no servidor (backups/chave-publica.asc) e só serve para cifrar.
# - A chave PRIVADA é a única que decifra. Ela é gravada em ~/ponto-backup-chave-privada.asc para
#   você guardar fora do servidor (ex.: Vaultwarden, como anexo) e depois apagar daqui com:
#       shred -u ~/ponto-backup-chave-privada.asc
#   Sem ela, nenhum backup pode ser restaurado. Com ela fora do servidor, um backup copiado
#   do servidor não pode ser lido.
#
# Uso:  scripts/backup-chave.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
PUBLICA="$RAIZ/backups/chave-publica.asc"
PRIVADA="$HOME/ponto-backup-chave-privada.asc"

if [[ -f "$PUBLICA" ]]; then
    echo "Já existe uma chave em $PUBLICA. Para trocar, apague-a antes (os backups antigos" >&2
    echo "continuam precisando da chave privada antiga)." >&2
    exit 1
fi

mkdir -p "$RAIZ/backups"
chmod 700 "$RAIZ/backups"
umask 077

# Chaveiro temporário: a chave privada nunca fica no chaveiro do usuário
GNUPGHOME="$(mktemp -d)"
export GNUPGHOME
trap 'gpgconf --kill gpg-agent 2>/dev/null || true; rm -rf "$GNUPGHOME"' EXIT

ID="Backup do ponto ($(hostname)) <backup-ponto@$(hostname)>"
gpg --batch --quiet --passphrase '' --quick-generate-key "$ID" ed25519 sign never
FPR="$(gpg --batch --with-colons --list-keys "$ID" 2>/dev/null | awk -F: '/^fpr/{print $10; exit}')"
gpg --batch --quiet --passphrase '' --quick-add-key "$FPR" cv25519 encr never

gpg --batch --armor --export "$FPR" > "$PUBLICA"
gpg --batch --armor --pinentry-mode loopback --passphrase '' --export-secret-keys "$FPR" > "$PRIVADA"
chmod 644 "$PUBLICA"
chmod 600 "$PRIVADA"

echo "Chave pública (fica no servidor): $PUBLICA"
echo "Chave PRIVADA: $PRIVADA"
echo
echo "Agora:"
echo "  1. Guarde $PRIVADA fora do servidor (ex.: anexo no Vaultwarden)."
echo "  2. Apague a cópia daqui:  shred -u $PRIVADA"
echo "Impressão digital da chave: $FPR"
