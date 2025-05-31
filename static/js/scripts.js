document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = ''; // Como o JS é servido pelo mesmo host, podemos usar caminhos relativos

    // Elementos do DOM
    const clanNameHeaderEl = document.getElementById('clanNameHeader');
    const clanBadgeHeaderEl = document.getElementById('clanBadgeHeader');

    const clanNameEl = document.getElementById('clanName');
    const clanTagEl = document.getElementById('clanTag');
    const clanLevelEl = document.getElementById('clanLevel');
    const clanPointsEl = document.getElementById('clanPoints');
    const clanMemberCountEl = document.getElementById('clanMemberCount');
    const clanCapitalPointsEl = document.getElementById('clanCapitalPoints');
    const clanWarWinsEl = document.getElementById('clanWarWins');
    const clanLocationEl = document.getElementById('clanLocation');
    const clanTypeEl = document.getElementById('clanType');
    const clanDescriptionEl = document.getElementById('clanDescription');
    const clanBadgeEl = document.getElementById('clanBadge');

    const warTypeEl = document.getElementById('warType');
    const warStateDescriptionEl = document.getElementById('warStateDescription');
    const warDetailsActiveEl = document.getElementById('warDetailsActive');
    const noWarMessageEl = document.getElementById('noWarMessage');
    const warOurClanNameEl = document.getElementById('warOurClanName');
    const warOurScoreEl = document.getElementById('warOurScore');
    const warOpponentNameEl = document.getElementById('warOpponentName');
    const warOpponentScoreEl = document.getElementById('warOpponentScore');
    const warTimeKeyEl = document.getElementById('warTimeKey');
    const warTimeValueEl = document.getElementById('warTimeValue');
    const warTimeRemainingEl = document.getElementById('warTimeRemaining');
    const warClanBadgeEl = document.getElementById('warClanBadge');
    const warOpponentBadgeEl = document.getElementById('warOpponentBadge');


    const membersClanNameEl = document.getElementById('membersClanName');
    const membersTableBodyEl = document.getElementById('membersTableBody');

    const botVersionEl = document.getElementById('botVersion');
    const lastUpdatedEl = document.getElementById('lastUpdated');

    // Elementos dos filtros de membros
    const filterNameInput = document.getElementById('filterName');
    const filterTHInput = document.getElementById('filterTH');
    const filterLeagueInput = document.getElementById('filterLeague');
    const filterTrophiesInput = document.getElementById('filterTrophies');
    const filterRoleInput = document.getElementById('filterRole');


    // Função para buscar dados
    async function fetchData(endpoint) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/${endpoint}`);
            if (!response.ok) {
                console.error(`HTTP error! status: ${response.status} for ${endpoint}`);
                return { error: `Falha ao carregar dados de ${endpoint}. Status: ${response.status}` };
            }
            return await response.json();
        } catch (error) {
            console.error(`Could not fetch data from ${endpoint}:`, error);
            return { error: `Erro de conexão ao buscar dados de ${endpoint}.` };
        }
    }

    function updateLastUpdated() {
        const now = new Date();
        lastUpdatedEl.textContent = `Última atualização: ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
    }

    // Preencher Informações do Clã
    function populateClanInfo(data) {
        if (data.error || !data.name) {
            clanNameHeaderEl.textContent = "Erro";
            clanNameEl.textContent = data.error || "N/A";
            console.error("Erro ao popular dados do clã:", data.error);
            return;
        }
        clanNameHeaderEl.textContent = data.name;
        clanNameEl.textContent = data.name;
        clanTagEl.textContent = data.tag || '-';
        clanLevelEl.textContent = data.level || '-';
        clanPointsEl.textContent = data.points || '-';
        clanMemberCountEl.textContent = data.member_count || '-';
        clanCapitalPointsEl.textContent = data.capital_points || '-';
        clanWarWinsEl.textContent = data.war_wins || '-';
        clanLocationEl.textContent = data.location || '-';
        clanTypeEl.textContent = data.type || '-';
        clanDescriptionEl.textContent = data.description || 'Sem descrição.';
        botVersionEl.textContent = data.version || '?'; 

        if (data.badge_url) {
            clanBadgeHeaderEl.src = data.badge_url;
            clanBadgeHeaderEl.style.display = 'inline-block';
            clanBadgeEl.src = data.badge_url;
            clanBadgeEl.style.display = 'inline-block';
        } else {
            clanBadgeHeaderEl.style.display = 'none';
            clanBadgeEl.style.display = 'none';
        }
    }

    // Preencher Status da Guerra
    function populateWarInfo(data) {
        if (data.error) {
            warTypeEl.textContent = "Erro ao carregar guerra";
            noWarMessageEl.textContent = data.error;
            noWarMessageEl.style.display = 'block';
            warDetailsActiveEl.style.display = 'none';
            console.error("Erro ao popular dados da guerra:", data.error);
            return;
        }

        warTypeEl.textContent = data.type || "Guerra";
        warStateDescriptionEl.textContent = data.state_description || data.status || '-';
        warStateDescriptionEl.className = 'war-state ' + (data.status || 'notInWar').toLowerCase();


        if (data.status === "NotInWar" || data.status === "PrivateWarLog" || !data.clan_name) { // Adicionado !data.clan_name para cobrir casos onde a guerra não tem detalhes
            noWarMessageEl.textContent = data.message || "Nenhuma guerra ativa ou detalhes indisponíveis.";
            noWarMessageEl.style.display = 'block';
            warDetailsActiveEl.style.display = 'none';
            warClanBadgeEl.style.display = 'none';
            warOpponentBadgeEl.style.display = 'none';
        } else {
            noWarMessageEl.style.display = 'none';
            warDetailsActiveEl.style.display = 'block';

            warOurClanNameEl.textContent = data.clan_name || 'Nosso Clã';
            warOurScoreEl.textContent = `${data.clan_stars || 0}⭐ (${data.clan_destruction || '0%'})`;
            warOpponentNameEl.textContent = data.opponent_name || 'Oponente';
            warOpponentScoreEl.textContent = `${data.opponent_stars || 0}⭐ (${data.opponent_destruction || '0%'})`;

            warTimeKeyEl.textContent = data.time_key || 'Tempo:';
            warTimeValueEl.textContent = data.time_value || '-';
            warTimeRemainingEl.textContent = data.time_remaining || '-';

            if (data.clan_badge_url) {
                warClanBadgeEl.src = data.clan_badge_url;
                warClanBadgeEl.style.display = 'inline-block';
            } else {
                warClanBadgeEl.style.display = 'none';
            }
            if (data.opponent_badge_url) {
                warOpponentBadgeEl.src = data.opponent_badge_url;
                warOpponentBadgeEl.style.display = 'inline-block';
            } else {
                warOpponentBadgeEl.style.display = 'none';
            }
        }
    }
    
    // Função para aplicar os filtros de membros
    function applyMemberFilters() {
        const nameFilter = filterNameInput.value.toLowerCase();
        const thFilter = filterTHInput.value.toLowerCase().replace(/\s/g, ''); // Remove espaços, ex: "cv 12" -> "cv12"
        const leagueFilter = filterLeagueInput.value.toLowerCase();
        const trophiesFilterText = filterTrophiesInput.value;
        const roleFilter = filterRoleInput.value.toLowerCase();

        const rows = membersTableBodyEl.getElementsByTagName('tr');

        for (let i = 0; i < rows.length; i++) {
            const row = rows[i];
            const cells = row.getElementsByTagName('td');
            let displayRow = true;

            // Células: # (0), Nome (1), CV (2), Liga (3), Troféus (4), Cargo (5), Doações (6), Recebidas (7)
            if (cells.length > 5) { 
                const memberName = cells[1].textContent.toLowerCase();
                const memberTH = cells[2].textContent.toLowerCase(); // ex: "cv17"
                const memberLeague = cells[3].textContent.toLowerCase();
                const memberTrophies = cells[4].textContent; // ex: "5117"
                const memberRole = cells[5].textContent.toLowerCase();

                if (nameFilter && !memberName.includes(nameFilter)) {
                    displayRow = false;
                }
                if (thFilter && !memberTH.includes(thFilter)) {
                    displayRow = false;
                }
                if (leagueFilter && !memberLeague.includes(leagueFilter)) {
                    displayRow = false;
                }
                // Filtro de troféus simples: verifica se o texto do filtro está contido nos troféus do membro
                if (trophiesFilterText && !memberTrophies.includes(trophiesFilterText)) {
                    displayRow = false;
                }
                if (roleFilter && !memberRole.includes(roleFilter)) {
                    displayRow = false;
                }
            } else if (row.getElementsByTagName('th').length === 0) { // Não aplicar em linhas de cabeçalho, se houver, nem em linhas malformadas
                displayRow = false; 
            }

            row.style.display = displayRow ? '' : 'none';
        }
    }

    // Adicionar event listeners aos inputs de filtro
    filterNameInput.addEventListener('input', applyMemberFilters);
    filterTHInput.addEventListener('input', applyMemberFilters);
    filterLeagueInput.addEventListener('input', applyMemberFilters);
    filterTrophiesInput.addEventListener('input', applyMemberFilters);
    filterRoleInput.addEventListener('input', applyMemberFilters);

    // Preencher Lista de Membros
    function populateMembersList(data) {
        if (data.error) {
            membersClanNameEl.textContent = "Erro ao carregar membros";
            membersTableBodyEl.innerHTML = `<tr><td colspan="8">${data.error}</td></tr>`;
            console.error("Erro ao popular lista de membros:", data.error);
            return;
        }

        membersClanNameEl.textContent = data.clan_name ? `(${data.clan_name})` : '';
        membersTableBodyEl.innerHTML = ''; // Limpa a tabela

        if (data.members && data.members.length > 0) {
            data.members.forEach((member, index) => {
                const row = membersTableBodyEl.insertRow();
                row.insertCell().textContent = index + 1;
                row.insertCell().textContent = member.name || '-';
                row.insertCell().textContent = `CV${member.town_hall || '?'}`;
                row.insertCell().textContent = member.league || 'N/A';
                row.insertCell().textContent = member.trophies || '0';
                row.insertCell().textContent = member.role || '-';
                row.insertCell().textContent = member.donations || '0';
                row.insertCell().textContent = member.received || '0';
            });
        } else {
            membersTableBodyEl.innerHTML = '<tr><td colspan="8">Nenhum membro encontrado.</td></tr>';
        }
        // Aplicar filtros após popular a tabela, caso algum filtro já esteja preenchido
        applyMemberFilters();
    }

    // Carregar todos os dados
    async function loadAllData() {
        const clanData = await fetchData('clan');
        populateClanInfo(clanData);

        const warData = await fetchData('war');
        populateWarInfo(warData);

        const membersData = await fetchData('members');
        populateMembersList(membersData); // Esta função já chama applyMemberFilters

        updateLastUpdated();
    }

    // Carregar dados inicialmente e depois periodicamente
    loadAllData();
    setInterval(loadAllData, 60000); // Atualiza a cada 60 segundos
});
