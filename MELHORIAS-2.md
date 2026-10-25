# Melhorias propostas — 2ª rodada

Levantamento feito em 25/10/2026, depois de concluídas as 14 melhorias da primeira rodada (o antigo `MELHORIAS.md`, que continua no histórico do git). Cada item traz a situação atual e a proposta, em ordem de prioridade. Os pontos de segurança ficam em `SEGURANCA.md`.

## Resumo

| # | Item | Prioridade | Esforço | Onde | Status |
|---|------|-----------|---------|------|--------|
| 1 | Ausências justificadas (atestado, férias, folga) | Alta | Grande | Backend + painel | Pendente |
| 2 | Início do controle e saldo inicial do banco de horas | Alta | Pequeno | Backend + painel | ✅ Concluído |
| 3 | Jornada diferente por dia da semana e escalas | Alta | Grande | Backend + painel | Pendente |
| 4 | Horas extras separadas em 50% e 100% | Alta | Médio | Backend + painel | Pendente |
| 5 | Funcionário vê o resultado das solicitações no app | Média | Médio | Backend + app | Pendente |
| 6 | Aviso por e-mail quando o backup ou o sistema falha | Média | Pequeno | Scripts + backend | Pendente |
| 7 | Teste de restauração do backup | Média | Pequeno | `web/scripts/` | Pendente |
| 8 | Limite de tamanho dos logs do Docker | Média | Pequeno | `docker-compose.yml` | Pendente |
| 9 | Teste das páginas no navegador, no deploy e no CI | Média | Médio | `web/frontend/` + GitHub Actions | Pendente |
| 10 | Administrador só de consulta (contabilidade) | Média | Médio | Backend + painel | Pendente |
| 11 | Feriados que se repetem todo ano | Baixa | Pequeno | Backend + painel | Pendente |
| 12 | Prorrogação do horário noturno | Baixa | Médio | Backend | Pendente |
| 13 | Dividir o `admin.js` em módulos | Baixa | Médio | Frontend | Pendente |

Os itens 1 a 4 são os que mais mudam o espelho de uma empresa real: sem eles, atestados, férias, sábados de meio período e funcionários antigos aparecem como faltas ou saldo errado. O item 2 é pequeno e deve vir antes de cadastrar a primeira empresa de verdade.

---

## 🔴 Prioridade alta

### 1. Ausências justificadas (atestado, férias, folga)

**Hoje.** O espelho só conhece dia de trabalho, folga da jornada e feriado. Um dia de atestado médico, de férias, de licença ou uma folga combinada aparece como **falta** e desconta a jornada inteira do saldo e do banco de horas. A única saída é lançar batidas falsas, o que suja o registro.

**Proposta.**
- Cadastro de ausências por funcionário: tipo (atestado, férias, licença, folga compensada, falta justificada), período (de/até), observação e, para atestado, o anexo opcional.
- Cada tipo diz se o dia **abona** (conta como jornada cumprida: atestado, férias, licença) ou **desconta do banco** (folga compensada).
- No espelho, o dia aparece com a marca do tipo e fora da contagem de faltas; no resumo do mês, uma coluna por tipo.
- Ausência em mês fechado só depois de reabrir, como as batidas. Tudo na auditoria.

### 2. Início do controle e saldo inicial do banco de horas

**Hoje.** O banco de horas começa na data de admissão. Uma empresa que passa a usar o sistema com funcionários admitidos antes começa com meses de "faltas": numa simulação, uma funcionária admitida em janeiro e com batidas só a partir de outubro ficou com banco de **−1506h**. Também não há como trazer o saldo que vinha do controle anterior (planilha, outro sistema).

**Proposta.**
- Uma data de **início do controle** por empresa (padrão: o dia do cadastro), com ajuste por funcionário. Antes dela nenhum dia conta.
- Um **saldo inicial** do banco por funcionário, lançado com motivo e visível no espelho como "saldo anterior ao sistema".
- Na migração, as empresas existentes recebem a data da primeira batida de cada funcionário, para nenhum saldo atual mudar sem querer (conferir antes com o resumo do mês).

**Status: concluído em 25/10/2026.** Início do controle na empresa (Configurações → Ajustes da empresa, só o superadmin) e, se preciso, por funcionário, com o **saldo inicial** do banco e o motivo (Editar funcionário → "Antes do sistema"). Antes do início, o dia aparece como "antes do controle": não é falta, não tem saldo nem avisos. O saldo inicial entra no banco a partir do mês do início e aparece no resumo do espelho. Empresa nova começa o controle no dia do cadastro. Na migração (0013), diferente do proposto, as empresas e os funcionários existentes ficaram **sem data**, ou seja, desde a admissão como antes: assim nenhum espelho muda sozinho, e o superadmin escolhe a data. Mudar o início ou o saldo é recusado se afetar um mês fechado, e tudo vai para a auditoria. Testes em `tests/integration/test_saldo_inicial.py`.

### 3. Jornada diferente por dia da semana e escalas

**Hoje.** A jornada é uma só: minutos por dia e quais dias da semana (`daily_minutes` + `workdays`). Não dá para ter segunda a sexta com 8h e sábado com 4h, nem escala 12x36 ou 6x1 com folga que roda na semana. Essas jornadas, comuns em padaria, comércio e portaria, geram faltas e saldos errados.

**Proposta.**
- Jornada com minutos **por dia da semana** (ex.: seg–sex 8h, sáb 4h), mantendo a vigência por data como hoje.
- Escalas cíclicas: um padrão (ex.: 12h trabalhando, 36h de folga) e a data de início do ciclo; o sistema calcula quais dias são de trabalho.
- O formulário de funcionário oferece os modelos mais comuns (5x2, 6x1, 12x36) e mostra a prévia das próximas duas semanas.

### 4. Horas extras separadas em 50% e 100%

**Hoje.** O saldo do dia é um número só. Para a folha, a contabilidade precisa separar as horas extras comuns (adicional mínimo de 50%) das feitas em domingo e feriado não compensados (normalmente 100%), além das horas noturnas, que já são separadas. Hoje isso é feito à mão a partir do espelho.

**Proposta.**
- No espelho e no resumo do mês: colunas **extras 50%**, **extras 100%**, **noturnas** e **faltas (horas)**, respeitando o banco de horas (o que foi para o banco não vira extra paga).
- Os percentuais e quais dias contam 100% ficam nas regras de jornada da empresa, com vigência, como as demais regras (convenção coletiva diferente por empresa).
- O CSV do resumo ganha essas colunas, na ordem que a contabilidade usa.

---

## 🟠 Prioridade média

### 5. Funcionário vê o resultado das solicitações no app

**Hoje.** Uma batida esquecida, correção ou exclusão pedida pelo app vira solicitação, e o admin aprova ou recusa no painel. O app não fica sabendo do resultado: o funcionário só descobre pela batida aparecendo (ou não) no resumo, e nunca vê o motivo da recusa.

**Proposta.** Uma rota `GET /api/pontos/solicitacoes` com as solicitações do próprio funcionário (pendente, aprovada, recusada, motivo), e uma lista no app com o estado de cada uma. Os ajustes pendentes que o app guarda passam a mostrar "aprovado" ou "recusado: motivo".

### 6. Aviso por e-mail quando o backup ou o sistema falha

**Hoje.** O `backup.sh` registra erros só em `backups/backup.log`. Se a chave pública sumir, o disco encher ou o Postgres parar, o backup falha todo dia sem ninguém ver. O mesmo vale para o backend fora do ar.

**Proposta.** Reaproveitar o SMTP do aviso de solicitações (`SMTP_*` no `.env`): o `backup.sh` manda um e-mail ao superadmin (`ALERTA_EMAIL`) quando falha ou quando a cópia remota não sai, e um script no cron confere `/api/health` a cada 5 minutos e avisa na primeira falha e na volta. Sem SMTP configurado, segue só o log.

### 7. Teste de restauração do backup

**Hoje.** Cada backup é conferido com `pg_restore --list`, que só prova que o arquivo é legível. Nunca se restaura um backup de verdade, então um dump incompleto ou uma chave privada perdida só seriam descobertos no dia em que fizessem falta.

**Proposta.** Um `scripts/testar-restauracao.sh`, rodado uma vez por mês: decifra o backup mais recente num chaveiro temporário, restaura num Postgres descartável (container), compara a contagem de linhas das tabelas principais com o banco atual e registra o resultado (e avisa por e-mail se falhar, ver item 6). Exige a chave privada à mão, então pode ficar como passo manual com lembrete.

### 8. Limite de tamanho dos logs do Docker

**Hoje.** Os containers usam o driver `json-file` sem limite (o `daemon.json` do servidor só define DNS). Os logs do backend e do nginx crescem para sempre e, com o tempo, podem encher o disco, levando junto o banco e os backups.

**Proposta.** No `docker-compose.yml`, `logging: { driver: json-file, options: { max-size: "10m", max-file: "5" } }` nos dois serviços. Uma linha cada, sem mudança de comportamento.

### 9. Teste das páginas no navegador, no deploy e no CI

**Hoje.** Os 82 testes cobrem só o backend. As páginas (painel, relógio, login) não têm teste: um erro de JavaScript só aparece quando alguém abre a tela. Na rodada anterior, o problema dos botões saindo do cartão no celular só foi visto com capturas feitas à mão.

**Proposta.** Testes com Playwright contra a pilha completa (Postgres, backend e nginx em containers descartáveis, com dados de exemplo): login, abrir cada aba, cadastrar funcionário, bater ponto no relógio, aprovar solicitação, nenhum erro no console, e capturas em largura de computador e de celular, nos temas claro e escuro. Roda no `deploy.sh` e no GitHub Actions.

### 10. Administrador só de consulta (contabilidade)

**Hoje.** Todo admin de uma empresa pode tudo: corrigir batidas, fechar o mês, criar admins, desligar relógios. Para dar acesso ao contador ou ao dono que só quer conferir, é preciso dar acesso total.

**Proposta.** Um papel **consulta** no cadastro de administradores: vê o espelho, o resumo, os CSVs e a auditoria, mas não altera nada (as rotas de escrita recusam com 403, conferido no backend e não só escondendo botões). O que ele exporta vai para a auditoria.

---

## 🟡 Prioridade baixa

### 11. Feriados que se repetem todo ano

**Hoje.** Os nacionais são calculados sozinhos, mas os municipais e estaduais (aniversário da cidade, padroeiro) precisam ser cadastrados de novo a cada ano. Se alguém esquecer, o dia vira falta.

**Proposta.** Uma opção **repete todo ano** no cadastro do feriado (mesmo dia e mês) e um botão "copiar os feriados de AAAA" para os móveis. O painel avisa em dezembro se o ano seguinte ainda não tem nenhum feriado da empresa.

### 12. Prorrogação do horário noturno

**Hoje.** Está nos limites conhecidos do `web/README.md`: quem trabalha a noite toda e continua depois das 5h não tem as horas seguintes contadas como noturnas. A Súmula 60 do TST manda prorrogar o adicional nesses casos.

**Proposta.** Uma opção nas regras de jornada da empresa (ligada por padrão para o urbano): quando a jornada cumpre todo o horário noturno, as horas seguintes também contam como noturnas, com hora reduzida. Vale por vigência e não recalcula meses fechados.

### 13. Dividir o `admin.js` em módulos

**Hoje.** O `admin.js` tem mais de 1100 linhas com todas as abas do painel num arquivo só. Cada mudança mexe no mesmo arquivo, e é fácil uma parte quebrar outra.

**Proposta.** Módulos ES nativos (`<script type="module">`, aceito pela CSP `script-src 'self'`), um por aba (`js/admin/funcionarios.js`, `espelho.js`...) e um com o que é comum (`api`, `ask`, `toast`). Sem bundler nem etapa de build. Fica mais fácil depois de existir o item 9, que confere que nada quebrou.

---

## Já registrados em outros documentos

- Cópia dos backups fora do servidor (`BACKUP_REMOTO`): `SEGURANCA.md`, item 4.
- Atualizar o Expo SDK do app: `SEGURANCA.md`, item 13.
- Arquivos AFD/AEJ da Portaria 671, se o sistema precisar valer como registro oficial: limites conhecidos no `web/README.md`.

## Configuração pendente (não são melhorias de código)

- Preencher `SMTP_*` e `PAINEL_URL` no `.env` e o e-mail de avisos de cada empresa, para o aviso de solicitações funcionar.
- Preencher o contato de privacidade de cada empresa no cadastro (`SEGURANCA.md`, item 15).

## Checklist

- [ ] 1. Ausências justificadas (atestado, férias, folga)
- [x] 2. Início do controle e saldo inicial do banco de horas
- [ ] 3. Jornada diferente por dia da semana e escalas
- [ ] 4. Horas extras separadas em 50% e 100%
- [ ] 5. Funcionário vê o resultado das solicitações no app
- [ ] 6. Aviso por e-mail quando o backup ou o sistema falha
- [ ] 7. Teste de restauração do backup
- [ ] 8. Limite de tamanho dos logs do Docker
- [ ] 9. Teste das páginas no navegador, no deploy e no CI
- [ ] 10. Administrador só de consulta (contabilidade)
- [ ] 11. Feriados que se repetem todo ano
- [ ] 12. Prorrogação do horário noturno
- [ ] 13. Dividir o `admin.js` em módulos
