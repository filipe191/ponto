# Melhorias de segurança e proteção de dados

Levantamento feito em 24/10/2026 sobre o sistema de ponto (`web/` e `app/`) e o servidor onde ele roda. Cada item traz o problema, o risco e a correção proposta, em ordem de prioridade.

O sistema guarda dados pessoais de funcionários (nome, horários de trabalho, faltas, banco de horas), então a LGPD se aplica.

## Como foi levantado

- Revisão do código do backend, das páginas e do app.
- Conferência no servidor: portas abertas, permissões de arquivos, serviços no mesmo IP.
- Varredura das páginas atrás de dados de usuário inseridos no HTML sem escape (XSS).

## O que já está bom

- Nenhum XSS encontrado: todo dado de usuário passa por `esc()` ou `textContent`.
- Senhas com scrypt, PINs com HMAC e chave própria (`PIN_KEY`), chaves de celular guardadas só como hash.
- Cookies `HttpOnly` e `Secure`, sessão do relógio separada da do admin.
- Limite de tentativas no login, no PIN e na chave do app.
- Permissões corretas: `.env` e chaves com `600`, pasta de backups com `700`.
- Backend roda sem root, documentação da API desligada, versão do nginx oculta.
- Batidas nunca são apagadas de verdade e toda correção fica no histórico.

## Resumo

| # | Item | Prioridade | Esforço | Onde | Status |
|---|------|-----------|---------|------|--------|
| 1 | CA local sem restrição de nomes | Alta | Pequeno | `web/scripts/gerar-certificado.sh` | ✅ Concluído |
| 2 | Postgres aberto na rede do Tailscale | Alta | Pequeno | Servidor (Postgres compartilhado) | Risco aceito |
| 3 | Sem firewall no servidor | Alta | Pequeno | Servidor | ✅ Concluído |
| 4 | Backups sem criptografia e no mesmo disco | Alta | Médio | `web/scripts/backup.sh` | ✅ Criptografia · cópia remota aguarda o servidor de backup |
| 5 | Cookie de admin enviado a outros serviços do mesmo IP / CSRF | Média | Pequeno | Backend + nginx | ✅ Concluído |
| 6 | Sair não invalida a sessão | Média | Médio | Backend | ✅ Concluído |
| 7 | Login de admin fraco | Média | Médio | Backend + painel | ✅ Concluído |
| 8 | Auditoria incompleta | Média | Médio | Backend | ✅ Concluído |
| 9 | PIN de 4 dígitos | Média | Pequeno | Backend + relógio | ✅ Concluído |
| 10 | Cartão de hoje expõe todos os colegas | Média | Pequeno | Relógio | ✅ Concluído |
| 11 | Fórmulas no CSV | Baixa | Pequeno | Backend | ✅ Concluído |
| 12 | Scripts dentro das páginas (CSP fraco) | Baixa | Médio | Frontend | ✅ Concluído |
| 13 | Dependências sem checagem de vulnerabilidades | Baixa | Pequeno | `web/scripts/deploy.sh` | ✅ Concluído |
| 14 | Chaves de celular não expiram | Baixa | Pequeno | Backend | ✅ Concluído |
| 15 | Processo de LGPD | Baixa | Médio | Documentação | ✅ Concluído · empresa e contato no cadastro de cada empresa |

Os itens 2 e 3 mexem em infraestrutura compartilhada com outros sistemas do servidor. Combine antes de aplicar.

---

## 🔴 Prioridade alta

### 1. A CA local pode interceptar qualquer site nos aparelhos dos funcionários

**Problema.** Para o HTTPS funcionar na rede local, cada tablet e celular instala a CA criada por `gerar-certificado.sh`. Essa CA não tem restrição de nomes, então o aparelho passa a confiar nela para **todos** os domínios. A chave da CA (`web/certs/ca.key`) fica no próprio servidor.

**Risco.** Quem obtiver `ca.key` consegue emitir certificados válidos para qualquer site (banco, e-mail, redes sociais) e interceptar o tráfego dos aparelhos que instalaram a CA. São aparelhos pessoais de funcionários: o vazamento seria de dados que nem pertencem ao sistema de ponto.

**Correção.**
- Recriar a CA com a extensão *name constraints* (crítica), permitindo só os IPs e nomes deste servidor. Assim, mesmo com a chave em mãos, não dá para se passar por outros sites.
- Depois de emitir o certificado do servidor, tirar `ca.key` do servidor (pendrive ou gerenciador de senhas) e só trazer de volta para renovar.

**Observação.** Todos os aparelhos precisam remover a CA antiga e instalar a nova.

**Status: concluído em 24/10/2026.** A CA nova foi gerada com restrição de nomes e chave cifrada. Detalhes da implementação: O `gerar-certificado.sh` agora:
- cria a CA com *name constraints* críticas (sub-rede local, IPs e nome do Tailscale, nomes do servidor);
- cifra `ca.key` com uma senha de no mínimo 12 caracteres, pedida ao criar a CA e ao renovar;
- recusa uma CA antiga sem restrição e oferece `--nova-ca`, que apaga a antiga com `shred`;
- renova o certificado do servidor sem quebrar o nginx se algo falhar (ex.: senha errada).

O `deploy.sh` também recusa subir com uma CA sem restrição. Testado: certificados para `google.com` e `8.8.8.8` assinados pela CA nova são recusados (*permitted subtree violation*).

Para trocar a CA no futuro: `cd ~/ponto/web && scripts/gerar-certificado.sh --nova-ca` (pede uma senha nova; todos os aparelhos precisam reinstalar a CA).

### 2. Postgres aberto na rede do Tailscale

**Problema.** O Postgres compartilhado (`postgres_db`) escuta no IP do Tailscale do servidor, na porta 5432.

**Risco.** Qualquer máquina da tailnet pode tentar se conectar ao banco, que guarda o ponto e os dados dos outros sistemas do servidor. Basta uma senha vazada ou fraca.

**Correção.** Deixar o Postgres acessível só pela rede Docker (`postgres_pg_network`) ou pelo localhost. Se o acesso pelo Tailscale for necessário, restringir com ACL do Tailscale a máquinas específicas.

**Observação.** Esse Postgres não é deste projeto. Confira se algum outro sistema depende do acesso pelo Tailscale antes de fechar.

**Status: risco aceito em 24/10/2026.** O acesso pelo Tailscale foi mantido de propósito: a tailnet tem um único dono, todos os aparelhos são dele e há travas (ACLs) configuradas no Tailscale. Se um dia a tailnet for compartilhada, ou se um dos servidores nela ficar exposto à internet, reavalie: restrinja a porta 5432 nas ACLs a um só aparelho ou remova a publicação no IP do Tailscale como descrito abaixo.

Levantamento feito antes da decisão: O container `postgres_db` é uma stack do Portainer e publica a porta 5432 em dois endereços: o IP do Tailscale e `172.17.0.1` (a ponte do Docker). Nenhum container usa o endereço do Tailscale:
- o carro-manutencao conecta por `host.docker.internal`, ou seja, `172.17.0.1`, que **precisa continuar**;
- o ponto usa a rede Docker `postgres_pg_network`;
- o graminas tem banco próprio.

Só um acesso de fora (ex.: DBeaver num notebook pela tailnet) dependeria do endereço do Tailscale. Para isso, prefira um túnel SSH (`ssh -L 5432:172.17.0.1:5432 servidor`).

Como aplicar (a stack é do Portainer, então a mudança precisa ser feita lá, senão o Portainer a desfaz):

1. No Portainer, abra **Stacks** e a stack do `postgres_db`, depois **Editor**.
2. Em `ports`, apague a linha que publica no IP do Tailscale (`<ip-do-tailscale>:5432:5432`) e mantenha a de `172.17.0.1:5432:5432`.
3. Clique em **Update the stack**. O Postgres reinicia: o ponto e o carro-manutencao ficam alguns segundos sem banco.
4. Confira no servidor: `ss -ltn | grep 5432` deve mostrar só `172.17.0.1:5432`.

### 3. Sem firewall no servidor

**Problema.** Não há firewall ativo visível, e as portas do ponto (9092 e 9443) escutam em todas as interfaces.

**Risco.** Se o roteador repassar alguma porta para o servidor, de propósito ou por engano (UPnP), o sistema fica exposto na internet.

**Correção.** Ativar um firewall (ex.: `ufw`) liberando as portas do ponto só para a rede local e para a interface do Tailscale.

**Status: concluído em 24/10/2026.** O serviço `ponto-firewall` está instalado e ativo. Detalhes da implementação: Um `ufw` comum não resolveria: o Docker publica as portas por fora dele. O novo `web/scripts/firewall.sh` coloca as regras na cadeia `DOCKER-USER`, que o Docker consulta antes de entregar o tráfego aos containers:
- as portas do ponto (9092 e 9443) só aceitam a rede local e o Tailscale (`100.64.0.0/10`);
- o serviço systemd `ponto-firewall` reaplica as regras a cada boot e a cada reinício do Docker;
- o ponto passa a publicar as portas só em IPv4, que é o que o firewall filtra.

Testado numa simulação com redirecionamento de porta igual ao do Docker: a rede local e o Tailscale entram, a internet é bloqueada nas portas do ponto e as outras portas não são afetadas.

Para conferir: `sudo scripts/firewall.sh status` (mostra as regras e quantos pacotes foram bloqueados).

Fora do escopo do ponto: os demais serviços do servidor (Portainer, Grafana, Vaultwarden, Pi-hole etc.) continuam sem esse filtro. Vale aplicar a mesma ideia a eles.

### 4. Backups sem criptografia e no mesmo disco

**Problema.** `backup.sh` gera dumps em texto aberto dentro do próprio servidor.

**Risco.**
- **Vazamento:** o dump contém todos os dados pessoais e os hashes de senhas e de chaves. Uma cópia perdida ou um acesso indevido ao disco expõe tudo.
- **Perda:** se o disco falhar, perdem-se o banco e os backups juntos, incluindo registros que precisam ser guardados por 5 anos.

**Correção.**
- Criptografar cada dump com `age` (ou `gpg`), usando uma chave pública. A chave privada fica fora do servidor.
- Enviar uma cópia para fora do servidor (outro computador, HD externo ou nuvem) após cada backup.
- Testar a restauração periodicamente (por exemplo, uma vez por mês).

---

**Status: criptografia concluída em 24/10/2026; cópia fora do servidor adiada.** O destino será um servidor de backup próprio, ainda não montado. Quando ele estiver no ar, defina `BACKUP_REMOTO`.
- Cada dump é cifrado com `gpg` usando a chave pública `web/backups/chave-publica.asc`; só a chave privada, fora do servidor, decifra.
- O dump em texto aberto só existe na memória (`/dev/shm`) durante a conferência e é apagado em seguida.
- Os backups antigos em texto aberto foram cifrados e destruídos com `shred`.
- A cópia remota já está pronta no `backup.sh`: basta definir `BACKUP_REMOTO` no `.env` com um destino do `rsync`. Até lá, o log avisa a cada execução.
- Testado: com a chave privada o backup decifra e restaura; sem ela, recusa (*No secret key*).

**Pendente com você:** guardar `~/ponto-backup-chave-privada.asc` fora do servidor (ex.: Vaultwarden) e apagá-la com `shred -u ~/ponto-backup-chave-privada.asc`.

## 🟠 Prioridade média

### 5. Cookie de admin enviado a outros serviços do mesmo IP (e CSRF)

**Problema.** Cookies não são separados por porta. Há outros serviços HTTPS no mesmo IP do servidor (portas 9090 e 10000, provavelmente painéis de administração do sistema), e o navegador envia o cookie de sessão do admin para eles também. Pelo mesmo motivo, esses serviços contam como "mesmo site", então a proteção `SameSite` não barra pedidos forjados vindos deles.

**Risco.** Uma falha em qualquer outro serviço do servidor pode ser usada para agir como o admin do ponto (CSRF) ou capturar o cookie.

**Correção.**
- No backend, recusar todo `POST`, `PATCH` e `DELETE` cujo cabeçalho `Origin` não seja o do próprio ponto (o app de celular não manda `Origin` e usa chave própria, então não é afetado).
- Se possível, acessar o ponto por um nome próprio (ex.: `ponto.local`) em vez do IP, o que isola os cookies dos outros serviços.

**Status: concluído em 24/10/2026.** O backend recusa POST, PUT, PATCH e DELETE com cookie de sessão cujo `Origin` não seja o próprio ponto (mesma origem, em HTTPS), e também os que chegam sem `Origin` (navegadores sempre o enviam). O app de celular não usa cookie e não é afetado. O nginx passou a repassar a porta no `Host` para a comparação. Testado: requisições de outra porta do mesmo IP, em HTTP ou sem `Origin` são recusadas.

O nome próprio (ex.: `ponto.local`) ficou como melhoria opcional: exige um registro no Pi-hole e um certificado novo (com a senha da CA). Com a checagem de `Origin`, o CSRF já está barrado; o nome próprio só evitaria o envio do cookie aos outros serviços.

### 6. Sair não invalida a sessão

**Problema.** A sessão do admin é um token assinado guardado só no cookie. "Sair" apaga o cookie no navegador, mas o token continua válido.

**Risco.** Um cookie copiado (de um computador compartilhado, por exemplo) segue funcionando por até 30 dias.

**Correção.**
- Guardar as sessões no banco, para que sair invalide o token.
- Adicionar "sair de todos os aparelhos" na tela de senha.
- Encerrar a sessão após algumas horas sem uso.

**Status: concluído em 24/10/2026.**
- A sessão do admin agora é um token aleatório com o hash guardado no banco (`admin_sessions`).
- Sair, trocar a senha, ativar o relógio ou excluir o admin invalidam a sessão na hora.
- A sessão cai sozinha após 8 horas sem uso e dura no máximo 30 dias.
- Em **Conta e segurança** (`/senha`): lista dos aparelhos conectados, encerrar um aparelho e "sair de todos os outros".

Testado: um cookie copiado deixa de valer após sair.

### 7. Login de admin fraco

**Problema.** A senha mínima tem 6 caracteres e não há segundo fator.

**Risco.** O admin vê e altera o ponto de todos os funcionários. Uma senha fraca ou reaproveitada de outro serviço basta para o acesso.

**Correção.**
- Exigir no mínimo 12 caracteres e recusar senhas muito comuns.
- Adicionar segundo fator por código no celular (TOTP, ex.: Google Authenticator), obrigatório para todos os admins.

**Status: concluído em 24/10/2026.**
- **Senha:** mínimo de 12 caracteres, sem senhas comuns, sem só números, sem o nome de usuário. Senha provisória (a do `.env` ou a criada por outro admin) ou fora da política obriga a troca antes de usar o painel.
- **Duas etapas obrigatória:** código TOTP de app autenticador, cadastrado por QR code. Os segredos ficam cifrados no banco (com a `PIN_KEY`); um código não pode ser reaproveitado; há 10 códigos de recuperação de uso único (só o hash fica no banco).
- Erros de código contam no limite de tentativas do login.
- Para desligar a obrigatoriedade: `ADMIN_2FA_REQUIRED=false`.
- Testado com o vetor oficial da RFC 6238 e no fluxo completo.

**No primeiro acesso depois do deploy, cada admin vai precisar trocar a senha (se for fraca) e cadastrar o app autenticador.**

### 8. Auditoria incompleta

**Problema.** Só as correções de batida ficam no histórico. Não deixam rastro:

- troca de PIN, mudança de jornada, admissão e desligamento;
- ativação e desativação de funcionários;
- criação e exclusão de administradores;
- geração e revogação de chaves de celular;
- "desligar todos os relógios";
- cadastro e remoção de feriados;
- fechamento e reabertura de mês.

Além disso, **reabrir um mês apaga o registro de fechamento junto com a ciência do funcionário**, que é justamente a prova de que ele conferiu o espelho.

**Risco.** Não há como saber quem mudou a jornada de alguém (o que altera o banco de horas) ou quem trocou um PIN. Em uma disputa trabalhista, a ciência dada pode desaparecer.

**Correção.**
- Criar uma tabela de auditoria geral (quem, quando, o quê, valor antes e depois) para todas as ações acima.
- Ao reabrir o mês, manter o fechamento e a ciência anteriores no histórico em vez de apagá-los.

**Status: concluído em 24/10/2026.**
- Nova tabela `audit_log` com quem, quando, o quê, antes e depois (e o IP, nos eventos do relógio e de login).
- Registra: cadastro, alteração, ativação, desativação e exclusão de funcionários; troca de PIN (sem o PIN); mudança de jornada; feriados; chaves de celular; criação e exclusão de admins; login e tentativas erradas em contas existentes; troca de senha e duas etapas; liberação e desligamento de relógios; fechamento, ciência e reabertura de mês; bloqueio do relógio por PINs errados.
- O registro entra na mesma transação da ação. O banco recusa `UPDATE`, `DELETE` e `TRUNCATE` na tabela (trigger), então nem um defeito do sistema apaga o histórico.
- Reabrir o mês exige motivo. O fechamento e a ciência anteriores ficam na auditoria e aparecem no espelho do painel ("Fechado por… · ciência em… · reaberto por… · motivo").
- No painel: seção **Auditoria**, com filtro por funcionário e por tipo de ação.

Testado na cópia do banco de produção, inclusive a recusa de alteração direta no banco.

### 9. PIN de 4 dígitos

**Problema.** O PIN aceita 4 dígitos. O limite atual permite 10 erros a cada 5 minutos por aparelho, ou seja, cerca de 2.900 tentativas por dia.

**Risco.** Com vários funcionários cadastrados, as chances de acertar o PIN de alguém em poucos dias são reais. Quem acertar pode bater o ponto pela pessoa e abrir o espelho dela em "Ver meu espelho" (horários, faltas, banco de horas), o que é vazamento de dados de outra pessoa.

**Correção.**
- Exigir no mínimo 6 dígitos nos PINs novos e pedir a troca dos atuais.
- Aumentar o tempo de bloqueio a cada nova rodada de erros no mesmo aparelho.
- Avisar o admin quando um relógio for bloqueado por excesso de PINs errados.

**Status: concluído em 24/10/2026.**
- PINs novos e trocados precisam ter de 6 a 8 dígitos. O cadastro ganhou o botão **Gerar PIN** (aleatório).
- Os PINs atuais de 4 ou 5 dígitos **continuam valendo**. A migração os identifica, o painel marca "PIN curto" e mostra um aviso, e o relógio pede ao funcionário que procure o admin. Ao trocar o PIN, a marca some.
- Bloqueio crescente no relógio: 10 erros em 5 minutos pausam o aparelho por 5 minutos; cada nova rodada dobra a pausa (10, 20, 40 minutos…, até 24 horas). A contagem zera depois de 24 horas sem bloqueio. Vale para bater o ponto e para "Ver meu espelho".
- Cada bloqueio vai para a auditoria e aparece em **Avisos de segurança**, na aba Início do painel, por 24 horas.
- O controle de tentativas fica no banco (tabelas `attempt_failures` e `attempt_blocks`, desde 25/10/2026): reiniciar o backend não zera os bloqueios em andamento.

### 10. O "Cartão de hoje" expõe todos os colegas

**Problema.** A tela do relógio mostra o nome e os horários de todos que bateram ponto no dia, para qualquer pessoa diante do tablet.

**Risco.** Pela LGPD, os dados devem ser limitados ao necessário. Colegas e visitantes não precisam ver os horários uns dos outros.

**Correção.** Escolher uma das opções:
- mostrar só a batida da própria pessoa, por alguns segundos, logo após o PIN;
- mostrar só iniciais e o status (trabalhando ou não), sem horários;
- deixar a lista configurável no painel.

**Status: concluído em 24/10/2026** (opção escolhida: só a batida da própria pessoa). A lista com todos os colegas saiu do relógio e a rota `/api/today` foi removida. Depois do PIN, o cartão mostra por 15 segundos só as batidas de hoje de quem bateu e depois volta a ficar vazio.

---

## 🟡 Prioridade baixa

### 11. Fórmulas no CSV

**Problema.** Um nome de funcionário ou de feriado começando com `=`, `+`, `-` ou `@` vira fórmula ao abrir o CSV no Excel.

**Risco.** Baixo, porque esses textos são digitados por admins. Mas uma fórmula maliciosa pode tentar executar comandos ou enviar dados ao abrir a planilha.

**Correção.** Ao gerar o CSV, prefixar com `'` toda célula que comece com esses caracteres.

**Status: concluído em 24/10/2026.** Nomes, feriados e avisos que começam com `=`, `+`, `-`, `@`, tab ou quebra de linha ganham um `'` na frente. Textos com `;`, aspas ou quebra de linha vão entre aspas, para não criar colunas ou linhas falsas na planilha. As colunas de horas e números não mudam.

### 12. Scripts dentro das páginas (CSP mais fraco)

**Problema.** O JavaScript fica dentro dos arquivos HTML, então a política de segurança de conteúdo (CSP) precisa permitir `'unsafe-inline'`.

**Risco.** Hoje não há XSS conhecido, mas, se surgir um, o CSP não vai barrá-lo.

**Correção.** Mover os scripts para arquivos `.js` e tirar `'unsafe-inline'` de `script-src`.

**Status: concluído em 24/10/2026.** Os scripts das 6 páginas estão em `frontend/public/js/` e a CSP passou a `script-src 'self'`: um script injetado numa página não roda. Só `login.js` e `privacidade.js` são públicos; os demais exigem login, como as páginas. `style-src` continua com `'unsafe-inline'` por causa dos atributos `style=` gerados pelas páginas, o que não permite executar código. Testado no navegador: nenhuma página com erro de script ou violação de CSP.

### 13. Dependências sem checagem de vulnerabilidades

**Problema.** As versões das bibliotecas são fixas e ninguém confere se alguma tem falha conhecida.

**Correção.** Rodar `pip-audit` (backend) e `npm audit` (app) no `deploy.sh`, interrompendo o deploy se houver falha grave.

**Status: concluído em 24/10/2026, com uma pendência no app.**
- O `deploy.sh` roda o `pip-audit` no backend e **interrompe o deploy** se houver falha conhecida. Em emergência (ex.: sem internet), pule com `PULAR_AUDITORIA=1 scripts/deploy.sh`.
- A primeira checagem achou 24 falhas no backend (Starlette e cryptography). Foram corrigidas atualizando `fastapi` (0.115 → 0.162), `starlette` (0.46 → 1.10) e `cryptography` (44 → 50). Os testes e os roteiros de ponta a ponta passaram com as versões novas.
- **App de celular:** o `npm audit` só avisa, porque o app não é publicado pelo `deploy.sh`. As correções que não mudam versões principais foram aplicadas (29 → 24 falhas), e o app continua compilando e gerando o pacote do iOS. As 24 restantes estão nas ferramentas de build do Expo (CLI, Metro, servidor de desenvolvimento), não no código que vai para o iPhone. Elas só saem atualizando o Expo SDK 52 para uma versão atual, o que exige testar o app num Mac/iPhone.
- **Testado no iPhone em 24/10/2026:** o app funciona normalmente com as correções aplicadas. As falhas restantes ficam como risco aceito por estarem só nas ferramentas de build; reavalie ao atualizar o Expo SDK.

### 14. Chaves de celular não expiram

**Problema.** Uma chave de celular vale até ser revogada manualmente.

**Correção.** Dar validade às chaves (ex.: 1 ano), avisar no painel quando estiverem perto de vencer e revogar automaticamente as que ficarem muito tempo sem uso.

**Status: concluído em 24/10/2026.**
- Cada chave vale 1 ano a partir da criação; as já existentes também passam a vencer 1 ano depois de criadas. A chave vencida é recusada com "Chave de acesso vencida. Peça uma nova ao administrador".
- A chave parada há 90 dias (ou nunca usada em 90 dias) é revogada sozinha, com registro do "sistema" na auditoria.
- O painel avisa quando alguma chave vence nos próximos 30 dias e mostra a data de vencimento na lista de celulares.

### 15. Processo de LGPD

**Problema.** Falta a parte de processo.

**Correção.**
- Aviso de privacidade aos funcionários: quais dados são coletados, para quê, por quanto tempo e com quem são compartilhados (ex.: contabilidade).
- Regra de retenção: apagar ou anonimizar os registros de quem saiu da empresa depois dos 5 anos legais (inclusive nos backups mensais).
- Canal para o funcionário pedir acesso ou correção dos próprios dados.

**Status: concluído em 24/10/2026.**
- **Aviso de privacidade** em `/privacidade`, público e com link no relógio e no login. Ele diz o que é guardado, para quê (obrigação legal da CLT, sem depender de consentimento), com quem é compartilhado, por quanto tempo e a quem pedir acesso ou correção. O nome e o contato vêm do **cadastro da empresa** (Administração → Empresas, só o superadmin), porque o sistema atende várias empresas no mesmo servidor. A página mostra a empresa do link próprio dela (`/privacidade?e=<código>`, código aleatório para não permitir listar as empresas, mostrado no painel para repassar aos funcionários), do relógio ou do admin logado no aparelho; sem eles, usa um texto genérico. **Preencha o contato de cada empresa ao cadastrá-la.** O texto é um modelo: vale uma revisão por quem cuida da parte jurídica da empresa.
- **Pedido de acesso:** o botão **Dados** na lista de funcionários baixa, em JSON, tudo o que o sistema guarda sobre a pessoa (cadastro, jornadas, batidas, correções, solicitações, celulares, fechamentos e auditoria), sem hashes de PIN ou chave. Cada exportação fica na auditoria.
- **Retenção:** 5 anos depois do desligamento, o painel avisa e mostra o botão **Anonimizar**. Ele troca o nome por "Ex-funcionário nº N", invalida o PIN, revoga e renomeia os celulares, tira o nome do aparelho das batidas e as observações das solicitações e das ausências, e apaga os registros de auditoria da pessoa. É a única exceção à regra de que a auditoria nunca é apagada, e o banco só a aceita dentro dessa operação. As batidas e as horas continuam, sem identificação.
- **Ausências (atestados):** são dado de saúde, sensível pela LGPD. O sistema guarda só o tipo, as datas e as horas abonadas; o painel orienta a não escrever o diagnóstico (CID) na observação e a guardar o atestado em papel. Não há envio de arquivo do atestado.
- **Backups:** os mensais são guardados por 5 anos e então descartados. Assim, um cadastro anonimizado ainda pode existir em backups antigos por até 5 anos.

---

## Checklist

- [x] 1. Recriar a CA com *name constraints* e chave cifrada
- [x] 2. Postgres no Tailscale — risco aceito (tailnet de um único dono, com ACLs)
- [x] 3. Ativar firewall (rede local e Tailscale)
- [x] 4. Criptografar backups — [ ] cópia fora do servidor (definir `BACKUP_REMOTO` quando o servidor de backup estiver montado)
- [x] 5. Checar `Origin` nas rotas que alteram dados
- [x] 6. Sessões no servidor, "sair de todos", expiração por inatividade
- [x] 7. Senha mínima de 12 caracteres e TOTP para admins
- [x] 8. Auditoria geral e histórico preservado na reabertura do mês
- [x] 9. PIN de 6 dígitos e bloqueio progressivo
- [x] 10. Reduzir os dados mostrados no "Cartão de hoje"
- [x] 11. Neutralizar fórmulas no CSV
- [x] 12. Scripts em arquivos `.js` e CSP sem `'unsafe-inline'`
- [x] 13. `pip-audit` e `npm audit` no deploy; app testado no iPhone
- [x] 14. Validade das chaves de celular
- [x] 15. Aviso de privacidade e regra de retenção — [ ] preencher o contato de privacidade de cada empresa no cadastro
