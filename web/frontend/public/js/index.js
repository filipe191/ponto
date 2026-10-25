const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const pad = (n) => String(n).padStart(2, '0');
const hhmm = (d) => new Date(d).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
const tilt = (ts) => `${((new Date(ts).getMinutes() * 7) % 5) - 2.5}deg`;
const fmtDur = (ms) => {
  const min = Math.floor(Math.abs(ms) / 60000);
  return `${Math.floor(min / 60)}h${pad(min % 60)}`;
};
const fmtSigned = (ms) => { const m = Math.round(ms / 60000); return (m > 0 ? '+' : m < 0 ? '−' : '') + fmtDur(ms); };

// ---------- Hora do servidor ----------
// A batida usa a hora do servidor; o visor também, para o funcionário ver a mesma hora que vai registrar
let clockOffset = 0;
const serverNow = () => new Date(Date.now() + clockOffset);
function syncClock(res) {
  const date = res?.headers.get('Date');
  if (date) clockOffset = Date.parse(date) + 500 - Date.now(); // o cabeçalho tem resolução de 1 s
}

// Sessão expirada ou encerrada: volta para o login
const toLogin = () => location.replace('/login?next=/');

// ---------- Acesso: relógio liberado e/ou admin logado ----------

let me = { admin: false, kiosk: false };

async function loadMe() {
  const res = await fetch('/api/auth/me').catch(() => null);
  if (res?.status === 401) return toLogin();
  if (!res?.ok) return;
  me = await res.json();
  $('company').textContent = me.company || '';
  document.querySelectorAll('[data-admin]').forEach((el) => { el.hidden = !me.admin; });
  $('kiosk').textContent = me.kiosk ? 'Desligar relógio' : 'Usar como relógio';
}
loadMe();

// Janela de confirmação (ou só de aviso, sem `cancel`); resolve true se o usuário confirmou
function ask({ title, message, ok = 'Confirmar', cancel = 'Cancelar' }) {
  const dlg = $('askDialog');
  $('askTitle').textContent = title;
  $('askMessage').textContent = message;
  $('askOk').textContent = ok;
  $('askCancel').textContent = cancel || '';
  $('askCancel').hidden = !cancel;
  dlg.returnValue = '';
  dlg.showModal();
  $(cancel ? 'askCancel' : 'askOk').focus(); // Enter sem querer não confirma
  return new Promise((resolve) => {
    dlg.addEventListener('close', () => resolve(dlg.returnValue === 'ok'), { once: true });
  });
}

$('kiosk').addEventListener('click', async () => {
  const confirmed = me.kiosk
    ? await ask({
      title: 'Desligar o modo relógio?',
      message: 'Para voltar a bater ponto neste aparelho será preciso entrar de novo.',
      ok: 'Desligar',
    })
    : await ask({
      title: 'Usar como relógio de ponto?',
      message: `Os funcionários${me.company ? ` da empresa ${me.company}` : ''} poderão bater o ponto neste aparelho, e a sua conta de administrador será desconectada dele.`,
      ok: 'Usar como relógio',
    });
  if (!confirmed) return;
  const res = await fetch('/api/auth/kiosk', { method: me.kiosk ? 'DELETE' : 'POST' }).catch(() => null);
  if (res?.status === 401) return toLogin();
  // Superadmin sem empresa aberta: escolhe uma no painel antes de liberar o relógio
  if (res?.status === 409) {
    const error = (await res.json().catch(() => ({}))).error || 'Escolha uma empresa no painel.';
    return ask({ title: 'Nenhuma empresa aberta', message: error, ok: 'Entendi', cancel: '' });
  }
  loadMe();
});

// Sai da conta do admin; num aparelho liberado como relógio, o relógio continua
$('logout').addEventListener('click', async () => {
  await fetch('/api/auth/logout', { method: 'POST' }).catch(() => {});
  location.replace('/');
});

let pin = '';
let slipTimer;
// Batidas de hoje de quem acabou de bater o ponto; somem sozinhas (os colegas não veem)
let card = null;
let cardTimer;
const CARD_SECONDS = 15;

// ---------- Visor ----------

function tick() {
  const now = serverNow();
  $('hm').textContent = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
  $('sec').textContent = pad(now.getSeconds());
  $('date').textContent = now.toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' });
  $('cardDate').textContent = now.toLocaleDateString('pt-BR');
  if (card && now.getSeconds() % 15 === 0) renderToday();
}
tick();
setInterval(tick, 1000);

// ---------- PIN ----------

function renderPin() {
  const slots = Math.max(4, pin.length);
  $('pin').innerHTML = Array.from({ length: slots }, (_, i) => `<i class="${i < pin.length ? 'on' : ''}"></i>`).join('');
  $('pin').setAttribute('aria-label', pin.length ? `${pin.length} dígitos digitados` : 'Nenhum dígito digitado');
}
renderPin();

function slip(html, cls = '', seconds = 6) {
  const el = $('slip');
  el.innerHTML = html;
  el.className = 'slip ' + cls;
  clearTimeout(slipTimer);
  slipTimer = setTimeout(() => {
    el.textContent = 'Digite seu PIN e toque em Bater ponto.';
    el.className = 'slip';
  }, seconds * 1000);
}

function takePin() {
  if (!pin) return null; // Enter repetido logo após bater o ponto
  if (pin.length < 4) { slip('O PIN tem de 4 a 8 dígitos.', 'error'); return null; }
  const typed = pin;
  pin = '';
  renderPin();
  return typed;
}

async function submit() {
  const typed = takePin();
  if (!typed) return;
  const ts = serverNow();
  let res;
  try {
    res = await fetch('/api/punch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pin: typed }) });
  } catch { res = null; }
  // Sem conexão (ou servidor fora do ar): guarda a batida neste aparelho e envia depois
  if (!res || res.status >= 502) return queuePunch(typed, ts);
  syncClock(res);
  if (res.status === 401) return toLogin();
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = res.status === 404 ? 'PIN não reconhecido. Confira os números e tente de novo.' : data.error || 'Não foi possível registrar.';
    return slip(esc(msg), 'error');
  }
  const cls = data.type === 'entrada' ? 'in' : 'out';
  const label = data.type === 'entrada' ? 'Entrada' : 'Saída';
  const shortPin = data.pin_short
    ? '<br><small class="pin-warn">Seu PIN é curto. Peça ao administrador um novo PIN de 6 dígitos.</small>'
    : '';
  slip(`<span class="stamp ${cls}">${hhmm(data.ts)}</span>
    <span><b>${label}</b> registrada, ${esc(data.name)}.<br><small class="receipt">Comprovante nº ${data.id} · código ${esc(data.receipt)}</small>${shortPin}</span>`, cls, data.pin_short ? 15 : 12);
  showCard(data);
}

function press(k) {
  if (k === 'ok') return submit();
  if (k === 'mirror') return openMirror();
  if (k === 'back') pin = pin.slice(0, -1);
  else if (k === 'clear') pin = '';
  else if (pin.length < 8) pin += k;
  renderPin();
}

$('keypad').addEventListener('click', (e) => {
  const k = e.target.closest('[data-k]')?.dataset.k;
  if (k) press(k);
});

document.addEventListener('keydown', (e) => {
  if ($('mirror').open || $('askDialog').open) return;
  const map = { Enter: 'ok', Backspace: 'back', Escape: 'clear' };
  const k = /^\d$/.test(e.key) ? e.key : map[e.key];
  if (!k) return;
  e.preventDefault();
  press(k);
  const btn = document.querySelector(`[data-k="${k === 'clear' ? 'back' : k}"]`);
  if (btn) {
    btn.classList.add('pressed');
    setTimeout(() => btn.classList.remove('pressed'), 90);
  }
});

// ---------- Batidas sem conexão ----------
// Ficam neste aparelho até a conexão voltar. O servidor marca como "offline" para o admin conferir.

const QUEUE_KEY = 'ponto-batidas-pendentes';
const readQueue = () => { try { return JSON.parse(localStorage.getItem(QUEUE_KEY)) || []; } catch { return []; } };
const writeQueue = (q) => { try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); } catch { /* sem armazenamento */ } };

function renderQueue() {
  const n = readQueue().length;
  $('queue').hidden = !n;
  $('queue').textContent = n === 1 ? '1 batida aguardando conexão' : `${n} batidas aguardando conexão`;
}

function queuePunch(typed, ts) {
  const queue = readQueue();
  queue.push({ pin: typed, ts: ts.toISOString() });
  writeQueue(queue);
  renderQueue();
  slip(`<span class="stamp">${hhmm(ts)}</span><span><b>Sem conexão.</b> Sua batida foi guardada neste aparelho e será enviada assim que a conexão voltar.</span>`, 'offline', 12);
}

let flushing = false;
async function flushQueue() {
  if (flushing) return;
  flushing = true;
  try {
    let queue = readQueue();
    while (queue.length) {
      const item = queue[0];
      let res;
      try {
        res = await fetch('/api/punch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pin: item.pin, offline_ts: item.ts }),
        });
      } catch { break; }
      if (res.status >= 500 || res.status === 401 || res.status === 429) break; // tenta de novo depois
      queue = readQueue().slice(1); // enviada (ou recusada pelo servidor, ex.: duplicada)
      writeQueue(queue);
    }
  } finally {
    flushing = false;
    renderQueue();
  }
}
renderQueue();
setInterval(flushQueue, 30000);
window.addEventListener('online', flushQueue);
if (readQueue().length) flushQueue();

// ---------- Cartão de hoje (só de quem bateu) ----------

function workedSoFar(punches) {
  let ms = 0;
  let open = null;
  for (const p of punches) {
    if (p.type === 'entrada') open = new Date(p.ts);
    else if (open) { ms += new Date(p.ts) - open; open = null; }
  }
  return { ms: ms + (open ? serverNow() - open : 0), working: Boolean(open) };
}

function showCard(data) {
  card = { ...data, fresh: true };
  renderToday();
  clearTimeout(cardTimer);
  cardTimer = setTimeout(() => { card = null; renderToday(); }, CARD_SECONDS * 1000);
}

function renderToday() {
  if (!card) {
    $('todayHead').innerHTML = '';
    $('todayBody').innerHTML = '<tr><td class="empty">Digite seu PIN e bata o ponto. Suas batidas de hoje aparecem aqui por alguns segundos, só para você.</td></tr>';
    return;
  }
  // Uma lista de batidas com E/S em cada uma (e não colunas Entrada/Saída fixas):
  // uma batida enviada depois, sem conexão, pode quebrar a alternância
  $('todayHead').innerHTML = '<tr><th>Nome</th><th>Batidas</th><th class="hours">Horas</th></tr>';
  const today = serverNow().toDateString();
  const stamps = card.today.map((p) => {
    const fresh = card.fresh && new Date(p.ts).getTime() === new Date(card.ts).getTime() ? ' fresh' : '';
    // Turno noturno: a entrada pode ter sido ontem
    const prev = new Date(p.ts).toDateString() !== today ? '<small class="prev">ontem</small>' : '';
    const label = p.type === 'entrada' ? 'Entrada' : 'Saída';
    return `<span class="stamp ${p.type === 'entrada' ? 'in' : 'out'}${fresh}" style="--tilt:${tilt(p.ts)}" title="${label}">${prev}<small class="kind">${label[0]}</small>${hhmm(p.ts)}</span>`;
  }).join('');
  const { ms, working } = workedSoFar(card.today);
  card.fresh = false; // a animação da batida nova só na primeira vez
  $('todayBody').innerHTML = `<tr><td class="who">${esc(card.name)}</td><td class="wrap"><div class="stamps">${stamps}</div></td><td class="hours">${fmtDur(ms)}${working ? ' <span class="live">em curso</span>' : ''}</td></tr>`;
}
renderToday();

// Mantém a hora do servidor em dia e percebe se o aparelho deixou de ser relógio
async function ping() {
  try {
    const res = await fetch('/api/auth/me');
    syncClock(res);
    if (res.status === 401) toLogin();
  } catch { /* tenta de novo no próximo ciclo */ }
}
ping();
setInterval(ping, 60000);

// ---------- Meu espelho ----------
// O PIN fica só na memória enquanto a janela estiver aberta

let mirrorPin = null;
let mirrorMonth = null;
let mirrorTimer;

const monthKey = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}`;
const shiftMonth = (key, delta) => { const [y, m] = key.split('-').map(Number); return monthKey(new Date(y, m - 1 + delta, 1)); };
const monthLabel = (key) => { const [y, m] = key.split('-').map(Number); return new Date(y, m - 1, 1).toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' }); };
const STATUS = { falta: 'falta', incompleto: 'incompleto', feriado: 'feriado', andamento: 'em andamento' };

function touchMirror() {
  clearTimeout(mirrorTimer);
  mirrorTimer = setTimeout(closeMirror, 60000);
}

function closeMirror() {
  clearTimeout(mirrorTimer);
  mirrorPin = null;
  $('mirrorBody').innerHTML = '';
  $('mirrorSummary').innerHTML = '';
  $('mirrorAck').innerHTML = '';
  if ($('mirror').open) $('mirror').close();
}

async function openMirror() {
  if (!pin) return slip('Digite seu PIN e toque em <b>Ver meu espelho</b>.', '');
  const typed = takePin();
  if (!typed) return;
  mirrorPin = typed;
  mirrorMonth = monthKey(serverNow());
  if (await loadMirror()) {
    $('mirror').showModal();
    touchMirror();
  }
}

async function api(path, body) {
  const res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).catch(() => null);
  if (!res) throw new Error('Sem conexão com o servidor.');
  if (res.status === 401) { toLogin(); throw new Error(''); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(res.status === 404 ? 'PIN não reconhecido. Confira os números e tente de novo.' : data.error || 'Erro');
  return data;
}

async function loadMirror() {
  let r;
  try {
    r = await api('/api/portal/report', { pin: mirrorPin, month: mirrorMonth });
  } catch (err) {
    closeMirror();
    slip(esc(err.message), 'error');
    return false;
  }
  $('mirrorTitle').textContent = r.employee.name;
  $('mirrorSub').textContent = monthLabel(mirrorMonth);
  $('mirrorNext').disabled = mirrorMonth >= monthKey(serverNow());
  $('mirrorSummary').innerHTML = `
    <div><span>Trabalhado</span><strong>${fmtDur(r.totalMs)}</strong></div>
    <div><span>Saldo do mês</span><strong>${fmtSigned(r.balanceMs)}</strong></div>
    <div><span>Banco de horas</span><strong>${fmtSigned(r.bankMs)}</strong></div>
    <div><span>Faltas</span><strong>${r.days.filter((d) => d.status === 'falta').length}</strong></div>`;

  const c = r.closure;
  $('mirrorAck').innerHTML = !c
    ? '<p class="form-hint">Este mês ainda não foi fechado pelo administrador.</p>'
    : c.acknowledged_at
      ? `<p class="form-ok">Você deu ciência deste espelho em ${new Date(c.acknowledged_at).toLocaleString('pt-BR')}.</p>`
      : '<div class="ack"><span>Mês fechado pelo administrador. Confira as batidas e confirme.</span><button class="key key-go" type="button" id="ackBtn">Dar ciência</button></div>';

  const days = r.days.filter((d) => d.punches.some((p) => !p.deleted_at) || ['falta', 'incompleto'].includes(d.status));
  $('mirrorBody').innerHTML = days.length
    ? days.slice().reverse().map((d) => {
        const dia = new Date(d.date + 'T12:00:00').toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit' });
        const tag = STATUS[d.status] ? ` <span class="tag">${STATUS[d.status]}</span>` : '';
        const stamps = d.punches.filter((p) => !p.deleted_at).map((p) =>
          `<span class="receipt-line"><span class="stamp ${p.type === 'entrada' ? 'in' : 'out'}">${hhmm(p.ts)}${p.manual ? '*' : ''}</span> <small>nº ${p.id} · ${esc(p.receipt)}</small></span>`).join('');
        return `<tr><td class="who">${dia}${tag}</td><td class="wrap">${stamps || '—'}</td>
          <td class="hours">${fmtDur(d.workedMs)}</td><td class="hours">${d.closed && (d.expectedMs || d.workedMs) ? fmtSigned(d.balanceMs) : ''}</td></tr>`;
      }).join('')
    : '<tr><td class="empty" colspan="4">Nenhuma batida neste mês.</td></tr>';
  return true;
}

$('mirror').addEventListener('click', async (e) => {
  touchMirror();
  if (e.target.id === 'ackBtn') {
    e.target.disabled = true;
    try { await api('/api/portal/ack', { pin: mirrorPin, month: mirrorMonth }); } catch (err) { slip(esc(err.message), 'error'); }
    loadMirror();
  }
});
$('mirrorPrev').addEventListener('click', () => { mirrorMonth = shiftMonth(mirrorMonth, -1); loadMirror(); });
$('mirrorNext').addEventListener('click', () => { mirrorMonth = shiftMonth(mirrorMonth, 1); loadMirror(); });
$('mirrorClose').addEventListener('click', closeMirror);
$('mirror').addEventListener('close', closeMirror);
