import { StyleProp, StyleSheet, View, ViewStyle } from 'react-native';

import { cores, espaco } from '../theme';

/**
 * Item de lista com divisor hairline. `ultima` tira a borda do ultimo item,
 * que senao fica com um risco solto no fim da lista.
 */
export function Linha({
  children,
  ultima = false,
  style,
}: {
  children?: React.ReactNode;
  ultima?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <View style={[estilos.base, ultima && estilos.semBorda, style]}>
      {children}
    </View>
  );
}

const estilos = StyleSheet.create({
  base: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: espaco.md,
    paddingVertical: espaco.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: cores.borda,
  },
  semBorda: {
    borderBottomWidth: 0,
  },
});
