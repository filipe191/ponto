package br.com.aurasoftware.ponto.web.dto;

import java.util.List;
import java.util.UUID;

/**
 * Resposta do lote. O app deve marcar como sincronizadas TODAS as batidas
 * listadas em aceitas + duplicadas — duplicada significa "ja estava salvo",
 * que e sucesso do ponto de vista do app.
 */
public record SincronizacaoResponse(
        List<UUID> aceitas,
        List<UUID> duplicadas,
        List<ErroItem> rejeitadas
) {
    public record ErroItem(UUID id, String motivo) {
    }
}
