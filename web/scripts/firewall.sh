#!/usr/bin/env bash
# Firewall das portas do ponto: só a rede local e o Tailscale chegam ao relógio e ao painel.
# Se alguma porta for repassada pelo roteador (de propósito, por engano ou por UPnP), o resto
# da internet é barrado.
#
# O Docker publica as portas por fora do ufw, então as regras ficam na cadeia DOCKER-USER, que o
# Docker consulta antes de entregar o tráfego aos containers.
#
# Uso (precisa de root):
#   sudo scripts/firewall.sh instalar     aplica agora e a cada boot (serviço systemd)
#   sudo scripts/firewall.sh desinstalar  remove o serviço e as regras
#   sudo scripts/firewall.sh aplicar      aplica uma vez (some no próximo boot)
#   sudo scripts/firewall.sh remover      remove as regras
#   sudo scripts/firewall.sh status       mostra as regras e os contadores
#
# Variáveis opcionais:
#   FIREWALL_REDES   redes liberadas (padrão: a rede local atual + 100.64.0.0/10 do Tailscale)
#   FIREWALL_PORTAS  portas do host protegidas (padrão: 9092 e a HTTPS_PORT do .env, ou 9443)
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$RAIZ/scripts/firewall.sh"
CADEIA="PONTO-FW"
SERVICO="/etc/systemd/system/ponto-firewall.service"

[[ $EUID -eq 0 ]] || { echo "Rode com sudo: sudo $0 ${1:-status}" >&2; exit 1; }
command -v iptables >/dev/null || { echo "iptables não encontrado" >&2; exit 1; }

rede_local() {
    local dev cidr
    dev="$(ip -o -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* dev \([^ ]*\).*/\1/p')"
    cidr="$(ip -o -4 addr show dev "$dev" 2>/dev/null | awk '{print $4}' | head -1)"
    [[ -n "$cidr" ]] && python3 -c "import ipaddress,sys; print(ipaddress.ip_network(sys.argv[1], strict=False))" "$cidr"
}

https_port="$(grep -E '^HTTPS_PORT=' "$RAIZ/.env" 2>/dev/null | cut -d= -f2- || true)"
PORTAS="${FIREWALL_PORTAS:-9092 ${https_port:-9443}}"
REDES="${FIREWALL_REDES:-$(rede_local) 100.64.0.0/10}"

regra() { echo "-p tcp -m conntrack --ctorigdstport $1 --ctdir ORIGINAL -j $CADEIA"; }

aplicar() {
    [[ "$REDES" =~ [0-9] ]] || { echo "Nenhuma rede detectada; defina FIREWALL_REDES" >&2; exit 1; }
    iptables -N DOCKER-USER 2>/dev/null || true
    iptables -N "$CADEIA" 2>/dev/null || iptables -F "$CADEIA"
    for rede in $REDES; do
        iptables -A "$CADEIA" -s "$rede" -j RETURN
    done
    iptables -A "$CADEIA" -j DROP
    for porta in $PORTAS; do
        # shellcheck disable=SC2046
        iptables -C DOCKER-USER $(regra "$porta") 2>/dev/null || iptables -I DOCKER-USER $(regra "$porta")
    done
    echo "Portas $PORTAS liberadas só para: $REDES"
}

remover() {
    for porta in $PORTAS; do
        # shellcheck disable=SC2046
        while iptables -C DOCKER-USER $(regra "$porta") 2>/dev/null; do iptables -D DOCKER-USER $(regra "$porta"); done
    done
    iptables -F "$CADEIA" 2>/dev/null || true
    iptables -X "$CADEIA" 2>/dev/null || true
    echo "Regras do ponto removidas"
}

status() {
    iptables -L DOCKER-USER -n -v --line-numbers 2>/dev/null | grep -E "Chain|$CADEIA" || echo "DOCKER-USER sem regras do ponto"
    iptables -L "$CADEIA" -n -v 2>/dev/null || echo "Cadeia $CADEIA não existe"
}

instalar() {
    # As redes são fixadas no serviço: no boot o Wi-Fi pode ainda não ter subido
    cat > "$SERVICO" <<EOF
[Unit]
Description=Firewall das portas do ponto (rede local e Tailscale)
After=docker.service network-online.target
Wants=network-online.target
PartOf=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
Environment="FIREWALL_REDES=$REDES" "FIREWALL_PORTAS=$PORTAS"
ExecStart=$SCRIPT aplicar
ExecStop=$SCRIPT remover

[Install]
WantedBy=multi-user.target docker.service
EOF
    systemctl daemon-reload
    systemctl enable --now ponto-firewall.service
    systemctl restart ponto-firewall.service
    echo "Serviço instalado: reaplica as regras a cada boot e a cada reinício do Docker"
    status
}

desinstalar() {
    systemctl disable --now ponto-firewall.service 2>/dev/null || true
    rm -f "$SERVICO"
    systemctl daemon-reload
    remover
}

case "${1:-status}" in
    aplicar) aplicar ;;
    remover) remover ;;
    status) status ;;
    instalar) instalar ;;
    desinstalar) desinstalar ;;
    *) echo "Uso: sudo $0 {instalar|desinstalar|aplicar|remover|status}" >&2; exit 1 ;;
esac
