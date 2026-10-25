import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { buscarSolicitacoes } from '../api';
import { carregarConfig, configCompleta } from '../config';
import { temRede } from '../rede';
import { dataAmigavel, dataLocal, horaLocal } from '../tempo';
import { Solicitacao } from '../tipos';
import { Cartao, Linha, Texto, cores, espaco, raio } from '../ui';

/**
 * "Seus pedidos": o que foi pedido ao administrador pelo app e a decisao dele.
 *
 * Sem isto, o funcionario so descobria o resultado vendo a batida aparecer (ou
 * nao) no resumo, e nunca ficava sabendo o motivo de uma recusa.
 *
 * `atualizar` muda quando a tela Corrigir recarrega, para a lista acompanhar.
 */
export function MeusPedidos({ atualizar }: { atualizar: unknown }) {
  const [pedidos, setPedidos] = useState<Solicitacao[] | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const config = await carregarConfig();
      if (!configCompleta(config) || !(await temRede())) {
        setAviso('Sem conexão: os pedidos aparecem quando houver rede.');
        return;
      }
      setPedidos(await buscarSolicitacoes(config));
      setAviso(null);
    } catch (e: any) {
      setAviso(`${e?.message ?? 'Servidor fora de alcance'}: não deu para buscar os pedidos.`);
    }
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar, atualizar]);

  return (
    <View style={estilos.bloco}>
      <Texto variante="titulo">Seus pedidos ao administrador</Texto>
      <Texto variante="legenda" tom="fraco" style={estilos.ajuda}>
        Batidas esquecidas e correções de dias anteriores só valem depois de aprovadas.
      </Texto>

      {aviso && <Texto variante="legenda" tom="pendente">{aviso}</Texto>}

      {pedidos && pedidos.length === 0 && (
        <Texto variante="legenda" tom="fraco">Nenhum pedido nos últimos 90 dias.</Texto>
      )}

      {pedidos && pedidos.length > 0 && (
        <Cartao>
          {pedidos.map((p, i) => (
            <Linha key={p.id} ultima={i === pedidos.length - 1} style={estilos.linha}>
              <View style={estilos.texto}>
                <Texto>{descricao(p)}</Texto>
                <Texto variante="legenda" tom="fraco">
                  pedido {dataAmigavel(dataLocal(p.pedidoEm)).toLowerCase()} às {horaLocal(p.pedidoEm)}
                  {p.decididoEm ? ` · decidido ${dataAmigavel(dataLocal(p.decididoEm)).toLowerCase()}` : ''}
                </Texto>
                {p.motivoDecisao ? (
                  <Texto variante="legenda" tom={p.status === 'recusada' ? 'erro' : 'fraco'}>
                    {p.status === 'recusada' ? 'Motivo: ' : 'Obs.: '}{p.motivoDecisao}
                  </Texto>
                ) : null}
              </View>
              <View style={[estilos.selo, { borderColor: COR[p.status] }]}>
                <Texto variante="legenda" style={{ color: COR[p.status] }}>{ROTULO[p.status]}</Texto>
              </View>
            </Linha>
          ))}
        </Cartao>
      )}
    </View>
  );
}

const ROTULO = { pendente: 'aguardando', aprovada: 'aprovado', recusada: 'recusado' } as const;
const COR = { pendente: cores.pendente, aprovada: cores.emTurno, recusada: cores.erro } as const;

function descricao(p: Solicitacao): string {
  const tipo = p.tipo === 'SAIDA' ? 'saída' : 'entrada';
  const quando = (iso: string | null) => (iso ? `${dataAmigavel(dataLocal(iso)).toLowerCase()} às ${horaLocal(iso)}` : '');
  if (p.acao === 'incluir') return `Incluir ${tipo} de ${quando(p.ocorridoEm)}`;
  if (p.acao === 'excluir') return `Excluir ${tipo} de ${quando(p.ocorridoEm)}`;
  return `Corrigir ${quando(p.horarioAtual)} para ${tipo} às ${p.ocorridoEm ? horaLocal(p.ocorridoEm) : '—'}`;
}

const estilos = StyleSheet.create({
  bloco: {
    marginTop: espaco.xl,
    gap: espaco.sm,
  },
  ajuda: {
    marginBottom: espaco.xs,
  },
  linha: {
    alignItems: 'flex-start',
  },
  texto: {
    flex: 1,
    gap: 2,
  },
  selo: {
    borderWidth: 1,
    borderRadius: raio.total,
    paddingHorizontal: espaco.sm,
    paddingVertical: 2,
  },
});
