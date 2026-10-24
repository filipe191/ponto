#!/usr/bin/env bash
# Certificado HTTPS para uso na rede local: uma CA própria (instalada uma vez em cada aparelho)
# e o certificado do servidor assinado por ela.
#
# Segurança da CA:
# - "name constraints": a CA só vale para a rede local, para os IPs do Tailscale e para os nomes
#   deste servidor. Mesmo que a chave vaze, não dá para se passar por outros sites (banco, e-mail...)
#   nos aparelhos que instalaram a CA.
# - A chave da CA (certs/ca.key) é cifrada com uma senha. Sem a senha, o arquivo não serve para nada.
#   Guarde a senha num gerenciador de senhas: ela é pedida para renovar o certificado do servidor.
#
# Uso:  scripts/gerar-certificado.sh            (cria o que estiver faltando)
#       scripts/gerar-certificado.sh --renovar  (refaz o certificado do servidor, ex.: mudou o IP)
#       scripts/gerar-certificado.sh --nova-ca  (troca a CA; todos os aparelhos precisam reinstalar)
#
# Variáveis opcionais:
#   CERT_HOSTS  nomes/IPs extras separados por espaço (ex.: "ponto.local 10.0.0.5")
#   CA_SENHA    senha da chave da CA (sem ela, é pedida no terminal)
#
# Depois de gerar, reinicie o frontend:  docker compose restart frontend
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$RAIZ/certs"
ACAO="${1:-}"
mkdir -p "$DIR"
chmod 755 "$DIR"
umask 077

# ---------- Endereços que os aparelhos usam para chegar aqui ----------
dev="$(ip -o -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* dev \([^ ]*\).*/\1/p')"
lan_cidr="$(ip -o -4 addr show dev "$dev" 2>/dev/null | awk '{print $4}' | head -1)"   # ex.: 192.168.0.34/24
lan_ip="${lan_cidr%/*}"
tailscale_ips="$(hostname -I | tr ' ' '\n' | grep -E '^100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.' || true)"
tailscale_dns="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null || true)"
nomes="localhost $(hostname) $(hostname).local $tailscale_dns ${CERT_HOSTS:-}"
ips="127.0.0.1 $lan_ip $tailscale_ips"

san=""
for n in $nomes; do [[ $n =~ ^[0-9.]+$ ]] && ips="$ips $n" || san="$san,DNS:$n"; done
for i in $ips; do san="$san,IP:$i"; done
san="${san#,}"

# Onde a CA pode valer: a sub-rede local inteira (o IP do servidor pode mudar no DHCP),
# os IPs exatos do Tailscale e os nomes acima
rede_local="$(python3 -c "import ipaddress,sys; n=ipaddress.ip_network(sys.argv[1], strict=False); print(f'{n.network_address}/{n.netmask}')" "$lan_cidr")"
permitidos="permitted;IP:127.0.0.1/255.255.255.255,permitted;IP:$rede_local"
for i in $tailscale_ips ${CERT_HOSTS:-}; do
    [[ $i =~ ^[0-9.]+$ ]] && permitidos="$permitidos,permitted;IP:$i/255.255.255.255"
done
for n in $nomes; do
    [[ $n =~ ^[0-9.]+$ ]] || permitidos="$permitidos,permitted;DNS:$n"
done

senha_da_ca() {
    # Pede a senha só uma vez por execução; CA_SENHA permite automatizar
    if [[ -z "${CA_SENHA:-}" ]]; then
        if [[ ! -t 0 ]]; then
            echo "A chave da CA é protegida por senha: rode no terminal ou defina CA_SENHA." >&2
            exit 1
        fi
        read -rsp "Senha da chave da CA: " CA_SENHA; echo
        if [[ "${1:-}" == "nova" ]]; then
            read -rsp "Repita a senha: " confirmacao; echo
            [[ "$CA_SENHA" == "$confirmacao" ]] || { echo "As senhas não conferem." >&2; exit 1; }
            [[ ${#CA_SENHA} -ge 12 ]] || { echo "Use pelo menos 12 caracteres." >&2; exit 1; }
        fi
    fi
    export CA_SENHA
}

tem_restricao() { openssl x509 -noout -ext nameConstraints -in "$DIR/ca.crt" 2>/dev/null | grep -qi permitted; }

# ---------- CA ----------
if [[ "$ACAO" == "--nova-ca" && -f "$DIR/ca.crt" ]]; then
    echo "Removendo a CA antiga: os aparelhos precisam remover a antiga e instalar a nova."
    [[ -f "$DIR/ca.key" ]] && shred -u "$DIR/ca.key" 2>/dev/null || rm -f "$DIR/ca.key"
    rm -f "$DIR/ca.crt" "$DIR/ca.srl" "$DIR/server.crt" "$DIR/server.key"
fi

if [[ -f "$DIR/ca.crt" ]] && ! tem_restricao; then
    echo "A CA atual não tem restrição de nomes: se a chave vazar, ela serve para qualquer site." >&2
    echo "Troque-a com: scripts/gerar-certificado.sh --nova-ca" >&2
    exit 1
fi

if [[ ! -f "$DIR/ca.crt" ]]; then
    echo "Criando a CA local (válida por 10 anos), restrita a: $permitidos"
    senha_da_ca nova
    openssl req -x509 -new -newkey rsa:3072 -sha256 -days 3650 \
        -keyout "$DIR/ca.key" -passout env:CA_SENHA -out "$DIR/ca.crt" \
        -subj "/CN=Ponto - CA local ($(hostname))" \
        -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
        -addext "keyUsage=critical,keyCertSign,cRLSign" \
        -addext "nameConstraints=critical,$permitidos"
    rm -f "$DIR/server.crt"
fi

# ---------- Certificado do servidor ----------
if [[ ! -f "$DIR/server.crt" || "$ACAO" == "--renovar" ]]; then
    echo "Criando o certificado do servidor para: $san"
    senha_da_ca
    # Gera em arquivos temporários: se algo falhar (ex.: senha errada), a chave e o certificado
    # em uso continuam intactos e o nginx não quebra
    novo="$DIR/.novo"
    trap 'rm -f "$novo".*' EXIT
    openssl req -new -nodes -newkey rsa:2048 -sha256 \
        -keyout "$novo.key" -out "$novo.csr" -subj "/CN=$(hostname)"
    # 825 dias: o máximo que iPhone/iPad aceitam
    openssl x509 -req -in "$novo.csr" -CA "$DIR/ca.crt" -CAkey "$DIR/ca.key" -passin env:CA_SENHA \
        -CAcreateserial -out "$novo.crt" -days 825 -sha256 \
        -extfile <(printf "subjectAltName=%s\nbasicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n" "$san")
    # Confere a cadeia, inclusive a restrição de nomes, antes de trocar os arquivos
    openssl verify -CAfile "$DIR/ca.crt" "$novo.crt" >/dev/null
    mv "$novo.key" "$DIR/server.key"
    mv "$novo.crt" "$DIR/server.crt"
fi

# Certificados públicos legíveis; chaves só para o dono (o nginx do container lê como root)
chmod 644 "$DIR/ca.crt" "$DIR/server.crt"
chmod 600 "$DIR/server.key" "$DIR/ca.key"

echo "Pronto. Certificado do servidor válido até: $(openssl x509 -enddate -noout -in "$DIR/server.crt" | cut -d= -f2)"
echo "Instale a CA em cada aparelho baixando:  http://${lan_ip:-<ip-do-servidor>}:9092/ponto-ca.crt"
