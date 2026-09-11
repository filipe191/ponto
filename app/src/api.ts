import { Config } from './config';
import { AjustePendente, Batida, BatidaServidor, ResumoMes, TipoBatida } from './tipos';

/**
 * Cliente HTTP. Toda funcao aqui pode falhar — quem chama trata.
 */

export interface RespostaLote {
  aceitas: string[];
  duplicadas: string[];
  rejeitadas: { id: string; motivo: string }[];
}

const TIMEOUT_MS = 15000;

/**
 * Erro com o status HTTP preservado. A fila de correcoes precisa distinguir
 * "o servidor recusou" (tira da fila) de "a rede falhou" (tenta de novo).
 */
export class ErroHttp extends Error {
  constructor(mensagem: string, readonly status: number) {
    super(mensagem);
    this.name = 'ErroHttp';
  }
}

async function requisicao<T>(
  config: Config,
  caminho: string,
  init: RequestInit = {},
): Promise<T> {
  const controlador = new AbortController();
  const timer = setTimeout(() => controlador.abort(), TIMEOUT_MS);

  try {
    const resposta = await fetch(`${config.urlApi}${caminho}`, {
      ...init,
      signal: controlador.signal,
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': config.apiKey,
        ...(init.headers ?? {}),
      },
    });

    if (resposta.status === 401) {
      throw new ErroHttp('Chave de acesso recusada. Confira em Ajustes.', 401);
    }
    if (!resposta.ok) {
      throw new ErroHttp(`Servidor respondeu ${resposta.status}`, resposta.status);
    }
    if (resposta.status === 204) {
      return null as T;
    }

    return (await resposta.json()) as T;
  } catch (e: any) {
    if (e?.name === 'AbortError') {
      throw new Error('Servidor demorou demais para responder');
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export async function enviarLote(config: Config, batidas: Batida[]): Promise<RespostaLote> {
  const corpo = {
    batidas: batidas.map((b) => ({
      id: b.id,
      tipo: b.tipo,
      ocorridoEm: b.ocorridoEm,
      uptimeMs: b.monotonicoMs,
      origem: b.origem,
      observacao: b.observacao,
      manual: b.manual,
    })),
  };

  return requisicao<RespostaLote>(config, '/api/pontos/lote', {
    method: 'POST',
    body: JSON.stringify(corpo),
  });
}

export async function testarConexao(config: Config): Promise<boolean> {
  await requisicao(config, '/api/pontos/ultima', { method: 'GET' });
  return true;
}

/**
 * Aplica uma correcao ja enfileirada. PATCH so com o que mudou; o servidor
 * mantem o resto do registro como esta.
 */
export async function aplicarAjuste(config: Config, ajuste: AjustePendente): Promise<void> {
  if (ajuste.acao === 'apagar') {
    await requisicao(config, `/api/pontos/${ajuste.id}`, { method: 'DELETE' });
    return;
  }

  const corpo: { ocorridoEm?: string; tipo?: TipoBatida } = {};
  if (ajuste.ocorridoEm) corpo.ocorridoEm = ajuste.ocorridoEm;
  if (ajuste.tipo) corpo.tipo = ajuste.tipo;

  await requisicao(config, `/api/pontos/${ajuste.id}`, {
    method: 'PATCH',
    body: JSON.stringify(corpo),
  });
}

/** Historico do mes (YYYY-MM) — e o servidor que calcula horas e saldo. */
export async function buscarResumo(config: Config, mes: string): Promise<ResumoMes> {
  return requisicao<ResumoMes>(config, `/api/pontos/resumo?mes=${mes}`, { method: 'GET' });
}

/** Batidas de um periodo, usado pela tela Corrigir. Datas em YYYY-MM-DD. */
export async function buscarPeriodo(
  config: Config,
  inicio: string,
  fim: string,
): Promise<BatidaServidor[]> {
  return requisicao<BatidaServidor[]>(
    config, `/api/pontos?inicio=${inicio}&fim=${fim}`, { method: 'GET' },
  );
}

/**
 * Ultima batida segundo o servidor. Ganhou importancia agora que o celular
 * apaga o historico local: depois da limpeza, e daqui que o app descobre se
 * voce esta em turno.
 */
export async function ultimaDoServidor(config: Config): Promise<BatidaServidor | null> {
  return requisicao<BatidaServidor | null>(config, '/api/pontos/ultima', { method: 'GET' });
}
