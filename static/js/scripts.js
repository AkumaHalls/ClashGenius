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

    const highlightsClanNameEl = document.getElementById('highlightsClanName');
    const topDonorsListEl = document.getElementById('topDonorsList');
    const bestAttacksListEl = document.getElementById('bestAttacksList');
    const warDateHighlightEl = document.getElementById('warDateHighlight');
    const activityChartCanvas = document.getElementById('activityChart');
    const noHighlightsMessageEl = document.getElementById('noHighlightsMessage');
    let activityChart = null;

    const warDetailClanBadgeEl = document.getElementById('warDetailClanBadge');
    const warDetailOurClanNameEl = document.getElementById('warDetailOurClanName');
    const warDetailOpponentNameEl = document.getElementById('warDetailOpponentName');
    const warDetailOpponentBadgeEl = document.getElementById('warDetailOpponentBadge');
    const warDetailTimeKeyEl = document.getElementById('warDetailTimeKey');
    const warDetailTimeValueEl = document.getElementById('warDetailTimeValue');
    const warDetailTimeRemainingEl = document.getElementById('warDetailTimeRemaining');
    const warDetailStateEl = document.getElementById('warDetailState');
    const noWarDetailMessageEl = document.getElementById('noWarDetailMessage');
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
    const missedAttacksContainerEl = document.getElementById('missedAttacksContainer');
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
    const filterNameInput = document.getElementById('filterName');
    const filterTHInput = document.getElementById('filterTH');
    const membersGridEl = document.getElementById('membersGrid');

    const botVersionEl = document.getElementById('botVersion');
    const lastUpdatedEl = document.getElementById('lastUpdated');

    const navLinks = document.querySelectorAll('.nav-link');
    const contentSections = document.querySelectorAll('.content-section');
    let isFirstLoad = true;

    const historicWarModal = document.getElementById('historicWarModal');
    const historicWarDetailContent = document.getElementById('historicWarDetailContent');
    const closeModalButton = document.querySelector('#historicWarModal .close-button');

    const memberProfileModal = document.getElementById('memberProfileModal');
    const memberProfileContent = document.getElementById('memberProfileContent');
    const closeProfileModalButton = document.querySelector('#memberProfileModal .close-button');
    let memberTrophyChart = null;


    // --- LÓGICA DA MÚSICA DE FUNDO ---
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
            localStorage.setItem('musicMuted', backgroundMusicEl.muted);
        });

        if (localStorage.getItem('musicMuted') === 'true') {
            backgroundMusicEl.muted = true;
            muteButtonEl.textContent = '🔇';
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
            if (response.status === 204) return { success: true };
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
        if (element) element.src = url || DEFAULT_BADGE_URL;
    }
    
    // --- NAVEGAÇÃO E ANIMAÇÃO DAS SEÇÕES ---
    const initialSectionId = navLinks.length > 0 ? navLinks[0].dataset.section : 'clan-info-nav';
    let currentActiveSectionId = localStorage.getItem('activeSection') || initialSectionId;
    let currentActiveIndex = Array.from(navLinks).findIndex(link => link.dataset.section === currentActiveSectionId);
    if (currentActiveIndex === -1) {
        currentActiveIndex = 0;
        currentActiveSectionId = initialSectionId;
    }

    contentSections.forEach(section => {
        section.classList.remove('active-section');
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
        
        if (!newSectionEl) return;

        if (oldSectionEl) oldSectionEl.classList.remove('active-section');
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
            setActiveSection(link.dataset.section, index);
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
        setHtml(clanCapitalDistrictsEl, data.capital_districts?.map(d => `<p><strong>${d.name || 'N/A'}:</strong> Nv ${d.level || '?'}</p>`).join('') || '<p>Nenhum distrito encontrado.</p>');
        setText(botVersionEl, data.version, '?');
    }

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
        setText(warDateHighlightEl, data.war_date ? `(${data.war_date})` : '');

        setHtml(topDonorsListEl, data.top_donors?.map((donor, index) => {
            const medals = ['gold', 'silver', 'bronze'];
            const medal_icons = ['🥇', '🥈', '🥉'];
            return `<div class="podium-item ${medals[index] || ''}">
                        <span class="podium-rank">${medal_icons[index] || ''}</span>
                        <div class="podium-details">
                            <div class="member-name">${donor.name} (CV${donor.town_hall})</div>
                            <div class="donation-count"><strong>${donor.donations.toLocaleString()}</strong> tropas doadas</div>
                        </div>
                    </div>`;
        }).join('') || '<p>Nenhum doador encontrado.</p>');

        const warHeroTitleEl = document.getElementById('warHeroTitle');
        setText(warHeroTitleEl, '⚔️ Heróis da Última Guerra');
        setHtml(bestAttacksListEl, data.war_heroes?.map(hero => {
            const isMvp = hero.rank === 1;
            const heroClass = isMvp ? 'mvp-card' : 'attack-item';
            const medals = ['🥇', '🥈', '🥉'];
            const titleHtml = isMvp 
                ? `<p class="mvp-title">Jogador Mais Valioso (MVP)</p><h4 class="mvp-name">${hero.name} <span>(CV${hero.town_hall})</span></h4>`
                : `<div class="attack-header">${medals[hero.rank - 1] || ''} ${hero.name} (CV${hero.town_hall})</div>`;
            
            return `<div class="${heroClass}">
                        ${titleHtml}
                        <span class="tooltip-text">${hero.reason}</span>
                    </div>`;
        }).join('') || '<p>Nenhum herói para destacar na última guerra.</p>');

        if (activityChart) activityChart.destroy();
        if (data.activity_chart_data?.labels.length > 0) {
            activityChart = new Chart(activityChartCanvas.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: data.activity_chart_data.labels,
                    datasets: [
                        { label: 'Tropas Doadas', data: data.activity_chart_data.donations, backgroundColor: 'rgba(54, 162, 235, 0.6)' },
                        { label: 'Tropas Recebidas', data: data.activity_chart_data.received, backgroundColor: 'rgba(255, 99, 132, 0.6)' }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, ticks: { color: 'rgba(255, 255, 255, 0.7)' } }, x: { ticks: { color: 'rgba(255, 255, 255, 0.7)' } } }, plugins: { legend: { labels: { color: 'rgba(255, 255, 255, 0.8)' } } } }
            });
        }
    }

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
            if (noWarMsg) { noWarMsg.style.display = 'block'; setText(noWarMsg, data.error || "Nenhuma guerra para detalhar."); }
            if (warHeader) warHeader.style.display = 'none';
            if (warTabsNav) warTabsNav.style.display = 'none';
            container.querySelectorAll('.war-tab-content').forEach(tab => tab.style.display = 'none');
            const predictionSection = container.querySelector('#warPredictionSection');
            if (predictionSection) predictionSection.style.display = 'none';
            return;
        }
        
        if (!isModal) {
            const predictionSection = container.querySelector('#warPredictionSection');
            const predictionTextEl = container.querySelector('#warPredictionText');
            const predictionTagsEl = container.querySelector('#warPredictionTags');
    
            if (predictionSection && predictionTextEl && predictionTagsEl && data.prediction && data.prediction.summary_panel) {
                setText(predictionTextEl, data.prediction.summary_panel);
                predictionTagsEl.innerHTML = `
                    <div class="prediction-tag">
                        <span class="prediction-tag-icon">🎯</span>
                        <div class="prediction-tag-text">
                            <span class="tag-label">Probabilidade</span>
                            <span class="tag-value">${(data.prediction.probability || 0).toFixed(1)}%</span>
                        </div>
                        <span class="tooltip-text">Chance de vitória do nosso clã no final da guerra, calculada pela IA.</span>
                    </div>
                    <div class="prediction-tag">
                        <span class="prediction-tag-icon">🧠</span>
                        <div class="prediction-tag-text">
                            <span class="tag-label">Confiança</span>
                            <span class="tag-value">${(data.prediction.confidence || 0).toFixed(1)}%</span>
                        </div>
                        <span class="tooltip-text">Nível de certeza da IA sobre a sua própria previsão, baseado na qualidade e quantidade de dados disponíveis.</span>
                    </div>`;
                predictionSection.style.display = 'block';
            } else if (predictionSection) {
                predictionSection.style.display = 'none';
            }
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
        
        const populateStats = (p) => {
            setText(container.querySelector(`#${p}statsOurAvgStars`), war.clan_avg_stars);
            setText(container.querySelector(`#${p}statsOurAvgDuration`), war.clan_avg_duration);
            setText(container.querySelector(`#${p}statsOpponentAvgStars`), war.opponent_avg_stars);
            setText(container.querySelector(`#${p}statsOpponentAvgDuration`), war.opponent_avg_duration);
            for(let i=0; i<=3; i++) {
                setText(container.querySelector(`#${p}statsOurStars${i}`), war.clan_star_distribution[i]);
                setText(container.querySelector(`#${p}statsOpponentStars${i}`), war.opponent_star_distribution[i]);
            }
        };
        populateStats(prefix);

        const eventsTableBody = container.querySelector(`#${prefix}warEventsTableBody`);
        setText(container.querySelector(`#${prefix}warTotalAttacksCount`), data.all_attacks.length);
        setHtml(eventsTableBody, data.all_attacks.map(att => `
            <tr>
                <td>${att.order}</td>
                <td>${att.attacker_name} (CV${att.attacker_townhall})</td>
                <td><span class="attack-stars">${createStarString(att.stars)}</span> ${att.destruction}%</td>
                <td>${att.defender_name} (CV${att.defender_townhall})</td>
                <td>${att.duration}</td>
            </tr>
        `).join('') || '<tr><td colspan="5">Nenhum ataque registrado.</td></tr>');

        const populateTeamTabData = (teamMembersData, teamNameKey, teamElement) => {
            setText(container.querySelector(`#${prefix}war${teamNameKey}TeamName`), war[`${teamNameKey === 'Our' ? 'clan' : 'opponent'}_name`]);
            setHtml(teamElement, teamMembersData.map(member => {
                const attacksHtml = '<h5>Ataques Feitos:</h5><ul class="member-attack-list">' + 
                    (member.attacks_made?.length > 0 
                        ? member.attacks_made.map(atk => `<li>${createStarString(atk.stars)} ${atk.destruction}% vs ${atk.defender_name} (CV${atk.defender_townhall})</li>`).join('')
                        : '<li>Nenhum ataque feito.</li>') + '</ul>';

                const defensesHtml = '<h5>Defesas Recebidas:</h5><ul class="member-defense-list">' +
                    (member.defenses_received?.length > 0
                        ? member.defenses_received.map(def => `<li>${createStarString(def.stars)} ${def.destruction}% por ${def.attacker_name} (CV${def.attacker_townhall})</li>`).join('')
                        : '<li>Nenhuma defesa registrada.</li>') + '</ul>';

                return `<div class="team-member-card">
                            <h4><img src="/static/images/townhall${member.townhall}.png" alt="CV${member.townhall}" onerror="this.style.display='none'"/> ${member.map_position}. ${member.name} (CV${member.townhall})</h4>
                            <p>Ataques: ${member.attacks_used}/${war.attacks_per_member}</p>
                            ${attacksHtml}${defensesHtml}
                        </div>`;
            }).join('') || '<p>Nenhum membro nesta equipe para a guerra.</p>');
        };

        populateTeamTabData(data.our_clan_members_in_war, "Our", container.querySelector(`#${prefix}warOurTeamMembers`));
        populateTeamTabData(data.opponent_clan_members_in_war, "Opponent", container.querySelector(`#${prefix}warOpponentTeamMembers`));
        
        if (!container.querySelector('.war-tab-button.active')) {
            container.querySelector('.war-tab-button[data-tab="war-stats"]')?.classList.add('active');
            container.querySelector(isModal ? '#historic-war-stats' : '#war-stats').style.display = 'block';
        }
    }

    function populateMissedAttacksHistory(data) {
        setText(attacksRemainingTitleEl.querySelector('span'), data.clan_name);

        if (data.error || !data.wars_with_missed_attacks?.length) {
            setHtml(missedAttacksContainerEl, '');
            if (noMissedAttacksMessageEl) { noMissedAttacksMessageEl.style.display = 'block'; setText(noMissedAttacksMessageEl, data.error || "Nenhuma pendência de ataque encontrada."); }
            return;
        }

        if (noMissedAttacksMessageEl) noMissedAttacksMessageEl.style.display = 'none';
        setHtml(missedAttacksContainerEl, data.wars_with_missed_attacks.map(war => `
            <div class="war-group">
                <h3 class="war-group-header">Guerra vs <strong>${war.opponent_name}</strong> (${war.end_date}) ${war.is_latest ? '<span class="latest-war-badge">💥 Última Guerra</span>' : ''}</h3>
                <div class="player-card-grid">
                    ${war.missed_attacks_members.map(member => `
                        <div class="missed-attack-card ${member.attacks_left >= 2 ? 'severity-high' : 'severity-medium'}">
                            <div class="player-info">
                                <h4>${member.name} <span>(CV${member.town_hall})</span></h4>
                                <div class="player-tag-container">
                                    <span class="player-tag">${member.tag}</span>
                                </div>
                            </div>
                            <div class="attacks-info">
                                <span class="attacks-count">${member.attacks_left}</span>
                                <span class="attacks-label">Ataque${member.attacks_left > 1 ? 's' : ''} Pendente${member.attacks_left > 1 ? 's' : ''}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join(''));
    }

    function populateCwlInfo(data) {
        if (data.error || data.status === "NotInCwl" || data.status === "CwlFeatureDisabled") {
            if(noCwlMessageEl) noCwlMessageEl.style.display = 'block';
            setText(noCwlMessageEl, data.message || data.error || "CWL indisponível.");
            if(cwlActiveInfoEl) cwlActiveInfoEl.style.display = 'none';
            return;
        }
        if(noCwlMessageEl) noCwlMessageEl.style.display = 'none';
        if(cwlActiveInfoEl) cwlActiveInfoEl.style.display = 'block';
        setText(cwlSeasonEl, data.season);
        setText(cwlGroupStateEl, data.state);
        setHtml(cwlGroupClansEl, data.clans_in_group?.map(c => `<p><img src="${c.badge_url || DEFAULT_BADGE_URL}" alt="Emblema ${c.name}"> <strong>${c.name}</strong> (${c.tag}) Nv ${c.level}</p>`).join('') || '<p>Nenhum clã no grupo.</p>');
        setHtml(cwlRoundsInfoEl, data.rounds?.map(r => `
            <div class="cwl-round">
                <h4>Rodada ${r.round_number}</h4>
                ${r.wars?.map(w => {
                    if (w.error) return `<p class="cwl-war-entry">Guerra (${w.war_tag || 'N/A'}): ${w.error}</p>`;
                    if (w.message) return `<p class="cwl-war-entry">${w.message}</p>`;
                    return `<p class="cwl-war-entry">
                                <strong><img src="${w.clan_badge_url}" class="cwl-war-badge"> ${w.clan_name}</strong> ${w.clan_stars}⭐ vs ${w.opponent_stars}⭐ <strong><img src="${w.opponent_badge_url}" class="cwl-war-badge"> ${w.opponent_name}</strong>
                                <br><small>Estado: ${w.state}</small>
                            </p>`;
                }).join('') || "<p>Nenhuma guerra nesta rodada.</p>"}
            </div>
        `).join('') || "Nenhuma info de rodada.");
    }

    function populateWarLog(data) {
        setText(warLogLimitEl, data.log?.length || '0');
        if (data.error || !data.log?.length) {
            if(noWarLogMessageEl) noWarLogMessageEl.style.display = 'block';
            setText(noWarLogMessageEl, data.error || "Log de guerra indisponível.");
            setHtml(warLogTableBodyEl, `<tr><td colspan="6">${data.error || "Nenhum registro encontrado."}</td></tr>`);
            return;
        }
        if(noWarLogMessageEl) noWarLogMessageEl.style.display = 'none';
        setHtml(warLogTableBodyEl, data.log.map(e => `
            <tr class="historic-war-row" data-war-id="${e.end_time_iso}">
                <td>${e.end_time_formatted}</td>
                <td><img src="${e.opponent_badge_url}" alt="Emblema" class="log-opponent-badge">${e.opponent_name || 'N/A'}</td>
                <td>${e.clan_stars}⭐ vs ${e.opponent_stars}⭐</td>
                <td class="war-result-${e.result?.toLowerCase()}">${e.result}</td>
                <td>${e.team_size}</td>
                <td>${e.is_cwl ? "CWL" : "Normal"}</td>
            </tr>
        `).join(''));
    }

    // --- CARREGAMENTO INICIAL E PERIÓDICO ---
    async function loadAllData() {
        try {
            const [clanData, membersData, currentWarDetailsData, missedAttacksData, warLogData, cwlInfoData, highlightsData] = await Promise.all([
                fetchData('clan'), fetchData('members'), fetchData('current_war_details'),
                fetchData('missed_attacks_history'), fetchData('war_log'), fetchData('cwl_info'), fetchData('highlights')
            ]);
            populateClanInfo(clanData);
            populateMembersList(membersData);
            populateWarDetails(currentWarDetailsData, 'war-details-nav', false);
            populateMissedAttacksHistory(missedAttacksData);
            populateWarLog(warLogData);
            populateCwlInfo(cwlInfoData);
            populateHighlights(highlightsData);
            updateLastUpdated();
        } catch (error) {
            console.error("Erro ao carregar todos os dados:", error);
        } finally {
            if (isFirstLoad && loadingOverlayEl) {
                setTimeout(() => { loadingOverlayEl.classList.add('hidden'); }, 500);
                isFirstLoad = false;
            }
        }
    }
    
    // --- EVENT LISTENERS DOS MODAIS ---
    if (closeModalButton) closeModalButton.addEventListener('click', () => historicWarModal.style.display = 'none');
    if (closeProfileModalButton) closeProfileModalButton.addEventListener('click', () => memberProfileModal.style.display = 'none');
    window.addEventListener('click', (event) => {
        if (event.target == historicWarModal) historicWarModal.style.display = 'none';
        if (event.target == memberProfileModal) memberProfileModal.style.display = 'none';
    });
    warLogTableBodyEl.addEventListener('click', (event) => {
        const row = event.target.closest('.historic-war-row');
        if (row && row.dataset.warId) {
             // Lógica para abrir modal de guerra histórica
        }
    });

    loadAllData();
    setInterval(loadAllData, 60000);
});

