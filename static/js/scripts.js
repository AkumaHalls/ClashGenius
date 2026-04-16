document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = '';
    const DEFAULT_BADGE_URL = '/static/images/default_badge.png';
    let phaseTimerInterval = null; 

    // --- ELEMENTOS DO DOM ---
    const loadingOverlayEl = document.getElementById('loading-overlay');
    const loadingStatusTextEl = loadingOverlayEl?.querySelector('p'); 
    const backgroundMusicEl = document.getElementById('background-music');
    const muteButtonEl = document.getElementById('mute-button');
    const adminLinkBtn = document.querySelector('.admin-link-btn');

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

    const warTabButtons = document.querySelectorAll('.war-tab-button');
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
    const warAdvisorContentEl = document.getElementById('warAdvisorContent');

    const attacksRemainingTitleEl = document.getElementById('attacksRemainingTitle');
    const missedAttacksContainerEl = document.getElementById('missedAttacksContainer');
    const noMissedAttacksMessageEl = document.getElementById('noMissedAttacksMessage');

    const cwlActiveInfoEl = document.getElementById('cwlActiveInfo');
    const noCwlMessageEl = document.getElementById('noCwlMessage');

    const cwlPlannerSectionEl = document.getElementById('cwlPlannerSection');
    const cwlPlanResultEl = document.getElementById('cwlPlanResult');
    const cwlPlanContentEl = document.getElementById('cwlPlanContent');
    const cwlInactivityAlertEl = document.getElementById('cwlInactivityAlert');
    const cwlInactivityTextEl = document.getElementById('cwlInactivityText');
    const cwlOverviewContainerEl = document.getElementById('cwlOverviewContainer'); 
    const cwlPlanDaysTabsEl = document.getElementById('cwlPlanDaysTabs'); 
    const cwlPlanWarningEl = document.getElementById('cwlPlanWarning'); 

    const warLogLimitEl = document.getElementById('warLogLimit');
    const warLogTableBodyEl = document.getElementById('warLogTableBody');
    const noWarLogMessageEl = document.getElementById('noWarLogMessage');

    const membersClanNameEl = document.getElementById('membersClanName');
    const filterNameInput = document.getElementById('filterName');
    const filterTHInput = document.getElementById('filterTH');
    const membersGridEl = document.getElementById('membersGrid');

    const capitalContentEl = document.getElementById('capitalContent');
    const capStatusEl = document.getElementById('capStatus');
    const capTotalLootEl = document.getElementById('capTotalLoot');
    const capTotalAttacksEl = document.getElementById('capTotalAttacks');
    const capDestroyedEl = document.getElementById('capDestroyed');
    const capTopAttackersListEl = document.getElementById('capTopAttackersList');
    const capZeroAttacksListEl = document.getElementById('capZeroAttacksList');
    const capIncompleteAttacksListEl = document.getElementById('capIncompleteAttacksList');
    const noCapitalMessageEl = document.getElementById('noCapitalMessage');

    const cgContentEl = document.getElementById('cgContent');
    const cgTotalPointsEl = document.getElementById('cgTotalPoints');
    const cgMaxPointsEl = document.getElementById('cgMaxPoints');
    const cgProgressBarEl = document.getElementById('cgProgressBar');
    const cgProgressTextEl = document.getElementById('cgProgressText');
    const cgTopPlayersListEl = document.getElementById('cgTopPlayersList');
    const cgZeroPlayersListEl = document.getElementById('cgZeroPlayersList');
    const noClanGamesMessageEl = document.getElementById('noClanGamesMessage');

    const botVersionEl = document.getElementById('botVersion');
    const lastUpdatedEl = document.getElementById('lastUpdated');

    const navLinks = document.querySelectorAll('.nav-link');
    const contentSections = document.querySelectorAll('.content-section');
    let isFirstLoad = true;
    let userIsAdmin = false; 

    const historicWarModal = document.getElementById('historicWarModal');
    const historicWarDetailContent = document.getElementById('historicWarDetailContent');
    const closeModalButton = historicWarModal?.querySelector('.close-button'); 

    const memberProfileModal = document.getElementById('memberProfileModal');
    const memberProfileContent = document.getElementById('memberProfileContent');
    const closeProfileModalButton = memberProfileModal?.querySelector('.close-button'); 
    let memberTrophyChart = null;

    let cwlPlanCached = null;
    let isFetchingCwlPlan = false;
    let activeCwlTabDay = null;

    const vipStyle = document.createElement('style');
    vipStyle.innerHTML = `
        .vip-golden-card {
            border: 1px solid #ffd700 !important;
            background: linear-gradient(135deg, rgba(255, 215, 0, 0.15) 0%, rgba(20, 20, 20, 0.9) 100%) !important;
            box-shadow: 0 4px 15px rgba(255, 215, 0, 0.15);
            position: relative;
            overflow: hidden;
        }
        .vip-golden-card:hover {
            box-shadow: 0 6px 20px rgba(255, 215, 0, 0.3);
            border-color: #ffdf00 !important;
        }
        .vip-golden-card .member-info h4 {
            color: #ffd700 !important;
            text-shadow: 0 0 8px rgba(255, 215, 0, 0.4);
        }
        .vip-ribbon {
            position: absolute;
            top: 12px;
            right: -32px;
            background: linear-gradient(90deg, #ff8c00, #ffd700);
            color: #000;
            font-weight: 900;
            font-size: 0.65em;
            padding: 4px 35px;
            transform: rotate(45deg);
            box-shadow: 0 2px 5px rgba(0,0,0,0.5);
            letter-spacing: 1px;
            z-index: 1;
        }
        .vip-golden-card .member-card-header, 
        .vip-golden-card .member-card-stats,
        .vip-golden-card .member-card-note,
        .vip-golden-card .member-cwl-status {
            position: relative;
            z-index: 2;
        }
        .xai-badge { display: inline-block; font-size: 0.8em; padding: 2px 6px; background: rgba(54, 162, 235, 0.2); border: 1px solid #36a2eb; color: #36a2eb; border-radius: 4px; margin-top: 5px; font-family: monospace; }
        .xai-sub { background: rgba(0,0,0,0.3); padding: 10px; border-left: 3px solid var(--color-warning); margin-bottom: 10px; font-size: 0.9em; border-radius: 4px;}
        .podium-item:hover .tooltip-text { visibility: visible; opacity: 1; }
    `;
    document.head.appendChild(vipStyle);

    async function fetchData(endpoint, options = {}) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/${endpoint}`, options);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: `Erro HTTP ${response.status}` }));
                const errorMessage = errorData.error || errorData.message || `Falha ao carregar ${endpoint}.`;
                if (response.status === 503 && loadingOverlayEl && !loadingOverlayEl.classList.contains('hidden')) {
                    setText(loadingStatusTextEl, 'Aguardando API CoC ficar pronta...');
                }
                return { error: errorMessage };
            }
            if (response.status === 204) return { success: true };
            return await response.json();
        } catch (error) {
            console.error(`Erro de conexão ao buscar ${endpoint}:`, error);
            return { error: `Erro de conexão ao buscar ${endpoint}.` };
        }
    }

    if (backgroundMusicEl && muteButtonEl) {
        backgroundMusicEl.volume = 0.2;
        let musicStarted = false; 
        const playMusic = async () => {
            if (musicStarted) return; 
            try {
                await backgroundMusicEl.play();
                musicStarted = true; 
                document.body.removeEventListener('click', playMusic);
                document.body.removeEventListener('keydown', playMusic);
            } catch (err) {
                musicStarted = true; 
            }
        };
        document.body.addEventListener('click', playMusic, { once: true });
        document.body.addEventListener('keydown', playMusic, { once: true });

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

    function updateLastUpdated() {
        const now = new Date();
        setText(lastUpdatedEl, `Última atualização: ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`);
    }

    function setText(element, text, defaultValue = '-') {
        if (element) {
            const finalText = (text === null || text === undefined || text === '') ? defaultValue : String(text);
            element.textContent = finalText;
        }
    }

    function setHtml(element, htmlContent) {
        if (element) element.innerHTML = htmlContent;
    }

    function setBadge(element, url) {
        if (element) {
                element.src = url || DEFAULT_BADGE_URL;
                element.onerror = () => { element.src = DEFAULT_BADGE_URL; };
        }
    }

    const initialSectionId = navLinks.length > 0 ? navLinks[0].dataset.section : 'clan-info-nav';
    let currentActiveSectionId = localStorage.getItem('activeSection') || initialSectionId;

    contentSections.forEach(section => {
        section?.classList.toggle('active-section', section.id === currentActiveSectionId); 
    });
    navLinks.forEach(link => {
        link?.classList.toggle('active-nav-link', link.dataset.section === currentActiveSectionId); 
    });

    function setActiveSection(newSectionId) {
        if (!newSectionId || newSectionId === currentActiveSectionId) return; 
        const oldSectionEl = document.getElementById(currentActiveSectionId);
        const newSectionEl = document.getElementById(newSectionId);
        if (!newSectionEl) return; 

        oldSectionEl?.classList.remove('active-section'); 
        navLinks.forEach(link => link?.classList.remove('active-nav-link')); 

        newSectionEl.classList.add('active-section');
        const newLink = document.querySelector(`.nav-link[data-section="${newSectionId}"]`);
        newLink?.classList.add('active-nav-link'); 

        localStorage.setItem('activeSection', newSectionId);
        currentActiveSectionId = newSectionId;
    }

    navLinks.forEach((link) => {
        link?.addEventListener('click', (e) => { 
            e.preventDefault(); 
            setActiveSection(link.dataset.section);
        });
    });

    function populateClanInfo(data) {
        if (!data || data.error || !data.name) {
            setText(clanNameHeaderEl, "Erro");
            setText(clanNameEl, data?.error || "N/A"); 
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
        setText(clanWarWinsEl, `${data.war_wins?.toLocaleString() || '-'} ⚔️`); 
        setText(clanPointsEl, `${data.points?.toLocaleString() || '-'} 🏆`); 
        setText(clanCapitalPointsEl, `${data.capital_points?.toLocaleString() || '-'} 🏆`); 
        setText(clanCapitalLeagueEl, data.capital_league);
        setText(clanDescriptionEl, data.description, 'Sem descrição.');
        setText(botVersionEl, data.version, '?');
    }

    function populateHighlights(data) {
        const highlightsContentEl = document.getElementById('highlightsContent'); 
        if (!data || data.error || !data.clan_name) {
            if (noHighlightsMessageEl) {
                noHighlightsMessageEl.style.display = 'block';
                setText(noHighlightsMessageEl, data?.error || "Não foi possível carregar os destaques.");
            }
            if(highlightsContentEl) highlightsContentEl.style.display = 'none'; 
            return;
        }

        if (noHighlightsMessageEl) noHighlightsMessageEl.style.display = 'none';
        if (highlightsContentEl) highlightsContentEl.style.display = 'block';

        setText(highlightsClanNameEl, data.clan_name);
        setText(warDateHighlightEl, data.war_date ? `(${data.war_date})` : ''); 

        setHtml(topDonorsListEl, data.top_donors?.length > 0 ? data.top_donors.map((donor, index) => {
            const medals = ['gold', 'silver', 'bronze'];
            const medal_icons = ['🥇', '🥈', '🥉'];
            const rankIcon = medal_icons[index] || `${index + 1}.`; 
            return `<div class="podium-item ${medals[index] || ''}" style="position: relative;">
                        <span class="podium-rank">${rankIcon}</span>
                        <div class="podium-details">
                            <div class="member-name">${donor.name || 'N/A'} (CV${donor.town_hall || '?'})</div>
                            <div class="donation-count"><strong>${(donor.donations || 0).toLocaleString()}</strong> tropas doadas</div>
                        </div>
                        ${donor.reason ? `<span class="tooltip-text" style="width:250px; background-color: var(--color-background); color: #fff; text-align: center; border-radius: 6px; padding: 10px; position: absolute; z-index: 10; bottom: 110%; left: 50%; margin-left: -125px; opacity: 0; transition: opacity 0.3s; font-size: 0.85em; border: 1px solid var(--color-border-light); box-shadow: 0 4px 8px rgba(0,0,0,0.3); pointer-events: none;">${donor.reason}</span>` : ''}
                    </div>`;
        }).join('') : '<p>Nenhum doador encontrado.</p>');

        const warHeroTitleEl = document.getElementById('warHeroTitle');
        setText(warHeroTitleEl, '⚔️ Heróis da Última Guerra'); 
        setHtml(bestAttacksListEl, data.war_heroes?.length > 0 ? data.war_heroes.map(hero => {
            const isMvp = hero.rank === 1;
            const heroClass = isMvp ? 'mvp-card' : 'attack-item';
            const medals = ['🥇', '🥈', '🥉'];
            const rankIcon = medals[hero.rank - 1] || `${hero.rank}.`; 

            const titleHtml = isMvp
                ? `<p class="mvp-title">Jogador Mais Valioso (MVP)</p><h4 class="mvp-name">${hero.name || 'N/A'} <span>(CV${hero.town_hall || '?'})</span></h4>`
                : `<div class="attack-header">${rankIcon} ${hero.name || 'N/A'} (CV${hero.town_hall || '?'})</div>`;

            return `<div class="${heroClass}">
                        ${titleHtml}
                        <span class="tooltip-text" style="pointer-events: none;">${hero.reason || 'Sem detalhes'}</span>
                    </div>`;
        }).join('') : '<p>Nenhum herói para destacar na última guerra ou análise indisponível.</p>'); 

        if (activityChart) {
            try { activityChart.destroy(); activityChart = null; } catch(e) {}
        }

        const chartData = data.activity_chart_data;
        if (activityChartCanvas && chartData && chartData.labels && chartData.labels.length > 0 && chartData.donations && chartData.received) {
            try {
                const ctx = activityChartCanvas.getContext('2d');
                if (!ctx) throw new Error("Não foi possível obter o contexto 2D do canvas."); 
                activityChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: chartData.labels,
                        datasets: [
                            { label: 'Tropas Doadas', data: chartData.donations, backgroundColor: 'rgba(54, 162, 235, 0.6)' },
                            { label: 'Tropas Recebidas', data: chartData.received, backgroundColor: 'rgba(255, 99, 132, 0.6)' }
                        ]
                    },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        scales: {
                            y: { beginAtZero: true, ticks: { color: 'rgba(255, 255, 255, 0.7)' } },
                            x: { ticks: { color: 'rgba(255, 255, 255, 0.7)' } }
                        },
                        plugins: { legend: { labels: { color: 'rgba(255, 255, 255, 0.8)' } } }
                    }
                });
            } catch (e) {
                if (activityChartCanvas) {
                    const ctx = activityChartCanvas.getContext('2d');
                    if (ctx) {
                        ctx.clearRect(0, 0, activityChartCanvas.width, activityChartCanvas.height);
                        ctx.fillStyle = 'rgba(255, 100, 100, 0.8)'; 
                        ctx.textAlign = 'center';
                        ctx.font = '14px Open Sans';
                        ctx.fillText('Erro ao renderizar o gráfico.', activityChartCanvas.width / 2, activityChartCanvas.height / 2);
                    }
                }
            }
        } else if (activityChartCanvas) {
            try {
                const ctx = activityChartCanvas.getContext('2d');
                if (ctx) {
                    ctx.clearRect(0, 0, activityChartCanvas.width, activityChartCanvas.height);
                    ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
                    ctx.textAlign = 'center';
                    ctx.font = '14px Open Sans';
                    ctx.fillText('Dados de atividade indisponíveis para o gráfico.', activityChartCanvas.width / 2, activityChartCanvas.height / 2);
                }
            } catch(e) {}
        }
    }

    function createStarString(stars) {
        const starCount = parseInt(stars, 10); 
        if (isNaN(starCount) || starCount < 0) return '⚫⚫⚫'; 
        return '⭐'.repeat(starCount) + '⚫'.repeat(Math.max(0, 3 - starCount));
    }

    function populateWarDetails(data, containerId = 'war-details-nav', isModal = false) {
        const container = document.getElementById(containerId);
        if (!container) return; 
        const prefix = isModal ? 'historic-' : ''; 
        const warHeader = container.querySelector('.war-header');
        const warTabsNav = container.querySelector('.war-tabs');
        const noWarMsg = container.querySelector(isModal ? `#${prefix}noWarDetailMessage` : '#noWarDetailMessage');
        const predictionSection = container.querySelector(isModal ? null : '#warPredictionSection');

        if (!data || data.error || !data.war_data) {
            if (noWarMsg) { noWarMsg.style.display = 'block'; setText(noWarMsg, data?.error || "Nenhuma guerra para detalhar."); }
            if (warHeader) warHeader.style.display = 'none';
            if (warTabsNav) warTabsNav.style.display = 'none';
            container.querySelectorAll('.war-tab-content').forEach(tab => tab.style.display = 'none'); 
            if (predictionSection) predictionSection.style.display = 'none'; 
            return;
        }

        if (!isModal && predictionSection) {
            const predictionTextEl = container.querySelector('#warPredictionText');
            const predictionTagsEl = container.querySelector('#warPredictionTags');
            if (data.prediction && data.prediction.summary_panel) {
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
            } else {
                predictionSection.style.display = 'none'; 
            }
        } else if (predictionSection) {
                predictionSection.style.display = 'none'; 
        }

        if (noWarMsg) noWarMsg.style.display = 'none'; 
        if (warHeader) warHeader.style.display = 'flex'; 
        if (warTabsNav) warTabsNav.style.display = 'flex'; 

        const war = data.war_data;
        const query = (sel) => container.querySelector(sel); 

        setText(query(`#${prefix}warDetailOurClanName`), war.clan_name);
        setText(query(`#${prefix}warDetailOpponentName`), war.opponent_name);
        setBadge(query(`#${prefix}warDetailClanBadge`), war.clan_badge_url);
        setBadge(query(`#${prefix}warDetailOpponentBadge`), war.opponent_badge_url);
        setText(query(`#${prefix}warDetailTimeKey`), war.time_key);
        setText(query(`#${prefix}warDetailTimeValue`), war.time_value);
        setText(query(`#${prefix}warDetailTimeRemaining`), war.time_remaining);
        const stateEl = query(`#${prefix}warDetailState`);
        setText(stateEl, war.state_description);
        if(stateEl) stateEl.className = 'war-state ' + (war.status || '').toLowerCase(); 

        setText(query(`#${prefix}statsOurClanName`), war.clan_name);
        setText(query(`#${prefix}statsOurStars`), war.clan_stars);
        setText(query(`#${prefix}statsOurDestruction`), war.clan_destruction?.replace('%', ''));
        setText(query(`#${prefix}statsOurAttacksUsed`), `${war.clan_attacks_used}/${war.team_size * war.attacks_per_member}`);
        setText(query(`#${prefix}statsOpponentName`), war.opponent_name);
        setText(query(`#${prefix}statsOpponentStars`), war.opponent_stars);
        setText(query(`#${prefix}statsOpponentDestruction`), war.opponent_destruction?.replace('%', ''));
        setText(query(`#${prefix}statsOpponentAttacksUsed`), `${war.opponent_attacks_used}/${war.team_size * war.attacks_per_member}`);
        setText(query(`#${prefix}statsOurAvgStars`), war.clan_avg_stars);
        setText(query(`#${prefix}statsOurAvgDuration`), war.clan_avg_stars); 
        setText(query(`#${prefix}statsOpponentAvgStars`), war.opponent_avg_stars);
        if(war.clan_star_distribution){
                for(let i=0; i<=3; i++) setText(query(`#${prefix}statsOurStars${i}`), war.clan_star_distribution[i]);
        }
        if(war.opponent_star_distribution){
                for(let i=0; i<=3; i++) setText(query(`#${prefix}statsOpponentStars${i}`), war.opponent_star_distribution[i]);
        }

        const eventsTableBody = query(`#${prefix}warEventsTableBody`);
        setText(query(`#${prefix}warTotalAttacksCount`), data.all_attacks?.length || 0); 
        setHtml(eventsTableBody, data.all_attacks?.length > 0 ? data.all_attacks.map(att => `
            <tr>
                <td>${att.order ?? '-'}</td>
                <td>${att.attacker_name || '?'} (CV${att.attacker_townhall || '?'})</td>
                <td><span class="attack-stars">${createStarString(att.stars)}</span> ${att.destruction ?? 0}%</td>
                <td>${att.defender_name || '?'} (CV${att.defender_townhall || '?'})</td>
                <td>${att.duration ?? '-'}</td>
            </tr>
        `).join('') : '<tr><td colspan="5">Nenhum ataque registado.</td></tr>');

        const populateTeamTabData = (teamMembersData, teamName, teamElementId) => {
            const teamMembersEl = query(`#${prefix}${teamElementId}Members`);
            setText(query(`#${prefix}${teamElementId}Name`), teamName);
            setHtml(teamMembersEl, teamMembersData?.length > 0 ? teamMembersData.map(member => {
                const attacksHtml = '<h5>Ataques Feitos:</h5><ul class="member-attack-list">' +
                    (member.attacks_made?.length > 0
                        ? member.attacks_made.map(atk => `<li>${createStarString(atk.stars)} ${atk.destruction ?? 0}% vs ${atk.defender_name || '?'} (CV${atk.defender_townhall || '?'})</li>`).join('')
                        : '<li>Nenhum ataque feito.</li>') + '</ul>';
                const defensesHtml = '<h5>Defesas Recebidas:</h5><ul class="member-defense-list">' +
                    (member.defenses_received?.length > 0
                        ? member.defenses_received.map(def => `<li>${createStarString(def.stars)} ${def.destruction ?? 0}% por ${def.attacker_name || '?'} (CV${def.attacker_townhall || '?'})</li>`).join('')
                        : '<li>Nenhuma defesa registada.</li>') + '</ul>';
                return `<div class="team-member-card">
                            <h4><img src="/static/images/townhall${member.townhall || 1}.png" alt="CV${member.townhall || '?'}" onerror="this.onerror=null; this.src=DEFAULT_BADGE_URL; this.style.height='28px';"/> ${member.map_position || '?'}. ${member.name || 'N/A'} (CV${member.townhall || '?'})</h4>
                            <p>Ataques: ${member.attacks_used ?? 0}/${war.attacks_per_member}</p>
                            ${attacksHtml}${defensesHtml}
                        </div>`;
            }).join('') : '<p>Nenhum membro nesta equipa para a guerra.</p>');
        };

        populateTeamTabData(data.our_clan_members_in_war, war.clan_name, "warOurTeam");
        populateTeamTabData(data.opponent_clan_members_in_war, war.opponent_name, "warOpponentTeam");

        const currentActiveTab = query('.war-tab-button.active');
        if (!currentActiveTab || !currentActiveTab.closest(`#${containerId}`)) { 
            const firstTabButton = query('.war-tab-button');
            const firstTabContentId = isModal ? `#historic-${firstTabButton?.dataset.tab}` : `#${firstTabButton?.dataset.tab}`;
            const firstTabContent = query(firstTabContentId);
            container.querySelectorAll('.war-tab-button').forEach(btn => btn.classList.remove('active'));
            container.querySelectorAll('.war-tab-content').forEach(cont => cont.style.display = 'none');
            firstTabButton?.classList.add('active');
            if(firstTabContent) firstTabContent.style.display = 'block';
        }
    }

    function populateWarAdvisorPlan(data) {
        if (!warAdvisorContentEl) return;
        if (phaseTimerInterval) { clearInterval(phaseTimerInterval); phaseTimerInterval = null; }

        const setupAdvisorUI = (planData) => {
            if (!planData || !planData.success) {
                const timerEl = warAdvisorContentEl.querySelector('#advisorPhaseTimer');
                if(timerEl) timerEl.style.display = 'none';
                setHtml(warAdvisorContentEl, `<div class="advisor-plan-container"><p class="message-box">${planData?.error || 'Nenhuma recomendação disponível.'}</p></div>`);
                return;
            }
            let contentHtml = `
                <div id="advisorPhaseTimer" class="advisor-phase-timer" style="display: none;"><h4>MUDANÇA DE FASE</h4><p id="advisorPhaseTimerText">Calculando...</p></div>
                <div class="advisor-header">
                    <h3>${planData.phase_title || 'Plano de Ataque'}</h3>
                    <p>${planData.prediction_summary || '-'}</p>
                </div>
                <div class="advisor-grid">`;
            contentHtml += planData.recommendations?.length > 0 ? planData.recommendations.map(rec => {
                const confidencePercent = ((rec.confidence_score || 0) * 100).toFixed(0);
                let confidenceColor = 'low';
                if (confidencePercent >= 75) confidenceColor = 'high';
                else if (confidencePercent >= 50) confidenceColor = 'medium';
                const alternativesHtml = rec.alternative_targets?.length > 0 ? `<div class="advisor-alternatives"><strong>Alternativas:</strong> #${rec.alternative_targets.join(', #')}</div>` : '';
                return `
                    <div class="advisor-card type-${rec.attack_type || 'unknown'}">
                        <div class="advisor-member-info">
                            <h4>${rec.member_pos || '?'}. ${rec.member_name || 'N/A'} (CV${rec.member_th || '?'})</h4>
                            <span>Ataque Nº ${rec.attack_number || '?'}</span>
                        </div>
                        <div class="advisor-target-info">
                            <p>Alvo Recomendado</p>
                            <span>#${rec.recommended_target_pos || '?'} (CV${rec.recommended_target_th || '?'})</span>
                        </div>
                        <div class="advisor-justification">
                            <p><strong>IA:</strong> ${rec.justification || '-'}</p>
                        </div>
                        ${alternativesHtml}
                        <div class="advisor-confidence">
                            <span>Confiança</span> 
                            <div class="confidence-bar-container"><div class="confidence-bar ${confidenceColor}" style="width: ${confidencePercent}%;"></div></div>
                            <span>${confidencePercent}%</span>
                        </div>
                    </div>`;
            }).join('') : '<p class="message-box">Nenhuma recomendação específica gerada.</p>'; 
            contentHtml += '</div>';
            setHtml(warAdvisorContentEl, contentHtml);

            const timerEl = warAdvisorContentEl.querySelector('#advisorPhaseTimer');
            const timerTextEl = warAdvisorContentEl.querySelector('#advisorPhaseTimerText');
            if (planData.phase_2_start_time_iso && timerEl && timerTextEl) {
                const phase2StartTime = new Date(planData.phase_2_start_time_iso);
                timerEl.style.display = 'block';
                const updateTimer = () => { 
                    const now = new Date(); const diff = phase2StartTime - now;
                    if (diff <= 0) {
                        setText(timerTextEl, 'Fase 2 Iniciada! Foco em limpeza.');
                        if(phaseTimerInterval) clearInterval(phaseTimerInterval); phaseTimerInterval = null;
                        return;
                    }
                    const hours = Math.floor(diff / 36e5); const minutes = Math.floor((diff % 36e5) / 6e4); const seconds = Math.floor((diff % 6e4) / 1000);
                    setText(timerTextEl, `${hours}h ${minutes}m ${seconds}s`);
                };
                updateTimer(); 
                phaseTimerInterval = setInterval(updateTimer, 1000); 
            } else if (timerEl) {
                timerEl.style.display = 'none';
            }
        };
        setupAdvisorUI(data);
    }

    function populateMissedAttacksHistory(data) {
        if(attacksRemainingTitleEl?.querySelector('span')) setText(attacksRemainingTitleEl.querySelector('span'), data?.clan_name || 'Clã');

        if (!data || data.error || !data.wars_with_missed_attacks?.length) {
            setHtml(missedAttacksContainerEl, ''); 
            if (noMissedAttacksMessageEl) {
                noMissedAttacksMessageEl.style.display = 'block';
                setText(noMissedAttacksMessageEl, data?.error || "Nenhuma pendência de ataque encontrada.");
            }
            return;
        }

        if (noMissedAttacksMessageEl) noMissedAttacksMessageEl.style.display = 'none';

        setHtml(missedAttacksContainerEl, data.wars_with_missed_attacks.map(war => `
            <div class="war-group">
                <h3 class="war-group-header">Guerra vs <strong>${war.opponent_name || '?'}</strong> (${war.end_date || '?'}) ${war.is_latest ? '<span class="latest-war-badge">💥 Última Guerra</span>' : ''}</h3>
                <div class="player-card-grid">
                    ${war.missed_attacks_members?.map(member => `
                        <div class="missed-attack-card ${member.attacks_left >= 2 ? 'severity-high' : 'severity-medium'}">
                            <div class="player-info">
                                <h4>${member.name || '?'} <span>(CV${member.town_hall || '?'})</span></h4>
                                <div class="player-tag-container">
                                    <span class="player-tag">${member.tag || '#?'}</span>
                                    <button class="copy-tag-btn" data-tag="${member.tag || '#?'}">Copiar</button>
                                </div>
                            </div>
                            <div class="attacks-info">
                                <span class="attacks-count">${member.attacks_left || '?'}</span>
                                <span class="attacks-label">Ataque${(member.attacks_left || 0) > 1 ? 's' : ''} Pendente${(member.attacks_left || 0) > 1 ? 's' : ''}</span>
                            </div>
                        </div>`).join('') || '<p>Nenhum membro com ataques pendentes nesta guerra.</p>'}
                </div>
            </div>`).join(''));

        document.querySelectorAll('.copy-tag-btn').forEach(button => {
            button.addEventListener('click', () => copyTagToClipboard(button));
        });
    }

    function copyTagToClipboard(button) {
        const tag = button.dataset.tag;
        const textArea = document.createElement("textarea");
        textArea.value = tag;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            const successful = document.execCommand('copy');
            if(successful){
                button.textContent = 'Copiado!'; button.disabled = true;
                setTimeout(() => { button.textContent = 'Copiar'; button.disabled = false; }, 2000);
            } else { throw new Error('execCommand failed'); }
        } catch (err) {
            console.error('Falha ao copiar tag:', err); button.textContent = 'Erro';
            setTimeout(() => { button.textContent = 'Copiar'; }, 2000);
        }
        document.body.removeChild(textArea);
    }

    function updateCwlHeaderUI(data) {
        if (!cwlActiveInfoEl) return;
        
        let mainStatusText = "";
        let statusColor = "var(--color-warning)";
        
        if (data.current_day >= 8) {
            mainStatusText = "🏁 Liga Finalizada";
            statusColor = "var(--color-text-secondary)";
        } else if (data.current_day >= 1) {
            let isPrep = false;
            if (data.state === 'preparation' || data.war_state === 'preparation') {
                isPrep = true;
            }
            if (data.rounds && Array.isArray(data.rounds) && data.rounds.length >= data.current_day) {
                if (data.rounds[data.current_day - 1] === 'preparation') isPrep = true;
            }
            
            if (isPrep) {
                mainStatusText = `⏳ Preparação (Dia ${data.current_day})`;
            } else {
                mainStatusText = `⚔️ Em Guerra (Dia ${data.current_day})`;
                statusColor = "var(--color-success)";
            }
        } else {
            mainStatusText = "🔍 Buscando Oponentes..."; 
            statusColor = "var(--color-info)";
        }

        let seasonStr = data.season || '-';
        let groupStateStr = data.state === 'preparation' ? 'Formando Grupo' : (data.state === 'inWar' ? 'Em Andamento' : (data.state || '-'));

        let clansHtml = '';
        if (data.clans && Array.isArray(data.clans) && data.clans.length > 0) {
            clansHtml = '<div style="display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-top: 15px;">';
            data.clans.forEach(c => {
                clansHtml += `<div style="background: rgba(0,0,0,0.3); padding: 8px 15px; border-radius: 20px; display:flex; align-items:center; font-size: 0.95em; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 4px 6px rgba(0,0,0,0.2);"><img src="${c.badge_url || DEFAULT_BADGE_URL}" style="width: 24px; height: 24px; margin-right: 10px;"> <span style="font-weight: bold; letter-spacing: 0.5px;">${c.name}</span></div>`;
            });
            clansHtml += '</div>';
        } else {
            clansHtml = "<p style='color:var(--color-warning); margin-top:10px; font-style: italic;'>⚠️ Dados do grupo ausentes no cache antigo. Clique em 'Recalcular Rotação Inteligente' para forçar a atualização.</p>";
        }

        let roundsText = '';
        if (data.rounds && Array.isArray(data.rounds) && data.rounds.length > 0) {
            roundsText = '<div style="display: flex; justify-content: center; gap: 10px; margin-top: 15px; flex-wrap: wrap;">';
            data.rounds.forEach((r, i) => {
                 let icon = r === 'warEnded' ? '✅' : (r === 'inWar' ? '⚔️' : '⏳');
                 let color = r === 'warEnded' ? 'var(--color-success)' : (r === 'inWar' ? 'var(--color-accent)' : 'var(--color-text-secondary)');
                 let bgColor = r === 'warEnded' ? 'rgba(46, 204, 113, 0.1)' : (r === 'inWar' ? 'rgba(231, 76, 60, 0.1)' : 'rgba(255, 255, 255, 0.05)');
                 roundsText += `<div style="background: ${bgColor}; padding: 10px 15px; border-radius: 10px; border-bottom: 3px solid ${color}; font-weight: bold; font-size: 0.9em; text-align: center; min-width: 60px;">Dia ${i+1}<br><span style="font-size: 1.4em; display:block; margin-top: 8px;">${icon}</span></div>`;
            });
            roundsText += '</div>';
        } else {
            roundsText = "<p style='color:var(--color-warning); margin-top:10px; font-style: italic;'>⚠️ Cronograma ausente no cache antigo. Clique em 'Recalcular Rotação Inteligente'.</p>";
        }

        const aestheticHeaderHtml = `
            <div class="status-badge" style="font-size: 1.3em; background-color: ${statusColor}1A; color: ${statusColor}; border: 1px solid ${statusColor}; margin-bottom: 25px; padding: 15px 20px; border-radius: 12px; text-align: center; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">
                ${mainStatusText}
            </div>
            
            <div class="stats-grid" style="margin-bottom: 25px;">
                <div class="stat-card" style="padding: 20px; text-align: center; background: linear-gradient(145deg, rgba(255,255,255,0.05) 0%, rgba(0,0,0,0.2) 100%);">
                    <h4 style="color: var(--color-text-secondary); font-size: 0.85em; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 10px;">Temporada</h4>
                    <div class="stat-value" style="font-size: 1.5em; color: var(--color-text-main); font-weight: bold;">${seasonStr}</div>
                </div>
                <div class="stat-card" style="padding: 20px; text-align: center; background: linear-gradient(145deg, rgba(255,255,255,0.05) 0%, rgba(0,0,0,0.2) 100%);">
                    <h4 style="color: var(--color-text-secondary); font-size: 0.85em; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 10px;">Estado do Grupo</h4>
                    <div class="stat-value" style="font-size: 1.5em; color: var(--color-text-main); font-weight: bold;">${groupStateStr}</div>
                </div>
            </div>

            <div class="cwl-overview-card" style="margin-bottom: 25px; text-align: center; padding: 25px; border: 1px solid rgba(255,255,255,0.05); border-radius: 15px; background-color: rgba(0,0,0,0.15);">
                <h3 style="margin-bottom: 5px; font-size: 1.2em; color: var(--color-text-main); text-transform: uppercase; letter-spacing: 1px;">🛡️ Clãs no Grupo</h3>
                ${clansHtml}
            </div>

            <div class="cwl-overview-card" style="margin-bottom: 40px; text-align: center; padding: 25px; border-radius: 15px; background: rgba(0,0,0,0.2);">
                <h3 style="margin-bottom: 5px; font-size: 1.2em; color: var(--color-text-main); text-transform: uppercase; letter-spacing: 1px;">📅 Cronograma Oficial</h3>
                ${roundsText}
            </div>
        `;

        setHtml(cwlActiveInfoEl, aestheticHeaderHtml);
    }

    function populateCwlOverview(planData) {
        if (!cwlOverviewContainerEl) return;

        const score = (planData && Array.isArray(planData.participation_score)) ? planData.participation_score : [];
        
        let placarHtml = '<h4>📊 Placar de Participação (Estimado)</h4>'; 
        placarHtml += '<div class="cwl-overview-list-bench">'; 
        
        if (score.length > 0) {
             score.sort((a, b) => (b.days_played || 0) - (a.days_played || 0));
             placarHtml += score.map(p => {
                 const name = p.name || (p.player && p.player.name) || 'Membro Oculto';
                 const th = p.town_hall || (p.player && p.player.town_hall) || '?';
                 const icon = p.status === 'priority' ? '⭐' : (p.status === 'unavailable' ? '🛑' : '');
                 return `<p>${icon} ${name} (CV${th}): <strong>${p.days_played || 0} / 7 dias</strong></p>`;
             }).join('');
        } else {
            placarHtml += '<p>Nenhum dado de participação gerado.</p>';
        }
        placarHtml += '</div>';

        setHtml(cwlOverviewContainerEl, `<div class="cwl-overview-card" style="grid-column: 1 / -1;">${placarHtml}</div>`);
        cwlOverviewContainerEl.style.gridTemplateColumns = '1fr';
    }

    function populateCwlSchedule(planData) {
        if (!cwlPlanDaysTabsEl || !cwlPlanContentEl) return;

        const schedule = (planData && Array.isArray(planData.schedule)) ? planData.schedule : [];
        const currentDay = planData.current_day || 1;

        if (schedule.length === 0) {
             setHtml(cwlPlanDaysTabsEl, '');
             setHtml(cwlPlanContentEl, '<p class="message-box">Não foi possível montar a escalação.</p>');
             return;
        }

        let dayToRender = activeCwlTabDay ? parseInt(activeCwlTabDay) : currentDay;
        if (!schedule.find(d => d.day === dayToRender)) {
            dayToRender = currentDay;
        }

        const tabsHtml = schedule.map(dayPlan => {
            const day = dayPlan.day || 1;
            const isActive = day === dayToRender;
            return `<button class="cwl-plan-day-tab ${isActive ? 'active' : ''}" data-day="${day}">Dia ${day}</button>`;
        }).join('');
        setHtml(cwlPlanDaysTabsEl, tabsHtml);

        const renderDayPlan = (day) => {
            const dayData = schedule.find(d => d.day == day);
            if (!dayData) {
                setHtml(cwlPlanContentEl, `<p class="message-box">Plano para o dia ${day} não encontrado.</p>`);
                return;
            }

            let planHtml = ``;

            if (dayData.opponent_analysis) {
                const opp = dayData.opponent_analysis;
                let tColor = opp.threat_level.includes("Extremo") ? "#e74c3c" : (opp.threat_level.includes("Baixa") ? "#2ecc71" : "#f1c40f");
                planHtml += `
                <div style="background: rgba(0,0,0,0.3); border-left: 4px solid ${tColor}; padding: 15px; margin-bottom: 20px; border-radius: 4px;">
                    <h4 style="margin: 0 0 5px 0; color: ${tColor};">Análise ML: vs ${opp.clan_name}</h4>
                    <p style="margin: 0; font-size: 0.9em;">Classificação: <strong>${opp.threat_level}</strong> | Tática IA: ${dayData.strategy_used}</p>
                </div>`;
            }

            planHtml += `<h4>Alterações XAI na Equipe</h4>`;
            planHtml += (dayData.substitutions && dayData.substitutions.length > 0)
                ? dayData.substitutions.map(sub => {
                    const outName = sub.out?.name || (sub.out?.player && sub.out.player.name) || '?';
                    const outTh = sub.out?.town_hall || (sub.out?.player && sub.out.player.town_hall) || '?';
                    const inName = sub.in?.name || (sub.in?.player && sub.in.player.name) || '?';
                    const inTh = sub.in?.town_hall || (sub.in?.player && sub.in.player.town_hall) || '?';
                    return `
                    <div class="xai-sub">
                        <p style="color: #e74c3c; margin-bottom:2px;">⬇️ <strong>Sai:</strong> ${outName} (CV${outTh}) - <em>${sub.out_reason || 'Rotação'}</em></p>
                        <p style="color: #2ecc71; margin-bottom:5px;">⬆️ <strong>Entra:</strong> ${inName} (CV${inTh})</p>
                        <div class="xai-badge">IA: ${sub.reason || 'Escalado pela matriz.'}</div>
                    </div>`;
                }).join('')
                : `<p>${day == 1 ? 'Escalação inicial baseada nos melhores CVs e Titulares Fixos.' : 'A IA sugere manter a escalação do dia anterior.'}</p>`;

            const roster = dayData.active_roster || [];
            planHtml += `<h4 style="margin-top:20px;">⚔️ Escalação Ativa Sugerida (Dia ${day}) - ${roster.length}v${roster.length}</h4><div class="roster-grid">`;
            
            const sortedRoster = [...roster].sort((a, b) => {
                const thA = a.town_hall || (a.player && a.player.town_hall) || 0;
                const thB = b.town_hall || (b.player && b.player.town_hall) || 0;
                return thB - thA;
            });

            planHtml += sortedRoster.length > 0
                ? sortedRoster.map((p, i) => {
                    const name = p.name || (p.player && p.player.name) || '?';
                    const th = p.town_hall || (p.player && p.player.town_hall) || '?';
                    const icon = p.status === 'priority' ? '⭐' : (p.status === 'unavailable' ? '🛑' : '');
                    return `
                    <div class="roster-player" ${p.status === 'priority' ? 'style="border-left: 3px solid var(--color-accent);"' : ''}>
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span>${i + 1}. ${icon} ${name} (CV${th})</span>
                            <span style="color:var(--color-text-secondary); font-size:0.8em;">${p.days_played || 0}d</span>
                        </div>
                        ${p.xai_justification ? `<div style="font-size: 0.7em; color: #a0aec0; margin-top: 5px; font-family: monospace;">> ${p.xai_justification}</div>` : ''}
                    </div>`;
                }).join('')
                : '<p>Nenhum jogador na escalação.</p>';
            planHtml += `</div>`; 
            
            const activeBench = dayData.active_bench || [];
            const backupBench = dayData.backup_bench || [];

            planHtml += `<h4 style="margin-top: 20px;"><span class="ai-indicator"></span>Banco de Reservas (Dia ${day})</h4>`;
            planHtml += '<div class="cwl-overview-card" style="background-color: rgba(0,0,0,0.1);">'; 
            planHtml += '<div class="cwl-overview-list-bench">'; 

            if (activeBench.length > 0) {
                planHtml += '<h5>Ativos (Próximos a entrar):</h5>';
                planHtml += activeBench
                    .sort((a, b) => (a.days_played || 0) - (b.days_played || 0)) 
                    .map((p, i) => {
                        const name = p.name || (p.player && p.player.name) || '?';
                        const th = p.town_hall || (p.player && p.player.town_hall) || '?';
                        return `<p>${i+1}. ${name} (CV${th}) - ${p.days_played || 0}d</p>`;
                    })
                    .join('');
            }
            if (backupBench.length > 0) {
                planHtml += '<h5 style="margin-top: 10px;">Backups (Emergência):</h5>';
                planHtml += backupBench
                    .sort((a, b) => (a.days_played || 0) - (b.days_played || 0)) 
                    .map((p, i) => {
                        const name = p.name || (p.player && p.player.name) || '?';
                        const th = p.town_hall || (p.player && p.player.town_hall) || '?';
                        return `<p>${i+1}. ${name} (CV${th}) - ${p.days_played || 0}d</p>`;
                    })
                    .join('');
            }
            if (activeBench.length === 0 && backupBench.length === 0) {
                 planHtml += '<p>Nenhum jogador no banco para este dia.</p>';
            }
            planHtml += '</div></div>';
            
            setHtml(cwlPlanContentEl, planHtml);
        };

        renderDayPlan(dayToRender);

        cwlPlanDaysTabsEl.querySelectorAll('.cwl-plan-day-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                cwlPlanDaysTabsEl.querySelector('.cwl-plan-day-tab.active')?.classList.remove('active');
                tab.classList.add('active');
                activeCwlTabDay = tab.dataset.day; 
                renderDayPlan(tab.dataset.day);
            });
        });
    }

    async function loadCwlPlan() {
        if (isFetchingCwlPlan) return;
        isFetchingCwlPlan = true;
        
        if(cwlOverviewContainerEl) setHtml(cwlOverviewContainerEl, `<div class="loading-spinner" style="margin: 20px auto;"></div><p style="text-align:center; grid-column: 1/-1;">A IA está calculando a rotação ideal...</p>`);
        if(cwlPlanDaysTabsEl) setHtml(cwlPlanDaysTabsEl, '');
        if(cwlPlanContentEl) setHtml(cwlPlanContentEl, '');
        
        try {
            const planData = await fetchData('cwl/generate_plan', { method: 'POST' });
            if (planData && !planData.error) {
                cwlPlanCached = planData;
                updateCwlHeaderUI(planData);
                populateCwlOverview(planData);
                populateCwlSchedule(planData);
            } else {
                if(cwlOverviewContainerEl) {
                     setHtml(cwlOverviewContainerEl, `<div class="error-text" style="grid-column: 1/-1;">Erro ao gerar rotação: ${planData?.error || 'Não há membros suficientes marcados como Ativos.'}</div>`);
                     cwlOverviewContainerEl.style.gridTemplateColumns = '1fr';
                }
            }
        } catch (e) {
            console.error("Erro no JS ao gerar plano:", e);
            if(cwlOverviewContainerEl) setHtml(cwlOverviewContainerEl, `<div class="error-text" style="grid-column: 1/-1;">Falha interna na Rotação. Tente novamente mais tarde.</div>`);
        } finally {
            isFetchingCwlPlan = false;
        }
    }

    async function populateCwlData(data) {
        if (!cwlPlannerSectionEl) return;
        cwlPlannerSectionEl.style.display = 'block';

        if (!data || data.error || data.status === "NotInCwl" || data.state === "not_in_season") {
            if (noCwlMessageEl) {
                noCwlMessageEl.style.display = 'block';
                setText(noCwlMessageEl, data?.error || data?.message || "O clã não está em CWL no momento.");
            }
            if (cwlActiveInfoEl) cwlActiveInfoEl.style.display = 'none';
            if (cwlPlanResultEl) cwlPlanResultEl.style.display = 'none'; 
            
            const oldStatus = document.getElementById('cwlStatusText');
            if (oldStatus) oldStatus.style.display = 'none'; 
            return;
        }

        const oldStatus = document.getElementById('cwlStatusText');
        if (oldStatus) oldStatus.style.display = 'none'; 
        
        if (noCwlMessageEl) noCwlMessageEl.style.display = 'none';
        if (cwlActiveInfoEl) cwlActiveInfoEl.style.display = 'block'; 
        if (cwlPlanResultEl) cwlPlanResultEl.style.display = 'block'; 

        updateCwlHeaderUI(data);

        if (data.warning) {
            setHtml(cwlPlanWarningEl, `<strong>Aviso da IA:</strong> ${data.warning}`);
            cwlPlanWarningEl.style.display = 'block';
        } else if (cwlPlanWarningEl) {
            cwlPlanWarningEl.style.display = 'none';
        }

        if (userIsAdmin) {
            if (!document.getElementById('recalc-cwl-btn')) {
                 const btnHtml = `<button id="recalc-cwl-btn" class="control-btn" style="margin-bottom: 20px; width: 100%; background-color: var(--color-accent); font-weight: bold; border-radius: 10px; padding: 12px; font-size: 1.1em; transition: all 0.3s ease;">🧠 Recalcular Rotação Inteligente</button>`;
                 if(cwlPlanResultEl) cwlPlanResultEl.insertAdjacentHTML('beforebegin', btnHtml);
                 
                 document.getElementById('recalc-cwl-btn')?.addEventListener('click', async () => {
                     cwlPlanCached = null;
                     if(cwlOverviewContainerEl) setHtml(cwlOverviewContainerEl, `<div class="loading-spinner" style="margin: 20px auto;"></div><p style="text-align:center; grid-column: 1/-1;">Recalculando e atualizando a base de dados...</p>`);
                     if(cwlPlanDaysTabsEl) setHtml(cwlPlanDaysTabsEl, '');
                     if(cwlPlanContentEl) setHtml(cwlPlanContentEl, '');

                     const planData = await fetchData('cwl/generate_plan', { 
                         method: 'POST', 
                         headers: {'Content-Type': 'application/json'}, 
                         body: JSON.stringify({force: true}) 
                     });
                     
                     if (planData && !planData.error) {
                         updateCwlHeaderUI(planData); 
                         populateCwlOverview(planData); 
                         populateCwlSchedule(planData);
                     } else {
                         if(cwlOverviewContainerEl) setHtml(cwlOverviewContainerEl, `<div class="error-text" style="grid-column: 1/-1;">Erro ao recalcular: ${planData?.error || 'Tente novamente.'}</div>`);
                     }
                 });
            }
        } else {
            const btn = document.getElementById('recalc-cwl-btn');
            if (btn) btn.remove();
        }

        populateCwlOverview(data);
        populateCwlSchedule(data);
    }

    function populateWarLog(data) {
        setText(warLogLimitEl, data?.log?.length || '0');

        if (!data || data.error || !data.log?.length) {
            if(noWarLogMessageEl) { noWarLogMessageEl.style.display = 'block'; setText(noWarLogMessageEl, data?.error || "Log de guerra indisponível."); }
            setHtml(warLogTableBodyEl, `<tr><td colspan="6">${data?.error || "Nenhum registo encontrado."}</td></tr>`);
            return;
        }

        if(noWarLogMessageEl) noWarLogMessageEl.style.display = 'none';
        
        setHtml(warLogTableBodyEl, data.log.map(e => {
            const warId = e.war_id || e.id || e._id || '';
            return `
            <tr class="historic-war-row" data-war-id="${warId}">
                <td>${e.end_time_formatted || '?'}</td>
                <td><img src="${e.opponent_badge_url || DEFAULT_BADGE_URL}" alt="Emblema" class="log-opponent-badge">${e.opponent_name || 'N/A'}</td>
                <td>${e.clan_stars ?? '?'}⭐ vs ${e.opponent_stars ?? '?'}⭐</td>
                <td class="war-result-${e.result?.toLowerCase() || 'unknown'}">${e.result || '?'}</td>
                <td>${e.team_size || '?'}</td>
                <td>${e.is_cwl ? "CWL" : "Normal"}</td>
            </tr>`;
        }).join(''));
    }

    function populateCapitalData(data) {
        if (!capitalContentEl) return;

        if (!data || data.error || !data.raid) {
            if (noCapitalMessageEl) {
                noCapitalMessageEl.style.display = 'block';
                setText(noCapitalMessageEl, data?.error || "Dados da Capital indisponíveis.");
            }
            capitalContentEl.style.display = 'none';
            return;
        }

        if (noCapitalMessageEl) noCapitalMessageEl.style.display = 'none';
        capitalContentEl.style.display = 'block';

        const raid = data.raid;
        const members = data.members || [];

        const statusPt = raid.state === "ongoing" ? "Em Andamento" : "Finalizada";
        setText(capStatusEl, statusPt);
        if(capStatusEl) capStatusEl.className = `status-badge ${raid.state === "ongoing" ? 'status-warning' : 'status-success'}`;
        
        setText(capTotalLootEl, '🪙 ' + (raid.total_loot?.toLocaleString() || '0'));
        setText(capTotalAttacksEl, raid.total_attacks || '0');
        setText(capDestroyedEl, raid.destroyed_districts || '0');

        const topAttackers = members.slice(0, 5);
        const zeroAttacks = members.filter(m => m.attacks === 0);
        const incompleteAttacks = members.filter(m => m.attacks > 0 && m.attacks < m.limit);

        if (capTopAttackersListEl) {
            const medals = ['🥇', '🥈', '🥉', '🏅', '🏅'];
            setHtml(capTopAttackersListEl, topAttackers.length > 0 && topAttackers[0].attacks > 0 ? topAttackers.map((m, i) => `
                <div class="podium-item ${i===0?'gold':i===1?'silver':i===2?'bronze':''}">
                    <span class="podium-rank">${medals[i] || `${i+1}.`}</span>
                    <div class="podium-details">
                        <div class="member-name">${m.name}</div>
                        <div class="donation-count"><strong>🪙 ${m.looted.toLocaleString()}</strong> ouro (Ataques: ${m.attacks}/${m.limit})</div>
                    </div>
                </div>
            `).join('') : '<p>Nenhum ataque registrado ainda.</p>');
        }

        if (capZeroAttacksListEl) {
            setHtml(capZeroAttacksListEl, zeroAttacks.length > 0 ? zeroAttacks.map(m => `
                <p>🔴 <strong>${m.name}</strong></p>
            `).join('') : '<p style="color: var(--color-success); font-weight: bold;">Incrível! Todos do clã atacaram.</p>');
        }

        if (capIncompleteAttacksListEl) {
            setHtml(capIncompleteAttacksListEl, incompleteAttacks.length > 0 ? incompleteAttacks.map(m => `
                <p>🟡 <strong>${m.name}</strong>: Fez ${m.attacks} de ${m.limit}</p>
            `).join('') : '<p>Nenhum ataque incompleto.</p>');
        }
    }

    // === FUNÇÃO CLAN GAMES COM EFEITO DE BLUR E CADEADO ===
    function populateClanGamesData(data) {
        if (!cgContentEl) return;

        if (!data || data.error || !data.active) {
            if (noClanGamesMessageEl) noClanGamesMessageEl.style.display = 'flex'; 
            if (cgContentEl) {
                cgContentEl.classList.add('cg-blurred-state'); 
            }
            
            setText(cgTotalPointsEl, '0');
            cgProgressBarEl.style.width = '0%';
            setText(cgProgressTextEl, 'Aguardando Caravana...');
            if (cgTopPlayersListEl) setHtml(cgTopPlayersListEl, '<p style="padding: 15px; color: var(--color-text-secondary);">Radar desligado.</p>');
            if (cgZeroPlayersListEl) setHtml(cgZeroPlayersListEl, '<p style="padding: 15px; color: var(--color-text-secondary);">Radar desligado.</p>');
            return;
        }

        if (noClanGamesMessageEl) noClanGamesMessageEl.style.display = 'none';
        if (cgContentEl) {
            cgContentEl.classList.remove('cg-blurred-state');
        }

        const totalPoints = data.total_points || 0;
        const maxClanPoints = data.max_clan_points || 50000;
        const maxPlayerPoints = data.max_player_points || 4000;
        const members = data.members || [];

        setText(cgTotalPointsEl, totalPoints.toLocaleString());
        setText(cgMaxPointsEl, maxClanPoints.toLocaleString());

        let progress = totalPoints / maxClanPoints;
        if (progress > 1) progress = 1;
        
        cgProgressBarEl.style.width = `${(progress * 100).toFixed(1)}%`;
        setText(cgProgressTextEl, `${(progress * 100).toFixed(1)}% Concluído`);

        const topPlayers = members.filter(m => m.score > 0);
        const zeroPlayers = members.filter(m => m.score === 0);

        if (cgTopPlayersListEl) {
            setHtml(cgTopPlayersListEl, topPlayers.length > 0 ? topPlayers.map((m, i) => `
                <div class="cg-player-item">
                    <div class="cg-player-info">
                        <span>${i+1}.</span> <strong>${m.name}</strong> <span style="font-size: 0.8em; color: var(--color-text-secondary);">(${m.role})</span>
                    </div>
                    <div class="cg-player-score ${m.score >= maxPlayerPoints ? 'max-score' : ''}">
                        ${m.score.toLocaleString()} ${m.score >= maxPlayerPoints ? '🔥' : ''}
                    </div>
                </div>
            `).join('') : '<p style="padding: 15px;">Ninguém pontuou ainda.</p>');
        }

        if (cgZeroPlayersListEl) {
            setHtml(cgZeroPlayersListEl, zeroPlayers.length > 0 ? zeroPlayers.map(m => `
                <div class="cg-player-item">
                    <div class="cg-player-info"><strong>${m.name}</strong></div>
                    <div class="cg-player-score text-danger">0</div>
                </div>
            `).join('') : '<p class="text-success" style="padding: 15px; font-weight:bold;">Todos pontuaram! 🎉</p>');
        }
    }


    async function savePlayerNote(playerTag, text, priority) {
        try {
            await fetchData(`notes/${encodeURIComponent(playerTag)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, priority })
            });
        } catch (e) {
            console.error("Erro ao salvar nota:", e);
        }
    }

    function populateMembersList(data) {
        setText(membersClanNameEl, data?.clan_name);

        if (!data || data.error || !data.members) {
            setHtml(membersGridEl, `<p class="message-box">${data?.error || "Não foi possível carregar os membros."}</p>`);
            return;
        }

        setHtml(membersGridEl, data.members.map(m => {
            const watchlistClass = m.isOnWatchlist ? 'on-watchlist' : '';
            const watchlistIconHtml = m.isOnWatchlist ? '<span class="watchlist-icon">⚠️</span>' : '';
            const watchlistTooltipHtml = m.isOnWatchlist
                ? `<span class="watchlist-tooltip">
                    <strong>Em Observação!</strong><br>
                    Motivo: ${m.watchlistReason || 'Não especificado'}<br>
                    ${m.watchlistDetails ? `Detalhes: ${m.watchlistDetails}` : ''}
                </span>`
                : '';
            const noteText = m.note || 'Clique para editar...';
            const notePriority = m.note_priority || 'none';

            let lastWarDateFormatted = 'N/A';
            if (m.last_war_date) {
                try {
                    const date = new Date(m.last_war_date);
                    lastWarDateFormatted = date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
                } catch (e) {
                    console.warn(`Data inválida de última guerra para ${m.name}: ${m.last_war_date}`);
                    lastWarDateFormatted = 'Inválida';
                }
            }
            const lastWarHtml = `<span title="Esta é a data da última guerra conhecida">⚔️ ${lastWarDateFormatted}</span>`;

            const isPriority = m.cwl_status === 'priority';
            const priorityClass = isPriority ? 'vip-golden-card' : '';
            const vipRibbonHtml = isPriority ? `<div class="vip-ribbon">⭐ TITULAR</div>` : '';

            return `
            <div class="member-card ${watchlistClass} ${priorityClass}" data-th="${m.town_hall || '?'}" data-name="${(m.name || '').toLowerCase()}">
                ${vipRibbonHtml}
                <div class="member-card-header" data-player-tag="${m.tag || ''}">
                    <img src="/static/images/townhall${m.town_hall || 1}.png" alt="CV${m.town_hall || '?'}" class="member-th-icon" onerror="this.onerror=null; this.src=DEFAULT_BADGE_URL; this.style.height='40px';">
                    <div class="member-info">
                        <h4>${m.name || 'N/A'} ${watchlistIconHtml}</h4>
                        <p>${m.role || 'Membro'} • 🏆 ${m.trophies || 0}</p>
                    </div>
                    ${watchlistTooltipHtml}
                </div>
                <div class="member-card-stats">
                    <span>🎁 Doadas: ${m.donations || 0}</span>
                    <span>📥 Recebidas: ${m.received || 0}</span>
                    ${lastWarHtml} </div>
                <div class="member-card-note">
                    <div class="note-container note-priority-${notePriority}">
                        <span class="note-text">${noteText}</span>
                        <input type="text" class="note-input" value="${m.note || ''}" style="display: none;">
                        <div class="priority-selector">
                            ${['green', 'yellow', 'red', 'none'].map(prio => `
                                <button class="priority-btn priority-${prio} ${prio === notePriority ? 'active' : ''}" data-priority="${prio}">
                                    ${prio === 'green' ? '✓' : prio === 'yellow' ? '!' : prio === 'red' ? '✗' : '×'}
                                </button>
                            `).join('')}
                        </div>
                    </div>
                </div>
                <div class="member-cwl-status" data-player-tag="${m.tag || ''}">
                    <label>CWL:</label>
                    <div class="cwl-status-selector">
                        <button class="cwl-status-btn ${m.cwl_status === 'priority' ? 'active' : ''}" data-status="priority" title="Titular Absoluto (IA fura-fila)">⭐ Fixo</button>
                        <button class="cwl-status-btn ${m.cwl_status === 'active' ? 'active' : ''}" data-status="active">Ativo</button>
                        <button class="cwl-status-btn ${m.cwl_status === 'backup' ? 'active' : ''}" data-status="backup">Reserva</button>
                    </div>
                </div>
            </div>`;
        }).join(''));

        attachMemberEventListeners();
        applyMemberFilters(); 
    }

    function applyMemberFilters() {
        const nameFilter = filterNameInput?.value?.toLowerCase() || '';
        const thFilter = filterTHInput?.value || '';
        document.querySelectorAll('.member-card').forEach(card => {
            const name = card.dataset.name || '';
            const th = card.dataset.th || '';
            const nameMatch = name.includes(nameFilter);
            const thMatch = !thFilter || th === thFilter;
            card.style.display = (nameMatch && thMatch) ? 'flex' : 'none';
        });
    }

    filterNameInput?.addEventListener('input', applyMemberFilters); 
    filterTHInput?.addEventListener('input', applyMemberFilters);

    function attachMemberEventListeners() {
        if (!userIsAdmin) {
            return;
        }

        membersGridEl?.querySelectorAll('.member-card-header').forEach(header => {
            header.replaceWith(header.cloneNode(true)); 
        });
        membersGridEl?.querySelectorAll('.note-text').forEach(span => {
            span.replaceWith(span.cloneNode(true));
        });
        membersGridEl?.querySelectorAll('.note-input').forEach(input => {
            input.replaceWith(input.cloneNode(true));
        });
        membersGridEl?.querySelectorAll('.priority-btn').forEach(btn => {
            btn.replaceWith(btn.cloneNode(true));
        });
        membersGridEl?.querySelectorAll('.cwl-status-btn').forEach(btn => {
            btn.replaceWith(btn.cloneNode(true));
        });

        membersGridEl?.querySelectorAll('.member-card-header').forEach(header => {
            header.addEventListener('click', () => openMemberProfileModal(header.dataset.playerTag));
        });
        membersGridEl?.querySelectorAll('.note-text').forEach(span => {
            span.addEventListener('click', () => {
                const input = span.nextElementSibling;
                if (input && input.classList.contains('note-input')) { 
                    span.style.display = 'none'; input.style.display = 'inline-block'; input.focus();
                }
            });
        });
        membersGridEl?.querySelectorAll('.note-input').forEach(input => {
            const saveChanges = () => {
                const container = input.closest('.note-container');
                const span = container?.querySelector('.note-text');
                const memberCard = input.closest('.member-card');
                const playerTag = memberCard?.querySelector('.member-card-header')?.dataset.playerTag;
                const activePriority = container?.querySelector('.priority-btn.active')?.dataset.priority || 'none';
                if (span) {
                    span.textContent = input.value || 'Clique para editar...'; span.style.display = 'inline-block';
                }
                input.style.display = 'none';
                if(playerTag) savePlayerNote(playerTag, input.value, activePriority);
            };
            input.addEventListener('blur', saveChanges);
            input.addEventListener('keypress', e => { if (e.key === 'Enter') input.blur(); });
        });
        membersGridEl?.querySelectorAll('.priority-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const container = btn.closest('.note-container');
                const memberCard = btn.closest('.member-card');
                const playerTag = memberCard?.querySelector('.member-card-header')?.dataset.playerTag;
                const text = container?.querySelector('.note-input')?.value || '';
                const newPriority = btn.dataset.priority;
                if(container) container.className = `note-container note-priority-${newPriority}`;
                container?.querySelectorAll('.priority-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                if(playerTag) savePlayerNote(playerTag, text, newPriority);
            });
        });
        membersGridEl?.querySelectorAll('.cwl-status-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                if (btn.classList.contains('active')) return;
                const selector = e.target.closest('.cwl-status-selector');
                const playerTag = e.target.closest('.member-cwl-status')?.dataset.playerTag;
                const newStatus = e.target.dataset.status;
                if (!playerTag || !newStatus) return;

                selector?.querySelector('.active')?.classList.remove('active'); 
                e.target.classList.add('active');
                const success = await setPlayerCwlStatus(playerTag, newStatus);
                if (!success) {
                    alert('Erro ao salvar status. Tente novamente.');
                    e.target.classList.remove('active');
                }
            });
        });
    }

    async function setPlayerCwlStatus(playerTag, status) {
        try {
            const response = await fetchData(`cwl/player_status/${encodeURIComponent(playerTag)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status })
            });
            return response && !response.error; 
        } catch (e) {
            console.error("Erro ao definir status CWL:", e);
            return false;
        }
    }

    async function openMemberProfileModal(playerTag) {
        if (!playerTag || !memberProfileModal || !memberProfileContent) return;
        
        setHtml(memberProfileContent, '<div class="loading-spinner" style="margin: 40px auto;"></div><p style="text-align:center;">A carregar registros do jogador...</p>');
        memberProfileModal.style.display = 'block';

        const membersData = await fetchData('members');
        let basicData = {};
        if (membersData && !membersData.error && membersData.members) {
            basicData = membersData.members.find(m => m.tag === playerTag) || {};
        }

        let detailedData = await fetchData(`player_profile/${encodeURIComponent(playerTag)}`);
        if (!detailedData || detailedData.error) {
             setHtml(memberProfileContent, `<p class="message-box">${detailedData?.error || 'Erro ao comunicar com a Supercell.'}</p>`);
             return;
        }

        const profileData = { ...basicData, ...detailedData };

        let lastWarDateFormatted = 'Sem Registro';
        if (profileData.last_war_date) {
            try {
                lastWarDateFormatted = new Date(profileData.last_war_date).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
            } catch (e) { lastWarDateFormatted = 'Inválida'; }
        }

        const heroImageMap = {
            'barbarian king': 'barbarian-king.png',
            'archer queen': 'archer-queen.png',
            'grand warden': 'grand-warden.png',
            'royal champion': 'royal-champion.png',
            'minion prince': 'minion-prince.png'
        };

        const heroesHtml = profileData.heroes?.length > 0 ? profileData.heroes.map(hero => {
            const imgName = heroImageMap[(hero.name || '').toLowerCase()] || 'default_hero.png';
            return `
                <div class="hero-item-new">
                    <img src="/static/images/heroes/${imgName}" alt="${hero.name}" onerror="this.src='/static/images/default_badge.png'">
                    <div class="hero-lvl-box">${hero.level} <span style="font-size:0.7em;color:var(--color-text-secondary);">/ ${hero.max_level}</span></div>
                </div>`;
        }).join('') : '<p class="message-box" style="width:100%;">Nenhum herói da vila principal encontrado.</p>';

        const cwlStatus = profileData.cwl_status || 'active';
        
        const cwlStatusHtml = userIsAdmin ? `
            <div class="member-cwl-status" data-player-tag="${profileData.tag || ''}" style="margin-bottom: 20px;">
                <label>Status na CWL:</label>
                <div class="cwl-status-selector">
                    <button class="cwl-status-btn ${cwlStatus === 'priority' ? 'active' : ''}" data-status="priority">⭐ Fixo</button>
                    <button class="cwl-status-btn ${cwlStatus === 'active' ? 'active' : ''}" data-status="active">Ativo</button>
                    <button class="cwl-status-btn ${cwlStatus === 'backup' ? 'active' : ''}" data-status="backup">Backup</button>
                </div>
            </div>` : `
            <div class="member-cwl-status" style="margin-bottom: 20px; justify-content: flex-start; gap: 15px;">
                <label>Status CWL:</label>
                <span style="color: ${cwlStatus === 'priority' ? 'var(--color-accent)' : (cwlStatus === 'active' ? 'var(--color-success)' : 'var(--color-warning)')}; font-weight:bold;">${cwlStatus === 'priority' ? '⭐ Titular Fixo' : (cwlStatus === 'active' ? 'Ativo' : 'Banco de Reservas')}</span>
            </div>`;

        const hitrate = profileData.hitrate || { total_wars: 0, attacks_made: 0, attacks_missed: 0, total_stars: 0, three_star_attacks: 0, avg_destruction: 0 };
        const totalPossiveis = hitrate.attacks_made + hitrate.attacks_missed;
        const txParticipacao = totalPossiveis > 0 ? Math.round((hitrate.attacks_made / totalPossiveis) * 100) : 0;
        const tx3Estrelas = hitrate.attacks_made > 0 ? Math.round((hitrate.three_star_attacks / hitrate.attacks_made) * 100) : 0;
        const mediaEstrelas = hitrate.attacks_made > 0 ? (hitrate.total_stars / hitrate.attacks_made).toFixed(1) : "0.0";

        let corParticipacao = 'text-danger';
        if (txParticipacao >= 90) corParticipacao = 'text-success';
        else if (txParticipacao >= 50) corParticipacao = 'text-warning';

        const battleCardHtml = `
            <div class="battle-card-container">
                <h3 class="profile-section-title" style="margin-bottom:10px; border:none; padding:0;">⚔️ Cartão de Batalha (Últimas ${hitrate.total_wars} Guerras)</h3>
                <div class="battle-card-stats">
                    <div class="bc-stat">
                        <span class="bc-label">Assiduidade</span>
                        <span class="bc-value ${corParticipacao}">${txParticipacao}%</span>
                        <span class="bc-sub">${hitrate.attacks_made} de ${totalPossiveis} atks</span>
                    </div>
                    <div class="bc-stat">
                        <span class="bc-label">Média de Estrelas</span>
                        <span class="bc-value text-gold">${mediaEstrelas} ⭐</span>
                        <span class="bc-sub">Destruição: ${hitrate.avg_destruction}%</span>
                    </div>
                    <div class="bc-stat">
                        <span class="bc-label">Taxa de Perfeitos</span>
                        <span class="bc-value text-info">${tx3Estrelas}%</span>
                        <span class="bc-sub">${hitrate.three_star_attacks} PTs</span>
                    </div>
                </div>
            </div>
        `;

        setHtml(memberProfileContent, `
            <div class="profile-header-new">
                <div class="profile-league-badge">
                    <img src="${profileData.league_icon || DEFAULT_BADGE_URL}" alt="${profileData.league || 'Liga'}" title="${profileData.league || 'Sem Liga'}">
                </div>
                <div class="profile-title-new">
                    <h2>${profileData.name || '?'} <img src="/static/images/townhall${profileData.town_hall || 1}.png" class="profile-th-icon" alt="CV" title="CV ${profileData.town_hall}" onerror="this.src=DEFAULT_BADGE_URL;"></h2>
                    <span class="profile-tag-new">${profileData.tag || '#?'}</span>
                    <span class="profile-role-new">${profileData.role || 'Membro'}</span>
                </div>
            </div>

            <div class="profile-stats-cards">
                <div class="p-card"><span class="p-icon">🏆</span><span class="p-val">${profileData.trophies || 0}</span><span class="p-label">Troféus</span></div>
                <div class="p-card"><span class="p-icon">🎁</span><span class="p-val">${profileData.donations || 0}</span><span class="p-label">Doadas</span></div>
                <div class="p-card"><span class="p-icon">📥</span><span class="p-val">${profileData.received || 0}</span><span class="p-label">Recebidas</span></div>
                <div class="p-card" title="Última guerra registrada no sistema">
                    <span class="p-icon">🛡️</span>
                    <span class="p-val" style="font-size:1em; margin-top:5px;">${lastWarDateFormatted}</span>
                    <span class="p-label">Últ. Guerra</span>
                </div>
            </div>
            
            ${cwlStatusHtml}
            ${battleCardHtml}

            <h3 class="profile-section-title">Progresso de Heróis</h3>
            <div class="profile-heroes-grid">
                ${heroesHtml}
            </div>

            <div class="profile-chart-container">
                <h3 class="profile-section-title">Evolução de Troféus (Local)</h3>
                <canvas id="trophyChart"></canvas>
            </div>
        `);

        if (userIsAdmin) {
            memberProfileContent.querySelectorAll('.cwl-status-btn').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    if (btn.classList.contains('active')) return;
                    const selector = e.target.closest('.cwl-status-selector');
                    const playerTag = e.target.closest('.member-cwl-status')?.dataset.playerTag;
                    const newStatus = e.target.dataset.status;
                    if (!playerTag || !newStatus) return;

                    selector?.querySelector('.active')?.classList.remove('active');
                    e.target.classList.add('active');
                    const success = await setPlayerCwlStatus(playerTag, newStatus);
                    if (!success) {
                        alert('Erro ao salvar status.');
                        e.target.classList.remove('active');
                    } else {
                         fetchData('members').then(populateMembersList);
                    }
                });
            });
        }

        if (memberTrophyChart) memberTrophyChart.destroy();
        const trophyCanvas = document.getElementById('trophyChart');
        
        if (trophyCanvas && profileData.trophy_history?.length > 0) {
            memberTrophyChart = new Chart(trophyCanvas.getContext('2d'), {
                type: 'line',
                data: {
                    labels: profileData.trophy_history.map(h => h.timestamp || '?'),
                    datasets: [{
                        label: 'Troféus', data: profileData.trophy_history.map(h => h.trophies || 0),
                        borderColor: 'rgba(54, 162, 235, 1)', backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        fill: true, tension: 0.1
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, scales: { y: { ticks: { color: '#fff' } }, x: { ticks: { color: '#fff' } } }, plugins: { legend: { display: false } } }
            });
        } else if (trophyCanvas) {
            const ctx = trophyCanvas.getContext('2d');
            ctx.clearRect(0, 0, trophyCanvas.width, trophyCanvas.height);
            ctx.fillStyle = 'rgba(255, 255, 255, 0.5)'; 
            ctx.textAlign = 'center';
            ctx.font = '14px Open Sans';
            ctx.fillText('Nenhum dado histórico registrado pelo bot ainda.', trophyCanvas.width / 2, trophyCanvas.height / 2);
        }
    }


    async function openHistoricWarModal(warId) {
        if (!warId || !historicWarModal || !historicWarDetailContent) return;
        setHtml(historicWarDetailContent, '<div class="loading-spinner" style="margin: 40px auto;"></div><p style="text-align:center;">A carregar detalhes da guerra...</p>');
        historicWarModal.style.display = 'block';

        const historicWarData = await fetchData(`war_history/${encodeURIComponent(warId)}`);

        const template = document.getElementById('historic-war-template');
        if (!template) {
            setHtml(historicWarDetailContent, '<p style="text-align:center; color: red;">Erro: Template do modal não encontrado.</p>');
            return;
        }

        historicWarDetailContent.innerHTML = ''; 
        try {
            const warDetailsContent = template.content.cloneNode(true);
            historicWarDetailContent.appendChild(warDetailsContent);
        } catch (e) {
            setHtml(historicWarDetailContent, '<p style="text-align:center; color: red;">Erro ao clonar template.</p>');
            return;
        }

        historicWarDetailContent.querySelectorAll('.war-tab-button').forEach(button => {
            button.addEventListener('click', () => {
                const modalContentEl = button.closest('.modal-content');
                if(!modalContentEl) return;
                modalContentEl.querySelectorAll('.war-tab-button').forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                const tabId = `historic-${button.dataset.tab}`;
                modalContentEl.querySelectorAll('.war-tab-content').forEach(content => {
                    content.style.display = content.id === tabId ? 'block' : 'none';
                });
            });
        });

        populateWarDetails(historicWarData, 'historicWarDetailContent', true);
    }

    warTabButtons.forEach(button => {
        button?.addEventListener('click', () => { 
            const parentSection = button.closest('.content-section');
            if (!parentSection) return;
            parentSection.querySelectorAll('.war-tab-button').forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            const tabId = button.dataset.tab;
            parentSection.querySelectorAll('.war-tab-content').forEach(content => {
                content.style.display = content.id === tabId ? 'block' : 'none';
            });
        });
    });

    if (closeModalButton) closeModalButton.addEventListener('click', () => { if(historicWarModal) historicWarModal.style.display = 'none'; });
    if (closeProfileModalButton) closeProfileModalButton.addEventListener('click', () => {
        if(memberProfileModal) memberProfileModal.style.display = 'none';
    });

    window.addEventListener('click', (event) => {
        if (event.target == historicWarModal && historicWarModal) historicWarModal.style.display = 'none';
        if (event.target == memberProfileModal && memberProfileModal) {
            memberProfileModal.style.display = 'none';
        }
    });

    warLogTableBodyEl?.addEventListener('click', (event) => { 
        const row = event.target.closest('.historic-war-row');
        if (row && row.dataset.warId) {
            openHistoricWarModal(row.dataset.warId);
        }
    });


    async function loadAllData() {
        try {
            const statusData = await fetch('/api/status').then(res => res.ok ? res.json() : { maintenance_mode: true, is_admin: false }).catch(() => ({ maintenance_mode: true, is_admin: false }));
            userIsAdmin = statusData.is_admin || false; 

            const clanData = await fetchData('clan');
            populateClanInfo(clanData);

            if (clanData?.error && isFirstLoad) { 
                if(loadingOverlayEl) loadingOverlayEl.classList.add('hidden');
                return; 
            }
            
            const [
                membersData, currentWarDetailsData, missedAttacksData,
                warLogData, cwlPlanData, highlightsData, warAdvisorData, capitalData, clanGamesData
            ] = await Promise.all([
                fetchData('members'), fetchData('current_war_details'), fetchData('missed_attacks_history'),
                fetchData('war_log'), fetchData('cwl/generate_plan', { method: 'POST' }), 
                fetchData('highlights'), fetchData('war_advisor_plan'), fetchData('capital'), fetchData('clan_games')
            ]);

            if (membersData && !membersData.error) populateMembersList(membersData);
            if (currentWarDetailsData) populateWarDetails(currentWarDetailsData, 'war-details-nav', false); 
            if (warAdvisorData) populateWarAdvisorPlan(warAdvisorData); 
            if (missedAttacksData && !missedAttacksData.error) populateMissedAttacksHistory(missedAttacksData);
            if (warLogData && !warLogData.error) populateWarLog(warLogData);
            if (cwlPlanData) populateCwlData(cwlPlanData); 
            if (highlightsData && !highlightsData.error) populateHighlights(highlightsData); 
            if (capitalData) populateCapitalData(capitalData);
            if (clanGamesData) populateClanGamesData(clanGamesData);

            updateLastUpdated();
        } catch (error) {
            console.error("Erro geral ao carregar todos os dados:", error);
            if (loadingStatusTextEl && loadingOverlayEl && !loadingOverlayEl.classList.contains('hidden')) {
                setText(loadingStatusTextEl, 'Erro grave ao carregar dados. Verifique a consola.');
            }
        } finally {
            if (isFirstLoad && loadingOverlayEl) {
                const isLoadingError = loadingStatusTextEl?.textContent?.toLowerCase().includes('erro');
                if(!isLoadingError){ 
                    setTimeout(() => { loadingOverlayEl.classList.add('hidden'); }, 300); 
                }
                isFirstLoad = false;
            }
        }
    }

    loadAllData();
    setInterval(loadAllData, 45000); 

    async function checkApiMaintenance() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/coc_status`, { cache: 'no-store' });
            if (!response.ok) { return; }
            const data = await response.json();
            if (data.status === 'maintenance') {
                if (!window.location.pathname.endsWith('/maintenance.html') && !window.location.pathname.endsWith('/maintenance')) {
                    window.location.href = '/maintenance'; 
                }
            } else if (data.status === 'ok' && (window.location.pathname.endsWith('/maintenance.html') || window.location.pathname.endsWith('/maintenance'))) {
                window.location.href = '/painel';
            }
        } catch (error) { console.error('Erro ao verificar status de manutenção:', error); }
    }
    checkApiMaintenance(); 
    setInterval(checkApiMaintenance, 20000); 
});
