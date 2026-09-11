package br.com.aurasoftware.ponto.service;

/** Id que nao existe (ou que ja foi apagado). Vira 404 no TratadorDeErros. */
public class NaoEncontrado extends RuntimeException {

    public NaoEncontrado(String mensagem) {
        super(mensagem);
    }
}
