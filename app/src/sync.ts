import { ErroHttp, aplicarAjuste, enviarLote } from './api';
import { carregarConfig, configCompleta } from './config';
import {
  ajustesPendentes,
  limparSincronizadas,
  marcarEnviadas,
  marcarErro,
  pendentes,
  registrarErroAjuste,
  registrarTentativa,
  removerAjuste,
} from './db';

/**
 * Sincronizacao. Roda quando:
 *   1. o app volta para o primeiro plano  (cobre a maioria dos casos no iOS)
 *   2. a rede volta com o app aberto      (NetInfo)
 *   3. logo depois de bater o ponto       (caminho feliz)
 *
 * Nunca bloqueia a interface e nunca impede uma batida de ser registrada.
 *
 * A ordem importa: primeiro as batidas novas, depois as correcoes. Uma correcao
 * so entra na fila para batida que o servidor ja tem, mas se as duas coisas
 * acontecerem no mesmo ciclo offline, mandar a criacao antes evita um 404.
 * Por ultimo a limpeza do banco local.
 */

const TAMANHO_LOTE = 200;

export interface ResultadoSync {
  status: 'ok' | 'nada-a-fazer' | 'sem-config' | 'falhou';
  enviadas: number;
  rejeitadas: number;
  ajustadas: number;
  limpas: number;
  mensagem?: string;
}

let sincronizando = false;

export async function sincronizar(): Promise<ResultadoSync> {
  // Duas chamadas concorrentes tentariam enviar o mesmo lote. O servidor
  // aguentaria (e idempotente), mas nao ha motivo para gastar rede.
  if (sincronizando) {
    return { status: 'nada-a-fazer', enviadas: 0, rejeitadas: 0, ajustadas: 0, limpas: 0 };
  }

  sincronizando = true;
  try {
    const config = await carregarConfig();
    if (!configCompleta(config)) {
      return {
        status: 'sem-config',
        enviadas: 0,
        rejeitadas: 0,
        ajustadas: 0,
        limpas: 0,
        mensagem: 'Falta configurar o endereco do servidor',
      };
    }

    const fila = await pendentes();
    const correcoes = await ajustesPendentes();

    let enviadas = 0;
    let rejeitadas = 0;
    let ajustadas = 0;

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
          ajustadas,
          limpas: 0,
          mensagem: e?.message ?? 'Falha ao enviar',
        };
      }
    }

    for (const correcao of correcoes) {
      try {
        await aplicarAjuste(config, correcao);
        await removerAjuste(correcao.id);
        ajustadas++;
      } catch (e: any) {
        // 404: a batida nao existe mais la (apagada em outro momento). Nao ha
        // o que corrigir, entao a correcao sai da fila em vez de tentar para
        // sempre.
        if (e instanceof ErroHttp && e.status === 404) {
          await removerAjuste(correcao.id);
          continue;
        }

        await registrarErroAjuste(correcao.id, e?.message ?? 'Falha ao ajustar');

        // Recusa do servidor (400) fica na fila com o motivo a vista na tela
        // Corrigir — perder a correcao em silencio seria pior. Qualquer outra
        // falha e tratada como rede: para o ciclo e tenta depois.
        if (!(e instanceof ErroHttp) || e.status >= 500 || e.status === 401) {
          return {
            status: 'falhou',
            enviadas,
            rejeitadas,
            ajustadas,
            limpas: 0,
            mensagem: e?.message ?? 'Falha ao ajustar',
          };
        }
      }
    }

    // Chegou aqui: o servidor confirmou tudo que dava para confirmar. Agora o
    // celular pode se desfazer do que ja esta la.
    const limpas = await limparSincronizadas();

    if (enviadas === 0 && rejeitadas === 0 && ajustadas === 0 && limpas === 0) {
      return { status: 'nada-a-fazer', enviadas: 0, rejeitadas: 0, ajustadas: 0, limpas: 0 };
    }

    return { status: 'ok', enviadas, rejeitadas, ajustadas, limpas };
  } finally {
    sincronizando = false;
  }
}
