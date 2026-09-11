package br.com.aurasoftware.ponto.service;

import br.com.aurasoftware.ponto.domain.Batida;
import br.com.aurasoftware.ponto.domain.TipoBatida;
import br.com.aurasoftware.ponto.repository.BatidaRepository;
import br.com.aurasoftware.ponto.web.dto.BatidaRequest;
import br.com.aurasoftware.ponto.web.dto.BatidaResponse;
import br.com.aurasoftware.ponto.web.dto.ResumoResponse;
import br.com.aurasoftware.ponto.web.dto.SincronizacaoRequest;
import br.com.aurasoftware.ponto.web.dto.SincronizacaoResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Deque;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Service
public class BatidaService {

    private static final Logger log = LoggerFactory.getLogger(BatidaService.class);

    /** Tolerancia para batidas "do futuro" antes de considerarmos o relogio suspeito. */
    private static final Duration TOLERANCIA_FUTURO = Duration.ofMinutes(5);

    /** Alem disso, recusamos de vez: provavel relogio quebrado. */
    private static final Duration LIMITE_FUTURO = Duration.ofHours(24);

    private final BatidaRepository repository;
    private final ZoneId zona;
    private final Duration jornadaDiaria;

    public BatidaService(BatidaRepository repository,
                         @Value("${ponto.timezone:America/Sao_Paulo}") String timezone,
                         @Value("${ponto.jornada-diaria:PT8H}") Duration jornadaDiaria) {
        this.repository = repository;
        this.zona = ZoneId.of(timezone);
        this.jornadaDiaria = jornadaDiaria;
    }

    /**
     * Recebe o lote de batidas pendentes do app.
     *
     * Idempotente por construcao: o id vem do dispositivo, entao reenviar o
     * mesmo lote nao duplica nada.
     */
    @Transactional
    public SincronizacaoResponse sincronizar(SincronizacaoRequest request) {
        List<UUID> aceitas = new ArrayList<>();
        List<UUID> duplicadas = new ArrayList<>();
        List<SincronizacaoResponse.ErroItem> rejeitadas = new ArrayList<>();

        OffsetDateTime agora = OffsetDateTime.now();

        for (BatidaRequest item : request.batidas()) {
            if (repository.existsById(item.id())) {
                duplicadas.add(item.id());
                continue;
            }

            if (item.ocorridoEm().isAfter(agora.plus(LIMITE_FUTURO))) {
                rejeitadas.add(new SincronizacaoResponse.ErroItem(
                        item.id(), "ocorridoEm mais de 24h no futuro — verifique o relogio do aparelho"));
                continue;
            }

            Batida batida = new Batida(
                    item.id(),
                    item.tipo(),
                    item.ocorridoEm(),
                    item.uptimeMs(),
                    item.origem(),
                    item.observacao(),
                    Boolean.TRUE.equals(item.manual()));

            repository.save(batida);
            aceitas.add(item.id());
        }

        log.info("Sincronizacao: {} aceitas, {} duplicadas, {} rejeitadas",
                aceitas.size(), duplicadas.size(), rejeitadas.size());

        return new SincronizacaoResponse(aceitas, duplicadas, rejeitadas);
    }

    /**
     * Ultima batida registrada. O app usa isso ao reinstalar/trocar de aparelho
     * para saber se o proximo toque e ENTRADA ou SAIDA.
     */
    @Transactional(readOnly = true)
    public Optional<BatidaResponse> ultima() {
        return repository.findTop1ByOrderByOcorridoEmDesc().stream()
                .findFirst()
                .map(b -> BatidaResponse.de(b, relogioSuspeito(b)));
    }

    @Transactional(readOnly = true)
    public List<BatidaResponse> listar(LocalDate inicio, LocalDate fim) {
        return buscar(inicio, fim).stream()
                .map(b -> BatidaResponse.de(b, relogioSuspeito(b)))
                .toList();
    }

    /**
     * Calcula horas trabalhadas no periodo, pareando ENTRADA com SAIDA.
     *
     * Suporta mais de um intervalo por dia (entrada/saida almoco/volta/saida
     * viram simplesmente dois pares).
     */
    @Transactional(readOnly = true)
    public ResumoResponse resumo(LocalDate inicio, LocalDate fim) {
        List<Batida> batidas = buscar(inicio, fim);

        Map<LocalDate, List<Batida>> porDia = new LinkedHashMap<>();
        for (Batida b : batidas) {
            LocalDate dia = b.getOcorridoEm().atZoneSameInstant(zona).toLocalDate();
            porDia.computeIfAbsent(dia, d -> new ArrayList<>()).add(b);
        }

        List<ResumoResponse.DiaResumo> dias = new ArrayList<>();
        long totalMinutos = 0;

        for (Map.Entry<LocalDate, List<Batida>> entry : porDia.entrySet()) {
            List<Batida> doDia = new ArrayList<>(entry.getValue());
            doDia.sort(Comparator.comparing(Batida::getOcorridoEm));

            long minutos = 0;
            boolean aberto = false;
            Deque<Batida> entradasPendentes = new ArrayDeque<>();

            for (Batida b : doDia) {
                if (b.getTipo() == TipoBatida.ENTRADA) {
                    entradasPendentes.push(b);
                } else if (!entradasPendentes.isEmpty()) {
                    Batida entrada = entradasPendentes.pop();
                    minutos += ChronoUnit.MINUTES.between(entrada.getOcorridoEm(), b.getOcorridoEm());
                }
            }
            if (!entradasPendentes.isEmpty()) {
                aberto = true;
            }

            long esperadoDia = ehDiaUtil(entry.getKey()) ? jornadaDiaria.toMinutes() : 0;

            dias.add(new ResumoResponse.DiaResumo(
                    entry.getKey(),
                    minutos,
                    formatar(minutos),
                    minutos - esperadoDia,
                    aberto,
                    doDia.stream().map(b -> BatidaResponse.de(b, relogioSuspeito(b))).toList()));

            totalMinutos += minutos;
        }

        long esperado = contarDiasUteis(inicio, fim) * jornadaDiaria.toMinutes();
        long saldo = totalMinutos - esperado;

        return new ResumoResponse(
                inicio, fim, totalMinutos, esperado, saldo,
                formatar(totalMinutos), formatar(saldo), dias);
    }

    private List<Batida> buscar(LocalDate inicio, LocalDate fim) {
        OffsetDateTime de = inicio.atStartOfDay(zona).toOffsetDateTime();
        OffsetDateTime ate = fim.plusDays(1).atStartOfDay(zona).toOffsetDateTime();
        return repository.findByOcorridoEmBetweenOrderByOcorridoEmAsc(de, ate);
    }

    /**
     * Heuristica simples: se o aparelho afirma que a batida aconteceu depois do
     * momento em que o servidor recebeu (fora da tolerancia), o relogio local
     * estava adiantado.
     */
    private boolean relogioSuspeito(Batida b) {
        return b.getOcorridoEm().isAfter(b.getRecebidoEm().plus(TOLERANCIA_FUTURO));
    }

    private boolean ehDiaUtil(LocalDate data) {
        return switch (data.getDayOfWeek()) {
            case SATURDAY, SUNDAY -> false;
            default -> true;
        };
    }

    private long contarDiasUteis(LocalDate inicio, LocalDate fim) {
        long total = 0;
        for (LocalDate d = inicio; !d.isAfter(fim); d = d.plusDays(1)) {
            if (ehDiaUtil(d)) {
                total++;
            }
        }
        return total;
    }

    private String formatar(long minutos) {
        String sinal = minutos < 0 ? "-" : "";
        long abs = Math.abs(minutos);
        return "%s%dh %02dmin".formatted(sinal, abs / 60, abs % 60);
    }
}
