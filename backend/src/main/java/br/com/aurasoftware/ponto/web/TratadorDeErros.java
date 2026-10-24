package br.com.aurasoftware.ponto.web;

import br.com.aurasoftware.ponto.service.NaoEncontrado;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.time.OffsetDateTime;
import java.util.HashMap;
import java.util.Map;

@RestControllerAdvice
public class TratadorDeErros {

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> validacao(MethodArgumentNotValidException ex) {
        Map<String, String> campos = new HashMap<>();
        ex.getBindingResult().getFieldErrors()
                .forEach(e -> campos.put(e.getField(), e.getDefaultMessage()));

        Map<String, Object> corpo = new HashMap<>();
        corpo.put("timestamp", OffsetDateTime.now());
        corpo.put("erro", "Dados invalidos");
        corpo.put("campos", campos);

        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(corpo);
    }

    /**
     * O app trata 404 numa correcao como "ja resolvido" e tira o item da fila —
     * batida que nao existe mais nao tem o que ajustar nem o que apagar.
     */
    @ExceptionHandler(NaoEncontrado.class)
    public ResponseEntity<Map<String, Object>> naoEncontrado(NaoEncontrado ex) {
        Map<String, Object> corpo = new HashMap<>();
        corpo.put("timestamp", OffsetDateTime.now());
        corpo.put("erro", ex.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(corpo);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> argumento(IllegalArgumentException ex) {
        Map<String, Object> corpo = new HashMap<>();
        corpo.put("timestamp", OffsetDateTime.now());
        corpo.put("erro", ex.getMessage());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(corpo);
    }
}
