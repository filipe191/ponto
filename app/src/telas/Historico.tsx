import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import { cores, espaco, tipo } from '../theme';
import { EstadoPonto } from '../estado';
import { buscarResumo } from '../api';
import { carregarConfig, configCompleta } from '../config';
import { lerCacheResumo, salvarCacheResumo } from '../db';
import { dataAmigavel, horaLocal, mesAtual, nomeDoDia, rotuloMes, somarMeses } from '../tempo';
import { ResumoMes } from '../tipos';

/**
 * Historico do mes, vindo do servidor.
 *
 * Desde que o celular passou a se limpar depois de cada sincronizacao, o passado
 * nao existe mais aqui — quem guarda e calcula e o backend. Isso tambem acaba
 * com a jornada duplicada: o saldo mostrado e o que o servidor calculou com o
 * ponto.jornada-diaria dele, e nao uma constante repetida no app.
 *
 * A ultima resposta de cada mes fica em cache no SQLite so para a tela abrir com
 * conteudo quando nao houver rede. Cache nunca vira fonte da verdade: qualquer
 * refresh bem-sucedido o substitui.
 */
export function Historico({ estado }: { estado: EstadoPonto }) {
  const { naFila, correcoesNaFila } = estado;

  const [mes, setMes] = useState(mesAtual());
  const [resumo, setResumo] = useState<ResumoMes | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [doCache, setDoCache] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setCarregando(true);
    try {
      const config = await carregarConfig();

      if (!configCompleta(config)) {
        setAviso('Configure o servidor em Ajustes para ver o histórico.');
        setResumo(null);
        return;
      }

      try {
        const doServidor = await buscarResumo(config, mes);
        setResumo(doServidor);
        setDoCache(false);
        setAviso(null);
        await salvarCacheResumo(mes, doServidor);
      } catch (e: any) {
        const cache = await lerCacheResumo(mes);
        if (cache) {
          setResumo(cache.resumo);
          setDoCache(true);
          setAviso(`Sem resposta do servidor. Mostrando a cópia de ${dataAmigavel(cache.buscadoEm.slice(0, 10))} às ${horaLocal(cache.buscadoEm)}.`);
        } else {
          setResumo(null);
          setAviso(e?.message ?? 'Não foi possível falar com o servidor');
        }
      }
    } finally {
      setCarregando(false);
    }
  }, [mes]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const dias = [...(resumo?.dias ?? [])].sort((a, b) => b.data.localeCompare(a.data));
  const naoEnviadas = naFila + correcoesNaFila;
  const podeAvancar = mes < mesAtual();

  return (
    <ScrollView
      contentContainerStyle={estilos.conteudo}
      refreshControl={
        <RefreshControl refreshing={carregando} onRefresh={carregar} tintColor={cores.textoFraco} />
      }
    >
      <View style={estilos.seletorMes}>
        <Pressable
          onPress={() => setMes(somarMeses(mes, -1))}
          accessibilityLabel="Mês anterior"
          style={estilos.seta}
        >
          <Text style={estilos.setaTexto}>‹</Text>
        </Pressable>

        <Text style={estilos.mes}>{rotuloMes(mes)}</Text>

        <Pressable
          onPress={() => podeAvancar && setMes(somarMeses(mes, 1))}
          disabled={!podeAvancar}
          accessibilityLabel="Próximo mês"
          style={estilos.seta}
        >
          <Text style={[estilos.setaTexto, !podeAvancar && estilos.setaApagada]}>›</Text>
        </Pressable>
      </View>

      <View style={estilos.resumo}>
        <View style={estilos.blocoResumo}>
          <Text style={estilos.valorResumo}>{resumo?.trabalhadoFormatado ?? '—'}</Text>
          <Text style={estilos.rotuloResumo}>trabalhadas no mês</Text>
        </View>
        <View style={estilos.blocoResumo}>
          <Text
            style={[
              estilos.valorResumo,
              { color: (resumo?.saldoMinutos ?? 0) < 0 ? cores.pendente : cores.emTurno },
            ]}
          >
            {resumo?.saldoFormatado ?? '—'}
          </Text>
          <Text style={estilos.rotuloResumo}>
            {(resumo?.saldoMinutos ?? 0) < 0 ? 'a compensar' : 'de saldo'}
          </Text>
        </View>
      </View>

      {doCache && <Text style={estilos.selo}>cópia local</Text>}

      {aviso && <Text style={estilos.aviso}>{aviso}</Text>}

      {naoEnviadas > 0 && (
        <Text style={estilos.aviso}>
          {naoEnviadas === 1
            ? '1 marcação ainda não enviada não entra nesta conta.'
            : `${naoEnviadas} marcações ainda não enviadas não entram nesta conta.`}
        </Text>
      )}

      {carregando && !resumo && <ActivityIndicator color={cores.textoFraco} style={{ marginTop: espaco.xl }} />}

      {!carregando && resumo && dias.length === 0 && (
        <Text style={estilos.vazio}>Nenhuma marcação neste mês.</Text>
      )}

      {dias.map((dia) => (
        <View key={dia.data} style={estilos.dia}>
          <View style={estilos.cabecalhoDia}>
            <View>
              <Text style={estilos.dataDia}>{dataAmigavel(dia.data)}</Text>
              <Text style={estilos.nomeDia}>{nomeDoDia(dia.data)}</Text>
            </View>
            <View style={estilos.totalDia}>
              <Text style={estilos.valorDia}>{dia.trabalhadoFormatado}</Text>
              {dia.diaAberto && <Text style={estilos.emAberto}>saída não registrada</Text>}
            </View>
          </View>

          <View style={estilos.horarios}>
            {dia.batidas.map((b) => (
              <View key={b.id} style={estilos.chip}>
                <View
                  style={[
                    estilos.chipMarcador,
                    { backgroundColor: b.tipo === 'ENTRADA' ? cores.emTurno : cores.fora },
                  ]}
                />
                <Text style={estilos.chipTexto}>{horaLocal(b.ocorridoEm)}</Text>
                {(b.manual || b.ajustadoEm) && <Text style={estilos.chipAjustada}>·</Text>}
              </View>
            ))}
          </View>
        </View>
      ))}

      {resumo && dias.length > 0 && (
        <Text style={estilos.nota}>
          Saldo calculado pelo servidor sobre {Math.round(resumo.esperadoMinutos / 60)}h de jornada
          nos dias úteis do mês. O ponto ao lado da hora marca correção manual.
        </Text>
      )}
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  conteudo: {
    padding: espaco.lg,
    paddingBottom: espaco.xl,
  },
  seletorMes: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: espaco.md,
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
  mes: {
    ...tipo.titulo,
    color: cores.texto,
    flex: 1,
    textAlign: 'center',
  },
  resumo: {
    flexDirection: 'row',
    gap: espaco.md,
  },
  blocoResumo: {
    flex: 1,
    backgroundColor: cores.superficie,
    borderRadius: 14,
    padding: espaco.md,
  },
  valorResumo: {
    ...tipo.numero,
    fontSize: 22,
    color: cores.texto,
  },
  rotuloResumo: {
    ...tipo.legenda,
    color: cores.textoFraco,
    marginTop: espaco.xs,
  },
  selo: {
    ...tipo.legenda,
    color: cores.pendente,
    marginTop: espaco.sm,
    textAlign: 'center',
  },
  aviso: {
    ...tipo.legenda,
    color: cores.textoFraco,
    marginTop: espaco.sm,
    textAlign: 'center',
    lineHeight: 19,
  },
  nota: {
    ...tipo.legenda,
    color: cores.fora,
    marginTop: espaco.lg,
    lineHeight: 19,
  },
  vazio: {
    ...tipo.corpo,
    color: cores.textoFraco,
    marginTop: espaco.xl,
    textAlign: 'center',
  },
  dia: {
    marginTop: espaco.lg,
    paddingTop: espaco.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: cores.borda,
  },
  cabecalhoDia: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  dataDia: {
    ...tipo.titulo,
    color: cores.texto,
  },
  nomeDia: {
    ...tipo.legenda,
    color: cores.textoFraco,
    marginTop: 2,
  },
  totalDia: {
    alignItems: 'flex-end',
  },
  valorDia: {
    ...tipo.numero,
    color: cores.texto,
  },
  emAberto: {
    ...tipo.legenda,
    color: cores.pendente,
    marginTop: 2,
  },
  horarios: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: espaco.sm,
    marginTop: espaco.md,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: cores.superficie,
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 8,
  },
  chipMarcador: {
    width: 5,
    height: 5,
    borderRadius: 3,
  },
  chipTexto: {
    ...tipo.legenda,
    color: cores.texto,
    fontVariant: ['tabular-nums'],
  },
  chipAjustada: {
    color: cores.textoFraco,
    fontSize: 16,
    lineHeight: 16,
  },
});
