document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = ''; 
    const DEFAULT_BADGE_URL = '/static/images/default_badge.png'; // Defina um placeholder

    // --- ELEMENTOS DO DOM ---
    // Clã
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

    // Status da Guerra (Geral)
    const warStatusClanBadgeEl = document.getElementById('warStatusClanBadge');
    const warStatusTypeEl = document.getElementById('warStatusType');
    const warStatusOpponentBadgeEl = document.getElementById('warStatusOpponentBadge');
    const warStatusStateDescriptionEl = document.getElementById('warStatusStateDescription');
    const warStatusDetailsActiveEl = document.getElementById('warStatusDetailsActive');
    const warStatusOurClanNameEl = document.getElementById('warStatusOurClanName');
    const warStatusOurScoreEl = document.getElementById('warStatusOurScore');
    const warStatusOpponentNameEl = document.getElementById('warStatusOpponentName');
    const warStatusOpponentScoreEl = document.getElementById('warStatusOpponentScore');
    const warStatusTimeKeyEl = document.getElementById('warStatusTimeKey');
    const warStatusTimeValueEl = document.getElementById('warStatusTimeValue');
    const warStatusTimeRemainingEl = document.getElementById('warStatusTimeRemaining');
    const noWarStatusMessageEl = document.getElementById('noWarStatusMessage');

    // Detalhes da Guerra Atual
    const currentWarClanBadgeEl = document.getElementById('currentWarClanBadge');
    const currentWarTypeEl = document.getElementById('currentWarType');
    const currentWarOpponentBadgeEl = document.getElementById('currentWarOpponentBadge');
    const currentWarInfoEl = document.getElementById('currentWarInfo');
    const currentWarStateEl = document.getElementById('currentWarState');
    const currentWarOurClanNameEl = document.getElementById('currentWarOurClanName');
    const currentWarOurScoreEl = document.getElementById('currentWarOurScore');
    const currentWarOpponentNameEl = document.getElementById('currentWarOpponentName');
    const currentWarOpponentScoreEl = document.getElementById('currentWarOpponentScore');
    const currentWarTimeKeyEl = document.getElementById('currentWarTimeKey');
    const currentWarTimeValueEl = document.getElementById('currentWarTimeValue');
    const currentWarTimeRemainingEl = document.getElementById('currentWarTimeRemaining');
    const currentWarTeamSizeEl = document.querySelectorAll('#currentWarTeamSize'); // NodeList
    const currentWarAttacksPerMemberEl = document.getElementById('currentWarAttacksPerMember');
    const currentWarAttacksTableBodyEl = document.getElementById('currentWarAttacksTableBody');
    const noCurrentWarDetailsMessageEl = document.getElementById('noCurrentWarDetailsMessage');

    // Ataques Pendentes
    const attacksRemainingClanNameEl = document.getElementById('attacksRemainingClanName');
    const attacksRemainingListEl = document.getElementById('attacksRemainingList');
    const noWarForAttacksRemainingMessageEl = document.getElementById('noWarForAttacksRemainingMessage');

    // CWL
    const cwlDetailsEl = document.getElementById('cwlDetails');
    const cwlStatusTextEl = document.getElementById('cwlStatusText');
    const cwlActiveInfoEl = document.getElementById('cwlActiveInfo');
    const cwlSeasonEl = document.getElementById('cwlSeason');
    const cwlGroupStateEl = document.getElementById('cwlGroupState');
    const cwlGroupClansEl = document.getElementById('cwlGroupClans');
    const cwlRoundsInfoEl = document.getElementById('cwlRoundsInfo');
    const noCwlMessageEl = document.getElementById('noCwlMessage');

    // Histórico de Guerras
    const warLogLimitEl = document.getElementById('warLogLimit'); // Para mostrar o limite usado
    const warLogTableBodyEl = document.getElementById('warLogTableBody');
    const noWarLogMessageEl = document.getElementById('noWarLogMessage');

    // Membros e Filtros
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

    // --- FUNÇÕES HELPER ---
    async function fetchData(endpoint) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/${endpoint}`);
            if (!response.ok) {
                console.error(`HTTP error! status: ${response.status} for ${endpoint}`);
                const errorData = await response.json().catch(() => ({ error: `Falha ao carregar ${endpoint}. Status: ${response.status}` }));
                return { error: errorData.error || `Falha ao carregar ${endpoint}. Status: ${response.status}` };
            }
            return await response.json();
        } catch (error) {
            console.error(`Could not fetch data from ${endpoint}:`, error);
            return { error: `Erro de conexão ao buscar dados de ${endpoint}. Verifique o console para detalhes.` };
        }
    }

    function updateLastUpdated() {
        const now = new Date();
        lastUpdatedEl.textContent = `Última atualização: ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
    }

    function setText(element, text, defaultValue = '-') {
        if (element) element.textContent = text || defaultValue;
    }
    function setBadge(element, url) {
        if (element) {
            if (url) {
                element.src = url;
                element.style.display = 'inline-block';
            } else {
                element.src = DEFAULT_BADGE_URL; // Ou esconda: element.style.display = 'none';
                element.style.display = 'inline-block'; // Mostra placeholder
            }
        }
    }

    // --- FUNÇÕES DE POPULAÇÃO DE DADOS ---
    function populateClanInfo(data) {
        if (data.error || !data.name) {
            setText(clanNameHeaderEl, "Erro");
            setText(clanNameEl, data.error || "N/A");
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
        
        clanCapitalDistrictsEl.innerHTML = '';
        if (data.capital_districts && data.capital_districts.length > 0) {
            data.capital_districts.forEach(district => {
                const p = document.createElement('p');
                p.innerHTML = `<strong>${district.name || 'Distrito Desconhecido'}:</strong> Nível ${district.level || '?'}`;
                clanCapitalDistrictsEl.appendChild(p);
            });
        } else {
            clanCapitalDistrictsEl.innerHTML = '<p>Nenhum distrito da capital encontrado.</p>';
        }
    }

    function populateWarStatus(data) { // Visão geral da guerra
        if (data.error || data.status === "NotInWar" || !data.clan_name) {
            setText(warStatusTypeEl, data.type || "Guerra");
            noWarStatusMessageEl.textContent = data.message || data.error || "Nenhuma guerra ativa ou detalhes indisponíveis.";
            noWarStatusMessageEl.style.display = 'block';
            warStatusDetailsActiveEl.style.display = 'none';
            setBadge(warStatusClanBadgeEl, null);
            setBadge(warStatusOpponentBadgeEl, null);
            setText(warStatusStateDescriptionEl, data.state_description || data.status || (data.error ? "Erro" : "N/A"));
            if(warStatusStateDescriptionEl) warStatusStateDescriptionEl.className = 'war-state ' + (data.status || 'notinwar').toLowerCase();
            return;
        }

        noWarStatusMessageEl.style.display = 'none';
        warStatusDetailsActiveEl.style.display = 'block';

        setText(warStatusTypeEl, data.type);
        setText(warStatusStateDescriptionEl, data.state_description);
        if(warStatusStateDescriptionEl) warStatusStateDescriptionEl.className = 'war-state ' + (data.status || '').toLowerCase();
        
        setBadge(warStatusClanBadgeEl, data.clan_badge_url);
        setBadge(warStatusOpponentBadgeEl, data.opponent_badge_url);

        setText(warStatusOurClanNameEl, data.clan_name);
        setText(warStatusOurScoreEl, `${data.clan_stars || 0}⭐ (${data.clan_destruction || '0%'})`);
        setText(warStatusOpponentNameEl, data.opponent_name);
        setText(warStatusOpponentScoreEl, `${data.opponent_stars || 0}⭐ (${data.opponent_destruction || '0%'})`);
        setText(warStatusTimeKeyEl, data.time_key);
        setText(warStatusTimeValueEl, data.time_value);
        setText(warStatusTimeRemainingEl, data.time_remaining);
    }

    function populateCurrentWarDetails(data) {
        if (data.error || !data.war_data) {
            noCurrentWarDetailsMessageEl.textContent = data.error || "Nenhuma guerra ativa ou recente para detalhar.";
            noCurrentWarDetailsMessageEl.style.display = 'block';
            currentWarInfoEl.style.display = 'none';
            currentWarAttacksTableBodyEl.innerHTML = `<tr><td colspan="6">${data.error || "N/A"}</td></tr>`;
            return;
        }

        noCurrentWarDetailsMessageEl.style.display = 'none';
        currentWarInfoEl.style.display = 'block';
        const war = data.war_data;

        setText(currentWarTypeEl, war.type);
        setBadge(currentWarClanBadgeEl, war.clan_badge_url);
        setBadge(currentWarOpponentBadgeEl, war.opponent_badge_url);
        setText(currentWarStateEl, war.state_description);
        if(currentWarStateEl) currentWarStateEl.className = 'war-state ' + (war.status || '').toLowerCase();

        setText(currentWarOurClanNameEl, war.clan_name);
        setText(currentWarOurScoreEl, `${war.clan_stars || 0}⭐ (${war.clan_destruction || '0%'})`);
        setText(currentWarOpponentNameEl, war.opponent_name);
        setText(currentWarOpponentScoreEl, `${war.opponent_stars || 0}⭐ (${war.opponent_destruction || '0%'})`);
        
        setText(currentWarTimeKeyEl, war.time_key);
        setText(currentWarTimeValueEl, war.time_value);
        setText(currentWarTimeRemainingEl, war.time_remaining);

        currentWarTeamSizeEl.forEach(el => setText(el, war.team_size));
        setText(currentWarAttacksPerMemberEl, war.attacks_per_member);

        currentWarAttacksTableBodyEl.innerHTML = '';
        if (data.attacks && data.attacks.length > 0) {
            data.attacks.forEach(attack => {
                const row = currentWarAttacksTableBodyEl.insertRow();
                setText(row.insertCell(), attack.order);
                setText(row.insertCell(), `${attack.attacker_name || 'Desconhecido'} (CV${attack.attacker_townhall || '?'})`);
                setText(row.insertCell(), `${attack.defender_name || 'Desconhecido'} (CV${attack.defender_townhall || '?'})`);
                
                const starsCell = row.insertCell();
                setText(starsCell, `${'⭐'.repeat(attack.stars)}${'⚫'.repeat(3 - attack.stars)}`);
                starsCell.className = `stars-${attack.stars}`;

                setText(row.insertCell(), `${attack.destruction || 0}%`);
                setText(row.insertCell(), `${attack.duration || 0}s`);
            });
        } else {
            currentWarAttacksTableBodyEl.innerHTML = `<tr><td colspan="6">Nenhum ataque registrado nesta guerra.</td></tr>`;
        }
    }

    function populateWarAttacksRemaining(data) {
        setText(attacksRemainingClanNameEl, data.clan_name || "Clã");
        if (data.error || !data.members_pending || data.members_pending.length === 0) {
            attacksRemainingListEl.innerHTML = `<p>${data.message || data.error || "Todos os ataques foram realizados ou não há guerra em andamento."}</p>`;
            noWarForAttacksRemainingMessageEl.style.display = (data.members_pending && data.members_pending.length > 0) ? 'none' : 'block';
            if (data.message && !(data.members_pending && data.members_pending.length > 0)) {
                 noWarForAttacksRemainingMessageEl.textContent = data.message;
            }
            return;
        }
        
        noWarForAttacksRemainingMessageEl.style.display = 'none';
        attacksRemainingListEl.innerHTML = '';
        data.members_pending.forEach(member => {
            const p = document.createElement('p');
            p.innerHTML = `<strong>${member.name}</strong> (CV${member.town_hall}) - ${member.attacks_left} ataque(s) restante(s)`;
            attacksRemainingListEl.appendChild(p);
        });
    }

    function populateCwlInfo(data) {
        if (data.error || data.status === "NotInCwl") {
            noCwlMessageEl.textContent = data.message || data.error || "O clã não está em CWL ou informações não disponíveis.";
            noCwlMessageEl.style.display = 'block';
            cwlActiveInfoEl.style.display = 'none';
            setText(cwlStatusTextEl, data.message || (data.error ? "Erro" : "Fora da CWL"));
            return;
        }

        noCwlMessageEl.style.display = 'none';
        cwlActiveInfoEl.style.display = 'block';
        setText(cwlStatusTextEl, "Em CWL");
        
        setText(cwlSeasonEl, data.season);
        setText(cwlGroupStateEl, data.state);

        cwlGroupClansEl.innerHTML = '';
        if (data.clans_in_group && data.clans_in_group.length > 0) {
            data.clans_in_group.forEach(clan => {
                const p = document.createElement('p');
                const badgeImg = clan.badge_url ? `<img src="${clan.badge_url}" alt="Emblema" style="height:20px; vertical-align:middle; margin-right:5px;">` : "";
                p.innerHTML = `${badgeImg}<strong>${clan.name}</strong> (#${clan.tag}) - Nível ${clan.level}`;
                cwlGroupClansEl.appendChild(p);
            });
        } else {
            cwlGroupClansEl.innerHTML = '<p>Nenhum clã no grupo.</p>';
        }
        
        cwlRoundsInfoEl.innerHTML = '';
        if (data.rounds && data.rounds.length > 0) {
            data.rounds.forEach(round => {
                const roundDiv = document.createElement('div');
                roundDiv.className = 'cwl-round';
                const roundTitle = document.createElement('h4');
                setText(roundTitle, `Rodada ${round.round_number}`);
                roundDiv.appendChild(roundTitle);

                if (round.wars && round.wars.length > 0) {
                    round.wars.forEach(war => {
                        const warP = document.createElement('p');
                        warP.className = 'cwl-war-entry';
                        if (war.error) {
                            setText(warP, `Guerra (${war.war_tag}): ${war.error}`);
                        } else {
                            const clanBadge = war.clan_badge_url ? `<img src="${war.clan_badge_url}" alt="" style="height:18px; vertical-align:middle;">` : "";
                            const oppBadge = war.opponent_badge_url ? `<img src="${war.opponent_badge_url}" alt="" style="height:18px; vertical-align:middle;">` : "";
                            warP.innerHTML = 
                                `<strong>${clanBadge} ${war.clan_name}</strong> ${war.clan_stars}⭐ (${war.clan_destruction}) 
                                 vs 
                                 ${war.opponent_stars}⭐ (${war.opponent_destruction}) <strong>${oppBadge} ${war.opponent_name}</strong>
                                 <br><small>Estado: ${war.state} | ${war.time_key}: ${war.time_value} (${war.time_remaining})</small>`;
                        }
                        roundDiv.appendChild(warP);
                    });
                } else {
                    setText(roundDiv.appendChild(document.createElement('p')), "Nenhuma guerra nesta rodada.");
                }
                cwlRoundsInfoEl.appendChild(roundDiv);
            });
        } else {
            setText(cwlRoundsInfoEl, "Nenhuma informação de rodada disponível.");
        }
    }

    function populateWarLog(data) {
        setText(warLogLimitEl, data.log ? data.log.length : '10'); // Atualiza o limite exibido
        if (data.error) {
            noWarLogMessageEl.textContent = data.error;
            noWarLogMessageEl.style.display = 'block';
            warLogTableBodyEl.innerHTML = `<tr><td colspan="6">${data.error}</td></tr>`;
            return;
        }

        noWarLogMessageEl.style.display = 'none';
        warLogTableBodyEl.innerHTML = '';
        if (data.log && data.log.length > 0) {
            data.log.forEach(entry => {
                const row = warLogTableBodyEl.insertRow();
                setText(row.insertCell(), entry.end_time);
                
                const opponentCell = row.insertCell();
                const oppBadgeImg = entry.opponent_badge_url ? `<img src="${entry.opponent_badge_url}" alt="" style="height:20px; vertical-align:middle; margin-right:5px;">` : "";
                opponentCell.innerHTML = `${oppBadgeImg}${entry.opponent_name || 'Desconhecido'}`;

                setText(row.insertCell(), `${entry.clan_stars}⭐ (${entry.clan_destruction}%) x ${entry.opponent_stars}⭐ (${entry.opponent_destruction}%)`);
                
                const resultCell = row.insertCell();
                setText(resultCell, entry.result);
                resultCell.className = entry.result ? `war-result-${entry.result.toLowerCase()}` : '';

                setText(row.insertCell(), entry.team_size);
                setText(row.insertCell(), entry.is_cwl ? "CWL" : "Normal");
            });
        } else {
            warLogTableBodyEl.innerHTML = `<tr><td colspan="6">Nenhum registro de guerra encontrado.</td></tr>`;
        }
    }

    function applyMemberFilters() {
        // ... (função de filtro de membros existente, já fornecida anteriormente) ...
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

            if (cells.length > 5) { 
                const memberName = cells[1].textContent.toLowerCase();
                const memberTH = cells[2].textContent.toLowerCase();
                const memberLeague = cells[3].textContent.toLowerCase();
                const memberTrophies = cells[4].textContent;
                const memberRole = cells[5].textContent.toLowerCase();

                if (nameFilter && !memberName.includes(nameFilter)) displayRow = false;
                if (thFilter && !memberTH.includes(thFilter)) displayRow = false;
                if (leagueFilter && !memberLeague.includes(leagueFilter)) displayRow = false;
                if (trophiesFilterText && !memberTrophies.includes(trophiesFilterText)) displayRow = false;
                if (roleFilter && !memberRole.includes(roleFilter)) displayRow = false;
            } else if (row.getElementsByTagName('th').length === 0) {
                displayRow = false; 
            }
            row.style.display = displayRow ? '' : 'none';
        }
    }
    
    filterNameInput.addEventListener('input', applyMemberFilters);
    filterTHInput.addEventListener('input', applyMemberFilters);
    filterLeagueInput.addEventListener('input', applyMemberFilters);
    filterTrophiesInput.addEventListener('input', applyMemberFilters);
    filterRoleInput.addEventListener('input', applyMemberFilters);

    function populateMembersList(data) {
        // ... (função de popular membros existente, já fornecida anteriormente) ...
        setText(membersClanNameEl, data.clan_name ? `(${data.clan_name})` : '');
        if (data.error) {
            membersTableBodyEl.innerHTML = `<tr><td colspan="8">${data.error}</td></tr>`;
            return;
        }
        membersTableBodyEl.innerHTML = '';
        if (data.members && data.members.length > 0) {
            data.members.forEach((member, index) => {
                const row = membersTableBodyEl.insertRow();
                setText(row.insertCell(), index + 1);
                setText(row.insertCell(), member.name);
                setText(row.insertCell(), `CV${member.town_hall || '?'}`);
                setText(row.insertCell(), member.league);
                setText(row.insertCell(), member.trophies);
                setText(row.insertCell(), member.role);
                setText(row.insertCell(), member.donations);
                setText(row.insertCell(), member.received);
            });
        } else {
            membersTableBodyEl.innerHTML = '<tr><td colspan="8">Nenhum membro encontrado.</td></tr>';
        }
        applyMemberFilters();
    }

    // --- CARREGAMENTO INICIAL E PERIÓDICO ---
    async function loadAllData() {
        // Usar Promise.all para buscar dados em paralelo onde fizer sentido
        const [
            clanData, membersData, warStatusData, 
            currentWarDetailsData, warAttacksRemainingData, 
            warLogData, cwlInfoData
        ] = await Promise.all([
            fetchData('clan'),
            fetchData('members'),
            fetchData('war'), // Visão geral da guerra
            fetchData('current_war_details'),
            fetchData('war_attacks_remaining'),
            fetchData('war_log?limit=10'), // Pega as últimas 10 por padrão
            fetchData('cwl_info')
        ]);

        populateClanInfo(clanData);
        populateMembersList(membersData);
        populateWarStatus(warStatusData);
        populateCurrentWarDetails(currentWarDetailsData);
        populateWarAttacksRemaining(warAttacksRemainingData);
        populateWarLog(warLogData);
        populateCwlInfo(cwlInfoData);
        
        updateLastUpdated();
    }

    loadAllData();
    setInterval(loadAllData, 60000); // Atualiza a cada 60 segundos
});
