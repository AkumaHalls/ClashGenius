// ==== PAINEL DE USUÁRIOS REFORMULADO ====
// Tabela limpa com CSS classes, dropdown agrupado, botão forçar troca separado
// Reset de senha real: aprovação gera código one-time que o usuário usa sem senha antiga

let umUsersCache = [];
let umQuery = '';
let umFilter = 'all';
let umBound = false;

const UM_ACTIONS = {
    ativado: {
        title: 'Reativar conta',
        body: 'A conta volta a ter acesso ao painel. O cargo atual e qualquer pedido de reset pendente são encerrados.',
        danger: false,
    },
    desativado: {
        title: 'Desativar conta',
        body: 'A conta perde o acesso ao painel e passa a ser encaminhada para a página que orienta abrir um ticket no Discord. O cargo atual é preservado e dá para reativar depois.',
        danger: true,
    },
    banido: {
        title: 'Banir conta',
        body: 'A conta perde o acesso ao painel e passa a ver a página de banimento. Dá para reverter a qualquer momento pela opção Ativar.',
        danger: true,
    },
    admin: {
        title: 'Tornar Admin',
        body: 'A conta passa a ter permissão de administração no painel. Se estava desativada ou banida, também é reativada.',
        danger: false,
    },
    viewer: {
        title: 'Tornar Membro Sênior',
        body: 'A conta passa a ter somente leitura no painel: não altera usuários nem configurações. Se estava desativada ou banida, também é reativada.',
        danger: false,
    },
    trocar_senha: {
        title: 'Forçar troca de senha',
        body: 'No próximo login, em vez de entrar no painel, o usuário verá uma página para definir uma nova senha. Cargo e status não mudam.',
        danger: false,
    },
    aprovar_reset_senha: {
        title: 'Aprovar reset de senha',
        body: 'O usuário pediu recuperação por ter esquecido a senha atual. Ao aprovar, será gerado um código de uso único. Copie e envie ao usuário (ex.: Discord) — ele usará em "Redefinir com código" na tela de login, sem precisar da senha antiga.',
        danger: false,
    },
    negar_reset_senha: {
        title: 'Negar reset de senha',
        body: 'O usuário continua usando a senha atual. Use se o pedido não for legítimo.',
        danger: true,
    },
};

function confirmAction({ title, body, confirmText, danger }) {
    return new Promise((resolve) => {
        const prev = document.getElementById('um-modal');
        if (prev) prev.remove();
        const wrap = document.createElement('div');
        wrap.id = 'um-modal';
        wrap.className = 'um-modal-backdrop';
        wrap.innerHTML = `
            <div class="um-modal" role="dialog" aria-modal="true" aria-label="${escapeHtml(title)}">
                <h4 class="um-modal-title">${escapeHtml(title)}</h4>
                <p class="um-modal-body">${escapeHtml(body)}</p>
                <div class="um-modal-actions">
                    <button type="button" class="um-btn" data-res="0">Cancelar</button>
                    <button type="button" class="um-btn ${danger ? 'um-btn-danger' : 'um-btn-primary'}" data-res="1">${escapeHtml(confirmText || 'Confirmar')}</button>
                </div>
            </div>`;
        document.body.appendChild(wrap);
        const onKey = (e) => { if (e.key === 'Escape') done(false); };
        const done = (v) => {
            wrap.remove();
            document.removeEventListener('keydown', onKey);
            resolve(v);
        };
        document.addEventListener('keydown', onKey);
        wrap.addEventListener('click', (e) => {
            const b = e.target.closest('[data-res]');
            if (b) { done(b.dataset.res === '1'); return; }
            if (e.target === wrap) done(false);
        });
        const cancel = wrap.querySelector('[data-res="0"]');
        if (cancel) cancel.focus();
    });
}

function showCodeModal(code, username) {
    return new Promise((resolve) => {
        const prev = document.getElementById('um-modal');
        if (prev) prev.remove();
        const wrap = document.createElement('div');
        wrap.id = 'um-modal';
        wrap.className = 'um-modal-backdrop';
        wrap.innerHTML = `
            <div class="um-modal" role="dialog" aria-modal="true" aria-label="Código de reset para ${escapeHtml(username)}" style="max-width:520px;">
                <h4 class="um-modal-title" style="display:flex;align-items:center;gap:8px;">
                    <span style="color:var(--neon-cyan);">✓</span> Reset aprovado — código gerado
                </h4>
                <p class="um-modal-body" style="margin-bottom:12px;">
                    Envie este código para <strong>${escapeHtml(username)}</strong> (ex.: via Discord).
                    Ele usará na tela de login → <em>Redefinir com código</em>.
                </p>
                <div style="background:rgba(0,0,0,0.4);border:1px solid var(--neon-cyan);border-radius:6px;padding:16px;text-align:center;margin-bottom:16px;">
                    <code id="um-code-display" style="font-size:1.3em;letter-spacing:0.3em;color:var(--neon-cyan);font-family:'Fira Code',monospace;">${escapeHtml(code)}</code>
                    <button type="button" id="um-copy-code" class="um-btn um-btn-primary" style="margin-top:10px;">Copiar código</button>
                </div>
                <p class="um-modal-body" style="font-size:0.8em;color:var(--color-text-secondary);margin:0;">
                    O código expira em <strong>60 minutos</strong> e só funciona uma vez.
                </p>
                <div class="um-modal-actions">
                    <button type="button" class="um-btn um-btn-primary" data-res="1">Entendi, fechar</button>
                </div>
            </div>`;
        document.body.appendChild(wrap);
        const onKey = (e) => { if (e.key === 'Escape') done(false); };
        const done = (v) => {
            wrap.remove();
            document.removeEventListener('keydown', onKey);
            resolve(v);
        };
        document.addEventListener('keydown', onKey);
        wrap.addEventListener('click', (e) => {
            if (e.target.id === 'um-copy-code') {
                navigator.clipboard.writeText(code).then(() => {
                    const btn = e.target;
                    const old = btn.textContent;
                    btn.textContent = 'Copiado!';
                    setTimeout(() => btn.textContent = old, 1500);
                });
                return;
            }
            const b = e.target.closest('[data-res]');
            if (b) { done(b.dataset.res === '1'); return; }
            if (e.target === wrap) done(false);
        });
        const btn = wrap.querySelector('[data-res="1"]');
        if (btn) btn.focus();
    });
}

function umBadge(kind, label) {
    return `<span class="um-badge" data-kind="${kind}">${escapeHtml(label)}</span>`;
}

function umStatusInfo(status) {
    if (status === 'active') return { kind: 'active', label: 'Ativo' };
    if (status === 'disabled') return { kind: 'disabled', label: 'Desativado' };
    if (status === 'banned') return { kind: 'banned', label: 'Banido' };
    return { kind: 'active', label: 'Ativo' };
}

function renderUsersList() {
    const list = document.getElementById('um-tbody');
    const chips = document.querySelectorAll('[data-um-filter]');
    if (!list) return;

    const countFor = (f) => {
        if (f === 'all') return umUsersCache.length;
        if (f === 'reset') return umUsersCache.filter(u => u.password_reset_pending).length;
        return umUsersCache.filter(u => u.status === f).length;
    };
    chips.forEach(c => {
        const n = c.querySelector('.um-chip-n');
        if (n) n.textContent = countFor(c.dataset.umFilter);
        c.classList.toggle('is-active', c.dataset.umFilter === umFilter);
    });

    const needle = umQuery;
    const shown = umUsersCache.filter(u => {
        if (umFilter === 'reset' && !u.password_reset_pending) return false;
        if (umFilter !== 'all' && umFilter !== 'reset' && u.status !== umFilter) return false;
        if (!needle) return true;
        return ((u.username || '') + ' ' + (u.discord || '')).toLowerCase().includes(needle);
    });

    if (shown.length === 0) {
        list.innerHTML = `<tr><td colspan="4" class="um-empty">Nenhum usuário corresponde ao filtro.</td></tr>`;
        return;
    }

    list.innerHTML = shown.map(u => {
        const isSelf = u.username === currentUsername;
        const readonly = isSelf || currentUserRole === 'viewer';
        const st = umStatusInfo(u.status);

        const badges = [
            umBadge(u.role === 'admin' ? 'admin' : 'viewer', u.role === 'admin' ? 'Admin' : 'Membro Sênior'),
            umBadge(st.kind, st.label),
        ];
        if (u.password_reset_pending) badges.push(umBadge('reset', 'Reset solicitado'));
        if (u.must_change_password) badges.push(umBadge('pw', 'Troca pendente'));

        const g = (act, text, on, tone, disabled) =>
            `<button type="button" class="um-btn-g${on ? ' is-on' : ''}" data-um-act="${act}"` +
            `${tone ? ` data-tone="${tone}"` : ''}${disabled ? ' disabled' : ''}>${text}</button>`;
        const seg = (label, buttons) =>
            `<div class="um-seg" role="group" aria-label="${label}">${buttons}</div>`;

        const actions = readonly
            ? `<span class="um-note">${isSelf ? 'Sua conta — altere com outro admin.' : 'Somente leitura'}</span>`
            : [
                seg('Cargo',
                    g('admin', 'Admin', u.role === 'admin', 'primary') +
                    g('viewer', 'Membro Sênior', u.role === 'viewer', 'warn')),
                seg('Acesso',
                    g('ativado', 'Ativar', u.status === 'active', 'primary') +
                    g('desativado', 'Desativar', u.status === 'disabled', 'warn') +
                    g('banido', 'Banir', u.status === 'banned', 'danger')),
                seg('Senha',
                    (u.password_reset_pending
                        ? g('aprovar_reset_senha', 'Aprovar reset', false, 'primary') +
                          g('negar_reset_senha', 'Negar reset', false, 'danger')
                        : '') +
                    g('trocar_senha', u.must_change_password ? 'Troca já liberada' : 'Forçar troca', false, 'primary', u.must_change_password)),
              ].join('');

        const statusCell = `
            <span class="um-status-cell">
                ${umBadge(st.kind, st.label)}
                ${u.password_reset_pending ? umBadge('reset', 'Reset solicitado') : ''}
                ${u.must_change_password ? umBadge('pw', 'Troca pendente') : ''}
            </span>`;

        return `
        <tr class="um-row" data-username="${escapeHtml(u.username)}" data-status="${escapeHtml(u.status)}" style="${u.status !== 'active' ? 'opacity:0.7;' : ''}">
            <td class="um-col-user">
                <span class="um-avatar" data-role="${u.role === 'admin' ? 'admin' : 'viewer'}">${escapeHtml((u.username||'?').slice(0,2).toUpperCase())}</span>
                <div>
                    <div class="um-name">${escapeHtml(u.username)}${isSelf ? '<span class="um-you">você</span>' : ''}</div>
                    <div class="um-meta">${u.discord ? escapeHtml(u.discord) : 'sem Discord'} · ${u.created_at ? new Date(u.created_at).toLocaleString('pt-BR') : '—'}</div>
                </div>
            </td>
            <td class="um-col-role">${badges[0]}</td>
            <td class="um-col-status">${statusCell}</td>
            <td class="um-col-actions">${actions}</td>
        </tr>`;
    }).join('');
}

async function loadActiveUsers() {
    const container = document.getElementById('active-users-list');
    if (!container) return;

    try {
        const data = await fetchAdminAPI('auth/users');
        if (!data || data.length === 0) {
            container.innerHTML = '<p style="color:var(--color-text-secondary);font-style:italic;">Nenhum usuário cadastrado.</p>';
            return;
        }

        const users = data.filter(u => u.status !== 'pending');
        if (users.length === 0) {
            container.innerHTML = '<p style="color:var(--color-text-secondary);font-style:italic;">Nenhum usuário aprovado.</p>';
            return;
        }

        umUsersCache = users;
        const counts = {
            active: users.filter(u => u.status === 'active').length,
            disabled: users.filter(u => u.status === 'disabled').length,
            banned: users.filter(u => u.status === 'banned').length,
        };

        container.innerHTML = `
            <div class="um-panel">
                <div class="um-toolbar">
                    <input type="search" id="um-search" class="um-search" placeholder="Buscar por nome ou Discord..." autocomplete="off" value="${escapeHtml(umQuery)}">
                    <div class="um-chips">
                        <button type="button" class="um-chip" data-um-filter="all">Todos <span class="um-chip-n">0</span></button>
                        <button type="button" class="um-chip" data-um-filter="active">Ativos <span class="um-chip-n">0</span></button>
                        <button type="button" class="um-chip" data-um-filter="disabled">Desativados <span class="um-chip-n">0</span></button>
                        <button type="button" class="um-chip" data-um-filter="banned">Banidos <span class="um-chip-n">0</span></button>
                        <button type="button" class="um-chip" data-um-filter="reset">Reset pedido <span class="um-chip-n">0</span></button>
                    </div>
                </div>
                <div class="um-table-wrap">
                    <table class="um-table">
                        <thead>
                            <tr>
                                <th>Usuário</th>
                                <th>Cargo</th>
                                <th>Status</th>
                                <th style="width:1%;white-space:nowrap;">Ações</th>
                            </tr>
                        </thead>
                        <tbody id="um-tbody"></tbody>
                    </table>
                </div>
                <p class="um-foot">
                    Total: ${users.length} · ${counts.active} ativo(s) · ${counts.disabled} desativado(s) · ${counts.banned} banido(s)
                </p>
                <p class="um-hint">
                    <strong>Cargo</strong> define permissão (Admin edita tudo, Membro Sênior é somente leitura).
                    <strong>Acesso</strong> bloqueia ou restaura o login: desativado leva a aviso para abrir ticket, banido leva à página de banimento.
                    <strong>Senha</strong> é independente: "Forçar troca" manda o usuário definir nova senha no próximo login.
                    <strong>Reset solicitado</strong>: o usuário pediu recuperação (esqueceu a senha). Ao <strong>Aprovar</strong>, será gerado um código de uso único — copie e envie ao usuário; ele usará em "Redefinir com código" na tela de login, sem precisar da senha antiga.
                    Não existe redefinição automática por e-mail.
                </p>
            </div>`;

        if (!umBound) {
            umBound = true;
            container.addEventListener('input', (e) => {
                if (e.target && e.target.id === 'um-search') {
                    umQuery = e.target.value.trim().toLowerCase();
                    renderUsersList();
                }
            });
            container.addEventListener('click', (e) => {
                const chip = e.target.closest('[data-um-filter]');
                if (chip) { umFilter = chip.dataset.umFilter; renderUsersList(); return; }
                const btn = e.target.closest('[data-um-act]');
                if (btn && !btn.disabled) {
                    const row = btn.closest('.um-row');
                    if (row) window.changeUserAction(row.dataset.username, btn.dataset.umAct);
                }
            });
        }
        renderUsersList();
    } catch(e) {
        container.innerHTML = `<p class="error-text">Erro ao carregar: ${escapeHtml(e.message)}</p>`;
    }
}

window.changeUserAction = async function(username, newAction) {
    const fb = document.getElementById('users-feedback');
    if (!fb) return;

    const spec = UM_ACTIONS[newAction];
    if (!spec) { await loadActiveUsers(); return; }

    const ok = await confirmAction({
        title: `${spec.title}: ${username}`,
        body: spec.body,
        confirmText: spec.danger ? 'Sim, confirmar' : 'Confirmar',
        danger: spec.danger,
    });
    if (!ok) return;

    fb.textContent = 'Aplicando...';
    fb.className = 'feedback-text';

    try {
        const data = await fetchAdminAPI('auth/role', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, role: newAction})
        });

        if (newAction === 'aprovar_reset_senha' && data.reset_code) {
            await showCodeModal(data.reset_code, username);
        }

        fb.textContent = data.message || 'OK';
        fb.className = 'feedback-text success';
        await loadActiveUsers();
    } catch(e) {
        fb.textContent = 'Erro: ' + e.message;
        fb.className = 'feedback-text error';
        await loadActiveUsers();
    }
};

window.changeUserRole = window.changeUserAction;