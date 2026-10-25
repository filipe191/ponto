// Comum a todas as abas do painel: formatação, chamadas à API, janela de confirmação e mensagem de "salvo".
export const $ = (id) => document.getElementById(id);
export const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const pad = (n) => String(n).padStart(2, '0');
export const WEEK = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom'];
export const STATUS = { falta: 'falta', incompleto: 'incompleto', andamento: 'em andamento', feriado: 'feriado', fora: 'fora do contrato', antes: 'antes do controle', ausencia: 'ausência' };
export const fmtD = (iso) => new Date(iso + 'T12:00:00').toLocaleDateString('pt-BR');
export const todayISO = () => localDate(new Date().toISOString());
export const ACTION = { criada: 'lançada', alterada: 'corrigida', excluida: 'excluída', restaurada: 'restaurada' };


// Sessão do admin expirada ou encerrada: volta para o login
export const toLogin = () => location.replace('/login?next=/admin');

// Rotas da empresa aberta no painel
export const api = (path, opts) => request('/api/admin' + path, opts);

export async function request(url, opts = {}) {
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

export const fmtH = (ms) => {
  const min = Math.round(Math.abs(ms) / 60000);
  return `${Math.floor(min / 60)}h${pad(min % 60)}`;
};
export const fmtSigned = (ms) => {
  const min = Math.round(ms / 60000);
  return (min > 0 ? '+' : min < 0 ? '−' : '') + fmtH(ms);
};
export const signCls = (ms) => { const min = Math.round(ms / 60000); return min > 0 ? 'pos' : min < 0 ? 'neg' : ''; };
export const fmtT = (iso) => new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
export const fmtDT = (iso) => new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' });
export const kind = (t) => (t === 'entrada' ? 'E' : 'S');
export const kindLabel = (t) => (t === 'entrada' ? 'Entrada' : 'Saída');
export const localDate = (iso) => { const d = new Date(iso); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
// ISO → valor do <input type="datetime-local"> no horário local
export const toLocalInput = (iso) => { const d = new Date(iso); return `${localDate(iso)}T${pad(d.getHours())}:${pad(d.getMinutes())}`; };


// ---------- Janela de confirmação ----------

// Mensagem curta no canto da tela depois de salvar; some sozinha. É um popover, para ficar acima
// até das janelas abertas (navegador sem popover: só aparece, como um elemento comum)
let toastTimer;
export function toast(message) {
  const el = $('toast');
  const show = (on) => {
    if (el.showPopover) { if (el.matches(':popover-open') !== on) el.togglePopover(on); } else el.hidden = !on;
  };
  el.textContent = message;
  el.classList.remove('toast-out');
  show(true);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.classList.add('toast-out');
    toastTimer = setTimeout(() => show(false), 300);
  }, 2500);
}
if (!$('toast').showPopover) $('toast').hidden = true;

export function ask({ title, message, input = '', ok = 'Confirmar', danger = false }) {
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


// "08:00" ou "8" → minutos; vazio = folga; NaN se inválido
export const parseHM = (v) => {
  const t = v.trim();
  if (!t) return 0;
  const m = t.match(/^(\d{1,2})(?::([0-5]\d))?$/);
  const min = m ? Number(m[1]) * 60 + Number(m[2] || 0) : NaN;
  return min <= 1440 ? min : NaN;
};
export const toHM = (min) => (min ? `${pad(Math.floor(min / 60))}:${pad(min % 60)}` : '');
export const shortH = (min) => (min ? (min % 60 ? `${Math.floor(min / 60)}h${pad(min % 60)}` : `${min / 60}h`) : 'folga');

// Mês de hoje (AAAA-MM), para o espelho e os feriados
export const now = new Date();
export const currentMonth = `${now.getFullYear()}-${pad(now.getMonth() + 1)}`;

// Quem está logado e a empresa aberta no painel (preenchidos na subida, em admin.js)
export const sessao = { user: '', companyId: null };
