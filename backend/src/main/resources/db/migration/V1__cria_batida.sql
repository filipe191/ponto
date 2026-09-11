CREATE TABLE batida (
    id           UUID         PRIMARY KEY,
    tipo         VARCHAR(20)  NOT NULL,
    ocorrido_em  TIMESTAMPTZ  NOT NULL,
    recebido_em  TIMESTAMPTZ  NOT NULL,
    uptime_ms    BIGINT,
    origem       VARCHAR(100),
    observacao   VARCHAR(500),
    manual       BOOLEAN      NOT NULL DEFAULT FALSE,

    CONSTRAINT ck_batida_tipo CHECK (tipo IN ('ENTRADA', 'SAIDA'))
);

-- Consulta por periodo e o acesso dominante (resumo mensal, listagem do dia).
CREATE INDEX ix_batida_ocorrido_em ON batida (ocorrido_em);

COMMENT ON COLUMN batida.id IS 'UUID gerado no dispositivo — garante idempotencia no reenvio';
COMMENT ON COLUMN batida.ocorrido_em IS 'Momento da batida segundo o relogio do aparelho';
COMMENT ON COLUMN batida.recebido_em IS 'Momento em que o servidor gravou — trilha de auditoria';
COMMENT ON COLUMN batida.uptime_ms IS 'Milissegundos desde o boot do device; detecta relogio alterado';
