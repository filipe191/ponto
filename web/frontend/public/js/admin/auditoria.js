// Aba Auditoria: o que foi feito na empresa, com filtros e "Carregar mais".
import { $, api, esc, fmtDT } from './comum.js';

let auditLast = null; // id do registro mais antigo carregado (para "Carregar mais")
export const AUDIT_PAGE = 50;

export async function loadAudit(more = false) {
  const params = new URLSearchParams({ limit: AUDIT_PAGE });
  if ($('audEmp').value) params.set('employee', $('audEmp').value);
  if ($('audKind').value) params.set('action', $('audKind').value);
  if (more && auditLast) params.set('before', auditLast);
  $('audError').textContent = '';
  let items = [];
  try { items = await api(`/audit?${params}`); } catch (err) { $('audError').textContent = err.message; return; }
  const rows = items.map((a) => `
    <tr>
      <td class="when">${fmtDT(a.at)}</td>
      <td class="who">${esc(a.user)}${a.ip ? `<small class="contract">${esc(a.ip)}</small>` : ''}</td>
      <td class="wrap">${esc(a.summary)}</td>
    </tr>`).join('');
  if (more) $('audit').insertAdjacentHTML('beforeend', rows);
  else $('audit').innerHTML = rows || '<tr><td colspan="3" class="empty">Nada registrado ainda.</td></tr>';
  if (items.length) auditLast = items[items.length - 1].id;
  $('audMore').hidden = items.length < AUDIT_PAGE;
}

$('audEmp').addEventListener('change', () => loadAudit());
$('audKind').addEventListener('change', () => loadAudit());
$('audMore').addEventListener('click', () => loadAudit(true));
