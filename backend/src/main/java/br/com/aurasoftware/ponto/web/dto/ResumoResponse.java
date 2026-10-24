package br.com.aurasoftware.ponto.web.dto;

import java.time.LocalDate;
import java.util.List;

/**
 * Resumo de horas de um periodo.
 *
 * saldoMinutos positivo = horas extras; negativo = horas devendo.
 */
public record ResumoResponse(
        LocalDate inicio,
        LocalDate fim,
        long trabalhadoMinutos,
        long esperadoMinutos,
        long saldoMinutos,
        String trabalhadoFormatado,
        String saldoFormatado,
        List<DiaResumo> dias
) {
    public record DiaResumo(
            LocalDate data,
            long trabalhadoMinutos,
            String trabalhadoFormatado,
            long saldoMinutos,
            boolean diaAberto,
            List<BatidaResponse> batidas
    ) {
    }
}
