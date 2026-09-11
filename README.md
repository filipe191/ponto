# Ponto

Controle de ponto pessoal que funciona sem rede. O iPhone grava a batida
localmente e sincroniza com o servidor quando houver conexão.

```
ponto/
├── backend/   Spring Boot + Postgres (API e histórico definitivo)
└── app/       Expo / React Native (iPhone)
```

## Como as duas partes conversam

A batida é gravada no SQLite do celular **primeiro**, sempre. O envio é um passo
separado que pode falhar quantas vezes for — o botão nunca depende da rede.

O `id` de cada batida é um UUID gerado **no aparelho**. É isso que torna o
reenvio seguro: se o POST chegar no servidor mas a resposta se perder, o retry
devolve aquele id na lista `duplicadas` em vez de criar uma batida repetida. O
app trata `aceitas` e `duplicadas` igual — as duas significam "está salvo lá".

A sincronização dispara em três momentos: quando o app volta ao primeiro plano
(o mais confiável no iOS), quando o NetInfo avisa que a rede voltou, e logo
depois de cada batida.

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

## 1. Subir o backend

Os segredos ficam num `.env` que **não vai para o git**. Na primeira vez:

```bash
cd backend
cp .env.example .env
openssl rand -hex 32   # cole em PONTO_API_KEY
openssl rand -hex 16   # cole em POSTGRES_PASSWORD e DB_PASSWORD
docker compose up --build
```

Postgres na porta 5433 do host, API na 8080. O Flyway cria o schema no primeiro
boot. A API **não sobe sem `PONTO_API_KEY`** — não existe chave padrão, de
propósito: um default publicado é o mesmo que não ter autenticação.

Detalhes de endpoints e decisões de modelagem estão em `backend/README.md`.

## 2. Rodar o app

```bash
cd app
npm install
npx expo install --fix     # alinha as versões nativas com o SDK instalado
npx expo start
```

Abra no Expo Go pelo QR code. Na primeira execução, vá em **Ajustes** e informe:

- **Endereço do servidor** — onde a API está rodando, sem barra no final
- **Chave de acesso** — a mesma do `PONTO_API_KEY`

Toque em *Salvar e testar*. Se o servidor responder, está pronto.

> O app usa `expo-sqlite` e `expo-secure-store`, que funcionam no Expo Go. Para
> instalar no iPhone de forma permanente (sem depender do Expo Go aberto), gere
> um build com `eas build --platform ios --profile preview` e instale via
> TestFlight.

## 3. Onde hospedar

O iPhone precisa alcançar a API. Duas opções que não expõem nada para a
internet aberta:

- **Tailscale** — instale no iPhone e no servidor, use o IP `100.x.x.x` no
  campo de endereço. Mais simples e o que recomendo.
- **Cloudflare Tunnel** — se quiser um domínio de verdade.

Enquanto o homelab não estiver de pé, um VPS pequeno ou o Fly.io seguram o
backend sem esforço; depois é só mover o container e o volume do Postgres.

---

## Como usar no dia a dia

A tela **Hoje** tem um botão só, que alterna entre entrada e saída conforme a
última marcação. Funciona com dois toques por dia ou com quatro (entrada,
almoço, volta, saída) — o cálculo pareia entrada com saída, então os dois
padrões funcionam sem configurar nada.

O ponto colorido ao lado de cada marcação mostra o estado da sincronização:
verde já está no servidor, âmbar ainda na fila, vermelho o servidor recusou.

**Histórico** mostra o mês com o saldo de horas, **calculado pelo servidor** —
use as setas ‹ › para navegar entre os meses. Dia com número ímpar de marcações
aparece como *saída não registrada*. Sem rede, a tela abre a última cópia
baixada daquele mês e avisa que é cópia.

**Corrigir** conserta o que ficou errado: hora trocada, marcação a mais, batida
esquecida. Escolha o dia nas setas ‹ ›, toque numa marcação para editar hora e
tipo (com passos de ±1, ±5 e ±15 minutos, ou digitando HH:MM), ou use
*Adicionar marcação* para lançar a que faltou.

A tela junta as duas fontes — o dia de hoje vem do aparelho, os dias anteriores
vêm do servidor — para que você não precise saber onde o registro mora. Se a
batida ainda não saiu do celular, a correção é local e instantânea; se o
servidor já tem, ela vira um `PATCH`/`DELETE` na fila, aparece na hora na tela e
sai na próxima sincronização.

## Ajustes comuns

| O que mudar | Onde |
|---|---|
| Jornada diária (padrão 8h) | `backend/src/main/resources/application.yml` → `ponto.jornada-diaria` (só aqui: o saldo do app vem pronto do servidor) |
| Fuso horário | `application.yml` → `ponto.timezone` |
| Cores e tipografia do app | `app/src/theme.ts` |
| Passos de minuto da tela Corrigir | `app/src/telas/Corrigir.tsx` → `PASSOS` |

## Se precisar zerar o banco

```bash
cd backend
docker compose down -v && docker compose up --build
```

No celular, desinstalar o app apaga o SQLite local. Batidas ainda pendentes se
perdem — sincronize antes. O que já foi confirmado não se perde: está no
servidor, e é de lá que o Histórico lê.

Zerar o banco do servidor, por outro lado, apaga o histórico de verdade — o
celular só tem o dia corrente.
