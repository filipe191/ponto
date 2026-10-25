# Melhorias propostas

Levantamento feito em 24/10/2026, depois da mudança para várias empresas no mesmo servidor. Cada item traz a situação atual e a proposta, em ordem de prioridade. Os pontos de segurança ficam em `SEGURANCA.md`.

## Resumo

| # | Item | Prioridade | Esforço | Onde | Status |
|---|------|-----------|---------|------|--------|
| 1 | Regras de jornada por empresa | Alta | Médio | Backend + painel | ✅ Concluído |
| 2 | Auditoria própria do superadmin | Alta | Pequeno | Backend + painel | ✅ Concluído |
| 3 | Segundo superadmin | Alta | Pequeno | Backend + painel | ✅ Concluído |
| 4 | Testes de ponta a ponta e CI | Alta | Médio | `web/backend/tests/` + GitHub Actions | ✅ Concluído |
| 5 | Painel em abas | Alta | Médio | Frontend | ✅ Concluído |
| 6 | Tabelas que viram cartões no celular | Alta | Pequeno | Frontend | ✅ Concluído |
| 7 | Link do aviso de privacidade por empresa | Média | Pequeno | Backend + frontend | ✅ Concluído |
| 8 | Bloqueios de tentativas guardados no banco | Média | Pequeno | Backend | ✅ Concluído |
| 9 | Aviso de solicitações pendentes | Média | Médio | Backend | ✅ Concluído |
| 10 | Confirmações do relógio com o visual do sistema | Média | Pequeno | Relógio | ✅ Concluído |
| 11 | Confirmação visual depois de salvar | Baixa | Pequeno | Painel | ✅ Concluído |
| 12 | Busca de funcionários | Baixa | Pequeno | Painel | ✅ Concluído |
| 13 | Tema escuro no painel | Baixa | Pequeno | Frontend | ✅ Concluído |
| 14 | Relógio instalável no tablet | Baixa | Pequeno | Relógio | Pendente |

Para começar, a melhor relação entre esforço e resultado está nos itens 1, 2, 4, 5 e 6.

---

## 🔴 Prioridade alta

### 1. Regras de jornada por empresa

**Hoje.** Tolerância diária (10 min), horário noturno (22h–5h, hora de 52min30s), jornada máxima (16 h), prazo das batidas sem conexão e fuso horário ficam no `.env` (`app/core/config.py`) e valem para todas as empresas.

**Problema.** Empresas diferentes têm regras diferentes. O trabalho rural, por exemplo, tem horário noturno de 21h–5h (lavoura) ou 20h–4h (pecuária), com hora de 60 minutos (Lei 5.889/73). Uma empresa em outro estado pode ter outro fuso.

**Proposta.**
- Levar essas regras para o cadastro da empresa, com os valores atuais como padrão.
- O cálculo do espelho (`report_service.py`, `shifts.py`, `utils/dates.py`) passa a ler as regras da empresa do funcionário.
- No painel do superadmin, um bloco "Regras de jornada" na edição da empresa.
- Mudança de regra vale a partir de uma data, como as jornadas, para não recalcular meses já fechados.

**Status: concluído em 24/10/2026.** Tabela `company_rules` com vigência: tolerância, horário noturno, hora noturna e jornada máxima. Cada dia do espelho (e do banco de horas acumulado) usa a regra que valia nele. A nova regra não pode começar num mês já fechado. Fuso e prazo das batidas sem conexão ficaram no cadastro da empresa; o fuso só muda antes da primeira batida. No painel, o cartão **Regras de jornada** mostra as vigências a todos os admins da empresa, e o formulário (com atalhos urbano, lavoura e pecuária) só aparece para o superadmin. As empresas existentes receberam os valores do `.env`, valendo desde sempre: nenhum espelho mudou com a migração. Cada mudança vai para a auditoria da empresa.

### 2. Auditoria própria do superadmin

**Hoje.** As ações pessoais do superadmin (login, troca de senha, duas etapas) vão para a auditoria da empresa nº 1, porque essa é a "empresa dele", e os admins dela veem essas entradas. Numa instalação nova, em que o superadmin não pertence a nenhuma empresa, os registros ficam sem empresa e não aparecem em painel nenhum.

**Proposta.**
- Gravar as ações do superadmin fora de uma empresa sem empresa (`company_id` vazio), também quando ele tem empresa própria.
- Mostrar esses registros numa auditoria do sistema, dentro do cartão **Empresas**, com o cadastro e a desativação de empresas.
- O que ele faz dentro de uma empresa (corrigir batida, cadastrar funcionário) continua na auditoria da empresa.

**Status: concluído em 24/10/2026.** Login, senha, duas etapas e códigos de recuperação do superadmin vão para a auditoria do sistema (sem empresa), também quando ele tem empresa própria. Cadastro, alteração e desativação de empresas ficam nas duas auditorias: na do sistema (com o nome da empresa) e na da empresa. A auditoria do sistema aparece no cartão **Empresas**. Os registros antigos continuam onde estavam (a auditoria não aceita alterações).

### 3. Segundo superadmin

**Hoje.** Só existe um superadmin, e não há como criar outro pelo painel.

**Risco.** Se ele perder a senha, o celular com o autenticador e os códigos de recuperação, ninguém mais consegue cadastrar, editar ou desativar empresas. A única saída é mexer direto no banco.

**Proposta.** Em **Empresas**, uma lista de superadministradores, para cadastrar mais um (senha provisória e duas etapas, como os demais) e excluir, mantendo sempre pelo menos um.

**Status: concluído em 24/10/2026.** Em **Empresas → Superadministradores**: cadastrar (senha provisória e duas etapas, como os demais) e excluir, sem excluir a própria conta e mantendo pelo menos um. Os superadmins não podem ser excluídos pelo painel de uma empresa. Tudo vai para a auditoria do sistema.

### 4. Testes de ponta a ponta e CI

**Hoje.** Os testes do repositório (55) são unitários e não usam banco. O roteiro de ponta a ponta usado na mudança para várias empresas (52 verificações de isolamento entre empresas, migração e relógios antigos) não ficou no repositório. Também não há CI.

**Proposta.**
- Trazer o roteiro para `web/backend/tests/`, rodando contra um Postgres de teste (container).
- Incluir um teste de migração: banco na versão anterior → `alembic upgrade head`.
- GitHub Actions rodando os testes a cada push e pull request, junto com o `pip-audit`.

**Status: concluído em 24/10/2026.** `tests/integration/` tem 19 testes contra um Postgres de verdade: migração de um banco na versão 0007 com dados (empresa nº 1, superadmin, relógio antigo, auditoria imutável), isolamento entre empresas, relógios, empresa desativada, regras por empresa e superadmins. Eles só rodam com `PGDATABASE` contendo "test", porque apagam e recriam o banco. O `deploy.sh` roda todos os testes com um Postgres descartável, e o GitHub Actions (`.github/workflows/backend.yml`) roda os testes e o `pip-audit` a cada push. O primeiro teste já pegou um erro real na migração das regras (data gravada como texto), corrigido antes de qualquer deploy.

### 5. Painel em abas

**Hoje.** O `/admin` é uma página única e comprida, com uns 8 cartões em sequência: Empresas, Avisos, Solicitações, Funcionários, Espelho, Feriados, Administradores e relógios, Auditoria.

**Proposta.**
- Abas (ou menu lateral no computador): **Início** (avisos e solicitações), **Funcionários**, **Espelho**, **Configurações** (feriados, admins, relógios), **Auditoria** e, para o superadmin, **Empresas**.
- Guardar a aba aberta no endereço (`/admin#espelho`), para o voltar do navegador e os links funcionarem.
- Mostrar na aba Início a contagem de solicitações pendentes.

**Status: concluído em 25/10/2026.** Abas **Início** (avisos de segurança e solicitações, com a contagem das pendentes no título da aba), **Funcionários**, **Espelho**, **Configurações** (feriados, regras de jornada, administradores e relógios), **Auditoria** e, só para o superadmin, **Empresas**. A aba fica no endereço (`/admin#espelho`): o voltar do navegador e os links funcionam, e trocar de empresa mantém a aba. As setas do teclado passam de uma aba para a outra. Sem empresa aberta, o superadmin vê só a aba Empresas.

### 6. Tabelas que viram cartões no celular

**Hoje.** Em largura de celular, a coluna de botões das tabelas fica cortada (visto na tabela de empresas, e o mesmo acontece em funcionários, admins e feriados). É preciso rolar a tabela para os lados.

**Proposta.** Abaixo de ~600 px, cada linha vira um cartão com os dados empilhados e os botões embaixo. Só CSS, com os rótulos vindos de um `data-label` em cada célula.

**Status: concluído em 25/10/2026.** Até 640 px, as tabelas de empresas, superadmins, auditorias, solicitações, funcionários, feriados, regras e administradores viram cartões: o nome em destaque, os demais dados com o título da coluna em cima e os botões embaixo, sem rolagem para os lados. Os rótulos são preenchidos pelo script a partir do cabeçalho de cada tabela, também quando a lista é recarregada. O espelho continua em tabela (as colunas de noturno e prevista já somem no celular).

---

## 🟠 Prioridade média

### 7. Link do aviso de privacidade por empresa

**Hoje.** A página `/privacidade` descobre a empresa pelo relógio ou pelo admin logado no aparelho. No celular do funcionário, sem nenhum dos dois, ela mostra o texto genérico, sem o nome da empresa nem o contato.

**Proposta.** Um código público e aleatório por empresa (ex.: `/privacidade?e=k3f9x2`), mostrado no painel para o admin repassar aos funcionários. O código é aleatório para não permitir listar as empresas atendidas.

**Status: concluído em 25/10/2026.** Cada empresa tem um código aleatório (migração 0010, gerado também para as empresas existentes). O link aparece em Configurações → Administradores e relógios → **Aviso de privacidade**, com botão para copiar, e o superadmin também recebe o código na lista de empresas. O código só é entregue a admins: o relógio não o recebe. Código errado ou empresa desativada mostram o texto genérico. Testes de integração em `tests/integration/test_privacidade.py`.

### 8. Bloqueios de tentativas guardados no banco

**Hoje.** Os limites de PIN errado no relógio, de senha errada no login e de chave errada no app ficam na memória do backend (`core/ratelimit.py`). Reiniciar o backend zera os bloqueios em andamento, inclusive o bloqueio crescente de até 24 h do relógio.

**Proposta.** Guardar as tentativas numa tabela, com limpeza das antigas. O comportamento visto pelo usuário não muda.

**Status: concluído em 25/10/2026.** Tabelas `attempt_failures` (cada erro, por tipo e IP) e `attempt_blocks` (bloqueio crescente do relógio: quantos seguidos e até quando), na migração 0011. Os limites continuam os mesmos (PIN, login e chave do app). Cada limitador grava numa sessão própria, então o erro fica registrado mesmo quando a requisição é desfeita. Tentativas fora da janela e bloqueios esquecidos são apagados a cada novo erro. Os testes do limitador passaram para `tests/integration/test_tentativas.py`, com um teste de que o bloqueio continua depois de reiniciar.

### 9. Aviso de solicitações pendentes

**Hoje.** O admin só fica sabendo das solicitações feitas pelo app (batida esquecida, correção, exclusão) quando abre o painel.

**Proposta.** Um e-mail por empresa (endereço no cadastro) quando chega uma solicitação, ou um resumo diário. Exige configurar um servidor de e-mail (SMTP) no `.env`.

**Status: concluído em 25/10/2026.** No cadastro da empresa (Empresas, só o superadmin) há um **e-mail de avisos** (vários separados por vírgula; migração 0012). Quando o app cria uma solicitação (batida esquecida, correção ou exclusão), esse endereço recebe um e-mail com a quantidade pendente e o link do painel (`PAINEL_URL`). Para não lotar a caixa, vai no máximo um aviso por empresa a cada 30 minutos. O e-mail não traz nomes nem horários: os dados dos funcionários ficam só no painel. O envio é em segundo plano, então um servidor de e-mail fora do ar só gera um aviso no log. Sem `SMTP_HOST` no `.env`, nada é enviado. **Para ligar:** preencher `SMTP_*` e `PAINEL_URL` no `.env` e o e-mail de cada empresa no cadastro.

### 10. Confirmações do relógio com o visual do sistema

**Hoje.** A tela do relógio (`js/index.js`) usa `confirm()` e `alert()` do navegador para ligar e desligar o modo relógio. Elas destoam do resto e ficam ruins no tablet.

**Proposta.** Reaproveitar a janela de confirmação que o painel já tem (`<dialog>` com título, mensagem e botões).

**Status: concluído em 25/10/2026.** Ligar e desligar o modo relógio e o aviso de "nenhuma empresa aberta" usam uma janela `<dialog>` com título, mensagem e botões no estilo das teclas do relógio (grandes, para o toque no tablet), como a janela do espelho. O foco começa em Cancelar, para um Enter sem querer não confirmar, e o teclado do PIN fica parado enquanto a janela está aberta. Não sobrou nenhum `confirm()` ou `alert()` nas páginas.

---

## 🟡 Prioridade baixa

### 11. Confirmação visual depois de salvar

**Hoje.** O painel só mostra mensagem quando dá erro. Ao salvar um funcionário, lançar uma batida ou fechar um mês, a tela apenas se atualiza.

**Proposta.** Uma mensagem curta no canto da tela ("Funcionário salvo", "Mês fechado"), que some sozinha.

**Status: concluído em 25/10/2026.** Toda gravação bem-sucedida do painel mostra uma mensagem curta no canto inferior direito, que some em 2,5 s: funcionários, batidas (lançar, corrigir, excluir, restaurar), fechamento e reabertura do mês, feriados, regras e configurações, administradores, celulares, solicitações, empresas e superadministradores. A mensagem é um `popover`, para aparecer até por cima de uma janela aberta, e é anunciada pelos leitores de tela (`role="status"`). Os erros continuam aparecendo junto do formulário.

### 12. Busca de funcionários

**Hoje.** A lista de funcionários e os seletores do espelho e da auditoria mostram todos os nomes, sem busca.

**Proposta.** Um campo de busca acima da lista e no seletor do espelho, com filtro de ativos e inativos. Fica importante quando a empresa passa de umas 20 pessoas.

**Status: concluído em 25/10/2026.** A aba Funcionários tem busca pelo nome e o filtro **Ativos / Inativos / Todos** (abre em Ativos), com a contagem "N de M" quando há filtro. O espelho tem uma busca ao lado do seletor: a lista mostra só os nomes que batem e, se o funcionário aberto sair da lista, o primeiro encontrado é aberto. A busca ignora maiúsculas e acentos ("joao" acha "João"). Tudo no navegador, sem mudança na API.

### 13. Tema escuro no painel

**Hoje.** O `style.css` tem só uma regra para o tema escuro do sistema e o `admin.css` nenhuma.

**Proposta.** Redefinir as cores (que já estão em variáveis) para o tema escuro com `prefers-color-scheme: dark`, conferindo o contraste do espelho e das marcas de batida.

**Status: concluído em 25/10/2026.** O `style.css` já trocava todas as cores no tema escuro e o painel as usa, então a maior parte já funcionava. Conferido no navegador (claro e escuro, computador e celular), sobraram quatro problemas, corrigidos com tokens novos: campos de data, seletores e caixas de marcar continuavam claros (agora `color-scheme` segue o tema); o botão principal (Aprovar, Lançar, Salvar) quase sumia no cartão escuro (no escuro vira azul claro); o número nos selos vermelhos e o texto do botão de excluir eram brancos sobre rosa (agora escuros no tema escuro). As marcas de batida e os saldos do espelho já tinham contraste bom. O tema claro não mudou.

### 14. Relógio instalável no tablet

**Hoje.** O relógio abre no navegador, com a barra de endereço visível.

**Proposta.** Um `manifest` com ícone e `display: standalone`, para o tablet instalar o relógio como um app e abrir em tela cheia. As batidas sem conexão já ficam guardadas no aparelho, então não é preciso um service worker para isso.

---

## Já registrados em outros documentos

- Cópia dos backups fora do servidor (`BACKUP_REMOTO`): `SEGURANCA.md`, item 4.
- Atualizar o Expo SDK do app: `SEGURANCA.md`, item 13.
- Arquivos AFD/AEJ da Portaria 671, se o sistema precisar valer como registro oficial: limites conhecidos no `web/README.md`.

## Checklist

- [x] 1. Regras de jornada por empresa
- [x] 2. Auditoria própria do superadmin
- [x] 3. Segundo superadmin
- [x] 4. Testes de ponta a ponta no repositório e CI
- [x] 5. Painel em abas
- [x] 6. Tabelas que viram cartões no celular
- [x] 7. Link do aviso de privacidade por empresa
- [x] 8. Bloqueios de tentativas guardados no banco
- [x] 9. Aviso de solicitações pendentes
- [x] 10. Confirmações do relógio com o visual do sistema
- [x] 11. Confirmação visual depois de salvar
- [x] 12. Busca de funcionários
- [x] 13. Tema escuro no painel
- [ ] 14. Relógio instalável no tablet
