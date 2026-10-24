# Ponto

Aplicação web de registro de ponto, para uso na rede local.

- **backend/**: API em Python (FastAPI + SQLAlchemy + psycopg) — container `ponto-backend`
- **frontend/**: HTML/CSS/JS servido por nginx, com HTTPS, que faz proxy de `/api` para o backend — container `ponto-frontend`
- **Banco**: database `ponto` no Postgres existente (`postgres_db`, rede `postgres_pg_network`), usuário dedicado `ponto`. O esquema é mantido por migrações (Alembic), aplicadas automaticamente na subida do backend.

## Colocar no ar

```bash
cd ~/ponto/web
cp .env.example .env   # só na primeira vez; preencha PGPASSWORD, SECRET_KEY e PIN_KEY
scripts/deploy.sh
```

O `deploy.sh` confere o `.env`, gera o certificado HTTPS se faltar, roda os testes, faz backup do banco e só então sobe os containers.

- Relógio de ponto: `https://<ip-do-servidor>:9443` (ex.: https://192.168.0.34:9443)
- Administração: `https://<ip-do-servidor>:9443/admin`
- O endereço antigo `http://<ip>:9092` apenas redireciona para o HTTPS.

### HTTPS na rede local (certificado próprio)

`scripts/gerar-certificado.sh` cria uma **CA local** e um certificado do servidor para o IP da rede, o IP e o nome do Tailscale e o nome da máquina. A CA tem duas proteções:

- **Restrição de nomes:** ela só vale para a rede local, o Tailscale e os nomes deste servidor. Mesmo que a chave vaze, não serve para se passar por outros sites (banco, e-mail) nos aparelhos que a instalaram.
- **Chave cifrada com senha:** `certs/ca.key` só funciona com a senha, pedida ao criar a CA e ao renovar o certificado do servidor. Guarde-a num gerenciador de senhas.

Para os navegadores confiarem no certificado, **instale a CA uma vez em cada aparelho** (tablet do relógio, celulares e computadores do admin):

1. No aparelho, abra `http://<ip-do-servidor>:9092/ponto-ca.crt` e baixe o arquivo.
2. Instale como autoridade certificadora:
   - **Android:** Configurações → Segurança → Criptografia e credenciais → Instalar certificado → Certificado CA.
   - **iPhone/iPad:** abra o arquivo, instale o perfil em Ajustes e depois ative em Ajustes → Geral → Sobre → Ajustes de Confiança de Certificados.
   - **Windows:** abra o arquivo → Instalar certificado → "Autoridades de Certificação Raiz Confiáveis".
   - **Linux/Chrome:** Configurações → Privacidade e segurança → Gerenciar certificados → Autoridades → Importar.
3. Sem instalar a CA também funciona, mas o navegador mostra um aviso que precisa ser aceito.

Se o IP do servidor mudar dentro da rede local, ou o certificado estiver para vencer: `scripts/gerar-certificado.sh --renovar && docker compose restart frontend` (pede a senha da CA). O certificado do servidor vale 825 dias (o `deploy.sh` avisa quando faltar menos de 30); a CA vale 10 anos. Se a rede local mudar (outra faixa de IPs) ou a senha for perdida, crie uma CA nova com `scripts/gerar-certificado.sh --nova-ca`: todos os aparelhos precisam remover a antiga e instalar a nova.

### Firewall

O Docker publica as portas por fora do `ufw`, então o `scripts/firewall.sh` coloca as regras na cadeia `DOCKER-USER`: as portas do ponto só aceitam conexões da rede local e do Tailscale. Se alguma porta for repassada pelo roteador por engano, o resto da internet é barrado. Instale uma vez (precisa de root):

```bash
sudo scripts/firewall.sh instalar   # aplica agora e a cada boot
sudo scripts/firewall.sh status     # mostra as regras e os contadores
```

As portas são publicadas só em IPv4, porque o firewall filtra IPv4.

### Logins

- **Administradores:** o primeiro é criado na primeira subida a partir de `ADMIN_USER`/`ADMIN_PASSWORD`. Os demais são cadastrados em Administração → "Administradores e relógios". Cada pessoa deve ter o próprio login: o histórico de correções registra quem fez cada alteração.
  - **Senha:** mínimo de 12 caracteres, recusando senhas muito comuns. Senha provisória (a do `.env`, ou a criada por outro admin) ou fora da política obriga a troca antes de usar o painel.
  - **Verificação em duas etapas (obrigatória):** no primeiro acesso, o admin cadastra a conta num app autenticador (Google Authenticator, Microsoft Authenticator, Bitwarden...) lendo um QR code, e recebe 10 códigos de recuperação para o caso de perder o celular. Depois, o login pede a senha e o código de 6 dígitos. Para desligar a obrigatoriedade: `ADMIN_2FA_REQUIRED=false` no `.env`.
  - **Sessões:** cada login fica guardado no servidor e vale até sair, por até 30 dias, caindo sozinho após 8 horas sem uso. Em **Conta e segurança** (`/senha`) dá para trocar a senha, gerenciar as duas etapas, ver os aparelhos conectados e encerrá-los. Trocar a senha encerra os outros aparelhos.
  - Após 5 erros (senha ou código) em 5 minutos o IP fica bloqueado até a janela passar.
- **Proteção contra CSRF:** toda requisição que altera dados (POST, PATCH, DELETE) com cookie de sessão precisa vir das próprias páginas do ponto (cabeçalho `Origin`). Isso importa porque outros serviços no mesmo IP contam como "mesmo site" para o navegador.
- **Aparelho do relógio:** não fica logado como admin.
  1. No aparelho, entre como administrador.
  2. Na tela do relógio, toque em **Usar como relógio**. O aparelho passa a só bater ponto (vale 1 ano) e o admin é desconectado dele.
  3. Para administrar a partir dele, toque em **Administração** e entre: nesse aparelho o login do admin dura 30 minutos. Use **Sair** ao terminar.
  4. Perdeu um tablet? Administração → **Desligar todos os relógios** e ative de novo os que continuam em uso.
- Dez PINs errados em 5 minutos pausam o relógio até a janela passar.

### Variáveis do `.env`

| Variável         | Descrição |
|------------------|-----------|
| `PGUSER`         | Usuário do Postgres (`ponto`) |
| `PGPASSWORD`     | Senha desse usuário |
| `ADMIN_USER`     | Usuário do primeiro administrador (só na primeira subida) |
| `ADMIN_PASSWORD` | Senha inicial dele (só na primeira subida) |
| `SECRET_KEY`     | Assina os cookies. Sem ela, todos os logins e relógios caem a cada reinício |
| `PIN_KEY`        | **Obrigatória.** Chave do hash dos PINs e dos códigos de comprovante. **Nunca troque**: todos os PINs deixam de funcionar. Guarde uma cópia num gerenciador de senhas, separada do backup |
| `COOKIE_SECURE`  | `true` (o site só funciona por HTTPS) |
| `HTTPS_PORT`     | Porta do HTTPS no servidor (padrão `9443`) |
| `API_DOCS`       | `true` liga a documentação da API em `/api/docs` (desligada por padrão) |

## Funcionalidades

**Relógio**
- O funcionário digita o PIN. É **saída** se houver uma entrada aberta há menos de 16 h, senão é **entrada**; turnos que passam da meia-noite contam no dia da entrada. Batida a menos de 1 minuto da anterior é recusada (toque duplo).
- Mostra o **comprovante** de cada batida (número e código de 10 caracteres, que só o sistema consegue gerar).
- O visor usa a **hora do servidor**, a mesma que vai na batida, mesmo se o relógio do tablet estiver errado.
- **Sem conexão:** a batida fica guardada no aparelho e é enviada quando a conexão volta (até 24 h). Ela entra marcada como `off` para o admin conferir, porque o horário veio do aparelho.
- **Ver meu espelho:** com o PIN, o funcionário vê o próprio mês, os comprovantes e o banco de horas, e dá **ciência** dos meses fechados. A janela fecha sozinha após 1 minuto sem uso.

**App de celular** (pasta `app/` na raiz do repositório)
- Este backend atende também o app de iPhone, no contrato `/api/pontos/...` (autenticação pelo cabeçalho `X-API-Key`).
- O admin gera uma **chave de celular** por funcionário (Funcionários → Celular). A chave aparece uma única vez, só o hash fica no banco, e pode ser revogada.
- A batida feita na hora no app entra direto no ponto, marcada `cel` (em vermelho se o relógio do celular estiver adiantado em relação ao servidor). Batida lançada depois, correção e exclusão feitas no app viram **solicitações** que o admin aprova ou recusa no card do topo do painel.

**Administração**
- **Funcionários:** nome, PIN, jornada diária e dias de trabalho, admissão e desligamento. Mudar a jornada cria uma nova vigência a partir de uma data, sem alterar o passado. Só cadastros sem nenhum registro podem ser excluídos; os demais são desativados.
- **Espelho mensal:** todos os dias com batidas, horas trabalhadas, horas noturnas, previsto e saldo; marca faltas, incompletos, feriados e dias fora do contrato. Resumo com saldo do mês e **banco de horas** acumulado.
- **Regras da CLT no cálculo:**
  - Hora noturna reduzida (art. 73): das 22h às 5h, 52min30s valem 1 hora. As horas trabalhadas já consideram isso e a coluna "Noturno" é a base do adicional.
  - Tolerância (art. 58 §1º): diferenças de até 10 minutos no dia não geram saldo.
  - Avisos para conferência: intervalo menor que 1h em jornada acima de 6h (ou 15 min acima de 4h), menos de 11h entre jornadas, mais de 2h extras no dia e trabalho em folga/feriado.
- **Feriados:** os nacionais são calculados automaticamente (inclusive a Sexta-feira Santa). Municipais, estaduais e pontos facultativos (Carnaval, Corpus Christi) são cadastrados pelo admin.
- **Correções com histórico:** lançamentos e correções exigem motivo e ficam marcados com `*`. O horário original do relógio é preservado, nada é apagado de verdade (excluídas podem ser vistas e restauradas) e cada ação registra quem fez, quando, antes e depois.
- **Fechamento do mês:** depois de conferido, o mês é fechado (por funcionário ou para todos). As batidas ficam travadas e o funcionário pode dar ciência no relógio. Reabrir apaga a ciência.
- **Exportação:** CSV do espelho de um funcionário, CSV com o resumo de todos (para a contabilidade) e página de impressão com o espelho de todos, com linha de assinatura (imprima ou salve como PDF).

Limites conhecidos: os arquivos AFD/AEJ da Portaria 671 não são gerados (o sistema é para controle interno, não um REP-P registrado no INPI); a prorrogação do horário noturno após as 5h não é calculada; uma batida enviada depois, sem conexão, não muda o tipo (entrada/saída) das batidas já registradas depois dela, e o dia aparece como incompleto para o admin corrigir.

## Backup

`scripts/backup.sh` roda todo dia às 03:15 (cron do usuário `filipe`) e guarda em `backups/`: os últimos 14 diários e um por mês por 5 anos. Log em `backups/backup.log`. O `deploy.sh` também faz um backup antes de cada atualização.

**Os backups são criptografados.** Cada dump é cifrado com a chave pública `backups/chave-publica.asc`; só a chave **privada**, guardada fora do servidor, decifra. O dump em texto aberto só existe na memória durante a conferência. Assim, uma cópia dos backups levada do servidor não pode ser lida.

- Criar o par de chaves (uma vez): `scripts/backup-chave.sh`. A chave privada sai em `~/ponto-backup-chave-privada.asc`: guarde-a fora do servidor (ex.: anexo no Vaultwarden) e apague daqui com `shred -u ~/ponto-backup-chave-privada.asc`. **Sem ela, nenhum backup pode ser restaurado.**
- Cópia fora do servidor (opcional): defina `BACKUP_REMOTO` no `.env` com um destino do `rsync` (ex.: `usuario@maquina:/backups/ponto/`, com login por chave SSH). Os arquivos já vão cifrados.

Restaurar (substitui o banco atual — pare o backend antes). Precisa da chave privada; use um chaveiro temporário para ela não ficar no servidor:

```bash
export GNUPGHOME=$(mktemp -d)
gpg --import ponto-backup-chave-privada.asc
docker compose stop backend
gpg --decrypt backups/ponto-AAAAMMDD-HHMMSS.dump.gpg \
  | docker exec -i postgres_db pg_restore -U ponto -d ponto --clean --if-exists --no-owner
docker compose start backend
rm -rf "$GNUPGHOME"; unset GNUPGHOME
```

O backup não contém a `PIN_KEY`: sem ela, os PINs, os códigos de comprovante e a verificação em duas etapas dos admins não funcionam no banco restaurado. Guarde-a também fora do servidor.

## Estrutura do backend

```
backend/app/
├── main.py                 # cria o FastAPI, handlers de erro e rotas
├── core/                   # configuração, erros, limite de tentativas, hash e tokens
├── db/                     # engine/sessão, migrações (migrations/versions/0001, 0002, 0003...)
├── models/                 # funcionário + jornadas, batida + histórico, admin, feriado, fechamento
├── schemas/                # entrada/saída da API (Pydantic)
├── repositories/           # consultas ao banco
├── services/
│   ├── shifts.py           # pares entrada→saída (inclusive turno noturno)
│   ├── report_service.py   # espelho, banco de horas, regras da CLT e CSV
│   ├── punch_service.py    # batida pelo PIN (inclusive offline), correções com histórico
│   ├── calendar_service.py # feriados, fechamento do mês e espelho do funcionário
│   ├── mobile_service.py   # app de celular: chaves, lote, consultas e solicitações
│   ├── employee_service.py
│   └── auth_service.py     # administradores e relógios
├── api/routes/             # health, auth, clock (relógio + espelho do funcionário), mobile (app), admin
└── utils/                  # datas/fuso, horário noturno, feriados nacionais
```

## Desenvolvimento

Testes (regras de jornada, CLT, feriados, espelho, tokens e limites):

```bash
cd ~/ponto/web/backend
docker build -t ponto-backend .
docker run --rm -u root -v "$PWD/tests:/app/tests:ro" -v "$PWD/requirements-dev.txt:/app/requirements-dev.txt:ro" \
  ponto-backend sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q tests"
```

Nova mudança no banco: crie `app/db/migrations/versions/0005_<descricao>.py` com `revision = "0005"` e `down_revision = "0004"` (veja as anteriores como modelo). Ela é aplicada na próxima subida.
