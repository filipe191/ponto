// Abas do painel (a aberta fica no endereço) e tabelas que viram cartões no celular.
import { $ } from './comum.js';

// ---------- Abas ----------
// Cada cartão pertence a uma aba (data-tab). A aba aberta fica no endereço (/admin#espelho), para o
// voltar do navegador e os links funcionarem.

export const TABS = [...document.querySelectorAll('[role="tab"]')];
// Guardada antes da primeira showTab, que ainda não sabe quais abas o usuário vê (Empresas fica escondida)
export const initialTab = location.hash.slice(1);

export function showTab(name) {
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

// ---------- Tabelas em cartões no celular ----------
// Em tela estreita cada linha vira um cartão (CSS); cada célula leva o título da sua coluna.

function labelCells(table) {
  const heads = [...table.tHead.rows[0].cells].map((th) => th.textContent.trim());
  for (const row of table.tBodies[0].rows) {
    [...row.cells].forEach((td, i) => { if (heads[i] && td.colSpan === 1) td.dataset.label = heads[i]; });
  }
}
document.querySelectorAll('table.stack').forEach((table) => {
  new MutationObserver(() => labelCells(table)).observe(table.tBodies[0], { childList: true });
  labelCells(table);
});
