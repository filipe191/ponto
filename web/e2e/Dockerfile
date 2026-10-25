# Navegador e Playwright na versão que os testes usam (mesmo resultado no servidor e no GitHub Actions)
FROM mcr.microsoft.com/playwright:v1.47.0-jammy
WORKDIR /e2e
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
CMD ["npx", "playwright", "test"]
