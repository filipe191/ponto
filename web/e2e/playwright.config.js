// Testes das páginas contra a pilha descartável de e2e/rodar.sh (nginx em https://frontend).
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './testes',
  outputDir: './resultados/falhas',
  globalSetup: require.resolve('./preparar.js'),
  timeout: 30_000,
  retries: 0,
  workers: 1, // os testes compartilham os dados de exemplo
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_URL || 'https://frontend',
    ignoreHTTPSErrors: true, // certificado temporário da pilha de teste
    locale: 'pt-BR',
    timezoneId: 'America/Sao_Paulo',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'computador', use: { viewport: { width: 1280, height: 900 } } },
    { name: 'celular', use: { ...devices['Pixel 5'], viewport: { width: 390, height: 844 } } },
  ],
});
