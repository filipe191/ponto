package br.com.aurasoftware.ponto.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Autenticacao minima por API key no header X-API-Key.
 *
 * Como o sistema e de uso pessoal e vai ficar atras de Tailscale ou Cloudflare
 * Tunnel, isso e suficiente. Se um dia virar multiusuario, troque por JWT.
 */
@Component
public class ApiKeyFilter extends OncePerRequestFilter {

    private final byte[] chaveEsperada;

    public ApiKeyFilter(@Value("${ponto.api-key}") String apiKey) {
        this.chaveEsperada = apiKey.getBytes(StandardCharsets.UTF_8);
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return path.startsWith("/actuator") || path.equals("/health");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {

        String recebida = request.getHeader("X-API-Key");

        // Comparacao em tempo constante: evita timing attack, custa nada.
        boolean ok = recebida != null && MessageDigest.isEqual(
                recebida.getBytes(StandardCharsets.UTF_8), chaveEsperada);

        if (!ok) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"erro\":\"API key invalida ou ausente\"}");
            return;
        }

        chain.doFilter(request, response);
    }
}
