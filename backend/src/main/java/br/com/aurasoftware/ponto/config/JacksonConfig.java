package br.com.aurasoftware.ponto.config;

import com.fasterxml.jackson.databind.SerializationFeature;
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

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
}
