package br.com.aurasoftware.ponto.web.dto;

import br.com.aurasoftware.ponto.domain.Batida;
import br.com.aurasoftware.ponto.domain.TipoBatida;

import java.time.OffsetDateTime;
import java.util.UUID;

public record BatidaResponse(
        UUID id,
        TipoBatida tipo,
        OffsetDateTime ocorridoEm,
        OffsetDateTime recebidoEm,
        String origem,
        String observacao,
        boolean manual,
        OffsetDateTime ajustadoEm,
        boolean relogioSuspeito
) {
    public static BatidaResponse de(Batida b, boolean relogioSuspeito) {
        return new BatidaResponse(
                b.getId(), b.getTipo(), b.getOcorridoEm(), b.getRecebidoEm(),
                b.getOrigem(), b.getObservacao(), b.isManual(), b.getAjustadoEm(),
                relogioSuspeito);
    }
}
