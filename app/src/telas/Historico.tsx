import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import { cores, espaco, tipo } from '../theme';
import { EstadoPonto } from '../estado';
import { dataAmigavel, ehDiaUtil, formatarDuracao, horaLocal, nomeDoDia } from '../tempo';

const JORNADA_MINUTOS = 8 * 60;

export function Historico({ estado }: { estado: EstadoPonto }) {
  const { dias, sincronizandoAgora, sincronizarAgora } = estado;

  const trabalhado = dias.reduce((soma, d) => soma + d.minutos, 0);
  const diasUteisComRegistro = dias.filter((d) => ehDiaUtil(d.data)).length;
  const esperado = diasUteisComRegistro * JORNADA_MINUTOS;
  const saldo = trabalhado - esperado;

  return (
    <ScrollView
      contentContainerStyle={estilos.conteudo}
      refreshControl={
        <RefreshControl
          refreshing={sincronizandoAgora}
          onRefresh={() => sincronizarAgora()}
          tintColor={cores.textoFraco}
        />
      }
    >
      <View style={estilos.resumo}>
        <View style={estilos.blocoResumo}>
          <Text style={estilos.valorResumo}>{formatarDuracao(trabalhado)}</Text>
          <Text style={estilos.rotuloResumo}>trabalhadas no mês</Text>
        </View>
        <View style={estilos.blocoResumo}>
          <Text style={[estilos.valorResumo, { color: saldo < 0 ? cores.pendente : cores.emTurno }]}>
            {formatarDuracao(saldo)}
          </Text>
          <Text style={estilos.rotuloResumo}>
            {saldo < 0 ? 'a compensar' : 'de saldo'}
          </Text>
        </View>
      </View>

      <Text style={estilos.nota}>
        Saldo comparado a {JORNADA_MINUTOS / 60}h nos {diasUteisComRegistro} dias úteis com registro.
      </Text>

      {dias.length === 0 && (
        <Text style={estilos.vazio}>Nenhuma marcação neste mês ainda.</Text>
      )}

      {dias.map((dia) => (
        <View key={dia.data} style={estilos.dia}>
          <View style={estilos.cabecalhoDia}>
            <View>
              <Text style={estilos.dataDia}>{dataAmigavel(dia.data)}</Text>
              <Text style={estilos.nomeDia}>{nomeDoDia(dia.data)}</Text>
            </View>
            <View style={estilos.totalDia}>
              <Text style={estilos.valorDia}>{formatarDuracao(dia.minutos)}</Text>
              {dia.emAberto && <Text style={estilos.emAberto}>saída não registrada</Text>}
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
                {b.status !== 'enviado' && <Text style={estilos.chipPendente}>·</Text>}
              </View>
            ))}
          </View>
        </View>
      ))}
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  conteudo: {
    padding: espaco.lg,
    paddingBottom: espaco.xl,
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
  nota: {
    ...tipo.legenda,
    color: cores.textoFraco,
    marginTop: espaco.sm,
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
  chipPendente: {
    color: cores.pendente,
    fontSize: 16,
    lineHeight: 16,
  },
});
