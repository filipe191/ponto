// Relógio (tela do tablet) e login.
const { test, expect, como, semRolagemLateral } = require('./apoio');
const d = require('../dados');

test.describe('relógio', () => {
  test.use(como(d.ADMIN)); // admin logado no aparelho também bate o ponto da empresa

  test('bate o ponto com o PIN', async ({ page, erros }, info) => {
    await page.goto('/');
    await semRolagemLateral(page);
    await page.screenshot({ path: `resultados/${info.project.name}-relogio.png`, fullPage: true });
    test.skip(info.project.name !== 'computador', 'uma batida por execução');
    for (const k of d.PIN) await page.click(`[data-k="${k}"]`);
    await page.click('[data-k="ok"]');
    await expect(page.locator('#slip')).toContainText(`registrada, ${d.FUNCIONARIO}`);
  });

  test('"Usar como relógio" pergunta na janela do sistema', async ({ page, erros }) => {
    await page.goto('/');
    await page.click('#kiosk');
    await expect(page.locator('#askDialog')).toBeVisible();
    await expect(page.locator('#askTitle')).toHaveText('Usar como relógio de ponto?');
    await page.click('#askCancel');
    await expect(page.locator('#askDialog')).toBeHidden();
  });
});

test('login com senha errada mostra o erro', async ({ page, erros }) => {
  await page.goto('/login');
  await page.fill('#username', 'ninguem');
  await page.fill('#password', 'senha-errada');
  await page.click('#submit');
  await expect(page.locator('#error')).not.toBeEmpty();
  await semRolagemLateral(page);
});
