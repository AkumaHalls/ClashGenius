document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = ''; // Caminhos relativos funcionam bem

    // Elementos do DOM para navegação SPA
    const mainNavLinks = document.querySelectorAll('.main-nav a');
    const contentSections = document.querySelectorAll('main > section');

    // Elementos do DOM - Cabeçalho
    const clanNameHeaderEl = document.getElementById('clanNameHeader');
    const clanBadgeHeaderEl = document.getElementById('clanBadgeHeader');

    // Elementos do DOM - Seção Clã
    const clanNameEl = document.getElementById('clanName');
    const clanTagEl = document.getElementById('clanTag');
    const clanLevelEl = document.getElementById('clanLevel');
    // ... (outros elementos da seção Clã como antes) ...
    const clanPointsEl = document.getElementById('clanPoints');
    const clanMemberCountEl = document.getElementById('clanMemberCount');
    const clanCapitalPointsEl = document.getElementById('clanCapitalPoints');
    const clanWarWinsEl = document.getElementById('clanWarWins');
    const clanLocationEl = document.getElementById('clanLocation');
    const clanTypeEl = document.getElementById('clanType');
    const clanDescriptionEl = document.getElementById('clanDescription');
    const clanBadgeEl = document.getElementById('clanBadge');


    // Elementos do DOM - Seção Guerra
    // ... (elementos da seção Guerra como antes) ...
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
    const warTeamSizeEl = document.getElementById('warTeamSize');
    const warAttacksPerMemberEl = document.getElementById('warAttacksPerMember');


    // Elementos do DOM - Seção Membros
    const membersClanNameEl = document.getElementById('membersClanName');
    const membersTableBodyEl = document.getElementById('membersTableBody');

    // Elementos do DOM - Seção CWL
    const cwlSeasonEl = document.getElementById('cwlSeason');
    const cwlStateEl = document.getElementById('cwlState');
    const cwlRoundsContainerEl = document.getElementById('cwlRoundsContainer');
    const noCwlMessageEl = document.getElementById('noCwlMessage');

    // Elementos do DOM - Seção Log de Eventos
    const eventsLogContainerEl = document.getElementById('eventsLogContainer');

    // Elementos do DOM - Modal Detalhes do Jogador
    const playerDetailsModalEl = document.getElementById('playerDetailsModal');
    // ... (IDs para cada span dentro do modal) ...
    const modalPlayerNameEl = document.getElementById('modalPlayerName');
    const modalPlayerTagEl = document.getElementById('modalPlayerTag');
    const modalPlayerTHEl = document.getElementById('modalPlayerTH');
    const modalPlayerLevelEl = document.getElementById('modalPlayerLevel');
    const modalPlayerLeagueIconEl = document.getElementById('modalPlayerLeagueIcon');
    const modalPlayerLeagueEl = document.getElementById('modalPlayerLeague');
    const modalPlayerTrophiesEl = document.getElementById('modalPlayerTrophies');
    const modalPlayerBestTrophiesEl = document.getElementById('modalPlayerBestTrophies');
    const modalPlayerClanNameEl = document.getElementById('modalPlayerClanName');
    const modalPlayerRoleEl = document.getElementById('modalPlayerRole');
    const modalPlayerDonationsEl = document.getElementById('modalPlayerDonations');
    const modalPlayerReceivedEl = document.getElementById('modalPlayerReceived');
    const modalPlayerWarStarsEl = document.getElementById('modalPlayerWarStars');
    const modalPlayerAttackWinsEl = document.getElementById('modalPlayerAttackWins');
    const modalPlayerHeroesEl = document.getElementById('modalPlayerHeroes');
    const modalPlayerTroopsEl = document.getElementById('modalPlayerTroops');
    const modalPlayerSpellsEl = document.getElementById('modalPlayerSpells');
    const modalPlayerAchievementsEl = document.getElementById('modalPlayerAchievements');


    // Elementos do DOM - Rodapé
    const botVersionEl = document.getElementById('botVersion');
    const lastUpdatedEl = document.getElementById('lastUpdated');

    // --- Lógica da Navegação SPA ---
    function navigateToSection(sectionId) {
        contentSections.forEach(section => {
            section.style.display = section.id === sectionId ? 'block' : 'none';
            section.classList.toggle('current-section', section.id === sectionId);
        });
        mainNavLinks.forEach(link => {
            link.classList.toggle('active', link.dataset.section === sectionId);
        });
        // Salva a seção atual no localStorage para persistir a navegação
        localStorage.setItem('currentPanelSection', sectionId);
        // Rola para o topo da página ao mudar de seção
        window.scrollTo(0, 0);
    }

    mainNavLinks.forEach(link => {
        link.addEventListener('click', (event) => {
            event.preventDefault();
            const targetSectionId = link.dataset.section;
            navigateToSection(targetSectionId);
            // Recarregar dados específicos da seção se necessário, ou confiar no polling geral
            if (targetSectionId === 'cwl-info-section') loadCwlData();
            if (targetSectionId === 'events-log-section') loadEventsLog();
        });
    });

    // Função para buscar dados da API
    async function fetchData(endpoint, isJson = true) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/${endpoint}`);
            if (!response.ok) {
                console.error(`HTTP error! status: ${response.status} for ${endpoint}`);
                const errorText = await response.text(); // Tenta pegar mais detalhes do erro
                return { error: `Falha ao carregar ${endpoint}. Status: ${response.status}. ${errorText}` };
            }
            return isJson ? await response.json() : await response.text();
        } catch (error) {
            console.error(`Fetch error for ${endpoint}:`, error);
            return { error: `Erro de conexão para ${endpoint}.` };
        }
    }

    function updateLastUpdated() {
        const now = new Date();
        lastUpdatedEl.textContent = `Última Atualização: ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
    }

    // --- Funções para Popular Seções ---
    function populateClanInfo(data) {
        if (data.error || !data.name) {
            clanNameHeaderEl.textContent = "Erro"; clanNameEl.textContent = data.error || "N/A"; return;
        }
        clanNameHeaderEl.textContent = data.name;
        if (data.badge_url) { clanBadgeHeaderEl.src = data.badge_url; clanBadgeHeaderEl.style.display = 'inline-block'; }
        else { clanBadgeHeaderEl.style.display = 'none'; }

        clanNameEl.textContent = data.name;
        clanTagEl.textContent = data.tag || '-';
        if (data.badge_url) { clanBadgeEl.src = data.badge_url; clanBadgeEl.style.display = 'inline-block'; }
        else { clanBadgeEl.style.display = 'none'; }

        clanLevelEl.textContent = data.level || '-';
        clanPointsEl.textContent = data.points || '-';
        clanMemberCountEl.textContent = data.member_count || '-';
        clanCapitalPointsEl.textContent = data.capital_points || '-';
        clanWarWinsEl.textContent = data.war_wins || '-';
        clanLocationEl.textContent = data.location || '-';
        clanTypeEl.textContent = data.type || '-';
        clanDescriptionEl.innerHTML = data.description ? data.description.replace(/\n/g, '<br>') : 'Sem descrição.';
        botVersionEl.textContent = data.version || '?';
    }

    function populateWarInfo(data) {
        if (data.error) {
            warTypeEl.textContent = "Erro"; noWarMessageEl.textContent = data.error;
            noWarMessageEl.style.display = 'block'; warDetailsActiveEl.style.display = 'none'; return;
        }
        warTypeEl.textContent = data.type || "Guerra";
        warStateDescriptionEl.textContent = data.state_description || data.status || '-';
        warStateDescriptionEl.className = 'war-state ' + (data.status ? data.status.toLowerCase() : 'notinwar');

        if (data.status === "NotInWar" || data.status === "PrivateWarLog") {
            noWarMessageEl.textContent = data.message || "Nenhuma guerra ativa ou log privado.";
            noWarMessageEl.style.display = 'block'; warDetailsActiveEl.style.display = 'none';
            if (data.clan_badge_url) { warClanBadgeEl.src = data.clan_badge_url; warClanBadgeEl.style.display = 'inline-block'; } else { warClanBadgeEl.style.display = 'none'; }
            warOpponentBadgeEl.style.display = 'none';
        } else {
            noWarMessageEl.style.display = 'none'; warDetailsActiveEl.style.display = 'block';
            warOurClanNameEl.textContent = data.clan_name || 'Nosso Clã';
            warOurScoreEl.textContent = `${data.clan_stars || 0}⭐ (${data.clan_destruction || '0%'})`;
            warOpponentNameEl.textContent = data.opponent_name || 'Oponente';
            warOpponentScoreEl.textContent = `${data.opponent_stars || 0}⭐ (${data.opponent_destruction || '0%'})`;
            warTimeKeyEl.textContent = data.time_key || 'Tempo:';
            warTimeValueEl.textContent = data.time_value || '-';
            warTimeRemainingEl.textContent = data.time_remaining || '-';
            if (data.clan_badge_url) { warClanBadgeEl.src = data.clan_badge_url; warClanBadgeEl.style.display = 'inline-block'; } else { warClanBadgeEl.style.display = 'none'; }
            if (data.opponent_badge_url) { warOpponentBadgeEl.src = data.opponent_badge_url; warOpponentBadgeEl.style.display = 'inline-block'; } else { warOpponentBadgeEl.style.display = 'none'; }
            warTeamSizeEl.textContent = data.team_size || '-';
            warAttacksPerMemberEl.textContent = data.attacks_per_member || '-';
        }
    }

    function populateMembersList(data) {
        if (data.error) {
            membersClanNameEl.textContent = "(Erro)";
            membersTableBodyEl.innerHTML = `<tr><td colspan="9">${data.error}</td></tr>`; return;
        }
        membersClanNameEl.textContent = data.clan_name ? `(${data.clan_name})` : '';
        membersTableBodyEl.innerHTML = '';
        if (data.members && data.members.length > 0) {
            data.members.forEach((member, index) => {
                const row = membersTableBodyEl.insertRow();
                row.insertCell().textContent = index + 1;
                const nameCell = row.insertCell();
                nameCell.textContent = member.name || '-';
                nameCell.title = `Tag: ${member.tag}`; // Adiciona tag no hover
                row.insertCell().textContent = `CV${member.town_hall || '?'}`;
                const leagueCell = row.insertCell();
                if(member.league_icon_url) {
                    leagueCell.innerHTML = `<img src="${member.league_icon_url}" alt="${member.league}" style="height:20px; vertical-align:middle;"> ${member.league || 'N/A'}`;
                } else {
                    leagueCell.textContent = member.league || 'N/A';
                }
                row.insertCell().textContent = member.trophies || '0';
                row.insertCell().textContent = member.role || '-';
                row.insertCell().textContent = member.donations || '0';
                row.insertCell().textContent = member.received || '0';
                const actionCell = row.insertCell();
                const detailsButton = document.createElement('button');
                detailsButton.textContent = 'Ver';
                detailsButton.className = 'player-details-button';
                detailsButton.onclick = () => openPlayerDetailsModal(member.tag);
                actionCell.appendChild(detailsButton);
            });
        } else {
            membersTableBodyEl.innerHTML = '<tr><td colspan="9">Nenhum membro encontrado.</td></tr>';
        }
    }

    async function openPlayerDetailsModal(playerTag) {
        modalPlayerNameEl.textContent = "Carregando...";
        playerDetailsModalEl.style.display = 'block';
        const data = await fetchData(`player/${playerTag.replace('#', '')}`); // Remove # para URL
        if (data.error) {
            modalPlayerNameEl.textContent = "Erro ao carregar jogador";
            // Limpar outros campos ou mostrar erro
            modalPlayerTagEl.textContent = playerTag;
            return;
        }
        modalPlayerNameEl.textContent = data.name;
        modalPlayerTagEl.textContent = data.tag;
        modalPlayerTHEl.textContent = data.town_hall;
        modalPlayerLevelEl.textContent = data.exp_level;
        if(data.league_icon_url){ modalPlayerLeagueIconEl.src = data.league_icon_url; modalPlayerLeagueIconEl.style.display='inline-block';}
        else {modalPlayerLeagueIconEl.style.display='none';}
        modalPlayerLeagueEl.textContent = data.league;
        modalPlayerTrophiesEl.textContent = data.trophies;
        modalPlayerBestTrophiesEl.textContent = data.best_trophies;
        modalPlayerClanNameEl.textContent = data.clan_name;
        modalPlayerRoleEl.textContent = data.role;
        modalPlayerDonationsEl.textContent = data.donations;
        modalPlayerReceivedEl.textContent = data.received;
        modalPlayerWarStarsEl.textContent = data.war_stars;
        modalPlayerAttackWinsEl.textContent = data.attack_wins;

        modalPlayerHeroesEl.innerHTML = data.heroes && data.heroes.length > 0 ?
            data.heroes.map(h => `<div>${h.name} (${h.village}): <strong>${h.level}</strong>/${h.max_level}</div>`).join('') : 'Nenhum herói.';
        
        // Filtrar tropas e feitiços principais (exemplo: apenas tropas de elixir e dark da vila principal)
        const mainVillageTroops = data.troops ? data.troops.filter(t => t.village === 'home' && (t.name.includes('Barbarian') || t.name.includes('Archer') || t.name.includes('Goblin') || t.name.includes('Giant') || t.name.includes('Dragon') || t.name.includes('P.E.K.K.A') || t.name.includes('Hog Rider') || t.name.includes('Golem'))) : [];
        modalPlayerTroopsEl.innerHTML = mainVillageTroops.length > 0 ?
            mainVillageTroops.map(t => `<div>${t.name}: <strong>${t.level}</strong>/${t.max_level}</div>`).join('') : 'Nenhuma tropa principal listada.';
        
        const mainVillageSpells = data.spells ? data.spells.filter(s => s.village === 'home') : [];
        modalPlayerSpellsEl.innerHTML = mainVillageSpells.length > 0 ?
            mainVillageSpells.map(s => `<div>${s.name}: <strong>${s.level}</strong>/${s.max_level}</div>`).join('') : 'Nenhum feitiço.';
        
        modalPlayerAchievementsEl.innerHTML = data.achievements && data.achievements.length > 0 ?
            data.achievements.map(a => `<li>${a.name}: ${a.stars}⭐ (${a.value}/${a.target})</li>`).join('') : 'Nenhuma conquista destacada.';
    }

    window.closeModal = function(modalId) { // Torna a função global para o onclick no HTML
        const modal = document.getElementById(modalId);
        if (modal) modal.style.display = 'none';
    }
    // Fechar modal clicando fora do conteúdo
    window.onclick = function(event) {
        if (event.target == playerDetailsModalEl) {
            playerDetailsModalEl.style.display = "none";
        }
    }


    function populateEventsLog(data) {
        if (data.error) {
            eventsLogContainerEl.innerHTML = `<p>${data.error}</p>`; return;
        }
        if (data.events && data.events.length > 0) {
            eventsLogContainerEl.innerHTML = data.events.map(event => `<p>${event}</p>`).join('');
        } else {
            eventsLogContainerEl.innerHTML = '<p>Nenhum evento recente no log.</p>';
        }
    }

    function populateCwlInfo(data) {
        if (data.error) {
            cwlRoundsContainerEl.innerHTML = `<p>${data.error}</p>`;
            noCwlMessageEl.style.display = 'block';
            noCwlMessageEl.textContent = data.error;
            if(cwlSeasonEl) cwlSeasonEl.textContent = '-';
            if(cwlStateEl) cwlStateEl.textContent = 'Erro';
            return;
        }
        if (data.status === "notInWar" || !data.rounds) {
            noCwlMessageEl.textContent = data.message || "Não em CWL.";
            noCwlMessageEl.style.display = 'block';
            cwlRoundsContainerEl.innerHTML = '';
            if(cwlSeasonEl) cwlSeasonEl.textContent = data.season || '-';
            if(cwlStateEl) cwlStateEl.textContent = data.status ? data.status.replace(/([A-Z])/g, ' $1').trim() : 'N/A';
            return;
        }

        noCwlMessageEl.style.display = 'none';
        if(cwlSeasonEl) cwlSeasonEl.textContent = data.season || '-';
        if(cwlStateEl) cwlStateEl.textContent = data.status ? data.status.replace(/([A-Z])/g, ' $1').trim() : 'N/A';
        cwlRoundsContainerEl.innerHTML = '';

        data.rounds.forEach(round => {
            const roundDiv = document.createElement('div');
            roundDiv.className = 'cwl-round';
            roundDiv.innerHTML = `<h4>Rodada ${round.round_number}</h4>`;
            if (round.wars && round.wars.length > 0) {
                round.wars.forEach(war => {
                    if (war.error) {
                        roundDiv.innerHTML += `<p>Erro ao carregar guerra ${war.war_tag}: ${war.error}</p>`;
                        return;
                    }
                    const warDiv = document.createElement('div');
                    warDiv.className = 'cwl-war';
                    warDiv.innerHTML = `
                        <div class="cwl-team">
                            ${war.clan1_badge_url ? `<img src="${war.clan1_badge_url}" alt="${war.clan1_name}">` : ''}
                            <span class="cwl-team-name">${war.clan1_name}</span><br>
                            <span class="cwl-score">${war.clan1_stars}⭐ (${war.clan1_destruction})</span>
                        </div>
                        <div class="cwl-vs">⚔️</div>
                        <div class="cwl-team">
                            ${war.clan2_badge_url ? `<img src="${war.clan2_badge_url}" alt="${war.clan2_name}">` : ''}
                            <span class="cwl-team-name">${war.clan2_name}</span><br>
                            <span class="cwl-score">${war.clan2_stars}⭐ (${war.clan2_destruction})</span>
                        </div>
                        `;
                    roundDiv.appendChild(warDiv);
                });
            } else {
                roundDiv.innerHTML += '<p>Nenhuma guerra para esta rodada.</p>';
            }
            cwlRoundsContainerEl.appendChild(roundDiv);
        });
    }


    // --- Carregamento de Dados ---
    async function loadCoreData() { // Carrega dados que são sempre visíveis ou frequentemente necessários
        const clanData = await fetchData('clan');
        populateClanInfo(clanData);
        const warData = await fetchData('war');
        populateWarInfo(warData);
        const membersData = await fetchData('members');
        populateMembersList(membersData);
    }

    async function loadCwlData() {
        const cwlData = await fetchData('cwl');
        populateCwlInfo(cwlData);
    }
    async function loadEventsLog() {
        const eventsData = await fetchData('events');
        populateEventsLog(eventsData);
    }

    // Carregamento Inicial e Polling
    function initializePanel() {
        const savedSection = localStorage.getItem('currentPanelSection') || 'clan-info-section';
        navigateToSection(savedSection); // Navega para a última seção salva ou padrão

        loadCoreData(); // Carrega dados do clã, guerra, membros
        if (savedSection === 'cwl-info-section') loadCwlData();
        if (savedSection === 'events-log-section') loadEventsLog();
        
        updateLastUpdated();

        setInterval(() => {
            loadCoreData(); // Recarrega dados principais periodicamente
            const currentVisibleSection = document.querySelector('.current-section').id;
            if (currentVisibleSection === 'cwl-info-section') loadCwlData();
            if (currentVisibleSection === 'events-log-section') loadEventsLog();
            updateLastUpdated();
        }, 30000); // Atualiza a cada 30 segundos (ajuste conforme necessário)
    }

    initializePanel();
});
