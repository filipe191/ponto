import os

# Antes de importar o app: as configurações são lidas na importação
os.environ.setdefault("PIN_KEY", "chave-de-teste")
os.environ.setdefault("SECRET_KEY", "segredo-de-teste")
os.environ.setdefault("TZ", "America/Sao_Paulo")
