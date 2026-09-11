package br.com.aurasoftware.ponto.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * Registro de batida de ponto.
 *
 * O id e gerado NO DISPOSITIVO (UUID v4), nao no servidor. Essa e a chave da
 * idempotencia: se a requisicao chegar duas vezes (retry apos timeout, por
 * exemplo), o segundo POST simplesmente reconhece o registro existente em vez
 * de criar uma duplicata.
 */
@Entity
@Table(name = "batida")
public class Batida {

    @Id
    @Column(name = "id", nullable = false, updatable = false)
    private UUID id;

    /**
     * Enum mapeado como VARCHAR de proposito. Tipos enum nativos do Postgres
     * exigem cuidado extra com o naming do Hibernate; VARCHAR + EnumType.STRING
     * evita a dor de cabeca e nao custa nada aqui.
     */
    @Enumerated(EnumType.STRING)
    @Column(name = "tipo", nullable = false, length = 20)
    private TipoBatida tipo;

    /** Momento da batida segundo o relogio do iPhone. */
    @Column(name = "ocorrido_em", nullable = false)
    private OffsetDateTime ocorridoEm;

    /** Momento em que o servidor recebeu. Trilha de auditoria. */
    @Column(name = "recebido_em", nullable = false)
    private OffsetDateTime recebidoEm;

    /**
     * Milissegundos desde o boot do device no instante da batida.
     * Serve para detectar relogio alterado manualmente: a relacao entre
     * ocorridoEm e uptimeMs deve ser monotonica dentro de uma mesma sessao.
     */
    @Column(name = "uptime_ms")
    private Long uptimeMs;

    /** Identificador do aparelho que originou a batida. */
    @Column(name = "origem", length = 100)
    private String origem;

    @Column(name = "observacao", length = 500)
    private String observacao;

    /** True quando foi inserida manualmente (correcao/esquecimento). */
    @Column(name = "manual", nullable = false)
    private boolean manual = false;

    protected Batida() {
        // JPA
    }

    public Batida(UUID id, TipoBatida tipo, OffsetDateTime ocorridoEm, Long uptimeMs,
                  String origem, String observacao, boolean manual) {
        this.id = id;
        this.tipo = tipo;
        this.ocorridoEm = ocorridoEm;
        this.uptimeMs = uptimeMs;
        this.origem = origem;
        this.observacao = observacao;
        this.manual = manual;
        this.recebidoEm = OffsetDateTime.now();
    }

    public UUID getId() {
        return id;
    }

    public TipoBatida getTipo() {
        return tipo;
    }

    public OffsetDateTime getOcorridoEm() {
        return ocorridoEm;
    }

    public OffsetDateTime getRecebidoEm() {
        return recebidoEm;
    }

    public Long getUptimeMs() {
        return uptimeMs;
    }

    public String getOrigem() {
        return origem;
    }

    public String getObservacao() {
        return observacao;
    }

    public boolean isManual() {
        return manual;
    }
}
