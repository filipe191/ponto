# Ponto

Aplicação web de registro de ponto.

- **backend/**: API em Python (FastAPI + psycopg) — container `ponto-backend`
- **frontend/**: HTML/CSS/JS servido por nginx, que faz proxy de `/api` para o backend — container `ponto-frontend`
- **Banco**: database `ponto` no Postgres existente (`postgres_db`, rede `postgres_pg_network`), usuário dedicado `ponto`. O esquema é mantido por migrações (Alembic), aplicadas automaticamente na subida do backend.

## Estrutura do backend

```
backend/app/
├── main.py                 # cria o FastAPI, handlers de erro e rotas
├── core/
│   ├── config.py           # Settings (variáveis de ambiente)
│   ├── errors.py           # ApiError e respostas {"error": "..."}
│   ├── ratelimit.py        # limite de tentativas (login e PIN) por IP
│   └── security.py         # hash de PIN/senha e tokens (admin e relógio)
├── db/
│   ├── base.py             # Base declarativa do SQLAlchemy
│   ├── session.py          # engine, sessão (get_db) e inicialização
│   ├── migrate.py          # aplica as migrações na subida
│   └── migrations/versions # migrações do Alembic (0001, 0002, ...)
├── models/                 # tabelas (SQLAlchemy ORM)
│   ├── employee.py         # funcionário + jornada prevista
│   └── punch.py            # batida + histórico de correções (punch_changes)
├── schemas/                # entrada/saída da API (Pydantic)
├── repositories/           # consultas ao banco
├── services/               # regras de negócio
│   ├── shifts.py           # pares entrada→saída (inclusive turno noturno)
│   ├── employee_service.py
│   ├── punch_service.py    # batida pelo PIN, correções com histórico
│   └── report_service.py   # espelho mensal, banco de horas e CSV
├── api/
│   ├── deps.py             # sessão do banco, acesso (admin / relógio)
│   ├── router.py           # junta tudo sob /api
│   └── routes/
│       ├── health.py       # /api/health
│       ├── auth.py         # /api/auth/* (login, modo relógio, senha)
│       ├── clock.py        # /api/punch, /api/today (relógio)
│       └── admin.py        # /api/admin/* (só admin)
└── utils/
    └── dates.py            # limites de dia/mês no fuso configurado
```

## Como rodar

```bash
cd ~/ponto
cp .env.example .env   # só na primeira vez; preencha PGPASSWORD, SECRET_KEY e PIN_KEY
docker compose up -d --build
```

- Relógio de ponto: http://localhost:9092
- Administração: http://localhost:9092/admin
- Trocar senha: http://localhost:9092/senha

O login do administrador é criado no banco (tabela `admin_account`) na primeira subida, a partir de `ADMIN_USER`/`ADMIN_PASSWORD`. Depois disso a senha é trocada pela página `/senha`; mudar o `.env` não altera mais o login. Após 5 senhas erradas em 5 minutos o IP fica bloqueado até a janela passar.

### Aparelho do relógio

O tablet/computador onde os funcionários batem o ponto **não fica logado como admin**:

1. No aparelho, entre com a conta de administrador.
2. Na tela do relógio, clique em **Usar como relógio**. O aparelho passa a só bater ponto (cookie `ponto_kiosk`, válido por 1 ano) e a conta do admin é desconectada dele.
3. Para administrar a partir desse aparelho, clique em **Administração** e entre com a senha. Nesse aparelho o login do admin dura só 30 minutos; use **Sair** ao terminar e o relógio continua funcionando.

Trocar a senha do admin desliga todos os relógios (exceto o aparelho onde a troca foi feita); é assim que se revoga um aparelho perdido. Dez PINs errados em 5 minutos pausam o relógio até a janela passar.

### Variáveis do `.env`

| Variável         | Descrição |
|------------------|-----------|
| `PGUSER`         | Usuário do Postgres (`ponto`) |
| `PGPASSWORD`     | Senha desse usuário |
| `ADMIN_USER`     | Usuário do login (só na primeira subida) |
| `ADMIN_PASSWORD` | Senha inicial do login (só na primeira subida) |
| `SECRET_KEY`     | Assina os cookies. Sem ela, todos os logins e relógios caem a cada reinício |
| `PIN_KEY`        | **Obrigatória.** Chave do hash dos PINs. **Nunca troque**: todos os PINs deixam de funcionar. Guarde uma cópia junto com o backup do banco |
| `COOKIE_SECURE`  | `true` quando o site estiver atrás de HTTPS |
| `API_DOCS`       | `true` liga a documentação da API em `/api/docs` (desligada por padrão) |

## Funcionalidades

- **Relógio**: digita o PIN (teclado na tela ou físico). É **saída** se o funcionário tiver uma entrada aberta há menos de 16 h, senão é **entrada** — turnos que passam da meia-noite funcionam e contam no dia da entrada. Uma batida com menos de 1 minuto da anterior é recusada (evita toque duplo).
- **Cartão de hoje**: lista ao lado do relógio, atualizada a cada 30 s (inclui quem entrou ontem à noite e ainda está trabalhando).
- **Funcionários**: nome, PIN, jornada diária e dias de trabalho; ativar/desativar. Só é possível excluir cadastros sem nenhum registro de ponto — quem já bateu ponto é desativado.
- **Espelho de ponto** mensal: todos os dias do mês com batidas, horas trabalhadas, previsto e saldo; marca faltas, dias incompletos e o dia em andamento. Resumo com saldo do mês e **banco de horas** acumulado desde o início do histórico do funcionário.
- **Correções com histórico**: lançamentos e correções exigem motivo e ficam marcados com `*`. O horário original do relógio é preservado, nada é apagado de verdade (batidas excluídas podem ser vistas e restauradas) e cada ação fica registrada com usuário, data, antes e depois.
- **Exportação CSV** do espelho (separador `;`, abre direto no Excel), com previsto, saldo e banco de horas.

Observações: alterar a jornada de um funcionário recalcula também os meses anteriores; feriados não são descontados automaticamente (lance a folga como ajuste ou considere no banco).

## Desenvolvimento

Testes (regras de jornada, espelho, tokens e limites), rodando dentro da imagem do backend:

```bash
cd ~/ponto/backend
docker build -t ponto-backend .
docker run --rm -u root -v "$PWD/tests:/app/tests:ro" -v "$PWD/requirements-dev.txt:/app/requirements-dev.txt:ro" \
  ponto-backend sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q tests"
```

Nova mudança no banco: crie `app/db/migrations/versions/0003_<descricao>.py` com `revision = "0003"` e `down_revision = "0002"` (veja a 0002 como modelo). Ela é aplicada na próxima subida.
