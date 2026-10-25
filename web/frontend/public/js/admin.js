const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const pad = (n) => String(n).padStart(2, '0');
const WEEK = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom'];
const STATUS = { falta: 'falta', incompleto: 'incompleto', andamento: 'em andamento', feriado: 'feriado', fora: 'fora do contrato' };
const fmtD = (iso) => new Date(iso + 'T12:00:00').toLocaleDateString('pt-BR');
const todayISO = () => localDate(new Date().toISOString());
const ACTION = { criada: 'lançada', alterada: 'corrigida', excluida: 'excluída', restaurada: 'restaurada' };

let employees = [];
let punches = {};       // batidas do espelho aberto, por id
let editingId = null;   // batida sendo corrigida no formulário (null = novo lançamento)
let editingEmp = null;  // funcionário aberto na janela (null = novo)

// Sessão do admin expirada ou encerrada: volta para o login
const toLogin = () => location.replace('/login?next=/admin');

// Rotas da empresa aberta no painel
const api = (path, opts) => request('/api/admin' + path, opts);

async function request(url, opts = {}) {
  const res = await fetch(url, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) { toLogin(); throw new Error(data.error); }
  // Senha provisória ou sem verificação em duas etapas: resolve em /senha antes de usar o painel
  if (res.status === 403 && data.pending) { location.replace('/senha'); throw new Error(data.error); }
  if (!res.ok) throw new Error(data.error || 'Erro');
  return data;
}

// ---------- Formatação ----------

const fmtH = (ms) => {
  const min = Math.round(Math.abs(ms) / 60000);
  return `${Math.floor(min / 60)}h${pad(min % 60)}`;
};
const fmtSigned = (ms) => {
  const min = Math.round(ms / 60000);
  return (min > 0 ? '+' : min < 0 ? '−' : '') + fmtH(ms);
};
const signCls = (ms) => { const min = Math.round(ms / 60000); return min > 0 ? 'pos' : min < 0 ? 'neg' : ''; };
const fmtT = (iso) => new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
const fmtDT = (iso) => new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' });
const kind = (t) => (t === 'entrada' ? 'E' : 'S');
const kindLabel = (t) => (t === 'entrada' ? 'Entrada' : 'Saída');
const localDate = (iso) => { const d = new Date(iso); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
// ISO → valor do <input type="datetime-local"> no horário local
const toLocalInput = (iso) => { const d = new Date(iso); return `${localDate(iso)}T${pad(d.getHours())}:${pad(d.getMinutes())}`; };

function workdaysLabel(w) {
  const named = { '': 'sem dias de trabalho', 12345: 'seg a sex', 123456: 'seg a sáb', 1234567: 'todos os dias' };
  return named[w] ?? [...w].map((d) => WEEK[d - 1]).join(', ');
}

// ---------- Janela de confirmação ----------

function ask({ title, message, input = '', ok = 'Confirmar', danger = false }) {
  const dlg = $('askDialog');
  $('askTitle').textContent = title;
  $('askMessage').textContent = message;
  $('askInputWrap').hidden = !input;
  $('askInputLabel').textContent = input;
  $('askInput').value = '';
  $('askOk').textContent = ok;
  $('askOk').className = 'btn ' + (danger ? 'btn-danger-solid' : 'btn-primary');
  dlg.returnValue = '';
  dlg.showModal();
  return new Promise((resolve) => {
    dlg.addEventListener('close', () => resolve(dlg.returnValue === 'ok' ? $('askInput').value.trim() : null), { once: true });
  });
}

$('logout').addEventListener('click', async () => {
  await fetch('/api/auth/logout', { method: 'POST' }).catch(() => {});
  location.replace('/'); // num aparelho liberado como relógio, volta para o relógio
});

// ---------- Funcionários ----------

$('fDays').innerHTML = WEEK.map((d, i) => `<label><input type="checkbox" value="${i + 1}"><span>${d}</span></label>`).join('');

async function loadEmployees() {
  employees = await api('/employees');
  $('employees').innerHTML = employees.length
    ? employees.map((e) => `
        <tr>
          <td class="who">${esc(e.name)}${e.active ? '' : '<span class="tag inativo">inativo</span>'}${e.pin_short && e.active ? '<span class="tag falta" title="PIN de 4 ou 5 dígitos: troque por um de 6">PIN curto</span>' : ''}
            <small class="contract">${e.terminated_on ? `desligado em ${fmtD(e.terminated_on)}` : `desde ${fmtD(e.hired_on)}`}</small></td>
          <td>${fmtH(e.daily_minutes * 60000)} · ${workdaysLabel(e.workdays)}</td>
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
    : '<tr><td colspan="3" class="empty">Nenhum funcionário cadastrado. Use “Novo funcionário”.</td></tr>';

  const current = $('repEmp').value;
  const options = employees.map((e) => `<option value="${e.id}">${esc(e.name)}${e.active ? '' : ' (inativo)'}</option>`).join('');
  $('repEmp').innerHTML = options;
  if (employees.some((e) => String(e.id) === current)) $('repEmp').value = current;
  const audCurrent = $('audEmp').value;
  $('audEmp').innerHTML = '<option value="">Todos os funcionários</option>' + options;
  $('audEmp').value = audCurrent;
}

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
  const minutes = emp ? emp.daily_minutes : 480;
  $('fHours').value = `${pad(Math.floor(minutes / 60))}:${pad(minutes % 60)}`;
  const days = emp ? emp.workdays : '12345';
  document.querySelectorAll('#fDays input').forEach((cb) => { cb.checked = days.includes(cb.value); });
  // Jornada com vigência: a mudança vale a partir de uma data e não altera o passado
  $('fFromWrap').hidden = !emp;
  $('fFrom').value = todayISO();
  $('fSchedules').innerHTML = emp && emp.schedules.length > 1
    ? emp.schedules.map((s) => `<li>desde ${fmtD(s.valid_from)}: ${fmtH(s.daily_minutes * 60000)} · ${workdaysLabel(s.workdays)}</li>`).join('')
    : '';
  $('fHired').value = emp?.hired_on || todayISO();
  $('fTerminated').value = emp?.terminated_on || '';
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
  const [h, m] = ($('fHours').value || '00:00').split(':').map(Number);
  const body = {
    name: $('fName').value,
    daily_minutes: h * 60 + m,
    workdays: [...document.querySelectorAll('#fDays input:checked')].map((cb) => cb.value).join(''),
    hired_on: $('fHired').value || null,
  };
  if (editingEmp) {
    body.terminated_on = $('fTerminated').value || null;
    body.schedule_from = $('fFrom').value || null;
  }
  const pin = $('fPin').value.trim();
  if (pin || !editingEmp) body.pin = pin;
  try {
    if (editingEmp) await api('/employees/' + editingEmp.id, { method: 'PATCH', body: JSON.stringify(body) });
    else await api('/employees', { method: 'POST', body: JSON.stringify(body) });
    $('empDialog').close();
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
      loadAlerts();
    }
    if (btn.dataset.act === 'toggle') {
      await api('/employees/' + emp.id, { method: 'PATCH', body: JSON.stringify({ active: !emp.active }) });
    } else if (btn.dataset.act === 'del') {
      const ok = await ask({
        title: `Excluir ${emp.name}?`,
        message: 'Só cadastros feitos por engano, sem nenhum registro de ponto, podem ser excluídos. Quem já bateu ponto deve ser desativado.',
        ok: 'Excluir',
        danger: true,
      });
      if (ok === null) return;
      await api('/employees/' + emp.id, { method: 'DELETE' });
    }
    await loadEmployees();
    loadReport();
    loadAudit();
  } catch (err) { $('empError').textContent = err.message; }
});

// ---------- Espelho de ponto ----------

const now = new Date();
const currentMonth = `${now.getFullYear()}-${pad(now.getMonth() + 1)}`;
$('repMonth').value = currentMonth;

function chip(p, day) {
  const next = localDate(p.ts) !== day ? '<sup>+1</sup>' : '';
  const off = p.offline ? '<span class="off-mark" title="Feita sem conexão: horário do aparelho">off</span>' : '';
  const cel = p.source === 'app'
    ? `<span class="off-mark${p.clock_suspect ? ' suspect' : ''}" title="Feita no app de celular${p.clock_suspect ? ': horário do celular à frente do servidor, confira' : ''}">cel</span>`
    : '';
  const label = `${kind(p.type)} ${fmtT(p.ts)}${next}${p.manual ? '*' : ''}${off}${cel}`;
  if (p.deleted_at) {
    return `<span class="chip">
      <span class="stamp deleted" title="Excluída em ${fmtDT(p.deleted_at)}">${label}</span>
      <button class="x restore" data-restore="${p.id}" title="Restaurar batida" aria-label="Restaurar batida">↺</button>
    </span>`;
  }
  const info = [`Comprovante nº ${p.id} · ${p.receipt}`];
  if (p.original_ts) info.push(`Original do relógio: ${kind(p.original_type)} ${fmtT(p.original_ts)}`);
  if (p.note) info.push(`Motivo: ${p.note}`);
  info.push('Clique para corrigir');
  const cls = `${p.type === 'entrada' ? 'in' : 'out'}${String(p.id) === editingId ? ' editing' : ''}`;
  return `<span class="chip">
    <button class="stamp ${cls}" data-edit="${p.id}" title="${esc(info.join(' · '))}">${label}</button>
    <button class="x" data-del="${p.id}" title="Excluir batida" aria-label="Excluir batida">✕</button>
  </span>`;
}

async function loadReport() {
  const emp = $('repEmp').value;
  const month = $('repMonth').value;
  $('repError').textContent = '';
  $('printLink').href = `/imprimir?mes=${month}`;
  if (!emp || !month) {
    $('summary').innerHTML = '';
    $('closure').innerHTML = '';
    $('repSub').textContent = '';
    $('report').innerHTML = '<tr><td colspan="6" class="empty">Cadastre um funcionário para ver o espelho.</td></tr>';
    return;
  }
  let r;
  try { r = await api(`/report?employee=${emp}&month=${month}`); } catch (err) { $('repError').textContent = err.message; return; }

  const showDeleted = $('showDeleted').checked;
  const e = employees.find((x) => String(x.id) === emp);
  $('repSub').textContent = e ? `Jornada atual: ${fmtH(e.daily_minutes * 60000)} · ${workdaysLabel(e.workdays)}` : '';
  punches = {};
  const count = (s) => r.days.filter((d) => d.status === s).length;
  const alerts = r.days.reduce((n, d) => n + d.alerts.length, 0);
  const untilNote = month === currentMonth ? '<small>até ontem</small>' : '';
  $('summary').innerHTML = `
    <div><span>Trabalhado</span><strong>${fmtH(r.totalMs)}</strong></div>
    <div><span>Noturno</span><strong>${fmtH(r.nightMs)}</strong><small>base do adicional</small></div>
    <div><span>Previsto</span><strong>${fmtH(r.expectedMs)}</strong>${untilNote}</div>
    <div><span>Saldo do mês</span><strong class="${signCls(r.balanceMs)}">${fmtSigned(r.balanceMs)}</strong>${untilNote}</div>
    <div><span>Banco de horas</span><strong class="${signCls(r.bankMs)}">${fmtSigned(r.bankMs)}</strong><small>anterior: ${fmtSigned(r.previousBalanceMs)}</small></div>
    <div><span>Faltas</span><strong>${count('falta')}</strong></div>
    <div><span>Incompletos</span><strong>${count('incompleto')}</strong></div>
    <div><span>Avisos da CLT</span><strong class="${alerts ? 'neg' : ''}">${alerts}</strong></div>`;

  // Fechamento do mês: trava as batidas e libera a ciência do funcionário no relógio
  const c = r.closure;
  const monthEnded = month < currentMonth;
  // Fechamentos desfeitos por reabertura: a ciência dada na época continua registrada
  const reopened = r.reopenings.length
    ? `<ul class="history reopenings">${r.reopenings.map((o) => `<li>Fechado por ${esc(o.closed_by || '?')} em ${o.closed_at ? fmtDT(o.closed_at) : '?'} ·
        ${o.acknowledged_at ? `ciência em ${fmtDT(o.acknowledged_at)}` : 'sem ciência'} ·
        <b>reaberto</b> por ${esc(o.reopened_by)} em ${fmtDT(o.reopened_at)}${o.note ? ` · motivo: ${esc(o.note)}` : ''}</li>`).join('')}</ul>`
    : '';
  $('closure').innerHTML = (c
    ? `<p><b>Mês fechado</b> por ${esc(c.closed_by)} em ${fmtDT(c.closed_at)} ·
         ${c.acknowledged_at ? `ciência do funcionário em ${fmtDT(c.acknowledged_at)}` : 'aguardando a ciência do funcionário no relógio'}</p>
       <button class="btn btn-sm" type="button" data-closure="reopen">Reabrir mês</button>`
    : monthEnded
      ? `<p>Mês em aberto: confira, corrija e feche. Depois de fechado, as batidas ficam travadas e o funcionário pode dar ciência no relógio.</p>
         <button class="btn btn-sm btn-primary" type="button" data-closure="one">Fechar mês deste funcionário</button>
         <button class="btn btn-sm" type="button" data-closure="all">Fechar mês de todos</button>`
      : '') + reopened;
  $('closure').className = 'closure' + (c ? ' is-closed' : '');

  $('report').innerHTML = r.days.length
    ? r.days.map((d) => {
        const dia = new Date(d.date + 'T12:00:00').toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit' });
        d.punches.forEach((p) => { punches[p.id] = p; });
        const chips = d.punches.filter((p) => showDeleted || !p.deleted_at).map((p) => chip(p, d.date)).join('');
        const tag = STATUS[d.status] ? `<span class="tag ${d.status}">${STATUS[d.status]}</span>` : '';
        const holiday = d.holiday ? `<small class="holiday">${esc(d.holiday)}</small>` : '';
        const warn = d.alerts.length ? `<span class="warn" tabindex="0" title="${esc(d.alerts.join('\n'))}" aria-label="${esc(d.alerts.join('; '))}">⚠</span>` : '';
        const hasHours = d.workedMs || d.punches.some((p) => !p.deleted_at);
        const showBalance = d.closed && (d.expectedMs || d.workedMs);
        const rowCls = ['folga', 'feriado', 'fora'].includes(d.status) ? 'folga' : '';
        return `<tr class="${rowCls}">
          <td class="day">${dia}${tag}${holiday}</td>
          <td class="wrap"><div class="chips">${chips || '<span class="muted">—</span>'}${warn}</div>
            ${d.alerts.length ? `<small class="alerts">${d.alerts.map(esc).join(' · ')}</small>` : ''}</td>
          <td class="num">${hasHours ? fmtH(d.workedMs) : ''}</td>
          <td class="num muted col-night">${d.nightMs ? fmtH(d.nightMs) : ''}</td>
          <td class="num muted col-expected">${d.expectedMs ? fmtH(d.expectedMs) : ''}</td>
          <td class="num ${signCls(d.balanceMs)}">${showBalance ? fmtSigned(d.balanceMs) : ''}</td>
        </tr>`;
      }).join('')
    : '<tr><td colspan="6" class="empty">Este mês ainda não começou.</td></tr>';
}

$('closure').addEventListener('click', async (e) => {
  const act = e.target.closest('[data-closure]')?.dataset.closure;
  if (!act) return;
  const emp = $('repEmp').value;
  const month = $('repMonth').value;
  $('repError').textContent = '';
  try {
    if (act === 'reopen') {
      const note = await ask({
        title: 'Reabrir o mês?',
        message: 'As batidas voltam a poder ser corrigidas e o funcionário precisará dar ciência de novo depois do novo fechamento. O fechamento e a ciência atuais ficam guardados na auditoria.',
        input: 'Motivo da reabertura (obrigatório)',
        ok: 'Reabrir',
      });
      if (note === null) return;
      if (!note) { $('repError').textContent = 'Informe o motivo da reabertura.'; return; }
      await api(`/closures/${emp}/${month}?note=${encodeURIComponent(note)}`, { method: 'DELETE' });
    } else {
      const all = act === 'all';
      const ok = await ask({
        title: all ? 'Fechar o mês de todos?' : 'Fechar o mês deste funcionário?',
        message: 'Depois de fechado, nenhuma batida do mês pode ser lançada, corrigida ou excluída sem reabrir o mês.',
        ok: 'Fechar mês',
      });
      if (ok === null) return;
      await api('/closures', { method: 'POST', body: JSON.stringify({ month, employee_id: all ? null : Number(emp) }) });
    }
  } catch (err) { $('repError').textContent = err.message; }
  loadReport();
  loadAudit();
});

$('summaryCsvBtn').addEventListener('click', () => downloadCsv(`/api/admin/summary?month=${$('repMonth').value}&format=csv`));

$('repEmp').addEventListener('change', () => { cancelEdit(); loadReport(); });
$('repMonth').addEventListener('change', () => { cancelEdit(); loadReport(); });
$('showDeleted').addEventListener('change', loadReport);

$('report').addEventListener('click', async (e) => {
  const t = e.target.closest('[data-edit], [data-del], [data-restore]');
  if (!t) return;
  if (t.dataset.edit) return startEdit(t.dataset.edit);
  $('manError').textContent = '';
  try {
    if (t.dataset.del) {
      const id = t.dataset.del;
      const note = await ask({
        title: 'Excluir esta batida?',
        message: 'Ela deixa de contar nas horas, mas continua registrada e pode ser restaurada em “Mostrar excluídas”.',
        input: 'Motivo (opcional)',
        ok: 'Excluir',
        danger: true,
      });
      if (note === null) return;
      await api(`/punches/${id}?note=${encodeURIComponent(note)}`, { method: 'DELETE' });
      if (id === editingId) cancelEdit();
    } else {
      await api(`/punches/${t.dataset.restore}/restore`, { method: 'POST' });
    }
  } catch (err) { $('manError').textContent = err.message; }
  loadReport();
});

// ---------- Corrigir batida ----------

async function showHistory(id) {
  const p = punches[id];
  let changes = [];
  try { changes = await api(`/punches/${id}/history`); } catch { /* mostra só o que já se sabe */ }
  if (id !== editingId) return;
  const describe = (c) => ({
    criada: `${kindLabel(c.new_type)} ${fmtDT(c.new_ts)}`,
    alterada: `${kindLabel(c.old_type)} ${fmtDT(c.old_ts)} → ${kindLabel(c.new_type)} ${fmtDT(c.new_ts)}`,
    excluida: `${kindLabel(c.old_type)} ${fmtDT(c.old_ts)}`,
    restaurada: '',
  }[c.action]);
  const items = [];
  if (p.original_ts) items.push(`<li><b>Registrada pelo relógio:</b> ${kindLabel(p.original_type)} ${fmtDT(p.original_ts)}</li>`);
  for (const c of changes) {
    items.push(`<li>${fmtDT(c.at)} · ${esc(c.user)} · <b>${ACTION[c.action]}</b> ${describe(c)}${c.note ? ` · motivo: ${esc(c.note)}` : ''}</li>`);
  }
  $('history').innerHTML = items.length
    ? `<h4 class="history-title">Histórico desta batida</h4><ul class="history">${items.join('')}</ul>`
    : '<p class="hint">Batida registrada pelo relógio, sem correções.</p>';
}

function startEdit(id) {
  const p = punches[id];
  if (!p) return;
  editingId = id;
  $('manTitle').textContent = 'Corrigir batida';
  $('manHint').textContent = 'O horário original fica guardado no histórico e a batida passa a ser marcada com *.';
  $('manTs').value = toLocalInput(p.ts);
  $('manType').value = p.type;
  $('manNote').value = '';
  $('manSubmit').textContent = 'Salvar correção';
  $('manCancel').hidden = false;
  $('manError').textContent = '';
  document.querySelectorAll('[data-edit]').forEach((b) => b.classList.toggle('editing', b.dataset.edit === id));
  $('manTs').focus();
  $('manTitle').scrollIntoView({ behavior: 'smooth', block: 'center' });
  showHistory(id);
}

function cancelEdit() {
  editingId = null;
  $('manTitle').textContent = 'Lançamento manual';
  $('manHint').textContent = 'Para registrar uma batida esquecida. O motivo é obrigatório e fica no histórico.';
  $('manNote').value = '';
  $('manSubmit').textContent = 'Lançar';
  $('manCancel').hidden = true;
  $('manError').textContent = '';
  $('history').innerHTML = '';
  document.querySelectorAll('[data-edit].editing').forEach((b) => b.classList.remove('editing'));
}

$('manCancel').addEventListener('click', cancelEdit);

$('manual').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('manError').textContent = '';
  const fields = {
    ts: new Date($('manTs').value).toISOString(),
    type: $('manType').value,
    note: $('manNote').value,
  };
  try {
    if (editingId) {
      await api('/punches/' + editingId, { method: 'PATCH', body: JSON.stringify(fields) });
      cancelEdit();
    } else {
      await api('/punches', { method: 'POST', body: JSON.stringify({ employee_id: $('repEmp').value, ...fields }) });
      $('manNote').value = '';
    }
    loadReport();
  } catch (err) { $('manError').textContent = err.message; }
});

async function downloadFile(url, errorEl, fallbackName) {
  const res = await fetch(url).catch(() => null);
  if (res?.status === 401) return toLogin();
  if (!res?.ok) return (errorEl.textContent = 'Não foi possível exportar.');
  const blobUrl = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = (res.headers.get('Content-Disposition') || '').match(/filename="(.+)"/)?.[1] || fallbackName;
  a.click();
  URL.revokeObjectURL(blobUrl);
  if (url.includes('/export')) loadAudit(); // a exportação fica registrada
}
const downloadCsv = (url) => downloadFile(url, $('repError'), 'ponto.csv');

$('csvBtn').addEventListener('click', () => {
  const emp = $('repEmp').value;
  const month = $('repMonth').value;
  if (emp && month) downloadCsv(`/api/admin/report?employee=${emp}&month=${month}&format=csv`);
});

// ---------- Feriados ----------

$('holYear').value = now.getFullYear();

async function loadHolidays() {
  let items = [];
  try { items = await api(`/holidays?year=${$('holYear').value}`); } catch (err) { $('holError').textContent = err.message; }
  $('holidays').innerHTML = items.map((h) => `
    <tr>
      <td>${new Date(h.date + 'T12:00:00').toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' })}</td>
      <td>${esc(h.name)}${h.national ? ' <span class="muted">· nacional</span>' : ''}</td>
      <td class="actions">${h.national ? '' : `<button class="btn btn-sm btn-danger" data-hol="${h.date}">Remover</button>`}</td>
    </tr>`).join('');
}

$('holYear').addEventListener('change', loadHolidays);
$('holForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('holError').textContent = '';
  try {
    await api('/holidays', { method: 'POST', body: JSON.stringify({ date: $('holDate').value, name: $('holName').value }) });
    $('holYear').value = $('holDate').value.slice(0, 4);
    $('holName').value = '';
    loadHolidays();
    loadReport();
    loadAudit();
  } catch (err) { $('holError').textContent = err.message; }
});
$('holidays').addEventListener('click', async (e) => {
  const day = e.target.closest('[data-hol]')?.dataset.hol;
  if (!day) return;
  try { await api(`/holidays/${day}`, { method: 'DELETE' }); } catch (err) { $('holError').textContent = err.message; }
  loadHolidays();
  loadReport();
  loadAudit();
});

// ---------- Administradores e relógios ----------

let currentUser = '';

async function loadAdmins() {
  let admins = [];
  try { admins = await api('/admins'); } catch (err) { $('admError').textContent = err.message; }
  $('admins').innerHTML = admins.map((a) => `
    <tr>
      <td class="who">${esc(a.username)}${a.username === currentUser ? ' <span class="muted">(você)</span>' : ''}${a.superadmin ? ' <span class="muted">· superadministrador</span>' : ''}</td>
      <td>${fmtDT(a.updated_at)}</td>
      <td class="actions">${a.username === currentUser || a.superadmin ? '' : `<button class="btn btn-sm btn-danger" data-adm="${a.id}" data-name="${esc(a.username)}">Excluir</button>`}</td>
    </tr>`).join('');
}

$('admForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('admError').textContent = '';
  try {
    await api('/admins', { method: 'POST', body: JSON.stringify({ username: $('admUser').value, password: $('admPass').value }) });
    $('admUser').value = '';
    $('admPass').value = '';
    loadAdmins();
    loadAudit();
  } catch (err) { $('admError').textContent = err.message; }
});
$('admins').addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-adm]');
  if (!btn) return;
  const ok = await ask({ title: `Excluir o administrador ${btn.dataset.name}?`, message: 'Ele perde o acesso na hora. O histórico de correções feitas por ele é mantido.', ok: 'Excluir', danger: true });
  if (ok === null) return;
  try { await api(`/admins/${btn.dataset.adm}`, { method: 'DELETE' }); } catch (err) { $('admError').textContent = err.message; }
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

// ---------- Solicitações do app ----------

const REQ_ACTION = { incluir: 'Incluir batida', alterar: 'Corrigir batida', excluir: 'Excluir batida' };
const REQ_STATUS = { aprovada: 'aprovada', recusada: 'recusada' };

function describeRequest(r) {
  const current = r.current_ts ? `${kindLabel(r.current_type)} ${fmtDT(r.current_ts)}` : '';
  const wanted = r.ts || r.type ? `${kindLabel(r.type || r.current_type)} ${fmtDT(r.ts || r.current_ts)}` : '';
  if (r.action === 'incluir') return `${wanted}`;
  if (r.action === 'excluir') return `<s>${current}</s>`;
  return `${current} → <b>${wanted}</b>`;
}

async function loadRequests() {
  const all = $('reqShowAll').checked;
  let items = [];
  try { items = await api(`/requests?status=${all ? '' : 'pendente'}`); } catch (err) { $('reqError').textContent = err.message; }
  const pending = items.filter((r) => r.status === 'pendente').length;
  $('reqCount').textContent = pending ? pending : '';
  $('tabReqCount').textContent = pending ? pending : '';
  $('reqCard').classList.toggle('has-pending', pending > 0);
  $('requests').innerHTML = items.length
    ? items.map((r) => `
        <tr>
          <td class="who">${esc(r.employee_name)}</td>
          <td class="wrap"><b>${REQ_ACTION[r.action]}</b>: ${describeRequest(r)}
            ${r.note ? `<small class="contract">${esc(r.note)}</small>` : ''}
            ${r.status !== 'pendente' ? `<small class="contract">${REQ_STATUS[r.status]} por ${esc(r.decided_by)} em ${fmtDT(r.decided_at)}${r.decision_note ? ` · ${esc(r.decision_note)}` : ''}</small>` : ''}</td>
          <td>${fmtDT(r.requested_at)}</td>
          <td class="actions">${r.status === 'pendente' ? `
            <button class="btn btn-sm btn-primary" data-req="approve" data-id="${r.id}">Aprovar</button>
            <button class="btn btn-sm btn-danger" data-req="reject" data-id="${r.id}">Recusar</button>` : `<span class="tag ${r.status === 'recusada' ? 'falta' : 'andamento'}">${REQ_STATUS[r.status]}</span>`}</td>
        </tr>`).join('')
    : `<tr><td colspan="4" class="empty">${all ? 'Nenhuma solicitação ainda.' : 'Nenhuma solicitação pendente.'}</td></tr>`;
}

$('reqShowAll').addEventListener('change', loadRequests);
$('requests').addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-req]');
  if (!btn) return;
  $('reqError').textContent = '';
  const approve = btn.dataset.req === 'approve';
  const note = await ask({
    title: approve ? 'Aprovar a solicitação?' : 'Recusar a solicitação?',
    message: approve
      ? 'A batida será lançada ou corrigida agora, com o pedido registrado no histórico.'
      : 'Nada muda no ponto. O motivo fica registrado na solicitação.',
    input: approve ? 'Observação (opcional)' : 'Motivo da recusa (opcional)',
    ok: approve ? 'Aprovar' : 'Recusar',
    danger: !approve,
  });
  if (note === null) return;
  try {
    await api(`/requests/${btn.dataset.id}/${btn.dataset.req}`, { method: 'POST', body: JSON.stringify({ note }) });
  } catch (err) { $('reqError').textContent = err.message; }
  loadRequests();
  loadReport();
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
  try { await api(`/devices/${id}`, { method: 'DELETE' }); } catch (err) { $('devError').textContent = err.message; }
  loadDevices();
  loadAudit();
});

// ---------- Avisos e auditoria ----------

async function loadAlerts() {
  let a;
  try { a = await api('/alerts'); } catch { return; }
  const items = [];
  if (a.pin_blocks.length) {
    const last = a.pin_blocks[0];
    items.push(`<li><b>Relógio bloqueado por PINs errados ${a.pin_blocks.length === 1 ? '1 vez' : `${a.pin_blocks.length} vezes`} nas últimas 24h</b>
      (último às ${fmtDT(last.at)}${last.ip ? `, aparelho ${esc(last.ip)}` : ''}). Pode ser alguém tentando adivinhar PINs.
      Se ninguém esqueceu o PIN, confira quem estava no relógio.</li>`);
  }
  if (a.devices_expiring) {
    items.push(`<li><b>${a.devices_expiring === 1 ? '1 chave de celular vence' : `${a.devices_expiring} chaves de celular vencem`} nos próximos dias.</b>
      Em Funcionários → Celular, gere uma chave nova e passe ao funcionário antes do vencimento.</li>`);
  }
  if (a.retention_due) {
    items.push(`<li><b>${a.retention_due === 1 ? '1 ex-funcionário passou' : `${a.retention_due} ex-funcionários passaram`} do prazo de guarda.</b>
      Os registros de ponto só precisam ser guardados até 5 anos depois do desligamento (LGPD): use “Anonimizar” na lista de funcionários.</li>`);
  }
  if (a.short_pins) {
    items.push(`<li><b>${a.short_pins === 1 ? '1 funcionário tem' : `${a.short_pins} funcionários têm`} PIN de 4 ou 5 dígitos.</b>
      Esses PINs ainda funcionam, mas são fáceis de adivinhar: troque por um de 6 dígitos em “Editar” (marcados com <span class="tag falta">PIN curto</span>).</li>`);
  }
  $('alertsList').innerHTML = items.join('');
  $('alertsCard').hidden = !items.length;
}

let auditLast = null; // id do registro mais antigo carregado (para "Carregar mais")
const AUDIT_PAGE = 50;

async function loadAudit(more = false) {
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

// ---------- Empresas (só o superadministrador) ----------

let companies = [];
let editingCompany = null; // empresa sendo editada no formulário (null = nova)

async function loadCompanies(openId) {
  try { companies = await request('/api/companies'); } catch (err) { $('coError').textContent = err.message; return; }
  $('companies').innerHTML = companies.length
    ? companies.map((c) => `
        <tr>
          <td class="who">${esc(c.name)}${c.active ? '' : '<span class="tag inativo">desativada</span>'}${c.id === openId ? ' <span class="muted">(aberta)</span>' : ''}</td>
          <td>${c.privacy_contact ? esc(c.privacy_contact) : '<span class="muted">—</span>'}</td>
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
  const body = { name: $('coName').value, privacy_contact: $('coContact').value };
  try {
    if (editingCompany) {
      await request(`/api/companies/${editingCompany.id}`, { method: 'PATCH', body: JSON.stringify(body) });
      if (editingCompany.id === openCompanyId) $('companyName').textContent = body.name.trim();
    } else {
      body.admin_username = $('coAdmUser').value;
      body.admin_password = $('coAdmPass').value;
      const created = await request('/api/companies', { method: 'POST', body: JSON.stringify(body) });
      if (!openCompanyId) return openCompany(created.id); // primeira empresa: já abre
    }
    companyForm();
    loadCompanies(openCompanyId);
    loadSystemAudit();
    if (openCompanyId) loadAudit();
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
  } catch (err) { $('coError').textContent = err.message; }
  loadCompanies(openCompanyId);
  loadSystemAudit();
  if (openCompanyId) loadAudit();
});

// ---------- Regras de jornada ----------

const RULE_PRESETS = {
  urbano: { night_start_hour: 22, night_end_hour: 5, night_hour_minutes: 52.5 },
  lavoura: { night_start_hour: 21, night_end_hour: 5, night_hour_minutes: 60 },
  pecuaria: { night_start_hour: 20, night_end_hour: 4, night_hour_minutes: 60 },
};
const RULE_INPUTS = { tolerance_minutes: 'rTol', night_start_hour: 'rNightStart', night_end_hour: 'rNightEnd', night_hour_minutes: 'rNightMin', max_shift_hours: 'rMaxShift' };
const nightMin = (m) => String(m).replace('.', ',');
const ruleText = (r) => `tolerância de ${r.tolerance_minutes} min · noturno das ${r.night_start_hour}h às ${r.night_end_hour}h (hora de ${nightMin(r.night_hour_minutes)} min) · jornada máxima de ${r.max_shift_hours} h`;

async function loadRules() {
  let r;
  try { r = await api('/rules'); } catch (err) { $('ruleError').textContent = err.message; return; }
  const today = todayISO();
  const current = [...r.periods].reverse().find((p) => p.valid_from <= today) || r.periods[0];
  $('rulesNow').textContent = current ? `Hoje: ${ruleText(current)}` : '';
  $('rulePeriods').innerHTML = r.periods.slice().reverse().map((p) => `
    <tr>
      <td>${p.valid_from === '2000-01-01' ? 'sempre' : fmtD(p.valid_from)}${p.valid_from > today ? ' <span class="muted">(futura)</span>' : ''}</td>
      <td>${p.tolerance_minutes} min</td>
      <td>${p.night_start_hour}h às ${p.night_end_hour}h · hora de ${nightMin(p.night_hour_minutes)} min</td>
      <td>${p.max_shift_hours} h</td>
      <td>${esc(p.created_by)}<small class="contract">${fmtDT(p.created_at)}</small></td>
    </tr>`).join('');
  // O formulário começa com as regras de hoje, para mudar só o que for preciso
  $('ruleForm').hidden = !r.can_edit;
  if (current) for (const [field, id] of Object.entries(RULE_INPUTS)) $(id).value = current[field];
  if (!$('rFrom').value) $('rFrom').value = today;
  $('sTz').value = r.timezone;
  $('sOffline').value = r.offline_max_hours;
  for (const id of ['sTz', 'sOffline']) $(id).disabled = !r.can_edit;
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
  const ok = await ask({
    title: `Novas regras a partir de ${fmtD(body.valid_from)}?`,
    message: `${ruleText(body)}. Os dias anteriores e o banco de horas acumulado até lá não mudam. Não é possível começar num mês já fechado.`,
    ok: 'Salvar regras',
  });
  if (ok === null) return;
  try {
    await api('/rules', { method: 'POST', body: JSON.stringify(body) });
    loadRules();
    loadReport();
    loadAudit();
  } catch (err) { $('ruleError').textContent = err.message; }
});
$('settingsForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('settingsError').textContent = '';
  try {
    await api('/rules/settings', { method: 'PATCH', body: JSON.stringify({ timezone: $('sTz').value.trim(), offline_max_hours: Number($('sOffline').value) }) });
    loadRules();
    loadAudit();
  } catch (err) { $('settingsError').textContent = err.message; }
});

// ---------- Superadministradores e auditoria do sistema ----------

async function loadSuperadmins() {
  let items = [];
  try { items = await request('/api/companies/superadmins'); } catch (err) { $('saError').textContent = err.message; }
  $('superadmins').innerHTML = items.map((a) => `
    <tr>
      <td class="who">${esc(a.username)}${a.username === currentUser ? ' <span class="muted">(você)</span>' : ''}</td>
      <td>${fmtDT(a.updated_at)}</td>
      <td class="actions">${a.username === currentUser ? '' : `<button class="btn btn-sm btn-danger" data-sa="${a.id}" data-name="${esc(a.username)}">Excluir</button>`}</td>
    </tr>`).join('');
}

$('saForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('saError').textContent = '';
  try {
    await request('/api/companies/superadmins', { method: 'POST', body: JSON.stringify({ username: $('saUser').value, password: $('saPass').value }) });
    $('saUser').value = '';
    $('saPass').value = '';
    loadSuperadmins();
    loadSystemAudit();
  } catch (err) { $('saError').textContent = err.message; }
});
$('superadmins').addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-sa]');
  if (!btn) return;
  const ok = await ask({ title: `Excluir o superadministrador ${btn.dataset.name}?`, message: 'Ele perde o acesso na hora. O histórico do que ele fez é mantido.', ok: 'Excluir', danger: true });
  if (ok === null) return;
  try { await request(`/api/companies/superadmins/${btn.dataset.sa}`, { method: 'DELETE' }); } catch (err) { $('saError').textContent = err.message; }
  loadSuperadmins();
  loadSystemAudit();
});

let sysAuditLast = null;

async function loadSystemAudit(more = false) {
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

// ---------- Abas ----------
// Cada cartão pertence a uma aba (data-tab). A aba aberta fica no endereço (/admin#espelho), para o
// voltar do navegador e os links funcionarem.

const TABS = [...document.querySelectorAll('[role="tab"]')];
// Guardada antes da primeira showTab, que ainda não sabe quais abas o usuário vê (Empresas fica escondida)
const initialTab = location.hash.slice(1);

function showTab(name) {
  const available = TABS.filter((t) => !t.hidden).map((t) => t.dataset.tab);
  if (!available.includes(name)) name = available[0];
  for (const tab of TABS) {
    const on = tab.dataset.tab === name;
    tab.setAttribute('aria-selected', on);
    tab.tabIndex = on ? 0 : -1;
  }
  document.querySelectorAll('section[data-tab]').forEach((s) => s.classList.toggle('tab-off', s.dataset.tab !== name));
  if (location.hash.slice(1) !== name) history.replaceState(null, '', `#${name}`);
}

TABS.forEach((tab, i) => {
  tab.addEventListener('click', () => { location.hash = tab.dataset.tab; });
  // Setas do teclado passam de uma aba para a vizinha (padrão de abas acessíveis)
  tab.addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const visible = TABS.filter((t) => !t.hidden);
    const next = visible[(visible.indexOf(tab) + (e.key === 'ArrowRight' ? 1 : visible.length - 1)) % visible.length];
    next.focus();
    location.hash = next.dataset.tab;
  });
});
window.addEventListener('hashchange', () => showTab(location.hash.slice(1)));
showTab(location.hash.slice(1));

// ---------- Início ----------

let openCompanyId = null;

function loadCompanyArea() {
  loadRequests();
  setInterval(loadRequests, 60000);
  loadAdmins();
  loadEmployees().then(() => { loadReport(); loadAudit(); }).catch((err) => { $('empError').textContent = err.message; });
  loadHolidays();
  loadRules();
  loadAlerts();
  setInterval(loadAlerts, 60000);
}

// A página só abre com o login do admin (o nginx confere o cookie antes)
fetch('/api/auth/admin').then((r) => (r.ok ? r.json() : null)).then((me) => {
  if (!me) return toLogin();
  if (me.pending) return location.replace('/senha');
  currentUser = me.user || '';
  openCompanyId = me.company_id;
  $('whoami').textContent = currentUser ? `Você entrou como ${currentUser}` : '';
  $('companyName').textContent = me.superadmin ? '' : me.company || '';
  $('companyName').hidden = me.superadmin;
  $('coCard').hidden = !me.superadmin;
  $('companyArea').hidden = !openCompanyId;
  // Sem empresa aberta, só a aba Empresas (superadmin)
  TABS.forEach((tab) => { tab.hidden = tab.dataset.tab === 'empresas' ? !me.superadmin : !openCompanyId; });
  showTab(initialTab || (openCompanyId ? 'inicio' : 'empresas'));
  if (me.superadmin) {
    loadCompanies(openCompanyId);
    loadSuperadmins();
    loadSystemAudit();
    if (!openCompanyId) $('coHint').insertAdjacentHTML('beforeend', ' <b>Nenhuma empresa aberta:</b> cadastre uma ou abra uma da lista.');
  }
  if (openCompanyId) loadCompanyArea();
}).catch(() => {});
