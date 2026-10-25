"""Aviso por e-mail a quem cuida do servidor: backup com falha, sistema fora do ar e de volta.

Usado pelos scripts (scripts/alertar.sh), que rodam a imagem do backend à parte para avisar mesmo com
o backend fora do ar:

    docker run --rm -i --env-file .env ponto-backend python -m app.alerta "Assunto" < corpo.txt

Usa o mesmo SMTP do aviso de solicitações (SMTP_* no .env) e manda para ALERTA_EMAIL. Sem eles, só
avisa que não enviou: o alerta fica no log do script.
"""

import sys

from app.core.config import settings
from app.services.notify import deliver, email_enabled, recipients


def main(argv: list[str]) -> int:
    subject = argv[1] if len(argv) > 1 else "Ponto: alerta"
    body = sys.stdin.read() if not sys.stdin.isatty() else ""
    to = recipients(settings.alerta_email)
    if not email_enabled() or not to:
        print("Alerta não enviado por e-mail: defina SMTP_HOST e ALERTA_EMAIL no .env")
        return 0
    if deliver(to, subject, body.strip() or subject):
        print(f"Alerta enviado para {', '.join(to)}")
        return 0
    print("Falhou o envio do alerta por e-mail (veja o servidor SMTP)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
