// Apoio comum: sessão de cada usuário e a coleta de erros de script da página (um erro reprova o teste).
const base = require('@playwright/test');
const d = require('../dados');

exports.test = base.test.extend({
  erros: async ({ page }, use) => {
    const erros = [];
    page.on('pageerror', (e) => erros.push(e.message));
    page.on('console', (m) => {
      // Respostas 4xx esperadas (ex.: a recusa do admin de consulta) aparecem como "Failed to load resource"
      if (m.type() === 'error' && !m.text().startsWith('Failed to load resource')) erros.push(m.text());
    });
    await use(erros);
    base.expect(erros, 'erros de script na página').toEqual([]);
  },
});
exports.expect = base.expect;
exports.como = (usuario) => ({ storageState: d.estado(usuario) });

// Sem rolagem para os lados (o layout cabe na largura da tela)
exports.semRolagemLateral = async (page) => {
  const sobra = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  base.expect(sobra, 'a página rola para os lados').toBeLessThanOrEqual(1);
};
