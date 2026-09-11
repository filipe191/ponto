package br.com.aurasoftware.ponto.web.dto;

import br.com.aurasoftware.ponto.domain.TipoBatida;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * Uma batida vinda do app. O id vem do dispositivo.
 */
public record BatidaRequest(

        @NotNull(message = "id e obrigatorio (UUID gerado no dispositivo)")
        UUID id,

        @NotNull(message = "tipo e obrigatorio")
        TipoBatida tipo,

        @NotNull(message = "ocorridoEm e obrigatorio")
        OffsetDateTime ocorridoEm,

        Long uptimeMs,

        @Size(max = 100)
        String origem,

        @Size(max = 500)
        String observacao,

        Boolean manual
) {
}
