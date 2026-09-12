import { StyleProp, StyleSheet, View, ViewStyle } from 'react-native';

import { cores, espaco, raio } from '../theme';

/**
 * Faixa arredondada para status efemero ("3 batidas esperando rede").
 * Alinha os filhos em linha, entao aceita um PontoStatus + Texto direto.
 */
export function Pilula({
  children,
  style,
}: {
  children?: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}) {
  return <View style={[estilos.base, style]}>{children}</View>;
}

const estilos = StyleSheet.create({
  base: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: espaco.sm,
    paddingVertical: espaco.sm,
    paddingHorizontal: espaco.md,
    borderRadius: raio.total,
    backgroundColor: cores.superficie,
  },
});
