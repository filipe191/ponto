import { StyleProp, StyleSheet, View, ViewStyle } from 'react-native';

import { cores, espaco, raio } from '../theme';

/**
 * Superficie elevada. Substitui os varios `backgroundColor: cores.superficie`
 * + borderRadius avulsos que existiam nas telas.
 */
export function Cartao({
  children,
  contornado = false,
  style,
}: {
  children?: React.ReactNode;
  /** Borda hairline — use quando o cartao fica sobre outra superficie. */
  contornado?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <View
      style={[
        estilos.base,
        contornado && estilos.contorno,
        style,
      ]}
    >
      {children}
    </View>
  );
}

const estilos = StyleSheet.create({
  base: {
    backgroundColor: cores.superficie,
    borderRadius: raio.grande,
    padding: espaco.md,
  },
  contorno: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: cores.borda,
  },
});
