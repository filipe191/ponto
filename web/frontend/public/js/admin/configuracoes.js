// Aba Configurações: feriados, regras de jornada, ajustes da empresa, administradores, aviso de privacidade e relógios.
import { loadAudit } from './auditoria.js';
import { $, api, ask, esc, fmtD, fmtDT, now, sessao, toast, todayISO } from './comum.js';
import { loadReport } from './espelho.js';

// ---------- Feriados ----------

$('holYear').value = now.getFullYear();

export async function loadHolidays() {
  let items = [];
  try { items = await api(`/holidays?year=${$('holYear').value}`); } catch (err) { $('holError').textContent = err.message; }
  $('holidays').innerHTML = items.map((h) => `
    <tr>
      <td>${new Date(h.date + 'T12:00:00').toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' })}</td>
      <td>${esc(h.name)}${h.national ? ' <span class="muted">· nacional</span>' : ''}${h.yearly ? ` <span class="muted">· todo ano, desde ${h.since.slice(0, 4)}</span>` : ''}</td>
      <td class="actions">${h.national ? '' : `<button class="btn btn-sm btn-danger" data-hol="${h.date}" data-yearly="${h.yearly ? h.since.slice(0, 4) : ''}">Remover</button>`}</td>
    </tr>`).join('');
}

$('holYear').addEventListener('change', loadHolidays);
$('holForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('holError').textContent = '';
  try {
    await api('/holidays', { method: 'POST', body: JSON.stringify({ date: $('holDate').value, name: $('holName').value, yearly: $('holYearly').checked }) });
    $('holYearly').checked = false;
    $('holYear').value = $('holDate').value.slice(0, 4);
    $('holName').value = '';
    toast('Feriado cadastrado');
    loadHolidays();
    loadReport();
    loadAudit();
  } catch (err) { $('holError').textContent = err.message; }
});
$('holidays').addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-hol]');
  const day = btn?.dataset.hol;
  if (!day) return;
  // Feriado que repete: remover num ano seguinte só para de repetir dali em diante (o passado fica)
  if (btn.dataset.yearly && btn.dataset.yearly !== day.slice(0, 4)) {
    const ok = await ask({
      title: 'Parar de repetir este feriado?',
      message: `Ele deixa de valer a partir de ${day.slice(0, 4)}. Os anos anteriores (desde ${btn.dataset.yearly}) continuam com o feriado.`,
      ok: 'Parar de repetir',
      danger: true,
    });
    if (ok === null) return;
  }
  try { await api(`/holidays/${day}`, { method: 'DELETE' }); toast('Feriado removido'); } catch (err) { $('holError').textContent = err.message; }
  loadHolidays();
  loadReport();
  loadAudit();
});
document.querySelectorAll('[data-movable]').forEach((b) => b.addEventListener('click', async () => {
  $('holError').textContent = '';
  try {
    await api('/holidays/movable', { method: 'POST', body: JSON.stringify({ year: Number($('holYear').value), items: [b.dataset.movable] }) });
    toast(`${b.textContent.replace('+ ', '')} de ${$('holYear').value} cadastrado`);
    loadHolidays();
    loadReport();
    loadAudit();
  } catch (err) { $('holError').textContent = err.message; }
}));

// ---------- Administradores e relógios ----------


export async function loadAdmins() {
  let admins = [];
  try { admins = await api('/admins'); } catch (err) { $('admError').textContent = err.message; }
  $('admins').innerHTML = admins.map((a) => `
    <tr>
      <td class="who">${esc(a.username)}${a.username === sessao.user ? ' <span class="muted">(você)</span>' : ''}${a.superadmin ? ' <span class="muted">· superadministrador</span>' : ''}${a.read_only ? '<span class="tag inativo">só consulta</span>' : ''}</td>
      <td>${fmtDT(a.updated_at)}</td>
      <td class="actions">${a.username === sessao.user || a.superadmin ? '' : `<button class="btn btn-sm btn-danger" data-adm="${a.id}" data-name="${esc(a.username)}">Excluir</button>`}</td>
    </tr>`).join('');
}

$('admForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('admError').textContent = '';
  try {
    await api('/admins', { method: 'POST', body: JSON.stringify({ username: $('admUser').value, password: $('admPass').value, read_only: $('admReadOnly').checked }) });
    $('admReadOnly').checked = false;
    $('admUser').value = '';
    $('admPass').value = '';
    toast('Administrador cadastrado');
    loadAdmins();
    loadAudit();
  } catch (err) { $('admError').textContent = err.message; }
});
$('admins').addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-adm]');
  if (!btn) return;
  const ok = await ask({ title: `Excluir o administrador ${btn.dataset.name}?`, message: 'Ele perde o acesso na hora. O histórico de correções feitas por ele é mantido.', ok: 'Excluir', danger: true });
  if (ok === null) return;
  try { await api(`/admins/${btn.dataset.adm}`, { method: 'DELETE' }); toast('Administrador excluído'); } catch (err) { $('admError').textContent = err.message; }
  loadAdmins();
  loadAudit();
});
$('resetKiosks').addEventListener('click', async () => {
  const ok = await ask({
    title: 'Desligar todos os relógios?',
    message: 'Todos os aparelhos liberados como relógio vão pedir login. Em cada um que continuar em uso, entre como administrador e toque em “Usar como relógio”.',
    ok: 'Desligar todos',
    danger: true,
  });
  if (ok === null) return;
  try {
    await api('/kiosks/reset', { method: 'POST' });
    $('kioskMsg').textContent = 'Relógios desligados.';
    loadAudit();
  } catch (err) { $('kioskMsg').textContent = err.message; }
});

// ---------- Regras de jornada ----------

const RULE_PRESETS = {
  urbano: { night_start_hour: 22, night_end_hour: 5, night_hour_minutes: 52.5 },
  lavoura: { night_start_hour: 21, night_end_hour: 5, night_hour_minutes: 60 },
  pecuaria: { night_start_hour: 20, night_end_hour: 4, night_hour_minutes: 60 },
};
const RULE_INPUTS = { tolerance_minutes: 'rTol', night_start_hour: 'rNightStart', night_end_hour: 'rNightEnd', night_hour_minutes: 'rNightMin', max_shift_hours: 'rMaxShift', overtime_pct: 'rPct', rest_overtime_pct: 'rRestPct' };
const overtimeText = (r) => (r.overtime_mode === 'pagar' ? `extras pagas (${r.overtime_pct}% · ${r.rest_overtime_pct}% em domingo e feriado)` : 'extras no banco de horas');
const nightMin = (m) => String(m).replace('.', ',');
const ruleText = (r) => `tolerância de ${r.tolerance_minutes} min · noturno das ${r.night_start_hour}h às ${r.night_end_hour}h (hora de ${nightMin(r.night_hour_minutes)} min${r.night_extension ? ', prorrogado' : ''}) · jornada máxima de ${r.max_shift_hours} h · ${overtimeText(r)}`;

export async function loadRules() {
  let r;
  try { r = await api('/rules'); } catch (err) { $('ruleError').textContent = err.message; return; }
  const today = todayISO();
  const current = [...r.periods].reverse().find((p) => p.valid_from <= today) || r.periods[0];
  $('rulesNow').textContent = current ? `Hoje: ${ruleText(current)}` : '';
  $('rulePeriods').innerHTML = r.periods.slice().reverse().map((p) => `
    <tr>
      <td>${p.valid_from === '2000-01-01' ? 'sempre' : fmtD(p.valid_from)}${p.valid_from > today ? ' <span class="muted">(futura)</span>' : ''}</td>
      <td>${p.tolerance_minutes} min</td>
      <td>${p.night_start_hour}h às ${p.night_end_hour}h · hora de ${nightMin(p.night_hour_minutes)} min${p.night_extension ? ' · prorrogado' : ''}</td>
      <td>${p.max_shift_hours} h</td>
      <td>${p.overtime_mode === 'pagar' ? `pagas · ${p.overtime_pct}% / ${p.rest_overtime_pct}%` : 'banco de horas'}</td>
      <td>${esc(p.created_by)}<small class="contract">${fmtDT(p.created_at)}</small></td>
    </tr>`).join('');
  // O formulário começa com as regras de hoje, para mudar só o que for preciso
  $('ruleForm').hidden = !r.can_edit;
  if (current) for (const [field, id] of Object.entries(RULE_INPUTS)) $(id).value = current[field];
  if (current) $('rMode').value = current.overtime_mode;
  if (current) $('rExt').checked = current.night_extension;
  if (!$('rFrom').value) $('rFrom').value = today;
  $('sTz').value = r.timezone;
  $('sOffline').value = r.offline_max_hours;
  $('sControl').value = r.control_start || '';
  for (const id of ['sTz', 'sOffline', 'sControl']) $(id).disabled = !r.can_edit;
  $('settingsSubmit').hidden = !r.can_edit;
}

document.querySelectorAll('[data-preset]').forEach((btn) => btn.addEventListener('click', () => {
  for (const [field, value] of Object.entries(RULE_PRESETS[btn.dataset.preset])) $(RULE_INPUTS[field]).value = value;
}));
$('ruleForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('ruleError').textContent = '';
  const body = { valid_from: $('rFrom').value };
  for (const [field, id] of Object.entries(RULE_INPUTS)) body[field] = Number($(id).value);
  body.overtime_mode = $('rMode').value;
  body.night_extension = $('rExt').checked;
  const ok = await ask({
    title: `Novas regras a partir de ${fmtD(body.valid_from)}?`,
    message: `${ruleText(body)}. Os dias anteriores e o banco de horas acumulado até lá não mudam. Não é possível começar num mês já fechado.`,
    ok: 'Salvar regras',
  });
  if (ok === null) return;
  try {
    await api('/rules', { method: 'POST', body: JSON.stringify(body) });
    toast('Regras salvas');
    loadRules();
    loadReport();
    loadAudit();
  } catch (err) { $('ruleError').textContent = err.message; }
});
$('settingsForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('settingsError').textContent = '';
  try {
    await api('/rules/settings', { method: 'PATCH', body: JSON.stringify({ timezone: $('sTz').value.trim(), offline_max_hours: Number($('sOffline').value), control_start: $('sControl').value || null }) });
    toast('Configurações salvas');
    loadRules();
    loadAudit();
  } catch (err) { $('settingsError').textContent = err.message; }
});

// ---------- Aviso de privacidade ----------

$('privacyCopy').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText($('privacyLink').textContent);
    $('privacyCopy').textContent = 'Copiado';
  } catch { $('privacyCopy').textContent = 'Selecione e copie'; }
  setTimeout(() => { $('privacyCopy').textContent = 'Copiar link'; }, 2000);
});
