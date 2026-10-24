import { useState } from 'react';
import { ActivityIndicator, Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';

import { cores, espaco, tipo } from './src/theme';
import { useEstadoPonto } from './src/estado';
import { Hoje } from './src/telas/Hoje';
import { Historico } from './src/telas/Historico';
import { Corrigir } from './src/telas/Corrigir';
import { Ajustes } from './src/telas/Ajustes';

// "Corrigir" e nao "Ajustar": ao lado de "Ajustes" (servidor e chave), dois
// rotulos parecidos na mesma barra so fariam voce entrar na aba errada.
type Aba = 'hoje' | 'historico' | 'corrigir' | 'ajustes';

const ABAS: { chave: Aba; rotulo: string }[] = [
  { chave: 'hoje', rotulo: 'Hoje' },
  { chave: 'historico', rotulo: 'Histórico' },
  { chave: 'corrigir', rotulo: 'Corrigir' },
  { chave: 'ajustes', rotulo: 'Ajustes' },
];

export default function App() {
  const estado = useEstadoPonto();
  const [aba, setAba] = useState<Aba>('hoje');

  return (
    <SafeAreaView style={estilos.raiz}>
      <StatusBar style="light" />

      <View style={estilos.corpo}>
        {!estado.pronto ? (
          <View style={estilos.carregando}>
            <ActivityIndicator color={cores.textoFraco} />
          </View>
        ) : aba === 'hoje' ? (
          <Hoje estado={estado} />
        ) : aba === 'historico' ? (
          <Historico estado={estado} />
        ) : aba === 'corrigir' ? (
          <Corrigir estado={estado} />
        ) : (
          <Ajustes estado={estado} />
        )}
      </View>

      <View style={estilos.abas}>
        {ABAS.map(({ chave, rotulo }) => {
          const ativa = aba === chave;
          return (
            <Pressable
              key={chave}
              onPress={() => setAba(chave)}
              accessibilityRole="tab"
              accessibilityState={{ selected: ativa }}
              style={estilos.aba}
            >
              <Text style={[estilos.abaTexto, ativa && estilos.abaAtiva]}>{rotulo}</Text>
              {chave === 'ajustes' && estado.pendencias > 0 && <View style={estilos.selo} />}
            </Pressable>
          );
        })}
      </View>
    </SafeAreaView>
  );
}

const estilos = StyleSheet.create({
  raiz: {
    flex: 1,
    backgroundColor: cores.fundo,
  },
  corpo: {
    flex: 1,
  },
  carregando: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  abas: {
    flexDirection: 'row',
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: cores.borda,
    paddingTop: espaco.sm,
    paddingBottom: espaco.xs,
  },
  aba: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: espaco.sm,
  },
  abaTexto: {
    ...tipo.legenda,
    color: cores.fora,
  },
  abaAtiva: {
    color: cores.texto,
    fontWeight: '600',
  },
  selo: {
    position: 'absolute',
    top: 2,
    right: '30%',
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: cores.pendente,
  },
});
