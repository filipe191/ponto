const $ = (id) => document.getElementById(id);

// Nome da empresa e contato vêm do .env (EMPRESA_NOME e PRIVACIDADE_CONTATO); sem eles, fica o texto genérico
fetch('/api/privacidade')
  .then((res) => (res.ok ? res.json() : null))
  .then((info) => {
    if (!info) return;
    if (info.empresa) $('empresa').textContent = info.empresa;
    if (info.contato) $('contato').textContent = info.contato;
    $('anos').textContent = info.retention_years === 1 ? '1 ano' : `${info.retention_years} anos`;
  })
  .catch(() => {});
