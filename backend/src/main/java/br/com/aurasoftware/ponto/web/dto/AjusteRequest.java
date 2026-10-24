package br.com.aurasoftware.ponto.web.dto;

import br.com.aurasoftware.ponto.domain.TipoBatida;
import jakarta.validation.constraints.Size;

import java.time.OffsetDateTime;

/**
 * Correcao de uma batida que ja esta no servidor.
 *
 * Todos os campos sao opcionais: o que vier nulo fica como estava. Na pratica o
 * app quase sempre manda so ocorridoEm — corrigir a hora e o caso comum.
 */
public record AjusteRequest(

        OffsetDateTime ocorridoEm,

        TipoBatida tipo,

        @Size(max = 500)
        String observacao
) {
    public boolean vazio() {
        return ocorridoEm == null && tipo == null && observacao == null;
    }
}
