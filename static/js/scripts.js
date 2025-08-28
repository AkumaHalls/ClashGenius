document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = '';
    const DEFAULT_BADGE_URL = '/static/images/default_badge.png';

    // --- ELEMENTOS DO DOM ---
    const loadingOverlayEl = document.getElementById('loading-overlay');
    const backgroundMusicEl = document.getElementById('background-music');
    const muteButtonEl = document.getElementById('mute-button');

    const clanNameHeaderEl = document.getElementById('clanNameHeader');
    const clanBadgeHeaderEl = document.getElementById('clanBadgeHeader');
    const clanNameEl = document.getElementById('clanName');
    const clanTagEl = document.getElementById('clanTag');
    const clanLevelEl = document.getElementById('clanLevel');
    const clanPointsEl = document.getElementById('clanPoints');
    const clanMemberCountEl = document.getElementById('clanMemberCount');
    const clanWarWinsEl = document.getElementById('clanWarWins');
    const clanLocationEl = document.getElementById('clanLocation');
    const clanTypeEl = document.getElementById('clanType');
    const clanDescriptionEl = document.getElementById('clanDescription');
    const clanBadgeEl = document.getElementById('clanBadge');
    const clanCapitalPointsEl = document.getElementById('clanCapitalPoints');
    const clanCapitalLeagueEl = document.getElementById('clanCapitalLeague');
    const clanCapitalDistrictsEl = document.getElementById('clanCapitalDistricts');

    const warDetailClanBadgeEl = document.getElementById('warDetailClanBadge');
    const warDetailOurClanNameEl = document.getElementById('warDetailOurClanName');
    const warDetailOpponentNameEl = document.getElementById('warDetailOpponentName');
    const warDetailOpponentBadgeEl = document.getElementById('warDetailOpponentBadge');
    const warDetailTimeKeyEl = document.getElementById('warDetailTimeKey');
    const warDetailTimeValueEl = document.getElementById('warDetailTimeValue');
    const warDetailTimeRemainingEl = document.getElementById('warDetailTimeRemaining');
    const warDetailStateEl = document.getElementById('warDetailState');
    const noWarDetailMessageEl = document.getElementById('noWarDetailMessage');
    const warTabButtons = document.querySelectorAll('.war-tab-button');
    const warTabContents = document.querySelectorAll('.war-tab-content');
    const statsOurClanNameEl = document.getElementById('statsOurClanName');
    const statsOurStarsEl = document.getElementById('statsOurStars');
    const statsOurDestructionEl = document.getElementById('statsOurDestruction');
    const statsOurAttacksUsedEl = document.getElementById('statsOurAttacksUsed');
    const statsOpponentNameEl = document.getElementById('statsOpponentName');
    const statsOpponentStarsEl = document.getElementById('statsOpponentStars');
    const statsOpponentDestructionEl = document.getElementById('statsOpponentDestruction');
    const statsOpponentAttacksUsedEl = document.getElementById('statsOpponentAttacksUsed');
    const statsOurAvgStarsEl = document.getElementById('statsOurAvgStars');
    const statsOurAvgDurationEl = document.getElementById('statsOurAvgDuration');
    const statsOpponentAvgStarsEl = document.getElementById('statsOpponentAvgStars');
    const statsOpponentAvgDurationEl = document.getElementById('statsOpponentAvgDuration');
    const statsOurStars3El = document.getElementById('statsOurStars3');
    const statsOurStars2El = document.getElementById('statsOurStars2');
    const statsOurStars1El = document.getElementById('statsOurStars1');
    const statsOurStars0El = document.getElementById('statsOurStars0');
    const statsOpponentStars3El = document.getElementById('statsOpponentStars3');
    const statsOpponentStars2El = document.getElementById('statsOpponentStars2');
    const statsOpponentStars1El = document.getElementById('statsOpponentStars1');
    const statsOpponentStars0El = document.getElementById('statsOpponentStars0');
    const warTotalAttacksCountEl = document.getElementById('warTotalAttacksCount');
    const warEventsTableBodyEl = document.getElementById('warEventsTableBody');
    const warOurTeamNameEl = document.getElementById('warOurTeamName');
    const warOurTeamMembersEl = document.getElementById('warOurTeamMembers');
    const warOpponentTeamNameEl = document.getElementById('warOpponentTeamName');
    const warOpponentTeamMembersEl = document.getElementById('warOpponentTeamMembers');

    const attacksRemainingTitleEl = document.getElementById('attacksRemainingTitle');
    const attacksRemainingClanNameEl = document.getElementById('attacksRemainingClanName');
    const attacksRemainingListEl = document.getElementById('attacksRemainingList');
    const noMissedAttacksMessageEl = document.getElementById('noMissedAttacksMessage');

    const cwlStatusTextEl = document.getElementById('cwlStatusText');
    const cwlActiveInfoEl = document.getElementById('cwlActiveInfo');
    const cwlSeasonEl = document.getElementById('cwlSeason');
    const cwlGroupStateEl = document.getElementById('cwlGroupState');
    const cwlGroupClansEl = document.getElementById('cwlGroupClans');
    const cwlRoundsInfoEl = document.getElementById('cwlRoundsInfo');
    const noCwlMessageEl = document.getElementById('noCwlMessage');

    const warLogLimitEl = document.getElementById('warLogLimit');
    const warLogTableBodyEl = document.getElementById('warLogTableBody');
    const noWarLogMessageEl = document.getElementById('noWarLogMessage');

    const membersClanNameEl = document.getElementById('membersClanName');
    const membersTableBodyEl = document.getElementById('membersTableBody');
    const filterNameInput = document.getElementById('filterName');
    const filterTHInput = document.getElementById('filterTH');
    const filterLeagueInput = document.getElementById('filterLeague');
    const filterTrophiesInput = document.getElementById('filterTrophies');
    const filterRoleInput = document.getElementById('filterRole');

    const botVersionEl = document.getElementById('botVersion');
    const lastUpdatedEl = document.getElementById('lastUpdated');

    const navLinks = document.querySelectorAll('.nav-link');
    const contentSections = document.querySelectorAll('.content-section');
    let isFirstLoad = true;

    const historicWarModal = document.getElementById('historicWarModal');
    const historicWarDetailContent = document.getElementById('historicWarDetailContent');
    const closeModalButton = document.querySelector('.modal .close-button');

    if (backgroundMusicEl && muteButtonEl) {
        backgroundMusicEl.volume = 0.2;
        const playMusic = async () => {
            try {
                await backgroundMusicEl.play();
                document.body.removeEventListener('click', playMusic);
            } catch (err) {
                console.log('Autoplay da música bloqueado pelo navegador.');
            }
        };
        document.body.addEventListener('click', playMusic, { once: true });

        muteButtonEl.addEventListener('click', () => {
            backgroundMusicEl.muted = !backgroundMusicEl.muted;
            muteButtonEl.textContent = backgroundMusicEl.muted ? '🔇' : '🔊';
            localStorage.setItem('musicMuted', backgroundMusicEl.muted.toString());
        });

        if (localStorage.getItem('musicMuted') === 'true') {
            backgroundMusicEl.muted = true;
            muteButtonEl.textContent = '🔇';
        }
    }

    async function fetchData(endpoint, options = {}) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/${endpoint}`, options);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: `Falha: ${response.status}` }));
                console.error(`HTTP error! status: ${response.status} for ${endpoint}`, errorData);
                return { error: errorData.error || `Falha ao carregar ${endpoint}.` };
            }
            return response.status === 204 ? { success: true } : await response.json();
        } catch (error) {
            console.error(`Could not fetch data from ${endpoint}:`, error);
            return { error: `Erro de conexão ao buscar ${endpoint}.` };
        }
    }

    function updateLastUpdated() {
        setText(lastUpdatedEl, `Última atualização: ${new Date().toLocaleTimeString()}`);
    }

    function setText(element, text, defaultValue = '-') {
        if (element) element.textContent = text ?? defaultValue;
    }

    function setHtml(element, htmlContent) {
        if (element) element.innerHTML = htmlContent;
    }

    function setBadge(element, url) {
        if (element) element.src = url || DEFAULT_BADGE_URL;
    }

    const initialSectionId = localStorage.getItem('activeSection') || navLinks[0]?.dataset.section || 'clan-info-nav';
    
    function setActiveSection(newSectionId) {
        const newIndex = Array.from(navLinks).findIndex(link => link.dataset.section === newSectionId);
        if (newIndex === -1) return;

        contentSections.forEach(section => section.classList.remove('active-section'));
        navLinks.forEach(link => link.classList.remove('active-nav-link'));

        document.getElementById(newSectionId)?.classList.add('active-section');
        navLinks[newIndex]?.classList.add('active-nav-link');
        
        localStorage.setItem('activeSection', newSectionId);
    }

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            setActiveSection(link.dataset.section);
        });
    });

    function populateClanInfo(data) {
        if (data.error) {
            setText(clanNameHeaderEl, "Erro");
            setText(clanNameEl, data.error);
            return;
        }
        setText(clanNameHeaderEl, data.name);
        setText(clanNameEl, data.name);
        setText(clanTagEl, data.tag);
        setText(clanLevelEl, data.level);
        setText(clanPointsEl, data.points);
        setText(clanMemberCountEl, data.member_count);
        setText(clanWarWinsEl, data.war_wins);
        setText(clanLocationEl, data.location);
        setText(clanTypeEl, data.type);
        setText(clanDescriptionEl, data.description, 'Sem descrição.');
        setText(botVersionEl, data.version, '?');
        setBadge(clanBadgeHeaderEl, data.badge_url);
        setBadge(clanBadgeEl, data.badge_url);
        setText(clanCapitalPointsEl, data.capital_points);
        setText(clanCapitalLeagueEl, data.capital_league);
        setHtml(clanCapitalDistrictsEl, data.capital_districts?.length ? 
            data.capital_districts.map(d => `<p><strong>${d.name || 'N/A'}:</strong> Nv ${d.level || '?'}</p>`).join('') :
            '<p>Nenhum distrito encontrado.</p>');
    }

    warTabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const parentSection = button.closest('.content-section');
            if (!parentSection) return;
            parentSection.querySelectorAll('.war-tab-button').forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            const tabId = button.dataset.tab;
            parentSection.querySelectorAll('.war-tab-content').forEach(content => {
                content.classList.toggle('active', content.id === tabId);
            });
        });
    });

    function createStarString(stars) {
        return '⭐'.repeat(stars) + '⚫'.repeat(Math.max(0, 3 - stars));
    }

    function populateWarDetails(data, container, isModal = false) {
        const prefix = isModal ? 'historic-' : '';
        const war = data.war_data;

        const setElementText = (id, text) => setText(container.querySelector(`#${prefix}${id}`), text);
        const setElementBadge = (id, url) => setBadge(container.querySelector(`#${prefix}${id}`), url);

        if (data.error || !war) {
            container.querySelector('.message-box').style.display = 'block';
            setText(container.querySelector('.message-box'), data.error || "Nenhuma guerra para detalhar.");
            container.querySelector('.war-header').style.display = 'none';
            container.querySelector('.war-tabs').style.display = 'none';
            container.querySelectorAll('.war-tab-content').forEach(tab => tab.style.display = 'none');
            return;
        }

        container.querySelector('.message-box').style.display = 'none';
        container.querySelector('.war-header').style.display = 'flex';
        container.querySelector('.war-tabs').style.display = 'flex';

        setElementText('warDetailOurClanName', war.clan_name);
        setElementText('warDetailOpponentName', war.opponent_name);
        setElementBadge('warDetailClanBadge', war.clan_badge_url);
        setElementBadge('warDetailOpponentBadge', war.opponent_badge_url);
        setElementText('warDetailTimeKey', war.time_key);
        setElementText('warDetailTimeValue', war.time_value);
        setElementText('warDetailTimeRemaining', war.time_remaining);
        const stateEl = container.querySelector(`#${prefix}warDetailState`);
        if(stateEl) {
            setText(stateEl, war.state_description);
            stateEl.className = `war-state ${(war.status || '').toLowerCase()}`;
        }

        setElementText('statsOurClanName', war.clan_name);
        setElementText('statsOurStars', war.clan_stars);
        setElementText('statsOurDestruction', war.clan_destruction?.replace('%', ''));
        setElementText('statsOurAttacksUsed', `${war.clan_attacks_used}/${war.team_size * war.attacks_per_member}`);
        setElementText('statsOpponentName', war.opponent_name);
        setElementText('statsOpponentStars', war.opponent_stars);
        setElementText('statsOpponentDestruction', war.opponent_destruction?.replace('%', ''));
        setElementText('statsOpponentAttacksUsed', `${war.opponent_attacks_used}/${war.team_size * war.attacks_per_member}`);
        setElementText('statsOurAvgStars', war.clan_avg_stars);
        setElementText('statsOurAvgDuration', war.clan_avg_duration);
        setElementText('statsOpponentAvgStars', war.opponent_avg_stars);
        setElementText('statsOpponentAvgDuration', war.opponent_avg_duration);
        
        for (let i = 0; i <= 3; i++) {
            setElementText(`statsOurStars${i}`, war.clan_star_distribution[i.toString()]);
            setElementText(`statsOpponentStars${i}`, war.opponent_star_distribution[i.toString()]);
        }

        setElementText('warTotalAttacksCount', data.all_attacks.length);
        const eventsTableBody = container.querySelector(`#${prefix}warEventsTableBody`);
        setHtml(eventsTableBody, data.all_attacks.map(att => `
            <tr>
                <td>${att.order}</td>
                <td>${att.attacker_name} (CV${att.attacker_townhall})</td>
                <td><span class="attack-stars">${createStarString(att.stars)}</span> ${att.destruction}%</td>
                <td>${att.defender_name} (CV${att.defender_townhall})</td>
                <td>${att.duration}</td>
            </tr>
        `).join('') || '<tr><td colspan="5">Nenhum ataque registrado.</td></tr>');

        const populateTeamTabData = (teamMembersData, teamNameKey) => {
            const teamContainer = container.querySelector(`#${prefix}war${teamNameKey}Members`);
            setElementText(`war${teamNameKey}Name`, war[`${teamNameKey === 'OurTeam' ? 'clan' : 'opponent'}_name`]);
            setHtml(teamContainer, teamMembersData.map(member => `
                <div class="team-member-card">
                    <h4><img src="/static/images/townhall${member.townhall}.png" alt="CV${member.townhall}" onerror="this.style.display='none'"/> ${member.map_position}. ${member.name} (CV${member.townhall})</h4>
                    <p>Ataques: ${member.attacks_used}/${war.attacks_per_member}</p>
                    <h5>Ataques Feitos:</h5>
                    <ul class="member-attack-list">${member.attacks_made.length ? member.attacks_made.map(atk => `<li>${createStarString(atk.stars)} ${atk.destruction}% vs ${atk.defender_name} (CV${atk.defender_townhall})</li>`).join('') : '<li>Nenhum ataque feito.</li>'}</ul>
                    <h5>Defesas Recebidas:</h5>
                    <ul class="member-defense-list">${member.defenses_received.length ? member.defenses_received.map(def => `<li>${createStarString(def.stars)} ${def.destruction}% por ${def.attacker_name} (CV${def.attacker_townhall})</li>`).join('') : '<li>Nenhuma defesa registrada.</li>'}</ul>
                </div>
            `).join('') || '<p>Nenhum membro nesta equipe para a guerra.</p>');
        };

        populateTeamTabData(data.our_clan_members_in_war, "OurTeam");
        populateTeamTabData(data.opponent_clan_members_in_war, "OpponentTeam");
    }

    function populateMissedAttacksHistory(data) {
        setText(attacksRemainingClanNameEl, data.clan_name);
        const hasMissedAttacks = data.missed_attacks && data.missed_attacks.length > 0;
        noMissedAttacksMessageEl.style.display = hasMissedAttacks ? 'none' : 'block';
        
        if (hasMissedAttacks) {
            setHtml(attacksRemainingListEl, data.missed_attacks.map(m => 
                `<p><strong>${m.name}</strong> (CV${m.town_hall}) - <strong>${m.attacks_left}</strong> atk restante(s) na guerra de <strong>${m.war_date}</strong></p>`
            ).join(''));
        } else {
            setText(noMissedAttacksMessageEl, data.error || "Nenhuma pendência de ataque encontrada.");
            setHtml(attacksRemainingListEl, '');
        }
    }

    function populateCwlInfo(data) {
        const isInCwl = data.status === "InCwl";
        noCwlMessageEl.style.display = isInCwl ? 'none' : 'block';
        cwlActiveInfoEl.style.display = isInCwl ? 'block' : 'none';
        setText(noCwlMessageEl, data.message || data.error || "CWL indisponível.");
        setText(cwlStatusTextEl, isInCwl ? "Em CWL" : "Fora da CWL");
        if (cwlStatusTextEl) cwlStatusTextEl.className = `war-state ${isInCwl ? 'incwl' : 'notincwl'}`;

        if (isInCwl) {
            setText(cwlSeasonEl, data.season);
            setText(cwlGroupStateEl, data.state);
            setHtml(cwlGroupClansEl, data.clans_in_group.map(c => `<p><img src="${c.badge_url || DEFAULT_BADGE_URL}" alt="Emblema ${c.name}"> <strong>${c.name}</strong> (${c.tag}) Nv ${c.level}</p>`).join(''));
            setHtml(cwlRoundsInfoEl, data.rounds.map(r => `
                <div class="cwl-round">
                    <h4>Rodada ${r.round_number}</h4>
                    ${r.wars.map(w => {
                        if (w.error) return `<p class="cwl-war-entry">Guerra: ${w.error}</p>`;
                        if (w.message) return `<p class="cwl-war-entry">${w.message}</p>`;
                        const cBadge = w.clan_badge_url ? `<img src="${w.clan_badge_url}" class="cwl-war-badge">` : "";
                        const oBadge = w.opponent_badge_url ? `<img src="${w.opponent_badge_url}" class="cwl-war-badge">` : "";
                        return `<p class="cwl-war-entry"><strong>${cBadge} ${w.clan_name}</strong> ${w.clan_stars}⭐ vs ${w.opponent_stars}⭐ <strong>${oBadge} ${w.opponent_name}</strong><br><small>Estado: ${w.state} | ${w.time_remaining}</small></p>`;
                    }).join('')}
                </div>
            `).join(''));
        }
    }

    function populateWarLog(data) {
        setText(warLogLimitEl, data.log?.length || '0');
        const hasLog = data.log && data.log.length > 0;
        noWarLogMessageEl.style.display = hasLog ? 'none' : 'block';
        
        if (hasLog) {
            setHtml(warLogTableBodyEl, data.log.map(e => `
                <tr class="historic-war-row" data-war-id="${e.end_time_iso}">
                    <td>${e.end_time_formatted}</td>
                    <td><img src="${e.opponent_badge_url || DEFAULT_BADGE_URL}" class="log-opponent-badge">${e.opponent_name || 'N/A'}</td>
                    <td>${e.clan_stars}⭐ (${e.clan_destruction}) vs ${e.opponent_stars}⭐ (${e.opponent_destruction})</td>
                    <td class="war-result-${e.result.toLowerCase()}">${e.result}</td>
                    <td>${e.team_size}</td>
                    <td>${e.is_cwl ? "CWL" : "Normal"}</td>
                </tr>
            `).join(''));
        } else {
            setText(noWarLogMessageEl, data.error || "Histórico de guerras indisponível.");
            setHtml(warLogTableBodyEl, '');
        }
    }
    
    function applyMemberFilters() {
        const filters = {
            name: filterNameInput.value.toLowerCase(),
            th: filterTHInput.value.toLowerCase().replace(/\s/g, ''),
            league: filterLeagueInput.value.toLowerCase(),
            trophies: filterTrophiesInput.value,
            role: filterRoleInput.value.toLowerCase()
        };

        membersTableBodyEl.querySelectorAll('tr').forEach(row => {
            const cells = row.cells;
            const member = {
                name: cells[1].textContent.toLowerCase(),
                th: `cv${cells[2].textContent}`.toLowerCase(),
                league: cells[3].textContent.toLowerCase(),
                trophies: parseInt(cells[4].textContent, 10),
                role: cells[5].textContent.toLowerCase()
            };

            let show = true;
            if (filters.name && !member.name.includes(filters.name)) show = false;
            if (filters.th && member.th !== filters.th) show = false;
            if (filters.league && !member.league.includes(filters.league)) show = false;
            if (filters.role && !member.role.includes(filters.role)) show = false;
            
            if (filters.trophies) {
                const match = filters.trophies.match(/(>=|<=|>|<)?\s*(\d+)/);
                if (match) {
                    const operator = match[1] || '==';
                    const value = parseInt(match[2], 10);
                    if ((operator === '>=' && member.trophies < value) ||
                        (operator === '<=' && member.trophies > value) ||
                        (operator === '>' && member.trophies <= value) ||
                        (operator === '<' && member.trophies >= value) ||
                        (operator === '==' && member.trophies !== value)) {
                        show = false;
                    }
                }
            }
            row.style.display = show ? '' : 'none';
        });
    }

    [filterNameInput, filterTHInput, filterLeagueInput, filterTrophiesInput, filterRoleInput].forEach(input => {
        input?.addEventListener('keyup', applyMemberFilters);
    });

    async function savePlayerNote(playerTag, text, priority) {
        await fetchData(`notes/${playerTag}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, priority })
        });
    }

    function populateMembersList(data) {
        setText(membersClanNameEl, data.clan_name);
        if (data.error || !data.members) {
            setHtml(membersTableBodyEl, `<tr><td colspan="9">${data.error || "N/A"}</td></tr>`);
            return;
        }

        setHtml(membersTableBodyEl, data.members.map((m, index) => `
            <tr>
                <td>${index + 1}</td>
                <td>${m.name}</td>
                <td>${m.town_hall}</td>
                <td>${m.league}</td>
                <td>${m.trophies}</td>
                <td>${m.role}</td>
                <td>${m.donations}</td>
                <td>${m.received}</td>
                <td class="member-note-cell" data-player-tag="${m.tag}" data-initial-note="${m.note || ''}" data-initial-priority="${m.note_priority || 'none'}"></td>
            </tr>
        `).join(''));
        
        membersTableBodyEl.querySelectorAll('.member-note-cell').forEach(cell => {
            const { playerTag, initialNote, initialPriority } = cell.dataset;
            const noteContainer = document.createElement('div');
            noteContainer.className = `note-container note-priority-${initialPriority}`;
            
            const noteTextSpan = document.createElement('span');
            noteTextSpan.className = 'note-text';
            noteTextSpan.textContent = initialNote || 'Clique para editar...';
            
            const noteInput = document.createElement('input');
            noteInput.type = 'text';
            noteInput.className = 'note-input';
            noteInput.value = initialNote;
            noteInput.style.display = 'none';
            
            const prioritySelector = document.createElement('div');
            prioritySelector.className = 'priority-selector';
            ['green', 'yellow', 'red', 'none'].forEach(prio => {
                const btn = document.createElement('button');
                btn.className = `priority-btn priority-${prio} ${prio === initialPriority ? 'active' : ''}`;
                btn.dataset.priority = prio;
                btn.innerHTML = { green: '&#10003;', yellow: '!', red: '&#10007;', none: '&times;' }[prio];
                
                btn.addEventListener('click', () => {
                    const newPriority = btn.dataset.priority;
                    noteContainer.className = `note-container note-priority-${newPriority}`;
                    prioritySelector.querySelectorAll('.priority-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    savePlayerNote(playerTag, noteInput.value, newPriority);
                });
                prioritySelector.appendChild(btn);
            });

            noteTextSpan.addEventListener('click', () => {
                noteTextSpan.style.display = 'none';
                noteInput.style.display = 'inline-block';
                noteInput.focus();
            });

            const finishEditing = () => {
                const newText = noteInput.value;
                const currentPriority = prioritySelector.querySelector('.priority-btn.active')?.dataset.priority || 'none';
                savePlayerNote(playerTag, newText, currentPriority);
                noteTextSpan.textContent = newText || 'Clique para editar...';
                noteInput.style.display = 'none';
                noteTextSpan.style.display = 'inline-block';
            };

            noteInput.addEventListener('blur', finishEditing);
            noteInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') finishEditing(); });

            noteContainer.append(noteTextSpan, noteInput, prioritySelector);
            cell.appendChild(noteContainer);
        });
        applyMemberFilters();
    }

    // --- LÓGICA DO MODAL DE GUERRA HISTÓRICA (SOLUÇÃO DEFINITIVA) ---
    async function openHistoricWarModal(warId) {
        setHtml(historicWarDetailContent, '<div class="loading-spinner" style="margin: 40px auto;"></div><p style="text-align:center;">Carregando detalhes da guerra...</p>');
        historicWarModal.style.display = 'block';
        const historicWarData = await fetchData(`war_history/${warId}`);
        
        const modalHTML = `
            <div class="war-details-card content-section" id="historic-war-container">
                <div class="war-header">
                    <img id="historic-warDetailClanBadge" src="${DEFAULT_BADGE_URL}" alt="Emblema Clã" class="war-header-badge">
                    <h2 id="historic-warDetailTitle"><span id="historic-warDetailOurClanName">-</span> vs <span id="historic-warDetailOpponentName">-</span></h2>
                    <img id="historic-warDetailOpponentBadge" src="${DEFAULT_BADGE_URL}" alt="Emblema Oponente" class="war-header-badge">
                </div>
                <p class="war-timing-overall"><strong id="historic-warDetailTimeKey">Tempo:</strong> <span id="historic-warDetailTimeValue">-</span> (<span id="historic-warDetailTimeRemaining" class="time-remaining">-</span>)</p>
                <p><strong>Estado:</strong> <span id="historic-warDetailState" class="war-state">-</span></p>
                <nav class="war-tabs">
                    <button class="war-tab-button active" data-tab="war-stats">Estatísticas</button>
                    <button class="war-tab-button" data-tab="war-events">Eventos</button>
                    <button class="war-tab-button" data-tab="war-our-team">Minha Equipe</button>
                    <button class="war-tab-button" data-tab="war-opponent-team">Equipe Inimiga</button>
                </nav>
                <div class="message-box" style="display: none;"></div>
                <div id="historic-war-stats" class="war-tab-content active">
                    <h3>Placar Geral</h3>
                    <div class="war-score-container">
                        <div class="team-score our-clan-score"><h4 id="historic-statsOurClanName">-</h4><p><span id="historic-statsOurStars">-</span>⭐ (<span id="historic-statsOurDestruction">-</span>%)</p><p><span id="historic-statsOurAttacksUsed">-</span> ataques</p></div>
                        <div class="vs-separator">⚔️</div>
                        <div class="team-score opponent-score"><h4 id="historic-statsOpponentName">-</h4><p><span id="historic-statsOpponentStars">-</span>⭐ (<span id="historic-statsOpponentDestruction">-</span>%)</p><p><span id="historic-statsOpponentAttacksUsed">-</span> ataques</p></div>
                    </div>
                    <div class="war-averages-container grid-container">
                        <div><h4>Médias (Nosso Clã)</h4><p><strong>Estrelas/Ataque:</strong> <span id="historic-statsOurAvgStars">-</span></p><p><strong>Duração/Ataque:</strong> <span id="historic-statsOurAvgDuration">-</span></p></div>
                        <div><h4>Médias (Oponente)</h4><p><strong>Estrelas/Ataque:</strong> <span id="historic-statsOpponentAvgStars">-</span></p><p><strong>Duração/Ataque:</strong> <span id="historic-statsOpponentAvgDuration">-</span></p></div>
                    </div>
                    <div class="star-distribution-container">
                        <h4>Distribuição de Estrelas (Nosso Clã)</h4><p>3⭐: <span id="historic-statsOurStars3">-</span> | 2⭐: <span id="historic-statsOurStars2">-</span> | 1⭐: <span id="historic-statsOurStars1">-</span> | 0⭐: <span id="historic-statsOurStars0">-</span></p>
                        <h4>Distribuição de Estrelas (Oponente)</h4><p>3⭐: <span id="historic-statsOpponentStars3">-</span> | 2⭐: <span id="historic-statsOpponentStars2">-</span> | 1⭐: <span id="historic-statsOpponentStars1">-</span> | 0⭐: <span id="historic-statsOpponentStars0">-</span></p>
                    </div>
                </div>
                <div id="historic-war-events" class="war-tab-content">
                    <h3>Todos os Ataques (<span id="historic-warTotalAttacksCount">0</span>)</h3>
                    <div class="table-container scrollable-box medium-table"><table id="historic-warEventsTable"><thead><tr><th>#</th><th>Atacante (CV)</th><th>Resultado</th><th>Defensor (CV)</th><th>Duração</th></tr></thead><tbody id="historic-warEventsTableBody"></tbody></table></div>
                </div>
                <div id="historic-war-our-team" class="war-tab-content">
                    <h3>Minha Equipe: <span id="historic-warOurTeamName">-</span></h3>
                    <div id="historic-warOurTeamMembers" class="team-members-container scrollable-box"></div>
                </div>
                <div id="historic-war-opponent-team" class="war-tab-content">
                    <h3>Equipe Inimiga: <span id="historic-warOpponentTeamName">-</span></h3>
                    <div id="historic-warOpponentTeamMembers" class="team-members-container scrollable-box"></div>
                </div>
            </div>
        `;
        setHtml(historicWarDetailContent, modalHTML);

        historicWarDetailContent.querySelectorAll('.war-tab-button').forEach(button => {
            button.addEventListener('click', () => {
                const modalContent = button.closest('.modal-content');
                modalContent.querySelectorAll('.war-tab-button').forEach(btn => btn.classList.remove('active'));
                modalContent.querySelectorAll('.war-tab-content').forEach(content => content.classList.remove('active'));
                
                button.classList.add('active');
                const tabId = `historic-${button.dataset.tab}`;
                const activeContent = modalContent.querySelector(`#${tabId}`);
                if (activeContent) activeContent.classList.add('active');
            });
        });
        
        populateWarDetails(historicWarData, historicWarDetailContent, true);
    }

    if (closeModalButton) closeModalButton.addEventListener('click', () => { historicWarModal.style.display = 'none'; });
    window.addEventListener('click', (event) => { if (event.target == historicWarModal) historicWarModal.style.display = 'none'; });

    warLogTableBodyEl.addEventListener('click', (event) => {
        const row = event.target.closest('.historic-war-row');
        if (row?.dataset.warId) openHistoricWarModal(row.dataset.warId);
    });

    async function loadAllData() {
        try {
            const [clanData, membersData, currentWarDetailsData, missedAttacksData, warLogData, cwlInfoData] = await Promise.all([
                fetchData('clan'), fetchData('members'), fetchData('current_war_details'),
                fetchData('missed_attacks_history'), fetchData('war_log'), fetchData('cwl_info')
            ]);
            populateClanInfo(clanData);
            populateMembersList(membersData);
            populateWarDetails(document.getElementById('war-details-nav'), currentWarDetailsData, false);
            populateMissedAttacksHistory(missedAttacksData);
            populateWarLog(warLogData);
            populateCwlInfo(cwlInfoData);
            updateLastUpdated();
        } catch (error) {
            console.error("Erro ao carregar todos os dados:", error);
        } finally {
            if (isFirstLoad) {
                loadingOverlayEl.classList.add('hidden');
                isFirstLoad = false;
            }
        }
    }

    setActiveSection(initialSectionId);
    loadAllData();
    setInterval(loadAllData, 60000);

    const particleCanvas = document.getElementById('particle-background');
    if (particleCanvas) {
        const ctx = particleCanvas.getContext('2d');
        let particlesArray = [];
        const particleSettings = { count: 35, maxSize: 3, color: 'rgba(255, 215, 0, 0.6)', lineColor: 'rgba(255, 215, 0, 0.1)' };

        const resizeCanvas = () => {
            particleCanvas.width = window.innerWidth;
            particleCanvas.height = window.innerHeight;
            particlesArray = [];
            for (let i = 0; i < particleSettings.count; i++) {
                particlesArray.push({
                    x: Math.random() * particleCanvas.width,
                    y: Math.random() * particleCanvas.height,
                    size: Math.random() * particleSettings.maxSize + 1,
                    speedX: Math.random() * 1 - 0.5,
                    speedY: Math.random() * 1 - 0.5
                });
            }
        };

        const animateParticles = () => {
            ctx.clearRect(0, 0, particleCanvas.width, particleCanvas.height);
            particlesArray.forEach(p => {
                p.x += p.speedX;
                p.y += p.speedY;
                if (p.x > particleCanvas.width || p.x < 0) p.speedX *= -1;
                if (p.y > particleCanvas.height || p.y < 0) p.speedY *= -1;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
                ctx.fillStyle = particleSettings.color;
                ctx.fill();
            });
            requestAnimationFrame(animateParticles);
        };
        
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();
        animateParticles();
    }
});
