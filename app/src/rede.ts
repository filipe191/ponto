import NetInfo from '@react-native-community/netinfo';

/**
 * Existe alguma interface de rede agora?
 *
 * Olha SO o isConnected, de proposito — nao o isInternetReachable. O servidor
 * do ponto normalmente mora no Tailscale ou na propria LAN, entao um Wi-Fi sem
 * saida para a internet ainda alcanca a API. Descartar esse caso faria o app
 * se recusar a sincronizar justamente em casa.
 *
 * O que isto evita e o caso sem duvida: modo aviao, sem Wi-Fi e sem celular.
 * Ai nao ha o que tentar, e esperar o timeout do HTTP e so tempo perdido.
 *
 * Nao substitui o tratamento de erro de quem chama: estar conectado a uma rede
 * nao garante que o servidor responda.
 */
export async function temRede(): Promise<boolean> {
  try {
    const estado = await NetInfo.fetch();
    return estado.isConnected === true;
  } catch {
    // Se nem da para perguntar, deixa tentar — a falha de rede ja e tratada.
    return true;
  }
}
