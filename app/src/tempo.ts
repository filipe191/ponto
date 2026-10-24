import { Batida, DiaTrabalhado, TipoBatida } from './tipos';

/**
 * Calculos de horas feitos LOCALMENTE, a partir do SQLite. O app mostra o
 * saldo correto mesmo sem nunca ter falado com o servidor.
 */

export function dataLocal(iso: string): string {
  return iso.slice(0, 10);
}

export function horaLocal(iso: string): string {
  return iso.slice(11, 16);
}

export function inicioDoDiaIso(data: Date): string {
  const d = new Date(data);
  d.setHours(0, 0, 0, 0);
  return formatarIso(d);
}

export function formatarIso(d: Date): string {
  const offset = -d.getTimezoneOffset();
  const sinal = offset >= 0 ? '+' : '-';
  const pad = (n: number) => String(Math.floor(Math.abs(n))).padStart(2, '0');
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 19) + sinal + pad(offset / 60) + ':' + pad(offset % 60);
}

export function formatarDuracao(minutos: number): string {
  const sinal = minutos < 0 ? '-' : '';
  const abs = Math.abs(Math.round(minutos));
  return `${sinal}${Math.floor(abs / 60)}h ${String(abs % 60).padStart(2, '0')}min`;
}

export function formatarCronometro(segundos: number): string {
  const h = Math.floor(segundos / 3600);
  const m = Math.floor((segundos % 3600) / 60);
  const s = Math.floor(segundos % 60);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/**
 * Pareia ENTRADA com SAIDA. Funciona igual com dois toques por dia ou com
 * quatro (entrada, almoco, volta, saida) — sao so dois pares.
 */
export function agruparPorDia(batidas: Batida[]): DiaTrabalhado[] {
  const mapa = new Map<string, Batida[]>();

  for (const b of batidas) {
    const dia = dataLocal(b.ocorridoEm);
    const lista = mapa.get(dia) ?? [];
    lista.push(b);
    mapa.set(dia, lista);
  }

  const dias: DiaTrabalhado[] = [];

  for (const [data, lista] of mapa) {
    const ordenadas = [...lista].sort((a, b) => a.ocorridoEm.localeCompare(b.ocorridoEm));
    const { minutos, emAberto } = minutosPareados(ordenadas);

    dias.push({ data, minutos, emAberto, batidas: ordenadas });
  }

  return dias.sort((a, b) => b.data.localeCompare(a.data));
}

/**
 * O pareamento em si, separado porque a tela Corrigir precisa do total de um
 * dia montado a partir de marcacoes que vieram do servidor — nao de linhas do
 * SQLite. Aceita qualquer coisa com tipo e ocorridoEm.
 */
export function minutosPareados(
  batidas: { tipo: TipoBatida; ocorridoEm: string }[],
): { minutos: number; emAberto: boolean } {
  const ordenadas = [...batidas].sort((a, b) => a.ocorridoEm.localeCompare(b.ocorridoEm));

  let minutos = 0;
  let entradaAberta: { ocorridoEm: string } | null = null;

  for (const b of ordenadas) {
    if (b.tipo === 'ENTRADA') {
      entradaAberta = b;
    } else if (entradaAberta) {
      minutos += diferencaMinutos(entradaAberta.ocorridoEm, b.ocorridoEm);
      entradaAberta = null;
    }
  }

  return { minutos, emAberto: entradaAberta !== null };
}

export function diferencaMinutos(inicioIso: string, fimIso: string): number {
  return (new Date(fimIso).getTime() - new Date(inicioIso).getTime()) / 60000;
}

/** Segundos decorridos desde a entrada em aberto, para o cronometro rodar. */
export function segundosDesde(iso: string): number {
  return Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
}

export function ehDiaUtil(data: string): boolean {
  const dia = new Date(`${data}T12:00:00`).getDay();
  return dia !== 0 && dia !== 6;
}

export function nomeDoDia(data: string): string {
  const nomes = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado'];
  return nomes[new Date(`${data}T12:00:00`).getDay()];
}

export function dataAmigavel(data: string): string {
  const hoje = dataLocal(formatarIso(new Date()));
  const ontem = dataLocal(formatarIso(new Date(Date.now() - 86400000)));
  if (data === hoje) return 'Hoje';
  if (data === ontem) return 'Ontem';
  const [, mes, dia] = data.split('-');
  return `${dia}/${mes}`;
}

/* -------------------------------------------------- navegacao por dia e mes */

export function hojeLocal(): string {
  return dataLocal(formatarIso(new Date()));
}

export function somarDias(data: string, dias: number): string {
  // Meio-dia evita que horario de verao empurre o resultado para o dia vizinho.
  const d = new Date(`${data}T12:00:00`);
  d.setDate(d.getDate() + dias);
  return dataLocal(formatarIso(d));
}

export function mesDe(data: string): string {
  return data.slice(0, 7);
}

export function mesAtual(): string {
  return mesDe(hojeLocal());
}

export function somarMeses(mes: string, meses: number): string {
  const [ano, m] = mes.split('-').map(Number);
  const d = new Date(ano, m - 1 + meses, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

const NOMES_MES = [
  'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
];

export function rotuloMes(mes: string): string {
  const [ano, m] = mes.split('-').map(Number);
  return `${NOMES_MES[m - 1]} de ${ano}`;
}

/** "quarta, 10/09" — cabecalho do seletor de dia na tela Corrigir. */
export function dataPorExtenso(data: string): string {
  const [, mes, dia] = data.split('-');
  return `${nomeDoDia(data)}, ${dia}/${mes}`;
}

/* ------------------------------------------------------ edicao de horario */

/** Junta um dia (YYYY-MM-DD) com uma hora (HH:MM) no ISO local com offset. */
export function isoDoDiaComHora(data: string, hora: string): string {
  return formatarIso(new Date(`${data}T${hora}:00`));
}

/** Desloca um ISO em minutos, mantendo o dia se a conta virar a meia-noite. */
export function deslocarMinutos(iso: string, minutos: number): string {
  return formatarIso(new Date(new Date(iso).getTime() + minutos * 60000));
}

/** Normaliza "8:5" -> "08:05". Devolve null se nao der para entender. */
export function normalizarHora(texto: string): string | null {
  const cru = texto.trim().replace(/[.,;]/g, ':');
  const m = /^(\d{1,2}):?(\d{0,2})$/.exec(cru);
  if (!m) return null;

  const h = Number(m[1]);
  const min = Number(m[2] || '0');
  if (h > 23 || min > 59) return null;

  return `${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}`;
}
