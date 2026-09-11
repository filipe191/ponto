import { enviarLote } from './api';
import { carregarConfig, configCompleta } from './config';
import { marcarEnviadas, marcarErro, pendentes, registrarTentativa } from './db';

/**
 * Sincronizacao. Roda quando:
 *   1. o app volta para o primeiro plano  (cobre a maioria dos casos no iOS)
 *   2. a rede volta com o app aberto      (NetInfo)
 *   3. logo depois de bater o ponto       (caminho feliz)
 *
 * Nunca bloqueia a interface e nunca impede uma batida de ser registrada.
 */

const TAMANHO_LOTE = 200;

export interface ResultadoSync {
  status: 'ok' | 'nada-a-fazer' | 'sem-config' | 'falhou';
  enviadas: number;
  rejeitadas: number;
  mensagem?: string;
}

let sincronizando = false;

export async function sincronizar(): Promise<ResultadoSync> {
  // Duas chamadas concorrentes tentariam enviar o mesmo lote. O servidor
  // aguentaria (e idempotente), mas nao ha motivo para gastar rede.
  if (sincronizando) {
    return { status: 'nada-a-fazer', enviadas: 0, rejeitadas: 0 };
  }

  sincronizando = true;
  try {
    const config = await carregarConfig();
    if (!configCompleta(config)) {
      return {
        status: 'sem-config',
        enviadas: 0,
        rejeitadas: 0,
        mensagem: 'Falta configurar o endereco do servidor',
      };
    }

    const fila = await pendentes();
    if (fila.length === 0) {
      return { status: 'nada-a-fazer', enviadas: 0, rejeitadas: 0 };
    }

    let enviadas = 0;
    let rejeitadas = 0;

    for (let i = 0; i < fila.length; i += TAMANHO_LOTE) {
      const lote = fila.slice(i, i + TAMANHO_LOTE);
      const ids = lote.map((b) => b.id);

      try {
        const resposta = await enviarLote(config, lote);

        // Duplicada = o servidor ja tinha. Do ponto de vista do app isso e
        // sucesso: a batida esta salva la. Tratar como erro faria a fila
        // nunca esvaziar depois de um retry.
        const confirmadas = [...resposta.aceitas, ...resposta.duplicadas];
        await marcarEnviadas(confirmadas);
        enviadas += confirmadas.length;

        if (resposta.rejeitadas.length > 0) {
          await Promise.all(
            resposta.rejeitadas.map((r) => marcarErro([r.id], r.motivo)),
          );
          rejeitadas += resposta.rejeitadas.length;
        }
      } catch (e: any) {
        // Falha de rede nao vira status 'erro': a batida continua pendente e
        // tenta de novo na proxima oportunidade.
        await registrarTentativa(ids, e?.message ?? 'Falha ao enviar');
        return {
          status: 'falhou',
          enviadas,
          rejeitadas,
          mensagem: e?.message ?? 'Falha ao enviar',
        };
      }
    }

    return { status: 'ok', enviadas, rejeitadas };
  } finally {
    sincronizando = false;
  }
}
