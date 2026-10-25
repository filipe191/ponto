const $ = (id) => document.getElementById(id);

// Nome e contato vêm do cadastro da empresa: pelo link da empresa (?e=<código>, para o celular do
// funcionário), pelo relógio ou pelo admin logado; sem nenhum deles, fica o texto genérico
const code = new URLSearchParams(location.search).get('e') || '';
fetch('/api/privacidade' + (code ? `?e=${encodeURIComponent(code)}` : ''))
  .then((res) => (res.ok ? res.json() : null))
  .then((info) => {
    if (!info) return;
    if (info.empresa) $('empresa').textContent = info.empresa;
    if (info.contato) $('contato').textContent = info.contato;
    $('anos').textContent = info.retention_years === 1 ? '1 ano' : `${info.retention_years} anos`;
  })
  .catch(() => {});
