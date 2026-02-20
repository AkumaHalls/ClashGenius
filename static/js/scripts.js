document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = '';
    const DEFAULT_BADGE_URL = '/static/images/default_badge.png';
    let phaseTimerInterval = null; // Variável para controlar o timer

    // --- ELEMENTOS DO DOM ---
    const loadingOverlayEl = document.getElementById('loading-overlay');
    const loadingStatusTextEl = loadingOverlayEl?.querySelector('p'); // Add null check
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
    const clanCapitalDistrictsEl = document.getElementById('clanCapitalDistricts'); // Keep reference if needed elsewhere

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
    const statsOurAvgDurationEl = document.getElementById('statsOurAvgDuration'); // Keep reference if needed elsewhere
    const statsOpponentAvgStarsEl = document.getElementById('statsOpponentAvgStars');
    const statsOpponentAvgDurationEl = document.getElementById('statsOpponentAvgDuration'); // Keep reference if needed elsewhere
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

    const cwlStatusTextEl = document.getElementById('cwlStatusText'); // <-- Elemento que estava travado
    const cwlActiveInfoEl = document.getElementById('cwlActiveInfo');
    const cwlSeasonEl = document.getElementById('cwlSeason');
    const cwlGroupStateEl = document.getElementById('cwlGroupState');
    const cwlGroupClansEl = document.getElementById('cwlGroupClans');
    const cwlRoundsInfoEl = document.getElementById('cwlRoundsInfo');
    const noCwlMessageEl = document.getElementById('noCwlMessage');

    // --- NOVOS ELEMENTOS DO "CÉREBRO CWL" ---
    const cwlPlannerSectionEl = document.getElementById('cwlPlannerSection');
    const cwlPlanResultEl = document.getElementById('cwlPlanResult');
    const cwlPlanContentEl = document.getElementById('cwlPlanContent');
    const cwlInactivityAlertEl = document.getElementById('cwlInactivityAlert');
    const cwlInactivityTextEl = document.getElementById('cwlInactivityText');
    const cwlOverviewContainerEl = document.getElementById('cwlOverviewContainer'); // Visão Geral (Placar/Banco)
    const cwlPlanDaysTabsEl = document.getElementById('cwlPlanDaysTabs'); // Abas 7 dias
    const cwlPlanWarningEl = document.getElementById('cwlPlanWarning'); // Aviso IA
    // Botão de gerar plano foi removido do HTML, esta referência não é mais necessária
    // const generateCwlPlanBtn = document.getElementById('generateCwlPlanBtn'); 

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
    let userIsAdmin = false; // <<< ADICIONADO para controle de acesso

    const historicWarModal = document.getElementById('historicWarModal');
    const historicWarDetailContent = document.getElementById('historicWarDetailContent');
    const closeModalButton = historicWarModal?.querySelector('.close-button'); // Add null check

    const memberProfileModal = document.getElementById('memberProfileModal');
    const memberProfileContent = document.getElementById('memberProfileContent');
    const closeProfileModalButton = memberProfileModal?.querySelector('.close-button'); // Add null check
    let memberTrophyChart = null;

    // --- FUNÇÃO DE FETCH MELHORADA ---
    async function fetchData(endpoint, options = {}) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/${endpoint}`, options);

            // Handle non-OK responses first
            if (!response.ok) {
                // *** CORREÇÃO HTTP 405: Adiciona log específico ***
                if (response.status === 405) {
                    console.error(`Erro 405 (Método Não Permitido) para ${endpoint}. O JS usou ${options.method || 'GET'}?`);
                }
                const errorData = await response.json().catch(() => ({ error: `Erro HTTP ${response.status}` }));
                const errorMessage = errorData.error || errorData.message || `Falha ao carregar ${endpoint}.`;

                if (response.status === 503) {
                    console.warn(`API retornou 503 (Serviço Indisponível/Iniciando) para ${endpoint}.`);
                    // Update loading text only if overlay is visible
                    if (loadingOverlayEl && !loadingOverlayEl.classList.contains('hidden')) {
                            setText(loadingStatusTextEl, 'Aguardando API CoC ficar pronta...');
                    }
                } else {
                    console.error(`Erro na API! Status: ${response.status} para ${endpoint}`, errorData);
                }
                // Always return an object with an error key for consistency
                return { error: errorMessage };
            }

            // Handle successful No Content response
            if (response.status === 204) {
                return { success: true };
            }

            // Handle successful responses with content
            return await response.json();

        } catch (error) {
            console.error(`Erro de conexão ao buscar ${endpoint}:`, error);
            // Update loading text only if overlay is visible
            if (loadingStatusTextEl && loadingOverlayEl && !loadingOverlayEl.classList.contains('hidden')) {
                setText(loadingStatusTextEl, 'Erro de conexão. Verifique a consola.');
            }
            // Return an object with an error key
            return { error: `Erro de conexão ao buscar ${endpoint}.` };
        }
    }


    // --- LÓGICA DA MÚSICA DE FUNDO ---
    if (backgroundMusicEl && muteButtonEl) {
        backgroundMusicEl.volume = 0.2;
        let musicStarted = false; // Flag to ensure play is attempted only once via interaction

        const playMusic = async () => {
            if (musicStarted) return; // Don't try again if already started or blocked
            try {
                await backgroundMusicEl.play();
                musicStarted = true; // Set flag on successful play
                // Remove listener after first successful interaction play
                document.body.removeEventListener('click', playMusic);
                document.body.removeEventListener('keydown', playMusic);
            } catch (err) {
                musicStarted = true; // Set flag even if blocked, to prevent retries
                console.log('Autoplay da música bloqueado pelo navegador.');
                // Keep listeners if initially blocked, maybe next interaction works
            }
        };
        // Attempt play on first click or keydown
        document.body.addEventListener('click', playMusic, { once: true });
        document.body.addEventListener('keydown', playMusic, { once: true });


        muteButtonEl.addEventListener('click', () => {
            backgroundMusicEl.muted = !backgroundMusicEl.muted;
            muteButtonEl.textContent = backgroundMusicEl.muted ? '🔇' : '🔊';
            localStorage.setItem('musicMuted', backgroundMusicEl.muted.toString()); // Save preference
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
        if (element) {
            // Ensure text is a string, handle null/undefined explicitly
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
                // Add error handler for badges
                element.onerror = () => { element.src = DEFAULT_BADGE_URL; };
        }
    }

    // --- NAVEGAÇÃO E ANIMAÇÃO DAS SEÇÕES ---
    const initialSectionId = navLinks.length > 0 ? navLinks[0].dataset.section : 'clan-info-nav';
    let currentActiveSectionId = localStorage.getItem('activeSection') || initialSectionId;

    // Set initial active section and link
    contentSections.forEach(section => {
        section?.classList.toggle('active-section', section.id === currentActiveSectionId); // Add null check
    });
    navLinks.forEach(link => {
        link?.classList.toggle('active-nav-link', link.dataset.section === currentActiveSectionId); // Add null check
    });

    function setActiveSection(newSectionId) {
        if (!newSectionId || newSectionId === currentActiveSectionId) return; // Do nothing if invalid or already active

        const oldSectionEl = document.getElementById(currentActiveSectionId);
        const newSectionEl = document.getElementById(newSectionId);

        if (!newSectionEl) {
            console.warn(`Section with ID "${newSectionId}" not found.`);
            return; // Exit if the new section doesn't exist
        }

        // Remove active class from old section and link
        oldSectionEl?.classList.remove('active-section'); // Add null check
        navLinks.forEach(link => link?.classList.remove('active-nav-link')); // Add null check

        // Add active class to new section and link
        newSectionEl.classList.add('active-section');
        const newLink = document.querySelector(`.nav-link[data-section="${newSectionId}"]`);
        newLink?.classList.add('active-nav-link'); // Add null check

        // Store the new active section and update the new ID
        localStorage.setItem('activeSection', newSectionId);
        currentActiveSectionId = newSectionId;
    }

    // Add click listeners to navigation links
    navLinks.forEach((link) => {
        link?.addEventListener('click', (e) => { // Add null check
            e.preventDefault(); // Prevent default anchor behavior
            setActiveSection(link.dataset.section);
        });
    });

    // --- FUNÇÕES DE POPULAÇÃO DE DADOS ---
    function populateClanInfo(data) {
        // (Código mantido igual, verificações já existentes)
        if (!data || data.error || !data.name) {
            setText(clanNameHeaderEl, "Erro");
            setText(clanNameEl, data?.error || "N/A"); // Add null check for data
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
        setText(clanWarWinsEl, `${data.war_wins?.toLocaleString() || '-'} ⚔️`); // Add toLocaleString
        setText(clanPointsEl, `${data.points?.toLocaleString() || '-'} 🏆`); // Add toLocaleString
        setText(clanCapitalPointsEl, `${data.capital_points?.toLocaleString() || '-'} 🏆`); // Add toLocaleString
        setText(clanCapitalLeagueEl, data.capital_league);
        setText(clanDescriptionEl, data.description, 'Sem descrição.');
        setText(botVersionEl, data.version, '?');
    }

    function populateHighlights(data) {
        const highlightsContentEl = document.getElementById('highlightsContent'); // Get content wrapper

        // Handle error case first
        if (!data || data.error || !data.clan_name) {
            if (noHighlightsMessageEl) {
                noHighlightsMessageEl.style.display = 'block';
                setText(noHighlightsMessageEl, data?.error || "Não foi possível carregar os destaques.");
            }
            if(highlightsContentEl) highlightsContentEl.style.display = 'none'; // Hide content area
            console.error("Erro ao carregar destaques ou dados ausentes:", data?.error || "Dados ausentes"); // Log do erro
            return;
        }

        // Show content area and hide error message
        if (noHighlightsMessageEl) noHighlightsMessageEl.style.display = 'none';
        if (highlightsContentEl) highlightsContentEl.style.display = 'block';

        setText(highlightsClanNameEl, data.clan_name);
        setText(warDateHighlightEl, data.war_date ? `(${data.war_date})` : ''); // Show war date if available

        // Populate Top Donors
        setHtml(topDonorsListEl, data.top_donors?.length > 0 ? data.top_donors.map((donor, index) => {
            const medals = ['gold', 'silver', 'bronze'];
            const medal_icons = ['🥇', '🥈', '🥉'];
            const rankIcon = medal_icons[index] || `${index + 1}.`; // Use number if beyond top 3
            return `<div class="podium-item ${medals[index] || ''}">
                        <span class="podium-rank">${rankIcon}</span>
                        <div class="podium-details">
                            <div class="member-name">${donor.name || 'N/A'} (CV${donor.town_hall || '?'})</div>
                            <div class="donation-count"><strong>${(donor.donations || 0).toLocaleString()}</strong> tropas doadas</div>
                        </div>
                    </div>`;
        }).join('') : '<p>Nenhum doador encontrado.</p>');

        // Populate War Heroes/Best Attacks
        const warHeroTitleEl = document.getElementById('warHeroTitle');
        setText(warHeroTitleEl, '⚔️ Heróis da Última Guerra'); // Title for the section
        setHtml(bestAttacksListEl, data.war_heroes?.length > 0 ? data.war_heroes.map(hero => {
            const isMvp = hero.rank === 1;
            const heroClass = isMvp ? 'mvp-card' : 'attack-item';
            const medals = ['🥇', '🥈', '🥉'];
            const rankIcon = medals[hero.rank - 1] || `${hero.rank}.`; // Use number if beyond top 3

            const titleHtml = isMvp
                ? `<p class="mvp-title">Jogador Mais Valioso (MVP)</p><h4 class="mvp-name">${hero.name || 'N/A'} <span>(CV${hero.town_hall || '?'})</span></h4>`
                : `<div class="attack-header">${rankIcon} ${hero.name || 'N/A'} (CV${hero.town_hall || '?'})</div>`;

            // Add tooltip with the reason
            return `<div class="${heroClass}">
                        ${titleHtml}
                        <span class="tooltip-text">${hero.reason || 'Sem detalhes'}</span>
                    </div>`;
        }).join('') : '<p>Nenhum herói para destacar na última guerra ou análise indisponível.</p>'); // More informative default

        // --- CHART LOGIC ---
        // Destroy previous chart instance if exists
        if (activityChart) {
            try {
                activityChart.destroy();
                activityChart = null; // Ensure variable is reset
                 console.log("Gráfico anterior destruído.");
            } catch(e) {
                 console.error("Erro ao destruir gráfico anterior:", e);
            }
        }

        // Create new Activity Chart if data is available
        const chartData = data.activity_chart_data;
        if (activityChartCanvas && chartData && chartData.labels && chartData.labels.length > 0 && chartData.donations && chartData.received) {
            console.log("Tentando criar gráfico com dados:", chartData); // Log dos dados
            try {
                const ctx = activityChartCanvas.getContext('2d');
                if (!ctx) throw new Error("Não foi possível obter o contexto 2D do canvas."); // Verifica se o contexto foi obtido

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
                console.log("Gráfico de atividade criado com sucesso.");
            } catch (e) {
                console.error("Erro detalhado ao criar gráfico de atividade:", e);
                // Optionally display an error message in the chart area
                if (activityChartCanvas) {
                    const ctx = activityChartCanvas.getContext('2d');
                    if (ctx) {
                        ctx.clearRect(0, 0, activityChartCanvas.width, activityChartCanvas.height);
                        ctx.fillStyle = 'rgba(255, 100, 100, 0.8)'; // Cor de erro
                        ctx.textAlign = 'center';
                        ctx.font = '14px Open Sans';
                        ctx.fillText('Erro ao renderizar o gráfico.', activityChartCanvas.width / 2, activityChartCanvas.height / 2);
                         console.error("Canvas context was available, but chart creation failed.");
                    } else {
                         console.error("Falha ao obter contexto 2D para mensagem de erro no canvas.");
                    }
                }
            }
        } else if (activityChartCanvas) {
            console.warn("Dados de atividade insuficientes ou canvas não encontrado. Limpando área do gráfico.");
            // Clear canvas or show message if no data or canvas error
            try {
                const ctx = activityChartCanvas.getContext('2d');
                if (ctx) {
                    ctx.clearRect(0, 0, activityChartCanvas.width, activityChartCanvas.height);
                    ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
                    ctx.textAlign = 'center';
                    ctx.font = '14px Open Sans';
                    ctx.fillText('Dados de atividade indisponíveis para o gráfico.', activityChartCanvas.width / 2, activityChartCanvas.height / 2);
                } else {
                     console.error("Não foi possível obter contexto 2D para limpar/mostrar mensagem no canvas.");
                }
            } catch(e) {
                 console.error("Erro ao tentar limpar ou exibir mensagem no canvas:", e);
            }
        } else {
             console.error("Elemento canvas 'activityChart' não encontrado no DOM.");
        }
    }


    function createStarString(stars) {
        const starCount = parseInt(stars, 10); // Ensure it's a number
        if (isNaN(starCount) || starCount < 0) return '⚫⚫⚫'; // Default empty
        return '⭐'.repeat(starCount) + '⚫'.repeat(Math.max(0, 3 - starCount));
    }

    function populateWarDetails(data, containerId = 'war-details-nav', isModal = false) {
        // (Código mantido igual, verificações já existentes)
        const container = document.getElementById(containerId);
        if (!container) return; // Exit if container not found

        const prefix = isModal ? 'historic-' : ''; // Prefix for element IDs in modal
        const warHeader = container.querySelector('.war-header');
        const warTabsNav = container.querySelector('.war-tabs');
        const noWarMsg = container.querySelector(isModal ? `#${prefix}noWarDetailMessage` : '#noWarDetailMessage');
        const predictionSection = container.querySelector(isModal ? null : '#warPredictionSection');

        // Handle error or no war data
        if (!data || data.error || !data.war_data) {
            if (noWarMsg) { noWarMsg.style.display = 'block'; setText(noWarMsg, data?.error || "Nenhuma guerra para detalhar."); }
            if (warHeader) warHeader.style.display = 'none';
            if (warTabsNav) warTabsNav.style.display = 'none';
            container.querySelectorAll('.war-tab-content').forEach(tab => tab.style.display = 'none'); // Hide all tabs
            if (predictionSection) predictionSection.style.display = 'none'; // Hide prediction
            return;
        }
        // --- Populate War Prediction (only on main page) ---
        // (Código mantido igual)
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
        // (Código mantido igual)
        setText(query(`#${prefix}statsOurClanName`), war.clan_name);
        setText(query(`#${prefix}statsOurStars`), war.clan_stars);
        setText(query(`#${prefix}statsOurDestruction`), war.clan_destruction?.replace('%', ''));
        setText(query(`#${prefix}statsOurAttacksUsed`), `${war.clan_attacks_used}/${war.team_size * war.attacks_per_member}`);
        setText(query(`#${prefix}statsOpponentName`), war.opponent_name);
        setText(query(`#${prefix}statsOpponentStars`), war.opponent_stars);
        setText(query(`#${prefix}statsOpponentDestruction`), war.opponent_destruction?.replace('%', ''));
        setText(query(`#${prefix}statsOpponentAttacksUsed`), `${war.opponent_attacks_used}/${war.team_size * war.attacks_per_member}`);
        setText(query(`#${prefix}statsOurAvgStars`), war.clan_avg_stars);
        setText(query(`#${prefix}statsOurAvgDuration`), war.clan_avg_stars); // Keep reference if needed elsewhere
        setText(query(`#${prefix}statsOpponentAvgStars`), war.opponent_avg_stars);
        if(war.clan_star_distribution){
                for(let i=0; i<=3; i++) setText(query(`#${prefix}statsOurStars${i}`), war.clan_star_distribution[i]);
        }
        if(war.opponent_star_distribution){
                for(let i=0; i<=3; i++) setText(query(`#${prefix}statsOpponentStars${i}`), war.opponent_star_distribution[i]);
        }

        // --- Populate Events Tab ---
        // (Código mantido igual)
        const eventsTableBody = query(`#${prefix}warEventsTableBody`);
        setText(query(`#${prefix}warTotalAttacksCount`), data.all_attacks?.length || 0); // Add null check
        setHtml(eventsTableBody, data.all_attacks?.length > 0 ? data.all_attacks.map(att => `
            <tr>
                <td>${att.order ?? '-'}</td>
                <td>${att.attacker_name || '?'} (CV${att.attacker_townhall || '?'})</td>
                <td><span class="attack-stars">${createStarString(att.stars)}</span> ${att.destruction ?? 0}%</td>
                <td>${att.defender_name || '?'} (CV${att.defender_townhall || '?'})</td>
                <td>${att.duration ?? '-'}</td>
            </tr>
        `).join('') : '<tr><td colspan="5">Nenhum ataque registado.</td></tr>');

        // --- Populate Team Tabs ---
        // (Código mantido igual)
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

        // --- Activate Default Tab ---
        // (Código mantido igual)
        const currentActiveTab = query('.war-tab-button.active');
        if (!currentActiveTab || !currentActiveTab.closest(`#${containerId}`)) { // Activate first tab if none is active within the container
            const firstTabButton = query('.war-tab-button');
            const firstTabContentId = isModal ? `#historic-${firstTabButton?.dataset.tab}` : `#${firstTabButton?.dataset.tab}`;
            const firstTabContent = query(firstTabContentId);
            // Deactivate others first
            container.querySelectorAll('.war-tab-button').forEach(btn => btn.classList.remove('active'));
            container.querySelectorAll('.war-tab-content').forEach(cont => cont.style.display = 'none');
            // Activate first
            firstTabButton?.classList.add('active');
            if(firstTabContent) firstTabContent.style.display = 'block';
        }
    }


    function populateWarAdvisorPlan(data) {
        // (Código mantido igual)
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
                            <span>Confiança</span> {/* Simplified label */}
                            <div class="confidence-bar-container"><div class="confidence-bar ${confidenceColor}" style="width: ${confidencePercent}%;"></div></div>
                            <span>${confidencePercent}%</span>
                        </div>
                    </div>`;
            }).join('') : '<p class="message-box">Nenhuma recomendação específica gerada.</p>'; // Message if no recommendations
            contentHtml += '</div>';
            setHtml(warAdvisorContentEl, contentHtml);

            const timerEl = warAdvisorContentEl.querySelector('#advisorPhaseTimer');
            const timerTextEl = warAdvisorContentEl.querySelector('#advisorPhaseTimerText');
            if (planData.phase_2_start_time_iso && timerEl && timerTextEl) {
                const phase2StartTime = new Date(planData.phase_2_start_time_iso);
                timerEl.style.display = 'block';
                const updateTimer = () => { // Function to update timer text
                    const now = new Date(); const diff = phase2StartTime - now;
                    if (diff <= 0) {
                        setText(timerTextEl, 'Fase 2 Iniciada! Foco em limpeza.');
                        if(phaseTimerInterval) clearInterval(phaseTimerInterval); phaseTimerInterval = null;
                        return;
                    }
                    const hours = Math.floor(diff / 36e5); const minutes = Math.floor((diff % 36e5) / 6e4); const seconds = Math.floor((diff % 6e4) / 1000);
                    setText(timerTextEl, `${hours}h ${minutes}m ${seconds}s`);
                };
                updateTimer(); // Initial call
                phaseTimerInterval = setInterval(updateTimer, 1000); // Update every second
            } else if (timerEl) {
                timerEl.style.display = 'none';
            }
        };
        setupAdvisorUI(data);
    }


    function populateMissedAttacksHistory(data) {
        // Check if title element exists before setting text
        if(attacksRemainingTitleEl?.querySelector('span')) setText(attacksRemainingTitleEl.querySelector('span'), data?.clan_name || 'Clã');

        if (!data || data.error || !data.wars_with_missed_attacks?.length) {
            setHtml(missedAttacksContainerEl, ''); // Clear container
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

        // Re-attach listeners to copy buttons
        document.querySelectorAll('.copy-tag-btn').forEach(button => {
            button.addEventListener('click', () => copyTagToClipboard(button));
        });
    }


    function copyTagToClipboard(button) {
        // (Código mantido igual)
        const tag = button.dataset.tag;
        const textArea = document.createElement("textarea");
        textArea.value = tag;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            // Use execCommand as fallback
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

    // ##### INÍCIO DAS NOVAS FUNÇÕES DO "CÉREBRO CWL" (CORRIGIDAS) #####

    /**
     * Preenche os quadros de "Visão Geral" (Placar de Participação e Banco de Reservas).
     */
    function populateCwlOverview(planData) {
        if (!cwlOverviewContainerEl) return;

        // --- CORREÇÃO: Tratamento de erro para evitar spinner infinito ---
        if (!planData || !planData.participation_score) {
            setHtml(cwlOverviewContainerEl, `<div class="cwl-overview-card" style="grid-column: 1 / -1;"><p>Dados de participação indisponíveis.</p></div>`);
            cwlOverviewContainerEl.style.gridTemplateColumns = '1fr';
            return;
        }

        const score = planData.participation_score || [];
        
        let placarHtml = '<h4>📊 Placar de Participação (Final)</h4>'; // Renomeia para "Final"
        placarHtml += '<div class="cwl-overview-list-bench">'; // Reutiliza a classe de lista
        
        if (score.length > 0) {
             // Ordena por dias jogados
             score.sort((a, b) => b.days_played - a.days_played);

             placarHtml += score.map(p => 
                // Mostra o placar final
                `<p>${p.player.name} (CV${p.player.town_hall}): <strong>${p.days_played} / 7 dias</strong></p>`
             ).join('');
        } else {
            placarHtml += '<p>Nenhum jogador "Ativo" encontrado.</p>';
        }
        placarHtml += '</div>';

        // Remove o grid de 2 colunas e o bancoHtml
        setHtml(cwlOverviewContainerEl, `
            <div class="cwl-overview-card" style="grid-column: 1 / -1;">${placarHtml}</div>
        `);
        
        // Aplica o CSS de 1 coluna
        cwlOverviewContainerEl.style.gridTemplateColumns = '1fr';
    }

    /**
     * Preenche as abas dos 7 dias e o conteúdo do dia selecionado.
     */
    function populateCwlSchedule(planData) {
        if (!cwlPlanDaysTabsEl || !cwlPlanContentEl) return;

        const schedule = planData.schedule || [];
        const currentDay = planData.current_day || 1;

        // 1. Gera as Abas dos 7 Dias
        const tabsHtml = schedule.map(dayPlan => {
            const day = dayPlan.day;
            const isActive = day === currentDay;
            return `<button class="cwl-plan-day-tab ${isActive ? 'active' : ''}" data-day="${day}">Dia ${day}</button>`;
        }).join('');
        setHtml(cwlPlanDaysTabsEl, tabsHtml);

        // 2. Função para Renderizar o Conteúdo de um Dia
        const renderDayPlan = (day) => {
            const dayData = schedule.find(d => d.day == day);
            if (!dayData) {
                setHtml(cwlPlanContentEl, `<p class="message-box">Plano para o dia ${day} não encontrado.</p>`);
                return;
            }

            // --- Substituições (Código existente) ---
            let planHtml = `<h4>Alterações na Equipa</h4>`;
            planHtml += dayData.substitutions?.length > 0
                ? dayData.substitutions.map(sub => `
                    <div class="substitution-card">
                        <p>🔴 <strong>Sai:</strong> ${sub.out?.name || '?'} (CV${sub.out?.town_hall || '?'})</p>
                        <p>🟢 <strong>Entra:</strong> ${sub.in?.name || '?'} (CV${sub.in?.town_hall || '?'})</p>
                        <p class="reason"><em>IA: ${sub.reason || '-'}</em></p>
                    </div>`).join('')
                : `<p>${day == 1 ? 'Escalação inicial.' : 'Manter a escalação do dia anterior.'}</p>`;

            // --- Escalação Ativa (Código existente) ---
            const roster = dayData.active_roster || [];
            planHtml += `<h4>⚔️ Escalação Ativa (Dia ${day}) - ${roster.length}v${roster.length}</h4><div class="roster-grid">`;
            
            // Ordena a escalação por CV (mais forte primeiro) para exibição
            const sortedRoster = [...roster].sort((a, b) => b.player.town_hall - a.player.town_hall);

            planHtml += sortedRoster.length > 0
                ? sortedRoster.map((p, i) => `
                    <div class="roster-player">
                        <span>${i + 1}.</span>${p.player.name || '?'} (CV${p.player.town_hall || '?'}) - ${p.days_played}d
                    </div>`).join('')
                : '<p>Nenhum jogador na escalação.</p>';
            planHtml += `</div>`; // Fim do .roster-grid
            
            // --- INÍCIO DA CORREÇÃO: Adiciona o Banco de Reservas do dia ---
            const activeBench = dayData.active_bench || [];
            const backupBench = dayData.backup_bench || [];

            planHtml += `<h4 style="margin-top: 20px;"><span class="ai-indicator"></span>Banco de Reservas (Dia ${day})</h4>`;
            planHtml += '<div class="cwl-overview-card" style="background-color: rgba(0,0,0,0.1);">'; // Reutiliza o estilo
            planHtml += '<div class="cwl-overview-list-bench">'; // Reutiliza o estilo

            if (activeBench.length > 0) {
                planHtml += '<h5>Ativos (Próximos a entrar):</h5>';
                planHtml += activeBench
                    .sort((a, b) => a.days_played - b.days_played) // Ordena por dias jogados
                    .map((p, i) => `<p>${i+1}. ${p.player.name} (CV${p.player.town_hall}) - ${p.days_played}d</p>`)
                    .join('');
            }
            if (backupBench.length > 0) {
                planHtml += '<h5 style="margin-top: 10px;">Backups (Emergência):</h5>';
                planHtml += backupBench
                    .sort((a, b) => a.days_played - b.days_played) // Ordena por dias jogados
                    .map((p, i) => `<p>${i+1}. ${p.player.name} (CV${p.player.town_hall}) - ${p.days_played}d</p>`)
                    .join('');
            }
            if (activeBench.length === 0 && backupBench.length === 0) {
                 planHtml += '<p>Nenhum jogador no banco para este dia.</p>';
            }
            planHtml += '</div></div>';
            // --- FIM DA CORREÇÃO ---
            
            setHtml(cwlPlanContentEl, planHtml);
        };

        // 3. Renderiza o dia atual (ou dia 1 se a CWL tiver terminado)
        renderDayPlan(currentDay <= 7 ? currentDay : 1);

        // 4. Adiciona Listeners às Abas
        cwlPlanDaysTabsEl.querySelectorAll('.cwl-plan-day-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                cwlPlanDaysTabsEl.querySelector('.cwl-plan-day-tab.active')?.classList.remove('active');
                tab.classList.add('active');
                renderDayPlan(tab.dataset.day);
            });
        });
    }

    /**
     * Função principal que é chamada pela API para preencher toda a seção CWL.
     */
    async function populateCwlData(data) {
        // --- CORREÇÃO: Tratamento de erro para evitar spinner infinito ---
        if (!cwlPlannerSectionEl) return;

        // 1. Trata erros ou CWL inativa
        if (!data || data.error || data.status === "NotInCwl") {
            if (noCwlMessageEl) {
                noCwlMessageEl.style.display = 'block';
                // *** CORREÇÃO HTTP 405: Mostra o erro da API se existir ***
                setText(noCwlMessageEl, data?.error || data?.message || "O clã não está em CWL no momento.");
            }
            // Garante que o container principal esteja visível para mostrar a mensagem de erro
            cwlPlannerSectionEl.style.display = 'block'; 
            
            if (cwlActiveInfoEl) cwlActiveInfoEl.style.display = 'none';
            if (cwlPlanResultEl) cwlPlanResultEl.style.display = 'none'; // Esconde a área do plano (onde fica o spinner)
            
            // <<< CORREÇÃO BUG "Carregando..." >>>
            setText(cwlStatusTextEl, "Não está em CWL");
            // <<< FIM CORREÇÃO >>>
            return;
        }

        // 2. Se a CWL está ativa, esconde a mensagem de "não está em cwl"
        if (noCwlMessageEl) noCwlMessageEl.style.display = 'none';
        if (cwlPlanResultEl) cwlPlanResultEl.style.display = 'block'; // Mostra a área do plano

        // <<< CORREÇÃO BUG "Carregando..." >>>
        if (data.current_day >= 8) {
            setText(cwlStatusTextEl, "Finalizada");
        } else if (data.current_day >= 1) {
            setText(cwlStatusTextEl, `Em Guerra (Dia ${data.current_day})`);
        } else {
            setText(cwlStatusTextEl, "Em Preparação"); // Fallback
        }
        // <<< FIM CORREÇÃO >>>

        // 3. Preenche o aviso da IA, se houver
        if (data.warning) {
            setHtml(cwlPlanWarningEl, `<strong>Aviso da IA:</strong> ${data.warning}`);
            cwlPlanWarningEl.style.display = 'block';
        } else if (cwlPlanWarningEl) {
            cwlPlanWarningEl.style.display = 'none';
        }

        // 4. Preenche os novos quadros da "Visão Geral"
        populateCwlOverview(data);

        // 5. Preenche as abas e o conteúdo dos 7 dias
        populateCwlSchedule(data);
    }

    // ##### FIM DAS NOVAS FUNÇÕES DO "CÉREBRO CWL" #####



    function populateWarLog(data) {
        setText(warLogLimitEl, data?.log?.length || '0');

        if (!data || data.error || !data.log?.length) {
            if(noWarLogMessageEl) { noWarLogMessageEl.style.display = 'block'; setText(noWarLogMessageEl, data?.error || "Log de guerra indisponível."); }
            setHtml(warLogTableBodyEl, `<tr><td colspan="6">${data?.error || "Nenhum registo encontrado."}</td></tr>`);
            return;
        }

        if(noWarLogMessageEl) noWarLogMessageEl.style.display = 'none';
        setHtml(warLogTableBodyEl, data.log.map(e => `
            <tr class="historic-war-row" data-war-id="${e.war_id || ''}">
                <td>${e.end_time_formatted || '?'}</td>
                <td><img src="${e.opponent_badge_url || DEFAULT_BADGE_URL}" alt="Emblema" class="log-opponent-badge">${e.opponent_name || 'N/A'}</td>
                <td>${e.clan_stars ?? '?'}⭐ vs ${e.opponent_stars ?? '?'}⭐</td>
                <td class="war-result-${e.result?.toLowerCase() || 'unknown'}">${e.result || '?'}</td>
                <td>${e.team_size || '?'}</td>
                <td>${e.is_cwl ? "CWL" : "Normal"}</td>
            </tr>`).join(''));
    }


    async function savePlayerNote(playerTag, text, priority) {
        // (Código mantido igual)
        try {
            await fetchData(`notes/${encodeURIComponent(playerTag)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, priority })
            });
            // No explicit success feedback needed here, UI updates optimistically
        } catch (e) {
            console.error("Erro ao salvar nota:", e);
            // Maybe add visual feedback about save failure here
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

            // *** NOVO: Formata a data da última guerra (se existir) ***
            let lastWarDateFormatted = 'N/A';
            if (m.last_war_date) {
                try {
                    const date = new Date(m.last_war_date);
                    // Formata para dd/mm/aaaa
                    lastWarDateFormatted = date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
                } catch (e) {
                    console.warn(`Data inválida de última guerra para ${m.name}: ${m.last_war_date}`);
                    lastWarDateFormatted = 'Inválida';
                }
            }
            // *** AJUSTE: Usa span com title para o tooltip ***
            const lastWarHtml = `<span title="Esta é a data da última guerra conhecida">⚔️ ${lastWarDateFormatted}</span>`;
            // *** FIM AJUSTE ***

            return `
            <div class="member-card ${watchlistClass}" data-th="${m.town_hall || '?'}" data-name="${(m.name || '').toLowerCase()}">
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
                        <button class="cwl-status-btn ${m.cwl_status === 'active' ? 'active' : ''}" data-status="active">Ativo</button>
                        <button class="cwl-status-btn ${m.cwl_status === 'backup' ? 'active' : ''}" data-status="backup">Backup</button>
                    </div>
                </div>
            </div>`;
        }).join(''));

        attachMemberEventListeners();
        applyMemberFilters(); // Apply filters after populating
    }


    function attachMemberEventListeners() {
        // <<< ADICIONADO: Bloqueia a função se não for admin >>>
        if (!userIsAdmin) {
            console.log("Modo Somente Leitura: Listeners de edição de membros desativados.");
            return;
        }
        console.log("Modo Admin: Listeners de edição de membros ATIVADOS.");
        // <<< FIM ADIÇÃO >>>

        // Remove existing listeners before adding new ones to prevent duplicates
        membersGridEl?.querySelectorAll('.member-card-header').forEach(header => {
            header.replaceWith(header.cloneNode(true)); // Simple way to remove listeners
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
        // Remove listeners for cwl status buttons
        membersGridEl?.querySelectorAll('.cwl-status-btn').forEach(btn => {
            btn.replaceWith(btn.cloneNode(true));
        });

        // Add new listeners
        membersGridEl?.querySelectorAll('.member-card-header').forEach(header => {
            header.addEventListener('click', () => openMemberProfileModal(header.dataset.playerTag));
        });
        membersGridEl?.querySelectorAll('.note-text').forEach(span => {
            span.addEventListener('click', () => {
                const input = span.nextElementSibling;
                if (input && input.classList.contains('note-input')) { // Check if next sibling is the input
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
        // Add listeners for cwl status buttons
        membersGridEl?.querySelectorAll('.cwl-status-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                if (btn.classList.contains('active')) return;
                const selector = e.target.closest('.cwl-status-selector');
                const playerTag = e.target.closest('.member-cwl-status')?.dataset.playerTag;
                const newStatus = e.target.dataset.status;
                if (!playerTag || !newStatus) return;

                selector?.querySelector('.active')?.classList.remove('active'); // Add null checks
                e.target.classList.add('active');
                const success = await setPlayerCwlStatus(playerTag, newStatus);
                if (!success) {
                    alert('Erro ao salvar o status. Tente novamente.');
                    e.target.classList.remove('active');
                    selector?.querySelector(`[data-status="${newStatus === 'active' ? 'backup' : 'active'}"]`)?.classList.add('active'); // Add null checks
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
            return response && !response.error; // Success if no error reported
        } catch (e) {
            console.error("Erro ao definir status CWL:", e);
            return false;
        }
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

    filterNameInput?.addEventListener('input', applyMemberFilters); // Use input for instant filtering
    filterTHInput?.addEventListener('input', applyMemberFilters);

    // =========================================================================
    // >>> LÓGICA ATUALIZADA DO MODAL DE PERFIL DO JOGADOR <<<
    // =========================================================================
    async function openMemberProfileModal(playerTag) {
        if (!playerTag || !memberProfileModal || !memberProfileContent) return;
        
        // 1. Mostrar Spinner
        setHtml(memberProfileContent, '<div class="loading-spinner" style="margin: 40px auto;"></div><p style="text-align:center;">A carregar perfil profundo da Supercell...</p>');
        memberProfileModal.style.display = 'block';

        // 2. Busca dados de contexto interno (BD do bot)
        const membersData = await fetchData('members');
        let basicData = {};
        if (membersData && !membersData.error && membersData.members) {
            basicData = membersData.members.find(m => m.tag === playerTag) || {};
        }

        // 3. Busca a nova requisição DIRETA detalhada para pegar a foto da liga e os heróis
        let detailedData = await fetchData(`player_profile/${encodeURIComponent(playerTag)}`);
        
        if (!detailedData || detailedData.error) {
             setHtml(memberProfileContent, `<p class="message-box">${detailedData?.error || 'Erro ao comunicar com API da Supercell.'}</p>`);
             return;
        }

        // 4. Merge dos dois mundos (Contexto Local + Dados em Tempo Real da Supercell)
        const profileData = { ...basicData, ...detailedData };

        // --- PREPARAÇÃO DE DADOS ---
        
        // Data de Guerra formatada
        let lastWarDateFormatted = 'Sem Registro';
        if (profileData.last_war_date) {
            try {
                lastWarDateFormatted = new Date(profileData.last_war_date).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
            } catch (e) { lastWarDateFormatted = 'Inválida'; }
        }

        // Renderização dos Heróis (com mapeamento de imagens locais)
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

        // Painel de Status CWL (Apenas para Admins)
        const cwlStatus = profileData.cwl_status || 'active';
        const cwlStatusHtml = userIsAdmin ? `
            <div class="member-cwl-status" data-player-tag="${profileData.tag || ''}" style="margin-bottom: 20px;">
                <label>Status na CWL:</label>
                <div class="cwl-status-selector">
                    <button class="cwl-status-btn ${cwlStatus === 'active' ? 'active' : ''}" data-status="active">Ativo</button>
                    <button class="cwl-status-btn ${cwlStatus === 'backup' ? 'active' : ''}" data-status="backup">Backup</button>
                </div>
            </div>` : `
            <div class="member-cwl-status" style="margin-bottom: 20px; justify-content: flex-start; gap: 15px;">
                <label>Status CWL:</label>
                <span style="color: ${cwlStatus === 'active' ? 'var(--color-success)' : 'var(--color-warning)'}; font-weight:bold;">${cwlStatus === 'active' ? 'Ativo' : 'Banco de Reservas'}</span>
            </div>
            `;

        // 5. Montagem do HTML com o Novo Design (CSS inserido no style.css)
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
                    <span class="p-icon">⚔️</span>
                    <span class="p-val" style="font-size:1em; margin-top:5px;">${lastWarDateFormatted}</span>
                    <span class="p-label">Últ. Guerra</span>
                </div>
            </div>
            
            ${cwlStatusHtml}

            <h3 class="profile-section-title">Progresso de Heróis</h3>
            <div class="profile-heroes-grid">
                ${heroesHtml}
            </div>

            <div class="profile-chart-container">
                <h3 class="profile-section-title">Evolução de Troféus (Local)</h3>
                <canvas id="trophyChart"></canvas>
            </div>
        `);

        // 6. Refazer Listeners Internos do Modal
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
                         // Refresh background list silently
                         fetchData('members').then(populateMembersList);
                    }
                });
            });
        }

        // 7. Lógica do Gráfico de Troféus
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
            // Se não tem histórico salvo no banco do bot
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

        historicWarDetailContent.innerHTML = ''; // Clear loading
        try {
            const warDetailsContent = template.content.cloneNode(true);
            historicWarDetailContent.appendChild(warDetailsContent);
        } catch (e) {
            setHtml(historicWarDetailContent, '<p style="text-align:center; color: red;">Erro ao clonar template.</p>');
            console.error("Template clone error:", e);
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
        button?.addEventListener('click', () => { // Add null check
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

    async function loadAllData() {
        try {
            // <<< ADICIONADO: Busca o status E o status de admin >>>
            const statusData = await fetch('/api/status').then(res => res.ok ? res.json() : { maintenance_mode: true, is_admin: false }).catch(() => ({ maintenance_mode: true, is_admin: false }));
            userIsAdmin = statusData.is_admin || false; // Salva o status de admin
            console.log(`Status Admin: ${userIsAdmin}`); // Log
            // <<< FIM ADIÇÃO >>>

            // No need to redirect here, backend handles it in /painel handler

            const clanData = await fetchData('clan');
            populateClanInfo(clanData);

            if (clanData?.error && isFirstLoad) { // Add null check
                if(loadingOverlayEl) loadingOverlayEl.classList.add('hidden');
                console.error("Erro inicial ao carregar dados do clã, parando carregamento:", clanData.error);
                return; // Stop further loading if essential clan data failed initially
            }
            
            // *** CORREÇÃO HTTP 405: Mudar cwl/generate_plan de GET para POST ***
            const [
                membersData, currentWarDetailsData, missedAttacksData,
                warLogData, cwlInfoData, highlightsData, warAdvisorData
            ] = await Promise.all([
                fetchData('members'), fetchData('current_war_details'), fetchData('missed_attacks_history'),
                fetchData('war_log'), 
                fetchData('cwl/generate_plan', { method: 'POST' }), // *** ESTA É A CORREÇÃO ***
                fetchData('highlights'), fetchData('war_advisor_plan')
            ]);

            // Populate sections, checking for errors in each response
            if (membersData && !membersData.error) populateMembersList(membersData); else console.error("Erro ao carregar membros:", membersData?.error);
            if (currentWarDetailsData) populateWarDetails(currentWarDetailsData, 'war-details-nav', false); else console.error("Erro ao carregar detalhes da guerra atual:", currentWarDetailsData?.error); // War details can have expected 'error' like 'not in war'
            if (warAdvisorData) populateWarAdvisorPlan(warAdvisorData); else console.error("Erro ao carregar plano da IA:", warAdvisorData?.error);
            if (missedAttacksData && !missedAttacksData.error) populateMissedAttacksHistory(missedAttacksData); else console.error("Erro ao carregar histórico de ataques perdidos:", missedAttacksData?.error);
            if (warLogData && !warLogData.error) populateWarLog(warLogData); else console.error("Erro ao carregar log de guerra:", warLogData?.error);
            // *** CORREÇÃO: Chama a nova função principal da CWL ***
            if (cwlInfoData) populateCwlData(cwlInfoData); else console.error("Erro ao carregar informações da CWL:", cwlInfoData?.error); 
            if (highlightsData && !highlightsData.error) populateHighlights(highlightsData); else console.error("Erro ao carregar destaques:", highlightsData?.error);

            updateLastUpdated();
        } catch (error) {
            console.error("Erro geral ao carregar todos os dados:", error);
            // Don't hide loading overlay if there's a major fetch error
            if (loadingStatusTextEl && loadingOverlayEl && !loadingOverlayEl.classList.contains('hidden')) {
                setText(loadingStatusTextEl, 'Erro grave ao carregar dados. Verifique a consola.');
            }
        } finally {
            if (isFirstLoad && loadingOverlayEl) {
                // Check if there was an error message displayed before hiding
                const isLoadingError = loadingStatusTextEl?.textContent?.toLowerCase().includes('erro');
                if(!isLoadingError){ // Hide only if no major error was shown during loading
                    setTimeout(() => { loadingOverlayEl.classList.add('hidden'); }, 300); // Shorter delay
                }
                isFirstLoad = false;
            }
        }
    }


    if (closeModalButton) closeModalButton.addEventListener('click', () => { if(historicWarModal) historicWarModal.style.display = 'none'; });
    if (closeProfileModalButton) closeProfileModalButton.addEventListener('click', () => {
        if(memberProfileModal) memberProfileModal.style.display = 'none';
        // Refresh member list after closing profile is handled in populateMembersList/attachMemberEventListeners
    });

    window.addEventListener('click', (event) => {
        if (event.target == historicWarModal && historicWarModal) historicWarModal.style.display = 'none';
        if (event.target == memberProfileModal && memberProfileModal) {
            memberProfileModal.style.display = 'none';
            // Refresh list handled inside modal logic now
        }
    });

    // Use event delegation on the table body for war log clicks
    warLogTableBodyEl?.addEventListener('click', (event) => { // Add null check
        const row = event.target.closest('.historic-war-row');
        if (row && row.dataset.warId) {
            openHistoricWarModal(row.dataset.warId);
        }
    });

    loadAllData();
    setInterval(loadAllData, 45000); // Refresh data every 45 seconds

    async function checkApiMaintenance() {
        // (Código mantido igual)
        try {
            const response = await fetch(`${API_BASE_URL}/api/coc_status`, { cache: 'no-store' });
            if (!response.ok) { console.error('Falha ao buscar status da API.'); return; }
            const data = await response.json();
            if (data.status === 'maintenance') {
                console.warn('API em manutenção. Redirecionando...');
                // Check if already on maintenance page to prevent loop
                if (!window.location.pathname.endsWith('/maintenance.html') && !window.location.pathname.endsWith('/maintenance')) {
                    window.location.href = '/maintenance'; // Use relative path
                }
            } else if (data.status === 'ok' && (window.location.pathname.endsWith('/maintenance.html') || window.location.pathname.endsWith('/maintenance'))) {
                // If API is OK and we are on maintenance page, redirect back
                console.info('API voltou. Redirecionando para o painel...');
                window.location.href = '/painel';
            }
        } catch (error) { console.error('Erro ao verificar status de manutenção:', error); }
    }
    checkApiMaintenance(); // Check immediately
    setInterval(checkApiMaintenance, 20000); // Check every 20 seconds
});
