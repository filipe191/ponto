import { StyleProp, Text, TextProps, TextStyle } from 'react-native';

import { cores, tipo } from '../theme';

type Variante = keyof typeof tipo;

/**
 * Tons nomeados pelo SIGNIFICADO, nao pela cor. Quem escreve a tela pensa
 * "isso esta pendente", nao "isso e ambar" — e o dia que a paleta mudar,
 * muda no theme sem passar por 60 <Text>.
 */
const TONS = {
  normal: cores.texto,
  fraco: cores.textoFraco,
  emTurno: cores.emTurno,
  pendente: cores.pendente,
  erro: cores.erro,
  /** Sobre fundo verde: o texto precisa ser escuro pra ter contraste. */
  sobreVerde: '#0B1F18',
} as const;

export interface TextoProps extends TextProps {
  variante?: Variante;
  tom?: keyof typeof TONS;
  style?: StyleProp<TextStyle>;
}

export function Texto({
  variante = 'corpo',
  tom = 'normal',
  style,
  ...resto
}: TextoProps) {
  return <Text style={[tipo[variante], { color: TONS[tom] }, style]} {...resto} />;
}
