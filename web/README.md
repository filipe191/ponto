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

O `deploy.sh` confere o `.env`, gera o certificado HTTPS se faltar, roda os testes, procura vulnerabilidades conhecidas nas dependências (`pip-audit`; interrompe o deploy se achar), faz backup do banco e só então sobe os containers. Para pular a checagem de dependências numa emergência (ex.: sem internet): `PULAR_AUDITORIA=1 scripts/deploy.sh`.

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

### Várias empresas

Um mesmo servidor atende várias empresas. Cada uma tem os próprios funcionários, feriados, administradores, relógios, celulares e auditoria, e uma não enxerga os dados da outra.

- **Superadministrador:** criado na primeira subida a partir de `ADMIN_USER`/`ADMIN_PASSWORD`. Em Administração → **Empresas** ele cadastra cada empresa já com o primeiro admin dela, edita o nome e o contato de privacidade, e desativa ou reativa a empresa. Para trabalhar numa empresa, ele a escolhe no seletor ao lado de "Ponto"; cada entrada fica na auditoria da empresa. Na mesma seção ficam os **superadministradores** (tenha pelo menos dois) e a **auditoria do sistema**: logins e conta dos superadmins, cadastro e desativação de empresas e de superadmins.
- **Admins de uma empresa** só veem e alteram a própria empresa.
- **Empresa desativada:** os admins dela saem na hora e não conseguem entrar, e os relógios e os celulares dela param. Nada é apagado; ao reativar, tudo volta.
- **PIN:** é único dentro de cada empresa, então duas empresas podem ter funcionários com o mesmo PIN. O relógio sabe de qual empresa é pela liberação do aparelho.
- **Instalação que já existia antes das várias empresas:** os dados viram a empresa nº 1, com nome e contato tirados de `EMPRESA_NOME` e `PRIVACIDADE_CONTATO`. O admin mais antigo vira superadmin, e os relógios já liberados continuam funcionando.

### Logins

- **Administradores:** o superadmin é criado na primeira subida (veja acima). Os admins de cada empresa são cadastrados em Administração → "Administradores e relógios". Cada pessoa deve ter o próprio login: o histórico de correções registra quem fez cada alteração. O nome de usuário é único no sistema todo.
  - **Senha:** mínimo de 12 caracteres, recusando senhas muito comuns. Senha provisória (a do `.env`, ou a criada por outro admin) ou fora da política obriga a troca antes de usar o painel.
  - **Verificação em duas etapas (obrigatória):** no primeiro acesso, o admin cadastra a conta num app autenticador (Google Authenticator, Microsoft Authenticator, Bitwarden...) lendo um QR code, e recebe 10 códigos de recuperação para o caso de perder o celular. Depois, o login pede a senha e o código de 6 dígitos. Para desligar a obrigatoriedade: `ADMIN_2FA_REQUIRED=false` no `.env`.
  - **Sessões:** cada login fica guardado no servidor e vale até sair, por até 30 dias, caindo sozinho após 8 horas sem uso. Em **Conta e segurança** (`/senha`) dá para trocar a senha, gerenciar as duas etapas, ver os aparelhos conectados e encerrá-los. Trocar a senha encerra os outros aparelhos.
  - Após 5 erros (senha ou código) em 5 minutos o IP fica bloqueado até a janela passar.
- **Proteção contra CSRF:** toda requisição que altera dados (POST, PATCH, DELETE) com cookie de sessão precisa vir das próprias páginas do ponto (cabeçalho `Origin`). Isso importa porque outros serviços no mesmo IP contam como "mesmo site" para o navegador.
- **Aparelho do relógio:** não fica logado como admin.
  1. No aparelho, entre como administrador (o superadmin escolhe antes a empresa no painel).
  2. Na tela do relógio, toque em **Usar como relógio**. O aparelho passa a só bater ponto, e só para os funcionários da empresa (vale 1 ano). O nome da empresa aparece no topo, e o admin é desconectado do aparelho.
  3. Para administrar a partir dele, toque em **Administração** e entre: nesse aparelho o login do admin dura 30 minutos. Use **Sair** ao terminar.
  4. Para abrir como um app, em tela cheia e sem a barra de endereço: no Chrome do tablet, menu → **Instalar app** (ou **Adicionar à tela inicial**; no iPad, Compartilhar → **Adicionar à Tela de Início**). O ícone é o mesmo do app de celular. O aparelho precisa confiar no certificado do ponto (CA instalada, ver HTTPS), senão o navegador não oferece a instalação.
  5. Perdeu um tablet? Administração → **Desligar todos os relógios** e ative de novo os que continuam em uso. Isso desliga só os relógios da empresa aberta.
- **PIN:** de 6 a 8 dígitos (botão **Gerar PIN** no cadastro). PINs antigos de 4 ou 5 dígitos ainda valem, mas aparecem como "PIN curto" no painel para serem trocados.
- Dez PINs errados em 5 minutos pausam o relógio por 5 minutos; cada nova rodada de erros dobra a pausa (até 24 h). Os bloqueios ficam no banco e continuam valendo depois de reiniciar o backend. Cada bloqueio aparece em **Avisos de segurança**, na aba Início do painel.

### Variáveis do `.env`

| Variável         | Descrição |
|------------------|-----------|
| `PGUSER`         | Usuário do Postgres (`ponto`) |
| `PGPASSWORD`     | Senha desse usuário |
| `ADMIN_USER`     | Usuário do superadministrador (só na primeira subida) |
| `ADMIN_PASSWORD` | Senha inicial dele (só na primeira subida) |
| `SECRET_KEY`     | Assina os cookies. Sem ela, todos os logins e relógios caem a cada reinício |
| `PIN_KEY`        | **Obrigatória.** Chave do hash dos PINs e dos códigos de comprovante. **Nunca troque**: todos os PINs deixam de funcionar. Guarde uma cópia num gerenciador de senhas, separada do backup |
| `COOKIE_SECURE`  | `true` (o site só funciona por HTTPS) |
| `HTTPS_PORT`     | Porta do HTTPS no servidor (padrão `9443`) |
| `API_DOCS`       | `true` liga a documentação da API em `/api/docs` (desligada por padrão) |
| `EMPRESA_NOME`   | Só para instalações anteriores às várias empresas: nome da empresa nº 1 na migração. Depois, o nome fica no cadastro da empresa |
| `PRIVACIDADE_CONTATO` | Idem: contato de privacidade da empresa nº 1 na migração |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Servidor de e-mail do aviso de solicitações do app. Sem `SMTP_HOST`, nenhum e-mail é enviado. Porta `465` usa SSL; as outras, STARTTLS (padrão `587`) |
| `PAINEL_URL`     | Endereço do painel no e-mail de aviso (ex.: `https://192.168.0.34:9443/admin`); vazio, o e-mail vai sem link |

## Funcionalidades

**Relógio**
- O funcionário digita o PIN. É **saída** se houver uma entrada aberta há menos de 16 h, senão é **entrada**; turnos que passam da meia-noite contam no dia da entrada. Batida a menos de 1 minuto da anterior é recusada (toque duplo).
- Mostra o **comprovante** de cada batida (número e código de 10 caracteres, que só o sistema consegue gerar) e, por 15 segundos, as batidas de hoje **só de quem bateu**: os colegas não aparecem na tela.
- O visor usa a **hora do servidor**, a mesma que vai na batida, mesmo se o relógio do tablet estiver errado.
- **Sem conexão:** a batida fica guardada no aparelho e é enviada quando a conexão volta (até 24 h). Ela entra marcada como `off` para o admin conferir, porque o horário veio do aparelho.
- **Ver meu espelho:** com o PIN, o funcionário vê o próprio mês, os comprovantes e o banco de horas, e dá **ciência** dos meses fechados. A janela fecha sozinha após 1 minuto sem uso.

**App de celular** (pasta `app/` na raiz do repositório)
- Este backend atende também o app de iPhone, no contrato `/api/pontos/...` (autenticação pelo cabeçalho `X-API-Key`).
- O admin gera uma **chave de celular** por funcionário (Funcionários → Celular). A chave aparece uma única vez, só o hash fica no banco, e pode ser revogada. Ela vale 1 ano (o painel avisa 30 dias antes) e é revogada sozinha depois de 90 dias sem uso.
- A batida feita na hora no app entra direto no ponto, marcada `cel` (em vermelho se o relógio do celular estiver adiantado em relação ao servidor). Batida lançada depois, correção e exclusão feitas no app viram **solicitações** que o admin aprova ou recusa na aba Início do painel (a aba mostra quantas estão pendentes). Com o SMTP configurado e um e-mail de avisos no cadastro da empresa, chega um e-mail quando há solicitação nova: só com a quantidade pendente (sem nomes nem horários) e no máximo um a cada 30 minutos por empresa.

**Administração**
- **Funcionários:** nome, PIN, jornada diária e dias de trabalho, admissão e desligamento. Mudar a jornada cria uma nova vigência a partir de uma data, sem alterar o passado. Só cadastros sem nenhum registro podem ser excluídos; os demais são desativados.
- **Espelho mensal:** todos os dias com batidas, horas trabalhadas, horas noturnas, previsto e saldo; marca faltas, incompletos, feriados e dias fora do contrato. Resumo com saldo do mês e **banco de horas** acumulado.
- **Regras da CLT no cálculo:**
  - Hora noturna reduzida (art. 73): por padrão das 22h às 5h, 52min30s valem 1 hora. As horas trabalhadas já consideram isso e a coluna "Noturno" é a base do adicional.
  - Tolerância (art. 58 §1º): por padrão, diferenças de até 10 minutos no dia não geram saldo.
- **Regras de jornada por empresa** (Administração → Regras de jornada): tolerância, horário noturno, hora noturna (urbano 52,5 min; rural 60 min, com atalhos para lavoura 21h–5h e pecuária 20h–4h) e jornada máxima. Cada mudança vale a partir de uma data e não pode começar num mês já fechado: os dias anteriores e o banco de horas acumulado não mudam. Fuso horário e prazo das batidas sem conexão também são da empresa; o fuso só muda antes da primeira batida. Só o superadmin altera; os admins da empresa consultam. Os valores do `.env` são o padrão das empresas novas.
  - Avisos para conferência: intervalo menor que 1h em jornada acima de 6h (ou 15 min acima de 4h), menos de 11h entre jornadas, mais de 2h extras no dia e trabalho em folga/feriado.
- **Feriados:** os nacionais são calculados automaticamente (inclusive a Sexta-feira Santa). Municipais, estaduais e pontos facultativos (Carnaval, Corpus Christi) são cadastrados pelo admin.
- **Correções com histórico:** lançamentos e correções exigem motivo e ficam marcados com `*`. O horário original do relógio é preservado, nada é apagado de verdade (excluídas podem ser vistas e restauradas) e cada ação registra quem fez, quando, antes e depois.
- **Fechamento do mês:** depois de conferido, o mês é fechado (por funcionário ou para todos). As batidas ficam travadas e o funcionário pode dar ciência no relógio. Reabrir exige motivo e pede uma nova ciência; o fechamento e a ciência anteriores continuam na auditoria e aparecem no espelho.
- **Auditoria:** cadastro, PIN (sem o valor), jornada, feriados, celulares, admins, logins, relógios e fechamentos ficam registrados com quem, quando, antes e depois. O banco recusa alterar ou apagar esses registros.
- **Exportação:** CSV do espelho de um funcionário, CSV com o resumo de todos (para a contabilidade) e página de impressão com o espelho de todos, com linha de assinatura (imprima ou salve como PDF).

**Privacidade (LGPD)**
- **Aviso de privacidade** em `/privacidade` (link no relógio e no login): o que é guardado, para quê, por quanto tempo e a quem pedir acesso. O nome e o contato vêm do cadastro da empresa do relógio (Administração → Empresas). Para o celular do funcionário, cada empresa tem um link próprio com um código aleatório (`/privacidade?e=<código>`), mostrado em Configurações → Administradores e relógios → **Aviso de privacidade**. Sem link, relógio ou admin logado, a página usa um texto genérico.
- **Pedido de acesso:** Funcionários → **Dados** baixa em JSON tudo o que o sistema guarda sobre a pessoa.
- **Retenção:** 5 anos depois do desligamento, o painel avisa e oferece **Anonimizar**. O nome, o PIN e os celulares são apagados; as batidas e as horas continuam, como "Ex-funcionário nº N".

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
├── api/routes/             # health, auth, clock (relógio + espelho do funcionário), mobile (app), admin, privacy
└── utils/                  # datas/fuso, horário noturno, feriados nacionais
```

## Desenvolvimento

Testes unitários (regras de jornada, CLT, feriados, espelho, tokens e limites) e de integração (`tests/integration/`: migração de um banco antigo, isolamento entre empresas, relógios, regras por empresa, superadmins), estes contra um Postgres de verdade:

```bash
cd ~/ponto/web/backend
docker network create ponto-testes
docker run -d --name ponto-testes-db --network ponto-testes -e POSTGRES_USER=ponto -e POSTGRES_PASSWORD=teste -e POSTGRES_DB=ponto_test postgres:18
docker build -t ponto-backend .
docker run --rm -u root --network ponto-testes -e PGHOST=ponto-testes-db -e PGUSER=ponto -e PGPASSWORD=teste -e PGDATABASE=ponto_test \
  -v "$PWD/tests:/app/tests:ro" -v "$PWD/requirements-dev.txt:/app/requirements-dev.txt:ro" \
  ponto-backend sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q tests"
docker rm -f ponto-testes-db && docker network rm ponto-testes
```

Os testes de integração **apagam e recriam o banco**: só rodam quando `PGDATABASE` contém "test"; sem isso, são pulados. O `scripts/deploy.sh` faz o mesmo com um Postgres descartável, e o GitHub Actions (`.github/workflows/backend.yml`) roda tudo, mais o `pip-audit`, a cada push.

Nova mudança no banco: crie `app/db/migrations/versions/0013_<descricao>.py` com `revision = "0013"` e `down_revision = "0012"` (veja as anteriores como modelo). Ela é aplicada na próxima subida.

Páginas: o HTML fica em `frontend/public/*.html` e o script de cada uma em `frontend/public/js/`. A CSP só aceita scripts desses arquivos (`script-src 'self'`): não coloque `<script>` com código nem `onclick=` dentro do HTML.
