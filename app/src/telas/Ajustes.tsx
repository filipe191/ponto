import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { cores, espaco, tipo } from '../theme';
import { EstadoPonto } from '../estado';
import { carregarConfig, salvarConfig } from '../config';
import { testarConexao } from '../api';

export function Ajustes({ estado }: { estado: EstadoPonto }) {
  const { naFila, correcoesNaFila, sincronizarAgora } = estado;

  const [urlApi, setUrlApi] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [retorno, setRetorno] = useState<{ ok: boolean; texto: string } | null>(null);

  useEffect(() => {
    carregarConfig().then((c) => {
      setUrlApi(c.urlApi);
      setApiKey(c.apiKey);
    });
  }, []);

  async function salvarETestar() {
    setOcupado(true);
    setRetorno(null);
    try {
      const config = { urlApi, apiKey };
      await salvarConfig(config);
      await testarConexao({ ...config, urlApi: urlApi.trim().replace(/\/+$/, '') });
      setRetorno({ ok: true, texto: 'Servidor respondeu. Configuração salva.' });
      sincronizarAgora();
    } catch (e: any) {
      setRetorno({ ok: false, texto: e?.message ?? 'Não foi possível falar com o servidor' });
    } finally {
      setOcupado(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={estilos.conteudo} keyboardShouldPersistTaps="handled">
        <Text style={estilos.rotulo}>Endereço do servidor</Text>
        <TextInput
          value={urlApi}
          onChangeText={setUrlApi}
          placeholder="http://100.x.x.x:8080"
          placeholderTextColor={cores.fora}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          style={estilos.campo}
        />
        <Text style={estilos.ajuda}>
          Endereço da API sem barra no final. Pelo Tailscale, use o IP da máquina onde o
          backend está rodando.
        </Text>

        <Text style={[estilos.rotulo, { marginTop: espaco.lg }]}>Chave de acesso</Text>
        <TextInput
          value={apiKey}
          onChangeText={setApiKey}
          placeholder="X-API-Key"
          placeholderTextColor={cores.fora}
          autoCapitalize="none"
          autoCorrect={false}
          secureTextEntry
          style={estilos.campo}
        />
        <Text style={estilos.ajuda}>
          A mesma definida em PONTO_API_KEY no servidor. Fica guardada no Keychain.
        </Text>

        <Pressable
          onPress={salvarETestar}
          disabled={ocupado}
          style={({ pressed }) => [estilos.botao, pressed && { opacity: 0.75 }]}
        >
          {ocupado
            ? <ActivityIndicator color="#0B1F18" />
            : <Text style={estilos.botaoTexto}>Salvar e testar</Text>}
        </Pressable>

        {retorno && (
          <Text style={[estilos.retorno, { color: retorno.ok ? cores.emTurno : cores.erro }]}>
            {retorno.texto}
          </Text>
        )}

        <View style={estilos.caixaFila}>
          <Text style={estilos.tituloFila}>Fila de envio</Text>
          <Text style={estilos.textoFila}>
            {naFila === 0
              ? 'Tudo sincronizado.'
              : `${naFila} ${naFila === 1 ? 'batida aguarda' : 'batidas aguardam'} envio. Ficam salvas no aparelho até o servidor confirmar.`}
          </Text>

          {correcoesNaFila > 0 && (
            <Text style={[estilos.textoFila, { marginTop: espaco.sm }]}>
              {correcoesNaFila === 1
                ? '1 correção feita na aba Corrigir ainda não chegou ao servidor.'
                : `${correcoesNaFila} correções feitas na aba Corrigir ainda não chegaram ao servidor.`}
            </Text>
          )}

          {(naFila > 0 || correcoesNaFila > 0) && (
            <Pressable onPress={() => sincronizarAgora()}>
              <Text style={estilos.link}>Tentar enviar agora</Text>
            </Pressable>
          )}
        </View>

        <View style={estilos.caixaFila}>
          <Text style={estilos.tituloFila}>Armazenamento</Text>
          <Text style={estilos.textoFila}>
            Depois de cada sincronização o aparelho apaga o que o servidor já
            confirmou. Ficam aqui apenas o dia de hoje, um turno em aberto e o
            que ainda não foi enviado — o histórico completo você vê na aba
            Histórico, direto do servidor.
          </Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const estilos = StyleSheet.create({
  conteudo: {
    padding: espaco.lg,
  },
  rotulo: {
    ...tipo.titulo,
    color: cores.texto,
    marginBottom: espaco.sm,
  },
  campo: {
    backgroundColor: cores.superficie,
    borderRadius: 12,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: cores.borda,
    paddingHorizontal: espaco.md,
    paddingVertical: 14,
    color: cores.texto,
    fontSize: 16,
  },
  ajuda: {
    ...tipo.legenda,
    color: cores.textoFraco,
    marginTop: espaco.sm,
    lineHeight: 19,
  },
  botao: {
    marginTop: espaco.xl,
    backgroundColor: cores.emTurno,
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: 'center',
  },
  botaoTexto: {
    ...tipo.titulo,
    color: '#0B1F18',
  },
  retorno: {
    ...tipo.legenda,
    marginTop: espaco.md,
    textAlign: 'center',
  },
  caixaFila: {
    marginTop: espaco.xl,
    padding: espaco.md,
    borderRadius: 14,
    backgroundColor: cores.superficie,
  },
  tituloFila: {
    ...tipo.titulo,
    color: cores.texto,
    marginBottom: espaco.sm,
  },
  textoFila: {
    ...tipo.legenda,
    color: cores.textoFraco,
    lineHeight: 19,
  },
  link: {
    ...tipo.legenda,
    color: cores.emTurno,
    marginTop: espaco.md,
  },
});
