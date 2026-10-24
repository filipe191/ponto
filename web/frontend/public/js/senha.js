const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtDT = (iso) => new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });

async function api(path, body, method = body === undefined ? 'GET' : 'POST') {
  const res = await fetch('/api/auth' + path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).catch(() => null);
  if (!res) throw new Error('Sem conexão com o servidor. Tente de novo em instantes.');
  if (res.status === 401) { location.replace('/login?next=/senha'); throw new Error(''); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Não foi possível concluir.');
  return data;
}

$('logout').addEventListener('click', async () => {
  await fetch('/api/auth/logout', { method: 'POST' }).catch(() => {});
  location.replace('/');
});

// ---------- Pendências ----------

async function loadMe() {
  const me = await api('/admin').catch(() => null);
  if (!me) return;
  $('who').textContent = ` · ${me.user}`;
  $('username').value = me.user;
  const text = {
    senha: '<b>Troque sua senha para continuar.</b> A senha atual é provisória ou não segue a política (mínimo de 12 caracteres, nada muito comum).',
    '2fa': '<b>Ative a verificação em duas etapas para continuar.</b> Ela é obrigatória para todos os administradores.',
  }[me.pending];
  $('pending').hidden = !text;
  $('pending').innerHTML = text ? `${text}` : '';
  if (!me.pending && sessionStorage.getItem('ponto-pendencia')) {
    sessionStorage.removeItem('ponto-pendencia');
    $('pending').hidden = false;
    $('pending').className = 'notice ok';
    $('pending').innerHTML = 'Tudo certo. <a href="/admin">Ir para a administração</a>';
  } else if (me.pending) {
    sessionStorage.setItem('ponto-pendencia', '1');
  }
}

// ---------- Senha ----------

$('pwForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('pwError').textContent = '';
  $('pwOk').textContent = '';
  const current = $('current').value;
  const novo = $('new1').value;
  if (!current || !novo) return ($('pwError').textContent = 'Preencha a senha atual e a nova.');
  if (novo.length < 12) return ($('pwError').textContent = 'A nova senha deve ter pelo menos 12 caracteres.');
  if (novo !== $('new2').value) return ($('pwError').textContent = 'As duas novas senhas não conferem.');
  $('pwSubmit').disabled = true;
  try {
    await api('/password', { current_password: current, new_password: novo });
    $('pwForm').reset();
    $('pwOk').textContent = 'Senha alterada. Os outros aparelhos foram desconectados.';
    loadMe();
    loadSessions();
  } catch (err) { $('pwError').textContent = err.message; }
  $('pwSubmit').disabled = false;
});

// ---------- Verificação em duas etapas ----------

function showTf(part) {
  for (const id of ['tfOff', 'tfSetup', 'tfCodes', 'tfOn']) $(id).hidden = id !== part;
  $('tfError').textContent = '';
}

async function loadTf() {
  const s = await api('/2fa').catch((err) => { $('tfError').textContent = err.message; return null; });
  if (!s) return;
  if (s.enabled) {
    $('tfLeft').textContent = `${s.recovery_codes_left} código(s) de recuperação disponíveis.`;
    showTf('tfOn');
  } else {
    showTf('tfOff');
  }
}

$('tfStart').addEventListener('click', async () => {
  try {
    const s = await api('/2fa/setup', {});
    $('tfQr').src = s.qr;
    $('tfSecret').textContent = s.secret.replace(/(.{4})/g, '$1 ').trim();
    $('tfCode').value = '';
    showTf('tfSetup');
    $('tfCode').focus();
  } catch (err) { $('tfError').textContent = err.message; }
});

function showCodes(codes) {
  $('tfCodeList').innerHTML = codes.map((c) => `<li><code>${esc(c)}</code></li>`).join('');
  $('tfCodeList').dataset.text = codes.join('\n');
  showTf('tfCodes');
}

$('tfConfirm').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    const r = await api('/2fa/enable', { code: $('tfCode').value });
    showCodes(r.codes);
    loadMe();
  } catch (err) { $('tfError').textContent = err.message; }
});

$('tfCopy').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText($('tfCodeList').dataset.text);
    $('tfCopy').textContent = 'Copiados';
  } catch { $('tfCopy').textContent = 'Selecione e copie'; }
});
$('tfDone').addEventListener('click', () => { $('tfCodeList').innerHTML = ''; loadTf(); });

$('tfRecovery').addEventListener('click', async () => {
  $('tfPassWrap').hidden = true;
  try { showCodes((await api('/2fa/recovery', { code: $('tfManageCode').value })).codes); } catch (err) { $('tfError').textContent = err.message; }
  $('tfManageCode').value = '';
});

$('tfDisable').addEventListener('click', async () => {
  if ($('tfPassWrap').hidden) {
    $('tfPassWrap').hidden = false;
    $('tfError').textContent = 'Digite o código do app e a sua senha e toque em Desativar de novo.';
    return;
  }
  try {
    await api('/2fa/disable', { password: $('tfPass').value, code: $('tfManageCode').value });
    $('tfPass').value = '';
    $('tfManageCode').value = '';
    $('tfPassWrap').hidden = true;
    loadTf();
    loadMe();
  } catch (err) { $('tfError').textContent = err.message; }
});

// ---------- Sessões ----------

function device(ua) {
  if (!ua) return 'Aparelho desconhecido';
  const os = /iPhone|iPad/.test(ua) ? 'iPhone/iPad' : /Android/.test(ua) ? 'Android' : /Mac OS/.test(ua) ? 'Mac' : /Windows/.test(ua) ? 'Windows' : /Linux/.test(ua) ? 'Linux' : '';
  const browser = /Edg\//.test(ua) ? 'Edge' : /Firefox\//.test(ua) ? 'Firefox' : /Chrome\//.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari' : 'Navegador';
  return os ? `${browser} no ${os}` : browser;
}

async function loadSessions() {
  let items = [];
  try { items = await api('/sessions'); } catch (err) { $('sesError').textContent = err.message; }
  $('sessions').innerHTML = items.map((s) => `
    <li>
      <span><b>${esc(device(s.user_agent))}</b>${s.current ? ' <span class="tag-current">este aparelho</span>' : ''}<br>
        <small>${esc(s.ip || '')} · entrou ${fmtDT(s.created_at)} · último uso ${fmtDT(s.last_seen_at)}</small></span>
      ${s.current ? '' : `<button class="key" type="button" data-end="${s.id}">Encerrar</button>`}
    </li>`).join('');
  $('endOthers').hidden = items.length < 2;
}

$('sessions').addEventListener('click', async (e) => {
  const id = e.target.closest('[data-end]')?.dataset.end;
  if (!id) return;
  try { await api(`/sessions/${id}`, undefined, 'DELETE'); } catch (err) { $('sesError').textContent = err.message; }
  loadSessions();
});
$('endOthers').addEventListener('click', async () => {
  try { await api('/sessions/end-others', {}); } catch (err) { $('sesError').textContent = err.message; }
  loadSessions();
});

loadMe();
loadTf();
loadSessions();
