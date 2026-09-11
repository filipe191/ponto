package br.com.aurasoftware.ponto.repository;

import br.com.aurasoftware.ponto.domain.Batida;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface BatidaRepository extends JpaRepository<Batida, UUID> {

    /**
     * Consultas de leitura ignoram o que foi apagado. Ja o existsById herdado
     * continua enxergando tudo, de proposito: uma batida apagada nao pode
     * voltar porque o app reenviou um lote antigo com o mesmo id.
     */
    List<Batida> findByOcorridoEmBetweenAndApagadoEmIsNullOrderByOcorridoEmAsc(
            OffsetDateTime inicio, OffsetDateTime fim);

    List<Batida> findTop1ByApagadoEmIsNullOrderByOcorridoEmDesc();

    Optional<Batida> findByIdAndApagadoEmIsNull(UUID id);
}
