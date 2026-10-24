import * as SQLite from 'expo-sqlite';
import * as Crypto from 'expo-crypto';
import { AcaoAjuste, AjustePendente, Batida, ResumoMes, StatusSync, TipoBatida } from './tipos';
import { formatarIso, inicioDoDiaIso } from './tempo';

/**
 * Banco local. Esta e a fonte da verdade do app.
 *
 * A batida e gravada aqui PRIMEIRO, sempre, e o envio ao servidor e um passo
 * separado que pode falhar quantas vezes for. O usuario nunca depende de rede
 * para bater o ponto.
 */

let db: SQLite.SQLiteDatabase | null = null;

/** Momento em que esta sessao do app comecou, em relogio monotonico. */
const inicioSessao = Date.now();

function monotonicoAgora(): number {
  // performance.now() nao anda para tras se o usuario mexer no relogio do
  // aparelho — e por isso que ele vai junto com a batida.
  if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
    return Math.round(performance.now());
  }
  return Date.now() - inicioSessao;
}

export async function abrir(): Promise<SQLite.SQLiteDatabase> {
  if (db) return db;

  db = await SQLite.openDatabaseAsync('ponto.db');

  await db.execAsync(`
    PRAGMA journal_mode = WAL;

    CREATE TABLE IF NOT EXISTS batida (
      id             TEXT PRIMARY KEY NOT NULL,
      tipo           TEXT NOT NULL,
      ocorrido_em    TEXT NOT NULL,
      monotonico_ms  INTEGER,
      origem         TEXT,
      observacao     TEXT,
      manual         INTEGER NOT NULL DEFAULT 0,
      status         TEXT NOT NULL DEFAULT 'pendente',
      tentativas     INTEGER NOT NULL DEFAULT 0,
      ultimo_erro    TEXT,
      enviado_em     TEXT
    );

    CREATE INDEX IF NOT EXISTS ix_batida_ocorrido ON batida (ocorrido_em);
    CREATE INDEX IF NOT EXISTS ix_batida_status   ON batida (status);

    -- Fila de correcoes de batidas que o servidor JA tem. Tabela separada de
    -- batida porque a linha da batida e apagada do celular depois de
    -- sincronizar — a correcao precisa sobreviver a essa limpeza.
    CREATE TABLE IF NOT EXISTS ajuste (
      id           TEXT PRIMARY KEY NOT NULL,   -- id da batida no servidor
      acao         TEXT NOT NULL,               -- 'editar' | 'apagar'
      ocorrido_em  TEXT,
      tipo         TEXT,
      criado_em    TEXT NOT NULL,
      tentativas   INTEGER NOT NULL DEFAULT 0,
      ultimo_erro  TEXT
    );

    -- Ultima resposta do /resumo por mes, para o Historico abrir com conteudo
    -- mesmo sem rede. E so cache: a fonte da verdade do passado e o servidor.
    CREATE TABLE IF NOT EXISTS cache_resumo (
      mes        TEXT PRIMARY KEY NOT NULL,     -- YYYY-MM
      json       TEXT NOT NULL,
      buscado_em TEXT NOT NULL
    );
  `);

  return db;
}

function paraBatida(linha: any): Batida {
  return {
    id: linha.id,
    tipo: linha.tipo as TipoBatida,
    ocorridoEm: linha.ocorrido_em,
    monotonicoMs: linha.monotonico_ms,
    origem: linha.origem,
    observacao: linha.observacao,
    manual: linha.manual === 1,
    status: linha.status as StatusSync,
    tentativas: linha.tentativas,
    ultimoErro: linha.ultimo_erro,
    enviadoEm: linha.enviado_em,
  };
}

/** Data/hora local em ISO-8601 preservando o offset (ex: -03:00). */
function agoraIso(): string {
  return formatarIso(new Date());
}

export async function registrarBatida(
  tipo: TipoBatida,
  opcoes: { origem?: string; observacao?: string; manual?: boolean; ocorridoEm?: string } = {},
): Promise<Batida> {
  const conexao = await abrir();

  const batida: Batida = {
    id: Crypto.randomUUID(),
    tipo,
    ocorridoEm: opcoes.ocorridoEm ?? agoraIso(),
    monotonicoMs: monotonicoAgora(),
    origem: opcoes.origem ?? 'iphone',
    observacao: opcoes.observacao ?? null,
    manual: opcoes.manual ?? false,
    status: 'pendente',
    tentativas: 0,
    ultimoErro: null,
    enviadoEm: null,
  };

  await conexao.runAsync(
    `INSERT INTO batida (id, tipo, ocorrido_em, monotonico_ms, origem, observacao, manual, status)
     VALUES (?, ?, ?, ?, ?, ?, ?, 'pendente')`,
    batida.id, batida.tipo, batida.ocorridoEm, batida.monotonicoMs,
    batida.origem, batida.observacao, batida.manual ? 1 : 0,
  );

  return batida;
}

export async function ultimaBatida(): Promise<Batida | null> {
  const conexao = await abrir();
  const linha = await conexao.getFirstAsync<any>(
    `SELECT * FROM batida ORDER BY ocorrido_em DESC LIMIT 1`,
  );
  return linha ? paraBatida(linha) : null;
}

/** Tudo que ainda nao foi confirmado pelo servidor. */
export async function pendentes(limite = 500): Promise<Batida[]> {
  const conexao = await abrir();
  const linhas = await conexao.getAllAsync<any>(
    `SELECT * FROM batida
      WHERE status IN ('pendente', 'erro')
      ORDER BY ocorrido_em ASC
      LIMIT ?`,
    limite,
  );
  return linhas.map(paraBatida);
}

export async function contarPendentes(): Promise<number> {
  const conexao = await abrir();
  const linha = await conexao.getFirstAsync<{ total: number }>(
    `SELECT COUNT(*) AS total FROM batida WHERE status IN ('pendente', 'erro')`,
  );
  return linha?.total ?? 0;
}

export async function marcarEnviadas(ids: string[]): Promise<void> {
  if (ids.length === 0) return;
  const conexao = await abrir();
  const marcadores = ids.map(() => '?').join(',');
  await conexao.runAsync(
    `UPDATE batida
        SET status = 'enviado', enviado_em = ?, ultimo_erro = NULL
      WHERE id IN (${marcadores})`,
    agoraIso(), ...ids,
  );
}

export async function marcarErro(ids: string[], motivo: string): Promise<void> {
  if (ids.length === 0) return;
  const conexao = await abrir();
  const marcadores = ids.map(() => '?').join(',');
  await conexao.runAsync(
    `UPDATE batida
        SET status = 'erro', tentativas = tentativas + 1, ultimo_erro = ?
      WHERE id IN (${marcadores})`,
    motivo, ...ids,
  );
}

/** Incrementa tentativa sem marcar erro definitivo — falha de rede e temporaria. */
export async function registrarTentativa(ids: string[], motivo: string): Promise<void> {
  if (ids.length === 0) return;
  const conexao = await abrir();
  const marcadores = ids.map(() => '?').join(',');
  await conexao.runAsync(
    `UPDATE batida
        SET tentativas = tentativas + 1, ultimo_erro = ?
      WHERE id IN (${marcadores})`,
    motivo, ...ids,
  );
}

export async function batidasEntre(inicioIso: string, fimIso: string): Promise<Batida[]> {
  const conexao = await abrir();
  const linhas = await conexao.getAllAsync<any>(
    `SELECT * FROM batida
      WHERE ocorrido_em >= ? AND ocorrido_em < ?
      ORDER BY ocorrido_em ASC`,
    inicioIso, fimIso,
  );
  return linhas.map(paraBatida);
}

/**
 * Tira a linha do banco local.
 *
 * Se a batida ja tiver sido confirmada pelo servidor, quem chama precisa ter
 * enfileirado um ajuste 'apagar' ANTES — some do celular e continuar la seria
 * divergencia silenciosa entre os dois bancos.
 */
export async function apagarBatida(id: string): Promise<void> {
  const conexao = await abrir();
  await conexao.runAsync(`DELETE FROM batida WHERE id = ?`, id);
}

export async function buscarBatida(id: string): Promise<Batida | null> {
  const conexao = await abrir();
  const linha = await conexao.getFirstAsync<any>(`SELECT * FROM batida WHERE id = ?`, id);
  return linha ? paraBatida(linha) : null;
}

/**
 * Reescreve a linha local com o valor corrigido.
 *
 * O status decide quem leva a correcao ao servidor. Batida que ainda nao foi
 * enviada volta para a fila e o proprio POST ja carrega o valor novo. Batida ja
 * confirmada continua 'enviado': quem corrige o servidor e o PATCH da fila de
 * ajustes, nao um reenvio — o POST /lote ignoraria o id por ja existir la.
 *
 * Reescrever mesmo assim importa porque a tela Hoje le daqui: sem isso, a hora
 * velha ficaria na tela e no total do dia ate a proxima sincronizacao.
 */
export async function corrigirBatidaLocal(
  id: string,
  mudancas: { ocorridoEm?: string; tipo?: TipoBatida },
): Promise<void> {
  const conexao = await abrir();
  await conexao.runAsync(
    `UPDATE batida
        SET ocorrido_em = COALESCE(?, ocorrido_em),
            tipo        = COALESCE(?, tipo),
            manual      = 1,
            status      = CASE WHEN status = 'enviado' THEN 'enviado' ELSE 'pendente' END,
            ultimo_erro = NULL
      WHERE id = ?`,
    mudancas.ocorridoEm ?? null, mudancas.tipo ?? null, id,
  );
}

/* ------------------------------------------------------------------ ajustes */

function paraAjuste(linha: any): AjustePendente {
  return {
    id: linha.id,
    acao: linha.acao as AcaoAjuste,
    ocorridoEm: linha.ocorrido_em,
    tipo: linha.tipo as TipoBatida | null,
    criadoEm: linha.criado_em,
    tentativas: linha.tentativas,
    ultimoErro: linha.ultimo_erro,
  };
}

/**
 * Enfileira a correcao de uma batida que ja esta no servidor.
 *
 * INSERT OR REPLACE: corrigir a hora duas vezes antes de sincronizar deixa so a
 * ultima versao na fila, e um 'apagar' posterior simplesmente substitui o
 * 'editar' — nao faz sentido ajustar a hora de algo que vai deixar de existir.
 */
export async function enfileirarAjuste(
  id: string,
  acao: AcaoAjuste,
  mudancas: { ocorridoEm?: string; tipo?: TipoBatida } = {},
): Promise<void> {
  const conexao = await abrir();
  await conexao.runAsync(
    `INSERT OR REPLACE INTO ajuste (id, acao, ocorrido_em, tipo, criado_em, tentativas, ultimo_erro)
     VALUES (?, ?, ?, ?, ?, 0, NULL)`,
    id, acao,
    acao === 'apagar' ? null : mudancas.ocorridoEm ?? null,
    acao === 'apagar' ? null : mudancas.tipo ?? null,
    agoraIso(),
  );
}

export async function ajustesPendentes(): Promise<AjustePendente[]> {
  const conexao = await abrir();
  const linhas = await conexao.getAllAsync<any>(
    `SELECT * FROM ajuste ORDER BY criado_em ASC`,
  );
  return linhas.map(paraAjuste);
}

export async function contarAjustes(): Promise<number> {
  const conexao = await abrir();
  const linha = await conexao.getFirstAsync<{ total: number }>(
    `SELECT COUNT(*) AS total FROM ajuste`,
  );
  return linha?.total ?? 0;
}

export async function removerAjuste(id: string): Promise<void> {
  const conexao = await abrir();
  await conexao.runAsync(`DELETE FROM ajuste WHERE id = ?`, id);
}

export async function registrarErroAjuste(id: string, motivo: string): Promise<void> {
  const conexao = await abrir();
  await conexao.runAsync(
    `UPDATE ajuste SET tentativas = tentativas + 1, ultimo_erro = ? WHERE id = ?`,
    motivo, id,
  );
}

/* ------------------------------------------------------------------ limpeza */

/**
 * Limpa do celular o que o servidor ja confirmou. Roda no fim de cada
 * sincronizacao bem-sucedida, entao na pratica acontece uma vez por dia:
 * passada a virada, o dia anterior sai daqui e so existe no servidor.
 *
 * O que NAO sai:
 *   - o dia de hoje, senao a tela Hoje perderia o cronometro e as marcacoes;
 *   - um turno em aberto, mesmo que tenha comecado ontem — sem a ENTRADA o app
 *     acharia que voce esta fora de turno e o proximo toque seria ENTRADA de
 *     novo, no meio do expediente;
 *   - batidas com correcao na fila, que ainda precisam do id por perto.
 */
export async function limparSincronizadas(): Promise<number> {
  const conexao = await abrir();

  let corte = inicioDoDiaIso(new Date());

  const ultima = await ultimaBatida();
  if (ultima?.tipo === 'ENTRADA' && ultima.ocorridoEm < corte) {
    corte = ultima.ocorridoEm;
  }

  const resultado = await conexao.runAsync(
    `DELETE FROM batida
      WHERE status = 'enviado'
        AND ocorrido_em < ?
        AND id NOT IN (SELECT id FROM ajuste)`,
    corte,
  );

  return resultado.changes ?? 0;
}

/* -------------------------------------------------------------------- cache */

export async function salvarCacheResumo(mes: string, resumo: ResumoMes): Promise<void> {
  const conexao = await abrir();
  await conexao.runAsync(
    `INSERT OR REPLACE INTO cache_resumo (mes, json, buscado_em) VALUES (?, ?, ?)`,
    mes, JSON.stringify(resumo), agoraIso(),
  );
}

export async function lerCacheResumo(
  mes: string,
): Promise<{ resumo: ResumoMes; buscadoEm: string } | null> {
  const conexao = await abrir();
  const linha = await conexao.getFirstAsync<{ json: string; buscado_em: string }>(
    `SELECT json, buscado_em FROM cache_resumo WHERE mes = ?`,
    mes,
  );
  if (!linha) return null;

  try {
    return { resumo: JSON.parse(linha.json) as ResumoMes, buscadoEm: linha.buscado_em };
  } catch {
    // Cache corrompido nao pode derrubar a tela — o refresh busca de novo.
    return null;
  }
}

export { agoraIso };
