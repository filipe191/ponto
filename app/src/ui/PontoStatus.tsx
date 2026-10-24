import { StyleProp, View, ViewStyle } from 'react-native';

import { cores, raio } from '../theme';
import { StatusSync } from '../tipos';

/** Inclui 'servidor', que so existe na tela Corrigir (MarcacaoEditavel). */
export type EstadoPonto = StatusSync | 'servidor';

const TAMANHOS = {
  pequeno: 6,
  medio: 7,
  grande: 8,
} as const;

/**
 * A regra de cor do ponto de sincronizacao, num lugar so.
 *
 * Estava repetida em 6 pontos do app, cada um com um tamanho diferente
 * (8, 7, 6, 5...) e o mesmo ternario aninhado copiado. Se um dia entrar um
 * quarto estado, muda aqui e acabou.
 */
export function corDoEstado(estado: EstadoPonto): string {
  switch (estado) {
    case 'enviado':
    case 'servidor':
      return cores.emTurno;
    case 'erro':
      return cores.erro;
    case 'pendente':
      return cores.pendente;
  }
}

export function PontoStatus({
  estado,
  tamanho = 'pequeno',
  cor,
  style,
}: {
  estado?: EstadoPonto;
  tamanho?: keyof typeof TAMANHOS;
  /** Sobrescreve a cor derivada do estado — use para turno (verde/cinza). */
  cor?: string;
  style?: StyleProp<ViewStyle>;
}) {
  const lado = TAMANHOS[tamanho];

  return (
    <View
      style={[
        {
          width: lado,
          height: lado,
          borderRadius: raio.total,
          backgroundColor: cor ?? (estado ? corDoEstado(estado) : cores.fora),
        },
        style,
      ]}
    />
  );
}
