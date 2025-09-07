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

    // --- INÍCIO: Seletores para a nova aba Destaques ---
    const highlightsClanNameEl = document.getElementById('highlightsClanName');
    const topDonorsListEl = document.getElementById('topDonorsList');
    const bestAttacksListEl = document.getElementById('bestAttacksList');
    const activityChartCanvas = document.getElementById('activityChart');
    const noHighlightsMessageEl = document.getElementById('noHighlightsMessage');
    let activityChart = null; // Variável para armazenar a instância do gráfico
    // --- FIM: Seletores para a nova aba Destaques ---

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

    // --- ELEMENTOS DO MODAL ---
    const historicWarModal = document.getElementById('historicWarModal');
    const historicWarDetailContent = document.getElementById('historicWarDetailContent');
    const closeModalButton = document.querySelector('.modal .close-button');


    // --- LÓGICA DA MÚSICA DE FUNDO ---
    if (backgroundMusicEl && muteButtonEl) {
        backgroundMusicEl.volume = 0.2;
        const playMusic = async () => {
            try {
                await backgroundMusicEl.play();
                document.body.removeEventListener('click', playMusic);
                console.log('Música de fundo iniciada.');
            } catch (err) {
                console.log('Autoplay da música bloqueado pelo navegador. Aguardando interação do usuário.');
            }
        };
        document.body.addEventListener('click', playMusic, { once: true });

        muteButtonEl.addEventListener('click', () => {
            backgroundMusicEl.muted = !backgroundMusicEl.muted;
            if (backgroundMusicEl.muted) {
                muteButtonEl.textContent = '🔇';
                localStorage.setItem('musicMuted', 'true');
            } else {
                muteButtonEl.textContent = '🔊';
                localStorage.setItem('musicMuted', 'false');
            }
        });

        if (localStorage.getItem('musicMuted') === 'true') {
            backgroundMusicEl.muted = true;
            muteButtonEl.textContent = '🔇';
        } else {
            backgroundMusicEl.muted = false;
            muteButtonEl.textContent = '🔊';
        }
    }

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

    function setBadge(element, url) {
        if (element) {
            element.src = url || DEFAULT_BADGE_URL;
            element.style.display = 'inline-block';
        }
    }

    // --- NAVEGAÇÃO E ANIMAÇÃO DAS SEÇÕES ---
    const initialSectionId = (navLinks.length > 0 && navLinks[0].dataset.section) ? navLinks[0].dataset.section : 'clan-info-nav';
    let currentActiveSectionId = localStorage.getItem('activeSection') || initialSectionId;
    let currentActiveIndex = Array.from(navLinks).findIndex(link => link.dataset.section === currentActiveSectionId);
    if (currentActiveIndex === -1) {
        currentActiveIndex = 0;
        currentActiveSectionId = initialSectionId;
    }

    contentSections.forEach(section => {
        section.classList.remove('active-section', 'slide-out-to-left', 'slide-out-to-right', 'slide-prepare', 'slide-from-left', 'slide-from-right');
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

        if (!newSectionEl) {
            console.error("Nova seção não encontrada:", newSectionId);
            return;
        }

        newSectionEl.classList.remove('slide-out-to-left', 'slide-out-to-right', 'slide-prepare', 'slide-from-left', 'slide-from-right');

        if (oldSectionEl) {
            oldSectionEl.classList.remove('active-section');
            if (newIndex > oldIndex) {
                oldSectionEl.classList.add('slide-out-to-left');
            } else {
                oldSectionEl.classList.add('slide-out-to-right');
            }
            oldSectionEl.addEventListener('transitionend', function handleOldOut() {
                oldSectionEl.classList.remove('slide-out-to-left', 'slide-out-to-right');
                oldSectionEl.removeEventListener('transitionend', handleOldOut);
            }, { once: true });
        }
        
        newSectionEl.classList.add('slide-prepare');
        if (newIndex > oldIndex) {
            newSectionEl.classList.add('slide-from-right');
        } else {
            newSectionEl.classList.add('slide-from-left');
        }

        void newSectionEl.offsetWidth; 

        newSectionEl.classList.remove('slide-prepare', 'slide-from-left', 'slide-from-right');
        newSectionEl.classList.add('active-section');

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
            setText(clanNameHeaderEl, "Erro");
            setText(clanNameEl, data.error || "N/A");
            return;
        }
        setText(clanNameHeaderEl, data.name);
        setText(clanNameEl, data.name);
        setText(clanTagEl, data.tag);
        setBadge(clanBadgeHeaderEl, data.badge_url);
        setBadge(clanBadgeEl, data.badge_url);
        setText(clanLevelEl, `Nível: ${data.level || '-'}`);
        setText(clanMemberCountEl, `Membros: ${data.member_count || '-'}/50`);
        setText(clanLocationEl, `Local: ${data.location || '-'}`);
        setText(clanTypeEl, `Tipo: ${data.type || '-'}`);
        setText(clanWarWinsEl, `${data.war_wins || '-'} ⚔️`);
        setText(clanPointsEl, `${data.points || '-'} 🏆`);
        setText(clanCapitalPointsEl, `${data.capital_points || '-'} 🏆`);
        setText(clanCapitalLeagueEl, data.capital_league);
        setText(clanDescriptionEl, data.description, 'Sem descrição.');
        setHtml(clanCapitalDistrictsEl, '');
        if (data.capital_districts && data.capital_districts.length > 0) {
            data.capital_districts.forEach(d => setHtml(clanCapitalDistrictsEl, clanCapitalDistrictsEl.innerHTML + `<p><strong>${d.name || 'N/A'}:</strong> Nv ${d.level || '?'}</p>`));
        } else {
            setHtml(clanCapitalDistrictsEl, '<p>Nenhum distrito encontrado.</p>');
        }
        setText(botVersionEl, data.version, '?');
    }

    // --- INÍCIO: Nova função para popular a aba Destaques ---
    function populateHighlights(data) {
        if (data.error || !data.clan_name) {
            noHighlightsMessageEl.style.display = 'block';
            setText(noHighlightsMessageEl, data.error || "Não foi possível carregar os destaques.");
            document.getElementById('highlightsContent').style.display = 'none';
            return;
        }

        noHighlightsMessageEl.style.display = 'none';
        document.getElementById('highlightsContent').style.display = 'block';
        setText(highlightsClanNameEl, data.clan_name);

        // Popula Top Doadores
        if (data.top_donors && data.top_donors.length > 0) {
            const medals = ['gold', 'silver', 'bronze'];
            let donorsHtml = '';
            data.top_donors.forEach((donor, index) => {
                donorsHtml += `
                    <div class="podium-item ${medals[index] || ''}">
                        <span class="podium-rank">${index === 0 ? '🥇' : index === 1 ? '🥈' : '🥉'}</span>
                        <div class="podium-details">
                            <div class="member-name">${donor.name} (CV${donor.town_hall})</div>
                            <div class="donation-count"><strong>${donor.donations.toLocaleString()}</strong> tropas doadas</div>
                        </div>
                    </div>
                `;
            });
            setHtml(topDonorsListEl, donorsHtml);
        } else {
            setHtml(topDonorsListEl, '<p>Nenhum doador encontrado.</p>');
        }

        // Popula Melhores Ataques
        if (data.best_attacks && data.best_attacks.length > 0) {
            let attacksHtml = '';
            data.best_attacks.forEach(attack => {
                attacksHtml += `
                    <div class="attack-item">
                        <div class="attack-header">${attack.attacker_name} vs ${attack.defender_name} (CV${attack.defender_townhall})</div>
                        <div class="attack-details">
                            <span class="attack-stars">${'⭐'.repeat(attack.stars)}</span>
                            <strong>${attack.destruction}%</strong> de destruição
                        </div>
                    </div>
                `;
            });
            setHtml(bestAttacksListEl, attacksHtml);
        } else {
            setHtml(bestAttacksListEl, '<p>Nenhum ataque na última guerra para destacar.</p>');
        }

        // Popula o Gráfico de Atividade
        if (activityChart) {
            activityChart.destroy(); // Destroi o gráfico antigo antes de criar um novo
        }
        if (data.activity_chart_data && data.activity_chart_data.labels.length > 0) {
            const ctx = activityChartCanvas.getContext('2d');
            activityChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.activity_chart_data.labels,
                    datasets: [
                        {
                            label: 'Tropas Doadas',
                            data: data.activity_chart_data.donations,
                            backgroundColor: 'rgba(54, 162, 235, 0.6)',
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 1
                        },
                        {
                            label: 'Tropas Recebidas',
                            data: data.activity_chart_data.received,
                            backgroundColor: 'rgba(255, 99, 132, 0.6)',
                            borderColor: 'rgba(255, 99, 132, 1)',
                            borderWidth: 1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: { color: 'rgba(255, 255, 255, 0.7)' }
                        },
                        x: {
                            ticks: { color: 'rgba(255, 255, 255, 0.7)' }
                        }
                    },
                    plugins: {
                        legend: {
                            labels: {
                                color: 'rgba(255, 255, 255, 0.8)'
                            }
                        }
                    }
                }
            });
        }
    }
    // --- FIM: Nova função para popular a aba Destaques ---


    warTabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const parentSection = button.closest('.content-section, .modal-content');
            if (!parentSection) return;
            parentSection.querySelectorAll('.war-tab-button').forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            const tabId = button.dataset.tab;
            parentSection.querySelectorAll('.war-tab-content').forEach(content => {
                content.style.display = content.id.endsWith(tabId) ? 'block' : 'none';
            });
        });
    });

    function createStarString(stars) {
        return '⭐'.repeat(stars) + '⚫'.repeat(Math.max(0, 3 - stars));
    }

    function populateWarDetails(data, containerId = 'war-details-nav', isModal = false) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const prefix = isModal ? 'historic-' : '';

        const warHeader = container.querySelector('.war-header');
        const warTabsNav = container.querySelector('.war-tabs');
        const noWarMsg = container.querySelector(isModal ? '.message-box' : '#noWarDetailMessage');

        if (data.error || !data.war_data) {
            if (noWarMsg) {
                noWarMsg.style.display = 'block';
                setText(noWarMsg, data.error || "Nenhuma guerra para detalhar.");
            }
            if (warHeader) warHeader.style.display = 'none';
            if (warTabsNav) warTabsNav.style.display = 'none';
            container.querySelectorAll('.war-tab-content').forEach(tab => tab.style.display = 'none');
            return;
        }

        if (noWarMsg) noWarMsg.style.display = 'none';
        if (warHeader) warHeader.style.display = 'flex';
        if (warTabsNav) warTabsNav.style.display = 'flex';
        
        const war = data.war_data;

        setText(container.querySelector(`#${prefix}warDetailOurClanName`), war.clan_name);
        setText(container.querySelector(`#${prefix}warDetailOpponentName`), war.opponent_name);
        setBadge(container.querySelector(`#${prefix}warDetailClanBadge`), war.clan_badge_url);
        setBadge(container.querySelector(`#${prefix}warDetailOpponentBadge`), war.opponent_badge_url);
        setText(container.querySelector(`#${prefix}warDetailTimeKey`), war.time_key);
        setText(container.querySelector(`#${prefix}warDetailTimeValue`), war.time_value);
        setText(container.querySelector(`#${prefix}warDetailTimeRemaining`), war.time_remaining);
        const stateEl = container.querySelector(`#${prefix}warDetailState`);
        setText(stateEl, war.state_description);
        if(stateEl) stateEl.className = 'war-state ' + (war.status || '').toLowerCase();

        setText(container.querySelector(`#${prefix}statsOurClanName`), war.clan_name);
        setText(container.querySelector(`#${prefix}statsOurStars`), war.clan_stars);
        setText(container.querySelector(`#${prefix}statsOurDestruction`), war.clan_destruction.replace('%', ''));
        setText(container.querySelector(`#${prefix}statsOurAttacksUsed`), `${war.clan_attacks_used}/${war.team_size * war.attacks_per_member}`);
        setText(container.querySelector(`#${prefix}statsOpponentName`), war.opponent_name);
        setText(container.querySelector(`#${prefix}statsOpponentStars`), war.opponent_stars);
        setText(container.querySelector(`#${prefix}statsOpponentDestruction`), war.opponent_destruction.replace('%', ''));
        setText(container.querySelector(`#${prefix}statsOpponentAttacksUsed`), `${war.opponent_attacks_used}/${war.team_size * war.attacks_per_member}`);
        
        const populateStats = (prefix) => {
            const ourAvgStarsEl = container.querySelector(`#${prefix}statsOurAvgStars`);
            if(ourAvgStarsEl) setText(ourAvgStarsEl, war.clan_avg_stars);

            const ourAvgDurationEl = container.querySelector(`#${prefix}statsOurAvgDuration`);
            if(ourAvgDurationEl) setText(ourAvgDurationEl, war.clan_avg_duration);
            
            const oppAvgStarsEl = container.querySelector(`#${prefix}statsOpponentAvgStars`);
            if(oppAvgStarsEl) setText(oppAvgStarsEl, war.opponent_avg_stars);

            const oppAvgDurationEl = container.querySelector(`#${prefix}statsOpponentAvgDuration`);
            if(oppAvgDurationEl) setText(oppAvgDurationEl, war.opponent_avg_duration);

            const ourStars3El = container.querySelector(`#${prefix}statsOurStars3`);
            if(ourStars3El) setText(ourStars3El, war.clan_star_distribution['3']);
            
            const ourStars2El = container.querySelector(`#${prefix}statsOurStars2`);
            if(ourStars2El) setText(ourStars2El, war.clan_star_distribution['2']);

            const ourStars1El = container.querySelector(`#${prefix}statsOurStars1`);
            if(ourStars1El) setText(ourStars1El, war.clan_star_distribution['1']);
            
            const ourStars0El = container.querySelector(`#${prefix}statsOurStars0`);
            if(ourStars0El) setText(ourStars0El, war.clan_star_distribution['0']);

            const oppStars3El = container.querySelector(`#${prefix}statsOpponentStars3`);
            if(oppStars3El) setText(oppStars3El, war.opponent_star_distribution['3']);

            const oppStars2El = container.querySelector(`#${prefix}statsOpponentStars2`);
            if(oppStars2El) setText(oppStars2El, war.opponent_star_distribution['2']);

            const oppStars1El = container.querySelector(`#${prefix}statsOpponentStars1`);
            if(oppStars1El) setText(oppStars1El, war.opponent_star_distribution['1']);

            const oppStars0El = container.querySelector(`#${prefix}statsOpponentStars0`);
            if(oppStars0El) setText(oppStars0El, war.opponent_star_distribution['0']);
        };

        populateStats(prefix);

        const eventsTableBody = container.querySelector(`#${prefix}warEventsTableBody`);
        setText(container.querySelector(`#${prefix}warTotalAttacksCount`), data.all_attacks.length);
        setHtml(eventsTableBody, '');
        if (data.all_attacks && data.all_attacks.length > 0) {
            data.all_attacks.forEach(att => {
                const row = eventsTableBody.insertRow();
                setText(row.insertCell(), att.order);
                setText(row.insertCell(), `${att.attacker_name} (CV${att.attacker_townhall})`);
                const resultCell = row.insertCell();
                resultCell.innerHTML = `<span class="attack-stars">${createStarString(att.stars)}</span> ${att.destruction}%`;
                setText(row.insertCell(), `${att.defender_name} (CV${att.defender_townhall})`);
                setText(row.insertCell(), att.duration);
            });
        } else {
            setHtml(eventsTableBody, '<tr><td colspan="5">Nenhum ataque registrado.</td></tr>');
        }

        const populateTeamTabData = (teamMembersData, teamNameKey, teamElement) => {
            setText(container.querySelector(`#${prefix}war${teamNameKey}TeamName`), war[`${teamNameKey === 'Our' ? 'clan' : 'opponent'}_name`]);
            setHtml(teamElement, '');
            if (teamMembersData && teamMembersData.length > 0) {
                teamMembersData.forEach(member => {
                    let attacksHtml = '<h5>Ataques Feitos:</h5><ul class="member-attack-list">';
                    if (member.attacks_made && member.attacks_made.length > 0) {
                        member.attacks_made.forEach(atk => {
                            attacksHtml += `<li>${createStarString(atk.stars)} ${atk.destruction}% vs ${atk.defender_name} (CV${atk.defender_townhall})</li>`;
                        });
                    } else {
                        attacksHtml += '<li>Nenhum ataque feito.</li>';
                    }
                    attacksHtml += '</ul>';

                    let defensesHtml = '<h5>Defesas Recebidas:</h5><ul class="member-defense-list">';
                    if (member.defenses_received && member.defenses_received.length > 0) {
                        member.defenses_received.forEach(def => {
                            defensesHtml += `<li>${createStarString(def.stars)} ${def.destruction}% por ${def.attacker_name} (CV${def.attacker_townhall})</li>`;
                        });
                    } else {
                        defensesHtml += '<li>Nenhuma defesa registrada.</li>';
                    }
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
            } else {
                setHtml(teamElement, '<p>Nenhum membro nesta equipe para a guerra.</p>');
            }
        };

        populateTeamTabData(data.our_clan_members_in_war, "Our", container.querySelector(`#${prefix}warOurTeamMembers`));
        populateTeamTabData(data.opponent_clan_members_in_war, "Opponent", container.querySelector(`#${prefix}warOpponentTeamMembers`));
        
        let activeWarTabFound = false;
        container.querySelectorAll('.war-tab-button').forEach(btn => {
            if (btn.classList.contains('active')) activeWarTabFound = true;
        });
        if (!activeWarTabFound) {
            const firstWarTabButton = container.querySelector('.war-tab-button[data-tab="war-stats"]');
            const firstWarTabContent = container.querySelector(isModal ? '#historic-war-stats' : '#war-stats');
            if (firstWarTabButton && firstWarTabContent) {
                container.querySelectorAll('.war-tab-button').forEach(btn => btn.classList.remove('active'));
                container.querySelectorAll('.war-tab-content').forEach(tc => tc.style.display = 'none');
                firstWarTabButton.classList.add('active');
                firstWarTabContent.style.display = 'block';
            }
        }
    }

    function populateMissedAttacksHistory(data) {
        const clanNameSpan = attacksRemainingTitleEl.querySelector('span');
        if (clanNameSpan) {
            setText(clanNameSpan, data.clan_name);
        }
    
        if (data.error || !data.missed_attacks || data.missed_attacks.length === 0) {
            const message = data.error || "Nenhuma pendência de ataque encontrada no histórico de guerras.";
            setHtml(attacksRemainingListEl, `<p>${message}</p>`);
            if (noMissedAttacksMessageEl) {
                noMissedAttacksMessageEl.style.display = 'block';
                setText(noMissedAttacksMessageEl, message);
            }
            return;
        }
    
        if (noMissedAttacksMessageEl) noMissedAttacksMessageEl.style.display = 'none';
        
        let htmlContent = '';
        data.missed_attacks.forEach(m => {
            htmlContent += `<p><strong>${m.name}</strong> (CV${m.town_hall}) - <strong>${m.attacks_left}</strong> atk restante(s) na guerra de <strong>${m.war_date}</strong></p>`;
        });
        setHtml(attacksRemainingListEl, htmlContent);
    }

    function populateCwlInfo(data) {
        setText(cwlStatusTextEl, "Carregando...");
        if (cwlStatusTextEl) cwlStatusTextEl.className = 'war-state';

        if (data.error || data.status === "NotInCwl" || data.status === "CwlFeatureDisabled") {
            if(noCwlMessageEl) noCwlMessageEl.style.display = 'block';
            setText(noCwlMessageEl, data.message || data.error || "CWL indisponível.");
            if(cwlActiveInfoEl) cwlActiveInfoEl.style.display = 'none';
            setText(cwlStatusTextEl, data.message || (data.error ? "Erro" : "Fora da CWL"));
            if (cwlStatusTextEl) cwlStatusTextEl.classList.add((data.status || 'notincwl').toLowerCase());
            return;
        }

        if(noCwlMessageEl) noCwlMessageEl.style.display = 'none';
        if(cwlActiveInfoEl) cwlActiveInfoEl.style.display = 'block';
        setText(cwlStatusTextEl, "Em CWL");
        if (cwlStatusTextEl) cwlStatusTextEl.classList.add('incwl');

        setText(cwlSeasonEl, data.season);
        setText(cwlGroupStateEl, data.state);

        setHtml(cwlGroupClansEl, '');
        if (data.clans_in_group && data.clans_in_group.length > 0) {
            data.clans_in_group.forEach(c => setHtml(cwlGroupClansEl, cwlGroupClansEl.innerHTML + `<p><img src="${c.badge_url || DEFAULT_BADGE_URL}" alt="Emblema ${c.name}"> <strong>${c.name}</strong> (${c.tag}) Nv ${c.level}</p>`));
        } else {
            setHtml(cwlGroupClansEl, '<p>Nenhum clã no grupo.</p>');
        }

        setHtml(cwlRoundsInfoEl, '');
        if (data.rounds && data.rounds.length > 0) {
            data.rounds.forEach(r => {
                let roundHtml = `<div class="cwl-round"><h4>Rodada ${r.round_number}</h4>`;
                if (r.wars && r.wars.length > 0) {
                    r.wars.forEach(w => {
                        if (w.error) {
                            roundHtml += `<p class="cwl-war-entry">Guerra (${w.war_tag || 'N/A'}): ${w.error}</p>`;
                        } else if (w.message) {
                            roundHtml += `<p class="cwl-war-entry">${w.message}</p>`;
                        } else {
                            const cBadge = w.clan_badge_url ? `<img src="${w.clan_badge_url}" alt="Emblema ${w.clan_name}" class="cwl-war-badge">` : "";
                            const oBadge = w.opponent_badge_url ? `<img src="${w.opponent_badge_url}" alt="Emblema ${w.opponent_name}" class="cwl-war-badge">` : "";
                            roundHtml += `<p class="cwl-war-entry"><strong>${cBadge} ${w.clan_name}</strong> ${w.clan_stars}⭐ (${w.clan_destruction}) vs ${w.opponent_stars}⭐ (${w.opponent_destruction}) <strong>${oBadge} ${w.opponent_name}</strong><br><small>Estado: ${w.state} | ${w.time_key}: ${w.time_value} (${w.time_remaining})</small></p>`;
                        }
                    });
                } else {
                    roundHtml += "<p>Nenhuma guerra nesta rodada.</p>";
                }
                roundHtml += "</div>";
                setHtml(cwlRoundsInfoEl, cwlRoundsInfoEl.innerHTML + roundHtml);
            });
        } else {
            setHtml(cwlRoundsInfoEl, "Nenhuma info de rodada.");
        }
    }

    function populateWarLog(data) {
        setText(warLogLimitEl, data.log ? data.log.length : '9');
        if (data.error || !data.log) {
            if(noWarLogMessageEl) noWarLogMessageEl.style.display = 'block';
            setText(noWarLogMessageEl, data.error || "Log de guerra indisponível.");
            setHtml(warLogTableBodyEl, `<tr><td colspan="6">${data.error || "N/A"}</td></tr>`);
            return;
        }

        if(noWarLogMessageEl) noWarLogMessageEl.style.display = 'none';
        setHtml(warLogTableBodyEl, '');
        if (data.log.length > 0) {
            data.log.forEach(e => {
                const row = warLogTableBodyEl.insertRow();
                row.classList.add('historic-war-row');
                row.dataset.warId = e.end_time_iso;
                setText(row.insertCell(), e.end_time_formatted);
                const oppCell = row.insertCell();
                const oppBadge = e.opponent_badge_url ? `<img src="${e.opponent_badge_url}" alt="Emblema ${e.opponent_name}" class="log-opponent-badge">` : "";
                setHtml(oppCell, `${oppBadge}${e.opponent_name || 'N/A'}`);
                setText(row.insertCell(), `${e.clan_stars}⭐ (${e.clan_destruction}) vs ${e.opponent_stars}⭐ (${e.opponent_destruction})`);
                const resCell = row.insertCell();
                setText(resCell, e.result);
                resCell.className = e.result ? `war-result-${e.result.toLowerCase()}` : '';
                setText(row.insertCell(), e.team_size);
                setText(row.insertCell(), e.is_cwl ? "CWL" : "Normal");
            });
        } else {
            setHtml(warLogTableBodyEl, '<tr><td colspan="6">Nenhum registro encontrado.</td></tr>');
        }
    }
    
    function applyMemberFilters() {
        const nameFilter = filterNameInput.value.toLowerCase();
        const thFilter = filterTHInput.value.toLowerCase().replace(/\s/g, '');
        const leagueFilter = filterLeagueInput.value.toLowerCase();
        const trophiesFilterText = filterTrophiesInput.value;
        const roleFilter = filterRoleInput.value.toLowerCase();

        const rows = membersTableBodyEl.getElementsByTagName('tr');
        for (let i = 0; i < rows.length; i++) {
            const cells = rows[i].getElementsByTagName('td');
            const name = cells[1].textContent.toLowerCase();
            const th = `cv${cells[2].textContent}`.toLowerCase();
            const league = cells[3].textContent.toLowerCase();
            const trophies = parseInt(cells[4].textContent, 10);
            const role = cells[5].textContent.toLowerCase();

            let show = true;
            if (nameFilter && !name.includes(nameFilter)) show = false;
            if (thFilter && th !== thFilter) show = false;
            if (leagueFilter && !league.includes(leagueFilter)) show = false;
            if (roleFilter && !role.includes(roleFilter)) show = false;
            
            if (trophiesFilterText) {
                const match = trophiesFilterText.match(/(>=|<=|>|<)?\s*(\d+)/);
                if (match) {
                    const operator = match[1] || '==';
                    const value = parseInt(match[2], 10);
                    if (operator === '>=' && trophies < value) show = false;
                    else if (operator === '<=' && trophies > value) show = false;
                    else if (operator === '>' && trophies <= value) show = false;
                    else if (operator === '<' && trophies >= value) show = false;
                    else if (operator === '==' && trophies !== value) show = false;
                }
            }
            rows[i].style.display = show ? '' : 'none';
        }
    }

    [filterNameInput, filterTHInput, filterLeagueInput, filterTrophiesInput, filterRoleInput].forEach(input => {
        if(input) input.addEventListener('keyup', applyMemberFilters);
    });

    async function savePlayerNote(playerTag, text, priority) {
        const encodedPlayerTag = encodeURIComponent(playerTag);
        try {
            const response = await fetchData(`notes/${encodedPlayerTag}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, priority })
            });
            if (response && !response.error) {
                console.log(`Nota para ${playerTag} salva com sucesso.`);
            } else {
                console.error(`Falha ao salvar nota para ${playerTag}:`, response ? response.error : 'Resposta desconhecida');
            }
        } catch (error) {
            console.error('Erro de rede ao salvar nota:', error);
        }
    }

    function populateMembersList(data) {
        setText(membersClanNameEl, data.clan_name);
        if (data.error || !data.members) {
            setHtml(membersTableBodyEl, `<tr><td colspan="9">${data.error || "N/A"}</td></tr>`);
            return;
        }

        setHtml(membersTableBodyEl, '');
        if (data.members.length > 0) {
            data.members.forEach((m, index) => {
                const row = membersTableBodyEl.insertRow();
                setText(row.insertCell(), index + 1);
                setText(row.insertCell(), m.name);
                setText(row.insertCell(), m.town_hall);
                setText(row.insertCell(), m.league);
                setText(row.insertCell(), m.trophies);
                setText(row.insertCell(), m.role);
                setText(row.insertCell(), m.donations);
                setText(row.insertCell(), m.received);

                const noteCell = row.insertCell();
                noteCell.className = 'member-note-cell';
                const noteContainer = document.createElement('div');
                noteContainer.className = `note-container note-priority-${m.note_priority || 'none'}`;
                
                const noteTextSpan = document.createElement('span');
                noteTextSpan.className = 'note-text';
                noteTextSpan.textContent = m.note || 'Clique para editar...';
                noteTextSpan.title = m.note || 'Sem observação';
                noteContainer.appendChild(noteTextSpan);

                const noteInput = document.createElement('input');
                noteInput.type = 'text';
                noteInput.className = 'note-input';
                noteInput.value = m.note;
                noteInput.style.display = 'none';
                noteContainer.appendChild(noteInput);
                
                const prioritySelector = document.createElement('div');
                prioritySelector.className = 'priority-selector';
                ['green', 'yellow', 'red', 'none'].forEach(prio => {
                    const btn = document.createElement('button');
                    btn.className = `priority-btn priority-${prio}`;
                    btn.dataset.priority = prio;
                    if (prio === 'green') btn.innerHTML = '&#10003;';
                    else if (prio === 'yellow') btn.innerHTML = '!';
                    else if (prio === 'red') btn.innerHTML = '&#10007;';
                    else if (prio === 'none') btn.innerHTML = '&times;';
                    else btn.innerHTML = '&#9679;';
                    
                    if (prio === (m.note_priority || 'none')) btn.classList.add('active');
                    
                    btn.addEventListener('click', () => {
                        const currentText = noteInput.style.display === 'none' 
                            ? (noteTextSpan.textContent === 'Clique para editar...' ? '' : noteTextSpan.textContent)
                            : noteInput.value;
                        
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
                    
                    noteTextSpan.textContent = newText || 'Clique para editar...';
                    noteTextSpan.title = newText || 'Sem observação';
                    noteInput.style.display = 'none';
                    noteTextSpan.style.display = 'inline-block';
                });

                noteInput.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') noteInput.blur();
                });

                noteCell.appendChild(noteContainer);
            });
        } else {
            setHtml(membersTableBodyEl, '<tr><td colspan="9">Nenhum membro.</td></tr>');
        }
        applyMemberFilters();
    }

    async function openHistoricWarModal(warId) {
        setHtml(historicWarDetailContent, '<div class="loading-spinner" style="margin: 40px auto;"></div><p style="text-align:center;">Carregando detalhes da guerra...</p>');
        historicWarModal.style.display = 'block';
        
        const historicWarData = await fetchData(`war_history/${warId}`);
        
        const template = document.getElementById('historic-war-template');
        if (!template) {
            console.error("Template 'historic-war-template' não encontrado!");
            setHtml(historicWarDetailContent, '<p style="text-align:center; color: red;">Erro de configuração: Template do modal não encontrado.</p>');
            return;
        }
        const warDetailsContent = template.content.cloneNode(true);

        setHtml(historicWarDetailContent, '');
        historicWarDetailContent.appendChild(warDetailsContent);

        historicWarDetailContent.querySelectorAll('.war-tab-button').forEach(button => {
            button.addEventListener('click', () => {
                const modalContentEl = button.closest('.modal-content');
                if (!modalContentEl) return;

                modalContentEl.querySelectorAll('.war-tab-button').forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                
                const tabId = button.dataset.tab;

                modalContentEl.querySelectorAll('.war-tab-content').forEach(content => {
                    if (content.id.endsWith(tabId)) {
                        content.style.display = 'block';
                    } else {
                        content.style.display = 'none';
                    }
                });
            });
        });
        
        populateWarDetails(historicWarData, 'historicWarDetailContent', true);
    }

    if (closeModalButton) {
        closeModalButton.addEventListener('click', () => {
            historicWarModal.style.display = 'none';
        });
    }
    
    window.addEventListener('click', (event) => {
        if (event.target == historicWarModal) {
            historicWarModal.style.display = 'none';
        }
    });

    warLogTableBodyEl.addEventListener('click', (event) => {
        const row = event.target.closest('.historic-war-row');
        if (row && row.dataset.warId) {
            openHistoricWarModal(row.dataset.warId);
        }
    });

    // --- CARREGAMENTO INICIAL E PERIÓDICO ---
    async function loadAllData() {
        try {
            const [clanData, membersData, currentWarDetailsData, missedAttacksData, warLogData, cwlInfoData, highlightsData] = await Promise.all([
                fetchData('clan'),
                fetchData('members'),
                fetchData('current_war_details'),
                fetchData('missed_attacks_history'),
                fetchData('war_log'),
                fetchData('cwl_info'),
                fetchData('highlights') // Adiciona a busca de dados para a nova aba
            ]);
            populateClanInfo(clanData);
            populateMembersList(membersData);
            populateWarDetails(currentWarDetailsData, 'war-details-nav', false);
            populateMissedAttacksHistory(missedAttacksData);
            populateWarLog(warLogData);
            populateCwlInfo(cwlInfoData);
            populateHighlights(highlightsData); // Chama a nova função para popular os destaques
            updateLastUpdated();
        } catch (error) {
            console.error("Erro ao carregar todos os dados:", error);
        } finally {
            if (isFirstLoad && loadingOverlayEl) {
                setTimeout(() => {
                    loadingOverlayEl.classList.add('hidden');
                }, 500);
                isFirstLoad = false;
            }
        }
    }

    loadAllData();
    setInterval(loadAllData, 60000);

    // --- ANIMAÇÃO DE PARTÍCULAS DE FUNDO ---
    const particleCanvas = document.getElementById('particle-background');
    if (particleCanvas) {
        const ctx = particleCanvas.getContext('2d');
        let particlesArrayLocal = [];
        let mouse = { x: undefined, y: undefined, radius: 120 };

        const particleSettings = {
            count: 35,
            minSize: 1,
            maxSize: 3,
            minSpeed: 0.1,
            maxSpeed: 0.5,
            color: 'rgba(255, 215, 0, 0.6)',
            lineColor: 'rgba(255, 215, 0, 0.1)'
        };

        particleCanvas.width = window.innerWidth;
        particleCanvas.height = window.innerHeight;

        window.addEventListener('resize', () => {
            particleCanvas.width = window.innerWidth;
            particleCanvas.height = window.innerHeight;
            mouse.radius = 120;
            initParticles();
        });
        
        particleCanvas.addEventListener('mousemove', (event) => {
            mouse.x = event.x;
            mouse.y = event.y;
        });
        particleCanvas.addEventListener('mouseout', () => {
            mouse.x = undefined;
            mouse.y = undefined;
        });

        class Particle {
            constructor(x, y, size, speedX, speedY, color) {
                this.x = x; this.y = y; this.size = size;
                this.speedX = speedX; this.speedY = speedY; this.color = color;
            }
            draw() {
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2, false);
                ctx.fillStyle = this.color;
                ctx.fill();
            }
            update() {
                if (this.x > particleCanvas.width || this.x < 0) this.speedX = -this.speedX;
                if (this.y > particleCanvas.height || this.y < 0) this.speedY = -this.speedY;
                this.x += this.speedX;
                this.y += this.speedY;
                
                let dx = mouse.x - this.x;
                let dy = mouse.y - this.y;
                let distance = Math.sqrt(dx * dx + dy * dy);
                if (distance < mouse.radius + this.size) {
                    if (mouse.x < this.x && this.x < particleCanvas.width - this.size * 10) this.x += 5;
                    if (mouse.x > this.x && this.x > this.size * 10) this.x -= 5;
                    if (mouse.y < this.y && this.y < particleCanvas.height - this.size * 10) this.y += 5;
                    if (mouse.y > this.y && this.y > this.size * 10) this.y -= 5;
                }
            }
        }

        function initParticles() {
            particlesArrayLocal = [];
            for (let i = 0; i < particleSettings.count; i++) {
                let size = (Math.random() * (particleSettings.maxSize - particleSettings.minSize)) + particleSettings.minSize;
                let x = (Math.random() * ((innerWidth - size * 2) - (size * 2)) + size * 2);
                let y = (Math.random() * ((innerHeight - size * 2) - (size * 2)) + size * 2);
                let speedX = (Math.random() * (particleSettings.maxSpeed - particleSettings.minSpeed) * 2) - particleSettings.maxSpeed;
                let speedY = (Math.random() * (particleSettings.maxSpeed - particleSettings.minSpeed) * 2) - particleSettings.maxSpeed;
                particlesArrayLocal.push(new Particle(x, y, size, speedX, speedY, particleSettings.color));
            }
        }

        function connectParticles() {
            let opacityValue = 1;
            for (let a = 0; a < particlesArrayLocal.length; a++) {
                for (let b = a; b < particlesArrayLocal.length; b++) {
                    let distance = ((particlesArrayLocal[a].x - particlesArrayLocal[b].x) * (particlesArrayLocal[a].x - particlesArrayLocal[b].x))
                        + ((particlesArrayLocal[a].y - particlesArrayLocal[b].y) * (particlesArrayLocal[a].y - particlesArrayLocal[b].y));
                    if (distance < (particleCanvas.width / 7) * (particleCanvas.height / 7)) {
                        opacityValue = 1 - (distance / 20000);
                        ctx.strokeStyle = particleSettings.lineColor.replace('0.1', opacityValue.toString());
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        ctx.moveTo(particlesArrayLocal[a].x, particlesArrayLocal[a].y);
                        ctx.lineTo(particlesArrayLocal[b].x, particlesArrayLocal[b].y);
                        ctx.stroke();
                    }
                }
            }
        }

        function animateParticles() {
            requestAnimationFrame(animateParticles);
            ctx.clearRect(0, 0, innerWidth, innerHeight);
            for (let i = 0; i < particlesArrayLocal.length; i++) {
                particlesArrayLocal[i].update();
                particlesArrayLocal[i].draw();
            }
            connectParticles();
        }
        
        initParticles();
        animateParticles();
    }
});

