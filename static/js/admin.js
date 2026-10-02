// =========================================================
// PAINEL ADMINISTRATIVO — ClashGenius
// -------------------------------------------------------------
// Depende de utils.js (escapeHtml), carregado antes deste arquivo.
// Cobre todas as abas: Geral, Diagnostico, Configuracoes, Watchlist,
// Radar Pericial, Analytics IA, Acoes, Base de Dados, DiscoHook e Usuarios.
// =========================================================
(function () {
'use strict';

// =========================================================
// ESTADO GLOBAL
// =========================================================
let currentUsername = '';
let currentUserRole = 'admin';
let currentActiveSectionId = 'admin-geral';
let adminReady = false;

let dhEmbeds = [];
let dhEmbedIdCounter = 0;

let umUsersCache = [];
let umQuery = '';
let umFilter = 'all';
let umBound = false;

const DH_COLOR_PRESETS = [
    '#5865f2', '#57f287', '#faa61a', '#ed4245', '#eb459e',
    '#ff73fa', '#00b0f4', '#4e5058', '#95ef1a', '#fee75c',
    '#b9bbbe', '#1abc9c', '#3498db', '#9b59b6', '#e67e22'
];

// =========================================================
// UTILITARIOS
// =========================================================
function $(id) { return document.getElementById(id); }

function fmtDateTime(value) {
    if (!value) return '—';
    const d = new Date(value);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleString('pt-BR');
}

function fmtDate(value) {
    if (!value) return '—';
    const d = new Date(value);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleDateString('pt-BR');
}

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') || '' : '';
}

function displayFeedback(element, message, isError = false, duration = 4000) {
    if (!element) return;
    element.textContent = message;
    element.classList.remove('error', 'success');
    element.classList.add(isError ? 'error' : 'success');
    if (element._fbTimer) clearTimeout(element._fbTimer);
    if (duration > 0) {
        element._fbTimer = setTimeout(() => {
            element.textContent = '';
            element.classList.remove('error', 'success');
        }, duration);
    }
}

/** Elemento de feedback adequado para a aba visivel no momento. */
function feedbackForSection() {
    switch (currentActiveSectionId) {
        case 'admin-configuracoes': return $('settings-feedback');
        case 'admin-watchlist': return $('watchlist-list-feedback') || $('watchlist-add-feedback');
        case 'admin-geral': return $('geral-feedback');
        case 'admin-db': return $('db-feedback');
        case 'admin-radar': return $('radar-feedback');
        case 'admin-users': return $('users-feedback');
        case 'admin-acoes': return $('actions-feedback');
        default: return $('actions-feedback');
    }
}

/**
 * Camada fina sobre fetchAdminAPI (utils.js): injeta CSRF em mutacoes,
 * normaliza respostas sem corpo e mostra o erro na aba correspondente.
 */
async function api(endpoint, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const headers = Object.assign({}, options.headers || {});
    if (method !== 'GET' && method !== 'HEAD') {
        headers['X-CSRF-Token'] = getCsrfToken();
    }

    let response;
    try {
        response = await fetch('/api/admin/' + endpoint, Object.assign({}, options, {
            headers,
            credentials: 'include'
        }));
    } catch (err) {
        displayFeedback(feedbackForSection(), 'Erro de conexão: ' + err.message, true);
        throw err;
    }

    if (response.status === 204) return { status: 'success', message: 'Operação concluída.' };

    const data = await response.json().catch(() => null);

    if (!response.ok) {
        const message = (data && data.message) || ('Falha ao acessar ' + endpoint + ' (HTTP ' + response.status + ')');
        displayFeedback(feedbackForSection(), message, true);
        throw new Error(message);
    }
    return data;
}

// =========================================================
// RADAR DE INATIVIDADE ( gaveta do sino)
// =========================================================
window.toggleRadarDrawer = function () {
    const drawer = $('radar-drawer');
    if (drawer) drawer.classList.toggle('open');
};

window.updateRadarNotifications = function (members) {
    const drawerContent = $('radar-content');
    const badge = $('radar-badge');
    if (!drawerContent || !badge) return;

    drawerContent.innerHTML = '';
    let alertCount = 0;
    const now = new Date();

    (members || []).forEach(member => {
        const lastWarStr = member.last_war_date;
        if (!lastWarStr) return;

        const lastWar = new Date(lastWarStr);
        if (isNaN(lastWar.getTime())) return;

        const diffTime = now.getTime() - lastWar.getTime();
        const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
        if (diffDays < 15) return;

        alertCount++;
        let alertType, icon, message, colorClass;

        if (diffDays >= 30) {
            alertType = 'INFRAÇÃO GRAVE (30+ dias)';
            icon = '<img src="/assets/icons/Icon_HV_Attack_Star.png" class="icon-sm" alt="critical">';
            colorClass = 'alert-critical';
            message = `Atenção: o membro <strong>${escapeHtml(member.name)}</strong> violou a diretriz principal do clã. O sistema forense registra exatos <strong>${diffDays} dias</strong> sem qualquer participação no campo de guerra. Remoção recomendada.`;
        } else if (diffDays >= 22) {
            alertType = 'ALERTA VERMELHO (22+ dias)';
            icon = '<img src="/assets/icons/Icon_HV_Raid_Attack.png" class="icon-sm" alt="alert">';
            colorClass = 'alert-danger';
            message = `Risco altíssimo de desligamento: a conta de <strong>${escapeHtml(member.name)}</strong> está congelada há <strong>${diffDays} dias</strong>. Sugere-se intervenção imediata da liderança para cobrança.`;
        } else {
            alertType = 'ATENÇÃO TÁTICA (15+ dias)';
            icon = '<img src="/assets/icons/Icon_HV_Sword.png" class="icon-sm" alt="target">';
            colorClass = 'alert-warning';
            message = `A conta <strong>${escapeHtml(member.name)}</strong> acaba de entrar no radar de ociosidade. A nossa telemetria aponta <strong>${diffDays} dias</strong> sem se voluntariar para o confronto.`;
        }

        drawerContent.innerHTML += `
            <div class="radar-alert ${colorClass}">
                <div class="alert-icon">${icon}</div>
                <div class="alert-text"><strong>${alertType}</strong><span>${message}</span></div>
            </div>`;
    });

    if (alertCount === 0) {
        drawerContent.innerHTML = `
            <div class="radar-empty">
                <div style="font-size: 3rem; margin-bottom: 10px;"><img src="/assets/icons/Icon_HV_Shield.png" class="icon-sm" alt="clean"></div>
                <p>O radar está limpo.<br>Nenhum membro detectado em inatividade bunkica no momento!</p>
            </div>`;
        badge.style.display = 'none';
    } else {
        badge.textContent = alertCount;
        badge.style.display = 'flex';
    }
};

window.fetchRadarInactivityData = async function () {
    const drawerContent = $('radar-content');
    try {
        const response = await fetch('/api/members', { credentials: 'include' });
        if (response.ok) {
            const data = await response.json();
            if (data && data.members) {
                window.updateRadarNotifications(data.members);
            } else if (drawerContent) {
                drawerContent.innerHTML = '<div class="radar-empty"><p style="color:#f1c40f;">Nenhum membro encontrado na API.</p></div>';
            }
        } else if (drawerContent) {
            drawerContent.innerHTML = `<div class="radar-empty"><p style="color:#e74c3c;">Erro de conexão com o Banco de Dados (Código ${response.status}).</p></div>`;
        }
    } catch (e) {
        console.error('Falha de leitura térmica do radar:', e);
        if (drawerContent) drawerContent.innerHTML = '<div class="radar-empty"><p style="color:#e74c3c;">Falha crítica ao tentar buscar as datas de inatividade.</p></div>';
    }
};

// =========================================================
// TOOLTIPS
// =========================================================
function initTooltips() {
    document.querySelectorAll('[data-tooltip]').forEach(el => {
        if (el.querySelector('.cyber-tooltip')) return;
        const tip = document.createElement('span');
        tip.className = 'cyber-tooltip';
        tip.textContent = el.dataset.tooltip;
        el.appendChild(tip);
        el.style.position = 'relative';
        el.style.cursor = 'help';
    });
}

// =========================================================
// ABA: GERAL / DIAGNOSTICO
// =========================================================
function updateStatus(data) {
    const statusTextEl = $('maintenance-status-text');
    if (statusTextEl) {
        statusTextEl.textContent = data.maintenance_mode ? 'ATIVADO' : 'DESATIVADO';
        statusTextEl.className = 'status-badge ' + (data.maintenance_mode ? 'status-on' : 'status-off');
    }
    const botVersionEl = $('bot-version-text');
    if (botVersionEl) botVersionEl.textContent = data.version || '-';
}

function updateDiagnostics(data) {
    if (!data) return;
    const api_status = data.api_status;
    const recent_logs = data.recent_logs;

    const badge = $('api-status-badge');
    const message = $('api-status-message');
    const logs = $('recent-logs-box');

    if (badge && api_status) {
        badge.className = 'status-badge status-' + api_status.status;
        badge.textContent = api_status.status === 'ok' ? 'Operacional'
            : (api_status.status === 'maintenance' ? 'Manutenção' : 'Erro');
    }
    if (message && api_status) message.textContent = api_status.message || '';
    if (logs) {
        logs.textContent = Array.isArray(recent_logs) && recent_logs.length > 0
            ? recent_logs.join('\n')
            : 'Nenhum log recente.';
    }
}

// =========================================================
// ABA: CONFIGURACOES
// =========================================================
const CHANNEL_SELECT_IDS = [
    'channel_id', 'post_war_analysis_channel_id', 'post_war_verdict_channel_id',
    'clan_games_channel_id', 'cwl_planner_channel_id', 'donations_channel_id',
    'watchlist_alert_channel_id', 'low_performance_channel_id', 'capital_report_channel_id',
    'smurf_log_channel_id', 'maintenance_alert_channel_id', 'changelog_channel_id',
    'war_preference_channel_id'
];
const ROLE_SELECT_IDS = [
    'role_id_1star_alert', 'role_id_missed_attack', 'leader_role_id',
    'coleader_role_id', 'maintenance_role_id'
];

function fillSelect(select, options, placeholder) {
    if (!select) return;
    select.innerHTML = '<option value="0">' + placeholder + '</option>' +
        options.map(o => '<option value="' + escapeHtml(o.id) + '">' + escapeHtml(o.name) + '</option>').join('');
}

function populateDiscordDropdowns(discordData) {
    if (!discordData || discordData.error) return;
    CHANNEL_SELECT_IDS.forEach(id => {
        const select = $(id);
        if (select && Array.isArray(discordData.channels)) {
            fillSelect(select, discordData.channels, 'Nenhum / Desativado');
        }
    });
    ROLE_SELECT_IDS.forEach(id => {
        const select = $(id);
        if (select && Array.isArray(discordData.roles)) {
            fillSelect(select, discordData.roles, 'Nenhum / Desativado');
        }
    });
}

function populateSettingsForm(data) {
    if (!data || data.error) return;
    const settingsForm = $('settings-form');
    if (!settingsForm) return;

    Object.keys(data).forEach(key => {
        const input = $(key);
        if (!input) return;
        if (input.tagName === 'SELECT') {
            const valStr = String(data[key] || '0');
            let optionExists = false;
            for (let i = 0; i < input.options.length; i++) {
                if (input.options[i].value === valStr) { optionExists = true; break; }
            }
            if (!optionExists && valStr !== '0') {
                const dummy = document.createElement('option');
                dummy.value = valStr;
                dummy.text = 'ID Desconhecido (Salvo: ' + valStr + ')';
                input.add(dummy);
            }
            input.value = valStr;
        } else if (input.type === 'checkbox') {
            input.checked = (data[key] === 'true' || data[key] === true);
        } else {
            input.value = (data[key] !== null && data[key] !== undefined) ? data[key] : '';
        }
    });
}

// =========================================================
// ABA: BASE DE DADOS
// =========================================================
function updateDbViewer(data) {
    const dbFeedback = $('db-feedback');
    const warsBody = document.querySelector('#db-wars-table tbody');
    const notesBody = document.querySelector('#db-notes-table tbody');

    if (!data || data.error) {
        if (warsBody) warsBody.innerHTML = '<tr><td colspan="3">Erro ao carregar guerras.</td></tr>';
        if (notesBody) notesBody.innerHTML = '<tr><td colspan="3">Erro ao carregar notas.</td></tr>';
        displayFeedback(dbFeedback, (data && data.error) || 'Erro ao carregar dados do DB.', true);
        return;
    }

    if (warsBody) {
        if (Array.isArray(data.last_wars) && data.last_wars.length > 0) {
            warsBody.innerHTML = data.last_wars.map(w => {
                const id = w.id ? escapeHtml(w.id) : '';
                const label = id || 'N/A';
                const clickable = id
                    ? ' style="cursor:pointer;" title="Clique para copiar" data-copy="' + id + '"'
                    : '';
                return '<tr><td>' + escapeHtml(w.opponent || 'N/A') + '</td><td>' + fmtDateTime(w.end_time) +
                       '</td><td' + clickable + '>' + label + '</td></tr>';
            }).join('');
            warsBody.querySelectorAll('[data-copy]').forEach(td => {
                td.addEventListener('click', async () => {
                    try {
                        await navigator.clipboard.writeText(td.dataset.copy);
                        const original = td.textContent;
                        td.textContent = 'Copiado!';
                        setTimeout(() => { td.textContent = original; }, 1500);
                    } catch (err) { /* clipboard bloqueado */ }
                });
            });
        } else {
            warsBody.innerHTML = '<tr><td colspan="3">Nenhum registro de guerra encontrado.</td></tr>';
        }
    }

    if (notesBody) {
        if (Array.isArray(data.last_notes) && data.last_notes.length > 0) {
            notesBody.innerHTML = data.last_notes.map(n => {
                const priority = n.priority || 'none';
                return '<tr><td>' + escapeHtml(n.player_tag || 'N/A') + '</td><td>' +
                       escapeHtml(n.note || '-') + '</td><td class="priority-cell priority-' +
                       escapeHtml(priority) + '">' + escapeHtml(priority) + '</td></tr>';
            }).join('');
        } else {
            notesBody.innerHTML = '<tr><td colspan="3">Nenhuma nota de jogador encontrada.</td></tr>';
        }
    }
}

// =========================================================
// ABA: WATCHLIST
// =========================================================
function applyWatchlistFilter() {
    const body = document.querySelector('#admin-watchlist-tbody');
    if (!body) return;

    const nameFilter = $('watchlist-filter-name');
    const tagFilter = $('watchlist-filter-tag');
    const filterName = nameFilter ? nameFilter.value.trim().toLowerCase() : '';
    const filterTag = tagFilter ? tagFilter.value.trim().toLowerCase() : '';

    body.querySelectorAll('tr[data-player]').forEach(row => {
        const cellName = row.cells[0] ? row.cells[0].textContent.toLowerCase() : '';
        const cellTag = row.cells[1] ? row.cells[1].textContent.toLowerCase() : '';
        const nameMatch = cellName.includes(filterName);
        const tagMatch = cellTag.includes(filterTag);
        row.style.display = (nameMatch && tagMatch) ? '' : 'none';
    });
}

async function loadWatchlist() {
    const body = document.querySelector('#admin-watchlist-tbody');
    if (!body) return;

    body.innerHTML = '<tr><td colspan="6"><div class="loading-spinner" style="margin: 10px auto;"></div></td></tr>';

    let data;
    try {
        data = await api('watchlist');
    } catch (e) {
        body.innerHTML = '<tr><td colspan="6" class="error-text">Erro: ' + escapeHtml(e.message) + '</td></tr>';
        return;
    }

    if (data && data.error) {
        body.innerHTML = '<tr><td colspan="6" class="error-text">Erro: ' + escapeHtml(data.error) + '</td></tr>';
        return;
    }

    const watchlist = Array.isArray(data) ? data : [];
    if (watchlist.length === 0) {
        body.innerHTML = '<tr><td colspan="6">Nenhum jogador na lista de observação.</td></tr>';
        return;
    }

    const isViewer = currentUserRole === 'viewer';
    const actionHeader = document.querySelector('#admin-watchlist-table thead th:last-child');
    if (actionHeader) actionHeader.style.display = isViewer ? 'none' : '';

    body.innerHTML = watchlist.map(player => {
        const tag = player._id || '';
        return '<tr data-player="1">' +
            '<td><strong>' + escapeHtml(player.name || 'N/A') + '</strong></td>' +
            '<td style="font-family: monospace; color: var(--color-accent);">' + escapeHtml(tag || 'N/A') + '</td>' +
            '<td>' + escapeHtml(player.reason || '-') + '</td>' +
            '<td>' + escapeHtml(player.details || '-') + '</td>' +
            '<td>' + fmtDate(player.date_added) + '</td>' +
            '<td>' + (isViewer || !tag ? '' :
                '<button class="admin-remove-btn btn-admin btn-danger" data-tag="' + escapeHtml(tag) + '">Remover</button>') +
            '</td></tr>';
    }).join('');

    applyWatchlistFilter();
}

async function handleAddWatchlist(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const feedback = $('watchlist-add-feedback');

    const data = Object.fromEntries(new FormData(form).entries());
    const tag = (data.player_tag || '').trim();

    if (!tag || !tag.startsWith('#') || tag.length < 5) {
        displayFeedback(feedback, 'Por favor, insira uma tag válida (Ex: #ABC123XYZ).', true);
        return;
    }

    displayFeedback(feedback, 'Adicionando...', false, 0);
    try {
        const response = await api('watchlist/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (response && response.status === 'error') {
            displayFeedback(feedback, response.message || 'Erro ao adicionar.', true);
            return;
        }
        form.reset();
        displayFeedback(feedback, (response && response.message) || 'Jogador adicionado/atualizado.');
        await loadWatchlist();
    } catch (e) {
        displayFeedback(feedback, 'Erro ao adicionar à lista.', true);
    }
}

async function handleRemoveWatchlist(event) {
    const button = event.target.closest('.admin-remove-btn');
    if (!button) return;

    const playerTag = button.dataset.tag;
    const row = button.closest('tr');
    const playerName = (row && row.cells[0] && row.cells[0].textContent) || playerTag;

    if (!playerTag || !confirm('Tem certeza que deseja remover ' + playerName + ' (' + playerTag + ') da lista?')) return;

    button.disabled = true;
    button.textContent = '...';
    displayFeedback($('watchlist-list-feedback'), 'Removendo...', false, 0);

    try {
        const response = await api('watchlist/remove', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ player_tag: playerTag })
        });
        if (response && response.status === 'error') {
            displayFeedback($('watchlist-list-feedback'), response.message || 'Erro ao remover.', true);
            button.disabled = false;
            button.textContent = 'Remover';
            return;
        }
        displayFeedback($('watchlist-list-feedback'), (response && response.message) || 'Operação concluída.');
        await loadWatchlist();
    } catch (e) {
        button.disabled = false;
        button.textContent = 'Remover';
    }
}

// =========================================================
// ABA: RADAR PERICIAL (XAI)
// =========================================================
async function loadTrainingStatus() {
    const el = $('radar-training-status');
    if (!el) return;

    let data;
    try {
        data = await api('smurf_training_status');
    } catch (e) {
        el.innerHTML = '';
        return;
    }
    if (!data || data.error) { el.innerHTML = ''; return; }

    const realNeeded = data.real_labels_needed || 1;
    const samplesNeeded = data.total_samples_needed || 1;
    const pctLabels = Math.min(100, (data.real_labels / realNeeded) * 100);
    const pctSamples = Math.min(100, (data.total_samples / samplesNeeded) * 100);

    const statusMap = {
        cold_start: 'Cold Start', ready: 'Pronto para Treinar',
        trained: 'Modelo Treinado', unavailable: 'Indisponivel', error: 'Erro'
    };
    const statusColors = {
        cold_start: '#3498db', ready: '#f39c12', trained: '#2ecc71',
        unavailable: '#e74c3c', error: '#e74c3c'
    };
    const statusIcons = {
        cold_start: '&#10052;', ready: '&#9889;', trained: '&#10004;',
        unavailable: '&#9888;', error: '&#9888;'
    };

    const st = data.model_status;
    const stColor = statusColors[st] || '#a0aec0';
    const stLabel = statusMap[st] || st;
    const stIcon = statusIcons[st] || '';
    const bar1Color = pctLabels >= 100 ? '#2ecc71' : '#f39c12';
    const bar2Color = pctSamples >= 100 ? '#2ecc71' : '#3498db';

    const hints = {
        cold_start: 'Use os botoes Absolver/Condenar abaixo para treinar o modelo.',
        ready: 'Requisitos atingidos! O modelo sera treinado no proximo ciclo.',
        trained: 'Modelo ativo e previsoes usando XGBoost.'
    };

    el.innerHTML = `
    <div style="background:rgba(0,0,0,0.25); border:1px solid rgba(255,255,255,0.08); border-radius:10px; padding:15px 20px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; gap:10px;">
            <span style="font-size:0.8em; text-transform:uppercase; letter-spacing:1px; color:#a0aec0; font-weight:bold;">Status do Modelo XGBoost</span>
            <span style="font-size:0.8em; color:${stColor}; font-weight:bold;">${stIcon} ${stLabel}</span>
        </div>
        <div style="margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; font-size:0.78em; color:#cbd5e0; margin-bottom:4px;">
                <span>Labels Reais (Absolver / Condenar)</span>
                <span style="font-weight:bold; color:${bar1Color};">${data.real_labels} / ${data.real_labels_needed}</span>
            </div>
            <div style="height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                <div style="height:100%; width:${pctLabels}%; background:${bar1Color}; border-radius:3px;"></div>
            </div>
        </div>
        <div>
            <div style="display:flex; justify-content:space-between; font-size:0.78em; color:#cbd5e0; margin-bottom:4px;">
                <span>Amostras de Treino</span>
                <span style="font-weight:bold; color:${bar2Color};">${data.total_samples} / ${data.total_samples_needed}</span>
            </div>
            <div style="height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                <div style="height:100%; width:${pctSamples}%; background:${bar2Color}; border-radius:3px;"></div>
            </div>
        </div>
        ${hints[st] ? '<div style="margin-top:10px; font-size:0.75em; color:#718096; font-style:italic;">' + hints[st] + '</div>' : ''}
    </div>`;
}

function renderDossierTerminal(doc, color) {
    let terminalHtml = '';
    if (Array.isArray(doc.thoughts)) {
        doc.thoughts.forEach(t => {
            let weightBadge;
            if (t.weight && t.weight !== 'Info' && t.weight !== 'Trace') {
                weightBadge = '<span style="display:inline-block; padding:2px 6px; background:rgba(255,255,255,0.1); border-radius:3px; margin-right:8px; font-weight:bold; color:' + color + ';">[Peso: ' + escapeHtml(t.weight) + ']</span>';
            } else {
                weightBadge = '<span style="display:inline-block; padding:2px 6px; background:rgba(255,255,255,0.1); border-radius:3px; margin-right:8px; color:#a0aec0;">[' + escapeHtml(t.axis) + ']</span>';
            }
            terminalHtml += '<div style="margin-bottom:8px; padding-left:10px; border-left:2px solid ' + color + '55;">' +
                weightBadge + ' <span style="color:#e2e8f0;">' + escapeHtml(t.text) + '</span></div>';
        });
    }
    return terminalHtml;
}

async function loadRadarDossier() {
    const container = $('radar-dossier-container');
    if (!container) return;

    container.innerHTML = '<div style="text-align:center;"><div class="loading-spinner" style="margin: 20px auto;"></div></div>';

    let data;
    try {
        data = await api('smurf_dossier');
    } catch (e) {
        container.innerHTML = '<p class="error-text">Falha de comunicação com o Módulo XAI Forense.</p>';
        return;
    }

    if (data && data.error) {
        container.innerHTML = '<p class="error-text">' + escapeHtml(data.error) + '</p>';
        return;
    }

    let dossier = [];
    if (Array.isArray(data)) dossier = data;
    else if (data && Array.isArray(data.dossier)) dossier = data.dossier;
    else if (data && Array.isArray(data.data)) dossier = data.data;
    else if (data && Array.isArray(data.message)) dossier = data.message;

    if (dossier.length === 0) {
        container.innerHTML = `
        <div style="text-align:center; padding:30px; background:rgba(46,204,113,0.05); border:1px solid rgba(46,204,113,0.2); border-radius:8px;">
            <h3 style="color: var(--color-success); margin-bottom:10px;"><img src="/assets/icons/Icon_HV_Shield.png" class="icon-sm" alt="clean"> Clã Limpo (Status Verde)</h3>
            <p style="color: var(--color-text-secondary);">A Inteligência Forense cruzou todos os eixos de guerra, doação, laboratório e lexicologia nas últimas horas e não encontrou elos suspeitos.</p>
        </div>`;
        return;
    }

    let html = '<div class="dossier-grid" style="display:grid; gap:20px;">';
    dossier.forEach(doc => {
        const color = doc.risk_color || '#a0aec0';
        const confidence = Number(doc.confidence) || 0;
        const pairId = doc.pair_id || '';

        html += `
        <div class="dossier-card" data-pair-id="${escapeHtml(pairId)}" style="background:rgba(0,0,0,0.25); border:1px solid rgba(255,255,255,0.05); border-radius:12px; overflow:hidden; box-shadow:0 4px 6px rgba(0,0,0,0.3);">
            <div style="padding:15px 20px; background:linear-gradient(90deg, ${color}22 0%, transparent 100%); border-bottom:1px solid ${color}44; display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap;">
                <div>
                    <span style="font-size:0.75em; text-transform:uppercase; letter-spacing:1px; color:${color}; font-weight:bold;">Identificação XAI</span>
                    <h4 style="margin:5px 0 0 0; font-size:1.2em; display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                        <img src="/assets/icons/Icon_HV_Podium.png" class="icon-sm" alt="main"> ${escapeHtml(doc.main_name)} <span style="font-size:0.7em; color:var(--color-text-secondary);">${escapeHtml(doc.main_tag)}</span>
                        <span style="color:${color};"><img src="/assets/icons/Icon_HV_Raid_Attack.png" class="icon-sm" alt="link"></span>
                        <img src="/assets/icons/no_star.png" class="icon-sm" alt="smurf"> ${escapeHtml(doc.smurf_name)} <span style="font-size:0.7em; color:var(--color-text-secondary);">${escapeHtml(doc.smurf_tag)}</span>
                    </h4>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:1.8em; font-weight:900; color:${color}; line-height:1;">${escapeHtml(doc.confidence)}%</div>
                    <div style="font-size:0.8em; color:var(--color-text-secondary); text-transform:uppercase;">${escapeHtml(doc.risk_label)}</div>
                </div>
            </div>
            <div style="height:4px; background:rgba(255,255,255,0.05); width:100%;">
                <div style="height:100%; width:${confidence}%; background:${color}; box-shadow:0 0 10px ${color};"></div>
            </div>
            <div style="padding:20px;">
                <div style="margin-bottom:8px; font-size:0.85em; color:var(--color-text-secondary); text-transform:uppercase; font-weight:bold; letter-spacing:1px;"><img src="/assets/icons/Icon_HV_Attack_Star.png" class="icon-sm" alt="AI"> Motor de Inferência (Cadeia Lógica)</div>
                <div style="background:rgba(0,0,0,0.4); border:1px solid rgba(255,255,255,0.05); border-radius:6px; padding:15px; font-family:'Courier New', monospace; font-size:0.9em; line-height:1.5; max-height:250px; overflow-y:auto;">
                    ${renderDossierTerminal(doc, color)}
                </div>
            </div>
            <div style="padding:15px 20px; background:rgba(0,0,0,0.2); border-top:1px solid rgba(255,255,255,0.05); display:flex; gap:15px; flex-wrap:wrap;">
                <button type="button" class="btn-admin" data-judge="absolve_smurf" style="background:rgba(46,204,113,0.15); color:#2ecc71; border:1px solid #2ecc71; flex:1; min-width:180px;"><img src="/assets/icons/Icon_HV_Shield.png" class="icon-sm" alt="safe"> Falso Positivo (Limpar)</button>
                <button type="button" class="btn-admin" data-judge="condemn_smurf" style="background:rgba(231,76,60,0.15); color:#e74c3c; border:1px solid #e74c3c; flex:1; min-width:180px;"><img src="/assets/icons/Icon_HV_Attack_Star.png" class="icon-sm" alt="danger"> Condenar p/ Watchlist</button>
            </div>
        </div>`;
    });
    html += '</div>';
    container.innerHTML = html;
}

async function judgeSmurf(pairId, action) {
    if (!pairId) return;
    const isCondemn = action === 'condemn_smurf';
    const msg = isCondemn
        ? 'ATENÇÃO: TEM CERTEZA?\n\nA Matriz Forense enviará ambas as contas para a Watchlist como "Smurfs Confirmadas" e apagará o dossiê da tela principal.'
        : 'Absolver Contas?\n\nA IA aprenderá que este padrão é falso positivo e atenuará a pontuação vetorial desta ligação.';
    if (!confirm(msg)) return;

    const feedback = $('radar-feedback');
    displayFeedback(feedback, 'Processando veredito na Base de Dados...', false, 0);

    try {
        const response = await api('actions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: action, payload: { pair_id: pairId } })
        });
        displayFeedback(feedback, (response && response.message) || 'Sentença aplicada!');
        await loadRadarDossier();
        await loadTrainingStatus();
    } catch (e) {
        displayFeedback(feedback, 'Erro ao comunicar com o Kernel Central.', true);
    }
}

async function cleanupSmurfDB() {
    if (!confirm('ATENÇÃO: TEM CERTEZA?\n\nIsso vai APAGAR TODAS as evidências do Radar Pericial e resetar o banco de dados.\n\nApós limpar, o novo sistema v3.0 vai começar do zero com regras muito mais precisas.')) return;

    const feedback = $('radar-feedback');
    displayFeedback(feedback, 'Limpando banco de dados do Radar Pericial...', false, 0);

    try {
        const response = await api('actions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'smurf_cleanup', payload: {} })
        });
        displayFeedback(feedback, (response && response.message) || 'Banco limpo com sucesso!');
        await loadRadarDossier();
    } catch (e) {
        displayFeedback(feedback, 'Erro ao limpar banco de dados.', true);
    }
}

// Expostos para os botoes com onclick no admin_panel.html
window.loadRadarDossier = loadRadarDossier;
window.cleanupSmurfDB = cleanupSmurfDB;
window.judgeSmurf = judgeSmurf;

// =========================================================
// ABA: ANALYTICS IA
// =========================================================
async function loadAnalyticsData() {
    const tbody = document.querySelector('#analytics-table tbody');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="5"><div class="loading-spinner" style="margin: 10px auto;"></div></td></tr>';

    let response;
    try {
        response = await fetch('/api/members', { credentials: 'include' });
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="5" class="error-text">Erro de conexão ao buscar dados da IA.</td></tr>';
        return;
    }

    if (!response.ok) {
        let msg = 'HTTP ' + response.status;
        try {
            const errData = await response.json();
            if (errData && errData.message) msg = errData.message;
        } catch (e) { /* sem corpo */ }
        tbody.innerHTML = '<tr><td colspan="5" class="error-text">' + escapeHtml(msg) + '</td></tr>';
        return;
    }

    let data;
    try {
        data = await response.json();
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="5" class="error-text">Resposta inválida da API.</td></tr>';
        return;
    }

    if (data && data.status === 'error') {
        tbody.innerHTML = '<tr><td colspan="5" class="error-text">' + escapeHtml(data.message || 'Erro desconhecido.') + '</td></tr>';
        return;
    }

    const members = (data && Array.isArray(data.members)) ? data.members : [];
    if (members.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5">Nenhum membro encontrado.</td></tr>';
        return;
    }

    const sorted = members.slice().sort((a, b) => (b.attack_probability || 0) - (a.attack_probability || 0));

    tbody.innerHTML = sorted.map(m => {
        const hasProb = m.attack_probability !== undefined && m.attack_probability !== null;
        const prob = hasProb ? m.attack_probability + '%' : 'Aguardando Guerras...';
        const tier = m.tier || 'Sem Dados Suficientes';
        const wars = m.wars_participated_ml || 0;

        let probColor = 'var(--color-text-main)';
        if (hasProb) {
            if (m.attack_probability >= 90) probColor = '#2ecc71';
            else if (m.attack_probability >= 60) probColor = '#f1c40f';
            else probColor = '#e74c3c';
        }

        return '<tr>' +
            '<td><strong>' + escapeHtml(m.name) + '</strong></td>' +
            '<td style="font-family: monospace; color: var(--color-accent);">' + escapeHtml(m.tag) + '</td>' +
            '<td style="font-weight: bold;">' + escapeHtml(tier) + '</td>' +
            '<td style="color: ' + probColor + '; font-weight: 900; font-size: 1.1em;">' + escapeHtml(prob) + '</td>' +
            '<td>' + escapeHtml(wars) + ' / 50</td>' +
            '</tr>';
    }).join('');
}

// =========================================================
// DISCOHOOK — EDITOR DE EMBEDS
// =========================================================
function dhEsc(s) { return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

function dhInitEditor() {
    const list = $('dh-embeds-list');
    if (!list) return;

    dhEmbeds = [];
    dhEmbedIdCounter = 0;

    $('dh-add-embed-btn').onclick = () => dhAddEmbed();
    $('dh-clear-btn').onclick = dhClearAll;
    $('dh-export-json-btn').onclick = dhExportJSON;
    $('dh-import-json-btn').onclick = dhImportJSON;
    $('dh-example-btn').onclick = dhLoadExample;
    $('dh-send-btn').onclick = dhSendWebhook;
    $('dh-content').oninput = dhUpdatePreview;
    $('dh-webhook-url').oninput = function () {
        try { localStorage.setItem('dh_saved_webhook', this.value); } catch (e) { /* modo privado */ }
        dhFetchWebhookInfo(this.value.trim());
    };

    try {
        const saved = localStorage.getItem('dh_saved_webhook');
        if (saved) {
            $('dh-webhook-url').value = saved;
            dhFetchWebhookInfo(saved);
        }
    } catch (e) { /* localStorage indisponivel */ }

    dhUpdatePreview();
}

function dhFetchWebhookInfo(url) {
    const info = $('dh-webhook-info');
    const avatar = $('dh-webhook-avatar');
    const name = $('dh-webhook-name');
    const channel = $('dh-webhook-channel');
    if (!info) return;

    if (!url || !url.match(/^https:\/\/(discord|discordapp)\.com\/api\/webhooks\//)) {
        info.style.display = 'none';
        return;
    }

    fetch(url, { method: 'GET', headers: { 'Accept': 'application/json' } })
        .then(r => { if (!r.ok) throw new Error(); return r.json(); })
        .then(d => {
            avatar.src = d.avatar
                ? 'https://cdn.discordapp.com/avatars/' + d.id + '/' + d.avatar + '.png?size=32'
                : 'https://cdn.discordapp.com/embed/avatars/0.png';
            name.textContent = d.name || 'Sem nome';
            channel.textContent = d.channel_id ? '#' + d.channel_id : '';
            info.style.display = 'flex';
        })
        .catch(() => { info.style.display = 'none'; });
}

function dhCreateId() { return ++dhEmbedIdCounter; }

function dhAddEmbed(data) {
    const id = dhCreateId();
    const d = data || {};
    const embed = {
        id,
        title: d.title || '',
        description: d.description || '',
        color: d.color || '#5865f2',
        url: d.url || '',
        author_name: d.author_name || '',
        author_url: d.author_url || '',
        author_icon_url: d.author_icon_url || '',
        footer_text: d.footer_text || '',
        footer_icon_url: d.footer_icon_url || '',
        thumbnail_url: d.thumbnail_url || '',
        image_url: d.image_url || '',
        fields: Array.isArray(d.fields) ? d.fields.map(f => Object.assign({}, f)) : []
    };
    dhEmbeds.push(embed);
    dhRenderCard(embed);
    dhUpdatePreview();
}

function dhRenderCard(embed) {
    const container = $('dh-embeds-list');
    if (!container) return;
    const idx = dhEmbeds.indexOf(embed);
    const ec = dhEsc;

    const card = document.createElement('div');
    card.className = 'dh-embed-card';
    card.id = 'dh-card-' + embed.id;

    card.innerHTML =
        '<div class="dh-embed-header" data-id="' + embed.id + '">' +
            '<div class="dh-embed-header-left">' +
                '<span class="dh-embed-header-color" style="display:inline-block;width:10px;height:10px;border-radius:2px;background:' + embed.color + '"></span>' +
                'Embed #' + (idx + 1) +
            '</div>' +
            '<div class="dh-embed-header-actions">' +
                '<button type="button" class="dh-mvup" title="↑">↑</button>' +
                '<button type="button" class="dh-mvdn" title="↓">↓</button>' +
                '<button type="button" class="dh-dub" title="Duplicar">⧉</button>' +
                '<button type="button" class="dh-tog" title="Recolher">−</button>' +
                '<button type="button" class="dh-rm danger" title="Remover">✕</button>' +
            '</div>' +
        '</div>' +
        '<div class="dh-embed-body">' +
            '<div class="dh-field-row">' +
                '<div class="dh-field-group"><label>Title</label><input type="text" class="dh-fi-title" value="' + ec(embed.title) + '" placeholder="Título"></div>' +
                '<div class="dh-field-group"><label>URL</label><input type="url" class="dh-fi-url" value="' + ec(embed.url) + '" placeholder="https://..."></div>' +
            '</div>' +
            '<div class="dh-field-group"><label>Description</label><textarea class="dh-fi-desc" rows="2" placeholder="Descrição">' + ec(embed.description) + '</textarea></div>' +
            '<div class="dh-field-row">' +
                '<div class="dh-field-group"><label>Color</label>' +
                    '<div class="dh-color-input-wrap">' +
                        '<input type="color" class="dh-fi-color" value="' + embed.color + '">' +
                        '<input type="text" class="dh-fi-colortxt" value="' + embed.color + '" placeholder="#5865f2">' +
                    '</div>' +
                    '<div class="dh-color-presets">' + DH_COLOR_PRESETS.map(c =>
                        '<div class="dh-color-preset' + (c === embed.color ? ' active' : '') + '" style="background:' + c + '" data-c="' + c + '"></div>'
                    ).join('') + '</div>' +
                '</div>' +
                '<div class="dh-field-group"><label>Thumbnail URL</label><input type="url" class="dh-fi-thumb" value="' + ec(embed.thumbnail_url) + '" placeholder="https://..."></div>' +
            '</div>' +
            '<div class="dh-field-row">' +
                '<div class="dh-field-group"><label>Author Name</label><input type="text" class="dh-fi-aname" value="' + ec(embed.author_name) + '" placeholder="Nome"></div>' +
                '<div class="dh-field-group"><label>Author URL</label><input type="url" class="dh-fi-aurl" value="' + ec(embed.author_url) + '" placeholder="https://..."></div>' +
            '</div>' +
            '<div class="dh-field-group"><label>Author Icon URL</label><input type="url" class="dh-fi-aicon" value="' + ec(embed.author_icon_url) + '" placeholder="https://..."></div>' +
            '<div class="dh-field-row">' +
                '<div class="dh-field-group"><label>Footer Text</label><input type="text" class="dh-fi-ftext" value="' + ec(embed.footer_text) + '" placeholder="Texto"></div>' +
                '<div class="dh-field-group"><label>Footer Icon URL</label><input type="url" class="dh-fi-ficon" value="' + ec(embed.footer_icon_url) + '" placeholder="https://..."></div>' +
            '</div>' +
            '<div class="dh-field-group"><label>Image URL</label><input type="url" class="dh-fi-img" value="' + ec(embed.image_url) + '" placeholder="https://..."></div>' +
            '<div class="dh-field-group"><label>Fields</label><div class="dh-fields-container" id="dh-fc-' + embed.id + '"></div><button type="button" class="dh-addf" data-id="' + embed.id + '">+ Add Field</button></div>' +
        '</div>';

    container.appendChild(card);

    const body = card.querySelector('.dh-embed-body');
    const hdr = card.querySelector('.dh-embed-header');

    hdr.querySelector('.dh-tog').onclick = function (e) { e.stopPropagation(); dhToggleBody(embed.id); };
    hdr.querySelector('.dh-rm').onclick = function (e) { e.stopPropagation(); dhRemove(embed.id); };
    hdr.querySelector('.dh-dub').onclick = function (e) { e.stopPropagation(); dhDuplicate(embed.id); };
    hdr.querySelector('.dh-mvup').onclick = function (e) { e.stopPropagation(); dhMove(embed.id, -1); };
    hdr.querySelector('.dh-mvdn').onclick = function (e) { e.stopPropagation(); dhMove(embed.id, 1); };
    hdr.onclick = function () { dhToggleBody(embed.id); };

    function bind(sel, key) {
        const node = card.querySelector(sel);
        if (node) node.oninput = function () {
            embed[key] = this.value;
            dhUpdateHeadColor(embed.id);
            dhUpdatePreview();
        };
    }
    bind('.dh-fi-title', 'title');
    bind('.dh-fi-url', 'url');
    bind('.dh-fi-desc', 'description');
    bind('.dh-fi-color', 'color');
    bind('.dh-fi-colortxt', 'color');
    bind('.dh-fi-thumb', 'thumbnail_url');
    bind('.dh-fi-aname', 'author_name');
    bind('.dh-fi-aurl', 'author_url');
    bind('.dh-fi-aicon', 'author_icon_url');
    bind('.dh-fi-ftext', 'footer_text');
    bind('.dh-fi-ficon', 'footer_icon_url');
    bind('.dh-fi-img', 'image_url');

    card.querySelectorAll('.dh-color-preset').forEach(preset => {
        preset.onclick = function () {
            embed.color = this.dataset.c;
            const p = card.querySelector('.dh-fi-color');
            const t = card.querySelector('.dh-fi-colortxt');
            if (p) p.value = embed.color;
            if (t) t.value = embed.color;
            card.querySelectorAll('.dh-color-preset').forEach(x => x.classList.remove('active'));
            this.classList.add('active');
            dhUpdateHeadColor(embed.id);
            dhUpdatePreview();
        };
    });

    card.querySelector('.dh-addf').onclick = function () { dhAddField(embed.id); };
    embed.fields.forEach(f => dhRenderField(embed.id, f));
    dhUpdateHeadColor(embed.id);

    if (body) body.classList.remove('collapsed');
}

function dhToggleBody(id) {
    const card = $('dh-card-' + id);
    if (!card) return;
    const body = card.querySelector('.dh-embed-body');
    const tog = card.querySelector('.dh-tog');
    if (!body || !tog) return;
    body.classList.toggle('collapsed');
    tog.textContent = body.classList.contains('collapsed') ? '+' : '−';
}

function dhRenderField(eid, field) {
    const container = $('dh-fc-' + eid);
    if (!container) return;
    const embed = dhEmbeds.find(e => e.id === eid);
    if (!embed) return;

    const item = document.createElement('div');
    item.className = 'dh-field-item';
    item.innerHTML =
        '<input type="text" class="dh-fname" value="' + dhEsc(field.name) + '" placeholder="Nome">' +
        '<textarea class="dh-fval" rows="1" placeholder="Valor">' + dhEsc(field.value) + '</textarea>' +
        '<label class="dh-field-inline-label"><input type="checkbox" class="dh-finline"' + (field.inline ? ' checked' : '') + '><span>Inline</span></label>' +
        '<button type="button" class="dh-field-remove" title="Remover">✕</button>';
    container.appendChild(item);

    item.querySelector('.dh-fname').oninput = function () { field.name = this.value; dhUpdatePreview(); };
    item.querySelector('.dh-fval').oninput = function () { field.value = this.value; dhUpdatePreview(); };
    item.querySelector('.dh-finline').onchange = function () { field.inline = this.checked; dhUpdatePreview(); };
    item.querySelector('.dh-field-remove').onclick = function () {
        embed.fields = embed.fields.filter(f => f !== field);
        container.removeChild(item);
        dhUpdatePreview();
    };
}

function dhAddField(id) {
    const embed = dhEmbeds.find(e => e.id === id);
    if (!embed) return;
    const field = { name: '', value: '', inline: false };
    embed.fields.push(field);
    dhRenderField(id, field);
    dhUpdatePreview();
}

function dhRemove(id) {
    dhEmbeds = dhEmbeds.filter(e => e.id !== id);
    const card = $('dh-card-' + id);
    if (card) card.remove();
    dhRenumber();
    dhUpdatePreview();
}

function dhDuplicate(id) {
    const embed = dhEmbeds.find(e => e.id === id);
    if (!embed) return;
    const clone = Object.assign({}, embed, { fields: embed.fields.map(f => Object.assign({}, f)) });
    clone.id = dhCreateId();
    dhEmbeds.push(clone);
    dhRenderCard(clone);
    dhUpdatePreview();
}

function dhMove(id, dir) {
    const idx = dhEmbeds.findIndex(e => e.id === id);
    if (idx === -1) return;
    const ni = idx + dir;
    if (ni < 0 || ni >= dhEmbeds.length) return;
    const tmp = dhEmbeds[idx];
    dhEmbeds[idx] = dhEmbeds[ni];
    dhEmbeds[ni] = tmp;

    const list = $('dh-embeds-list');
    if (list) list.innerHTML = '';
    dhEmbeds.forEach(e => dhRenderCard(e));
    dhUpdatePreview();
}

function dhRenumber() {
    dhEmbeds.forEach((e, i) => {
        const card = $('dh-card-' + e.id);
        if (!card) return;
        const left = card.querySelector('.dh-embed-header-left');
        if (left) {
            left.innerHTML = '<span class="dh-embed-header-color" style="display:inline-block;width:10px;height:10px;border-radius:2px;background:' + e.color + '"></span> Embed #' + (i + 1);
        }
    });
}

function dhUpdateHeadColor(id) {
    const e = dhEmbeds.find(x => x.id === id);
    if (!e) return;
    const card = $('dh-card-' + id);
    if (!card) return;
    const dot = card.querySelector('.dh-embed-header-color');
    if (dot) dot.style.background = e.color;
    card.querySelectorAll('.dh-color-preset').forEach(p => p.classList.toggle('active', p.dataset.c === e.color));
}

function dhGetPayload() {
    const contentEl = $('dh-content');
    const content = contentEl ? (contentEl.value || '') : '';

    const embeds = dhEmbeds.map(e => {
        const obj = {};
        if (e.title) obj.title = e.title;
        if (e.description) obj.description = e.description;
        if (e.url) obj.url = e.url;
        if (e.color) {
            const parsed = parseInt(e.color.replace('#', ''), 16);
            if (!isNaN(parsed)) obj.color = parsed;
        }
        if (e.author_name) {
            obj.author = { name: e.author_name };
            if (e.author_url) obj.author.url = e.author_url;
            if (e.author_icon_url) obj.author.icon_url = e.author_icon_url;
        }
        if (e.footer_text) {
            obj.footer = { text: e.footer_text };
            if (e.footer_icon_url) obj.footer.icon_url = e.footer_icon_url;
        }
        if (e.thumbnail_url) obj.thumbnail = { url: e.thumbnail_url };
        if (e.image_url) obj.image = { url: e.image_url };
        if (Array.isArray(e.fields) && e.fields.length) {
            obj.fields = e.fields.map(f => ({
                name: f.name || ' ', value: f.value || ' ', inline: !!f.inline
            }));
        }
        return obj;
    }).filter(o => Object.keys(o).length > 0);

    const payload = {};
    if (content) payload.content = content;
    if (embeds.length) payload.embeds = embeds;
    return payload;
}

function dhUpdatePreview() {
    const container = $('dh-preview-messages');
    if (!container) return;

    const contentEl = $('dh-content');
    const content = contentEl ? (contentEl.value || '') : '';
    const payload = dhGetPayload();

    const count = $('dh-content-count');
    if (count) {
        count.textContent = content.length + '/2000';
        count.className = 'dh-char-count';
        if (content.length > 2000) count.classList.add('exceed');
        else if (content.length > 1800) count.classList.add('warn');
    }

    if (!content && (!payload.embeds || !payload.embeds.length)) {
        container.innerHTML = '<div class="dh-preview-placeholder">' +
            '<div style="font-size:3rem;margin-bottom:10px;opacity:0.3;"><svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg></div>' +
            '<div style="color:var(--color-text-secondary);">Preencha os dados ao lado para ver o preview</div></div>';
        return;
    }

    let html = '';
    if (content) html += '<div class="dh-msg-content">' + dhFormatContent(content) + '</div>';
    if (payload.embeds) payload.embeds.forEach(e => { html += dhRenderPreview(e); });
    container.innerHTML = html;
}

function dhFormatContent(t) {
    return dhEsc(t)
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/~~(.+?)~~/g, '<s>$1</s>')
        .replace(/__(.+?)__/g, '<u>$1</u>')
        .replace(/`(.+?)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>')
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
        .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
}

function dhRenderPreview(embed) {
    const color = embed.color ? '#' + embed.color.toString(16).padStart(6, '0') : '#5865f2';
    let h = '<div class="dh-embed-preview"><div class="dh-embed-color" style="background:' + color + '"></div><div class="dh-embed-body-preview">';

    if (embed.thumbnail) h += '<div class="dh-embed-thumbnail"><img src="' + dhEsc(embed.thumbnail.url) + '" alt="" onerror="this.style.display=\'none\'"></div>';

    if (embed.author) {
        h += '<div class="dh-embed-author">';
        if (embed.author.icon_url) h += '<img src="' + dhEsc(embed.author.icon_url) + '" alt="" onerror="this.style.display=\'none\'">';
        h += '<span>';
        if (embed.author.url) h += '<a href="' + dhEsc(embed.author.url) + '" target="_blank" rel="noopener noreferrer">';
        h += dhEsc(embed.author.name);
        if (embed.author.url) h += '</a>';
        h += '</span></div>';
    }

    if (embed.title) {
        h += '<div class="dh-embed-title">';
        if (embed.url) h += '<a href="' + dhEsc(embed.url) + '" target="_blank" rel="noopener noreferrer">';
        h += dhEsc(embed.title);
        if (embed.url) h += '</a>';
        h += '</div>';
    }

    if (embed.description) h += '<div class="dh-embed-description">' + dhFormatContent(embed.description) + '</div>';

    if (Array.isArray(embed.fields) && embed.fields.length) {
        h += '<div class="dh-embed-fields">';
        embed.fields.forEach(f => {
            h += '<div class="dh-embed-field' + (f.inline ? ' inline' : '') + '">' +
                 '<div class="dh-embed-field-name">' + dhEsc(f.name) + '</div>' +
                 '<div class="dh-embed-field-value">' + dhFormatContent(f.value) + '</div></div>';
        });
        h += '</div>';
    }

    if (embed.image) h += '<div class="dh-embed-image"><img src="' + dhEsc(embed.image.url) + '" alt="" onerror="this.style.display=\'none\'"></div>';

    if (embed.footer || embed.timestamp) {
        h += '<div class="dh-embed-footer">';
        if (embed.footer) {
            if (embed.footer.icon_url) h += '<img src="' + dhEsc(embed.footer.icon_url) + '" alt="" onerror="this.style.display=\'none\'">';
            h += '<span>' + dhEsc(embed.footer.text) + '</span>';
        }
        if (embed.timestamp) {
            const ts = new Date(embed.timestamp);
            if (!isNaN(ts.getTime())) h += '<span class="dh-embed-timestamp">' + ts.toLocaleDateString('pt-BR') + '</span>';
        }
        h += '</div>';
    }

    h += '</div></div>';
    return h;
}

async function dhSendWebhook() {
    const urlEl = $('dh-webhook-url');
    const fb = $('dh-feedback');
    const url = urlEl ? urlEl.value.trim() : '';

    if (!url) {
        if (fb) { fb.className = 'dh-send-status error'; fb.textContent = 'Insira uma URL de Webhook primeiro.'; }
        return;
    }

    const payload = dhGetPayload();
    if (!payload.content && (!payload.embeds || !payload.embeds.length)) {
        if (fb) { fb.className = 'dh-send-status error'; fb.textContent = 'Adicione conteúdo ou pelo menos um embed.'; }
        return;
    }

    const btn = $('dh-send-btn');
    const orig = btn ? btn.textContent : '';
    if (btn) { btn.textContent = 'Enviando...'; btn.disabled = true; }
    if (fb) { fb.className = 'dh-send-status loading'; fb.textContent = 'Enviando...'; }

    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (r.ok) {
            if (fb) { fb.className = 'dh-send-status success'; fb.textContent = 'Mensagem enviada com sucesso!'; }
        } else {
            const err = await r.text().catch(() => 'Erro desconhecido');
            if (fb) { fb.className = 'dh-send-status error'; fb.textContent = 'Erro ' + r.status + ': ' + err.substring(0, 200); }
        }
    } catch (err) {
        if (fb) { fb.className = 'dh-send-status error'; fb.textContent = 'Falha: ' + err.message; }
    } finally {
        if (btn) { btn.textContent = orig; btn.disabled = false; }
    }
}

function dhClearAll() {
    const content = $('dh-content');
    if (content) content.value = '';
    const list = $('dh-embeds-list');
    if (list) list.innerHTML = '';
    dhEmbeds = [];
    dhEmbedIdCounter = 0;
    const fb = $('dh-feedback');
    if (fb) { fb.textContent = ''; fb.className = ''; }
    dhUpdatePreview();
}

function dhExportJSON() { dhShowModal('Exportar JSON', JSON.stringify(dhGetPayload(), null, 2), false); }
function dhImportJSON() { dhShowModal('Importar JSON', '', true); }

function dhShowModal(title, json, isImport) {
    const old = document.querySelector('.dh-modal-overlay');
    if (old) old.remove();

    const ov = document.createElement('div');
    ov.className = 'dh-modal-overlay';
    ov.innerHTML = '<div class="dh-modal"><h3>' + dhEsc(title) + '</h3>' +
        '<textarea id="dh-json-ta"' + (isImport ? ' placeholder="Cole o JSON..."' : '') + '>' + dhEsc(json) + '</textarea>' +
        '<div class="dh-modal-actions"><button type="button" class="dh-mc">Cancelar</button>' +
        (isImport ? '<button type="button" class="dh-mi primary">Importar</button>'
                  : '<button type="button" class="dh-mcp primary">Copiar</button>') + '</div></div>';
    document.body.appendChild(ov);

    ov.querySelector('.dh-mc').onclick = () => ov.remove();
    ov.onclick = e => { if (e.target === ov) ov.remove(); };

    if (isImport) {
        ov.querySelector('.dh-mi').onclick = function () {
            try {
                const data = JSON.parse($('dh-json-ta').value);
                dhImportPayload(data);
                ov.remove();
            } catch (e) {
                alert('JSON inválido: ' + e.message);
            }
        };
    } else {
        ov.querySelector('.dh-mcp').onclick = function () {
            const ta = $('dh-json-ta');
            ta.select();
            try { document.execCommand('copy'); } catch (e) { /* clipboard legado */ }
            this.textContent = 'Copiado!';
            setTimeout(() => ov.remove(), 800);
        };
    }
}

function dhImportPayload(data) {
    const list = $('dh-embeds-list');
    if (list) list.innerHTML = '';
    dhEmbeds = [];
    dhEmbedIdCounter = 0;

    if (data.content) {
        const content = $('dh-content');
        if (content) content.value = data.content;
    }

    if (Array.isArray(data.embeds)) {
        data.embeds.forEach(ed => {
            const source = ed || {};
            dhAddEmbed({
                title: source.title || '',
                description: source.description || '',
                color: source.color ? '#' + source.color.toString(16).padStart(6, '0') : '#5865f2',
                url: source.url || '',
                author_name: (source.author && source.author.name) || '',
                author_url: (source.author && source.author.url) || '',
                author_icon_url: (source.author && source.author.icon_url) || '',
                footer_text: (source.footer && source.footer.text) || '',
                footer_icon_url: (source.footer && source.footer.icon_url) || '',
                thumbnail_url: (source.thumbnail && source.thumbnail.url) || '',
                image_url: (source.image && source.image.url) || '',
                fields: Array.isArray(source.fields)
                    ? source.fields.map(f => ({ name: f.name || '', value: f.value || '', inline: !!f.inline }))
                    : []
            });
        });
    }
    dhUpdatePreview();
}

function dhLoadExample() {
    dhClearAll();
    const content = $('dh-content');
    if (content) content.value = 'Bem-vindo ao **DiscoHook**!\n\nUse este editor para criar mensagens personalizadas com embeds ricos.';

    dhAddEmbed({
        title: 'O que é isso?',
        description: 'Editor visual de embeds do Discord. Crie mensagens estilizadas com cores, campos, imagens e envie via Webhook.',
        color: '#58b9ff',
        author_name: 'DiscoHook',
        footer_text: 'Criado com DiscoHook',
        fields: [
            { name: 'Content', value: 'Texto acima dos embeds', inline: true },
            { name: 'Embeds', value: 'Mensagens ricas formatadas', inline: true },
            { name: 'Webhook', value: 'Envie para qualquer canal', inline: false }
        ]
    });
    dhAddEmbed({
        title: 'Discord Bot',
        description: 'Bot complementar para formatação, reaction roles e restauração.',
        color: '#5865f2',
        fields: [
            { name: '/format', value: 'Formatação especial', inline: true },
            { name: '/reaction-role', value: 'Cargos por reação', inline: true }
        ]
    });

    dhUpdatePreview();
    const fb = $('dh-feedback');
    if (fb) { fb.className = ''; fb.textContent = ''; }
}

// =========================================================
// ABA: USUARIOS (painel reformulado)
// =========================================================
const UM_ACTIONS = {
    ativado: {
        title: 'Reativar conta',
        body: 'A conta volta a ter acesso ao painel. O cargo atual e qualquer pedido de reset pendente são encerrados.',
        danger: false
    },
    desativado: {
        title: 'Desativar conta',
        body: 'A conta perde o acesso ao painel e passa a ser encaminhada para a página que orienta abrir um ticket no Discord. O cargo atual é preservado e dá para reativar depois.',
        danger: true
    },
    banido: {
        title: 'Banir conta',
        body: 'A conta perde o acesso ao painel e passa a ver a página de banimento. Dá para reverter a qualquer momento pela opção Ativar.',
        danger: true
    },
    admin: {
        title: 'Tornar Admin',
        body: 'A conta passa a ter permissão de administração no painel. Se estava desativada ou banida, também é reativada.',
        danger: false
    },
    viewer: {
        title: 'Tornar Membro Sênior',
        body: 'A conta passa a ter somente leitura no painel: não altera usuários nem configurações. Se estava desativada ou banida, também é reativada.',
        danger: false
    },
    trocar_senha: {
        title: 'Forçar troca de senha',
        body: 'No próximo login, em vez de entrar no painel, o usuário verá uma página para definir uma nova senha. Cargo e status não mudam.',
        danger: false
    },
    aprovar_reset_senha: {
        title: 'Aprovar reset de senha',
        body: 'O usuário pediu recuperação por ter esquecido a senha atual. Ao aprovar, ele entra normalmente no próximo login e o sistema exige que defina uma nova senha. Cargo e status não mudam.',
        danger: false
    },
    negar_reset_senha: {
        title: 'Negar reset de senha',
        body: 'O usuário continua usando a senha atual. Use se o pedido não for legítimo.',
        danger: true
    }
};

function confirmAction(spec) {
    return new Promise(resolve => {
        const prev = $('um-modal');
        if (prev) prev.remove();

        const wrap = document.createElement('div');
        wrap.id = 'um-modal';
        wrap.className = 'um-modal-backdrop';
        wrap.innerHTML =
            '<div class="um-modal" role="dialog" aria-modal="true" aria-label="' + escapeHtml(spec.title) + '">' +
                '<h4 class="um-modal-title">' + escapeHtml(spec.title) + '</h4>' +
                '<p class="um-modal-body">' + escapeHtml(spec.body) + '</p>' +
                '<div class="um-modal-actions">' +
                    '<button type="button" class="um-btn" data-res="0">Cancelar</button>' +
                    '<button type="button" class="um-btn ' + (spec.danger ? 'um-btn-danger' : 'um-btn-primary') + '" data-res="1">' +
                        escapeHtml(spec.confirmText || 'Confirmar') + '</button>' +
                '</div>' +
            '</div>';
        document.body.appendChild(wrap);

        function done(v) {
            wrap.remove();
            document.removeEventListener('keydown', onKey);
            resolve(v);
        }
        function onKey(e) { if (e.key === 'Escape') done(false); }

        document.addEventListener('keydown', onKey);
        wrap.addEventListener('click', function (e) {
            const b = e.target.closest('[data-res]');
            if (b) { done(b.dataset.res === '1'); return; }
            if (e.target === wrap) done(false);
        });

        const cancel = wrap.querySelector('[data-res="0"]');
        if (cancel) cancel.focus();
    });
}

function confirmDeleteUser(username, role) {
    // Exclusão é definitiva. Além do aviso, exige digitar o nome da conta e a
    // própria senha: protege contra clique acidental e contra alguém usando uma
    // sessão esquecida em máquina compartilhada. O backend repete as duas
    // checagens — isto aqui é só a primeira barreira.
    return new Promise(resolve => {
        const prev = $('um-modal');
        if (prev) prev.remove();

        const wrap = document.createElement('div');
        wrap.id = 'um-modal';
        wrap.className = 'um-modal-backdrop';
        wrap.innerHTML =
            '<div class="um-modal um-modal-danger" role="dialog" aria-modal="true" aria-label="Excluir conta">' +
                '<h4 class="um-modal-title um-modal-title-danger">Excluir conta: ' + escapeHtml(username) + '</h4>' +
                '<p class="um-modal-body">' +
                    'O documento da conta será <strong>removido do banco</strong>. Não há como desfazer: ' +
                    'o usuário perde o acesso ao painel e precisará solicitar uma nova conta. ' +
                '</p>' +
                '<ul class="um-modal-list">' +
                    '<li>Cargo <strong>' + escapeHtml(role === 'admin' ? 'Admin' : 'Membro Sênior') + '</strong> e histórico de aprovações são perdidos.</li>' +
                    '<li>Pedidos de reset de senha pendentes são eliminados.</li>' +
                    '<li>Se você só quer tirar o acesso, use <strong>Desativar</strong> ou <strong>Banir</strong> — são reversíveis.</li>' +
                '</ul>' +
                '<label class="um-modal-label" for="um-del-name">Digite <code>' + escapeHtml(username) + '</code> para confirmar</label>' +
                '<input type="text" id="um-del-name" class="um-modal-input" autocomplete="off" spellcheck="false">' +
                '<label class="um-modal-label" for="um-del-pass">Sua senha de admin</label>' +
                '<input type="password" id="um-del-pass" class="um-modal-input" autocomplete="current-password">' +
                '<p class="um-modal-hint" id="um-del-err" role="alert"></p>' +
                '<div class="um-modal-actions">' +
                    '<button type="button" class="um-btn" data-res="0">Cancelar</button>' +
                    '<button type="button" class="um-btn um-btn-danger" data-res="1" disabled>Excluir definitivamente</button>' +
                '</div>' +
            '</div>';
        document.body.appendChild(wrap);

        const nameInput = wrap.querySelector('#um-del-name');
        const passInput = wrap.querySelector('#um-del-pass');
        const confirmBtn = wrap.querySelector('[data-res="1"]');
        const err = wrap.querySelector('#um-del-err');

        function done(v) {
            wrap.remove();
            document.removeEventListener('keydown', onKey);
            resolve(v);
        }
        function onKey(e) {
            if (e.key === 'Escape') done(null);
            if (e.key === 'Enter' && !confirmBtn.disabled) done({ username: nameInput.value, password: passInput.value });
        }
        function sync() {
            confirmBtn.disabled = nameInput.value.trim() !== username || !passInput.value;
            err.textContent = '';
        }

        document.addEventListener('keydown', onKey);
        nameInput.addEventListener('input', sync);
        passInput.addEventListener('input', sync);
        wrap.addEventListener('click', function (e) {
            const b = e.target.closest('[data-res]');
            if (b) {
                if (b.dataset.res === '1') done({ username: nameInput.value, password: passInput.value });
                else done(null);
                return;
            }
            if (e.target === wrap) done(null);
        });

        nameInput.focus();
    });
}

async function deleteUserAccount(username) {
    const fb = $('users-feedback');

    // O papel vem do cache já carregado: evita um GET extra só para montar o aviso.
    const cached = umUsersCache.find(u => u.username === username);
    const creds = await confirmDeleteUser(username, cached ? cached.role : 'viewer');
    if (!creds) return;

    if (fb) { fb.textContent = 'Excluindo...'; fb.className = 'feedback-text'; }

    try {
        const data = await api('auth/delete/' + encodeURIComponent(username), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: username, password: creds.password })
        });
        if (fb) {
            fb.textContent = (data && data.message) || (username + ' excluída.');
            fb.className = 'feedback-text success';
        }
    } catch (e) {
        if (fb) { fb.textContent = 'Erro: ' + e.message; fb.className = 'feedback-text error'; }
        return;
    }

    await loadActiveUsers();
    await loadPendingUsers();
}

function umBadge(kind, label) {
    return '<span class="um-badge" data-kind="' + kind + '">' + escapeHtml(label) + '</span>';
}

function umStatusInfo(status) {
    if (status === 'disabled') return { kind: 'disabled', label: 'Desativado' };
    if (status === 'banned') return { kind: 'banned', label: 'Banido' };
    if (status === 'pending') return { kind: 'pending', label: 'Pendente' };
    return { kind: 'active', label: 'Ativo' };
}

function renderUsersList() {
    const body = $('um-tbody');
    if (!body) return;

    const countFor = f => {
        if (f === 'all') return umUsersCache.length;
        if (f === 'reset') return umUsersCache.filter(u => u.password_reset_pending).length;
        return umUsersCache.filter(u => u.status === f).length;
    };

    document.querySelectorAll('[data-um-filter]').forEach(chip => {
        const n = chip.querySelector('.um-chip-n');
        if (n) n.textContent = countFor(chip.dataset.umFilter);
        chip.classList.toggle('is-active', chip.dataset.umFilter === umFilter);
    });

    const needle = umQuery;
    const shown = umUsersCache.filter(u => {
        if (umFilter === 'reset' && !u.password_reset_pending) return false;
        if (umFilter !== 'all' && umFilter !== 'reset' && u.status !== umFilter) return false;
        if (!needle) return true;
        return ((u.username || '') + ' ' + (u.discord || '')).toLowerCase().includes(needle);
    });

    if (shown.length === 0) {
        body.innerHTML = '<tr><td colspan="4" class="um-empty">Nenhum usuário corresponde ao filtro.</td></tr>';
        return;
    }

    body.innerHTML = shown.map(u => {
        const isSelf = u.username === currentUsername;
        const readonly = isSelf || currentUserRole === 'viewer';
        const st = umStatusInfo(u.status);

        const roleBadge = umBadge(u.role === 'admin' ? 'admin' : 'viewer', u.role === 'admin' ? 'Admin' : 'Membro Sênior');

        const btn = (act, text, on, tone, disabled) =>
            '<button type="button" class="um-btn-g' + (on ? ' is-on' : '') + '" data-um-act="' + act + '"' +
            (tone ? ' data-tone="' + tone + '"' : '') + (disabled ? ' disabled' : '') + '>' + escapeHtml(text) + '</button>';
        const seg = (label, inner) =>
            '<div class="um-seg" role="group" aria-label="' + escapeHtml(label) + '">' + inner + '</div>';

        const actions = readonly
            ? '<span class="um-note">' + (isSelf ? 'Sua conta — altere com outro admin.' : 'Somente leitura') + '</span>'
            : [
                seg('Cargo',
                    btn('admin', 'Admin', u.role === 'admin', 'primary') +
                    btn('viewer', 'Membro Sênior', u.role === 'viewer', 'warn')),
                seg('Acesso',
                    btn('ativado', 'Ativar', u.status === 'active', 'primary') +
                    btn('desativado', 'Desativar', u.status === 'disabled', 'warn') +
                    btn('banido', 'Banir', u.status === 'banned', 'danger')),
                seg('Senha',
                    (u.password_reset_pending
                        ? btn('aprovar_reset_senha', 'Aprovar reset', false, 'primary') +
                          btn('negar_reset_senha', 'Negar reset', false, 'danger')
                        : '') +
                    btn('trocar_senha', u.must_change_password ? 'Troca já liberada' : 'Forçar troca', false, 'primary', u.must_change_password)),
                // Fora do fluxo de cargos/status: exclusão é definitiva e por
                // isso pede confirmação digitada no modal. Nunca na própria conta.
                seg('Conta',
                    btn('excluir', 'Excluir conta', false, 'danger') +
                    (u.role === 'admin' ? '<span class="um-note">admin</span>' : ''))
              ].join('');

        const statusCell =
            '<span class="um-status-cell">' + umBadge(st.kind, st.label) +
            (u.password_reset_pending ? umBadge('reset', 'Reset solicitado') : '') +
            (u.must_change_password ? umBadge('pw', 'Troca pendente') : '') +
            '</span>';

        const initial = ((u.username || '?').slice(0, 2) || '?').toUpperCase();
        const meta = (u.discord ? escapeHtml(u.discord) : 'sem Discord') + ' · ' +
                     (u.created_at ? fmtDateTime(u.created_at) : '—');

        return '<tr class="um-row" data-username="' + escapeHtml(u.username) + '"' +
            (u.status !== 'active' ? ' style="opacity:0.7;"' : '') + '>' +
            '<td class="um-col-user">' +
                '<span class="um-avatar" data-role="' + (u.role === 'admin' ? 'admin' : 'viewer') + '">' + escapeHtml(initial) + '</span>' +
                '<div>' +
                    '<div class="um-name">' + escapeHtml(u.username) + (isSelf ? '<span class="um-you">você</span>' : '') + '</div>' +
                    '<div class="um-meta">' + meta + '</div>' +
                '</div>' +
            '</td>' +
            '<td class="um-col-role">' + roleBadge + '</td>' +
            '<td class="um-col-status">' + statusCell + '</td>' +
            '<td class="um-col-actions">' + actions + '</td>' +
        '</tr>';
    }).join('');
}

async function loadActiveUsers() {
    const container = $('active-users-list');
    if (!container) return;

    let data;
    try {
        data = await api('auth/users');
    } catch (e) {
        container.innerHTML = '<p class="error-text">Erro ao carregar: ' + escapeHtml(e.message) + '</p>';
        return;
    }

    const all = Array.isArray(data) ? data : [];
    if (all.length === 0) {
        umUsersCache = [];
        container.innerHTML = '<p class="um-empty-note">Nenhum usuário cadastrado.</p>';
        return;
    }

    const users = all.filter(u => u.status !== 'pending');
    if (users.length === 0) {
        umUsersCache = [];
        container.innerHTML = '<p class="um-empty-note">Nenhum usuário aprovado ainda.</p>';
        return;
    }

    umUsersCache = users;

    const counts = {
        active: users.filter(u => u.status === 'active').length,
        disabled: users.filter(u => u.status === 'disabled').length,
        banned: users.filter(u => u.status === 'banned').length
    };

    container.innerHTML =
        '<div class="um-panel">' +
            '<div class="um-toolbar">' +
                '<input type="search" id="um-search" class="um-search" placeholder="Buscar por nome ou Discord..." autocomplete="off" value="' + escapeHtml(umQuery) + '">' +
                '<div class="um-chips">' +
                    '<button type="button" class="um-chip" data-um-filter="all">Todos <span class="um-chip-n">0</span></button>' +
                    '<button type="button" class="um-chip" data-um-filter="active">Ativos <span class="um-chip-n">0</span></button>' +
                    '<button type="button" class="um-chip" data-um-filter="disabled">Desativados <span class="um-chip-n">0</span></button>' +
                    '<button type="button" class="um-chip" data-um-filter="banned">Banidos <span class="um-chip-n">0</span></button>' +
                    '<button type="button" class="um-chip" data-um-filter="reset">Reset pedido <span class="um-chip-n">0</span></button>' +
                '</div>' +
            '</div>' +
            '<div class="um-table-wrap">' +
                '<table class="um-table">' +
                    '<thead><tr>' +
                        '<th>Usuário</th><th>Cargo</th><th>Status</th>' +
                        '<th style="width:1%;white-space:nowrap;">Ações</th>' +
                    '</tr></thead>' +
                    '<tbody id="um-tbody"></tbody>' +
                '</table>' +
            '</div>' +
            '<p class="um-foot">Total: ' + users.length + ' · ' + counts.active + ' ativo(s) · ' +
                counts.disabled + ' desativado(s) · ' + counts.banned + ' banido(s)</p>' +
            '<p class="um-hint">' +
                '<strong>Cargo</strong> define permissão (Admin edita tudo, Membro Sênior é somente leitura). ' +
                '<strong>Acesso</strong> bloqueia ou restaura o login: desativado leva a aviso para abrir ticket, banido leva à página de banimento. ' +
                '<strong>Senha</strong> é independente: "Forçar troca" ou "Aprovar reset" liberam o usuário para definir uma nova senha no próximo login. ' +
                '<strong>Reset solicitado</strong> aparece quando o titular usa "Esqueci minha senha" na tela de login; ' +
                'ao aprovar, ele entra normalmente com a senha antiga e o sistema exige uma nova. ' +
                '<strong>Excluir conta</strong> apaga o registro de forma definitiva e exige a sua senha; ' +
                'prefira desativar ou banir quando o objetivo for apenas tirar o acesso. ' +
                'Não existe redefinição automática por e-mail.' +
            '</p>' +
        '</div>';

    if (!umBound) {
        umBound = true;

        container.addEventListener('input', function (e) {
            if (e.target && e.target.id === 'um-search') {
                umQuery = e.target.value.trim().toLowerCase();
                renderUsersList();
            }
        });

        container.addEventListener('click', function (e) {
            const chip = e.target.closest('[data-um-filter]');
            if (chip) {
                umFilter = chip.dataset.umFilter;
                renderUsersList();
                return;
            }

            const actBtn = e.target.closest('[data-um-act]');
            if (actBtn && !actBtn.disabled) {
                const row = actBtn.closest('.um-row');
                if (row) changeUserAction(row.dataset.username, actBtn.dataset.umAct);
                return;
            }

            const pendingBtn = e.target.closest('[data-um-pending]');
            if (pendingBtn) {
                const card = pendingBtn.closest('[data-um-username]');
                if (card) {
                    const username = card.dataset.umUsername;
                    if (pendingBtn.dataset.umPending === 'approve') approvePendingUser(username);
                    else rejectPendingUser(username);
                }
            }
        });
    }

    renderUsersList();
}

async function loadPendingUsers() {
    const container = $('pending-users-list');
    if (!container) return;

    let data;
    try {
        data = await api('auth/users');
    } catch (e) {
        container.innerHTML = '<p class="error-text">Erro: ' + escapeHtml(e.message) + '</p>';
        return;
    }

    const pending = (Array.isArray(data) ? data : []).filter(u => u.status === 'pending');

    if (pending.length === 0) {
        container.innerHTML = '<p class="um-empty-note">Nenhuma solicitação pendente.</p>';
        return;
    }

    container.innerHTML = pending.map(u =>
        '<div class="um-pending-card" data-um-username="' + escapeHtml(u.username) + '">' +
            '<div class="um-pending-info">' +
                '<strong>' + escapeHtml(u.username) + '</strong>' +
                (u.discord ? '<span class="um-pending-discord"> · ' + escapeHtml(u.discord) + '</span>' : '') +
                '<div class="um-pending-date">Criado: ' + fmtDateTime(u.created_at) + '</div>' +
            '</div>' +
            '<div class="um-pending-actions">' +
                '<button type="button" class="um-btn um-btn-primary" data-um-pending="approve">Aprovar</button>' +
                '<button type="button" class="um-btn um-btn-danger" data-um-pending="reject">Rejeitar</button>' +
            '</div>' +
        '</div>'
    ).join('');
}

async function changeUserAction(username, newAction) {
    const fb = $('users-feedback');
    if (!fb) return;

    // Exclusão não passa por 'auth/role' (que só altera cargo/status) e tem
    // confirmação própria, com senha do admin.
    if (newAction === 'excluir') { await deleteUserAccount(username); return; }

    const spec = UM_ACTIONS[newAction];
    if (!spec) { await loadActiveUsers(); return; }

    const ok = await confirmAction({
        title: spec.title + ': ' + username,
        body: spec.body,
        confirmText: spec.danger ? 'Sim, confirmar' : 'Confirmar',
        danger: spec.danger
    });
    if (!ok) return;

    fb.textContent = 'Aplicando...';
    fb.className = 'feedback-text';

    try {
        const data = await api('auth/role', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: username, role: newAction })
        });

        fb.textContent = (data && data.message) || 'OK';
        fb.className = 'feedback-text success';
    } catch (e) {
        fb.textContent = 'Erro: ' + e.message;
        fb.className = 'feedback-text error';
    }

    await loadActiveUsers();
}

async function approvePendingUser(username) {
    const fb = $('users-feedback');
    try {
        await api('auth/approve/' + encodeURIComponent(username), { method: 'POST' });
        if (fb) { fb.textContent = username + ' aprovado.'; fb.className = 'feedback-text success'; }
    } catch (e) {
        if (fb) { fb.textContent = 'Erro: ' + e.message; fb.className = 'feedback-text error'; }
        return;
    }
    await loadPendingUsers();
    await loadActiveUsers();
}

async function rejectPendingUser(username) {
    if (!confirm('Rejeitar a solicitação de ' + username + '?')) return;
    const fb = $('users-feedback');
    try {
        await api('auth/reject/' + encodeURIComponent(username), { method: 'POST' });
        if (fb) { fb.textContent = username + ' rejeitado.'; fb.className = 'feedback-text success'; }
    } catch (e) {
        if (fb) { fb.textContent = 'Erro: ' + e.message; fb.className = 'feedback-text error'; }
        return;
    }
    await loadPendingUsers();
}

window.changeUserAction = changeUserAction;
window.changeUserRole = changeUserAction;
window.approvePendingUser = approvePendingUser;
window.rejectPendingUser = rejectPendingUser;
window.loadActiveUsers = loadActiveUsers;
window.loadPendingUsers = loadPendingUsers;

// =========================================================
// NAVEGACAO ENTRE ABAS
// =========================================================
const SECTION_KEY = 'activeAdminSection';

function resolveInitialSection() {
    let saved = null;
    try {
        // 'activeSection' era a chave da versao quebrada; migra e limpa.
        const legacy = localStorage.getItem('activeSection');
        if (legacy && !localStorage.getItem(SECTION_KEY)) {
            localStorage.setItem(SECTION_KEY, legacy);
        }
        localStorage.removeItem('activeSection');
        saved = localStorage.getItem(SECTION_KEY);
    } catch (e) { /* localStorage indisponivel */ }

    if (saved && document.getElementById(saved)) return saved;
    const first = document.querySelector('.admin-nav .nav-link[data-section]');
    return first ? first.dataset.section : 'admin-geral';
}

function setActiveAdminSection(sectionId) {
    if (!sectionId || !document.getElementById(sectionId)) return false;

    document.querySelectorAll('.admin-section').forEach(s => s.classList.remove('active-section'));
    document.querySelectorAll('.admin-nav .nav-link').forEach(l => l.classList.remove('active-nav-link'));

    document.getElementById(sectionId).classList.add('active-section');

    const link = document.querySelector('.admin-nav .nav-link[data-section="' + sectionId + '"]');
    if (link) link.classList.add('active-nav-link');

    const wrapper = document.querySelector('.admin-sections-wrapper');
    if (wrapper) wrapper.classList.toggle('allow-scroll', sectionId === 'admin-discohook');

    try { localStorage.setItem(SECTION_KEY, sectionId); } catch (e) { /* ignora */ }
    currentActiveSectionId = sectionId;
    return true;
}

async function loadDataForCurrentTab() {
    ['settings-feedback', 'actions-feedback', 'geral-feedback', 'db-feedback',
     'watchlist-add-feedback', 'watchlist-list-feedback', 'radar-feedback', 'users-feedback']
        .forEach(id => {
            const el = $(id);
            if (el) { el.textContent = ''; el.classList.remove('error', 'success'); }
        });

    let status = { maintenance_mode: false, version: '?' };
    try {
        const res = await fetch('/api/status', { credentials: 'include' });
        if (res.ok) status = await res.json();
    } catch (e) { /* segue com o fallback */ }
    updateStatus(status);

    switch (currentActiveSectionId) {
        case 'admin-geral':
            break;

        case 'admin-diagnostico':
            try {
                updateDiagnostics(await api('diagnostics'));
            } catch (e) {
                const box = $('recent-logs-box');
                if (box) box.textContent = 'Erro ao carregar logs: ' + e.message;
            }
            break;

        case 'admin-configuracoes':
            try {
                const [settings, discordData] = await Promise.all([
                    api('settings'),
                    api('discord_data')
                ]);
                populateDiscordDropdowns(discordData);
                populateSettingsForm(settings);
            } catch (e) { /* feedback ja exibido por api() */ }
            break;

        case 'admin-db':
            try {
                updateDbViewer(await api('db_viewer'));
            } catch (e) { /* feedback ja exibido por api() */ }
            break;

        case 'admin-watchlist':
            await loadWatchlist();
            break;

        case 'admin-radar':
            await loadTrainingStatus();
            await loadRadarDossier();
            break;

        case 'admin-analytics':
            await loadAnalyticsData();
            break;

        case 'admin-acoes':
            break;

        case 'admin-discohook':
            break;

        case 'admin-users':
            await loadPendingUsers();
            await loadActiveUsers();
            break;
    }
}

// =========================================================
// AUTENTICACAO / RESTRICOES DE CARGO
// =========================================================
async function checkUserAuth() {
    try {
        const res = await fetch('/api/admin/auth/me', { credentials: 'include' });
        if (res.ok) {
            const data = await res.json();
            currentUserRole = data.role || 'admin';
            currentUsername = data.username || '';
        }
    } catch (e) { /* mantem o padrao */ }

    const badge = $('user-role-badge');
    if (badge) {
        const isViewer = currentUserRole === 'viewer';
        badge.textContent = isViewer ? 'Membro Sênior' : 'Admin';
        badge.style.color = isViewer ? 'var(--neon-orange)' : 'var(--neon-cyan)';
        badge.style.borderColor = isViewer ? 'rgba(255,165,0,0.3)' : 'rgba(0,255,249,0.3)';
        badge.style.background = isViewer ? 'rgba(255,165,0,0.1)' : 'rgba(0,255,249,0.1)';
    }

    if (currentUserRole !== 'viewer') return;

    document.querySelectorAll('[data-viewer-hide]').forEach(el => { el.style.display = 'none'; });
    document.querySelectorAll('[data-admin-only]').forEach(el => { el.style.display = 'none'; });

    document.querySelectorAll('.control-btn, .btn-admin, [data-write-only]').forEach(el => {
        if (el.classList.contains('logout-btn')) return;
        el.disabled = true;
        el.style.opacity = '0.4';
        el.style.pointerEvents = 'none';
    });

    document.querySelectorAll('#admin-panel-container form, #admin-body form').forEach(f => {
        f.querySelectorAll('button, input, select, textarea').forEach(el => {
            el.disabled = true;
            el.style.opacity = '0.5';
        });
    });
}

// =========================================================
// BINDINGS GERAIS
// =========================================================
function bindGeneralControls() {
    const toggleBtn = $('toggle-maintenance-btn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', async () => {
            const original = toggleBtn.textContent;
            toggleBtn.disabled = true;
            toggleBtn.textContent = 'Aguarde...';
            try {
                const r = await fetch('/admin/toggle_maintenance', {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'X-CSRF-Token': getCsrfToken() }
                });
                if (!r.ok) throw new Error('HTTP ' + r.status);
                const status = await fetch('/api/status', { credentials: 'include' })
                    .then(res => res.ok ? res.json() : {})
                    .catch(() => ({}));
                updateStatus(status);
                displayFeedback($('geral-feedback'),
                    status.maintenance_mode ? 'Modo manutenção ATIVADO.' : 'Modo manutenção DESATIVADO.');
            } catch (e) {
                displayFeedback($('geral-feedback'), 'Erro: ' + (e.message || 'falha na comunicação.'), true);
            } finally {
                toggleBtn.disabled = false;
                toggleBtn.textContent = original;
            }
        });
    }

    const testBtn = $('send-test-embed-btn');
    if (testBtn) {
        testBtn.addEventListener('click', async () => {
            const original = testBtn.textContent;
            testBtn.disabled = true;
            testBtn.textContent = 'Enviando...';
            try {
                const r = await fetch('/admin/send_test_embed', {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'X-CSRF-Token': getCsrfToken() }
                });
                if (!r.ok) throw new Error('HTTP ' + r.status);
                displayFeedback($('geral-feedback'), 'Mensagem de teste enviada!');
            } catch (e) {
                displayFeedback($('geral-feedback'), 'Erro: ' + (e.message || 'falha na comunicação.'), true);
            } finally {
                testBtn.disabled = false;
                testBtn.textContent = original;
            }
        });
    }

    const settingsForm = $('settings-form');
    if (settingsForm) {
        settingsForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const settings = {};
            const feedback = $('settings-feedback');

            new FormData(settingsForm).forEach((value, key) => {
                if (key === 'auto_add_watchlist_enabled') {
                    settings[key] = value === 'true';
                } else if (key.indexOf('_id') !== -1 || key.indexOf('channel_id') !== -1) {
                    settings[key] = /^\d+$/.test(value) ? value : 0;
                } else if (/^\d+$/.test(value) && key.indexOf('message') === -1) {
                    settings[key] = value === '' ? null : parseInt(value, 10);
                } else {
                    settings[key] = value;
                }
            });

            displayFeedback(feedback, 'Salvando...', false, 0);
            try {
                const response = await api('settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
                displayFeedback(feedback, (response && response.message) || 'Configurações salvas.');
            } catch (err) {
                displayFeedback(feedback, 'Erro de conexão ao salvar.', true);
            }
        });
    }

    document.querySelectorAll('.action-btn').forEach(button => {
        button.addEventListener('click', async () => {
            const original = button.textContent;
            const action = button.dataset.action;
            let payload;
            try {
                payload = JSON.parse(button.dataset.payload || '{}');
            } catch (e) {
                payload = {};
            }

            button.disabled = true;
            button.textContent = 'Executando...';

            if (action === 'export_clan_json' || action === 'export_players_csv') {
                try {
                    const endpoint = action === 'export_clan_json' ? 'export/clan' : 'export/players';
                    const resp = await fetch('/api/admin/' + endpoint, { credentials: 'include' });
                    const data = await resp.json();
                    if (data.error || (resp.status !== 200 && data.status === 'error')) {
                        displayFeedback($('actions-feedback'), data.error || data.message || 'Erro na exportação.', true);
                        return;
                    }
                    const isCsv = action === 'export_players_csv';
                    const payloadText = isCsv ? (data.data || data.csv || '') : JSON.stringify(data.data || data, null, 2);
                    const blob = new Blob([payloadText], { type: isCsv ? 'text/csv' : 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'clashgenius_admin_export.' + (isCsv ? 'csv' : 'json');
                    a.click();
                    URL.revokeObjectURL(url);
                    displayFeedback($('actions-feedback'), 'Exportação concluída!');
                } catch (e) {
                    displayFeedback($('actions-feedback'), 'Erro na exportação.', true);
                } finally {
                    button.disabled = false;
                    button.textContent = original;
                }
                return;
            }

            try {
                const response = await api('actions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: action, payload: payload })
                });
                displayFeedback($('actions-feedback'), (response && response.message) || ("Ação '" + action + "' concluída."));
            } catch (e) {
                displayFeedback($('actions-feedback'), 'Erro de conexão ao executar ação.', true);
            } finally {
                button.disabled = false;
                button.textContent = original;
            }
        });
    });

    const sendAnnouncementBtn = $('send-announcement-btn');
    if (sendAnnouncementBtn) {
        sendAnnouncementBtn.addEventListener('click', async () => {
            const channelEl = $('announcement-channel-id');
            const messageEl = $('announcement-message');
            const channelId = channelEl ? channelEl.value.trim() : '';
            const message = messageEl ? messageEl.value : '';

            if (!/^\d+$/.test(channelId) || !message) {
                displayFeedback($('actions-feedback'), 'Preencha um ID numérico e a mensagem.', true);
                return;
            }

            const original = sendAnnouncementBtn.textContent;
            sendAnnouncementBtn.disabled = true;
            sendAnnouncementBtn.textContent = 'Enviando...';

            try {
                const response = await api('actions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        action: 'send_announcement',
                        payload: { channel_id: channelId, message: message }
                    })
                });
                const ok = response && (response.status === 'success' || !response.error);
                displayFeedback($('actions-feedback'),
                    (response && response.message) || (ok ? 'Enviado.' : 'Erro ao enviar.'), !ok);
                if (ok && messageEl) messageEl.value = '';
            } catch (e) {
                displayFeedback($('actions-feedback'), 'Erro de conexão ao enviar anúncio.', true);
            } finally {
                sendAnnouncementBtn.disabled = false;
                sendAnnouncementBtn.textContent = original;
            }
        });
    }

    const addWatchlistForm = $('admin-add-watchlist-form');
    if (addWatchlistForm) addWatchlistForm.addEventListener('submit', handleAddWatchlist);

    const watchlistBody = document.querySelector('#admin-watchlist-tbody');
    if (watchlistBody) watchlistBody.addEventListener('click', handleRemoveWatchlist);

    const filterName = $('watchlist-filter-name');
    if (filterName) filterName.addEventListener('input', applyWatchlistFilter);
    const filterTag = $('watchlist-filter-tag');
    if (filterTag) filterTag.addEventListener('input', applyWatchlistFilter);

    // Vereditos do Radar Pericial por delegacao (sem injetar ids em onclick).
    const dossier = $('radar-dossier-container');
    if (dossier) {
        dossier.addEventListener('click', function (e) {
            const judgeBtn = e.target.closest('[data-judge]');
            if (!judgeBtn) return;
            const card = judgeBtn.closest('[data-pair-id]');
            if (card) judgeSmurf(card.dataset.pairId, judgeBtn.dataset.judge);
        });
    }
}

// =========================================================
// BOOT
// =========================================================
async function initAdminPanel() {
    if (adminReady) return;
    adminReady = true;

    await checkUserAuth();

    currentActiveSectionId = resolveInitialSection();
    setActiveAdminSection(currentActiveSectionId);

    document.querySelectorAll('.admin-nav .nav-link[data-section]').forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            const sectionId = link.dataset.section;
            if (!sectionId || sectionId === currentActiveSectionId) return;
            setActiveAdminSection(sectionId);
            loadDataForCurrentTab();
        });
    });

    bindGeneralControls();
    dhInitEditor();
    initTooltips();
    await loadDataForCurrentTab();

    // Radar de inatividade (sino) — somente no painel admin.
    if (window.location.pathname.indexOf('/admin') !== -1) {
        window.fetchRadarInactivityData();
        setInterval(window.fetchRadarInactivityData, 30 * 60 * 1000);
    }
}

// =========================================================
// BOOT
// =========================================================
document.addEventListener('DOMContentLoaded', function () {
    if (window.location.pathname.indexOf('/admin') !== -1) {
        initAdminPanel();
    }
});

})();