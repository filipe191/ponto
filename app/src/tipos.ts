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
