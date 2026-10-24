const $ = (id) => document.getElementById(id);

function tick() {
  const now = new Date();
  $('hm').textContent = now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}
tick();
setInterval(tick, 1000);

// Só aceita voltar para um caminho do próprio site
const next = new URLSearchParams(location.search).get('next');
const target = next && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/login') ? next : '/';

$('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = $('username').value.trim();
  const password = $('password').value;
  if (!username || !password) {
    $('error').textContent = 'Preencha usuário e senha.';
    return;
  }
  $('error').textContent = '';
  $('submit').disabled = true;
  $('submit').textContent = 'Entrando…';
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, code: $('code').value }),
    });
    const data = await res.json().catch(() => ({}));
    // Senha provisória ou sem verificação em duas etapas: resolve isso antes do painel
    if (res.ok) return location.replace(data.pending ? '/senha' : target);
    if (data.otp_required) {
      // Senha certa e conta com duas etapas: pede o código, mantendo usuário e senha
      const asked = !$('codeField').hidden;
      $('codeField').hidden = false;
      $('error').textContent = asked ? data.error : '';
      $('code').value = '';
      $('code').focus();
    } else {
      $('error').textContent = res.status === 401
        ? 'Usuário ou senha incorretos.'
        : data.error || 'Não foi possível entrar. Tente de novo.';
      $('codeField').hidden = true;
      $('code').value = '';
      $('password').value = '';
      $('password').focus();
    }
  } catch {
    $('error').textContent = 'Sem conexão com o servidor. Tente de novo em instantes.';
  }
  $('submit').disabled = false;
  $('submit').textContent = 'Entrar';
});
