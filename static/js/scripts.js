document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = ''; 
    const DEFAULT_BADGE_URL = '/static/images/default_badge.png'; 

    // --- ELEMENTOS DO DOM ---
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
    const warDetailSection = document.getElementById('war-details-nav');
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
    const toastNotificationEl = document.getElementById('toast-notification');

    // Navegação Principal e Seções de Conteúdo
    const navLinks = document.querySelectorAll('.nav-link');
    const contentSections = document.querySelectorAll('.content-section');

    // --- FUNÇÕES HELPER ---
    async function fetchData(endpoint, options = {}) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/${endpoint}`, options);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: `Falha: ${response.status}` }));
                console.error(`HTTP error! status: ${response.status} for ${endpoint}`, errorData);
                showToast(`Erro: ${errorData.error || response.statusText || 'Falha ao carregar dados.'}`, 'error');
                return { error: errorData.error || `Falha ao carregar ${endpoint}. Status: ${response.status}` };
            }
            return await response.json();
        } catch (error) {
            console.error(`Could not fetch data from ${endpoint}:`, error);
            showToast(`Erro de conexão com API.`, 'error');
            return { error: `Erro de conexão ao buscar ${endpoint}.` };
        }
    }

    function showToast(message, type = 'info') { // type can be 'info', 'success', 'error'
        if (!toastNotificationEl) return;
        toastNotificationEl.textContent = message;
        toastNotificationEl.className = 'toast show'; // Reset classes
        if (type === 'success') {
            toastNotificationEl.classList.add('success');
        } else if (type === 'error') {
            toastNotificationEl.classList.add('error');
        }
        setTimeout(() => { toastNotificationEl.className = toastNotificationEl.className.replace("show", ""); }, 3000);
    }


    function updateLastUpdated() {
        const now = new Date();
        setText(lastUpdatedEl, `Última atualização: ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`);
    }

    function setText(element, text, defaultValue = '-') {
        if (element) element.textContent = text === null || text === undefined || text === '' ? defaultValue : text;
    }
    function setHtml(element, htmlContent) {
        if(element) element.innerHTML = htmlContent;
    }
    function setBadge(element, url) {
        if (element) { element.src = url || DEFAULT_BADGE_URL; element.style.display = 'inline-block';}
    }
    function show(element) { if(element) element.style.display = 'block'; }
    function hide(element) { if(element) element.style.display = 'none'; }

    // --- NAVEGAÇÃO PRINCIPAL ---
    function setActiveSection(sectionId) {
        contentSections.forEach(section => {
            section.classList.toggle('active-section', section.id === sectionId);
        });
        navLinks.forEach(link => {
            link.classList.toggle('active-nav-link', link.dataset.section === sectionId);
        });
        localStorage.setItem('activeSection', sectionId);
    }

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const sectionId = link.dataset.section;
            setActiveSection(sectionId);
            const sectionElement = document.getElementById(sectionId);
            if(sectionElement) sectionElement.scrollIntoView({behavior: "smooth", block: "start"});
        });
    });
    
    const savedSection = localStorage.getItem('activeSection');
    if (savedSection && document.getElementById(savedSection)) {
        setActiveSection(savedSection);
    } else {
        setActiveSection('clan-info-nav'); 
    }

    // --- FUNÇÕES DE POPULAÇÃO DE DADOS ---
    function populateClanInfo(data) {
        if (data.error || !data.name) { setText(clanNameHeaderEl, "Erro"); setText(clanNameEl, data.error || "N/A"); return; }
        setText(clanNameHeaderEl, data.name); setText(clanNameEl, data.name); setText(clanTagEl, data.tag);
        setText(clanLevelEl, data.level); setText(clanPointsEl, data.points); setText(clanMemberCountEl, data.member_count);
        setText(clanWarWinsEl, data.war_wins); setText(clanLocationEl, data.location); setText(clanTypeEl, data.type);
        setText(clanDescriptionEl, data.description, 'Sem descrição.'); setText(botVersionEl, data.version, '?');
        setBadge(clanBadgeHeaderEl, data.badge_url); setBadge(clanBadgeEl, data.badge_url);
        setText(clanCapitalPointsEl, data.capital_points); setText(clanCapitalLeagueEl, data.capital_league);
        setHtml(clanCapitalDistrictsEl, ''); 
        if (data.capital_districts && data.capital_districts.length > 0 && data.capital_districts[0].name !== "Distritos Indisponíveis (erro import)") {
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
        if(warDetailStateEl) warDetailStateEl.className = 'war-state ' + (war.status || '').toLowerCase();

        setText(statsOurClanNameEl, war.clan_name);
        setText(statsOurStarsEl, war.clan_stars);
        setText(statsOurDestructionEl, war.clan_destruction.replace('%',''));
        setText(statsOurAttacksUsedEl, `${war.clan_attacks_used}/${war.team_size * war.attacks_per_member}`);
        setText(statsOpponentNameEl, war.opponent_name);
        setText(statsOpponentStarsEl, war.opponent_stars);
        setText(statsOpponentDestructionEl, war.opponent_destruction.replace('%',''));
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
            const clanNameForTeam = war[`${teamNameKey.toLowerCase()}_name`] || (teamNameKey === "ourClan" ? "Nosso Clã" : "Oponente");
            setText(document.getElementById(`war${teamNameKey === "ourClan" ? "Our" : "Opponent"}TeamName`), clanNameForTeam);

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
                    // Tenta carregar a imagem do CV, se não existir, não quebra
                    const townHallImgSrc = `/static/images/townhall${member.townhall}.png`;
                    memberCard.innerHTML = `
                        <h4><img src="${townHallImgSrc}" alt="CV${member.townhall}" onerror="this.style.display='none'; this.alt='CV${member.townhall}'" /> ${member.map_position}. ${member.name} (CV${member.townhall})</h4>
                        <p>Ataques: ${member.attacks_used}/${war.attacks_per_member}</p>
                        ${attacksHtml}
                        ${defensesHtml}
                    `;
                    teamElement.appendChild(memberCard);
                });
            } else { setHtml(teamElement, '<p>Nenhum membro nesta equipe para a guerra.</p>'); }
        };
        
        populateTeamTabData(data.our_clan_members_in_war, "ourClan", warOurTeamMembersEl);
        populateTeamTabData(data.opponent_clan_members_in_war, "opponent", warOpponentTeamMembersEl);

        if (!document.querySelector('.war-tab-button.active')) {
             const firstTab = document.querySelector('.war-tab-button[data-tab="war-stats"]');
             if(firstTab) firstTab.click();
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
        if (data.error || data.status === "NotInCwl" || data.status === "CwlFeatureDisabled") {
            show(noCwlMessageEl); setText(noCwlMessageEl, data.message || data.error || "CWL indisponível.");
            hide(cwlActiveInfoEl); setText(cwlStatusTextEl, data.message || (data.error ? "Erro" : "Fora da CWL"));
            if(cwlStatusTextEl) cwlStatusTextEl.className = 'war-state ' + (data.status || 'notincwl').toLowerCase();
            return;
        }
        hide(noCwlMessageEl); show(cwlActiveInfoEl);
        setText(cwlStatusTextEl, "Em CWL"); if(cwlStatusTextEl) cwlStatusTextEl.className = 'war-state incwl'; // Supondo que 'incwl' seja uma classe válida
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
                        if(w.error) { roundHtml += `<p class="cwl-war-entry">Guerra (${w.war_tag || 'N/A'}): ${w.error}</p>`; }
                        else if(w.message) { roundHtml += `<p class="cwl-war-entry">${w.message}</p>`;}
                        else {
                            const cBadge = w.clan_badge_url ? `<img src="${w.clan_badge_url}" alt="Emblema ${w.clan_name}" style="height:18px; vertical-align:middle;">`:"";
                            const oBadge = w.opponent_badge_url ? `<img src="${w.opponent_badge_url}" alt="Emblema ${w.opponent_name}" style="height:18px; vertical-align:middle;">`:"";
                            roundHtml += `<p class="cwl-war-entry"><strong>${cBadge} ${w.clan_name}</strong> ${w.clan_stars}⭐ (${w.clan_destruction}) vs ${w.opponent_stars}⭐ (${w.opponent_destruction}) <strong>${oBadge} ${w.opponent_name}</strong><br><small>Estado: ${w.state} | ${w.time_key}: ${w.time_value} (${w.time_remaining})</small></p>`;
                        }
                    });
                } else { roundHtml += "<p>Nenhuma guerra nesta rodada.</p>"; }
                roundHtml += "</div>";
                setHtml(cwlRoundsInfoEl, cwlRoundsInfoEl.innerHTML + roundHtml);
            });
        } else { setHtml(cwlRoundsInfoEl, "<p>Nenhuma informação de rodada.</p>"); }
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
                const oppBadge = e.opponent_badge_url ? `<img src="${e.opponent_badge_url}" alt="Emblema ${e.opponent_name}" style="height:20px; vertical-align:middle; margin-right:5px;">` : "";
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
        const trophiesFilterText = filterTrophiesInput.value; // Mantém como texto para correspondência exata se necessário, ou converte para número se for comparação
        const roleFilter = filterRoleInput.value.toLowerCase();
        const rows = membersTableBodyEl.getElementsByTagName('tr');
        for (let i = 0; i < rows.length; i++) {
            const row = rows[i]; const cells = row.getElementsByTagName('td'); let displayRow = true;
            // A tabela agora tem 10 colunas (0-9)
            if (cells.length > 7) { // Verifica se a linha tem células de dados (Nome é cells[1], Observação é cells[8])
                if (nameFilter && !cells[1].textContent.toLowerCase().includes(nameFilter)) displayRow = false;
                if (thFilter && !cells[2].textContent.toLowerCase().includes(thFilter)) displayRow = false;
                if (leagueFilter && !cells[3].textContent.toLowerCase().includes(leagueFilter)) displayRow = false;
                if (trophiesFilterText) { // Adicionar lógica para > < = se necessário
                    const trophiesValue = parseInt(cells[4].textContent, 10);
                    if (isNaN(trophiesValue) || !cells[4].textContent.includes(trophiesFilterText)) displayRow = false; // Simples contains por enquanto
                }
                if (roleFilter && !cells[5].textContent.toLowerCase().includes(roleFilter)) displayRow = false;
            } else if (row.getElementsByTagName('th').length === 0 && cells.length < 2) { // Linha de 'nenhum membro' ou similar
                 displayRow = false; 
            }
            row.style.display = displayRow ? '' : 'none';
        }
    }
    if(filterNameInput) filterNameInput.addEventListener('input', applyMemberFilters);
    if(filterTHInput) filterTHInput.addEventListener('input', applyMemberFilters);
    if(filterLeagueInput) filterLeagueInput.addEventListener('input', applyMemberFilters);
    if(filterTrophiesInput) filterTrophiesInput.addEventListener('input', applyMemberFilters);
    if(filterRoleInput) filterRoleInput.addEventListener('input', applyMemberFilters);

    async function handleSaveObservation(playerTag, observationText, priority) {
        const payload = {
            player_tag: playerTag,
            observation_text: observationText,
            observation_priority: priority
        };
        const result = await fetchData('member_observation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (result && result.status === 'success') {
            showToast('Observação salva com sucesso!', 'success');
        } else {
            showToast(result.message || 'Falha ao salvar observação.', 'error');
        }
    }
    
    function updatePriorityVisuals(textarea, select) {
        const priority = select.value;
        textarea.classList.remove('priority-normal', 'priority-alert', 'priority-critical');
        select.classList.remove('priority-normal', 'priority-alert', 'priority-critical');

        if (priority === 'normal') {
            textarea.classList.add('priority-normal');
            select.classList.add('priority-normal');
        } else if (priority === 'alert') {
            textarea.classList.add('priority-alert');
            select.classList.add('priority-alert');
        } else if (priority === 'critical') {
            textarea.classList.add('priority-critical');
            select.classList.add('priority-critical');
        }
    }


    function populateMembersList(data) {
        setText(membersClanNameEl, data.clan_name ? `(${data.clan_name})` : '');
        if (data.error) { setHtml(membersTableBodyEl, `<tr><td colspan="10">${data.error}</td></tr>`); return; }
        setHtml(membersTableBodyEl, '');
        if (data.members && data.members.length > 0) {
            data.members.forEach((m, i) => {
                const r = membersTableBodyEl.insertRow();
                r.dataset.playerTag = m.tag; // Armazena a tag do jogador na linha

                setText(r.insertCell(), i + 1); 
                setText(r.insertCell(), m.name); 
                setText(r.insertCell(), `CV${m.town_hall || '?'}`);
                setText(r.insertCell(), m.league); 
                setText(r.insertCell(), m.trophies); 
                setText(r.insertCell(), m.role);
                setText(r.insertCell(), m.donations); 
                setText(r.insertCell(), m.received);

                // Coluna de Observação
                const obsCell = r.insertCell();
                const obsTextarea = document.createElement('textarea');
                obsTextarea.className = 'member-observation-text';
                obsTextarea.value = m.observation_text || '';
                obsTextarea.rows = 2;
                obsCell.appendChild(obsTextarea);

                // Coluna de Prioridade e Ações
                const actionCell = r.insertCell();
                const prioritySelect = document.createElement('select');
                prioritySelect.className = 'member-observation-priority';
                const priorities = { normal: 'Normal', alert: 'Alerta', critical: 'Crítico' };
                for (const value in priorities) {
                    const option = document.createElement('option');
                    option.value = value;
                    option.textContent = priorities[value];
                    if (value === (m.observation_priority || 'normal')) {
                        option.selected = true;
                    }
                    prioritySelect.appendChild(option);
                }
                actionCell.appendChild(prioritySelect);
                
                updatePriorityVisuals(obsTextarea, prioritySelect); // Cor inicial
                prioritySelect.addEventListener('change', () => updatePriorityVisuals(obsTextarea, prioritySelect));


                const saveButton = document.createElement('button');
                saveButton.className = 'save-observation-btn';
                saveButton.textContent = 'Salvar';
                saveButton.addEventListener('click', () => {
                    handleSaveObservation(m.tag, obsTextarea.value, prioritySelect.value);
                });
                actionCell.appendChild(saveButton);
            });
        } else { setHtml(membersTableBodyEl, '<tr><td colspan="10">Nenhum membro para exibir.</td></tr>'); }
        applyMemberFilters(); // Aplica filtros após popular
    }


    // --- CARREGAMENTO INICIAL E PERIÓDICO ---
    async function loadAllData() {
        const [clanData, membersData, currentWarDetailsData, warAttacksRemainingData, warLogData, cwlInfoData] = await Promise.all([
            fetchData('clan'), fetchData('members'), fetchData('current_war_details'),
            fetchData('war_attacks_remaining'), fetchData('war_log?limit=10'), fetchData('cwl_info')
        ]);
        populateClanInfo(clanData);
        populateMembersList(membersData);
        populateWarDetails(currentWarDetailsData); 
        populateWarAttacksRemaining(warAttacksRemainingData);
        populateWarLog(warLogData);
        populateCwlInfo(cwlInfoData);
        updateLastUpdated();
    }
    loadAllData();
    setInterval(loadAllData, 60000); // Atualiza a cada 60 segundos
});
