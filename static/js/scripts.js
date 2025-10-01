document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = '';
    const DEFAULT_BADGE_URL = '/static/images/default_badge.png';
    let phaseTimerInterval = null; // Variável para controlar o timer

    // --- ELEMENTOS DO DOM ---
    const loadingOverlayEl = document.getElementById('loading-overlay');
    const loadingStatusTextEl = loadingOverlayEl.querySelector('p');
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

    const cwlStatusTextEl = document.getElementById('cwlStatusText');
    const cwlActiveInfoEl = document.getElementById('cwlActiveInfo');
    const cwlSeasonEl = document.getElementById('cwlSeason');
    const cwlGroupStateEl = document.getElementById('cwlGroupState');
    const cwlGroupClansEl = document.getElementById('cwlGroupClans');
    const cwlRoundsInfoEl = document.getElementById('cwlRoundsInfo');
    const noCwlMessageEl = document.getElementById('noCwlMessage');

    const cwlPlannerSectionEl = document.getElementById('cwlPlannerSection');
    const generateCwlPlanBtn = document.getElementById('generateCwlPlanBtn');
    const cwlPlanResultEl = document.getElementById('cwlPlanResult');
    const cwlInactivityAlertEl = document.getElementById('cwlInactivityAlert');
    const cwlInactivityTextEl = document.getElementById('cwlInactivityText');

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

    // --- FUNÇÃO DE FETCH MELHORADA ---
    async function fetchData(endpoint, options = {}) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/${endpoint}`, options);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: `Erro HTTP ${response.status}` }));
                
                if (response.status === 503) {
                    console.warn(`API retornou 503 (Serviço Indisponível) para ${endpoint}. O bot pode estar a iniciar.`);
                    if (!loadingOverlayEl.classList.contains('hidden')) {
                         setText(loadingStatusTextEl, errorData.error || 'A aguardar o bot iniciar...');
                    }
                } else {
                    console.error(`Erro na API! Status: ${response.status} para ${endpoint}`, errorData);
                }
                return { error: errorData.error || `Falha ao carregar ${endpoint}.` };
            }

            if (response.status === 204) return { success: true };
            return await response.json();

        } catch (error) {
            console.error(`Erro de conexão ao buscar ${endpoint}:`, error);
            if (loadingStatusTextEl && !loadingOverlayEl.classList.contains('hidden')) {
                setText(loadingStatusTextEl, 'Erro de conexão. Verifique a consola.');
            }
            return { error: `Erro de conexão ao buscar ${endpoint}.` };
        }
    }

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
    
    contentSections.forEach(section => {
        section.classList.toggle('active-section', section.id === currentActiveSectionId);
    });
    navLinks.forEach(link => {
        link.classList.toggle('active-nav-link', link.dataset.section === currentActiveSectionId);
    });

    function setActiveSection(newSectionId) {
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
    }

    navLinks.forEach((link) => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            setActiveSection(link.dataset.section);
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
        const noWarMsg = container.querySelector(isModal ? `#${prefix}noWarDetailMessage` : '#noWarDetailMessage');

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
        setText(query(`#${prefix}statsOurDestruction`), war.clan_destruction.replace('%', ''));
        setText(query(`#${prefix}statsOurAttacksUsed`), `${war.clan_attacks_used}/${war.team_size * war.attacks_per_member}`);
        setText(query(`#${prefix}statsOpponentName`), war.opponent_name);
        setText(query(`#${prefix}statsOpponentStars`), war.opponent_stars);
        setText(query(`#${prefix}statsOpponentDestruction`), war.opponent_destruction.replace('%', ''));
        setText(query(`#${prefix}statsOpponentAttacksUsed`), `${war.opponent_attacks_used}/${war.team_size * war.attacks_per_member}`);
        
        setText(query(`#${prefix}statsOurAvgStars`), war.clan_avg_stars);
        setText(query(`#${prefix}statsOpponentAvgStars`), war.opponent_avg_stars);
        for(let i=0; i<=3; i++) {
            setText(query(`#${prefix}statsOurStars${i}`), war.clan_star_distribution[i]);
            setText(query(`#${prefix}statsOpponentStars${i}`), war.opponent_star_distribution[i]);
        }

        const eventsTableBody = query(`#${prefix}warEventsTableBody`);
        setText(query(`#${prefix}warTotalAttacksCount`), data.all_attacks.length);
        setHtml(eventsTableBody, data.all_attacks.map(att => `
            <tr>
                <td>${att.order}</td>
                <td>${att.attacker_name} (CV${att.attacker_townhall})</td>
                <td><span class="attack-stars">${createStarString(att.stars)}</span> ${att.destruction}%</td>
                <td>${att.defender_name} (CV${att.defender_townhall})</td>
                <td>${att.duration}</td>
            </tr>
        `).join('') || '<tr><td colspan="5">Nenhum ataque registado.</td></tr>');

        const populateTeamTabData = (teamMembersData, teamName, teamElementId) => {
            setText(query(`#${prefix}${teamElementId}Name`), teamName);
            setHtml(query(`#${prefix}${teamElementId}Members`), teamMembersData.map(member => {
                const attacksHtml = '<h5>Ataques Feitos:</h5><ul class="member-attack-list">' + 
                    (member.attacks_made?.length > 0 
                        ? member.attacks_made.map(atk => `<li>${createStarString(atk.stars)} ${atk.destruction}% vs ${atk.defender_name} (CV${atk.defender_townhall})</li>`).join('')
                        : '<li>Nenhum ataque feito.</li>') + '</ul>';
                const defensesHtml = '<h5>Defesas Recebidas:</h5><ul class="member-defense-list">' +
                    (member.defenses_received?.length > 0
                        ? member.defenses_received.map(def => `<li>${createStarString(def.stars)} ${def.destruction}% por ${def.attacker_name} (CV${def.attacker_townhall})</li>`).join('')
                        : '<li>Nenhuma defesa registada.</li>') + '</ul>';
                return `<div class="team-member-card">
                            <h4><img src="/static/images/townhall${member.townhall}.png" alt="CV${member.townhall}" onerror="this.style.display='none'"/> ${member.map_position}. ${member.name} (CV${member.townhall})</h4>
                            <p>Ataques: ${member.attacks_used}/${war.attacks_per_member}</p>
                            ${attacksHtml}${defensesHtml}
                        </div>`;
            }).join('') || '<p>Nenhum membro nesta equipa para a guerra.</p>');
        };

        populateTeamTabData(data.our_clan_members_in_war, war.clan_name, "warOurTeam");
        populateTeamTabData(data.opponent_clan_members_in_war, war.opponent_name, "warOpponentTeam");
        
        if (!query('.war-tab-button.active')) {
            query('.war-tab-button[data-tab="war-stats"]')?.classList.add('active');
            query(isModal ? '#historic-war-stats' : '#war-stats').style.display = 'block';
        }
    }
    
    function populateWarAdvisorPlan(data) {
        if (!warAdvisorContentEl) return;
    
        // Limpa o timer anterior para evitar múltiplos intervalos
        if (phaseTimerInterval) {
            clearInterval(phaseTimerInterval);
            phaseTimerInterval = null;
        }
    
        const advisorPhaseTimerEl = document.getElementById('advisorPhaseTimer');
        const advisorPhaseTimerTextEl = document.getElementById('advisorPhaseTimerText');
        
        // CORREÇÃO: A lógica é encapsulada para ser chamada após a renderização
        const setupAdvisorUI = (planData) => {
            if (!planData.success) {
                if(advisorPhaseTimerEl) advisorPhaseTimerEl.style.display = 'none';
                setHtml(warAdvisorContentEl, `<div class="advisor-plan-container"><p class="message-box">${planData.error || 'Nenhuma recomendação disponível.'}</p></div>`);
                return;
            }
    
            let contentHtml = `
                <div class="advisor-header">
                    <h3>${planData.phase_title}</h3>
                    <p>${planData.prediction_summary}</p>
                </div>
                <div class="advisor-grid">
            `;
    
            contentHtml += planData.recommendations.map(rec => {
                const confidencePercent = (rec.confidence_score * 100).toFixed(0);
                let confidenceColor = 'low';
                if (confidencePercent >= 75) confidenceColor = 'high';
                else if (confidencePercent >= 50) confidenceColor = 'medium';
    
                const alternativesHtml = rec.alternative_targets.length > 0
                    ? `<div class="advisor-alternatives"><strong>Alternativas:</strong> #${rec.alternative_targets.join(', #')}</div>`
                    : '';
    
                return `
                    <div class="advisor-card type-${rec.attack_type}">
                        <div class="advisor-member-info">
                            <h4>${rec.member_pos}. ${rec.member_name} (CV${rec.member_th})</h4>
                            <span>Ataque Nº ${rec.attack_number}</span>
                        </div>
                        <div class="advisor-target-info">
                            <p>Alvo Recomendado</p>
                            <span>#${rec.recommended_target_pos} (CV${rec.recommended_target_th})</span>
                        </div>
                        <div class="advisor-justification">
                            <p><strong>IA:</strong> ${rec.justification}</p>
                        </div>
                        ${alternativesHtml}
                        <div class="advisor-confidence">
                            <span>Confiança da IA</span>
                            <div class="confidence-bar-container">
                                <div class="confidence-bar ${confidenceColor}" style="width: ${confidencePercent}%;"></div>
                            </div>
                            <span>${confidencePercent}%</span>
                        </div>
                    </div>
                `;
            }).join('');
    
            contentHtml += '</div>';
            
            // Renderiza o plano de ataque primeiro
            setHtml(warAdvisorContentEl, `<div id="advisorPhaseTimer" class="advisor-phase-timer" style="display: none;"><h4>MUDANÇA DE FASE</h4><p id="advisorPhaseTimerText">Calculando...</p></div>` + contentHtml);
            
            // Depois de renderizar, inicia o timer se houver dados
            if (planData.phase_2_start_time_iso) {
                const phase2StartTime = new Date(planData.phase_2_start_time_iso);
                const timerEl = document.getElementById('advisorPhaseTimer'); // Re-seleciona o elemento
                const timerTextEl = document.getElementById('advisorPhaseTimerText');
                if (timerEl && timerTextEl) {
                    timerEl.style.display = 'block';
                    
                    phaseTimerInterval = setInterval(() => {
                        const now = new Date();
                        const diff = phase2StartTime - now;
        
                        if (diff <= 0) {
                            setText(timerTextEl, 'Fase 2 Iniciada! Foco em ataques de limpeza.');
                            clearInterval(phaseTimerInterval);
                            phaseTimerInterval = null;
                            return;
                        }
        
                        const hours = Math.floor(diff / (1000 * 60 * 60));
                        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                        const seconds = Math.floor((diff % (1000 * 60)) / 1000);
        
                        setText(timerTextEl, `${hours}h ${minutes}m ${seconds}s`);
                    }, 1000);
                }
            }
        };
        
        // Inicia o processo
        setupAdvisorUI(data);
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
        cwlPlannerSectionEl.style.display = 'block';
        if (data.error || data.status === "NotInCwl") {
            if(noCwlMessageEl) noCwlMessageEl.style.display = 'block';
            setText(noCwlMessageEl, data.message || data.error || "O clã não está em CWL no momento.");
            if(cwlActiveInfoEl) cwlActiveInfoEl.style.display = 'none';
            generateCwlPlanBtn.disabled = true;
            generateCwlPlanBtn.classList.add('disabled');
        } else {
            if(noCwlMessageEl) noCwlMessageEl.style.display = 'none';
            if(cwlActiveInfoEl) cwlActiveInfoEl.style.display = 'block';
            setText(cwlSeasonEl, data.season);
            setText(cwlGroupStateEl, data.state);
            setHtml(cwlGroupClansEl, data.clans_in_group?.map(c => `<p><img src="${c.badge_url || DEFAULT_BADGE_URL}" alt="Emblema ${c.name}"> <strong>${c.name}</strong> (${c.tag}) Nv ${c.level}</p>`).join('') || '<p>Nenhum clã no grupo.</p>');
            setHtml(cwlRoundsInfoEl, data.rounds?.map(r => `
                <div class="cwl-round">
                    <h4>Rodada ${r.round_number}</h4>
                    ${r.wars?.map(w => w.error ? `<p class="cwl-war-entry">Guerra: ${w.error}</p>` : `<p class="cwl-war-entry">
                        <strong><img src="${w.clan_badge_url}" class="cwl-war-badge"> ${w.clan_name}</strong> ${w.clan_stars}⭐ vs ${w.opponent_stars}⭐ <strong><img src="${w.opponent_badge_url}" class="cwl-war-badge"> ${w.opponent_name}</strong>
                        <br><small>Estado: ${w.state_description}</small></p>`).join('') || "<p>Nenhuma guerra nesta rodada.</p>"}
                </div>
            `).join('') || "Nenhuma info de rodada.");
            generateCwlPlanBtn.disabled = false;
            generateCwlPlanBtn.classList.remove('disabled');
            checkCwlInactivity(); 
            setInterval(checkCwlInactivity, 60000);
        }
    }
    
    // CORREÇÃO: Função para gerar o plano de rotação da CWL
    async function handleGenerateCwlPlan() {
        generateCwlPlanBtn.disabled = true;
        generateCwlPlanBtn.innerHTML = '<div class="loading-spinner" style="width: 20px; height: 20px; border-width: 3px; margin: 0 auto;"></div>'; // Adiciona spinner
        cwlPlanResultEl.style.display = 'block';
        setHtml(cwlPlanResultEl, ''); // Limpa resultados anteriores

        const data = await fetchData('cwl/generate_plan', { method: 'POST' });

        generateCwlPlanBtn.disabled = false;
        generateCwlPlanBtn.textContent = 'Gerar Plano de Rotação'; // Restaura o texto do botão

        if (data.error) {
            setHtml(cwlPlanResultEl, `<p class="message-box">${data.error}</p>`);
        } else if (data.schedule && Array.isArray(data.schedule)) {
            // Cria abas para cada dia
            const tabsHtml = data.schedule.map((dayPlan, index) => 
                `<button class="cwl-plan-tab ${index === 0 ? 'active' : ''}" data-day="${dayPlan.day}">Dia ${dayPlan.day}</button>`
            ).join('');
            
            // Cria o conteúdo para cada dia
            const contentHtml = data.schedule.map((dayPlan, index) => `
                <div class="day-plan-content ${index === 0 ? 'active' : ''}" id="day-plan-${dayPlan.day}">
                    <h6>🔄 Alterações na Equipa</h6>
                    ${dayPlan.substitutions.length > 0 
                        ? dayPlan.substitutions.map(sub => `
                            <div class="substitution-card">
                                <p><span style="color: var(--color-danger);">🔴 Sai:</span> ${sub.out.name} (CV${sub.out.town_hall})</p>
                                <p><span style="color: var(--color-success);">🟢 Entra:</span> ${sub.in.name} (CV${sub.in.town_hall})</p>
                            </div>`).join('') 
                        : '<p>Nenhuma alteração na escalação para este dia.</p>'
                    }
                    <h6>⚔️ Escalação Ativa</h6>
                    <div class="roster-list">
                        ${dayPlan.active_roster.map((player, i) => `<span>${i + 1}. ${player.name} (CV${player.town_hall})</span>`).join('')}
                    </div>
                </div>
            `).join('');

            // Junta tudo para injeção no DOM
            const fullHtml = `
                <h4 class="plan-summary">${data.summary}</h4>
                <nav class="cwl-plan-tabs">${tabsHtml}</nav>
                <div class="cwl-plan-content-wrapper">${contentHtml}</div>
            `;
            setHtml(cwlPlanResultEl, fullHtml);

            // Adiciona os event listeners para as abas recém-criadas
            cwlPlanResultEl.querySelectorAll('.cwl-plan-tab').forEach(tab => {
                tab.addEventListener('click', () => {
                    cwlPlanResultEl.querySelectorAll('.cwl-plan-tab').forEach(t => t.classList.remove('active'));
                    cwlPlanResultEl.querySelectorAll('.day-plan-content').forEach(c => c.classList.remove('active'));
                    
                    tab.classList.add('active');
                    document.getElementById(`day-plan-${tab.dataset.day}`).classList.add('active');
                });
            });

        } else {
            setHtml(cwlPlanResultEl, `<p class="message-box">Não foi possível gerar o plano. Resposta da API inválida.</p>`);
        }
    }

    async function checkCwlInactivity() {
        const data = await fetchData('cwl/inactivity_check');
        if (data && data.alert) {
            const { inactive_players, time_remaining, best_substitute } = data.alert;
            let alertText = `<strong>${inactive_players.map(p => p.name).join(', ')}</strong> ainda não atacou(aram)! Faltam ${time_remaining} horas.`;
            if (best_substitute) {
                alertText += `<br>A IA sugere a substituição imediata por <strong>${best_substitute.name}</strong> para não afetar a próxima rodada.`;
            }
            setHtml(cwlInactivityTextEl, alertText);
            cwlInactivityAlertEl.style.display = 'block';
        } else {
            cwlInactivityAlertEl.style.display = 'none';
        }
    }

    if (generateCwlPlanBtn) {
        generateCwlPlanBtn.addEventListener('click', handleGenerateCwlPlan);
    }

    function populateWarLog(data) {
        setText(warLogLimitEl, data.log?.length || '0');
        if (data.error || !data.log?.length) {
            if(noWarLogMessageEl) noWarLogMessageEl.style.display = 'block';
            setText(noWarLogMessageEl, data.error || "Log de guerra indisponível.");
            setHtml(warLogTableBodyEl, `<tr><td colspan="6">${data.error || "Nenhum registo encontrado."}</td></tr>`);
            return;
        }
        if(noWarLogMessageEl) noWarLogMessageEl.style.display = 'none';
        setHtml(warLogTableBodyEl, data.log.map(e => `
            <tr class="historic-war-row" data-war-id="${e.end_time_iso}">
                <td>${e.end_time_formatted}</td>
                <td><img src="${e.opponent_badge_url || DEFAULT_BADGE_URL}" alt="Emblema" class="log-opponent-badge">${e.opponent_name || 'N/A'}</td>
                <td>${e.clan_stars}⭐ vs ${e.opponent_stars}⭐</td>
                <td class="war-result-${e.result?.toLowerCase()}">${e.result}</td>
                <td>${e.team_size}</td>
                <td>${e.is_cwl ? "CWL" : "Normal"}</td>
            </tr>
        `).join(''));
    }

    async function savePlayerNote(playerTag, text, priority) {
        await fetchData(`notes/${encodeURIComponent(playerTag)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, priority })
        });
    }
    
    function populateMembersList(data) {
        setText(membersClanNameEl, data.clan_name);
        if (data.error || !data.members) {
            setHtml(membersGridEl, `<p class="message-box">${data.error || "Não foi possível carregar os membros."}</p>`);
            return;
        }

        setHtml(membersGridEl, data.members.map(m => `
            <div class="member-card" data-th="${m.town_hall}" data-name="${m.name.toLowerCase()}">
                <div class="member-card-header" data-player-tag="${m.tag}">
                    <img src="/static/images/townhall${m.town_hall}.png" alt="CV${m.town_hall}" class="member-th-icon" onerror="this.style.display='none'">
                    <div class="member-info">
                        <h4>${m.name}</h4>
                        <p>${m.role} • 🏆 ${m.trophies}</p>
                    </div>
                </div>
                <div class="member-card-stats">
                    <span>🎁 Doadas: ${m.donations}</span>
                    <span>📥 Recebidas: ${m.received}</span>
                </div>
                <div class="member-card-note">
                    <div class="note-container note-priority-${m.note_priority || 'none'}">
                        <span class="note-text">${m.note || 'Clique para editar...'}</span>
                        <input type="text" class="note-input" value="${m.note}" style="display: none;">
                        <div class="priority-selector">
                            ${['green', 'yellow', 'red', 'none'].map(prio => `
                                <button class="priority-btn priority-${prio} ${prio === (m.note_priority || 'none') ? 'active' : ''}" data-priority="${prio}">
                                    ${prio === 'green' ? '✓' : prio === 'yellow' ? '!' : prio === 'red' ? '✗' : '×'}
                                </button>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>`).join(''));
        attachMemberEventListeners();
    }

    function attachMemberEventListeners() {
        document.querySelectorAll('.member-card-header').forEach(header => {
            header.addEventListener('click', () => openMemberProfileModal(header.dataset.playerTag));
        });
        document.querySelectorAll('.note-text').forEach(span => {
            span.addEventListener('click', () => {
                const input = span.nextElementSibling;
                span.style.display = 'none';
                input.style.display = 'inline-block';
                input.focus();
            });
        });
        document.querySelectorAll('.note-input').forEach(input => {
            const saveChanges = () => {
                const container = input.closest('.note-container');
                const span = container.querySelector('.note-text');
                const playerTag = input.closest('.member-card').querySelector('.member-card-header').dataset.playerTag;
                const activePriority = container.querySelector('.priority-btn.active')?.dataset.priority || 'none';
                span.textContent = input.value || 'Clique para editar...';
                input.style.display = 'none';
                span.style.display = 'inline-block';
                savePlayerNote(playerTag, input.value, activePriority);
            };
            input.addEventListener('blur', saveChanges);
            input.addEventListener('keypress', e => { if (e.key === 'Enter') input.blur(); });
        });
        document.querySelectorAll('.priority-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const container = btn.closest('.note-container');
                const playerTag = btn.closest('.member-card').querySelector('.member-card-header').dataset.playerTag;
                const text = container.querySelector('.note-input').value;
                const newPriority = btn.dataset.priority;
                container.className = `note-container note-priority-${newPriority}`;
                container.querySelectorAll('.priority-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                savePlayerNote(playerTag, text, newPriority);
            });
        });
    }

    function applyMemberFilters() {
        const nameFilter = filterNameInput.value.toLowerCase();
        const thFilter = filterTHInput.value;
        document.querySelectorAll('.member-card').forEach(card => {
            const name = card.dataset.name;
            const th = card.dataset.th;
            card.style.display = (name.includes(nameFilter) && (!thFilter || th === thFilter)) ? 'flex' : 'none';
        });
    }
    
    [filterNameInput, filterTHInput].forEach(input => input.addEventListener('keyup', applyMemberFilters));

    async function openMemberProfileModal(playerTag) {
        setHtml(memberProfileContent, '<div class="loading-spinner" style="margin: 40px auto;"></div><p style="text-align:center;">A carregar perfil do membro...</p>');
        memberProfileModal.style.display = 'block';
        const profileData = await fetchData(`player_profile/${encodeURIComponent(playerTag)}`);

        if (profileData.error) {
            setHtml(memberProfileContent, `<p class="message-box">${profileData.error}</p>`);
            return;
        }
        
        const heroesHtml = profileData.heroes.map(hero => `
            <div class="hero-item">
                <img src="/static/images/heroes/${hero.name.toLowerCase().replace(/\s+/g, '-')}.png" alt="${hero.name}" onerror="this.style.display='none'">
                <p><strong>${hero.level}</strong> / ${hero.max_level}</p>
            </div>
        `).join('');

        const leagueImageHtml = profileData.league_icon 
            ? `<div class="profile-league-container">
                   <img src="${profileData.league_icon}" alt="${profileData.league}" class="profile-league-image">
               </div>` 
            : '';

        const statsGridHtml = `
            <div class="profile-details-container">
                <div class="profile-stats-grid">
                    <div class="profile-stat-card"><h4>Liga</h4><p>${profileData.league}</p></div>
                    <div class="profile-stat-card"><h4>Troféus</h4><p>🏆 ${profileData.trophies}</p></div>
                    <div class="profile-stat-card"><h4>Doadas</h4><p>🎁 ${profileData.donations}</p></div>
                    <div class="profile-stat-card"><h4>Recebidas</h4><p>📥 ${profileData.received}</p></div>
                </div>
            </div>`;

        setHtml(memberProfileContent, `
            <div class="profile-header">
                <h2>${profileData.name} (CV${profileData.town_hall})</h2>
                <p class="player-tag">${profileData.tag}</p>
            </div>
            <div class="profile-main-content">
                ${leagueImageHtml}
                ${statsGridHtml}
            </div>
            <h3>Heróis</h3>
            <div class="heroes-list">${heroesHtml || '<p>Nenhum herói encontrado.</p>'}</div>
            <div class="profile-chart-container">
                 <h3>Evolução de Troféus</h3>
                <canvas id="trophyChart"></canvas>
            </div>
        `);

        if (memberTrophyChart) memberTrophyChart.destroy();
        if (profileData.trophy_history?.length > 0) {
            memberTrophyChart = new Chart(document.getElementById('trophyChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: profileData.trophy_history.map(h => h.timestamp),
                    datasets: [{
                        label: 'Troféus',
                        data: profileData.trophy_history.map(h => h.trophies),
                        borderColor: 'rgba(54, 162, 235, 1)',
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        fill: true,
                        tension: 0.1
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, scales: { y: { ticks: { color: 'rgba(255, 255, 255, 0.7)' } }, x: { ticks: { color: 'rgba(255, 255, 255, 0.7)' } } }, plugins: { legend: { display: false } } }
            });
        }
    }

    async function openHistoricWarModal(warId) {
        setHtml(historicWarDetailContent, '<div class="loading-spinner" style="margin: 40px auto;"></div><p style="text-align:center;">A carregar detalhes da guerra...</p>');
        historicWarModal.style.display = 'block';
        const historicWarData = await fetchData(`war_history/${warId}`);
        const template = document.getElementById('historic-war-template');
        if (!template) {
            setHtml(historicWarDetailContent, '<p style="text-align:center; color: red;">Erro: Template do modal não encontrado.</p>');
            return;
        }
        const warDetailsContent = template.content.cloneNode(true);
        historicWarDetailContent.innerHTML = '';
        historicWarDetailContent.appendChild(warDetailsContent);
        historicWarDetailContent.querySelectorAll('.war-tab-button').forEach(button => {
            button.addEventListener('click', () => {
                const modalContentEl = button.closest('.modal-content');
                modalContentEl.querySelectorAll('.war-tab-button').forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                const tabId = `historic-${button.dataset.tab}`;
                modalContentEl.querySelectorAll('.war-tab-content').forEach(content => { content.style.display = content.id === tabId ? 'block' : 'none'; });
            });
        });
        populateWarDetails(historicWarData, 'historicWarDetailContent', true);
    }
    
    warTabButtons.forEach(button => {
        button.addEventListener('click', () => {
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

    // --- CARREGAMENTO INICIAL E PERIÓDICO ---
    async function loadAllData() {
        try {
            const clanData = await fetchData('clan');
            if (clanData.error) {
                if (!isFirstLoad) { 
                    loadingOverlayEl.classList.add('hidden');
                }
                return; 
            }
            
            const [
                membersData, 
                currentWarDetailsData, 
                missedAttacksData, 
                warLogData, 
                cwlInfoData, 
                highlightsData,
                warAdvisorData
            ] = await Promise.all([
                fetchData('members'), 
                fetchData('current_war_details'),
                fetchData('missed_attacks_history'), 
                fetchData('war_log'), 
                fetchData('cwl_info'), 
                fetchData('highlights'),
                fetchData('war_advisor_plan')
            ]);
            populateClanInfo(clanData);
            populateMembersList(membersData);
            populateWarDetails(currentWarDetailsData, 'war-details-nav', false); 
            populateWarAdvisorPlan(warAdvisorData);
            populateMissedAttacksHistory(missedAttacksData);
            populateWarLog(warLogData);
            populateCwlInfo(cwlInfoData);
            populateHighlights(highlightsData);
            updateLastUpdated();
        } catch (error) {
            console.error("Erro geral ao carregar todos os dados:", error);
        } finally {
            if (isFirstLoad) {
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
             openHistoricWarModal(row.dataset.warId);
        }
    });

    loadAllData();
    setInterval(loadAllData, 45000);
});
