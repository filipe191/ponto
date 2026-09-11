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
    fontVariant: ['tabular-nums'] as const,
  },
  numero: {
    fontSize: 20,
    fontWeight: '500' as const,
    fontVariant: ['tabular-nums'] as const,
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
