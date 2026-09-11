package br.com.aurasoftware.ponto.repository;

import br.com.aurasoftware.ponto.domain.Batida;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

public interface BatidaRepository extends JpaRepository<Batida, UUID> {

    List<Batida> findByOcorridoEmBetweenOrderByOcorridoEmAsc(OffsetDateTime inicio, OffsetDateTime fim);

    List<Batida> findTop1ByOrderByOcorridoEmDesc();
}
