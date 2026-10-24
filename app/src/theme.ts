/**
 * Paleta pensada para o estado ser lido de relance, com o telefone na mão,
 * na porta do escritorio. A cor CARREGA informacao: se a tela esta verde voce
 * esta em turno; se esta neutra voce nao esta; ambar sempre significa
 * "tem coisa esperando rede".
 */
export const cores = {
  fundo: '#111820',
  superficie: '#1B242F',
  superficieAlta: '#243040',
  borda: '#2E3B4B',

  texto: '#E7EDF4',
  textoFraco: '#93A2B4',

  emTurno: '#3FB68B',
  emTurnoFraco: '#1F4D3E',

  fora: '#5C7089',

  pendente: '#E0A458',
  erro: '#E06A5C',
};

export const espaco = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 40,
};

export const tipo = {
  cronometro: {
    fontSize: 64,
    fontWeight: '200' as const,
    letterSpacing: -2,
    // Sem isso os digitos "pulam" a cada segundo. Detalhe que faz diferenca
    // num app que fica com um cronometro rodando na tela.
    fontVariant: ['tabular-nums' as const],
  },
  numero: {
    fontSize: 20,
    fontWeight: '500' as const,
    fontVariant: ['tabular-nums' as const],
  },
  titulo: {
    fontSize: 17,
    fontWeight: '600' as const,
  },
  corpo: {
    fontSize: 15,
    fontWeight: '400' as const,
  },
  legenda: {
    fontSize: 13,
    fontWeight: '400' as const,
  },
};

/**
 * Raios. Antes cada tela escolhia o seu: havia 3, 4, 8, 10, 12, 14, 18 e 999
 * espalhados pelos arquivos, sem criterio. A escala abaixo e a unificacao —
 * nada de numero solto em StyleSheet novo.
 */
export const raio = {
  pequeno: 8,
  medio: 12,      // campos de texto
  grande: 14,     // cartoes e botoes
  enorme: 18,     // o botao principal da tela Hoje
  total: 999,     // circulos e pilulas
};

/**
 * Estados de toque. Um so lugar decide como um Pressable reage, senao cada
 * tela inventa a sua opacidade.
 */
export const toque = {
  opacidade: 0.75,
  escala: 0.985,
};
