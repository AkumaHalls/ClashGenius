document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = '';
    const DEFAULT_BADGE_URL = '/static/images/default_badge.png'; // Mantido para outros usos, mas não para o loading badge principal

    // --- ELEMENTOS DO DOM ---
    const loadingOverlayEl = document.getElementById('loading-overlay');
    // const loadingClanBadgeEl = document.getElementById('loadingClanBadge'); // Não precisamos mais manipular o SRC dele aqui

    const clanNameHeaderEl = document.getElementById('clanNameHeader');
    const clanBadgeHeaderEl = document.getElementById('clanBadgeHeader');
    // Clã Info
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

    // Guerra Detalhes
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

    // Ataques Pendentes
    const attacksRemainingClanNameEl = document.getElementById('attacksRemainingClanName');
    const attacksRemainingListEl = document.getElementById('attacksRemainingList');
    const noWarForAttacksRemainingMessageEl = document.getElementById('noWarForAttacksRemainingMessage');

    // CWL
    const cwlStatusTextEl = document.getElementById('cwlStatusText');
    const cwlActiveInfoEl = document.getElementById('cwlActiveInfo');
    const cwlSeasonEl = document.getElementById('cwlSeason');
    const cwlGroupStateEl = document.getElementById('cwlGroupState');
    const cwlGroupClansEl = document.getElementById('cwlGroupClans');
    const cwlRoundsInfoEl = document.getElementById('cwlRoundsInfo');
    const noCwlMessageEl = document.getElementById('noCwlMessage');

    // Histórico de Guerras
    const warLogLimitEl = document.getElementById('warLogLimit');
    const warLogTableBodyEl = document.getElementById('warLogTableBody');
    const noWarLogMessageEl = document.getElementById('noWarLogMessage');

    // Membros
    const membersClanNameEl = document.getElementById('membersClanName');
    const membersTableBodyEl = document.getElementById('membersTableBody');
    const filterNameInput = document.getElementById('filterName');
    const filterTHInput = document.getElementById('filterTH');
    const filterLeagueInput = document.getElementById('filterLeague');
    const filterTrophiesInput = document.getElementById('filterTrophies');
    const filterRoleInput = document.getElementById('filterRole');

    // Rodapé
    const botVersionEl = document.getElementById('botVersion');
    const lastUpdatedEl = document.getElementById('lastUpdated');

    const navLinks = document.querySelectorAll('.nav-link');
    const contentSections = document.querySelectorAll('.content-section');
    let isFirstLoad = true;


    // --- FUNÇÕES HELPER ---
    async function fetchData(endpoint, options = {}) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/${endpoint}`, options);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: `Falha: ${response.status}` }));
                console.error(`HTTP error! status: ${response.status} for ${endpoint}`, errorData);
                return { error: errorData.error || `Falha ao carregar ${endpoint}. Status: ${response.status}` };
            }
            if (options.method && options.method !== 'GET' && response.status === 204) {
                return { success: true };
            }
            return await response.json();
        } catch (error) {
            console.error(`Could not fetch data from ${endpoint}:`, error);
            return { error: `Erro de conexão ao buscar ${endpoint}.` };
        }
    }

    function updateLastUpdated() {
        const now = new Date();
        setText(lastUpdatedEl, `Última atualização: ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`);
    }

    function setText(element, text, defaultValue = '-') {
        if (element) element.textContent = text === null || text === undefined || text === '' ? defaultValue : text;
    }
    function setHtml(element, htmlContent) {
        if (element) element.innerHTML = htmlContent;
    }
    function setBadge(element, url) { // Esta função ainda é usada para outros badges no site
        if (element) { element.src = url || DEFAULT_BADGE_URL; element.style.display = 'inline-block'; }
    }
    function show(element) { if (element) element.style.display = 'block'; }
    function hide(element) { if (element) element.style.display = 'none'; }


    // --- NAVEGAÇÃO E ANIMAÇÃO DAS SEÇÕES ---
    const initialSectionId = (navLinks.length > 0 && navLinks[0].dataset.section) ? navLinks[0].dataset.section : 'clan-info-nav';
    let currentActiveSectionId = localStorage.getItem('activeSection') || initialSectionId;
    let currentActiveIndex = Array.from(navLinks).findIndex(link => link.dataset.section === currentActiveSectionId);

    if (currentActiveIndex === -1) {
        currentActiveIndex = 0;
        currentActiveSectionId = initialSectionId;
    }

    contentSections.forEach(section => {
        section.classList.remove('active-section', 'slide-out-left', 'slide-out-right', 'slide-in-from-left', 'slide-in-from-right');
        if (section.id === currentActiveSectionId) {
            section.classList.add('active-section');
        }
    });
    navLinks.forEach(link => {
        link.classList.toggle('active-nav-link', link.dataset.section === currentActiveSectionId);
    });


    function setActiveSection(newSectionId, newIndex) {
        if (newSectionId === currentActiveSectionId) return;

        const oldSectionEl = document.getElementById(currentActiveSectionId);
        const newSectionEl = document.getElementById(newSectionId);
        const oldIndex = currentActiveIndex;

        if (!newSectionEl) return;

        newSectionEl.classList.remove('slide-out-left', 'slide-out-right', 'slide-in-from-left', 'slide-in-from-right', 'active-section');

        if (oldSectionEl) {
            oldSectionEl.classList.remove('active-section');
            if (newIndex > oldIndex) {
                oldSectionEl.classList.add('slide-out-left');
            } else {
                oldSectionEl.classList.add('slide-out-right');
            }
            oldSectionEl.addEventListener('transitionend', () => {
                oldSectionEl.classList.remove('slide-out-left', 'slide-out-right');
            }, { once: true });
        }

        if (newIndex > oldIndex) {
            newSectionEl.classList.add('slide-in-from-right');
        } else {
            newSectionEl.classList.add('slide-in-from-left');
        }

        void newSectionEl.offsetWidth;

        newSectionEl.classList.add('active-section');

        newSectionEl.addEventListener('transitionend', () => {
            newSectionEl.classList.remove('slide-in-from-left', 'slide-in-from-right');
        }, { once: true });

        navLinks.forEach(link => {
            link.classList.toggle('active-nav-link', link.dataset.section === newSectionId);
        });

        localStorage.setItem('activeSection', newSectionId);
        currentActiveSectionId = newSectionId;
        currentActiveIndex = newIndex;
    }

    navLinks.forEach((link, index) => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const sectionId = link.dataset.section;
            setActiveSection(sectionId, index);
        });
    });


    // --- FUNÇÕES DE POPULAÇÃO DE DADOS ---
    function populateClanInfo(data) {
        if (data.error || !data.name) {
            setText(clanNameHeaderEl, "Erro"); setText(clanNameEl, data.error || "N/A");
            // NÃO atualizamos mais o loadingClanBadgeEl.src aqui
            return;
        }
        setText(clanNameHeaderEl, data.name); setText(clanNameEl, data.name); setText(clanTagEl, data.tag);
        setText(clanLevelEl, data.level); setText(clanPointsEl, data.points); setText(clanMemberCountEl, data.member_count);
        setText(clanWarWinsEl, data.war_wins); setText(clanLocationEl, data.location); setText(clanTypeEl, data.type);
        setText(clanDescriptionEl, data.description, 'Sem descrição.'); setText(botVersionEl, data.version, '?');
        setBadge(clanBadgeHeaderEl, data.badge_url); // Badge do header continua sendo o do clã
        setBadge(clanBadgeEl, data.badge_url);       // Badge da seção "Clã Info" continua sendo o do clã
        // NENHUMA alteração no loadingClanBadgeEl.src aqui

        setText(clanCapitalPointsEl, data.capital_points); setText(clanCapitalLeagueEl, data.capital_league);
        setHtml(clanCapitalDistrictsEl, '');
        if (data.capital_districts && data.capital_districts.length > 0 && data.capital_districts[0].name !== "Distritos da Capital Indisponíveis (erro de importação)") {
            data.capital_districts.forEach(d => setHtml(clanCapitalDistrictsEl, clanCapitalDistrictsEl.innerHTML + `<p><strong>${d.name || 'N/A'}:</strong> Nv ${d.level || '?'}</p>`));
        } else if (data.capital_districts && data.capital_districts.length > 0) {
            setHtml(clanCapitalDistrictsEl, `<p>${data.capital_districts[0].name}</p>`);
        } else { setHtml(clanCapitalDistrictsEl, '<p>Nenhum distrito encontrado.</p>'); }
    }

    warTabButtons.forEach(button => {
        button.addEventListener('click', () => {
            warTabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            const tabId = button.dataset.tab;
            warTabContents.forEach(content => {
                content.style.display = content.id === tabId ? 'block' : 'none';
            });
        });
    });

    function createStarString(stars) {
        return '⭐'.repeat(stars) + '⚫'.repeat(Math.max(0, 3 - stars));
    }

    function populateWarDetails(data) {
        if (data.error || !data.war_data) {
            show(noWarDetailMessageEl); setText(noWarDetailMessageEl, data.error || "Nenhuma guerra para detalhar.");
            hide(document.querySelector('#war-details-nav .war-header'));
            hide(document.querySelector('#war-details-nav .war-tabs'));
            warTabContents.forEach(hide);
            return;
        }
        hide(noWarDetailMessageEl);
        show(document.querySelector('#war-details-nav .war-header'));
        show(document.querySelector('#war-details-nav .war-tabs'));

        const war = data.war_data;
        setText(warDetailOurClanNameEl, war.clan_name);
        setText(warDetailOpponentNameEl, war.opponent_name);
        setBadge(warDetailClanBadgeEl, war.clan_badge_url);
        setBadge(warDetailOpponentBadgeEl, war.opponent_badge_url);
        setText(warDetailTimeKeyEl, war.time_key);
        setText(warDetailTimeValueEl, war.time_value);
        setText(warDetailTimeRemainingEl, war.time_remaining);
        setText(warDetailStateEl, war.state_description);
        if (warDetailStateEl) warDetailStateEl.className = 'war-state ' + (war.status || '').toLowerCase();

        setText(statsOurClanNameEl, war.clan_name);
        setText(statsOurStarsEl, war.clan_stars);
        setText(statsOurDestructionEl, war.clan_destruction.replace('%', ''));
        setText(statsOurAttacksUsedEl, `${war.clan_attacks_used}/${war.team_size * war.attacks_per_member}`);
        setText(statsOpponentNameEl, war.opponent_name);
        setText(statsOpponentStarsEl, war.opponent_stars);
        setText(statsOpponentDestructionEl, war.opponent_destruction.replace('%', ''));
        setText(statsOpponentAttacksUsedEl, `${war.opponent_attacks_used}/${war.team_size * war.attacks_per_member}`);
        setText(statsOurAvgStarsEl, war.clan_avg_stars);
        setText(statsOurAvgDurationEl, war.clan_avg_duration);
        setText(statsOpponentAvgStarsEl, war.opponent_avg_stars);
        setText(statsOpponentAvgDurationEl, war.opponent_avg_duration);
        setText(statsOurStars3El, war.clan_star_distribution[3]); setText(statsOurStars2El, war.clan_star_distribution[2]);
        setText(statsOurStars1El, war.clan_star_distribution[1]); setText(statsOurStars0El, war.clan_star_distribution[0]);
        setText(statsOpponentStars3El, war.opponent_star_distribution[3]); setText(statsOpponentStars2El, war.opponent_star_distribution[2]);
        setText(statsOpponentStars1El, war.opponent_star_distribution[1]); setText(statsOpponentStars0El, war.opponent_star_distribution[0]);

        setText(warTotalAttacksCountEl, data.all_attacks.length);
        setHtml(warEventsTableBodyEl, '');
        if (data.all_attacks && data.all_attacks.length > 0) {
            data.all_attacks.forEach(att => {
                const row = warEventsTableBodyEl.insertRow();
                setText(row.insertCell(), att.order);
                setText(row.insertCell(), `${att.attacker_name} (CV${att.attacker_townhall})`);
                const resultCell = row.insertCell();
                resultCell.innerHTML = `<span class="attack-stars">${createStarString(att.stars)}</span> ${att.destruction}%`;
                setText(row.insertCell(), `${att.defender_name} (CV${att.defender_townhall})`);
                setText(row.insertCell(), att.duration);
            });
        } else { setHtml(warEventsTableBodyEl, '<tr><td colspan="5">Nenhum ataque registrado.</td></tr>'); }

        const populateTeamTabData = (teamMembersData, teamNameKey, teamElement) => {
            setText(document.getElementById(`war${teamNameKey}TeamName`), war[`${teamNameKey.toLowerCase()}_clan_name`] || (teamNameKey === "Our" ? "Nosso Clã" : "Oponente"));
            setHtml(teamElement, '');
            if (teamMembersData && teamMembersData.length > 0) {
                teamMembersData.forEach(member => {
                    let attacksHtml = '<h5>Ataques Feitos:</h5><ul class="member-attack-list">';
                    if (member.attacks_made && member.attacks_made.length > 0) {
                        member.attacks_made.forEach(atk => {
                            attacksHtml += `<li>${createStarString(atk.stars)} ${atk.destruction}% vs ${atk.defender_name} (CV${atk.defender_townhall})</li>`;
                        });
                    } else { attacksHtml += '<li>Nenhum ataque feito.</li>'; }
                    attacksHtml += '</ul>';

                    let defensesHtml = '<h5>Defesas Recebidas:</h5><ul class="member-defense-list">';
                    if (member.defenses_received && member.defenses_received.length > 0) {
                        member.defenses_received.forEach(def => {
                            defensesHtml += `<li>${createStarString(def.stars)} ${def.destruction}% por ${def.attacker_name} (CV${def.attacker_townhall})</li>`;
                        });
                    } else { defensesHtml += '<li>Nenhuma defesa registrada.</li>'; }
                    defensesHtml += '</ul>';

                    const memberCard = document.createElement('div');
                    memberCard.className = 'team-member-card';
                    memberCard.innerHTML = `
                        <h4><img src="/static/images/townhall${member.townhall}.png" alt="CV${member.townhall}" onerror="this.style.display='none'"/> ${member.map_position}. ${member.name} (CV${member.townhall})</h4>
                        <p>Ataques: ${member.attacks_used}/${war.attacks_per_member}</p>
                        ${attacksHtml}
                        ${defensesHtml}
                    `;
                    teamElement.appendChild(memberCard);
                });
            } else { setHtml(teamElement, '<p>Nenhum membro nesta equipe para a guerra.</p>'); }
        };

        populateTeamTabData(data.our_clan_members_in_war, "Our", warOurTeamMembersEl);
        populateTeamTabData(data.opponent_clan_members_in_war, "Opponent", warOpponentTeamMembersEl);

        if (!document.querySelector('.war-tab-button.active')) {
            const firstTab = document.querySelector('.war-tab-button[data-tab="war-stats"]');
            if (firstTab) firstTab.click();
        }
    }

    function populateWarAttacksRemaining(data) {
        setText(attacksRemainingClanNameEl, data.clan_name);
        if (data.error || !data.members_pending || data.members_pending.length === 0) {
            setHtml(attacksRemainingListEl, `<p>${data.message || data.error || "Todos os ataques realizados ou não há guerra."}</p>`);
            show(noWarForAttacksRemainingMessageEl);
            setText(noWarForAttacksRemainingMessageEl, data.message || data.error || "Todos os ataques realizados ou não há guerra.");
            return;
        }
        hide(noWarForAttacksRemainingMessageEl);
        setHtml(attacksRemainingListEl, '');
        data.members_pending.forEach(m => setHtml(attacksRemainingListEl, attacksRemainingListEl.innerHTML + `<p><strong>${m.name}</strong> (CV${m.town_hall}) - ${m.attacks_left} atk restante(s)</p>`));
    }

    function populateCwlInfo(data) {
        setText(cwlStatusTextEl, "Carregando...");
        if (cwlStatusTextEl) cwlStatusTextEl.className = 'war-state';

        if (data.error || data.status === "NotInCwl" || data.status === "CwlFeatureDisabled") {
            show(noCwlMessageEl); setText(noCwlMessageEl, data.message || data.error || "CWL indisponível.");
            hide(cwlActiveInfoEl); setText(cwlStatusTextEl, data.message || (data.error ? "Erro" : "Fora da CWL"));
            if (cwlStatusTextEl) cwlStatusTextEl.classList.add((data.status || 'notincwl').toLowerCase());
            return;
        }
        hide(noCwlMessageEl); show(cwlActiveInfoEl);
        setText(cwlStatusTextEl, "Em CWL"); if (cwlStatusTextEl) cwlStatusTextEl.classList.add('incwl');
        setText(cwlSeasonEl, data.season); setText(cwlGroupStateEl, data.state);
        setHtml(cwlGroupClansEl, '');
        if (data.clans_in_group && data.clans_in_group.length > 0) {
            data.clans_in_group.forEach(c => setHtml(cwlGroupClansEl, cwlGroupClansEl.innerHTML + `<p><img src="${c.badge_url || DEFAULT_BADGE_URL}" alt="Emblema ${c.name}"> <strong>${c.name}</strong> (${c.tag}) Nv ${c.level}</p>`));
        } else { setHtml(cwlGroupClansEl, '<p>Nenhum clã no grupo.</p>'); }
        setHtml(cwlRoundsInfoEl, '');
        if (data.rounds && data.rounds.length > 0) {
            data.rounds.forEach(r => {
                let roundHtml = `<div class="cwl-round"><h4>Rodada ${r.round_number}</h4>`;
                if (r.wars && r.wars.length > 0) {
                    r.wars.forEach(w => {
                        if (w.error) { roundHtml += `<p class="cwl-war-entry">Guerra (${w.war_tag || 'N/A'}): ${w.error}</p>`; }
                        else if (w.message) { roundHtml += `<p class="cwl-war-entry">${w.message}</p>`; }
                        else {
                            const cBadge = w.clan_badge_url ? `<img src="${w.clan_badge_url}" alt="Emblema ${w.clan_name}" class="cwl-war-badge">` : "";
                            const oBadge = w.opponent_badge_url ? `<img src="${w.opponent_badge_url}" alt="Emblema ${w.opponent_name}" class="cwl-war-badge">` : "";
                            roundHtml += `<p class="cwl-war-entry"><strong>${cBadge} ${w.clan_name}</strong> ${w.clan_stars}⭐ (${w.clan_destruction}) vs ${w.opponent_stars}⭐ (${w.opponent_destruction}) <strong>${oBadge} ${w.opponent_name}</strong><br><small>Estado: ${w.state} | ${w.time_key}: ${w.time_value} (${w.time_remaining})</small></p>`;
                        }
                    });
                } else { roundHtml += "<p>Nenhuma guerra nesta rodada.</p>"; }
                roundHtml += "</div>";
                setHtml(cwlRoundsInfoEl, cwlRoundsInfoEl.innerHTML + roundHtml);
            });
        } else { setHtml(cwlRoundsInfoEl, "Nenhuma info de rodada."); }
    }

    function populateWarLog(data) {
        setText(warLogLimitEl, data.log ? data.log.length : '10');
        if (data.error || !data.log) {
            show(noWarLogMessageEl); setText(noWarLogMessageEl, data.error || "Log de guerra indisponível.");
            setHtml(warLogTableBodyEl, `<tr><td colspan="6">${data.error || "N/A"}</td></tr>`);
            return;
        }
        hide(noWarLogMessageEl); setHtml(warLogTableBodyEl, '');
        if (data.log.length > 0) {
            data.log.forEach(e => {
                const row = warLogTableBodyEl.insertRow();
                setText(row.insertCell(), e.end_time);
                const oppCell = row.insertCell();
                const oppBadge = e.opponent_badge_url ? `<img src="${e.opponent_badge_url}" alt="Emblema ${e.opponent_name}" class="log-opponent-badge">` : "";
                setHtml(oppCell, `${oppBadge}${e.opponent_name || 'N/A'}`);
                setText(row.insertCell(), `${e.clan_stars}⭐ (${e.clan_destruction}%) vs ${e.opponent_stars}⭐ (${e.opponent_destruction}%)`);
                const resCell = row.insertCell(); setText(resCell, e.result); resCell.className = e.result ? `war-result-${e.result.toLowerCase()}` : '';
                setText(row.insertCell(), e.team_size); setText(row.insertCell(), e.is_cwl ? "CWL" : "Normal");
            });
        } else { setHtml(warLogTableBodyEl, '<tr><td colspan="6">Nenhum registro encontrado.</td></tr>'); }
    }

    function applyMemberFilters() {
        const nameFilter = filterNameInput.value.toLowerCase();
        const thFilter = filterTHInput.value.toLowerCase().replace(/\s/g, '');
        const leagueFilter = filterLeagueInput.value.toLowerCase();
        const trophiesFilterText = filterTrophiesInput.value;
        const roleFilter = filterRoleInput.value.toLowerCase();
        const rows = membersTableBodyEl.getElementsByTagName('tr');

        for (let i = 0; i < rows.length; i++) {
            const row = rows[i];
            const cells = row.getElementsByTagName('td');
            let displayRow = true;

            if (cells.length > 7) {
                if (nameFilter && !cells[1].textContent.toLowerCase().includes(nameFilter)) displayRow = false;
                if (thFilter && !cells[2].textContent.toLowerCase().includes(thFilter)) displayRow = false;
                if (leagueFilter && !cells[3].textContent.toLowerCase().includes(leagueFilter)) displayRow = false;
                if (trophiesFilterText) {
                    const memberTrophies = parseInt(cells[4].textContent, 10);
                    const filterTrophiesNum = parseInt(trophiesFilterText, 10);
                    if (!isNaN(filterTrophiesNum) && memberTrophies !== filterTrophiesNum) {
                        displayRow = false;
                    } else if (isNaN(filterTrophiesNum) && !cells[4].textContent.includes(trophiesFilterText)) {
                         displayRow = false;
                    }
                }
                if (roleFilter && !cells[5].textContent.toLowerCase().includes(roleFilter)) displayRow = false;
            } else if (row.getElementsByTagName('th').length === 0) {
                displayRow = false;
            }
            row.style.display = displayRow ? '' : 'none';
        }
    }
    if (filterNameInput) filterNameInput.addEventListener('input', applyMemberFilters);
    if (filterTHInput) filterTHInput.addEventListener('input', applyMemberFilters);
    if (filterLeagueInput) filterLeagueInput.addEventListener('input', applyMemberFilters);
    if (filterTrophiesInput) filterTrophiesInput.addEventListener('input', applyMemberFilters);
    if (filterRoleInput) filterRoleInput.addEventListener('input', applyMemberFilters);

    async function savePlayerNote(playerTag, text, priority) {
        const cleanTag = playerTag.replace("#", "");
        const response = await fetchData(`notes/${cleanTag}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, priority })
        });
        if (response.error) {
            console.error("Erro ao salvar nota:", response.error);
        } else {
            console.log("Nota salva:", response.message);
        }
    }

    function populateMembersList(data) {
        setText(membersClanNameEl, data.clan_name ? `(${data.clan_name})` : '');
        if (data.error) { setHtml(membersTableBodyEl, `<tr><td colspan="9">${data.error}</td></tr>`); return; }
        setHtml(membersTableBodyEl, '');
        if (data.members && data.members.length > 0) {
            data.members.forEach((m, i) => {
                const r = membersTableBodyEl.insertRow();
                setText(r.insertCell(), i + 1);
                setText(r.insertCell(), m.name);
                setText(r.insertCell(), `CV${m.town_hall || '?'}`);
                setText(r.insertCell(), m.league);
                setText(r.insertCell(), m.trophies);
                setText(r.insertCell(), m.role);
                setText(r.insertCell(), m.donations);
                setText(r.insertCell(), m.received);

                const noteCell = r.insertCell();
                noteCell.className = 'member-note-cell';
                const noteContainer = document.createElement('div');
                noteContainer.className = `note-container note-priority-${m.note_priority || 'none'}`;
                const noteTextSpan = document.createElement('span');
                noteTextSpan.className = 'note-text';
                noteTextSpan.textContent = m.note || '';
                noteTextSpan.title = m.note || 'Sem observação';
                noteContainer.appendChild(noteTextSpan);
                const noteInput = document.createElement('input');
                noteInput.type = 'text';
                noteInput.className = 'note-input';
                noteInput.value = m.note || '';
                noteInput.style.display = 'none';
                noteContainer.appendChild(noteInput);
                const prioritySelector = document.createElement('div');
                prioritySelector.className = 'priority-selector';
                ['none', 'green', 'yellow', 'red'].forEach(prio => {
                    const btn = document.createElement('button');
                    btn.className = `priority-btn priority-${prio}`;
                    btn.dataset.priority = prio;
                    if (prio === 'none') btn.innerHTML = '&times;';
                    else btn.innerHTML = '&#9679;';
                    if (prio === (m.note_priority || 'none')) btn.classList.add('active');
                    btn.addEventListener('click', () => {
                        const currentText = noteInput.style.display === 'none' ? noteTextSpan.textContent : noteInput.value;
                        savePlayerNote(m.tag, currentText, prio);
                        noteContainer.className = `note-container note-priority-${prio}`;
                        prioritySelector.querySelectorAll('.priority-btn').forEach(b => b.classList.remove('active'));
                        btn.classList.add('active');
                    });
                    prioritySelector.appendChild(btn);
                });
                noteContainer.appendChild(prioritySelector);
                noteTextSpan.addEventListener('click', () => {
                    noteTextSpan.style.display = 'none';
                    noteInput.style.display = 'inline-block';
                    noteInput.focus();
                });
                noteInput.addEventListener('blur', () => {
                    const newText = noteInput.value;
                    const currentPriority = prioritySelector.querySelector('.priority-btn.active')?.dataset.priority || 'none';
                    savePlayerNote(m.tag, newText, currentPriority);
                    noteTextSpan.textContent = newText;
                    noteTextSpan.title = newText || 'Sem observação';
                    noteInput.style.display = 'none';
                    noteTextSpan.style.display = 'inline';
                });
                 noteInput.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') noteInput.blur();
                });
                noteCell.appendChild(noteContainer);
            });
        } else { setHtml(membersTableBodyEl, '<tr><td colspan="9">Nenhum membro.</td></tr>'); }
        applyMemberFilters();
    }


    // --- CARREGAMENTO INICIAL E PERIÓDICO ---
    async function loadAllData() {
        const [clanData, membersData, currentWarDetailsData, warAttacksRemainingData, warLogData, cwlInfoData] = await Promise.all([
            fetchData('clan'), fetchData('members'), fetchData('current_war_details'),
            fetchData('war_attacks_remaining'), fetchData('war_log?limit=10'), fetchData('cwl_info')
        ]);
        populateClanInfo(clanData); // Não mexe mais no loadingClanBadgeEl.src
        populateMembersList(membersData);
        populateWarDetails(currentWarDetailsData);
        populateWarAttacksRemaining(warAttacksRemainingData);
        populateWarLog(warLogData);
        populateCwlInfo(cwlInfoData);
        updateLastUpdated();

        if (isFirstLoad && loadingOverlayEl) {
            // A imagem de carregamento agora é definida apenas no HTML.
            // Apenas controlamos o tempo para esconder o overlay.
            setTimeout(() => {
                loadingOverlayEl.classList.add('hidden');
            }, 4000); // Tempo aumentado para 2 segundos
            isFirstLoad = false;
        }
    }
    loadAllData();
    setInterval(loadAllData, 60000);
});
