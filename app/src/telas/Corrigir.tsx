import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { cores, espaco, tipo as tipografia } from '../theme';
import { EstadoPonto } from '../estado';
import { buscarPeriodo } from '../api';
import { carregarConfig, configCompleta } from '../config';
import { batidasEntre } from '../db';
import {
  dataPorExtenso,
  formatarDuracao,
  hojeLocal,
  horaLocal,
  isoDoDiaComHora,
  minutosPareados,
  normalizarHora,
  somarDias,
} from '../tempo';
import { MarcacaoEditavel, TipoBatida } from '../tipos';

/**
 * Tela Corrigir: conserta o que ficou errado — hora trocada, marcacao a mais,
 * batida esquecida.
 *
 * O dia de hoje ainda esta no celular; qualquer dia anterior ja foi limpo e vem
 * do servidor. A tela junta as duas fontes para que isso nao apareca na
 * interface: voce escolhe o dia e corrige, sem precisar saber onde o registro
 * mora naquele momento.
 */

/** Ajuste em edicao. id nulo = marcacao nova. */
interface Edicao {
  id: string | null;
  tipo: TipoBatida;
  hora: string;
}

const PASSOS = [-15, -5, -1, 1, 5, 15];

export function Corrigir({ estado }: { estado: EstadoPonto }) {
  const { ajustes, correcoesNaFila, adicionarMarcacao, corrigirMarcacao, apagarMarcacao } = estado;

  const [dia, setDia] = useState(hojeLocal());
  const [marcacoes, setMarcacoes] = useState<MarcacaoEditavel[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [avisoServidor, setAvisoServidor] = useState<string | null>(null);
  const [edicao, setEdicao] = useState<Edicao | null>(null);
  const [erroForm, setErroForm] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  const carregar = useCallback(async () => {
    setCarregando(true);
    try {
      const locais = await batidasEntre(
        isoDoDiaComHora(dia, '00:00'),
        isoDoDiaComHora(somarDias(dia, 1), '00:00'),
      );

      // A lista do servidor pode faltar (sem rede, sem config). Quando falta, a
      // tela ainda funciona com o que houver no aparelho — so avisa o motivo.
      let doServidor: MarcacaoEditavel[] = [];
      try {
        const config = await carregarConfig();
        if (configCompleta(config)) {
          const resposta = await buscarPeriodo(config, dia, dia);
          doServidor = resposta.map((b) => ({
            id: b.id,
            tipo: b.tipo,
            ocorridoEm: b.ocorridoEm,
            manual: b.manual,
            local: false,
            status: 'servidor' as const,
            ajustePendente: null,
          }));
          setAvisoServidor(null);
        } else {
          setAvisoServidor('Sem servidor configurado — mostrando só o que está no aparelho.');
        }
      } catch (e: any) {
        setAvisoServidor(
          `${e?.message ?? 'Servidor fora de alcance'} — mostrando só o que está no aparelho.`,
        );
      }

      const mapa = new Map<string, MarcacaoEditavel>();
      for (const m of doServidor) {
        mapa.set(m.id, m);
      }

      // Local por cima: se a batida esta nos dois lugares, a copia do celular e
      // a que pode ter alteracao ainda nao enviada.
      for (const b of locais) {
        mapa.set(b.id, {
          id: b.id,
          tipo: b.tipo,
          ocorridoEm: b.ocorridoEm,
          manual: b.manual,
          local: b.status !== 'enviado',
          status: b.status,
          ajustePendente: null,
        });
      }

      // Correcao na fila ainda nao chegou no servidor, mas a tela ja mostra o
      // resultado dela — esperar o proximo sync para ver o que voce acabou de
      // digitar seria estranho.
      for (const ajuste of ajustes) {
        const atual = mapa.get(ajuste.id);
        if (!atual) continue;

        mapa.set(ajuste.id, {
          ...atual,
          tipo: ajuste.tipo ?? atual.tipo,
          ocorridoEm: ajuste.ocorridoEm ?? atual.ocorridoEm,
          ajustePendente: ajuste.acao,
        });
      }

      const lista = [...mapa.values()].sort((a, b) => a.ocorridoEm.localeCompare(b.ocorridoEm));
      setMarcacoes(lista);
    } finally {
      setCarregando(false);
    }
  }, [dia, ajustes]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const vivas = marcacoes.filter((m) => m.ajustePendente !== 'apagar');
  const { minutos, emAberto } = minutosPareados(vivas);
  const podeAvancar = dia < hojeLocal();

  function abrirNova() {
    setErroForm(null);
    // Uma marcacao esquecida quase sempre e o par que falta da ultima batida.
    const ultimaViva = vivas[vivas.length - 1];
    setEdicao({
      id: null,
      tipo: ultimaViva?.tipo === 'ENTRADA' ? 'SAIDA' : 'ENTRADA',
      hora: ultimaViva ? horaLocal(ultimaViva.ocorridoEm) : '09:00',
    });
  }

  function abrirEdicao(m: MarcacaoEditavel) {
    setErroForm(null);
    setEdicao({ id: m.id, tipo: m.tipo, hora: horaLocal(m.ocorridoEm) });
  }

  function deslocar(minutosPasso: number) {
    setEdicao((atual) => {
      if (!atual) return atual;

      const normalizada = normalizarHora(atual.hora);
      if (!normalizada) return atual;

      const [h, m] = normalizada.split(':').map(Number);
      // Preso ao dia escolhido: passar da meia-noite mudaria a data por baixo
      // dos panos, e a data aqui e a que voce selecionou no topo.
      const total = Math.min(23 * 60 + 59, Math.max(0, h * 60 + m + minutosPasso));

      return {
        ...atual,
        hora: `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`,
      };
    });
  }

  async function salvar() {
    if (!edicao) return;

    const hora = normalizarHora(edicao.hora);
    if (!hora) {
      setErroForm('Horário inválido. Use HH:MM.');
      return;
    }

    const ocorridoEm = isoDoDiaComHora(dia, hora);

    setSalvando(true);
    try {
      if (edicao.id === null) {
        await adicionarMarcacao(edicao.tipo, ocorridoEm);
      } else {
        await corrigirMarcacao(edicao.id, { ocorridoEm, tipo: edicao.tipo });
      }
      setEdicao(null);
      setErroForm(null);
      await carregar();
    } catch (e: any) {
      setErroForm(e?.message ?? 'Não foi possível salvar');
    } finally {
      setSalvando(false);
    }
  }

  function confirmarExclusao(id: string) {
    Alert.alert(
      'Apagar marcação',
      'A marcação sai do histórico e o saldo do dia é recalculado.',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Apagar',
          style: 'destructive',
          onPress: async () => {
            await apagarMarcacao(id);
            setEdicao(null);
            await carregar();
          },
        },
      ],
    );
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        contentContainerStyle={estilos.conteudo}
        keyboardShouldPersistTaps="handled"
        refreshControl={
          <RefreshControl refreshing={carregando} onRefresh={carregar} tintColor={cores.textoFraco} />
        }
      >
        <View style={estilos.seletorDia}>
          <Pressable
            onPress={() => setDia(somarDias(dia, -1))}
            accessibilityLabel="Dia anterior"
            style={estilos.seta}
          >
            <Text style={estilos.setaTexto}>‹</Text>
          </Pressable>

          <View style={estilos.tituloDia}>
            <Text style={estilos.dataDia}>{dataPorExtenso(dia)}</Text>
            <Text style={estilos.totalDia}>
              {formatarDuracao(minutos)}
              {emAberto ? ' · saída não registrada' : ''}
            </Text>
          </View>

          <Pressable
            onPress={() => podeAvancar && setDia(somarDias(dia, 1))}
            disabled={!podeAvancar}
            accessibilityLabel="Próximo dia"
            style={estilos.seta}
          >
            <Text style={[estilos.setaTexto, !podeAvancar && estilos.setaApagada]}>›</Text>
          </Pressable>
        </View>

        {avisoServidor && <Text style={estilos.aviso}>{avisoServidor}</Text>}

        {correcoesNaFila > 0 && (
          <View style={estilos.faixaFila}>
            <View style={estilos.pontoFila} />
            <Text style={estilos.textoFila}>
              {correcoesNaFila === 1
                ? '1 correção esperando o servidor'
                : `${correcoesNaFila} correções esperando o servidor`}
            </Text>
          </View>
        )}

        {ajustes
          .filter((a) => a.ultimoErro)
          .map((a) => (
            <Text key={a.id} style={estilos.erroAjuste}>
              Correção recusada: {a.ultimoErro}
            </Text>
          ))}

        {carregando && marcacoes.length === 0 ? (
          <ActivityIndicator color={cores.textoFraco} style={{ marginTop: espaco.xl }} />
        ) : marcacoes.length === 0 ? (
          <Text style={estilos.vazio}>Nenhuma marcação neste dia.</Text>
        ) : (
          <View style={estilos.lista}>
            {marcacoes.map((m) => {
              const selecionada = edicao?.id === m.id;
              const removida = m.ajustePendente === 'apagar';

              return (
                <Pressable
                  key={m.id}
                  onPress={() => !removida && abrirEdicao(m)}
                  disabled={removida}
                  style={[estilos.linha, selecionada && estilos.linhaSelecionada]}
                >
                  <Text style={[estilos.hora, removida && estilos.textoRemovido]}>
                    {horaLocal(m.ocorridoEm)}
                  </Text>

                  <View style={{ flex: 1 }}>
                    <Text style={[estilos.tipoBatida, removida && estilos.textoRemovido]}>
                      {m.tipo === 'ENTRADA' ? 'Entrada' : 'Saída'}
                    </Text>
                    <Text style={estilos.detalhe}>{rotuloEstado(m)}</Text>
                  </View>

                  <View
                    style={[
                      estilos.marcadorSync,
                      { backgroundColor: corDoEstado(m) },
                    ]}
                  />
                </Pressable>
              );
            })}
          </View>
        )}

        {!edicao && (
          <Pressable onPress={abrirNova} style={({ pressed }) => [estilos.botaoSecundario, pressed && { opacity: 0.7 }]}>
            <Text style={estilos.botaoSecundarioTexto}>+ Adicionar marcação</Text>
          </Pressable>
        )}

        {edicao && (
          <View style={estilos.editor}>
            <Text style={estilos.tituloEditor}>
              {edicao.id === null ? 'Nova marcação' : 'Corrigir marcação'}
            </Text>

            <View style={estilos.alternador}>
              {(['ENTRADA', 'SAIDA'] as TipoBatida[]).map((t) => {
                const ativo = edicao.tipo === t;
                return (
                  <Pressable
                    key={t}
                    onPress={() => setEdicao({ ...edicao, tipo: t })}
                    style={[estilos.opcao, ativo && estilos.opcaoAtiva]}
                  >
                    <Text style={[estilos.opcaoTexto, ativo && estilos.opcaoTextoAtivo]}>
                      {t === 'ENTRADA' ? 'Entrada' : 'Saída'}
                    </Text>
                  </Pressable>
                );
              })}
            </View>

            <TextInput
              value={edicao.hora}
              onChangeText={(hora) => setEdicao({ ...edicao, hora })}
              onBlur={() => {
                const normalizada = normalizarHora(edicao.hora);
                if (normalizada) setEdicao({ ...edicao, hora: normalizada });
              }}
              placeholder="HH:MM"
              placeholderTextColor={cores.fora}
              keyboardType="numbers-and-punctuation"
              maxLength={5}
              selectTextOnFocus
              style={estilos.campoHora}
            />

            {/* Digitar hora no celular e chato; os passos resolvem o caso comum,
                que e errar por poucos minutos. */}
            <View style={estilos.passos}>
              {PASSOS.map((passo) => (
                <Pressable
                  key={passo}
                  onPress={() => deslocar(passo)}
                  style={({ pressed }) => [estilos.passo, pressed && { opacity: 0.6 }]}
                >
                  <Text style={estilos.passoTexto}>
                    {passo > 0 ? `+${passo}` : passo}
                  </Text>
                </Pressable>
              ))}
            </View>

            {erroForm && <Text style={estilos.erroForm}>{erroForm}</Text>}

            <Pressable
              onPress={salvar}
              disabled={salvando}
              style={({ pressed }) => [estilos.botao, pressed && { opacity: 0.75 }]}
            >
              {salvando
                ? <ActivityIndicator color="#0B1F18" />
                : <Text style={estilos.botaoTexto}>Salvar</Text>}
            </Pressable>

            <View style={estilos.acoesSecundarias}>
              <Pressable onPress={() => { setEdicao(null); setErroForm(null); }}>
                <Text style={estilos.link}>Cancelar</Text>
              </Pressable>

              {edicao.id !== null && (
                <Pressable onPress={() => confirmarExclusao(edicao.id!)}>
                  <Text style={[estilos.link, { color: cores.erro }]}>Apagar marcação</Text>
                </Pressable>
              )}
            </View>
          </View>
        )}

        <Text style={estilos.rodape}>
          Correção feita aqui vale para o servidor. Sem rede, ela fica na fila e
          sai na próxima sincronização.
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function rotuloEstado(m: MarcacaoEditavel): string {
  if (m.ajustePendente === 'apagar') return 'removida — aguardando servidor';
  if (m.ajustePendente === 'editar') return 'corrigida — aguardando servidor';
  if (m.status === 'erro') return 'o servidor recusou';
  if (m.status === 'pendente') return 'esperando rede';
  if (m.manual) return 'lançada manualmente';
  return 'no servidor';
}

function corDoEstado(m: MarcacaoEditavel): string {
  if (m.ajustePendente) return cores.pendente;
  if (m.status === 'erro') return cores.erro;
  if (m.status === 'pendente') return cores.pendente;
  return cores.emTurno;
}

const estilos = StyleSheet.create({
  conteudo: {
    padding: espaco.lg,
    paddingBottom: espaco.xl,
  },
  seletorDia: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  seta: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  setaTexto: {
    color: cores.texto,
    fontSize: 30,
    lineHeight: 34,
  },
  setaApagada: {
    color: cores.borda,
  },
  tituloDia: {
    flex: 1,
    alignItems: 'center',
  },
  dataDia: {
    ...tipografia.titulo,
    color: cores.texto,
  },
  totalDia: {
    ...tipografia.legenda,
    color: cores.textoFraco,
    marginTop: 2,
  },
  aviso: {
    ...tipografia.legenda,
    color: cores.textoFraco,
    marginTop: espaco.md,
    textAlign: 'center',
    lineHeight: 19,
  },
  faixaFila: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'center',
    gap: espaco.sm,
    marginTop: espaco.md,
    paddingVertical: espaco.sm,
    paddingHorizontal: espaco.md,
    borderRadius: 999,
    backgroundColor: cores.superficie,
  },
  pontoFila: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: cores.pendente,
  },
  textoFila: {
    ...tipografia.legenda,
    color: cores.pendente,
  },
  erroAjuste: {
    ...tipografia.legenda,
    color: cores.erro,
    marginTop: espaco.sm,
    textAlign: 'center',
  },
  lista: {
    marginTop: espaco.lg,
  },
  linha: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: espaco.md,
    paddingVertical: espaco.md,
    paddingHorizontal: espaco.sm,
    borderRadius: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: cores.borda,
  },
  linhaSelecionada: {
    backgroundColor: cores.superficie,
  },
  hora: {
    ...tipografia.numero,
    color: cores.texto,
    width: 68,
  },
  tipoBatida: {
    ...tipografia.corpo,
    color: cores.texto,
  },
  detalhe: {
    ...tipografia.legenda,
    color: cores.textoFraco,
    marginTop: 2,
  },
  textoRemovido: {
    color: cores.fora,
    textDecorationLine: 'line-through',
  },
  marcadorSync: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  vazio: {
    ...tipografia.corpo,
    color: cores.textoFraco,
    marginTop: espaco.xl,
    textAlign: 'center',
  },
  botaoSecundario: {
    marginTop: espaco.lg,
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: cores.borda,
    alignItems: 'center',
  },
  botaoSecundarioTexto: {
    ...tipografia.corpo,
    color: cores.texto,
  },
  editor: {
    marginTop: espaco.lg,
    padding: espaco.md,
    borderRadius: 16,
    backgroundColor: cores.superficie,
  },
  tituloEditor: {
    ...tipografia.titulo,
    color: cores.texto,
    marginBottom: espaco.md,
  },
  alternador: {
    flexDirection: 'row',
    backgroundColor: cores.fundo,
    borderRadius: 10,
    padding: 3,
  },
  opcao: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
  },
  opcaoAtiva: {
    backgroundColor: cores.superficieAlta,
  },
  opcaoTexto: {
    ...tipografia.corpo,
    color: cores.fora,
  },
  opcaoTextoAtivo: {
    color: cores.texto,
    fontWeight: '600',
  },
  campoHora: {
    marginTop: espaco.md,
    alignSelf: 'center',
    minWidth: 150,
    textAlign: 'center',
    color: cores.texto,
    fontSize: 44,
    fontWeight: '300',
    fontVariant: ['tabular-nums'],
    paddingVertical: espaco.sm,
  },
  passos: {
    flexDirection: 'row',
    justifyContent: 'center',
    flexWrap: 'wrap',
    gap: espaco.sm,
    marginTop: espaco.sm,
  },
  passo: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: cores.superficieAlta,
  },
  passoTexto: {
    ...tipografia.legenda,
    color: cores.texto,
    fontVariant: ['tabular-nums'],
  },
  erroForm: {
    ...tipografia.legenda,
    color: cores.erro,
    marginTop: espaco.md,
    textAlign: 'center',
  },
  botao: {
    marginTop: espaco.lg,
    backgroundColor: cores.emTurno,
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: 'center',
  },
  botaoTexto: {
    ...tipografia.titulo,
    color: '#0B1F18',
  },
  acoesSecundarias: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: espaco.md,
  },
  link: {
    ...tipografia.legenda,
    color: cores.textoFraco,
  },
  rodape: {
    ...tipografia.legenda,
    color: cores.fora,
    marginTop: espaco.xl,
    textAlign: 'center',
    lineHeight: 19,
  },
});
