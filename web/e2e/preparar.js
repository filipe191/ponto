// Prepara os dados pela própria API, como um usuário faria: troca as senhas provisórias, cadastra a
// empresa, funcionários, uma solicitação vinda do app e um admin só de consulta. Guarda a sessão de
// cada usuário para os testes não precisarem fazer login de novo.
const { request } = require('@playwright/test');
const crypto = require('crypto');
const fs = require('fs');
const d = require('./dados');

const BASE = process.env.E2E_URL || 'https://frontend';

async function cliente() {
  return request.newContext({ baseURL: BASE, ignoreHTTPSErrors: true, extraHTTPHeaders: { Origin: BASE } });
}

async function ok(resposta, oQue) {
  if (!resposta.ok()) throw new Error(`${oQue}: ${resposta.status()} ${await resposta.text()}`);
  return resposta.status() === 204 ? null : resposta.json();
}

// Entra com a senha provisória e troca pela definitiva (o banco da pilha de teste é sempre novo).
// Sem tentativas erradas: elas contam no limite de logins por IP.
async function entrar(usuario, senhaInicial) {
  const c = await cliente();
  await ok(await c.post('/api/auth/login', { data: { username: usuario, password: senhaInicial } }), `login ${usuario}`);
  await ok(await c.post('/api/auth/password', { data: { current_password: senhaInicial, new_password: d.SENHA } }), `senha ${usuario}`);
  return c;
}

async function esperarNoAr() {
  const c = await cliente();
  for (let i = 0; i < 90; i++) {
    try { if ((await c.get('/api/health')).ok()) return; } catch {}
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`A pilha de teste não respondeu em ${BASE}`);
}

module.exports = async () => {
  fs.mkdirSync('resultados', { recursive: true });
  await esperarNoAr();

  const sa = await entrar(d.SUPERADMIN, d.SENHA_INICIAL);
  const empresa = await ok(await sa.post('/api/companies', {
    data: { name: d.EMPRESA, privacy_contact: 'rh@padaria.teste', admin_username: d.ADMIN, admin_password: d.SENHA_INICIAL },
  }), 'empresa');
  // Empresa nova começa o controle no dia do cadastro; os dados de exemplo são de janeiro de 2026
  await ok(await sa.post('/api/auth/company', { data: { company_id: empresa.id } }), 'abrir empresa');
  await ok(await sa.patch('/api/admin/rules/settings', { data: { control_start: '2026-01-01' } }), 'início do controle');
  await sa.storageState({ path: d.estado(d.SUPERADMIN) });

  const adm = await entrar(d.ADMIN, d.SENHA_INICIAL);
  {
    const ana = await ok(await adm.post('/api/admin/employees', {
      data: { name: d.FUNCIONARIO, pin: d.PIN, hired_on: '2026-01-05', schedule: { kind: 'semana', minutes: [480, 480, 480, 480, 480, 240, 0] } },
    }), 'Ana');
    const joao = await ok(await adm.post('/api/admin/employees', {
      data: { name: 'João Pereira', pin: '246801', hired_on: '2026-01-05', schedule: { kind: 'ciclo', minutes: [720, 0], cycle_start: '2026-01-05' } },
    }), 'João');
    await ok(await adm.post('/api/admin/absences', {
      data: { employee_id: ana.id, kind: 'atestado', first_day: '2026-01-06', last_day: '2026-01-06', note: 'teste' },
    }), 'ausência');
    // Solicitação vinda do app: batida esquecida pelo celular do João
    const chave = (await ok(await adm.post(`/api/admin/employees/${joao.id}/devices`, { data: { name: 'Celular' } }), 'celular')).key;
    const celular = await request.newContext({ baseURL: BASE, ignoreHTTPSErrors: true, extraHTTPHeaders: { 'X-API-Key': chave } });
    await ok(await celular.post('/api/pontos/lote', {
      data: { batidas: [{ id: crypto.randomUUID(), tipo: 'ENTRADA', ocorridoEm: '2026-01-07T08:00:00-03:00', manual: true, observacao: 'Esqueci' }] },
    }), 'lote');
    await ok(await adm.post('/api/admin/admins', { data: { username: d.CONSULTA, password: d.SENHA_INICIAL, read_only: true } }), 'consulta');
  }
  await adm.storageState({ path: d.estado(d.ADMIN) });
  const consulta = await entrar(d.CONSULTA, d.SENHA_INICIAL);
  await consulta.storageState({ path: d.estado(d.CONSULTA) });
};
