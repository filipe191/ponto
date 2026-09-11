import * as SQLite from 'expo-sqlite';
import * as Crypto from 'expo-crypto';
import { Batida, TipoBatida, StatusSync } from './tipos';
import { formatarIso } from './tempo';

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

export async function apagarBatida(id: string): Promise<void> {
  const conexao = await abrir();
  // Batida ja confirmada pelo servidor nao some so do celular — seria
  // divergencia silenciosa entre os dois bancos.
  await conexao.runAsync(`DELETE FROM batida WHERE id = ? AND status <> 'enviado'`, id);
}

export { agoraIso };
