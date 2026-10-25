// Aba Espelho: espelho do mês, fechamento, correção e lançamento de batidas e as ausências.
import { loadAudit } from './auditoria.js';
import { $, ACTION, STATUS, api, ask, currentMonth, esc, fmtD, fmtDT, fmtH, fmtSigned, fmtT, kind, kindLabel, localDate, parseHM, shortH, signCls, toLocalInput, toLogin, toast } from './comum.js';
import { employees } from './funcionarios.js';

let punches = {};       // batidas do espelho aberto, por id
let editingId = null;   // batida sendo corrigida no formulário (null = novo lançamento)

// ---------- Espelho de ponto ----------

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

const ABSENCE_LABEL = { atestado: 'atestado', ferias: 'férias', licenca: 'licença', abonada: 'abonada', folga: 'folga do banco' };
const absenceSummary = (counts) => Object.entries(counts || {}).map(([k, n]) => `${n} ${n > 1 ? 'dias' : 'dia'} de ${ABSENCE_LABEL[k]}`).join(' · ');

export async function loadAbsences() {
  const emp = $('repEmp').value;
  if (!emp) { $('absList').innerHTML = ''; return; }
  let items = [];
  try { items = await api(`/employees/${emp}/absences`); } catch (err) { $('absError').textContent = err.message; return; }
  $('absList').innerHTML = items.length
    ? items.map((a) => `<li class="dev-row"><span><b>${esc(a.label)}</b> · ${a.first_day === a.last_day ? fmtD(a.first_day) : `${fmtD(a.first_day)} a ${fmtD(a.last_day)}`}${a.minutes ? ` · ${shortH(a.minutes)} por dia` : ''}${a.note ? ` · ${esc(a.note)}` : ''}
        <small class="contract">lançada por ${esc(a.created_by)} em ${fmtDT(a.created_at)}</small></span>
        <button class="btn btn-sm btn-danger" type="button" data-abs="${a.id}">Remover</button></li>`).join('')
    : '<li class="muted">Nenhuma ausência lançada para este funcionário.</li>';
}

$('absForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('absError').textContent = '';
  const minutes = parseHM($('absHours').value);
  if (Number.isNaN(minutes)) { $('absError').textContent = 'Horas abonadas: use horas:minutos (ex.: 02:00) ou deixe vazio para o dia inteiro.'; return; }
  const body = {
    employee_id: Number($('repEmp').value),
    kind: $('absKind').value,
    first_day: $('absFrom').value,
    last_day: $('absTo').value,
    minutes: minutes || null,
    note: $('absNote').value,
  };
  try {
    await api('/absences', { method: 'POST', body: JSON.stringify(body) });
    toast('Ausência lançada');
    $('absHours').value = '';
    $('absNote').value = '';
    loadAbsences();
    loadReport();
    loadAudit();
  } catch (err) { $('absError').textContent = err.message; }
});
$('absFrom').addEventListener('change', () => { if (!$('absTo').value || $('absTo').value < $('absFrom').value) $('absTo').value = $('absFrom').value; });
$('absKind').addEventListener('change', () => { $('absHours').disabled = $('absKind').value === 'folga'; if ($('absHours').disabled) $('absHours').value = ''; });
$('absList').addEventListener('click', async (e) => {
  const id = e.target.closest('[data-abs]')?.dataset.abs;
  if (!id) return;
  const ok = await ask({ title: 'Remover esta ausência?', message: 'Os dias voltam a contar como antes (faltas, se não houver batidas). Fica registrado na auditoria.', ok: 'Remover', danger: true });
  if (ok === null) return;
  $('absError').textContent = '';
  try { await api(`/absences/${id}`, { method: 'DELETE' }); toast('Ausência removida'); } catch (err) { $('absError').textContent = err.message; }
  loadAbsences();
  loadReport();
  loadAudit();
});

export async function loadReport() {
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
  $('repSub').textContent = e ? `Jornada atual: ${e.schedule_label}` : '';
  punches = {};
  const count = (s) => r.days.filter((d) => d.status === s).length;
  const alerts = r.days.reduce((n, d) => n + d.alerts.length, 0);
  const untilNote = month === currentMonth ? '<small>até ontem</small>' : '';
  $('summary').innerHTML = `
    <div><span>Trabalhado</span><strong>${fmtH(r.totalMs)}</strong></div>
    <div><span>Noturno</span><strong>${fmtH(r.nightMs)}</strong><small>base do adicional</small></div>
    <div><span>Previsto</span><strong>${fmtH(r.expectedMs)}</strong>${untilNote}</div>
    <div><span>Saldo do mês</span><strong class="${signCls(r.balanceMs)}">${fmtSigned(r.balanceMs)}</strong>${untilNote}</div>
    ${r.paidDays ? `<div><span>Extras no dia comum</span><strong class="pos">${fmtH(r.extraMs)}</strong><small>a pagar</small></div>
    <div><span>Extras em domingo e feriado</span><strong class="pos">${fmtH(r.extraRestMs)}</strong><small>a pagar</small></div>
    <div><span>A descontar</span><strong class="${r.deficitMs ? 'neg' : ''}">${fmtH(r.deficitMs)}</strong><small>faltas e atrasos</small></div>` : ''}
    <div><span>Banco de horas</span><strong class="${signCls(r.bankMs)}">${fmtSigned(r.bankMs)}</strong><small>anterior: ${fmtSigned(r.previousBalanceMs)}${r.initialBalanceMs ? ` · inclui saldo inicial ${fmtSigned(r.initialBalanceMs)}` : ''}</small></div>
    <div><span>Faltas</span><strong>${count('falta')}</strong></div>
    <div><span>Abonado</span><strong>${fmtH(r.creditedMs)}</strong><small>${absenceSummary(r.absenceDays) || 'sem ausências'}</small></div>
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
        // Ausência: a marca é o tipo (atestado, férias...), também nos dias sem jornada dentro do período
        const tag = d.absence
          ? `<span class="tag ausencia" title="${esc(d.absence.note)}">${esc(d.absence.label)}${d.absence.minutes ? ` · ${shortH(d.absence.minutes)}` : ''}</span>`
          : STATUS[d.status] ? `<span class="tag ${d.status}">${STATUS[d.status]}</span>` : '';
        const holiday = d.holiday ? `<small class="holiday">${esc(d.holiday)}</small>` : '';
        const warn = d.alerts.length ? `<span class="warn" tabindex="0" title="${esc(d.alerts.join('\n'))}" aria-label="${esc(d.alerts.join('; '))}">⚠</span>` : '';
        const hasHours = d.workedMs || d.punches.some((p) => !p.deleted_at);
        const showBalance = d.closed && (d.expectedMs || d.workedMs);
        const rowCls = ['folga', 'feriado', 'fora', 'antes'].includes(d.status) ? 'folga' : '';
        return `<tr class="${rowCls}">
          <td class="day">${dia}${tag}${holiday}</td>
          <td class="wrap"><div class="chips">${chips || '<span class="muted">—</span>'}${warn}</div>
            ${d.alerts.length ? `<small class="alerts">${d.alerts.map(esc).join(' · ')}</small>` : ''}</td>
          <td class="num">${hasHours ? fmtH(d.workedMs) : ''}</td>
          <td class="num muted col-night">${d.nightMs ? fmtH(d.nightMs) : ''}</td>
          <td class="num muted col-expected">${d.expectedMs ? fmtH(d.expectedMs) : ''}</td>
          <td class="num ${signCls(d.balanceMs)}">${showBalance ? fmtSigned(d.balanceMs) : ''}${d.extraRestMs ? '<small class="contract">extra dom./fer.</small>' : d.extraMs ? '<small class="contract">extra</small>' : d.deficitMs ? '<small class="contract">a descontar</small>' : ''}</td>
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
      toast('Mês reaberto');
    } else {
      const all = act === 'all';
      const ok = await ask({
        title: all ? 'Fechar o mês de todos?' : 'Fechar o mês deste funcionário?',
        message: 'Depois de fechado, nenhuma batida do mês pode ser lançada, corrigida ou excluída sem reabrir o mês.',
        ok: 'Fechar mês',
      });
      if (ok === null) return;
      await api('/closures', { method: 'POST', body: JSON.stringify({ month, employee_id: all ? null : Number(emp) }) });
      toast(all ? 'Mês fechado para todos' : 'Mês fechado');
    }
  } catch (err) { $('repError').textContent = err.message; }
  loadReport();
  loadAudit();
});

$('summaryCsvBtn').addEventListener('click', () => downloadCsv(`/api/admin/summary?month=${$('repMonth').value}&format=csv`));

$('repEmp').addEventListener('change', () => { cancelEdit(); loadReport(); loadAbsences(); });
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
      toast('Batida excluída');
      if (id === editingId) cancelEdit();
    } else {
      await api(`/punches/${t.dataset.restore}/restore`, { method: 'POST' });
      toast('Batida restaurada');
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

export function cancelEdit() {
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
      toast('Correção salva');
    } else {
      await api('/punches', { method: 'POST', body: JSON.stringify({ employee_id: $('repEmp').value, ...fields }) });
      $('manNote').value = '';
      toast('Batida lançada');
    }
    loadReport();
  } catch (err) { $('manError').textContent = err.message; }
});

export async function downloadFile(url, errorEl, fallbackName) {
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
