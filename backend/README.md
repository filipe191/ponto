# Ponto — backend

Controle de ponto pessoal com sincronização offline. O app iOS grava as batidas
localmente e envia em lote quando há rede; este backend recebe, deduplica e
calcula as horas.

## Subir

```bash
docker compose up --build
```

Postgres sobe na porta **5433** do host (para não conflitar com outro Postgres),
a API na **8080**. O Flyway cria o schema no primeiro boot.

Antes de expor, troque `PONTO_API_KEY` no `docker-compose.yml`:

```bash
openssl rand -hex 32
```

## Endpoints

Todos exigem o header `X-API-Key`.

| Método | Rota | Para quê |
|---|---|---|
| POST | `/api/pontos/lote` | Sincroniza as batidas pendentes do app |
| PATCH | `/api/pontos/{id}` | Corrige hora, tipo ou observação de uma batida |
| DELETE | `/api/pontos/{id}` | Remove uma batida errada (exclusão lógica) |
| GET | `/api/pontos/ultima` | Última batida (o app usa para saber se o próximo toque é entrada ou saída) |
| GET | `/api/pontos?inicio=&fim=` | Lista batidas do período |
| GET | `/api/pontos/resumo?mes=2026-09` | Horas trabalhadas e saldo do mês |

Como o app limpa o SQLite depois de sincronizar, o servidor virou a única cópia
do que passou — por isso as rotas de correção existem, e por isso o histórico do
app é lido daqui em vez de calculado no aparelho.

### Enviar um lote

```bash
curl -X POST http://localhost:8080/api/pontos/lote \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PONTO_API_KEY" \
  -d '{
    "batidas": [
      {
        "id": "3f2b1c4a-8d5e-4f6a-9b7c-1d2e3f4a5b6c",
        "tipo": "ENTRADA",
        "ocorridoEm": "2026-09-10T08:02:00-03:00",
        "uptimeMs": 184320000,
        "origem": "iphone-pessoal"
      },
      {
        "id": "7a8b9c0d-1e2f-4a3b-8c5d-6e7f8a9b0c1d",
        "tipo": "SAIDA",
        "ocorridoEm": "2026-09-10T17:31:00-03:00",
        "uptimeMs": 218460000,
        "origem": "iphone-pessoal"
      }
    ]
  }'
```

Resposta:

```json
{
  "aceitas": ["3f2b1c4a-...", "7a8b9c0d-..."],
  "duplicadas": [],
  "rejeitadas": []
}
```

Reenvie exatamente o mesmo lote e os ids migram para `duplicadas`. **O app deve
tratar `aceitas` e `duplicadas` como sucesso** e marcar as duas listas como
sincronizadas no SQLite local — só o que cai em `rejeitadas` (ou o que não
voltou por falha de rede) continua pendente.

### Corrigir uma batida

Só o que vier no corpo muda; o resto do registro fica como está. Na prática o
app manda apenas `ocorridoEm`.

```bash
curl -X PATCH http://localhost:8080/api/pontos/3f2b1c4a-8d5e-4f6a-9b7c-1d2e3f4a5b6c \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $PONTO_API_KEY" \
  -d '{"ocorridoEm": "2026-09-10T07:45:00-03:00"}'
```

A resposta é a batida já corrigida, com `manual: true` e `ajustadoEm` preenchido.
Id inexistente (ou já apagado) devolve **404** — o app trata isso como correção
resolvida e tira o item da fila.

```bash
curl -X DELETE http://localhost:8080/api/pontos/3f2b1c4a-8d5e-4f6a-9b7c-1d2e3f4a5b6c \
  -H "X-API-Key: $PONTO_API_KEY"
```

Responde **204**. A linha continua no banco com `apagado_em` preenchido e some
de toda consulta e de todo cálculo.

### Resumo do mês

```bash
curl "http://localhost:8080/api/pontos/resumo?mes=2026-09" \
  -H "X-API-Key: $PONTO_API_KEY"
```

Retorna total trabalhado, esperado (dias úteis × jornada), saldo e o detalhe
dia a dia com `diaAberto: true` quando você esqueceu de bater a saída.

## Decisões que valem saber

- **O id vem do dispositivo.** É o que torna o reenvio seguro. Nunca gere o
  UUID no servidor.
- **Dois carimbos de tempo.** `ocorridoEm` é o relógio do iPhone, `recebidoEm`
  é o do servidor. Se o primeiro for maior que o segundo, a batida volta com
  `relogioSuspeito: true`.
- **`uptime_ms`** guarda o tempo desde o boot do aparelho. Se você mexer no
  relógio, a relação entre ele e `ocorridoEm` quebra de forma detectável.
- **Exclusão é lógica, não física.** `DELETE` preenche `apagado_em`; a linha
  fica. Dois motivos: o ponto é trilha de auditoria, e apagar de verdade
  liberaria o id — um lote antigo reenviado pelo app ressuscitaria a batida,
  porque a dedupe olha justamente o id.
- **Enum como VARCHAR + CHECK**, não como tipo enum nativo do Postgres — evita
  o descompasso de nome com o Hibernate.
- **`ddl-auto: validate`.** O schema é do Flyway. Se a validação falhar no
  boot, é migration faltando, não motivo para trocar por `update`.

## Configuração

Em `application.yml`, sob `ponto`:

- `jornada-diaria: PT8H` — muda o cálculo de saldo
- `timezone: America/Sao_Paulo` — usado para agrupar batidas por dia

## Reset do banco

Se uma migration rodar pela metade e o Flyway travar em dirty state:

```bash
docker compose down -v
docker compose up --build
```
