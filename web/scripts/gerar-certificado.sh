#!/usr/bin/env bash
# Certificado HTTPS para uso na rede local: uma CA própria (instalada uma vez em cada aparelho)
# e o certificado do servidor assinado por ela.
#
# Uso:  scripts/gerar-certificado.sh            (cria o que estiver faltando)
#       scripts/gerar-certificado.sh --renovar  (refaz o certificado do servidor, ex.: mudou o IP)
#
# Variáveis opcionais:
#   CERT_HOSTS  nomes/IPs extras separados por espaço (ex.: "ponto.local 10.0.0.5")
#
# Depois de gerar, reinicie o frontend:  docker compose restart frontend
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$RAIZ/certs"
mkdir -p "$DIR"
chmod 700 "$DIR"
umask 077

# Endereços que os aparelhos usam para chegar aqui: IP da rede local, Tailscale (100.64.0.0/10) e nomes
lan_ip="$(ip -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([0-9.]*\).*/\1/p')"
tailscale_ips="$(hostname -I | tr ' ' '\n' | grep -E '^100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.' || true)"
nomes="localhost $(hostname) $(hostname).local ${CERT_HOSTS:-}"
ips="127.0.0.1 $lan_ip $tailscale_ips"

san=""
for n in $nomes; do [[ $n =~ ^[0-9.]+$ ]] && ips="$ips $n" || san="$san,DNS:$n"; done
for i in $ips; do san="$san,IP:$i"; done
san="${san#,}"

if [[ ! -f "$DIR/ca.key" ]]; then
    echo "Criando a CA local (válida por 10 anos)..."
    openssl req -x509 -new -nodes -newkey rsa:3072 -sha256 -days 3650 \
        -keyout "$DIR/ca.key" -out "$DIR/ca.crt" \
        -subj "/CN=Ponto - CA local ($(hostname))" \
        -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
        -addext "keyUsage=critical,keyCertSign,cRLSign"
fi

if [[ ! -f "$DIR/server.crt" || "${1:-}" == "--renovar" ]]; then
    echo "Criando o certificado do servidor para: $san"
    openssl req -new -nodes -newkey rsa:2048 -sha256 \
        -keyout "$DIR/server.key" -out "$DIR/server.csr" -subj "/CN=$(hostname)"
    # 825 dias: o máximo que iPhone/iPad aceitam
    openssl x509 -req -in "$DIR/server.csr" -CA "$DIR/ca.crt" -CAkey "$DIR/ca.key" -CAcreateserial \
        -out "$DIR/server.crt" -days 825 -sha256 \
        -extfile <(printf "subjectAltName=%s\nbasicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n" "$san")
    rm -f "$DIR/server.csr"
fi

# Certificados públicos legíveis; chaves só para o dono (o nginx do container lê como root)
chmod 644 "$DIR/ca.crt" "$DIR/server.crt"
chmod 600 "$DIR/server.key"  # o nginx lê como root
chmod 755 "$DIR"
chmod 600 "$DIR/ca.key"

echo "Pronto. Certificado do servidor válido até: $(openssl x509 -enddate -noout -in "$DIR/server.crt" | cut -d= -f2)"
echo "Instale a CA em cada aparelho baixando:  http://${lan_ip:-<ip-do-servidor>}:9092/ponto-ca.crt"
