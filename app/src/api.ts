import { Config } from './config';
import { Batida } from './tipos';

/**
 * Cliente HTTP. Toda funcao aqui pode falhar — quem chama trata.
 */

export interface RespostaLote {
  aceitas: string[];
  duplicadas: string[];
  rejeitadas: { id: string; motivo: string }[];
}

const TIMEOUT_MS = 15000;

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
      throw new Error('Chave de acesso recusada. Confira em Ajustes.');
    }
    if (!resposta.ok) {
      throw new Error(`Servidor respondeu ${resposta.status}`);
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
