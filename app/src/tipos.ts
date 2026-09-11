export type TipoBatida = 'ENTRADA' | 'SAIDA';

export type StatusSync = 'pendente' | 'enviado' | 'erro';

export interface Batida {
  id: string;
  tipo: TipoBatida;
  ocorridoEm: string;      // ISO-8601 com offset
  monotonicoMs: number | null;
  origem: string | null;
  observacao: string | null;
  manual: boolean;
  status: StatusSync;
  tentativas: number;
  ultimoErro: string | null;
  enviadoEm: string | null;
}

export interface DiaTrabalhado {
  data: string;            // YYYY-MM-DD
  minutos: number;
  emAberto: boolean;
  batidas: Batida[];
}

/**
 * Correcao de uma batida que o servidor JA tem.
 *
 * Vive numa tabela separada de propósito: depois de sincronizar, a linha da
 * batida some do celular, e a correcao precisa sobreviver a essa limpeza.
 */
export type AcaoAjuste = 'editar' | 'apagar';

export interface AjustePendente {
  id: string;              // id da batida no servidor
  acao: AcaoAjuste;
  ocorridoEm: string | null;
  tipo: TipoBatida | null;
  criadoEm: string;
  tentativas: number;
  ultimoErro: string | null;
}

/** Batida como o servidor devolve. */
export interface BatidaServidor {
  id: string;
  tipo: TipoBatida;
  ocorridoEm: string;
  origem: string | null;
  observacao: string | null;
  manual: boolean;
  ajustadoEm: string | null;
  relogioSuspeito: boolean;
}

export interface DiaResumo {
  data: string;            // YYYY-MM-DD
  trabalhadoMinutos: number;
  trabalhadoFormatado: string;
  saldoMinutos: number;
  diaAberto: boolean;
  batidas: BatidaServidor[];
}

export interface ResumoMes {
  inicio: string;
  fim: string;
  trabalhadoMinutos: number;
  esperadoMinutos: number;
  saldoMinutos: number;
  trabalhadoFormatado: string;
  saldoFormatado: string;
  dias: DiaResumo[];
}

/** Uma marcacao na tela Corrigir, venha ela do servidor ou da fila local. */
export interface MarcacaoEditavel {
  id: string;
  tipo: TipoBatida;
  ocorridoEm: string;
  manual: boolean;
  /** true = ainda nao saiu do celular, entao a correcao e local e instantanea. */
  local: boolean;
  status: StatusSync | 'servidor';
  ajustePendente: AcaoAjuste | null;
}
