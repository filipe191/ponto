// Aba Empresas (só o superadministrador): empresas, superadministradores e auditoria do sistema.
import { AUDIT_PAGE, loadAudit } from './auditoria.js';
import { $, api, ask, esc, fmtDT, request, sessao, toast } from './comum.js';

// ---------- Empresas (só o superadministrador) ----------

let companies = [];
let editingCompany = null; // empresa sendo editada no formulário (null = nova)

export async function loadCompanies(openId) {
  try { companies = await request('/api/companies'); } catch (err) { $('coError').textContent = err.message; return; }
  $('companies').innerHTML = companies.length
    ? companies.map((c) => `
        <tr>
          <td class="who">${esc(c.name)}${c.active ? '' : '<span class="tag inativo">desativada</span>'}${c.id === openId ? ' <span class="muted">(aberta)</span>' : ''}</td>
          <td>${c.privacy_contact ? esc(c.privacy_contact) : '<span class="muted">—</span>'}${c.notify_email ? `<small class="contract">avisos: ${esc(c.notify_email)}</small>` : ''}</td>
          <td class="actions">
            ${c.id === openId ? '' : `<button class="btn btn-sm" data-co="open" data-id="${c.id}">Abrir</button>`}
            <button class="btn btn-sm" data-co="edit" data-id="${c.id}">Editar</button>
            <button class="btn btn-sm${c.active ? ' btn-danger' : ''}" data-co="toggle" data-id="${c.id}">${c.active ? 'Desativar' : 'Ativar'}</button>
          </td>
        </tr>`).join('')
    : '<tr><td colspan="3" class="empty">Nenhuma empresa cadastrada. Cadastre a primeira acima.</td></tr>';
  $('companyPick').innerHTML = (openId ? '' : '<option value="">Escolha uma empresa</option>')
    + companies.map((c) => `<option value="${c.id}">${esc(c.name)}${c.active ? '' : ' (desativada)'}</option>`).join('');
  $('companyPick').value = openId || '';
  $('companyPick').hidden = !companies.length;
}

// Abrir outra empresa recarrega o painel inteiro: nada da anterior fica na tela
async function openCompany(id) {
  try {
    await request('/api/auth/company', { method: 'POST', body: JSON.stringify({ company_id: Number(id) }) });
    location.reload();
  } catch (err) { $('coError').textContent = err.message; }
}

function companyForm(company = null) {
  editingCompany = company;
  $('coName').value = company?.name || '';
  $('coContact').value = company?.privacy_contact || '';
  $('coEmail').value = company?.notify_email || '';
  // O primeiro admin só é pedido no cadastro; depois, os admins são criados no painel da empresa
  for (const id of ['coAdmUser', 'coAdmPass']) {
    $(id).hidden = !!company;
    $(id).required = !company;
    $(id).value = '';
  }
  $('coSubmit').textContent = company ? 'Salvar empresa' : 'Cadastrar empresa';
  $('coCancel').hidden = !company;
  $('coError').textContent = '';
  if (company) $('coName').focus();
}

$('companyPick').addEventListener('change', () => { if ($('companyPick').value) openCompany($('companyPick').value); });
$('coCancel').addEventListener('click', () => companyForm());
$('coForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('coError').textContent = '';
  const body = { name: $('coName').value, privacy_contact: $('coContact').value, notify_email: $('coEmail').value };
  try {
    if (editingCompany) {
      await request(`/api/companies/${editingCompany.id}`, { method: 'PATCH', body: JSON.stringify(body) });
      if (editingCompany.id === sessao.companyId) $('companyName').textContent = body.name.trim();
    } else {
      body.admin_username = $('coAdmUser').value;
      body.admin_password = $('coAdmPass').value;
      const created = await request('/api/companies', { method: 'POST', body: JSON.stringify(body) });
      if (!sessao.companyId) return openCompany(created.id); // primeira empresa: já abre
    }
    toast(editingCompany ? 'Empresa salva' : 'Empresa cadastrada');
    companyForm();
    loadCompanies(sessao.companyId);
    loadSystemAudit();
    if (sessao.companyId) loadAudit();
  } catch (err) { $('coError').textContent = err.message; }
});
$('companies').addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-co]');
  if (!btn) return;
  const company = companies.find((c) => String(c.id) === btn.dataset.id);
  $('coError').textContent = '';
  if (btn.dataset.co === 'open') return openCompany(company.id);
  if (btn.dataset.co === 'edit') return companyForm(company);
  if (company.active) {
    const ok = await ask({
      title: `Desativar ${company.name}?`,
      message: 'Os administradores da empresa saem na hora e não conseguem entrar, os relógios e os celulares dela param de registrar ponto. Nada é apagado: ao reativar, tudo volta a funcionar.',
      ok: 'Desativar',
      danger: true,
    });
    if (ok === null) return;
  }
  try {
    await request(`/api/companies/${company.id}`, { method: 'PATCH', body: JSON.stringify({ active: !company.active }) });
    toast(company.active ? 'Empresa desativada' : 'Empresa ativada');
  } catch (err) { $('coError').textContent = err.message; }
  loadCompanies(sessao.companyId);
  loadSystemAudit();
  if (sessao.companyId) loadAudit();
});

// ---------- Superadministradores e auditoria do sistema ----------

export async function loadSuperadmins() {
  let items = [];
  try { items = await request('/api/companies/superadmins'); } catch (err) { $('saError').textContent = err.message; }
  $('superadmins').innerHTML = items.map((a) => `
    <tr>
      <td class="who">${esc(a.username)}${a.username === sessao.user ? ' <span class="muted">(você)</span>' : ''}</td>
      <td>${fmtDT(a.updated_at)}</td>
      <td class="actions">${a.username === sessao.user ? '' : `<button class="btn btn-sm btn-danger" data-sa="${a.id}" data-name="${esc(a.username)}">Excluir</button>`}</td>
    </tr>`).join('');
}

$('saForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('saError').textContent = '';
  try {
    await request('/api/companies/superadmins', { method: 'POST', body: JSON.stringify({ username: $('saUser').value, password: $('saPass').value }) });
    $('saUser').value = '';
    $('saPass').value = '';
    toast('Superadministrador cadastrado');
    loadSuperadmins();
    loadSystemAudit();
  } catch (err) { $('saError').textContent = err.message; }
});
$('superadmins').addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-sa]');
  if (!btn) return;
  const ok = await ask({ title: `Excluir o superadministrador ${btn.dataset.name}?`, message: 'Ele perde o acesso na hora. O histórico do que ele fez é mantido.', ok: 'Excluir', danger: true });
  if (ok === null) return;
  try { await request(`/api/companies/superadmins/${btn.dataset.sa}`, { method: 'DELETE' }); toast('Superadministrador excluído'); } catch (err) { $('saError').textContent = err.message; }
  loadSuperadmins();
  loadSystemAudit();
});

let sysAuditLast = null;

export async function loadSystemAudit(more = false) {
  const params = new URLSearchParams({ limit: AUDIT_PAGE });
  if (more && sysAuditLast) params.set('before', sysAuditLast);
  $('sysAudError').textContent = '';
  let items = [];
  try { items = await request(`/api/companies/audit?${params}`); } catch (err) { $('sysAudError').textContent = err.message; return; }
  const rows = items.map((a) => `
    <tr>
      <td class="when">${fmtDT(a.at)}</td>
      <td class="who">${esc(a.user)}${a.ip ? `<small class="contract">${esc(a.ip)}</small>` : ''}</td>
      <td class="wrap">${esc(a.summary)}</td>
    </tr>`).join('');
  if (more) $('sysAudit').insertAdjacentHTML('beforeend', rows);
  else $('sysAudit').innerHTML = rows || '<tr><td colspan="3" class="empty">Nada registrado ainda.</td></tr>';
  if (items.length) sysAuditLast = items[items.length - 1].id;
  $('sysAudMore').hidden = items.length < AUDIT_PAGE;
}

$('sysAudMore').addEventListener('click', () => loadSystemAudit(true));
