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
    const cwlPlanSpinner = document.getElementById('cwlPlanSpinner');
    const cwlPlanContentEl = document.getElementById('cwlPlanContent');
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

            if (response.status === 204) return { success: true }; // Handle No Content response
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
                document.body.removeEventListener('click', playMusic); // Remove listener after first interaction
            } catch (err) {
                console.log('Autoplay da música bloqueado pelo navegador.');
                // We don't need to add the listener again if blocked initially
            }
        };
        // Add listener only once on body click to attempt play
        document.body.addEventListener('click', playMusic, { once: true });

        muteButtonEl.addEventListener('click', () => {
            backgroundMusicEl.muted = !backgroundMusicEl.muted;
            muteButtonEl.textContent = backgroundMusicEl.muted ? '🔇' : '🔊';
            localStorage.setItem('musicMuted', backgroundMusicEl.muted); // Save preference
        });

        // Restore preference on load
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

    // Set initial active section and link
    contentSections.forEach(section => {
        section.classList.toggle('active-section', section.id === currentActiveSectionId);
    });
    navLinks.forEach(link => {
        link.classList.toggle('active-nav-link', link.dataset.section === currentActiveSectionId);
    });

    function setActiveSection(newSectionId) {
        if (newSectionId === currentActiveSectionId) return; // Do nothing if already active

        const oldSectionEl = document.getElementById(currentActiveSectionId);
        const newSectionEl = document.getElementById(newSectionId);

        if (!newSectionEl) return; // Exit if the new section doesn't exist

        // Remove active class from old section and link
        if (oldSectionEl) oldSectionEl.classList.remove('active-section');
        navLinks.forEach(link => link.classList.remove('active-nav-link'));

        // Add active class to new section and link
        newSectionEl.classList.add('active-section');
        const newLink = document.querySelector(`.nav-link[data-section="${newSectionId}"]`);
        if (newLink) newLink.classList.add('active-nav-link');

        // Store the new active section and update the current ID
        localStorage.setItem('activeSection', newSectionId);
        currentActiveSectionId = newSectionId;
    }

    // Add click listeners to navigation links
    navLinks.forEach((link) => {
        link.addEventListener('click', (e) => {
            e.preventDefault(); // Prevent default anchor behavior
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
        // Removed Capital Districts population as per previous request
        // setHtml(clanCapitalDistrictsEl, data.capital_districts?.map(d => `<p><strong>${d.name || 'N/A'}:</strong> Nv ${d.level || '?'}</p>`).join('') || '<p>Nenhum distrito encontrado.</p>');
        setText(botVersionEl, data.version, '?');
    }

    function populateHighlights(data) {
        if (data.error || !data.clan_name) {
            noHighlightsMessageEl.style.display = 'block';
            setText(noHighlightsMessageEl, data.error || "Não foi possível carregar os destaques.");
            document.getElementById('highlightsContent').style.display = 'none'; // Hide content area
            return;
        }

        // Show content area and hide error message
        noHighlightsMessageEl.style.display = 'none';
        document.getElementById('highlightsContent').style.display = 'block';

        setText(highlightsClanNameEl, data.clan_name);
        setText(warDateHighlightEl, data.war_date ? `(${data.war_date})` : ''); // Show war date if available

        // Populate Top Donors
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

        // Populate War Heroes/Best Attacks
        const warHeroTitleEl = document.getElementById('warHeroTitle');
        setText(warHeroTitleEl, '⚔️ Heróis da Última Guerra'); // Title for the section
        setHtml(bestAttacksListEl, data.war_heroes?.map(hero => {
            const isMvp = hero.rank === 1;
            const heroClass = isMvp ? 'mvp-card' : 'attack-item'; // Different style for MVP
            const medals = ['🥇', '🥈', '🥉'];
            const titleHtml = isMvp
                ? `<p class="mvp-title">Jogador Mais Valioso (MVP)</p><h4 class="mvp-name">${hero.name} <span>(CV${hero.town_hall})</span></h4>` // MVP specific title
                : `<div class="attack-header">${medals[hero.rank - 1] || ''} ${hero.name} (CV${hero.town_hall})</div>`; // Normal rank title

            // Add tooltip with the reason
            return `<div class="${heroClass}">
                        ${titleHtml}
                        <span class="tooltip-text">${hero.reason}</span>
                    </div>`;
        }).join('') || '<p>Nenhum herói para destacar na última guerra.</p>');

        // Destroy previous chart instance if exists
        if (activityChart) activityChart.destroy();

        // Create new Activity Chart if data is available
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
                options: { // Chart options for responsiveness, axes, legend colors
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, ticks: { color: 'rgba(255, 255, 255, 0.7)' } }, // Y-axis styling
                        x: { ticks: { color: 'rgba(255, 255, 255, 0.7)' } } // X-axis styling
                    },
                    plugins: {
                        legend: { labels: { color: 'rgba(255, 255, 255, 0.8)' } } // Legend styling
                    }
                }
            });
        }
    }

    function createStarString(stars) {
        // Creates a string like ⭐⭐⚫ for 2 stars
        return '⭐'.repeat(stars) + '⚫'.repeat(Math.max(0, 3 - stars));
    }

    function populateWarDetails(data, containerId = 'war-details-nav', isModal = false) {
        const container = document.getElementById(containerId);
        if (!container) return; // Exit if container not found

        const prefix = isModal ? 'historic-' : ''; // Prefix for element IDs in modal
        const warHeader = container.querySelector('.war-header');
        const warTabsNav = container.querySelector('.war-tabs');
        const noWarMsg = container.querySelector(isModal ? `#${prefix}noWarDetailMessage` : '#noWarDetailMessage');
        const predictionSection = container.querySelector(isModal ? null : '#warPredictionSection'); // Prediction only on main page

        // Handle error or no war data
        if (data.error || !data.war_data) {
            if (noWarMsg) { noWarMsg.style.display = 'block'; setText(noWarMsg, data.error || "Nenhuma guerra para detalhar."); }
            if (warHeader) warHeader.style.display = 'none';
            if (warTabsNav) warTabsNav.style.display = 'none';
            container.querySelectorAll('.war-tab-content').forEach(tab => tab.style.display = 'none'); // Hide all tabs
            if (predictionSection) predictionSection.style.display = 'none'; // Hide prediction
            return;
        }

        // --- Populate War Prediction (only on main page) ---
        if (!isModal && predictionSection) {
            const predictionTextEl = container.querySelector('#warPredictionText');
            const predictionTagsEl = container.querySelector('#warPredictionTags');

            if (data.prediction && data.prediction.summary_panel) {
                setText(predictionTextEl, data.prediction.summary_panel);
                // Populate prediction tags with probability and confidence
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
                predictionSection.style.display = 'block'; // Show prediction section
            } else {
                predictionSection.style.display = 'none'; // Hide if no prediction data
            }
        } else if (predictionSection) {
             predictionSection.style.display = 'none'; // Ensure prediction is hidden in modal
        }


        // --- Populate General War Info ---
        if (noWarMsg) noWarMsg.style.display = 'none'; // Hide no war message
        if (warHeader) warHeader.style.display = 'flex'; // Show header
        if (warTabsNav) warTabsNav.style.display = 'flex'; // Show tabs

        const war = data.war_data;
        const query = (sel) => container.querySelector(sel); // Helper to query within container

        // Set header info
        setText(query(`#${prefix}warDetailOurClanName`), war.clan_name);
        setText(query(`#${prefix}warDetailOpponentName`), war.opponent_name);
        setBadge(query(`#${prefix}warDetailClanBadge`), war.clan_badge_url);
        setBadge(query(`#${prefix}warDetailOpponentBadge`), war.opponent_badge_url);
        setText(query(`#${prefix}warDetailTimeKey`), war.time_key);
        setText(query(`#${prefix}warDetailTimeValue`), war.time_value);
        setText(query(`#${prefix}warDetailTimeRemaining`), war.time_remaining);
        const stateEl = query(`#${prefix}warDetailState`);
        setText(stateEl, war.state_description);
        if(stateEl) stateEl.className = 'war-state ' + (war.status || '').toLowerCase(); // Style based on war state

        // --- Populate Stats Tab ---
        setText(query(`#${prefix}statsOurClanName`), war.clan_name);
        setText(query(`#${prefix}statsOurStars`), war.clan_stars);
        setText(query(`#${prefix}statsOurDestruction`), war.clan_destruction?.replace('%', '')); // Remove % for display
        setText(query(`#${prefix}statsOurAttacksUsed`), `${war.clan_attacks_used}/${war.team_size * war.attacks_per_member}`);
        setText(query(`#${prefix}statsOpponentName`), war.opponent_name);
        setText(query(`#${prefix}statsOpponentStars`), war.opponent_stars);
        setText(query(`#${prefix}statsOpponentDestruction`), war.opponent_destruction?.replace('%', '')); // Remove %
        setText(query(`#${prefix}statsOpponentAttacksUsed`), `${war.opponent_attacks_used}/${war.team_size * war.attacks_per_member}`);

        setText(query(`#${prefix}statsOurAvgStars`), war.clan_avg_stars);
        // Average duration needs backend support or complex calculation here
        // setText(query(`#${prefix}statsOurAvgDuration`), '-');
        setText(query(`#${prefix}statsOpponentAvgStars`), war.opponent_avg_stars);
        // setText(query(`#${prefix}statsOpponentAvgDuration`), '-');

        // Populate star distribution
        if(war.clan_star_distribution){
             for(let i=0; i<=3; i++) setText(query(`#${prefix}statsOurStars${i}`), war.clan_star_distribution[i]);
        }
         if(war.opponent_star_distribution){
             for(let i=0; i<=3; i++) setText(query(`#${prefix}statsOpponentStars${i}`), war.opponent_star_distribution[i]);
         }


        // --- Populate Events Tab ---
        const eventsTableBody = query(`#${prefix}warEventsTableBody`);
        setText(query(`#${prefix}warTotalAttacksCount`), data.all_attacks.length); // Show total attacks
        setHtml(eventsTableBody, data.all_attacks.map(att => `
            <tr>
                <td>${att.order}</td>
                <td>${att.attacker_name} (CV${att.attacker_townhall})</td>
                <td><span class="attack-stars">${createStarString(att.stars)}</span> ${att.destruction}%</td>
                <td>${att.defender_name} (CV${att.defender_townhall})</td>
                <td>${att.duration}</td>
            </tr>
        `).join('') || '<tr><td colspan="5">Nenhum ataque registado.</td></tr>'); // Message if no attacks

        // --- Populate Team Tabs ---
        const populateTeamTabData = (teamMembersData, teamName, teamElementId) => {
            setText(query(`#${prefix}${teamElementId}Name`), teamName); // Set team name header
            // Map member data to HTML cards
            setHtml(query(`#${prefix}${teamElementId}Members`), teamMembersData.map(member => {
                // Generate HTML for attacks made
                const attacksHtml = '<h5>Ataques Feitos:</h5><ul class="member-attack-list">' +
                    (member.attacks_made?.length > 0
                        ? member.attacks_made.map(atk => `<li>${createStarString(atk.stars)} ${atk.destruction}% vs ${atk.defender_name} (CV${atk.defender_townhall})</li>`).join('')
                        : '<li>Nenhum ataque feito.</li>') + '</ul>';
                // Generate HTML for defenses received
                const defensesHtml = '<h5>Defesas Recebidas:</h5><ul class="member-defense-list">' +
                    (member.defenses_received?.length > 0
                        ? member.defenses_received.map(def => `<li>${createStarString(def.stars)} ${def.destruction}% por ${def.attacker_name} (CV${def.attacker_townhall})</li>`).join('')
                        : '<li>Nenhuma defesa registada.</li>') + '</ul>';
                // Member card HTML
                return `<div class="team-member-card">
                            <h4><img src="/static/images/townhall${member.townhall}.png" alt="CV${member.townhall}" onerror="this.style.display='none'"/> ${member.map_position}. ${member.name} (CV${member.townhall})</h4>
                            <p>Ataques: ${member.attacks_used}/${war.attacks_per_member}</p>
                            ${attacksHtml}${defensesHtml}
                        </div>`;
            }).join('') || '<p>Nenhum membro nesta equipa para a guerra.</p>'); // Message if no members
        };

        populateTeamTabData(data.our_clan_members_in_war, war.clan_name, "warOurTeam");
        populateTeamTabData(data.opponent_clan_members_in_war, war.opponent_name, "warOpponentTeam");

        // --- Activate Default Tab (if needed, especially for modal) ---
         if (!query('.war-tab-button.active')) { // If no tab is currently active
            const firstTabButton = query('.war-tab-button'); // Get the first tab button
            const firstTabContentId = isModal ? `#historic-${firstTabButton?.dataset.tab}` : `#${firstTabButton?.dataset.tab}`; // Determine content ID
            const firstTabContent = query(firstTabContentId); // Get the content element
            firstTabButton?.classList.add('active'); // Activate button
            if(firstTabContent) firstTabContent.style.display = 'block'; // Show content
         }
    }

    function populateWarAdvisorPlan(data) {
        if (!warAdvisorContentEl) return; // Exit if element doesn't exist

        // Clear existing timer if running
        if (phaseTimerInterval) {
            clearInterval(phaseTimerInterval);
            phaseTimerInterval = null;
        }

        // Function to set up the UI based on plan data
         const setupAdvisorUI = (planData) => {
             // Handle error or unsuccessful plan generation
            if (!planData || !planData.success) {
                // Hide timer if it exists in the template
                const timerEl = warAdvisorContentEl.querySelector('#advisorPhaseTimer');
                if(timerEl) timerEl.style.display = 'none';
                // Show error message
                setHtml(warAdvisorContentEl, `<div class="advisor-plan-container"><p class="message-box">${planData?.error || 'Nenhuma recomendação disponível.'}</p></div>`);
                return;
            }

            // --- Build Advisor Plan HTML ---
            // Start with timer placeholder and header
            let contentHtml = `
                <div id="advisorPhaseTimer" class="advisor-phase-timer" style="display: none;"><h4>MUDANÇA DE FASE</h4><p id="advisorPhaseTimerText">Calculando...</p></div>
                <div class="advisor-header">
                    <h3>${planData.phase_title}</h3>
                    <p>${planData.prediction_summary}</p>
                </div>
                <div class="advisor-grid">
            `;

            // Map each recommendation to an advisor card
            contentHtml += planData.recommendations.map(rec => {
                 const confidencePercent = (rec.confidence_score * 100).toFixed(0);
                 // Determine confidence color based on score
                 let confidenceColor = 'low';
                 if (confidencePercent >= 75) confidenceColor = 'high';
                 else if (confidencePercent >= 50) confidenceColor = 'medium';
                 // Add alternative targets if available
                 const alternativesHtml = rec.alternative_targets.length > 0
                     ? `<div class="advisor-alternatives"><strong>Alternativas:</strong> #${rec.alternative_targets.join(', #')}</div>`
                     : '';
                 // Card HTML structure
                 return `
                    <div class="advisor-card type-${rec.attack_type || 'unknown'}"> {/* Class based on attack type */}
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
                                <div class="confidence-bar ${confidenceColor}" style="width: ${confidencePercent}%;"></div> {/* Confidence bar */}
                            </div>
                            <span>${confidencePercent}%</span>
                        </div>
                    </div>`;
            }).join(''); // Join all card HTML strings
             contentHtml += '</div>'; // Close advisor-grid
             setHtml(warAdvisorContentEl, contentHtml); // Set the generated HTML

             // --- Set up Phase Timer (if applicable) ---
             // Query timer elements *after* setting the HTML
             const timerEl = warAdvisorContentEl.querySelector('#advisorPhaseTimer');
             const timerTextEl = warAdvisorContentEl.querySelector('#advisorPhaseTimerText');

             // Check if phase 2 start time is provided and elements exist
             if (planData.phase_2_start_time_iso && timerEl && timerTextEl) {
                const phase2StartTime = new Date(planData.phase_2_start_time_iso);
                timerEl.style.display = 'block'; // Show the timer
                // Start interval to update timer every second
                phaseTimerInterval = setInterval(() => {
                    const now = new Date(); const diff = phase2StartTime - now; // Calculate time difference
                    if (diff <= 0) { // If time is up
                        setText(timerTextEl, 'Fase 2 Iniciada! Foco em limpeza.'); // Update text
                        clearInterval(phaseTimerInterval); // Stop timer
                        phaseTimerInterval = null;
                        return;
                    }
                    // Calculate hours, minutes, seconds remaining
                    const hours = Math.floor(diff / (36e5)); // 1000 * 60 * 60
                    const minutes = Math.floor((diff % (36e5)) / (6e4)); // 1000 * 60
                    const seconds = Math.floor((diff % (6e4)) / 1000);
                    // Update timer text
                    setText(timerTextEl, `${hours}h ${minutes}m ${seconds}s`);
                }, 1000);
             } else if (timerEl) { // If no phase 2 time, hide timer element
                 timerEl.style.display = 'none';
             }
         };
         // Call the setup function with the provided data
         setupAdvisorUI(data);
    }

    function populateMissedAttacksHistory(data) {
        setText(attacksRemainingTitleEl.querySelector('span'), data.clan_name); // Set clan name in title
        // Handle error or no data
        if (data.error || !data.wars_with_missed_attacks?.length) {
            setHtml(missedAttacksContainerEl, ''); // Clear container
            if (noMissedAttacksMessageEl) { noMissedAttacksMessageEl.style.display = 'block'; setText(noMissedAttacksMessageEl, data.error || "Nenhuma pendência de ataque encontrada."); }
            return;
        }
        // Hide error message and populate container
        if (noMissedAttacksMessageEl) noMissedAttacksMessageEl.style.display = 'none';
        setHtml(missedAttacksContainerEl, data.wars_with_missed_attacks.map(war => `
            <div class="war-group">
                {/* War header with opponent and date */}
                <h3 class="war-group-header">Guerra vs <strong>${war.opponent_name}</strong> (${war.end_date}) ${war.is_latest ? '<span class="latest-war-badge">💥 Última Guerra</span>' : ''}</h3>
                <div class="player-card-grid">
                    {/* Map members with missed attacks */}
                    ${war.missed_attacks_members.map(member => `
                        <div class="missed-attack-card ${member.attacks_left >= 2 ? 'severity-high' : 'severity-medium'}"> {/* Style based on severity */}
                            <div class="player-info">
                                <h4>${member.name} <span>(CV${member.town_hall})</span></h4>
                                <div class="player-tag-container">
                                    <span class="player-tag">${member.tag}</span>
                                    {/* Copy button */}
                                    <button class="copy-tag-btn" data-tag="${member.tag}">Copiar</button>
                                </div>
                            </div>
                            <div class="attacks-info">
                                <span class="attacks-count">${member.attacks_left}</span>
                                <span class="attacks-label">Ataque${member.attacks_left > 1 ? 's' : ''} Pendente${member.attacks_left > 1 ? 's' : ''}</span>
                            </div>
                        </div>`).join('')}
                </div>
            </div>`).join(''));
        // Add listeners to copy buttons after they are added to the DOM
        document.querySelectorAll('.copy-tag-btn').forEach(button => {
            button.addEventListener('click', () => copyTagToClipboard(button));
        });
    }

    function copyTagToClipboard(button) {
        const tag = button.dataset.tag;
        // Use document.execCommand as a fallback for potential iframe restrictions
        const textArea = document.createElement("textarea");
        textArea.value = tag;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy'); // Attempt copy command
            button.textContent = 'Copiado!'; // Success feedback
            button.disabled = true; // Disable briefly
            setTimeout(() => { // Reset button after 2 seconds
                button.textContent = 'Copiar';
                button.disabled = false;
            }, 2000);
        } catch (err) {
            console.error('Falha ao copiar tag:', err); // Log error
            button.textContent = 'Erro'; // Error feedback
            setTimeout(() => { button.textContent = 'Copiar'; }, 2000); // Reset button
        }
        document.body.removeChild(textArea); // Clean up textarea element
    }

    function populateCwlInfo(data) {
        cwlPlannerSectionEl.style.display = 'block'; // Show planner section regardless
        // Handle error or not in CWL
        if (data.error || data.status === "NotInCwl") {
            if(noCwlMessageEl) noCwlMessageEl.style.display = 'block'; // Show message
            setText(noCwlMessageEl, data.message || data.error || "O clã não está em CWL no momento.");
            if(cwlActiveInfoEl) cwlActiveInfoEl.style.display = 'none'; // Hide active info
            generateCwlPlanBtn.disabled = true; generateCwlPlanBtn.classList.add('disabled'); // Disable button
        } else { // Populate CWL info if active
            if(noCwlMessageEl) noCwlMessageEl.style.display = 'none'; // Hide message
            if(cwlActiveInfoEl) cwlActiveInfoEl.style.display = 'block'; // Show active info
            setText(cwlSeasonEl, data.season); // Set season
            setText(cwlGroupStateEl, data.state); // Set group state
            // Populate list of clans in the group
            setHtml(cwlGroupClansEl, data.clans_in_group?.map(c => `<p><img src="${c.badge_url || DEFAULT_BADGE_URL}" alt="Emblema ${c.name}"> <strong>${c.name}</strong> (${c.tag}) Nv ${c.level}</p>`).join('') || '<p>Nenhum clã no grupo.</p>');
            // Populate rounds info
            setHtml(cwlRoundsInfoEl, data.rounds?.map(r => `
                <div class="cwl-round">
                    <h4>Rodada ${r.round_number}</h4>
                    {/* Map wars in the round */}
                    ${r.wars?.map(w => w.error ? `<p class="cwl-war-entry">Guerra: ${w.error}</p>` : `<p class="cwl-war-entry">
                        <strong><img src="${w.clan_badge_url}" class="cwl-war-badge"> ${w.clan_name}</strong> ${w.clan_stars}⭐ vs ${w.opponent_stars}⭐ <strong><img src="${w.opponent_badge_url}" class="cwl-war-badge"> ${w.opponent_name}</strong>
                        <br><small>Estado: ${w.state_description}</small></p>`).join('') || "<p>Nenhuma guerra nesta rodada.</p>"}
                </div>`).join('') || "Nenhuma info de rodada.");
            generateCwlPlanBtn.disabled = false; generateCwlPlanBtn.classList.remove('disabled'); // Enable button
            // Start checking for inactivity periodically
            checkCwlInactivity();
            setInterval(checkCwlInactivity, 60000); // Check every minute
        }
    }

    async function handleGenerateCwlPlan() {
        // Disable button and show spinner
        generateCwlPlanBtn.disabled = true; generateCwlPlanBtn.textContent = 'A gerar...';
        cwlPlanResultEl.style.display = 'block'; // Show result area
        setHtml(cwlPlanContentEl, '<div class="loading-spinner" style="margin: 20px auto;"></div>'); // Show spinner inside

        // Fetch plan data
        const data = await fetchData('cwl/generate_plan', { method: 'POST' });

        // Re-enable button
        generateCwlPlanBtn.disabled = false; generateCwlPlanBtn.textContent = 'Gerar Plano de Rotação';

        // Handle error
        if (data.error) {
            setHtml(cwlPlanContentEl, `<p class="message-box">${data.error}</p>`);
            document.getElementById('cwlPlanDaysTabs').innerHTML = ''; // Clear tabs
        } else { // Populate plan
            // Create day tabs
            const tabsHtml = data.schedule.map((dayPlan, index) =>
                `<button class="cwl-plan-day-tab ${index === 0 ? 'active' : ''}" data-day="${dayPlan.day}">Dia ${dayPlan.day}</button>`
            ).join('');
            document.getElementById('cwlPlanDaysTabs').innerHTML = tabsHtml;

            // Function to render a specific day's plan
            const renderDayPlan = (day) => {
                const dayData = data.schedule.find(d => d.day == day); // Find data for the selected day
                if (!dayData) { // Handle case where day data is missing
                    setHtml(cwlPlanContentEl, `<p class="message-box">Plano para o dia ${day} não encontrado.</p>`);
                    return;
                }
                // Build HTML for substitutions
                let planHtml = `<h4>Alterações na Equipa</h4>`;
                planHtml += dayData.substitutions.length > 0 ? dayData.substitutions.map(sub => `<div class="substitution-card"><p>🔴 <strong>Sai:</strong> ${sub.out.name} (CV${sub.out.town_hall})</p><p>🟢 <strong>Entra:</strong> ${sub.in.name} (CV${sub.in.town_hall})</p><p class="reason"><em>IA: ${sub.reason}</em></p></div>`).join('') : `<p>Manter a escalação do dia anterior.</p>`;
                // Build HTML for active roster
                planHtml += `<h4>⚔️ Escalação Ativa</h4><div class="roster-grid">`;
                planHtml += dayData.active_roster.map((p, i) => `<div class="roster-player"><span>${i+1}.</span>${p.name} (CV${p.town_hall})</div>`).join('');
                planHtml += `</div>`;
                // Set the content
                setHtml(cwlPlanContentEl, planHtml);
            };

            // Render day 1 initially
            renderDayPlan(1);

            // Add click listeners to day tabs
            document.querySelectorAll('.cwl-plan-day-tab').forEach(tab => {
                tab.addEventListener('click', () => {
                    // Deactivate old tab, activate new one, and render plan
                    document.querySelector('.cwl-plan-day-tab.active').classList.remove('active');
                    tab.classList.add('active');
                    renderDayPlan(tab.dataset.day);
                });
            });
        }
    }

    async function checkCwlInactivity() {
        // Fetch inactivity data (implementation depends on backend endpoint)
        // const data = await fetchData('cwl/inactivity_check');
        // Example logic:
        const data = {}; // Placeholder - Replace with actual fetch
        if (data && data.alert) {
            const { inactive_players, time_remaining, best_substitute } = data.alert;
            let alertText = `<strong>${inactive_players.map(p => p.name).join(', ')}</strong> ainda não atacou(aram)! Faltam ${time_remaining} horas.`;
            if (best_substitute) { // Suggest substitute if provided
                alertText += `<br>A IA sugere a substituição imediata por <strong>${best_substitute.name}</strong> para não afetar a próxima rodada.`;
            }
            setHtml(cwlInactivityTextEl, alertText);
            cwlInactivityAlertEl.style.display = 'block'; // Show alert
        } else {
            cwlInactivityAlertEl.style.display = 'none'; // Hide alert if no inactivity
        }
    }


    if (generateCwlPlanBtn) {
        generateCwlPlanBtn.addEventListener('click', handleGenerateCwlPlan);
    }

    function populateWarLog(data) {
        setText(warLogLimitEl, data.log?.length || '0'); // Show number of entries
        // Handle error or no log data
        if (data.error || !data.log?.length) {
            if(noWarLogMessageEl) noWarLogMessageEl.style.display = 'block';
            setText(noWarLogMessageEl, data.error || "Log de guerra indisponível.");
            setHtml(warLogTableBodyEl, `<tr><td colspan="6">${data.error || "Nenhum registo encontrado."}</td></tr>`);
            return;
        }
        // Hide error message and populate table
        if(noWarLogMessageEl) noWarLogMessageEl.style.display = 'none';
        setHtml(warLogTableBodyEl, data.log.map(e => `
            <tr class="historic-war-row" data-war-id="${e.war_id}"> {/* Add war ID for modal */}
                <td>${e.end_time_formatted}</td>
                <td><img src="${e.opponent_badge_url || DEFAULT_BADGE_URL}" alt="Emblema" class="log-opponent-badge">${e.opponent_name || 'N/A'}</td>
                <td>${e.clan_stars}⭐ vs ${e.opponent_stars}⭐</td>
                <td class="war-result-${e.result?.toLowerCase()}">${e.result}</td> {/* Style based on result */}
                <td>${e.team_size}</td>
                <td>${e.is_cwl ? "CWL" : "Normal"}</td>
            </tr>`).join(''));
    }


    async function savePlayerNote(playerTag, text, priority) {
        // Sends note data to the backend API
        await fetchData(`notes/${encodeURIComponent(playerTag)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, priority })
        });
        // No explicit success/error handling here, assuming backend handles it
    }

    function populateMembersList(data) {
        setText(membersClanNameEl, data.clan_name); // Set clan name in header
        // Handle error or no member data
        if (data.error || !data.members) {
            setHtml(membersGridEl, `<p class="message-box">${data.error || "Não foi possível carregar os membros."}</p>`);
            return;
        }

        // Map member data to HTML cards
        setHtml(membersGridEl, data.members.map(m => {
            const watchlistClass = m.isOnWatchlist ? 'on-watchlist' : ''; // Add class if on watchlist
            const watchlistIconHtml = m.isOnWatchlist ? '<span class="watchlist-icon">⚠️</span>' : ''; // Add icon if on watchlist
            // Add tooltip if on watchlist
            const watchlistTooltipHtml = m.isOnWatchlist
                ? `<span class="watchlist-tooltip">
                       <strong>Em Observação!</strong><br>
                       Motivo: ${m.watchlistReason || 'Não especificado'}<br>
                       ${m.watchlistDetails ? `Detalhes: ${m.watchlistDetails}` : ''}
                   </span>`
                : '';

            // Member card HTML structure
            return `
            <div class="member-card ${watchlistClass}" data-th="${m.town_hall}" data-name="${m.name.toLowerCase()}">
                <div class="member-card-header" data-player-tag="${m.tag}"> {/* Store tag for profile modal */}
                    <img src="/static/images/townhall${m.town_hall}.png" alt="CV${m.town_hall}" class="member-th-icon" onerror="this.style.display='none'">
                    <div class="member-info">
                        <h4>${m.name} ${watchlistIconHtml}</h4> {/* Add watchlist icon */}
                        <p>${m.role} • 🏆 ${m.trophies}</p>
                    </div>
                     ${watchlistTooltipHtml} {/* Add watchlist tooltip */}
                </div>
                <div class="member-card-stats">
                    <span>🎁 Doadas: ${m.donations}</span>
                    <span>📥 Recebidas: ${m.received}</span>
                </div>
                <div class="member-card-note">
                    {/* Note editing elements */}
                    <div class="note-container note-priority-${m.note_priority || 'none'}">
                        <span class="note-text">${m.note || 'Clique para editar...'}</span>
                        <input type="text" class="note-input" value="${m.note}" style="display: none;">
                        <div class="priority-selector">
                            {/* Priority buttons */}
                            ${['green', 'yellow', 'red', 'none'].map(prio => `
                                <button class="priority-btn priority-${prio} ${prio === (m.note_priority || 'none') ? 'active' : ''}" data-priority="${prio}">
                                    ${prio === 'green' ? '✓' : prio === 'yellow' ? '!' : prio === 'red' ? '✗' : '×'}
                                </button>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>`;
        }).join('')); // Join all card HTML strings
        attachMemberEventListeners(); // Add event listeners after populating
    }


    function attachMemberEventListeners() {
        // Listener to open profile modal on header click
        document.querySelectorAll('.member-card-header').forEach(header => {
            header.addEventListener('click', () => openMemberProfileModal(header.dataset.playerTag));
        });
        // Listener to switch note display to input on click
        document.querySelectorAll('.note-text').forEach(span => {
            span.addEventListener('click', () => {
                const input = span.nextElementSibling; // Get the input field
                span.style.display = 'none'; // Hide the span
                input.style.display = 'inline-block'; // Show the input
                input.focus(); // Focus the input
            });
        });
        // Listeners for note input blur (lose focus) or Enter key
        document.querySelectorAll('.note-input').forEach(input => {
            const saveChanges = () => { // Function to save changes
                const container = input.closest('.note-container');
                const span = container.querySelector('.note-text');
                const playerTag = input.closest('.member-card').querySelector('.member-card-header').dataset.playerTag;
                const activePriority = container.querySelector('.priority-btn.active')?.dataset.priority || 'none'; // Get current priority
                span.textContent = input.value || 'Clique para editar...'; // Update span text
                input.style.display = 'none'; // Hide input
                span.style.display = 'inline-block'; // Show span
                savePlayerNote(playerTag, input.value, activePriority); // Save note via API
            };
            input.addEventListener('blur', saveChanges); // Save on blur
            input.addEventListener('keypress', e => { if (e.key === 'Enter') input.blur(); }); // Save on Enter
        });
        // Listeners for priority button clicks
        document.querySelectorAll('.priority-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const container = btn.closest('.note-container');
                const playerTag = btn.closest('.member-card').querySelector('.member-card-header').dataset.playerTag;
                const text = container.querySelector('.note-input').value; // Get current note text
                const newPriority = btn.dataset.priority; // Get new priority
                container.className = `note-container note-priority-${newPriority}`; // Update container class for styling
                // Update active button state
                container.querySelectorAll('.priority-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                savePlayerNote(playerTag, text, newPriority); // Save note with new priority
            });
        });
    }

    async function setPlayerCwlStatus(playerTag, status) {
        // Updates player CWL status via API
        const response = await fetchData(`cwl/player_status/${encodeURIComponent(playerTag)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        });
        return !response.error; // Return true on success
    }

    function applyMemberFilters() {
        // Filters member list based on name and TH inputs
        const nameFilter = filterNameInput.value.toLowerCase();
        const thFilter = filterTHInput.value;
        document.querySelectorAll('.member-card').forEach(card => {
            const name = card.dataset.name;
            const th = card.dataset.th;
            // Show card only if name matches and TH matches (or TH filter is empty)
            card.style.display = (name.includes(nameFilter) && (!thFilter || th === thFilter)) ? 'flex' : 'none';
        });
    }

    // Add listeners to filter inputs
    [filterNameInput, filterTHInput].forEach(input => input.addEventListener('keyup', applyMemberFilters));

    async function openMemberProfileModal(playerTag) {
        // Show loading spinner
        setHtml(memberProfileContent, '<div class="loading-spinner" style="margin: 40px auto;"></div><p style="text-align:center;">A carregar perfil do membro...</p>');
        memberProfileModal.style.display = 'block'; // Show modal

        // Fetch profile data
        const profileData = await fetchData(`player_profile/${encodeURIComponent(playerTag)}`);

        // Handle error fetching profile
        if (profileData.error) {
            setHtml(memberProfileContent, `<p class="message-box">${profileData.error}</p>`);
            return;
        }

        // --- Build Profile Modal HTML ---
        // Heroes list
        const heroesHtml = profileData.heroes.map(hero => `
            <div class="hero-item">
                <img src="/static/images/heroes/${hero.name.toLowerCase().replace(/\s+/g, '-')}.png" alt="${hero.name}" onerror="this.style.display='none'">
                <p><strong>${hero.level}</strong> / ${hero.max_level}</p>
            </div>`).join('');
        // League image (if exists)
        const leagueImageHtml = profileData.league_icon
            ? `<div class="profile-league-container"><img src="${profileData.league_icon}" alt="${profileData.league}" class="profile-league-image"></div>`
            : '';
        // CWL Status selector
        const cwlStatusHtml = `
            <div class="member-cwl-status" data-player-tag="${profileData.tag}">
                <label>Status na CWL:</label>
                <div class="cwl-status-selector">
                    <button class="cwl-status-btn ${profileData.cwl_status === 'active' ? 'active' : ''}" data-status="active">Ativo</button>
                    <button class="cwl-status-btn ${profileData.cwl_status === 'backup' ? 'active' : ''}" data-status="backup">Backup</button>
                </div>
            </div>`;
        // Stats grid
        const statsGridHtml = `
            <div class="profile-details-container">
                <div class="profile-stats-grid">
                    <div class="profile-stat-card"><h4>Liga</h4><p>${profileData.league}</p></div>
                    <div class="profile-stat-card"><h4>Troféus</h4><p>🏆 ${profileData.trophies}</p></div>
                    <div class="profile-stat-card"><h4>Doadas</h4><p>🎁 ${profileData.donations}</p></div>
                    <div class="profile-stat-card"><h4>Recebidas</h4><p>📥 ${profileData.received}</p></div>
                </div>
                ${cwlStatusHtml} {/* Include CWL status selector */}
            </div>`;

        // Set the complete modal content
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
                <canvas id="trophyChart"></canvas> {/* Canvas for trophy chart */}
            </div>`);

        // Add listeners to CWL status buttons within the modal
        document.querySelectorAll('#memberProfileContent .cwl-status-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                if (btn.classList.contains('active')) return; // Ignore clicks on active button
                const selector = e.target.closest('.cwl-status-selector');
                const playerTag = e.target.closest('.member-cwl-status').dataset.playerTag;
                const newStatus = e.target.dataset.status;
                // Update button states
                selector.querySelector('.active').classList.remove('active');
                e.target.classList.add('active');
                // Save status via API
                const success = await setPlayerCwlStatus(playerTag, newStatus);
                // Revert UI on error
                if (!success) {
                    alert('Erro ao salvar o status. Tente novamente.');
                    e.target.classList.remove('active'); // Remove active from clicked
                    // Reactivate the previously active button
                    selector.querySelector(`[data-status="${newStatus === 'active' ? 'backup' : 'active'}"]`).classList.add('active');
                }
            });
        });

        // --- Create Trophy Chart ---
        if (memberTrophyChart) memberTrophyChart.destroy(); // Destroy previous chart
        if (profileData.trophy_history?.length > 0) { // If history data exists
            memberTrophyChart = new Chart(document.getElementById('trophyChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: profileData.trophy_history.map(h => h.timestamp), // X-axis labels (dates)
                    datasets: [{
                        label: 'Troféus',
                        data: profileData.trophy_history.map(h => h.trophies), // Y-axis data (trophies)
                        borderColor: 'rgba(54, 162, 235, 1)',
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        fill: true,
                        tension: 0.1 // Smooth line
                    }]
                },
                options: { // Chart options
                    responsive: true, maintainAspectRatio: false,
                    scales: { y: { ticks: { color: 'rgba(255, 255, 255, 0.7)' } }, x: { ticks: { color: 'rgba(255, 255, 255, 0.7)' } } },
                    plugins: { legend: { display: false } } // Hide legend
                }
            });
        }
    }


    async function openHistoricWarModal(warId) {
        // Show loading state
        setHtml(historicWarDetailContent, '<div class="loading-spinner" style="margin: 40px auto;"></div><p style="text-align:center;">A carregar detalhes da guerra...</p>');
        historicWarModal.style.display = 'block'; // Show modal

        // Fetch historic war data
        const historicWarData = await fetchData(`war_history/${encodeURIComponent(warId)}`);

        // Get modal content template
        const template = document.getElementById('historic-war-template');
        if (!template) { // Handle template error
            setHtml(historicWarDetailContent, '<p style="text-align:center; color: red;">Erro: Template do modal não encontrado.</p>');
            return;
        }

        // Clone template and inject into modal
        const warDetailsContent = template.content.cloneNode(true);
        historicWarDetailContent.innerHTML = ''; // Clear loading state
        historicWarDetailContent.appendChild(warDetailsContent);

        // Add event listeners to tabs within the newly added content
        historicWarDetailContent.querySelectorAll('.war-tab-button').forEach(button => {
            button.addEventListener('click', () => {
                const modalContentEl = button.closest('.modal-content'); // Find parent modal
                // Deactivate all tabs, activate clicked one
                modalContentEl.querySelectorAll('.war-tab-button').forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                const tabId = `historic-${button.dataset.tab}`; // Construct content ID
                // Show/hide content based on clicked tab
                modalContentEl.querySelectorAll('.war-tab-content').forEach(content => {
                    content.style.display = content.id === tabId ? 'block' : 'none';
                });
            });
        });

        // Populate the modal content with fetched data
        populateWarDetails(historicWarData, 'historicWarDetailContent', true);
    }

    // Add click listeners to main page war tabs
    warTabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const parentSection = button.closest('.content-section'); // Find parent section
            if (!parentSection) return;
            // Deactivate all tabs in section, activate clicked one
            parentSection.querySelectorAll('.war-tab-button').forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            const tabId = button.dataset.tab; // Get target content ID
            // Show/hide content based on clicked tab
            parentSection.querySelectorAll('.war-tab-content').forEach(content => {
                content.style.display = content.id === tabId ? 'block' : 'none';
            });
        });
    });

    // --- CARREGAMENTO INICIAL E PERIÓDICO ---
    async function loadAllData() {
        try {
            // Fetch bot status (includes maintenance mode) first
            const statusData = await fetch('/api/status').then(res => res.json());
             if (statusData.maintenance_mode) {
                 // The main painel_handler on the backend should redirect to maintenance.html,
                 // but log a message here just in case.
                 console.log("Bot em modo manutenção, painel pode ter dados limitados ou redirecionar.");
             }

            // Fetch clan data first to update header early
            const clanData = await fetchData('clan');
             populateClanInfo(clanData); // Populate header early

            // If initial clan fetch fails, hide loading and stop (prevents errors)
            if (clanData.error && isFirstLoad) {
                loadingOverlayEl.classList.add('hidden');
                return;
            }

            // Fetch remaining data in parallel using Promise.all
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

            // Populate the rest of the sections with fetched data
            populateMembersList(membersData);
            populateWarDetails(currentWarDetailsData, 'war-details-nav', false); // Populate main war section
            populateWarAdvisorPlan(warAdvisorData);
            populateMissedAttacksHistory(missedAttacksData);
            populateWarLog(warLogData);
            populateCwlInfo(cwlInfoData);
            populateHighlights(highlightsData); // Highlights uses clanData which is already populated

            updateLastUpdated(); // Update timestamp
        } catch (error) {
            console.error("Erro geral ao carregar todos os dados:", error);
        } finally {
            // Hide loading overlay after first load attempt (success or fail)
            if (isFirstLoad) {
                setTimeout(() => { loadingOverlayEl.classList.add('hidden'); }, 500); // Small delay for smoother transition
                isFirstLoad = false;
            }
        }
    }

    // --- EVENT LISTENERS DOS MODAIS ---
    // Close historic war modal
    if (closeModalButton) closeModalButton.addEventListener('click', () => historicWarModal.style.display = 'none');
    // Close member profile modal and refresh member list
    if (closeProfileModalButton) closeProfileModalButton.addEventListener('click', () => {
        memberProfileModal.style.display = 'none';
        fetchData('members').then(populateMembersList); // Refresh member list after closing profile
    });
    // Close modals on clicking outside the content
    window.addEventListener('click', (event) => {
        if (event.target == historicWarModal) historicWarModal.style.display = 'none';
        if (event.target == memberProfileModal) {
            memberProfileModal.style.display = 'none';
            fetchData('members').then(populateMembersList); // Refresh member list
        }
    });
    // Open historic war modal on table row click
    warLogTableBodyEl.addEventListener('click', (event) => {
        const row = event.target.closest('.historic-war-row');
        if (row && row.dataset.warId) {
             openHistoricWarModal(row.dataset.warId); // Call function to open modal with war ID
        }
    });


    // --- Inicialização ---
    loadAllData(); // Load data on initial page load
    setInterval(loadAllData, 45000); // Refresh data every 45 seconds

    // --- VERIFICAÇÃO DE MANUTENÇÃO DA API ---
    async function checkApiMaintenance() {
        try {
            // Fetch API status, ensuring no browser cache is used
            const response = await fetch(`${API_BASE_URL}/api/coc_status`, { cache: 'no-store' });
            if (!response.ok) { // Handle server error
                console.error('Falha ao buscar status da API, servidor pode estar offline.');
                return;
            }
            const data = await response.json();
            // If API is in maintenance, redirect to maintenance page
            if (data.status === 'maintenance') {
                console.warn('API em manutenção. Redirecionando...');
                window.location.href = '/static/maintenance.html';
            }
        } catch (error) { // Handle network error
            console.error('Erro ao verificar status de manutenção:', error);
        }
    }
    checkApiMaintenance(); // Check immediately on load
    setInterval(checkApiMaintenance, 20000); // Check every 20 seconds
});

