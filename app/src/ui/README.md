# Design system

Tokens em [`../theme.ts`](../theme.ts), componentes aqui. As telas importam
sempre do barrel:

```ts
import { Botao, Cartao, Texto, PontoStatus, cores, espaco } from '../ui';
```

## Por que existe

As 4 telas somavam 98 blocos de `StyleSheet` com muita coisa repetida:

| Repetição encontrada | Onde |
|---|---|
| Ponto de status reimplementado **6×**, com tamanhos 8, 7, 6, 5, 7 e 6 | Hoje, Historico, Corrigir |
| Mesmo ternário aninhado de cor (`enviado`/`erro`/`pendente`) copiado 3× | idem |
| Botão em 2 formatos diferentes sem motivo (pv 22/r 18 e pv 16/r 14) | Hoje, Ajustes |
| `borderRadius` com **7 valores** avulsos: 3, 4, 8, 10, 12, 14, 18, 999 | todas |
| `backgroundColor: cores.superficie` solto 8× | todas |

## Componentes

| Componente | Para quê | Props principais |
|---|---|---|
| `Texto` | Todo texto do app | `variante` (cronometro/numero/titulo/corpo/legenda), `tom` (normal/fraco/emTurno/pendente/erro/sobreVerde) |
| `Botao` | Ações | `variante` (primario/secundario/perigo), `tamanho` (normal/grande), `carregando`, `desabilitado` |
| `PontoStatus` | Bolinha de sincronização | `estado` (pendente/enviado/erro/servidor), `tamanho`, `cor` |
| `Cartao` | Superfície elevada | `contornado` |
| `Campo` | Entrada de texto | `rotulo`, `ajuda` + tudo de `TextInput` |
| `Pilula` | Faixa de status efêmero | — |
| `Linha` | Item de lista com divisor | `ultima` |

`corDoEstado(estado)` fica exportada à parte para quem precisa só da cor.

## Antes e depois

O ponto de sincronização, hoje repetido em cada tela:

```tsx
// antes — em Hoje.tsx, Historico.tsx e Corrigir.tsx, com variações
<View style={[ estilos.marcadorSync, { backgroundColor:
    b.status === 'enviado' ? cores.emTurno
  : b.status === 'erro'    ? cores.erro
  : cores.pendente } ]} />
// + no StyleSheet:  marcadorSync: { width: 6, height: 6, borderRadius: 3 }

// depois
<PontoStatus estado={b.status} />
```

O botão principal:

```tsx
// antes — 14 linhas de JSX + 3 blocos de estilo
<Pressable onPress={() => bater()} accessibilityRole="button" style={({ pressed }) => [
  estilos.botao, { backgroundColor: emTurno ? cores.superficieAlta : cores.emTurno },
  pressed && estilos.botaoPressionado ]}>
  <Text style={[estilos.botaoTexto, { color: emTurno ? cores.texto : '#0B1F18' }]}>
    {emTurno ? 'Registrar saída' : 'Registrar entrada'}
  </Text>
</Pressable>

// depois
<Botao
  titulo={emTurno ? 'Registrar saída' : 'Registrar entrada'}
  variante={emTurno ? 'secundario' : 'primario'}
  tamanho="grande"
  onPress={() => bater()}
/>
```

## Regras

1. **Nada de número solto** em `StyleSheet` novo — use `espaco` e `raio`.
2. **Cor por significado**, não por matiz: `tom="pendente"`, não `color: '#E0A458'`.
3. Componente novo entra aqui só quando o padrão aparece **na terceira tela**.
   Antes disso é estilo local mesmo.
4. `Botao` já traz `accessibilityRole` e `accessibilityState`; não recrie
   `Pressable` para ação que caiba nele.
