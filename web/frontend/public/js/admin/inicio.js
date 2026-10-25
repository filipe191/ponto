// Aba Início: solicitações do app e avisos de segurança.
import { $, api, ask, esc, fmtDT, kindLabel, toast } from './comum.js';
import { loadReport } from './espelho.js';

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

export async function loadRequests() {
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
    toast(approve ? 'Solicitação aprovada' : 'Solicitação recusada');
  } catch (err) { $('reqError').textContent = err.message; }
  loadRequests();
  loadReport();
});

// ---------- Avisos e auditoria ----------

export async function loadAlerts() {
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
  if (a.holidays_missing_year) {
    items.push(`<li><b>Ainda não há feriados da empresa para ${a.holidays_missing_year}.</b>
      Cadastre os municipais e estaduais (ou marque “Repete todo ano”) em Configurações → Feriados, senão esses dias viram falta.</li>`);
  }
  $('alertsList').innerHTML = items.join('');
  $('alertsCard').hidden = !items.length;
}
