import { ActivityIndicator, Pressable, StyleProp, StyleSheet, ViewStyle } from 'react-native';

import { cores, espaco, raio, toque } from '../theme';
import { Texto } from './Texto';

type Variante = 'primario' | 'secundario' | 'perigo';
type Tamanho = 'normal' | 'grande';

const FUNDOS: Record<Variante, string> = {
  primario: cores.emTurno,
  secundario: cores.superficieAlta,
  perigo: cores.erro,
};

/** No primario o fundo e verde claro, entao o texto tem que ser escuro. */
const TONS = {
  primario: 'sobreVerde',
  secundario: 'normal',
  perigo: 'normal',
} as const;

const ALTURAS: Record<Tamanho, { paddingVertical: number; borderRadius: number }> = {
  normal: { paddingVertical: 16, borderRadius: raio.grande },
  grande: { paddingVertical: 22, borderRadius: raio.enorme },
};

export function Botao({
  titulo,
  onPress,
  variante = 'primario',
  tamanho = 'normal',
  carregando = false,
  desabilitado = false,
  style,
}: {
  titulo: string;
  onPress: () => void;
  variante?: Variante;
  tamanho?: Tamanho;
  carregando?: boolean;
  desabilitado?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const inativo = desabilitado || carregando;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={titulo}
      accessibilityState={{ disabled: inativo, busy: carregando }}
      onPress={onPress}
      disabled={inativo}
      style={({ pressed }) => [
        estilos.base,
        ALTURAS[tamanho],
        { backgroundColor: FUNDOS[variante] },
        pressed && estilos.pressionado,
        inativo && estilos.inativo,
        style,
      ]}
    >
      {carregando ? (
        <ActivityIndicator
          size="small"
          color={variante === 'primario' ? '#0B1F18' : cores.texto}
        />
      ) : (
        <Texto
          variante="titulo"
          tom={TONS[variante]}
          style={tamanho === 'grande' ? estilos.textoGrande : undefined}
        >
          {titulo}
        </Texto>
      )}
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  base: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: espaco.md,
  },
  pressionado: {
    opacity: toque.opacidade,
    transform: [{ scale: toque.escala }],
  },
  inativo: {
    opacity: 0.45,
  },
  textoGrande: {
    fontSize: 18,
  },
});
