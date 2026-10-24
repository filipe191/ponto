package br.com.aurasoftware.ponto.web.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;

import java.util.List;

/**
 * Lote de batidas pendentes enviadas pelo app quando a rede volta.
 */
public record SincronizacaoRequest(

        @NotEmpty(message = "envie ao menos uma batida")
        @Size(max = 500, message = "maximo de 500 batidas por lote")
        @Valid
        List<BatidaRequest> batidas
) {
}
