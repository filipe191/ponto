// Aba Funcionários: lista com busca, cadastro (com a jornada por dia ou escala) e os celulares do app.
import { loadAudit } from './auditoria.js';
import { $, WEEK, api, ask, esc, fmtD, fmtDT, fmtH, fmtSigned, localDate, parseHM, shortH, toHM, toast, todayISO } from './comum.js';
import { cancelEdit, downloadFile, loadAbsences, loadReport } from './espelho.js';
import { loadAlerts } from './inicio.js';

export let employees = [];
let editingEmp = null;  // funcionário aberto na janela (null = novo)

// ---------- Funcionários ----------

// ---------- Jornada: horas de cada dia da semana ou de cada dia da escala ----------

const SCHEDULE_PRESETS = {
  '5x2': { kind: 'semana', minutes: [480, 480, 480, 480, 480, 0, 0] },
  '44h': { kind: 'semana', minutes: [480, 480, 480, 480, 480, 240, 0] },
  '6x1': { kind: 'semana', minutes: [440, 440, 440, 440, 440, 440, 0] },
  '12x36': { kind: 'ciclo', minutes: [720, 0] },
  '24x48': { kind: 'ciclo', minutes: [1440, 0, 0] },
};

function hmInputs(el, labels, minutes) {
  el.innerHTML = labels.map((l, i) => `<label>${l}<input class="input" inputmode="numeric" placeholder="folga" value="${toHM(minutes[i] || 0)}" aria-label="${l}: horas de trabalho (vazio = folga)" autocomplete="off"></label>`).join('');
}

function setSchedule(spec) {
  const cycle = spec.kind === 'ciclo';
  document.querySelector(`[name="fKind"][value="${cycle ? 'ciclo' : 'semana'}"]`).checked = true;
  $('fWeekWrap').hidden = cycle;
  $('fCycleWrap').hidden = !cycle;
  if (cycle) {
    $('fCycleLen').value = spec.minutes.length;
    hmInputs($('fCycle'), spec.minutes.map((_, i) => `${i + 1}º dia`), spec.minutes);
    if (spec.cycle_start) $('fCycleStart').value = spec.cycle_start;
  } else {
    hmInputs($('fWeek'), WEEK, spec.minutes);
  }
  schedulePreview();
}

// Lê o formulário; lança Error com a mensagem para o usuário
function readSchedule() {
  const cycle = document.querySelector('[name="fKind"]:checked').value === 'ciclo';
  const minutes = [...$(cycle ? 'fCycle' : 'fWeek').querySelectorAll('input')].map((i) => parseHM(i.value));
  if (minutes.some(Number.isNaN)) throw new Error('Jornada: use horas:minutos em cada dia (ex.: 08:00), ou deixe vazio para folga.');
  if (!cycle) return { kind: 'semana', minutes };
  if (!$('fCycleStart').value) throw new Error('Informe o 1º dia da escala.');
  return { kind: 'ciclo', minutes, cycle_start: $('fCycleStart').value };
}

function minutesOn(spec, day) {
  if (spec.kind !== 'ciclo') return spec.minutes[(day.getDay() + 6) % 7];
  const n = spec.minutes.length;
  const diff = Math.round((day - new Date(spec.cycle_start + 'T12:00:00')) / 86400000);
  return spec.minutes[((diff % n) + n) % n];
}

function schedulePreview() {
  let spec;
  try { spec = readSchedule(); } catch (err) { $('fPreview').textContent = err.message; return; }
  const from = new Date((($('fFromWrap').hidden ? '' : $('fFrom').value) || todayISO()) + 'T12:00:00');
  const days = Array.from({ length: 14 }, (_, i) => new Date(from.getTime() + i * 86400000));
  const total = spec.kind === 'semana' ? ` Total: ${fmtH(spec.minutes.reduce((a, b) => a + b, 0) * 60000)} por semana.` : '';
  $('fPreview').textContent = `Próximos 14 dias: ${days.map((d) => `${WEEK[(d.getDay() + 6) % 7]} ${d.getDate()}: ${shortH(minutesOn(spec, d))}`).join(' · ')}.${total}`;
}

document.querySelectorAll('[name="fKind"]').forEach((r) => r.addEventListener('change', () => {
  if (r.value === 'ciclo') setSchedule({ ...SCHEDULE_PRESETS['12x36'], cycle_start: $('fCycleStart').value || todayISO() });
  else setSchedule(SCHEDULE_PRESETS['5x2']);
}));
document.querySelectorAll('[data-sched]').forEach((b) => b.addEventListener('click', () => {
  setSchedule({ ...SCHEDULE_PRESETS[b.dataset.sched], cycle_start: $('fCycleStart').value || todayISO() });
}));
$('fCycleLen').addEventListener('change', () => {
  const n = Math.min(28, Math.max(2, Number($('fCycleLen').value) || 2));
  const current = [...$('fCycle').querySelectorAll('input')].map((i) => parseHM(i.value) || 0);
  setSchedule({ kind: 'ciclo', minutes: Array.from({ length: n }, (_, i) => current[i] || 0), cycle_start: $('fCycleStart').value });
});
for (const id of ['fWeek', 'fCycle', 'fCycleStart', 'fFrom']) $(id).addEventListener('input', schedulePreview);

// Busca sem diferenciar maiúsculas nem acentos ("joao" acha "João")
const fold = (s) => s.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
const matches = (e, query) => fold(e.name).includes(fold(query.trim()));

export async function loadEmployees() {
  employees = await api('/employees');
  renderEmployees();
  renderReportPicker();
  const audCurrent = $('audEmp').value;
  $('audEmp').innerHTML = '<option value="">Todos os funcionários</option>' + employeeOptions(employees);
  $('audEmp').value = audCurrent;
}

const employeeOptions = (list) => list.map((e) => `<option value="${e.id}">${esc(e.name)}${e.active ? '' : ' (inativo)'}</option>`).join('');

function renderEmployees() {
  const status = $('empStatus').value;
  const shown = employees.filter((e) => matches(e, $('empSearch').value)
    && (status === 'todos' || (status === 'ativos') === e.active));
  $('empCount').textContent = shown.length === employees.length ? '' : `${shown.length} de ${employees.length}`;
  $('employees').innerHTML = shown.length
    ? shown.map((e) => `
        <tr>
          <td class="who">${esc(e.name)}${e.active ? '' : '<span class="tag inativo">inativo</span>'}${e.pin_short && e.active ? '<span class="tag falta" title="PIN de 4 ou 5 dígitos: troque por um de 6">PIN curto</span>' : ''}
            <small class="contract">${e.terminated_on ? `desligado em ${fmtD(e.terminated_on)}` : `desde ${fmtD(e.hired_on)}`}</small></td>
          <td>${esc(e.schedule_label)}</td>
          <td class="actions">${e.anonymized_at ? `
            <span class="tag inativo" title="Dados pessoais apagados em ${fmtDT(e.anonymized_at)} (LGPD)">anonimizado</span>` : `
            <button class="btn btn-sm" data-act="edit" data-id="${e.id}">Editar</button>
            <button class="btn btn-sm" data-act="devices" data-id="${e.id}">Celular</button>
            <button class="btn btn-sm" data-act="export" data-id="${e.id}" title="Tudo o que o sistema guarda sobre a pessoa (pedido de acesso, LGPD)">Dados</button>
            ${e.retention_due ? `<button class="btn btn-sm btn-danger" data-act="anon" data-id="${e.id}">Anonimizar</button>` : `
            <button class="btn btn-sm" data-act="toggle" data-id="${e.id}">${e.active ? 'Desativar' : 'Ativar'}</button>
            <button class="btn btn-sm btn-danger" data-act="del" data-id="${e.id}">Excluir</button>`}`}
          </td>
        </tr>`).join('')
    : `<tr><td colspan="3" class="empty">${employees.length ? 'Ninguém encontrado com essa busca.' : 'Nenhum funcionário cadastrado. Use “Novo funcionário”.'}</td></tr>`;
}

// Seletor do espelho: só os nomes que batem com a busca. Se o escolhido sumir da lista, abre o primeiro.
function renderReportPicker() {
  const current = $('repEmp').value;
  const shown = employees.filter((e) => matches(e, $('repSearch').value));
  $('repEmp').innerHTML = employeeOptions(shown);
  if (shown.some((e) => String(e.id) === current)) $('repEmp').value = current;
  return shown.length > 0 && $('repEmp').value !== current;
}

$('empSearch').addEventListener('input', renderEmployees);
$('empStatus').addEventListener('change', renderEmployees);
$('repSearch').addEventListener('input', () => {
  if (renderReportPicker()) { cancelEdit(); loadReport(); loadAbsences(); }
});

function openEmpDialog(emp = null) {
  editingEmp = emp;
  $('empTitle').textContent = emp ? `Editar ${emp.name}` : 'Novo funcionário';
  $('fName').value = emp?.name || '';
  $('fPin').value = '';
  $('fPin').type = 'password';
  $('fPinHint').hidden = true;
  $('fPin').required = !emp || emp.pin_short;
  $('fPinLabel').textContent = !emp
    ? 'PIN (6 a 8 dígitos)'
    : emp.pin_short
      ? 'Novo PIN (obrigatório: o atual é curto)'
      : 'Novo PIN (deixe em branco para manter)';
  // Jornada em vigor hoje (a última que já começou)
  const today = todayISO();
  const current = emp ? (emp.schedules.filter((s) => s.valid_from <= today).pop() || emp.schedules[0]) : null;
  // Jornada com vigência: a mudança vale a partir de uma data e não altera o passado
  $('fFromWrap').hidden = !emp;
  $('fFrom').value = todayISO();
  $('fSchedules').innerHTML = emp && emp.schedules.length > 1
    ? emp.schedules.map((s) => `<li>desde ${fmtD(s.valid_from)}: ${esc(s.label)}</li>`).join('')
    : '';
  $('fHired').value = emp?.hired_on || todayISO();
  $('fCycleStart').value = current?.cycle_start || todayISO();
  setSchedule(current || SCHEDULE_PRESETS['5x2']);
  $('fTerminated').value = emp?.terminated_on || '';
  $('fControl').value = emp?.control_start || '';
  $('fInitial').value = emp?.initial_balance_minutes ? fmtSigned(emp.initial_balance_minutes * 60000).replace('h', ':') : '';
  $('fInitialNote').value = emp?.initial_balance_note || '';
  $('fControlWrap').open = !!(emp?.control_start || emp?.initial_balance_minutes);
  $('fError').textContent = '';
  $('empDialog').showModal();
  $('fName').focus();
}

$('newEmp').addEventListener('click', () => openEmpDialog());
// PIN aleatório: evita PINs fáceis (datas, 123456) e o admin não precisa inventar um
$('fPinGen').addEventListener('click', () => {
  const n = crypto.getRandomValues(new Uint32Array(1))[0] % 1000000;
  $('fPin').value = String(n).padStart(6, '0');
  $('fPin').type = 'text';
  $('fPinHint').hidden = false;
});
$('fCancel').addEventListener('click', () => $('empDialog').close());

$('empForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  let schedule;
  try { schedule = readSchedule(); } catch (err) { $('fError').textContent = err.message; return; }
  const body = {
    name: $('fName').value,
    schedule,
    hired_on: $('fHired').value || null,
  };
  if (editingEmp) {
    body.terminated_on = $('fTerminated').value || null;
    body.schedule_from = $('fFrom').value || null;
  }
  body.control_start = $('fControl').value || null;
  const initial = $('fInitial').value.trim().match(/^([+−-]?)(\d+):([0-5]\d)$/);
  if ($('fInitial').value.trim() && !initial) { $('fError').textContent = 'Saldo inicial: use horas:minutos, ex.: +12:30 ou −3:00.'; return; }
  body.initial_balance_minutes = initial ? (initial[1] && initial[1] !== '+' ? -1 : 1) * (Number(initial[2]) * 60 + Number(initial[3])) : 0;
  body.initial_balance_note = $('fInitialNote').value;
  const pin = $('fPin').value.trim();
  if (pin || !editingEmp) body.pin = pin;
  try {
    if (editingEmp) await api('/employees/' + editingEmp.id, { method: 'PATCH', body: JSON.stringify(body) });
    else await api('/employees', { method: 'POST', body: JSON.stringify(body) });
    $('empDialog').close();
    toast(editingEmp ? 'Funcionário salvo' : 'Funcionário cadastrado');
    await loadEmployees();
    loadReport();
    loadAlerts();
    loadAudit();
  } catch (err) { $('fError').textContent = err.message; }
});

$('employees').addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-act]');
  if (!btn) return;
  const emp = employees.find((x) => String(x.id) === btn.dataset.id);
  $('empError').textContent = '';
  try {
    if (btn.dataset.act === 'edit') return openEmpDialog(emp);
    if (btn.dataset.act === 'devices') return openDevDialog(emp);
    if (btn.dataset.act === 'export') return downloadFile(`/api/admin/employees/${emp.id}/export`, $('empError'), 'dados.json');
    if (btn.dataset.act === 'anon') {
      const ok = await ask({
        title: `Anonimizar ${emp.name}?`,
        message: `Passou o prazo de guarda depois do desligamento. O nome, o PIN, os celulares e os registros de auditoria dessa pessoa serão apagados; as batidas e as horas continuam, como “Ex-funcionário nº ${emp.id}”. Não dá para desfazer. Se precisar, use antes o botão “Dados” para guardar uma cópia.`,
        ok: 'Anonimizar',
        danger: true,
      });
      if (ok === null) return;
      await api(`/employees/${emp.id}/anonymize`, { method: 'POST' });
      toast('Dados pessoais apagados');
      loadAlerts();
    }
    if (btn.dataset.act === 'toggle') {
      await api('/employees/' + emp.id, { method: 'PATCH', body: JSON.stringify({ active: !emp.active }) });
      toast(emp.active ? 'Funcionário desativado' : 'Funcionário ativado');
    } else if (btn.dataset.act === 'del') {
      const ok = await ask({
        title: `Excluir ${emp.name}?`,
        message: 'Só cadastros feitos por engano, sem nenhum registro de ponto, podem ser excluídos. Quem já bateu ponto deve ser desativado.',
        ok: 'Excluir',
        danger: true,
      });
      if (ok === null) return;
      await api('/employees/' + emp.id, { method: 'DELETE' });
      toast('Funcionário excluído');
    }
    await loadEmployees();
    loadReport();
    loadAudit();
  } catch (err) { $('empError').textContent = err.message; }
});

// ---------- Celulares (chaves do app) ----------

let devEmp = null;

async function loadDevices() {
  let items = [];
  try { items = await api(`/employees/${devEmp.id}/devices`); } catch (err) { $('devError').textContent = err.message; }
  $('devList').innerHTML = items.length
    ? items.map((d) => `<li class="dev-row">
        <span><b>${esc(d.name)}</b> · criada em ${fmtDT(d.created_at)} por ${esc(d.created_by)}
          · ${d.revoked_at ? `revogada em ${fmtDT(d.revoked_at)}` : d.last_used_at ? `último uso ${fmtDT(d.last_used_at)}` : 'ainda não usada'}${d.revoked_at ? '' : new Date(d.expires_at) <= new Date() ? ' · <b class="neg">vencida</b>' : ` · vence em ${fmtD(localDate(d.expires_at))}`}</span>
        ${d.revoked_at ? '' : `<button class="btn btn-sm btn-danger" type="button" data-dev="${d.id}">Revogar</button>`}
      </li>`).join('')
    : '<li class="muted">Nenhum celular liberado.</li>';
}

function openDevDialog(emp) {
  devEmp = emp;
  $('devTitle').textContent = `Celulares de ${emp.name}`;
  $('devName').value = '';
  $('devKey').hidden = true;
  $('devError').textContent = '';
  $('devDialog').showModal();
  loadDevices();
}

$('devClose').addEventListener('click', () => $('devDialog').close());
$('devDialog').addEventListener('close', () => { $('devKeyValue').textContent = ''; });
$('devForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('devError').textContent = '';
  try {
    const d = await api(`/employees/${devEmp.id}/devices`, { method: 'POST', body: JSON.stringify({ name: $('devName').value }) });
    $('devUrl').textContent = location.origin;
    $('devKeyValue').textContent = d.key;
    $('devKey').hidden = false;
    $('devName').value = '';
    loadDevices();
    loadAudit();
  } catch (err) { $('devError').textContent = err.message; }
});
$('devCopy').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText($('devKeyValue').textContent);
    $('devCopy').textContent = 'Copiada';
  } catch { $('devCopy').textContent = 'Selecione e copie'; }
  setTimeout(() => { $('devCopy').textContent = 'Copiar chave'; }, 2000);
});
$('devList').addEventListener('click', async (e) => {
  const id = e.target.closest('[data-dev]')?.dataset.dev;
  if (!id) return;
  const ok = await ask({ title: 'Revogar este celular?', message: 'O app nesse aparelho para de sincronizar na hora. Batidas já enviadas continuam valendo.', ok: 'Revogar', danger: true });
  if (ok === null) return;
  try { await api(`/devices/${id}`, { method: 'DELETE' }); toast('Celular revogado'); } catch (err) { $('devError').textContent = err.message; }
  loadDevices();
  loadAudit();
});
