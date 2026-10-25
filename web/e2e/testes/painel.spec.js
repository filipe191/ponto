// Painel de administração: abas nos dois temas, sem erro de script e sem rolagem lateral; cadastro de
// funcionário, aprovação de solicitação e as contas de consulta e de superadmin.
const { test, expect, como, semRolagemLateral } = require('./apoio');
const d = require('../dados');

const ABAS = ['inicio', 'funcionarios', 'espelho', 'configuracoes', 'auditoria'];

test.describe('admin da empresa', () => {
  test.use(como(d.ADMIN));

  for (const tema of ['light', 'dark']) {
    test(`abas no tema ${tema === 'light' ? 'claro' : 'escuro'}`, async ({ page, erros }, info) => {
      await page.emulateMedia({ colorScheme: tema });
      for (const aba of ABAS) {
        await page.goto(`/admin#${aba}`);
        await expect(page.locator(`[role="tab"][data-tab="${aba}"]`)).toHaveAttribute('aria-selected', 'true');
        await expect(page.locator(`section[data-tab="${aba}"]:not(.tab-off):not([hidden])`).first()).toBeVisible();
        await page.waitForLoadState('networkidle');
        await semRolagemLateral(page);
        await page.screenshot({ path: `resultados/${info.project.name}-${tema}-${aba}.png`, fullPage: true });
      }
    });
  }

  test('cadastra funcionário com sábado de meio período', async ({ page, erros }) => {
    await page.goto('/admin#funcionarios');
    await page.click('#newEmp');
    const nome = `Teste ${Date.now() % 100000}`;
    await page.fill('#fName', nome);
    await page.click('#fPinGen');
    await page.click('[data-sched="44h"]');
    await expect(page.locator('#fPreview')).toContainText('44h00 por semana');
    await page.click('#empForm button[type="submit"]');
    await expect(page.locator('#toast')).toHaveText('Funcionário cadastrado');
    await expect(page.locator('#employees')).toContainText(nome);
    await expect(page.locator('#employees')).toContainText('sáb 4h00');
  });

  test('espelho mostra a ausência lançada', async ({ page, erros }) => {
    await page.goto('/admin#espelho');
    await page.selectOption('#repEmp', { label: d.FUNCIONARIO });
    await page.fill('#repMonth', '2026-01');
    await page.dispatchEvent('#repMonth', 'change');
    await expect(page.locator('#report')).toContainText('Atestado médico');
    await expect(page.locator('#absList')).toContainText('Atestado médico');
  });

  test('aprova a solicitação feita pelo app', async ({ page, erros }, info) => {
    test.skip(info.project.name !== 'computador', 'há uma solicitação só');
    await page.goto('/admin#inicio');
    await expect(page.locator('#tabReqCount')).toHaveText('1');
    await page.click('[data-req="approve"]');
    await page.click('#askOk');
    await expect(page.locator('#toast')).toHaveText('Solicitação aprovada');
  });
});

test.describe('admin só de consulta', () => {
  test.use(como(d.CONSULTA));

  test('vê o painel sem os botões de alteração', async ({ page, erros }) => {
    await page.goto('/admin#funcionarios');
    await expect(page.locator('#readOnlyNotice')).toBeVisible();
    await expect(page.locator('#employees')).toContainText(d.FUNCIONARIO);
    await expect(page.locator('#newEmp')).toBeHidden();
    await expect(page.locator('[data-act="edit"]').first()).toBeHidden();
    await page.goto('/admin#espelho');
    await expect(page.locator('#manual')).toBeHidden();
    await expect(page.locator('#absForm')).toBeHidden();
  });
});

test.describe('superadmin', () => {
  test.use(como(d.SUPERADMIN));

  test('vê as empresas', async ({ page, erros }) => {
    await page.goto('/admin#empresas');
    await expect(page.locator('#coCard')).toBeVisible();
    await expect(page.locator('#companies')).toContainText(d.EMPRESA);
    await semRolagemLateral(page);
  });
});
