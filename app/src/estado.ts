import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import NetInfo from '@react-native-community/netinfo';

import { abrir, batidasEntre, contarPendentes, registrarBatida, ultimaBatida } from './db';
import { sincronizar } from './sync';
import { agruparPorDia, formatarIso } from './tempo';
import { Batida, DiaTrabalhado, TipoBatida } from './tipos';

/**
 * Estado compartilhado do app. Concentra o ciclo carregar -> bater -> sincronizar
 * para que as telas so cuidem de desenhar.
 */
export function useEstadoPonto() {
  const [pronto, setPronto] = useState(false);
  const [ultima, setUltima] = useState<Batida | null>(null);
  const [dias, setDias] = useState<DiaTrabalhado[]>([]);
  const [naFila, setNaFila] = useState(0);
  const [sincronizandoAgora, setSincronizando] = useState(false);
  const [avisoSync, setAvisoSync] = useState<string | null>(null);

  const emTurno = ultima?.tipo === 'ENTRADA';
  const proximoTipo: TipoBatida = emTurno ? 'SAIDA' : 'ENTRADA';

  const recarregar = useCallback(async () => {
    const inicio = new Date();
    inicio.setDate(1);
    inicio.setHours(0, 0, 0, 0);

    const fim = new Date();
    fim.setDate(fim.getDate() + 1);
    fim.setHours(0, 0, 0, 0);

    const [batidas, ult, fila] = await Promise.all([
      batidasEntre(formatarIso(inicio), formatarIso(fim)),
      ultimaBatida(),
      contarPendentes(),
    ]);

    setDias(agruparPorDia(batidas));
    setUltima(ult);
    setNaFila(fila);
  }, []);

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

  // Gatilho 2: rede voltou com o app aberto.
  const tinhaRede = useRef<boolean | null>(null);
  useEffect(() => {
    const remover = NetInfo.addEventListener((estado) => {
      const temRede = Boolean(estado.isConnected && estado.isInternetReachable !== false);
      if (tinhaRede.current === false && temRede) {
        sincronizarAgora();
      }
      tinhaRede.current = temRede;
    });
    return () => remover();
  }, [sincronizarAgora]);

  return {
    pronto,
    ultima,
    emTurno,
    proximoTipo,
    dias,
    naFila,
    sincronizandoAgora,
    avisoSync,
    bater,
    recarregar,
    sincronizarAgora,
  };
}

export type EstadoPonto = ReturnType<typeof useEstadoPonto>;
