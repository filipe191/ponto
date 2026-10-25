# Ponto

Sistema de registro de ponto: relógio em tablet, painel de administração e app de celular, atendendo várias empresas no mesmo servidor.

- `web/backend/`: API em FastAPI + PostgreSQL (SQLAlchemy, migrações Alembic em `app/db/migrations/versions/`, aplicadas na subida do backend).
- `web/frontend/`: nginx servindo páginas estáticas (`public/*.html`, scripts em `public/js/`, CSP `script-src 'self'`, sem scripts inline). O painel é dividido em módulos ES por aba (`public/js/admin/`), sem build.
- `app/`: app de celular (Expo).
- Documento de acompanhamento: `SEGURANCA.md` (segurança). Ao concluir um item, atualize o status e o checklist do documento. As duas rodadas de melhorias (`MELHORIAS.md`, 14 itens, e `MELHORIAS-2.md`, 13 itens, todas concluídas em 24 e 25/10/2026) foram apagadas e continuam no histórico do git.

## Convenções

- Textos, mensagens de erro, comentários e commits em português.
- Várias empresas: todo dado de funcionário, feriado, admin, relógio, celular e auditoria pertence a uma empresa. Repositórios e serviços recebem `company_id`, e toda busca por id confere a empresa antes de devolver ou alterar. Rotas do painel usam `CompanyAdmin`, as do superadmin usam `SuperAdmin` e as do relógio usam `ClockCompany` (`app/api/deps.py`).
- A auditoria (`audit_log`) só aceita inclusões; o banco recusa UPDATE e DELETE.
- Regras de jornada mudam por vigência (`company_rules`): nunca recalcule o passado.

## Testes

Comandos em `web/README.md` → Desenvolvimento. Os testes de integração (`tests/integration/`) precisam de um Postgres descartável, com `PGDATABASE` contendo `test` (eles apagam e recriam o banco); sem isso são pulados. Nunca aponte esses testes para o banco de produção. As páginas têm testes no navegador (`web/e2e/rodar.sh`, Playwright, pilha descartável); mudou uma tela, rode-os e olhe as capturas em `web/e2e/resultados/`.

## Depois de terminar qualquer atualização

Sempre, ao concluir uma mudança no código (com os testes passando):

1. **Atualizar o Docker:** `cd web && scripts/deploy.sh`. O script confere o `.env`, roda os testes, audita as dependências, faz backup do banco e sobe os containers. Se ele falhar, não force: corrija e rode de novo, e avise o que aconteceu.
2. **Atualizar o graphify:** rode `/graphify . --update` na raiz do projeto (grafo em `graphify-out/`, fora do git).
3. **Commit e push:** um commit para cada funcionalidade (não junte funcionalidades diferentes num commit só), com mensagem em português no estilo dos anteriores (título curto e lista do que mudou). Quando um arquivo tiver mudanças de mais de uma funcionalidade, separe as partes entre os commits. Depois, `git push` para o `origin`.
