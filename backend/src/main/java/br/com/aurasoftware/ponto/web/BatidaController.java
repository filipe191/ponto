package br.com.aurasoftware.ponto.web;

import br.com.aurasoftware.ponto.service.BatidaService;
import br.com.aurasoftware.ponto.web.dto.AjusteRequest;
import br.com.aurasoftware.ponto.web.dto.BatidaResponse;
import br.com.aurasoftware.ponto.web.dto.ResumoResponse;
import br.com.aurasoftware.ponto.web.dto.SincronizacaoRequest;
import br.com.aurasoftware.ponto.web.dto.SincronizacaoResponse;
import jakarta.validation.Valid;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.time.YearMonth;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/pontos")
public class BatidaController {

    private final BatidaService service;

    public BatidaController(BatidaService service) {
        this.service = service;
    }

    /**
     * Endpoint principal. O app manda TODAS as batidas com status pendente.
     * Sempre em lote, mesmo que seja uma so — assim existe um caminho unico.
     */
    @PostMapping("/lote")
    public SincronizacaoResponse sincronizar(@Valid @RequestBody SincronizacaoRequest request) {
        return service.sincronizar(request);
    }

    /**
     * Corrige uma batida ja sincronizada (tela Corrigir do app). Campo ausente
     * no corpo fica como esta — normalmente vem so o ocorridoEm.
     */
    @PatchMapping("/{id}")
    public BatidaResponse ajustar(@PathVariable UUID id, @Valid @RequestBody AjusteRequest ajuste) {
        return service.ajustar(id, ajuste);
    }

    /** Apaga (logicamente) uma batida errada. */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> apagar(@PathVariable UUID id) {
        service.apagar(id);
        return ResponseEntity.noContent().build();
    }

    /** Usado pelo app na primeira abertura para saber o proximo tipo de batida. */
    @GetMapping("/ultima")
    public ResponseEntity<BatidaResponse> ultima() {
        return service.ultima()
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.noContent().build());
    }

    @GetMapping
    public List<BatidaResponse> listar(
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate inicio,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate fim) {
        return service.listar(inicio, fim);
    }

    /**
     * Resumo do mes: /api/pontos/resumo?mes=2026-09
     * Ou de um periodo livre: /api/pontos/resumo?inicio=2026-09-01&fim=2026-09-15
     */
    @GetMapping("/resumo")
    public ResumoResponse resumo(
            @RequestParam(required = false) String mes,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate inicio,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate fim) {

        if (mes != null && !mes.isBlank()) {
            YearMonth ym = YearMonth.parse(mes);
            return service.resumo(ym.atDay(1), ym.atEndOfMonth());
        }

        LocalDate hoje = LocalDate.now();
        LocalDate de = inicio != null ? inicio : hoje.withDayOfMonth(1);
        LocalDate ate = fim != null ? fim : hoje;
        return service.resumo(de, ate);
    }
}
