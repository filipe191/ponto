import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { cores, espaco, tipo } from '../theme';
import { EstadoPonto } from '../estado';
import {
  dataLocal,
  formatarCronometro,
  formatarDuracao,
  formatarIso,
  horaLocal,
  segundosDesde,
} from '../tempo';

export function Hoje({ estado }: { estado: EstadoPonto }) {
  const { emTurno, ultima, dias, naFila, sincronizandoAgora, avisoSync, bater } = estado;

  const hojeStr = dataLocal(formatarIso(new Date()));
  const hoje = dias.find((d) => d.data === hojeStr);

  const [segundos, setSegundos] = useState(0);

  // O cronometro so existe enquanto ha turno aberto — nao faz sentido gastar
  // um timer por segundo quando a pessoa nao esta trabalhando.
  useEffect(() => {
    if (!emTurno || !ultima) {
      setSegundos(0);
      return;
    }
    const atualizar = () => setSegundos(segundosDesde(ultima.ocorridoEm));
    atualizar();
    const timer = setInterval(atualizar, 1000);
    return () => clearInterval(timer);
  }, [emTurno, ultima]);

  const minutosFechados = hoje?.minutos ?? 0;
  const totalHoje = minutosFechados + (emTurno ? segundos / 60 : 0);

  return (
    <ScrollView contentContainerStyle={estilos.conteudo}>
      <View style={estilos.cabecalho}>
        <View style={[estilos.pontoStatus, { backgroundColor: emTurno ? cores.emTurno : cores.fora }]} />
        <Text style={estilos.status}>
          {emTurno ? `Em turno desde ${horaLocal(ultima!.ocorridoEm)}` : 'Fora de turno'}
        </Text>
      </View>

      <Text style={estilos.cronometro}>
        {emTurno ? formatarCronometro(segundos) : formatarDuracao(minutosFechados)}
      </Text>
      <Text style={estilos.legendaCronometro}>
        {emTurno ? `${formatarDuracao(totalHoje)} no dia` : 'trabalhadas hoje'}
      </Text>

      <Pressable
        accessibilityRole="button"
        accessibilityLabel={emTurno ? 'Registrar saída' : 'Registrar entrada'}
        onPress={() => bater()}
        style={({ pressed }) => [
          estilos.botao,
          { backgroundColor: emTurno ? cores.superficieAlta : cores.emTurno },
          pressed && estilos.botaoPressionado,
        ]}
      >
        <Text style={[estilos.botaoTexto, { color: emTurno ? cores.texto : '#0B1F18' }]}>
          {emTurno ? 'Registrar saída' : 'Registrar entrada'}
        </Text>
      </Pressable>

      {naFila > 0 && (
        <View style={estilos.faixaFila}>
          {sincronizandoAgora ? (
            <ActivityIndicator size="small" color={cores.pendente} />
          ) : (
            <View style={estilos.pontoFila} />
          )}
          <Text style={estilos.textoFila}>
            {naFila === 1 ? '1 batida esperando rede' : `${naFila} batidas esperando rede`}
          </Text>
        </View>
      )}

      {avisoSync && naFila > 0 && <Text style={estilos.aviso}>{avisoSync}</Text>}

      {hoje && hoje.batidas.length > 0 && (
        <View style={estilos.marcacoes}>
          <Text style={estilos.tituloSecao}>Marcações de hoje</Text>
          {hoje.batidas.map((b) => (
            <View key={b.id} style={estilos.linha}>
              <Text style={estilos.hora}>{horaLocal(b.ocorridoEm)}</Text>
              <Text style={estilos.tipoBatida}>
                {b.tipo === 'ENTRADA' ? 'Entrada' : 'Saída'}
              </Text>
              <View
                style={[
                  estilos.marcadorSync,
                  { backgroundColor: b.status === 'enviado' ? cores.emTurno
                      : b.status === 'erro' ? cores.erro : cores.pendente },
                ]}
              />
            </View>
          ))}
        </View>
      )}

      {(!hoje || hoje.batidas.length === 0) && (
        <Text style={estilos.vazio}>Toque no botão quando começar o expediente.</Text>
      )}
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  conteudo: {
    padding: espaco.lg,
    paddingTop: espaco.xl,
    alignItems: 'center',
  },
  cabecalho: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: espaco.sm,
  },
  pontoStatus: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  status: {
    ...tipo.corpo,
    color: cores.textoFraco,
  },
  cronometro: {
    ...tipo.cronometro,
    color: cores.texto,
    marginTop: espaco.md,
  },
  legendaCronometro: {
    ...tipo.legenda,
    color: cores.textoFraco,
    marginTop: espaco.xs,
  },
  botao: {
    marginTop: espaco.xl,
    width: '100%',
    paddingVertical: 22,
    borderRadius: 18,
    alignItems: 'center',
  },
  botaoPressionado: {
    opacity: 0.75,
    transform: [{ scale: 0.985 }],
  },
  botaoTexto: {
    ...tipo.titulo,
    fontSize: 18,
  },
  faixaFila: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: espaco.sm,
    marginTop: espaco.lg,
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
    ...tipo.legenda,
    color: cores.pendente,
  },
  aviso: {
    ...tipo.legenda,
    color: cores.textoFraco,
    marginTop: espaco.sm,
    textAlign: 'center',
  },
  marcacoes: {
    marginTop: espaco.xl,
    width: '100%',
  },
  tituloSecao: {
    ...tipo.legenda,
    color: cores.textoFraco,
    marginBottom: espaco.sm,
  },
  linha: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: espaco.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: cores.borda,
    gap: espaco.md,
  },
  hora: {
    ...tipo.numero,
    color: cores.texto,
    width: 68,
  },
  tipoBatida: {
    ...tipo.corpo,
    color: cores.textoFraco,
    flex: 1,
  },
  marcadorSync: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  vazio: {
    ...tipo.corpo,
    color: cores.textoFraco,
    marginTop: espaco.xl,
    textAlign: 'center',
  },
});
