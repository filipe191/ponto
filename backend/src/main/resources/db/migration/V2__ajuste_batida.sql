-- Correcao de batida: o app passou a poder ajustar hora/tipo e remover uma
-- marcacao errada depois que ela ja foi sincronizada.

ALTER TABLE batida ADD COLUMN ajustado_em TIMESTAMPTZ;
ALTER TABLE batida ADD COLUMN apagado_em  TIMESTAMPTZ;

-- Exclusao e logica, nao fisica: o historico do ponto e trilha de auditoria, e
-- um DELETE de verdade tambem faria o id sumir do controle de idempotencia --
-- um reenvio antigo do app ressuscitaria a batida apagada.
CREATE INDEX ix_batida_vivas ON batida (ocorrido_em) WHERE apagado_em IS NULL;

COMMENT ON COLUMN batida.ajustado_em IS 'Ultima correcao manual de hora/tipo — NULL quando nunca foi mexida';
COMMENT ON COLUMN batida.apagado_em  IS 'Exclusao logica; linhas com valor aqui saem de toda consulta e de todo calculo';
