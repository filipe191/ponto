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

---

## 1. Subir o backend

```bash
cd backend
docker compose up --build
```

Postgres na porta 5433 do host, API na 8080. O Flyway cria o schema no primeiro
boot. Antes de usar de verdade, troque a chave em `docker-compose.yml`:

```bash
openssl rand -hex 32
```

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

**Histórico** mostra o mês corrente com o saldo de horas, calculado localmente
— aparece certo mesmo se você nunca tiver conectado no servidor. Dia com número
ímpar de marcações aparece como *saída não registrada*.

## Ajustes comuns

| O que mudar | Onde |
|---|---|
| Jornada diária (padrão 8h) | `backend/src/main/resources/application.yml` → `ponto.jornada-diaria` e `app/src/telas/Historico.tsx` → `JORNADA_MINUTOS` |
| Fuso horário | `application.yml` → `ponto.timezone` |
| Cores e tipografia do app | `app/src/theme.ts` |

## Se precisar zerar o banco

```bash
cd backend
docker compose down -v && docker compose up --build
```

No celular, desinstalar o app apaga o SQLite local. Batidas ainda pendentes se
perdem — sincronize antes.
