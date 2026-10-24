# Ponto

Controle de ponto com **um único backend** e duas formas de bater o ponto:

- **Sistema web** (`web/`): o backend (FastAPI + Postgres) e o site servido por nginx em HTTPS.
  Tem o relógio da empresa (tablet com PIN) e o painel de administração: espelho mensal,
  banco de horas, regras da CLT, feriados, fechamento do mês e aprovação das solicitações
  do app. Instruções completas em [`web/README.md`](web/README.md).
- **App de celular** (`app/`): Expo / React Native para iPhone. Funciona sem rede: grava a
  batida no aparelho e sincroniza com o sistema web quando houver conexão. Cada
  funcionário usa a própria chave, gerada no painel.

```
ponto/
├── web/   Backend + relógio + administração (FastAPI, nginx, Postgres)
└── app/   App de celular (Expo / React Native, iPhone)
```

As batidas do app entram no mesmo espelho, banco de horas e regras das batidas do relógio,
marcadas como `cel`.

## Como o app conversa com o servidor

A batida é gravada no SQLite do celular **primeiro**, sempre. O envio é um passo
separado que pode falhar quantas vezes for — o botão nunca depende da rede.

O `id` de cada batida é um UUID gerado **no aparelho**. É isso que torna o
reenvio seguro: se o POST chegar no servidor mas a resposta se perder, o retry
devolve aquele id na lista `duplicadas` em vez de criar uma batida repetida. O
app trata `aceitas` e `duplicadas` igual — as duas significam "está salvo lá".
Uma batida que o funcionário também fez no relógio da empresa no mesmo minuto
volta como `duplicada`: o ponto já tem aquele horário.

A sincronização dispara em três momentos: quando o app volta ao primeiro plano
(o mais confiável no iOS), quando o NetInfo avisa que a rede voltou, e logo
depois de cada batida.

O servidor fala o mesmo contrato do antigo backend Spring (`/api/pontos/...`,
autenticação pelo cabeçalho `X-API-Key`), implementado em
`web/backend/app/api/routes/mobile.py`.

### O que vale na hora e o que precisa de aprovação

- **Batida feita na hora** pelo botão da tela Hoje: entra direto no ponto.
- **Marcação adicionada depois**, **correção** e **exclusão** (tela Corrigir): viram
  **solicitações** que o administrador aprova ou recusa no painel. Até a aprovação,
  o servidor — e portanto o Histórico — continua mostrando a batida original.
- Mês já fechado pelo administrador não recebe batidas novas do app; peça um
  lançamento manual ao administrador.

### Quem guarda o quê

Ao fim de cada sincronização bem-sucedida o celular **apaga o que o servidor já
confirmou**. Na prática isso acontece uma vez por dia: passada a virada, o dia
anterior sai do aparelho e passa a existir só no Postgres.

O que nunca é apagado do celular:

- o **dia de hoje**, senão a tela Hoje perderia o cronômetro e as marcações;
- um **turno em aberto**, mesmo começado ontem — sem a ENTRADA o app acharia que
  você está fora de turno e o próximo toque viraria ENTRADA no meio do
  expediente;
- o que **ainda não foi enviado**, incluindo correções na fila.

Por isso o **Histórico lê do servidor**, não do SQLite: o passado não mora mais
no aparelho. A última resposta de cada mês fica em cache local só para a tela
abrir com conteúdo quando não houver rede — e qualquer refresh bem-sucedido
substitui esse cache.

---

## 1. Subir o sistema

Veja [`web/README.md`](web/README.md). Em resumo:

```bash
cd web
cp .env.example .env   # só na primeira vez; preencha PGPASSWORD, SECRET_KEY e PIN_KEY
scripts/deploy.sh
```

## 2. Liberar o app para um funcionário

1. No painel (`https://<ip-do-servidor>:9443/admin`), em **Funcionários**, toque em
   **Celular** no funcionário e gere uma chave. Ela aparece uma única vez.
2. **No iPhone, confie no certificado do servidor** (o iOS só aceita HTTPS confiável):
   abra `http://<ip-do-servidor>:9092/ponto-ca.crt` no Safari, instale o perfil em
   Ajustes e ative em Ajustes → Geral → Sobre → Ajustes de Confiança de Certificados.
3. No app, em **Ajustes**, informe:
   - **Endereço do servidor** — `https://<ip-do-servidor>:9443`, sem barra no final
   - **Chave de acesso** — a chave gerada no passo 1

Toque em *Salvar e testar*. Se o servidor responder, está pronto. Celular perdido ou
trocado: revogue a chave no mesmo lugar.

## 3. Rodar o app (desenvolvimento)

```bash
cd app
npm install
npx expo install --fix     # alinha as versões nativas com o SDK instalado
npx expo start
```

Abra no Expo Go pelo QR code e configure como no passo 2.

> O app usa `expo-sqlite` e `expo-secure-store`, que funcionam no Expo Go. Para
> instalar no iPhone de forma permanente (sem depender do Expo Go aberto), gere
> um build com `eas build --platform ios --profile preview` e instale via
> TestFlight.

### Compilando pelo Xcode

As fases de script do Xcode rodam com um `PATH` mínimo e **não enxergam o
Homebrew**. Sem isso o build morre com `Command PhaseScriptExecution failed
with a nonzero exit code`, cercado de centenas de warnings irrelevantes dos
Pods. Em cada máquina, crie o arquivo local:

```bash
cd app/ios
echo "export NODE_BINARY=$(command -v node)" > .xcode.env.local
```

Use o caminho do symlink (`/opt/homebrew/bin/node`) e **não** o do Cellar
(`/opt/homebrew/Cellar/node/<versão>/bin/node`) — o segundo some no próximo
`brew upgrade node` e quebra o build do nada. O arquivo é ignorado pelo git,
então cada máquina tem o seu.

Quando o build falhar, o erro útil não é o que o Xcode mostra no topo:

```bash
cd app/ios
xcodebuild -workspace Ponto.xcworkspace -scheme Ponto -configuration Release \
  -sdk iphoneos -destination 'generic/platform=iOS' build 2>&1 | tee /tmp/build.log
grep -nE "error:|PhaseScriptExecution|failed" /tmp/build.log
```

Note que em **Debug o bundling do JS é pulado** (`SKIP_BUNDLING=1`): um build
Debug que passa não prova que o Release passa. Para testar a etapa de bundle e
o Hermes, compile em Release.

## 4. Acesso fora da empresa

O sistema roda na rede local, sem nada exposto para a internet aberta. Para o app
sincronizar de fora, use o **Tailscale** no iPhone e no servidor e coloque o IP
`100.x.x.x` do servidor no endereço (o certificado HTTPS já inclui esse IP). Sem
isso, o app guarda as batidas e sincroniza quando o celular voltar à rede da empresa.

---

## Como usar o app no dia a dia

A tela **Hoje** tem um botão só, que alterna entre entrada e saída conforme a
última marcação. Funciona com dois toques por dia ou com quatro (entrada,
almoço, volta, saída) — o cálculo pareia entrada com saída, então os dois
padrões funcionam sem configurar nada.

O ponto colorido ao lado de cada marcação mostra o estado da sincronização:
verde já está no servidor, âmbar ainda na fila, vermelho o servidor recusou.

**Histórico** mostra o mês com o saldo de horas, **calculado pelo servidor** com as
mesmas regras do espelho (jornada do funcionário, feriados, hora noturna, tolerância)
— use as setas ‹ › para navegar entre os meses. Sem rede, a tela abre a última cópia
baixada daquele mês e avisa que é cópia.

**Corrigir** pede o conserto do que ficou errado: hora trocada, marcação a mais,
batida esquecida. Escolha o dia nas setas ‹ ›, toque numa marcação para editar hora e
tipo (com passos de ±1, ±5 e ±15 minutos, ou digitando HH:MM), ou use
*Adicionar marcação* para lançar a que faltou. Se a batida ainda não saiu do celular,
a correção é local e instantânea; se o servidor já tem, ela vira uma **solicitação**
para o administrador, enviada na próxima sincronização.

## Ajustes comuns

| O que mudar | Onde |
|---|---|
| Jornada diária e dias de trabalho | Painel → Funcionários → Editar (vale para o app e o relógio) |
| Feriados | Painel → Feriados |
| Fuso horário, tolerância, horário noturno | `web/backend/app/core/config.py` (ou variáveis de ambiente) |
| Cores e tipografia do app | `app/src/theme.ts` |
| Passos de minuto da tela Corrigir | `app/src/telas/Corrigir.tsx` → `PASSOS` |

## Backup

O banco tem backup diário automático (veja `web/README.md`). No celular, desinstalar
o app apaga o SQLite local: batidas ainda pendentes se perdem — sincronize antes. O que
já foi confirmado está no servidor, e é de lá que o Histórico lê.
