// Painel de administração: cada aba é um módulo em js/admin/; aqui só a subida da página.
import { TABS, initialTab, showTab } from './admin/abas.js';
import { loadAudit } from './admin/auditoria.js';
import { $, api, sessao, toLogin } from './admin/comum.js';
import { loadAdmins, loadHolidays, loadRules } from './admin/configuracoes.js';
import { loadCompanies, loadSuperadmins, loadSystemAudit } from './admin/empresas.js';
import { loadAbsences, loadReport } from './admin/espelho.js';
import { loadEmployees } from './admin/funcionarios.js';
import { loadAlerts, loadRequests } from './admin/inicio.js';

// ---------- Início ----------


function loadCompanyArea() {
  loadRequests();
  setInterval(loadRequests, 60000);
  loadAdmins();
  loadEmployees().then(() => { loadReport(); loadAbsences(); loadAudit(); }).catch((err) => { $('empError').textContent = err.message; });
  loadHolidays();
  loadRules();
  loadAlerts();
  setInterval(loadAlerts, 60000);
}

// A página só abre com o login do admin (o nginx confere o cookie antes)
fetch('/api/auth/admin').then((r) => (r.ok ? r.json() : null)).then((me) => {
  if (!me) return toLogin();
  if (me.pending) return location.replace('/senha');
  sessao.user = me.user || '';
  document.body.classList.toggle('read-only', !!me.read_only);
  $('readOnlyNotice').hidden = !me.read_only;
  sessao.companyId = me.company_id;
  $('whoami').textContent = sessao.user ? `Você entrou como ${sessao.user}` : '';
  $('privacyLink').textContent = me.privacy_code ? `${location.origin}/privacidade?e=${me.privacy_code}` : '';
  $('companyName').textContent = me.superadmin ? '' : me.company || '';
  $('companyName').hidden = me.superadmin;
  $('coCard').hidden = !me.superadmin;
  $('companyArea').hidden = !sessao.companyId;
  // Sem empresa aberta, só a aba Empresas (superadmin)
  TABS.forEach((tab) => { tab.hidden = tab.dataset.tab === 'empresas' ? !me.superadmin : !sessao.companyId; });
  showTab(initialTab || (sessao.companyId ? 'inicio' : 'empresas'));
  if (me.superadmin) {
    loadCompanies(sessao.companyId);
    loadSuperadmins();
    loadSystemAudit();
    if (!sessao.companyId) $('coHint').insertAdjacentHTML('beforeend', ' <b>Nenhuma empresa aberta:</b> cadastre uma ou abra uma da lista.');
  }
  if (sessao.companyId) loadCompanyArea();
}).catch(() => {});
