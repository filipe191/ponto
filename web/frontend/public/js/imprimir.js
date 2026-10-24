const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const pad = (n) => String(n).padStart(2, '0');
const fmtH = (ms) => { const m = Math.round(Math.abs(ms) / 60000); return `${Math.floor(m / 60)}:${pad(m % 60)}`; };
const fmtSigned = (ms) => { const m = Math.round(ms / 60000); return (m > 0 ? '+' : m < 0 ? '−' : '') + fmtH(ms); };
const fmtT = (iso) => new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
const fmtDT = (iso) => new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
const localDate = (iso) => { const d = new Date(iso); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
const STATUS = { ok: '', incompleto: 'Incompleto', falta: 'Falta', folga: 'Folga', feriado: 'Feriado', fora: 'Fora do contrato', andamento: 'Em andamento' };

async function get(path) {
  const res = await fetch('/api/admin' + path);
  if (res.status === 401) { location.replace('/login?next=/imprimir'); throw new Error(''); }
  if (res.status === 403) { location.replace('/senha'); throw new Error(''); }
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || 'Erro');
  return res.json();
}

function sheet(r) {
  const [y, m] = r.month.split('-').map(Number);
  const monthName = new Date(y, m - 1, 1).toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' });
  const rows = r.days.map((d) => {
    const punches = d.punches.filter((p) => !p.deleted_at).map((p) =>
      `${p.type === 'entrada' ? 'E' : 'S'} ${fmtT(p.ts)}${localDate(p.ts) !== d.date ? ' (+1)' : ''}${p.manual ? '*' : ''}${p.offline ? ' (off)' : ''}${p.source === 'app' ? ' (cel)' : ''}`).join('  ');
    const dia = new Date(d.date + 'T12:00:00').toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit' });
    const status = [STATUS[d.status], d.holiday, ...d.alerts].filter(Boolean).join(' · ');
    const muted = ['folga', 'feriado', 'fora'].includes(d.status) ? 'muted' : '';
    return `<tr class="${muted}"><td>${dia}</td><td>${punches}</td><td class="n">${d.workedMs ? fmtH(d.workedMs) : ''}</td>
      <td class="n">${d.nightMs ? fmtH(d.nightMs) : ''}</td><td class="n">${d.expectedMs ? fmtH(d.expectedMs) : ''}</td>
      <td class="n">${d.closed && (d.expectedMs || d.workedMs) ? fmtSigned(d.balanceMs) : ''}</td><td class="status">${esc(status)}</td></tr>`;
  }).join('');
  const c = r.closure;
  return `<section class="card sheet">
    <h2>Espelho de ponto · ${esc(r.employee.name)}</h2>
    <div class="meta"><span>${monthName}</span>
      <span>${c ? `Fechado por ${esc(c.closed_by)} em ${fmtDT(c.closed_at)}${c.acknowledged_at ? ` · ciência do funcionário em ${fmtDT(c.acknowledged_at)}` : ''}` : 'Mês não fechado'}</span></div>
    <table>
      <thead><tr><th>Dia</th><th>Batidas</th><th class="n">Trab.</th><th class="n">Not.</th><th class="n">Prev.</th><th class="n">Saldo</th><th>Situação</th></tr></thead>
      <tbody>${rows}</tbody>
      <tfoot><tr><td colspan="2">Totais · banco anterior ${fmtSigned(r.previousBalanceMs)} · banco ao fim do mês ${fmtSigned(r.bankMs)}</td>
        <td class="n">${fmtH(r.totalMs)}</td><td class="n">${fmtH(r.nightMs)}</td><td class="n">${fmtH(r.expectedMs)}</td><td class="n">${fmtSigned(r.balanceMs)}</td><td></td></tr></tfoot>
    </table>
    <p class="notes">E entrada · S saída · * lançada ou corrigida manualmente · (+1) no dia seguinte · (off) feita sem conexão · (cel) feita no app de celular · horas noturnas com hora noturna reduzida e tolerância diária conforme as regras de jornada da empresa.</p>
    <div class="signs"><div>${esc(r.employee.name)}</div><div>Responsável</div></div>
  </section>`;
}

async function load() {
  const month = $('month').value;
  $('sheets').innerHTML = '';
  $('status').textContent = 'Carregando…';
  try {
    const summary = await get(`/summary?month=${month}`);
    const reports = await Promise.all(summary.map((s) => get(`/report?employee=${s.employee.id}&month=${month}`)));
    $('sheets').innerHTML = reports.map(sheet).join('') || '<p class="card sheet">Nenhum funcionário com contrato neste mês.</p>';
    $('status').textContent = `${reports.length} espelho(s)`;
  } catch (err) { $('status').textContent = err.message; }
}

const params = new URLSearchParams(location.search);
const now = new Date();
$('month').value = /^\d{4}-\d{2}$/.test(params.get('mes') || '') ? params.get('mes') : `${now.getFullYear()}-${pad(now.getMonth() + 1)}`;
$('month').addEventListener('change', () => { history.replaceState(null, '', `?mes=${$('month').value}`); load(); });
$('print').addEventListener('click', () => window.print());
load();
