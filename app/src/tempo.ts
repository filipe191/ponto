import { Batida, DiaTrabalhado } from './tipos';

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

    let minutos = 0;
    let entradaAberta: Batida | null = null;

    for (const b of ordenadas) {
      if (b.tipo === 'ENTRADA') {
        entradaAberta = b;
      } else if (entradaAberta) {
        minutos += diferencaMinutos(entradaAberta.ocorridoEm, b.ocorridoEm);
        entradaAberta = null;
      }
    }

    dias.push({ data, minutos, emAberto: entradaAberta !== null, batidas: ordenadas });
  }

  return dias.sort((a, b) => b.data.localeCompare(a.data));
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
