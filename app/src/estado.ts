import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import NetInfo from '@react-native-community/netinfo';

import { ultimaDoServidor } from './api';
import { carregarConfig, configCompleta } from './config';
import {
  abrir,
  ajustesPendentes,
  apagarBatida,
  batidasEntre,
  buscarBatida,
  contarAjustes,
  contarPendentes,
  corrigirBatidaLocal,
  enfileirarAjuste,
  registrarBatida,
  ultimaBatida,
} from './db';
import { temRede } from './rede';
import { sincronizar } from './sync';
import { agruparPorDia, formatarIso } from './tempo';
import { AjustePendente, Batida, BatidaServidor, DiaTrabalhado, TipoBatida } from './tipos';

/**
 * Estado compartilhado do app. Concentra o ciclo carregar -> bater -> sincronizar
 * para que as telas so cuidem de desenhar.
 *
 * Depois que o celular passou a se limpar apos cada sincronizacao, o que vive
 * aqui e so o presente: o dia de hoje, um turno em aberto e o que ainda nao foi
 * confirmado pelo servidor. O passado mora no servidor e e a tela Historico que
 * vai busca-lo.
 */
export function useEstadoPonto() {
  const [pronto, setPronto] = useState(false);
  const [ultima, setUltima] = useState<Batida | null>(null);
  const [dias, setDias] = useState<DiaTrabalhado[]>([]);
  const [ajustes, setAjustes] = useState<AjustePendente[]>([]);
  const [naFila, setNaFila] = useState(0);
  const [correcoesNaFila, setCorrecoesNaFila] = useState(0);
  const [sincronizandoAgora, setSincronizando] = useState(false);
  const [avisoSync, setAvisoSync] = useState<string | null>(null);

  const emTurno = ultima?.tipo === 'ENTRADA';
  const proximoTipo: TipoBatida = emTurno ? 'SAIDA' : 'ENTRADA';

  /**
   * Pergunta ao servidor se ha turno em aberto. So faz sentido quando o banco
   * local esta vazio — manha seguinte a uma limpeza, ou app recem instalado.
   *
   * NUNCA e esperado por quem chama: a tela ja abriu com o que tinha. Esperar
   * esta resposta para desenhar a primeira tela prendia o app no spinner ate o
   * timeout do HTTP quando o servidor estava fora do ar.
   */
  const conferindo = useRef(false);
  const conferirTurnoNoServidor = useCallback(async () => {
    if (conferindo.current) return;
    conferindo.current = true;

    try {
      const remota = await ultimaRemota();
      if (!remota) return;

      // Se voce bateu o ponto enquanto a resposta vinha, o local manda.
      const local = await ultimaBatida();
      if (!local) setUltima(remota);
    } finally {
      conferindo.current = false;
    }
  }, []);

  /** So banco local. Rapido e sem rede — e isto que libera a primeira tela. */
  const recarregar = useCallback(async () => {
    const inicio = new Date();
    inicio.setDate(1);
    inicio.setHours(0, 0, 0, 0);

    const fim = new Date();
    fim.setDate(fim.getDate() + 1);
    fim.setHours(0, 0, 0, 0);

    const [batidas, ult, fila, correcoes, filaCorrecoes] = await Promise.all([
      batidasEntre(formatarIso(inicio), formatarIso(fim)),
      ultimaBatida(),
      contarPendentes(),
      ajustesPendentes(),
      contarAjustes(),
    ]);

    setDias(agruparPorDia(batidas));
    setAjustes(correcoes);
    setNaFila(fila);
    setCorrecoesNaFila(filaCorrecoes);
    setUltima(ult);

    if (!ult) {
      conferirTurnoNoServidor();   // sem await: a tela nao espera a rede
    }
  }, [conferirTurnoNoServidor]);

  const sincronizarAgora = useCallback(async () => {
    setSincronizando(true);
    try {
      const resultado = await sincronizar();

      if (resultado.status === 'falhou' || resultado.status === 'sem-config') {
        setAvisoSync(resultado.mensagem ?? 'Não foi possível sincronizar');
      } else {
        setAvisoSync(null);
      }

      await recarregar();
      return resultado;
    } finally {
      setSincronizando(false);
    }
  }, [recarregar]);

  /**
   * Grava local e SO DEPOIS tenta enviar. Se a rede estiver fora, a batida ja
   * esta salva e a interface ja atualizou — o envio fica para a fila.
   */
  const bater = useCallback(async (tipo?: TipoBatida) => {
    const escolhido = tipo ?? proximoTipo;
    await registrarBatida(escolhido);
    await recarregar();
    sincronizarAgora();          // sem await: a tela nao espera a rede
    return escolhido;
  }, [proximoTipo, recarregar, sincronizarAgora]);

  /** Marcacao que voce esqueceu de bater, em qualquer dia e hora. */
  const adicionarMarcacao = useCallback(async (tipo: TipoBatida, ocorridoEm: string) => {
    await registrarBatida(tipo, { ocorridoEm, manual: true, origem: 'ajuste-manual' });
    await recarregar();
    sincronizarAgora();
  }, [recarregar, sincronizarAgora]);

  /**
   * Corrige hora ou tipo de uma marcacao.
   *
   * Se ela ainda nao saiu do celular, e so reescrever a linha. Se o servidor ja
   * tem, vira uma correcao na fila — a tela mostra o novo valor na hora e o
   * PATCH sai na proxima sincronizacao.
   */
  const corrigirMarcacao = useCallback(async (
    id: string,
    mudancas: { ocorridoEm?: string; tipo?: TipoBatida },
  ) => {
    const local = await buscarBatida(id);

    // Servidor ja tem (ou a linha nem existe mais aqui): a correcao vira PATCH
    // na fila. Se a copia local tambem existir, ela e reescrita junto para que
    // a tela Hoje nao continue mostrando a hora antiga.
    if (!local || local.status === 'enviado') {
      await enfileirarAjuste(id, 'editar', mudancas);
    }
    if (local) {
      await corrigirBatidaLocal(id, mudancas);
    }

    await recarregar();
    sincronizarAgora();
  }, [recarregar, sincronizarAgora]);

  const apagarMarcacao = useCallback(async (id: string) => {
    const local = await buscarBatida(id);

    // Mesma logica do corrigir: o DELETE so entra na fila quando o servidor ja
    // tem a batida. A linha local sai de qualquer jeito — deixa-la ai faria a
    // marcacao apagada continuar contando no dia de hoje.
    if (!local || local.status === 'enviado') {
      await enfileirarAjuste(id, 'apagar');
    }
    await apagarBatida(id);

    await recarregar();
    sincronizarAgora();
  }, [recarregar, sincronizarAgora]);

  // Boot
  useEffect(() => {
    (async () => {
      await abrir();
      await recarregar();
      setPronto(true);
      sincronizarAgora();
    })();
  }, [recarregar, sincronizarAgora]);

  // Gatilho 1: app volta ao primeiro plano. No iOS este e o mais confiavel.
  const estadoAnterior = useRef<AppStateStatus>(AppState.currentState);
  useEffect(() => {
    const inscricao = AppState.addEventListener('change', (proximo) => {
      if (estadoAnterior.current.match(/inactive|background/) && proximo === 'active') {
        recarregar();
        sincronizarAgora();
      }
      estadoAnterior.current = proximo;
    });
    return () => inscricao.remove();
  }, [recarregar, sincronizarAgora]);

  // Gatilho 2: rede voltou com o app aberto. E o que faz a fila esvaziar sozinha
  // assim que voce reconecta, sem precisar abrir e fechar o app.
  const tinhaRede = useRef<boolean | null>(null);
  useEffect(() => {
    const remover = NetInfo.addEventListener((estado) => {
      // Mesma regra do rede.ts: so isConnected. O servidor costuma estar na LAN
      // ou no Tailscale, entao exigir internet de verdade faria o app ignorar
      // justamente a rede de casa.
      const conectado = estado.isConnected === true;
      if (tinhaRede.current === false && conectado) {
        sincronizarAgora();
      }
      tinhaRede.current = conectado;
    });
    return () => remover();
  }, [sincronizarAgora]);

  return {
    pronto,
    ultima,
    emTurno,
    proximoTipo,
    dias,
    ajustes,
    naFila,
    correcoesNaFila,
    pendencias: naFila + correcoesNaFila,
    sincronizandoAgora,
    avisoSync,
    bater,
    adicionarMarcacao,
    corrigirMarcacao,
    apagarMarcacao,
    recarregar,
    sincronizarAgora,
  };
}

/**
 * Ultima batida segundo o servidor, convertida para o formato local. Falha de
 * rede aqui nao e erro: so significa que o app segue com o que tem.
 */
async function ultimaRemota(): Promise<Batida | null> {
  try {
    const config = await carregarConfig();
    if (!configCompleta(config)) return null;
    if (!(await temRede())) return null;

    const remota = await ultimaDoServidor(config);
    return remota ? deServidor(remota) : null;
  } catch {
    return null;
  }
}

export function deServidor(b: BatidaServidor): Batida {
  return {
    id: b.id,
    tipo: b.tipo,
    ocorridoEm: b.ocorridoEm,
    monotonicoMs: null,
    origem: b.origem,
    observacao: b.observacao,
    manual: b.manual,
    status: 'enviado',
    tentativas: 0,
    ultimoErro: null,
    enviadoEm: null,
  };
}

export type EstadoPonto = ReturnType<typeof useEstadoPonto>;
