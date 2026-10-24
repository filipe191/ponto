import { StyleProp, StyleSheet, TextInput, TextInputProps, TextStyle, View } from 'react-native';

import { cores, espaco, raio, tipo } from '../theme';
import { Texto } from './Texto';

export interface CampoProps extends TextInputProps {
  rotulo?: string;
  ajuda?: string;
  style?: StyleProp<TextStyle>;
}

/**
 * Campo de texto com rotulo e ajuda. Ja vem com as cores de placeholder e
 * selecao certas — no tema escuro o padrao do iOS fica ilegivel.
 */
export function Campo({ rotulo, ajuda, style, ...resto }: CampoProps) {
  return (
    <View>
      {rotulo && (
        <Texto variante="titulo" style={estilos.rotulo}>
          {rotulo}
        </Texto>
      )}

      <TextInput
        placeholderTextColor={cores.textoFraco}
        selectionColor={cores.emTurno}
        style={[estilos.campo, style]}
        {...resto}
      />

      {ajuda && (
        <Texto variante="legenda" tom="fraco" style={estilos.ajuda}>
          {ajuda}
        </Texto>
      )}
    </View>
  );
}

const estilos = StyleSheet.create({
  rotulo: {
    marginBottom: espaco.sm,
  },
  campo: {
    backgroundColor: cores.superficie,
    borderRadius: raio.medio,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: cores.borda,
    paddingHorizontal: espaco.md,
    paddingVertical: 14,
    color: cores.texto,
    fontSize: 16,
  },
  ajuda: {
    marginTop: espaco.sm,
    lineHeight: 19,
  },
});
