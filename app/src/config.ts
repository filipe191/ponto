import * as SecureStore from 'expo-secure-store';

/**
 * URL da API e chave ficam no Keychain do iOS, nao em AsyncStorage.
 */

export interface Config {
  urlApi: string;
  apiKey: string;
}

const CHAVE_URL = 'ponto.urlApi';
const CHAVE_API = 'ponto.apiKey';

export async function carregarConfig(): Promise<Config> {
  const [urlApi, apiKey] = await Promise.all([
    SecureStore.getItemAsync(CHAVE_URL),
    SecureStore.getItemAsync(CHAVE_API),
  ]);

  return {
    urlApi: urlApi ?? '',
    apiKey: apiKey ?? '',
  };
}

export async function salvarConfig(config: Config): Promise<void> {
  const url = config.urlApi.trim().replace(/\/+$/, '');
  await Promise.all([
    SecureStore.setItemAsync(CHAVE_URL, url),
    SecureStore.setItemAsync(CHAVE_API, config.apiKey.trim()),
  ]);
}

export function configCompleta(config: Config): boolean {
  return config.urlApi.length > 0 && config.apiKey.length > 0;
}
