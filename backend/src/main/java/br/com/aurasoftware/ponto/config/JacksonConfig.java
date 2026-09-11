package br.com.aurasoftware.ponto.config;

import com.fasterxml.jackson.databind.SerializationFeature;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.TimeZone;

@Configuration
public class JacksonConfig {

    /**
     * Datas como ISO-8601 (2026-09-10T08:31:00-03:00) em vez de array de numeros.
     * Sem isso o app precisa de parser especial.
     */
    @Bean
    public Jackson2ObjectMapperBuilderCustomizer datasComoIso() {
        return builder -> builder.featuresToDisable(
                SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    }

    /**
     * Sai no fuso do ponto, nao em UTC.
     *
     * O banco guarda instante (TIMESTAMPTZ) e o Hibernate le em UTC, entao sem
     * isto a resposta traria "2026-09-10T10:45:00Z" para uma batida das 07:45.
     * O app mostra a hora lendo o proprio texto ISO — e o mesmo texto define o
     * dia a que a batida pertence —, entao a resposta precisa vir ja no fuso em
     * que o servidor agrupa os dias.
     */
    @Bean
    public Jackson2ObjectMapperBuilderCustomizer fusoDoPonto(
            @Value("${ponto.timezone:America/Sao_Paulo}") String timezone) {
        return builder -> builder.timeZone(TimeZone.getTimeZone(timezone));
    }
}
