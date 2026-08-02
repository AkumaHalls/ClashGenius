document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = '';
    const DEFAULT_BADGE_URL = '/static/images/default_badge.png';
    const ASSETS_BASE_URL = '/assets';

    /** Gera URL para um asset do Clash of Clans.
     * @param {string} category - Ex: 'troops', 'heroes', 'spells', 'equipment', 'pets'
     * @param {string} name - Nome da unidade (ex: 'Barbarian', 'Lightning Spell')
     * @param {number} [level] - Nível (para buildings)
     * @returns {string} URL completa do asset
     */
    function getAssetUrl(category, name, level) {
        const cleaned = name.toLowerCase()
            .replace(/ /g, '_')
            .replace(/\./g, '')
            .replace(/\?/g, '')
            .replace(/'/g, '');
        if (level !== undefined) {
            return `${ASSETS_BASE_URL}/${category}/${cleaned}/level_${level}.webp`;
        }
        if (category === 'spells' || category === 'equipment') {
            return `${ASSETS_BASE_URL}/${category}/${cleaned}.webp`;
        }
        return `${ASSETS_BASE_URL}/${category}/${cleaned}/icon.webp`;
    }

    let phaseTimerInterval = null; 
    let globalMembersList = []; // <-- VARIAVEL GLOBAL ADICIONADA PARA SALVAR OS MEMBROS DO CLÃ

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
    const clanLevelValueEl = document.getElementById('clanLevelValue');
    const clanPointsEl = document.getElementById('clanPoints');
    const clanMemberCountValueEl = document.getElementById('clanMemberCountValue');
    const clanMemberCountBarEl = document.getElementById('clanMemberCountBar');
    const clanMemberBarFillEl = document.getElementById('clanMemberBarFill');
    const clanWarWinsEl = document.getElementById('clanWarWins');
    const clanLocationValueEl = document.getElementById('clanLocationValue');
    const clanTypeValueEl = document.getElementById('clanTypeValue');
    const clanDescriptionEl = document.getElementById('clanDescription');
    const clanBadgeEl = document.getElementById('clanBadge');
    const clanCapitalPointsEl = document.getElementById('clanCapitalPoints');
    const clanCapitalLeagueEl = document.getElementById('clanCapitalLeague');

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

    const cwlPlannerSectionEl = document.getElementById('cwlPlannerSection');
    const cwlActiveInfoEl = document.getElementById('cwlActiveInfo');
    const cwlPlanResultEl = document.getElementById('cwlPlanResult');
    const cwlPlanContentEl = document.getElementById('cwlPlanContent');
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

    // DOM ELEMENTS - EFEITOS BLUR E CADEADO (Adicionados CWL e Capital)
    const cwlBlurContentEl = document.getElementById('cwlBlurContent');
    const noCwlOverlayEl = document.getElementById('noCwlOverlay');
    
    const capitalBlurContentEl = document.getElementById('capitalBlurContent');
    const capStatusEl = document.getElementById('capStatus');
    const capTotalLootEl = document.getElementById('capTotalLoot');
    const capTotalAttacksEl = document.getElementById('capTotalAttacks');
    const capDestroyedEl = document.getElementById('capDestroyed');
    const capTopAttackersListEl = document.getElementById('capTopAttackersList');
    const capZeroAttacksListEl = document.getElementById('capZeroAttacksList');
    const capIncompleteAttacksListEl = document.getElementById('capIncompleteAttacksList');
    const noCapitalOverlayEl = document.getElementById('noCapitalOverlay');

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
    let globalMissedAttacks = [];

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
        .vip-admin-border {
            border: 2px solid transparent !important;
            background: rgba(20, 20, 30, 0.95) !important;
            position: relative;
            overflow: hidden;
        }
        .vip-admin-border::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            background: linear-gradient(45deg, #ff0040, #ff6600, #ffd700, #00ff41, #00fff9, #0080ff, #b300ff, #ff00aa, #ff0040);
            background-size: 400% 400%;
            animation: admin-border-dance 4s linear infinite;
            z-index: -1;
            border-radius: var(--border-radius-base);
        }
        @keyframes admin-border-dance {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        .vip-admin-border .member-info h4 {
            background: linear-gradient(90deg, #ff0040, #ffd700, #00fff9, #b300ff);
            background-size: 200% auto;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            animation: admin-text-shimmer 3s linear infinite;
        }
        @keyframes admin-text-shimmer {
            0% { background-position: 0% center; }
            100% { background-position: 200% center; }
        }
        .vip-admin-border:hover {
            box-shadow: 0 6px 25px rgba(179, 0, 255, 0.3), 0 0 40px rgba(0, 255, 249, 0.15);
        }
        .admin-border-btn {
            background: rgba(179, 0, 255, 0.15);
            border: 1px solid rgba(179, 0, 255, 0.4);
            color: #b300ff;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8em;
            font-weight: 500;
            transition: all 0.2s;
            font-family: var(--font-body);
        }
        .admin-border-btn:hover { background: rgba(179, 0, 255, 0.3); box-shadow: 0 0 8px rgba(179, 0, 255, 0.3); }
        .admin-border-btn.active {
            background: linear-gradient(135deg, #ff0040, #b300ff, #00fff9);
            color: white; font-weight: 700; border-color: transparent;
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
            muteButtonEl.innerHTML = backgroundMusicEl.muted ? '<svg width="1em" height="1em" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:middle"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0014 8.5v1.2l3.02 3.02c.07-.57.11-1.15.11-1.72zM16.5 12c0 .76-.18 1.48-.48 2.13l1.45 1.45A8.39 8.39 0 0018 12c0-3.54-2.46-6.52-5.76-7.33v2.07C14.23 7.47 16.5 9.53 16.5 12zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06a8.47 8.47 0 003.69-1.81L19.73 21 21 19.73l-9-9L4.27 3z"/></svg>' : '<svg width="1em" height="1em" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:middle"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0014 8.5v7a4.47 4.47 0 002.5-3.5zM14 3.23v2.06a6.5 6.5 0 010 13.42v2.06A8.5 8.5 0 0014 3.23z"/></svg>';
            localStorage.setItem('musicMuted', backgroundMusicEl.muted.toString()); 
        });
        if (localStorage.getItem('musicMuted') === 'true') {
            backgroundMusicEl.muted = true;
            muteButtonEl.innerHTML = '<svg width="1em" height="1em" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:middle"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0014 8.5v1.2l3.02 3.02c.07-.57.11-1.15.11-1.72zM16.5 12c0 .76-.18 1.48-.48 2.13l1.45 1.45A8.39 8.39 0 0018 12c0-3.54-2.46-6.52-5.76-7.33v2.07C14.23 7.47 16.5 9.53 16.5 12zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06a8.47 8.47 0 003.69-1.81L19.73 21 21 19.73l-9-9L4.27 3z"/></svg>';
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

    // === SISTEMA GLOBAL DE TOOLTIPS ===
    function initTooltips() {
        document.querySelectorAll('[data-tooltip]').forEach(el => {
            if (el.querySelector('.cyber-tooltip')) return;
            const tip = document.createElement('span');
            tip.className = 'cyber-tooltip';
            tip.textContent = el.dataset.tooltip;
            el.appendChild(tip);
            el.style.position = 'relative';
            el.style.cursor = 'help';
        });
        repositionTooltips();
    }

    function repositionTooltips() {
        document.querySelectorAll('[data-tooltip]').forEach(el => {
            const tip = el.querySelector('.cyber-tooltip');
            if (!tip) return;
            tip.classList.remove('tooltip-bottom');
            requestAnimationFrame(() => {
                const rect = tip.getBoundingClientRect();
                if (rect.top < 0) {
                    tip.classList.add('tooltip-bottom');
                }
            });
        });
    }

    window.addEventListener('scroll', () => {
        requestAnimationFrame(repositionTooltips);
    }, { passive: true });

    // Adiciona tooltip para o ícone de exclamação de ataques perdidos
    function addWarWarningTooltips() {
        document.querySelectorAll('.missed-attack-icon, .attacks-warning-icon').forEach(el => {
            if (el.querySelector('.ww-tooltip-text')) return;
            const tip = document.createElement('span');
            tip.className = 'ww-tooltip-text';
            tip.textContent = el.dataset.warning || 'ATENCAO: Este membro não realizou todos os ataques na guerra!';
            el.appendChild(tip);
            el.classList.add('war-warning-tooltip');
        });
    }

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
        if (clanNameEl) clanNameEl.setAttribute('data-text', data.name);
        setText(clanTagEl, data.tag);
        setBadge(clanBadgeHeaderEl, data.badge_url);
        setBadge(clanBadgeEl, data.badge_url);
        setText(clanLevelValueEl, data.level || '-');
        const memberCount = data.member_count || 0;
        setText(clanMemberCountValueEl, `${memberCount}/50`);
        setText(clanMemberCountBarEl, `${memberCount}/50`);
        if (clanMemberBarFillEl) {
            const pct = Math.min((memberCount / 50) * 100, 100);
            setTimeout(() => { clanMemberBarFillEl.style.width = `${pct}%`; }, 200);
        }
        setText(clanLocationValueEl, data.location || '-');
        setText(clanTypeValueEl, data.type || '-');
        setText(clanWarWinsEl, `${data.war_wins?.toLocaleString() || '-'}`);
        setText(clanPointsEl, `${data.points?.toLocaleString() || '-'}`);
        setText(clanCapitalPointsEl, `${data.capital_points?.toLocaleString() || '-'}`);
        setText(clanCapitalLeagueEl, data.capital_league);
        setText(clanDescriptionEl, data.description, 'Sem descrição.');
        setText(botVersionEl, data.version, '?');
        try {
            localStorage.setItem('clashgenius_version', data.version || '?');
            localStorage.setItem('clashgenius_last_clan', JSON.stringify({
                name: data.name,
                level: data.level,
                members: data.member_count,
                score: data.score
            }));
        } catch (e) { /* armazenamento indisponível */ }
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
            const medal_icons = ['<img src="/assets/icons/Icon_HV_Attack_Star.png" class="icon-sm">', '<img src="/assets/icons/Icon_HV_Attack_Star.png" class="icon-sm">', '<img src="/assets/icons/Icon_HV_Attack_Star.png" class="icon-sm">'];
            const rankIcon = medal_icons[index] || `${index + 1}.`; 
            return `<div class="podium-item ${medals[index] || ''}" style="position: relative;">
                        <span class="podium-rank">${rankIcon}</span>
                        <div class="podium-details">
                            <div class="member-name">${escapeHtml(donor.name || 'N/A')} (CV${escapeHtml(donor.town_hall || '?')})</div>
                            <div class="donation-count"><strong>${(donor.donations || 0).toLocaleString()}</strong> tropas doadas</div>
                        </div>
                        ${donor.reason ? `<span class="tooltip-text" style="width:250px; background-color: var(--color-background); color: #fff; text-align: center; border-radius: 6px; padding: 10px; position: absolute; z-index: 10; bottom: 110%; left: 50%; margin-left: -125px; opacity: 0; transition: opacity 0.3s; font-size: 0.85em; border: 1px solid var(--color-border-light); box-shadow: 0 4px 8px rgba(0,0,0,0.3); pointer-events: none;">${escapeHtml(donor.reason)}</span>` : ''}
                    </div>`;
        }).join('') : '<p>Nenhum doador encontrado.</p>');

        const warHeroTitleEl = document.getElementById('warHeroTitle');
        setText(warHeroTitleEl, 'Heroes da Ultima Guerra'); 
        setHtml(bestAttacksListEl, data.war_heroes?.length > 0 ? data.war_heroes.map(hero => {
            const isMvp = hero.rank === 1;
            const heroClass = isMvp ? 'mvp-card' : 'attack-item';
            const medals = ['<img src="/assets/icons/Icon_HV_Attack_Star.png" class="icon-sm">', '<img src="/assets/icons/Icon_HV_Attack_Star.png" class="icon-sm">', '<img src="/assets/icons/Icon_HV_Attack_Star.png" class="icon-sm">'];
            const rankIcon = medals[hero.rank - 1] || `${hero.rank}.`; 

            const titleHtml = isMvp
                ? `<p class="mvp-title">Jogador Mais Valioso (MVP)</p><h4 class="mvp-name">${escapeHtml(hero.name || 'N/A')} <span>(CV${escapeHtml(hero.town_hall || '?')})</span></h4>`
                : `<div class="attack-header">${rankIcon} ${escapeHtml(hero.name || 'N/A')} (CV${escapeHtml(hero.town_hall || '?')})</div>`;

            return `<div class="${heroClass}">
                        ${titleHtml}
                        <span class="tooltip-text" style="pointer-events: none;">${escapeHtml(hero.reason || 'Sem detalhes')}</span>
                    </div>`;
        }).join('') : '<p>Nenhum herói para destacar na última guerra ou análise indisponível.</p>'); 

        if (activityChart) {
            try { activityChart.destroy(); activityChart = null; } catch(e) {}
        }

        const chartData = data.activity_chart_data;
        if (activityChartCanvas && chartData && chartData.labels && chartData.labels.length > 0 && chartData.donations && chartData.received) {
            (function renderChart() {
                if (typeof Chart === 'undefined') {
                    setTimeout(renderChart, 500);
                    return;
                }
                try {
                    const ctx = activityChartCanvas.getContext('2d');
                    if (!ctx) throw new Error("Contexto 2D indisponível.");
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
            })();
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
        const FILLED = `<img src="${ASSETS_BASE_URL}/icons/Icon_HV_Attack_Star.png" class="star-icon" alt="*">`;
        const EMPTY = `<img src="${ASSETS_BASE_URL}/bot/icons/no_star.png" class="star-icon" alt="-">`;
        if (isNaN(starCount) || starCount < 0) return EMPTY + EMPTY + EMPTY; 
        return FILLED.repeat(starCount) + EMPTY.repeat(Math.max(0, 3 - starCount));
    }

    function icon(name, cls) {
        const ICONS = {
            sword: '/assets/icons/Icon_HV_Sword.png',
            shield: '/assets/icons/Icon_HV_Shield.png',
            trophy: '/assets/icons/Icon_HV_Podium.png',
            star: '/assets/icons/Icon_HV_Attack_Star.png',
            noStar: '/assets/bot/icons/no_star.png',
            warStar: '/assets/bot/icons/war_star.png',
            flag: '/assets/icons/Icon_HV_Start_Flag.png',
            shieldArrow: '/assets/icons/Icon_HV_Shield_Arrow.png',
            raidAttack: '/assets/icons/Icon_HV_Raid_Attack.png',
            trophyBest: '/assets/icons/Icon_HV_Trophy_Best.png',
            xp: '/assets/icons/Icon_HV_XP.png',
            in: '/assets/icons/Icon_HV_In.png',
            out: '/assets/icons/Icon_HV_Out.png',
            clanGamesMedal: '/assets/icons/Icon_HV_Clan_Games_Medal.png',
            goldPass: '/assets/icons/Icon_HV_Gold_Pass.png',
            planet: '/assets/icons/Icon_HV_Planet.png'
        };
        const src = ICONS[name] || ICONS.star;
        const clsAttr = cls ? ` ${cls}` : '';
        return `<img src="${src}" class="icon-sm${clsAttr}" alt="${name}">`;
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

        const warData = data.war_data || {};

        if (!isModal && predictionSection) {
            const predictionTextEl = container.querySelector('#warPredictionText');
            const predictionTagsEl = container.querySelector('#warPredictionTags');
            const isEnded = (warData.status || '').toLowerCase() === 'warended';

            if (isEnded) {
                const ourStars = warData.clan_stars ?? 0;
                const oppStars = warData.opponent_stars ?? 0;
                let resultIcon, resultText, resultColor;
                if (ourStars > oppStars) {
                    resultIcon = icon('trophy'); resultText = 'VITÓRIA'; resultColor = 'var(--color-success)';
                } else if (oppStars > ourStars) {
                    resultIcon = icon('noStar'); resultText = 'DERROTA'; resultColor = 'var(--color-danger)';
                } else {
                    resultIcon = icon('shield'); resultText = 'EMPATE'; resultColor = 'var(--color-warning)';
                }
                setHtml(predictionTextEl, `
                    <div class="war-ended-banner" style="border-color: ${resultColor};">
                        <div class="war-ended-icon">${resultIcon}</div>
                        <div class="war-ended-content">
                            <h3 class="war-ended-title" style="color: ${resultColor};">${resultText}</h3>
                            <p class="war-ended-score">${ourStars} <img src="${ASSETS_BASE_URL}/icons/Icon_HV_Attack_Star.png" class="star-icon" alt="*"> vs ${oppStars} <img src="${ASSETS_BASE_URL}/icons/Icon_HV_Attack_Star.png" class="star-icon" alt="*"></p>
                            <p class="war-ended-sub">${escapeHtml(warData.clan_name)} vs ${escapeHtml(warData.opponent_name)}</p>
                        </div>
                    </div>
                `);
                predictionTagsEl.innerHTML = '';
                predictionSection.style.display = 'block';
            } else if (data.prediction && data.prediction.summary_panel) {
                setText(predictionTextEl, data.prediction.summary_panel);
                predictionTagsEl.innerHTML = `
                    <div class="prediction-tag">
                        <span class="prediction-tag-icon">${icon('flag')}</span>
                        <div class="prediction-tag-text">
                            <span class="tag-label">Probabilidade</span>
                            <span class="tag-value">${(data.prediction.probability || 0).toFixed(1)}%</span>
                        </div>
                        <span class="tooltip-text">Chance de vitória do nosso clã no final da guerra, calculada pela IA.</span>
                    </div>
                    <div class="prediction-tag">
                        <span class="prediction-tag-icon">${icon('star')}</span>
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
        setText(query(`#${prefix}statsOurAvgDuration`), war.clan_avg_duration); 
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
                <td>${escapeHtml(att.attacker_name || '?')} (CV${escapeHtml(att.attacker_townhall || '?')})</td>
                <td><span class="attack-stars">${createStarString(att.stars)}</span> ${att.destruction ?? 0}%</td>
                <td>${escapeHtml(att.defender_name || '?')} (CV${escapeHtml(att.defender_townhall || '?')})</td>
                <td>${att.duration ?? '-'}</td>
            </tr>
        `).join('') : '<tr><td colspan="5">Nenhum ataque registado.</td></tr>');

        const populateTeamTabData = (teamMembersData, teamName, teamElementId) => {
            const teamMembersEl = query(`#${prefix}${teamElementId}Members`);
            setText(query(`#${prefix}${teamElementId}Name`), teamName);
            setHtml(teamMembersEl, teamMembersData?.length > 0 ? teamMembersData.map(member => {
                const attacksHtml = '<h5>Ataques Feitos:</h5><ul class="member-attack-list">' +
                    (member.attacks_made?.length > 0
                        ? member.attacks_made.map(atk => `<li>${createStarString(atk.stars)} ${atk.destruction ?? 0}% vs ${escapeHtml(atk.defender_name || '?')} (CV${escapeHtml(atk.defender_townhall || '?')})</li>`).join('')
                        : '<li>Nenhum ataque feito.</li>') + '</ul>';
                const defensesHtml = '<h5>Defesas Recebidas:</h5><ul class="member-defense-list">' +
                    (member.defenses_received?.length > 0
                        ? member.defenses_received.map(def => `<li>${createStarString(def.stars)} ${def.destruction ?? 0}% por ${escapeHtml(def.attacker_name || '?')} (CV${escapeHtml(def.attacker_townhall || '?')})</li>`).join('')
                        : '<li>Nenhuma defesa registada.</li>') + '</ul>';
                return `<div class="team-member-card">
                            <h4><img src="${getAssetUrl('buildings/home-village', 'town_hall', member.townhall || 1)}" alt="CV${escapeHtml(member.townhall || '?')}" onerror="this.onerror=null; this.src=DEFAULT_BADGE_URL; this.style.height='28px';"/> ${member.map_position || '?'}. ${escapeHtml(member.name || 'N/A')} (CV${escapeHtml(member.townhall || '?')})</h4>
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

    function populateWarAdvisorPlan(data, warState) {
        if (!warAdvisorContentEl) return;
        if (phaseTimerInterval) { clearInterval(phaseTimerInterval); phaseTimerInterval = null; }

        if (warState === 'warEnded') {
            const warData = window.__warData || {};
            const ourS = warData.clan_stars ?? 0;
            const oppS = warData.opponent_stars ?? 0;
            const result = ourS > oppS ? 'Vencemos' : (oppS > ourS ? 'Perdemos' : 'Empatamos');
            setHtml(warAdvisorContentEl, `
                <div class="war-ended-advisor">
                    <div class="war-ended-icon">${icon('flag')}</div>
                    <h3>Guerra Encerrada</h3>
                    <p>${result}! ${ourS} <img src="${ASSETS_BASE_URL}/icons/Icon_HV_Attack_Star.png" class="star-icon" alt="*"> vs ${oppS} <img src="${ASSETS_BASE_URL}/icons/Icon_HV_Attack_Star.png" class="star-icon" alt="*"></p>
                    <p class="war-ended-sub">O plano de ataque não está mais disponível. Consulte o Histórico de Guerras para análises pós-guerra.</p>
                </div>
            `);
            return;
        }

        const setupAdvisorUI = (planData) => {
            if (!planData || !planData.success) {
                const timerEl = warAdvisorContentEl.querySelector('#advisorPhaseTimer');
                if(timerEl) timerEl.style.display = 'none';
                setHtml(warAdvisorContentEl, `<div class="advisor-plan-container"><p class="message-box">${escapeHtml(planData?.error || 'Nenhuma recomendação disponível.')}</p></div>`);
                return;
            }
            let contentHtml = `
                <div id="advisorPhaseTimer" class="advisor-phase-timer" style="display: none;"><h4>MUDANÇA DE FASE</h4><p id="advisorPhaseTimerText">Calculando...</p></div>
                <div class="advisor-header">
                    <h3>${escapeHtml(planData.phase_title || 'Plano de Ataque')}</h3>
                    <p>${escapeHtml(planData.prediction_summary || '-')}</p>
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
                            <h4>${rec.member_pos || '?'}. ${escapeHtml(rec.member_name || 'N/A')} (CV${escapeHtml(rec.member_th || '?')})</h4>
                            <span>Ataque Nº ${rec.attack_number || '?'}</span>
                        </div>
                        <div class="advisor-target-info">
                            <p>Alvo Recomendado</p>
                            <span>#${rec.recommended_target_pos || '?'} (CV${escapeHtml(rec.recommended_target_th || '?')})</span>
                        </div>
                        <div class="advisor-justification">
                            <p><span class="ai-indicator"></span><strong>IA:</strong> ${escapeHtml(rec.justification || '-')}</p>
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
                <h3 class="war-group-header">Guerra vs <strong>${escapeHtml(war.opponent_name || '?')}</strong> (${escapeHtml(war.end_date || '?')}) ${war.is_latest ? '<span class="latest-war-badge"><img src="/assets/icons/Icon_HV_Start_Flag.png" class="icon-sm"> Última Guerra</span>' : ''}</h3>
                <div class="player-card-grid">
                    ${war.missed_attacks_members?.map(member => `
                        <div class="missed-attack-card ${member.attacks_left >= 2 ? 'severity-high' : 'severity-medium'} war-warning-tooltip">
                            <span class="ww-tooltip-text">${member.attacks_left >= 2 ? 'ALERTA: Este membro esqueceu 2 ou mais ataques! Infração grave.' : 'ATENCAO: Este membro não realizou todos os seus ataques nesta guerra.'}</span>
                            <div class="player-info">
                                <h4>${escapeHtml(member.name || '?')} <span>(CV${escapeHtml(member.town_hall || '?')})</span></h4>
                                <div class="player-tag-container">
                                    <span class="player-tag">${escapeHtml(member.tag || '#?')}</span>
                                    <button class="copy-tag-btn" data-tag="${escapeHtml(member.tag || '#?')}">Copiar</button>
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
                mainStatusText = `Preparação (Dia ${data.current_day})`;
            } else {
                mainStatusText = `${icon('sword')} Em Guerra (Dia ${data.current_day})`;
                statusColor = "var(--color-success)";
            }
        } else {
            mainStatusText = "Buscando Oponentes..."; 
            statusColor = "var(--color-info)";
        }

        let seasonStr = data.season || '-';
        let groupStateStr = data.state === 'preparation' ? 'Formando Grupo' : (data.state === 'inWar' ? 'Em Andamento' : (data.state || '-'));

        let clansHtml = '';
        if (data.clans && Array.isArray(data.clans) && data.clans.length > 0) {
            clansHtml = '<div style="display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-top: 15px;">';
            data.clans.forEach(c => {
                clansHtml += `<div style="background: rgba(0,0,0,0.3); padding: 8px 15px; border-radius: 20px; display:flex; align-items:center; font-size: 0.95em; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 4px 6px rgba(0,0,0,0.2);"><img src="${c.badge_url || DEFAULT_BADGE_URL}" style="width: 24px; height: 24px; margin-right: 10px;"> <span style="font-weight: bold; letter-spacing: 0.5px;">${escapeHtml(c.name)}</span></div>`;
            });
            clansHtml += '</div>';
        } else {
            clansHtml = "<p style='color:var(--color-warning); margin-top:10px; font-style: italic;'>Dados do grupo ausentes no cache antigo. Clique em 'Recalcular Rotação Inteligente' para forçar a atualização.</p>";
        }

        let roundsText = '';
        if (data.rounds && Array.isArray(data.rounds) && data.rounds.length > 0) {
            roundsText = '<div style="display: flex; justify-content: center; gap: 10px; margin-top: 15px; flex-wrap: wrap;">';
            data.rounds.forEach((r, i) => {
                 let roundIcon = r === 'warEnded' ? icon('star') : (r === 'inWar' ? icon('sword') : icon('flag'));
                 let color = r === 'warEnded' ? 'var(--color-success)' : (r === 'inWar' ? 'var(--color-accent)' : 'var(--color-text-secondary)');
                 let bgColor = r === 'warEnded' ? 'rgba(46, 204, 113, 0.1)' : (r === 'inWar' ? 'rgba(231, 76, 60, 0.1)' : 'rgba(255, 255, 255, 0.05)');
                 roundsText += `<div style="background: ${bgColor}; padding: 10px 15px; border-radius: 10px; border-bottom: 3px solid ${color}; font-weight: bold; font-size: 0.9em; text-align: center; min-width: 60px;">Dia ${i+1}<br><span style="display:block; margin-top: 8px;">${roundIcon}</span></div>`;
            });
            roundsText += '</div>';
        } else {
            roundsText = "<p style='color:var(--color-warning); margin-top:10px; font-style: italic;'>Cronograma ausente no cache antigo. Clique em 'Recalcular Rotação Inteligente'.</p>";
        }

        const aestheticHeaderHtml = `
            <div class="status-badge" style="font-size: 1.3em; background-color: ${statusColor}1A; color: ${statusColor}; border: 1px solid ${statusColor}; margin-bottom: 25px; padding: 15px 20px; border-radius: 12px; text-align: center; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">
                ${mainStatusText}
            </div>
            
            <div class="stats-grid" style="margin-bottom: 25px;">
                <div class="stat-card" style="padding: 20px; text-align: center; background: linear-gradient(145deg, rgba(255,255,255,0.05) 0%, rgba(0,0,0,0.2) 100%);">
                    <h4 style="color: var(--color-text-secondary); font-size: 0.85em; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 10px;">Temporada</h4>
                    <div class="stat-value" style="font-size: 1.5em; color: var(--color-text-main); font-weight: bold;">${escapeHtml(seasonStr)}</div>
                </div>
                <div class="stat-card" style="padding: 20px; text-align: center; background: linear-gradient(145deg, rgba(255,255,255,0.05) 0%, rgba(0,0,0,0.2) 100%);">
                    <h4 style="color: var(--color-text-secondary); font-size: 0.85em; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 10px;">Estado do Grupo</h4>
                    <div class="stat-value" style="font-size: 1.5em; color: var(--color-text-main); font-weight: bold;">${groupStateStr}</div>
                </div>
            </div>

            <div class="cwl-overview-card" style="margin-bottom: 25px; text-align: center; padding: 25px; border: 1px solid rgba(255,255,255,0.05); border-radius: 15px; background-color: rgba(0,0,0,0.15);">
                <h3 style="margin-bottom: 5px; font-size: 1.2em; color: var(--color-text-main); text-transform: uppercase; letter-spacing: 1px;">${icon('shield')} Clãs no Grupo</h3>
                ${clansHtml}
            </div>

            <div class="cwl-overview-card" style="margin-bottom: 40px; text-align: center; padding: 25px; border-radius: 15px; background: rgba(0,0,0,0.2);">
                <h3 style="margin-bottom: 5px; font-size: 1.2em; color: var(--color-text-main); text-transform: uppercase; letter-spacing: 1px;">Cronograma Oficial</h3>
                ${roundsText}
            </div>
        `;

        setHtml(cwlActiveInfoEl, aestheticHeaderHtml);
    }

    function populateCwlOverview(planData) {
        if (!cwlOverviewContainerEl) return;

        const score = (planData && Array.isArray(planData.participation_score)) ? planData.participation_score : [];
        
        let placarHtml = '<h4>Placar de Participação (Estimado)</h4>'; 
        placarHtml += '<div class="cwl-overview-list-bench">'; 
        
        if (score.length > 0) {
             score.sort((a, b) => (b.days_played || 0) - (a.days_played || 0));
             placarHtml += score.map(p => {
                 const name = p.name || (p.player && p.player.name) || 'Membro Oculto';
                 const th = p.town_hall || (p.player && p.player.town_hall) || '?';
                 const pIcon = p.status === 'priority' ? icon('star') : (p.status === 'unavailable' ? `<span style="color:var(--color-danger);">&#10006;</span>` : '');
                 return `<p>${pIcon} ${escapeHtml(name)} (CV${escapeHtml(th)}): <strong>${p.days_played || 0} / 7 dias</strong></p>`;
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
                    <h4 style="margin: 0 0 5px 0; color: ${tColor};">Análise ML: vs ${escapeHtml(opp.clan_name)}</h4>
                    <p style="margin: 0; font-size: 0.9em;">Classificação: <strong>${escapeHtml(opp.threat_level)}</strong> | Tática <span class="ai-indicator"></span>IA: ${escapeHtml(dayData.strategy_used)}</p>
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
                        <p style="color: #e74c3c; margin-bottom:2px;"><strong>Sai:</strong> ${escapeHtml(outName)} (CV${escapeHtml(outTh)}) - <em>${escapeHtml(sub.out_reason || 'Rotação')}</em></p>
                        <p style="color: #2ecc71; margin-bottom:5px;"><strong>Entra:</strong> ${escapeHtml(inName)} (CV${escapeHtml(inTh)})</p>
                        <div class="xai-badge"><span class="ai-indicator"></span>IA: ${escapeHtml(sub.reason || 'Escalado pela matriz.')}</div>
                    </div>`;
                }).join('')
                : `<p>${day == 1 ? 'Escalação inicial baseada nos melhores CVs e Titulares Fixos.' : '<span class="ai-indicator"></span>A IA sugere manter a escalação do dia anterior.'}</p>`;

            const roster = dayData.active_roster || [];
            planHtml += `<h4 style="margin-top:20px;">${icon('sword')} Escalação Ativa Sugerida (Dia ${day}) - ${roster.length}v${roster.length}</h4><div class="roster-grid">`;
            
            const sortedRoster = [...roster].sort((a, b) => {
                const thA = a.town_hall || (a.player && a.player.town_hall) || 0;
                const thB = b.town_hall || (b.player && b.player.town_hall) || 0;
                return thB - thA;
            });

            planHtml += sortedRoster.length > 0
                ? sortedRoster.map((p, i) => {
                    const name = p.name || (p.player && p.player.name) || '?';
                    const th = p.town_hall || (p.player && p.player.town_hall) || '?';
                    const pIcon = p.status === 'priority' ? icon('star') : (p.status === 'unavailable' ? `<span style="color:var(--color-danger);">&#10006;</span>` : '');
                    return `
                    <div class="roster-player" ${p.status === 'priority' ? 'style="border-left: 3px solid var(--color-accent);"' : ''}>
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span>${i + 1}. ${pIcon} ${escapeHtml(name)} (CV${escapeHtml(th)})</span>
                            <span style="color:var(--color-text-secondary); font-size:0.8em;">${p.days_played || 0}d</span>
                        </div>
                        ${p.xai_justification ? `<div style="font-size: 0.7em; color: #a0aec0; margin-top: 5px; font-family: monospace;">> ${escapeHtml(p.xai_justification)}</div>` : ''}
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
                        return `<p>${i+1}. ${escapeHtml(name)} (CV${escapeHtml(th)}) - ${p.days_played || 0}d</p>`;
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
                        return `<p>${i+1}. ${escapeHtml(name)} (CV${escapeHtml(th)}) - ${p.days_played || 0}d</p>`;
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
        
        if(cwlOverviewContainerEl) setHtml(cwlOverviewContainerEl, `<div class="loading-spinner" style="margin: 20px auto;"></div><p style="text-align:center; grid-column: 1/-1;"><span class="ai-indicator"></span>A IA está calculando a rotação ideal...</p>`);
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
                     setHtml(cwlOverviewContainerEl, `<div class="error-text" style="grid-column: 1/-1;">Erro ao gerar rotação: ${escapeHtml(planData?.error || 'Não há membros suficientes marcados como Ativos.')}</div>`);
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

    // === FUNÇÃO CWL COM EFEITO BLUR ===
    function populateCwlData(data) {
        if (!cwlPlannerSectionEl) return;
        cwlPlannerSectionEl.style.display = 'block';

        if (!data || data.error || data.status === "NotInCwl" || data.state === "not_in_season") {
            if (noCwlOverlayEl) noCwlOverlayEl.style.display = 'flex';
            if (cwlBlurContentEl) cwlBlurContentEl.classList.add('cg-blurred-state');
            
            // Oculta alertas padrão que quebram o layout bonito
            const oldStatus = document.getElementById('cwlStatusText');
            if (oldStatus) oldStatus.style.display = 'none'; 
            return;
        }

        if (noCwlOverlayEl) noCwlOverlayEl.style.display = 'none';
        if (cwlBlurContentEl) cwlBlurContentEl.classList.remove('cg-blurred-state');

        const oldStatus = document.getElementById('cwlStatusText');
        if (oldStatus) oldStatus.style.display = 'none'; 
        
        if (cwlActiveInfoEl) cwlActiveInfoEl.style.display = 'block'; 
        if (cwlPlanResultEl) cwlPlanResultEl.style.display = 'block'; 

        updateCwlHeaderUI(data);

        if (data.warning) {
            setHtml(cwlPlanWarningEl, `<strong>Aviso da <span class="ai-indicator"></span>IA:</strong> ${escapeHtml(data.warning)}`);
            cwlPlanWarningEl.style.display = 'block';
        } else if (cwlPlanWarningEl) {
            cwlPlanWarningEl.style.display = 'none';
        }

        if (userIsAdmin) {
            if (!document.getElementById('recalc-cwl-btn')) {
                 const btnHtml = `<button id="recalc-cwl-btn" class="control-btn" style="margin-bottom: 20px; width: 100%; background-color: var(--color-accent); font-weight: bold; border-radius: 10px; padding: 12px; font-size: 1.1em; transition: all 0.3s ease;">${icon('star')} Recalcular Rotação Inteligente</button>`;
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
                          if(cwlOverviewContainerEl) setHtml(cwlOverviewContainerEl, `<div class="error-text" style="grid-column: 1/-1;">Erro ao recalcular: ${escapeHtml(planData?.error || 'Tente novamente.')}</div>`);
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

    function renderWarSummaryBars(logData) {
        const container = document.getElementById('warSummaryBars');
        const recordEl = document.getElementById('warSummaryRecord');
        if (!container) return;

        if (!logData || !logData.log || logData.log.length === 0) {
            setHtml(container, '<span class="war-summary-loading">Nenhum dado de guerra disponível.</span>');
            return;
        }

        const recent = logData.log.slice(0, 10);
        let wins = 0, losses = 0, ties = 0;
        const totalScore = recent.reduce((acc, w) => {
            const cls = w.clan_stars || 0;
            const ops = w.opponent_stars || 0;
            if (w.result === 'Vitória') wins++;
            else if (w.result === 'Derrota') losses++;
            else ties++;
            return acc + (cls > ops ? 2 : cls === ops ? 1 : 0);
        }, 0);
        const maxPossible = recent.length * 2;
        const pct = maxPossible > 0 ? Math.round((totalScore / maxPossible) * 100) : 0;

        if (recordEl) setText(recordEl, `${wins}V ${losses}D ${ties}E (${pct}%)`);

        setHtml(container, recent.map(w => {
            const cls = w.clan_stars || 0;
            const ops = w.opponent_stars || 0;
            const resultClass = w.result === 'Vitória' ? 'win' : (w.result === 'Derrota' ? 'loss' : 'tie');
            const label = w.end_time_formatted ? w.end_time_formatted.split(' ')[0] : '?';
            return `<div class="war-summary-bar ${resultClass}" title="${escapeHtml(w.opponent_name || '?')}: ${cls} * vs ${ops} *">
                        <span class="wsb-result">${cls} <img src="${ASSETS_BASE_URL}/icons/Icon_HV_Attack_Star.png" class="star-icon" alt="*"></span>
                        <span class="wsb-label">${label}</span>
                        <span class="wsb-tooltip">${escapeHtml(w.opponent_name || '?')}<br>${cls}⭐ x ${ops}⭐</span>
                    </div>`;
        }).join(''));
    }

    function populateWarLog(data) {
        setText(warLogLimitEl, data?.log?.length || '0');

        renderWarSummaryBars(data);

        if (!data || data.error || !data.log?.length) {
            if(noWarLogMessageEl) { noWarLogMessageEl.style.display = 'block'; setText(noWarLogMessageEl, data?.error || "Log de guerra indisponível."); }
            setHtml(warLogTableBodyEl, `<tr><td colspan="6">${escapeHtml(data?.error || "Nenhum registo encontrado.")}</td></tr>`);
            return;
        }

        if(noWarLogMessageEl) noWarLogMessageEl.style.display = 'none';
        
        setHtml(warLogTableBodyEl, data.log.map(e => {
            const warId = e.war_id || e.id || e._id || '';
            return `
            <tr class="historic-war-row" data-war-id="${warId}">
                <td>${escapeHtml(e.end_time_formatted || '?')}</td>
                <td><img src="${e.opponent_badge_url || DEFAULT_BADGE_URL}" alt="Emblema" class="log-opponent-badge">${escapeHtml(e.opponent_name || 'N/A')}</td>
                <td>${e.clan_stars ?? '?'} <img src="${ASSETS_BASE_URL}/icons/Icon_HV_Attack_Star.png" class="star-icon" alt="*"> vs ${e.opponent_stars ?? '?'} <img src="${ASSETS_BASE_URL}/icons/Icon_HV_Attack_Star.png" class="star-icon" alt="*"></td>
                <td class="war-result-${e.result?.toLowerCase() || 'unknown'}">${escapeHtml(e.result || '?')}</td>
                <td>${e.team_size || '?'}</td>
                <td>${e.is_cwl ? "CWL" : "Normal"}</td>
            </tr>`;
        }).join(''));
    }

    // === FUNÇÃO CAPITAL COM EFEITO BLUR E CORREÇÃO DE AUSENTES ===
    function populateCapitalData(data) {
        if (!capitalBlurContentEl) return;

        const isRaidOngoing = data && data.raid && data.raid.state === "ongoing";

        if (!data || data.error || !data.raid || !isRaidOngoing) {
            if (noCapitalOverlayEl) noCapitalOverlayEl.style.display = 'flex';
            if (capitalBlurContentEl) capitalBlurContentEl.classList.add('cg-blurred-state');
            
            // Se não tem nem rastro de raid pra manter bonito borrado atrás, aborta.
            if (!data || !data.raid) return; 
        } else {
            if (noCapitalOverlayEl) noCapitalOverlayEl.style.display = 'none';
            if (capitalBlurContentEl) capitalBlurContentEl.classList.remove('cg-blurred-state');
        }

        const raid = data.raid;
        const members = data.members || [];

        const statusPt = raid.state === "ongoing" ? "Em Andamento" : "Finalizada";
        setText(capStatusEl, statusPt);
        if(capStatusEl) capStatusEl.className = `status-badge ${raid.state === "ongoing" ? 'status-warning' : 'status-success'}`;
        
        setText(capTotalLootEl, (raid.total_loot?.toLocaleString() || '0'));
        setText(capTotalAttacksEl, raid.total_attacks || '0');
        setText(capDestroyedEl, raid.destroyed_districts || '0');

        const topAttackers = members.slice(0, 5);
        const incompleteAttacks = members.filter(m => m.attacks > 0 && m.attacks < m.limit);

        // CRUZAMENTO DE DADOS: Pega quem tá no clã globalmente e não atacou
        let zeroAttacks = [];
        if (globalMembersList && globalMembersList.length > 0) {
            zeroAttacks = globalMembersList.filter(gm => {
                const attacker = members.find(m => m.tag === gm.tag);
                return !attacker || attacker.attacks === 0;
            });
        } else {
            zeroAttacks = members.filter(m => m.attacks === 0);
        }

        if (capTopAttackersListEl) {
            const medals = ['<span class="medal-rank medal-gold">1</span>', '<span class="medal-rank medal-silver">2</span>', '<span class="medal-rank medal-bronze">3</span>', '<span class="medal-rank">4</span>', '<span class="medal-rank">5</span>'];
            setHtml(capTopAttackersListEl, topAttackers.length > 0 && topAttackers[0].attacks > 0 ? topAttackers.map((m, i) => `
                <div class="podium-item ${i===0?'gold':i===1?'silver':i===2?'bronze':''}">
                    <span class="podium-rank">${medals[i] || `${i+1}.`}</span>
                    <div class="podium-details">
                        <div class="member-name">${escapeHtml(m.name)}</div>
                        <div class="donation-count"><strong>${m.looted.toLocaleString()}</strong> ouro (Ataques: ${m.attacks}/${m.limit})</div>
                    </div>
                </div>
            `).join('') : '<p style="padding: 15px;">Nenhum ataque registrado ainda.</p>');
        }

        // RENDERIZA A LISTA DE AUSENTES CONSERTADA
        if (capZeroAttacksListEl) {
            setHtml(capZeroAttacksListEl, zeroAttacks.length > 0 ? zeroAttacks.map(m => `
                <div style="padding: 10px 15px; border-bottom: 1px solid rgba(255,255,255,0.05); display: flex; justify-content: space-between; align-items: center;">
                    <strong>${escapeHtml(m.name)}</strong>
                    <span class="text-danger" style="font-weight:bold;">0 Ataques</span>
                </div>
            `).join('') : '<p class="text-success" style="padding: 15px; font-weight: bold;">Incrível! Todos do clã atacaram.</p>');
        }

        if (capIncompleteAttacksListEl) {
            setHtml(capIncompleteAttacksListEl, incompleteAttacks.length > 0 ? incompleteAttacks.map(m => `
                <div style="padding: 10px 15px; border-bottom: 1px solid rgba(255,255,255,0.05); display: flex; justify-content: space-between; align-items: center;">
                    <strong>${escapeHtml(m.name)}</strong>
                    <span class="text-warning" style="font-weight:bold;">Fez ${m.attacks} de ${m.limit}</span>
                </div>
            `).join('') : '<p style="padding: 15px;">Nenhum ataque incompleto.</p>');
        }
    }

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
                        <span>${i+1}.</span> <strong>${escapeHtml(m.name)}</strong> <span style="font-size: 0.8em; color: var(--color-text-secondary);">(${escapeHtml(m.role)})</span>
                    </div>
                    <div class="cg-player-score ${m.score >= maxPlayerPoints ? 'max-score' : ''}">
                        ${m.score.toLocaleString()}                         ${m.score >= maxPlayerPoints ? icon('star') : ''}
                    </div>
                </div>
            `).join('') : '<p style="padding: 15px;">Ninguém pontuou ainda.</p>');
        }

        if (cgZeroPlayersListEl) {
            setHtml(cgZeroPlayersListEl, zeroPlayers.length > 0 ? zeroPlayers.map(m => `
                <div class="cg-player-item">
                    <div class="cg-player-info"><strong>${escapeHtml(m.name)}</strong></div>
                    <div class="cg-player-score text-danger">0</div>
                </div>
            `)                    .join('') : '<p class="text-success" style="padding: 15px; font-weight:bold;">Todos pontuaram!</p>');
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
            setHtml(membersGridEl, `<p class="message-box">${escapeHtml(data?.error || "Não foi possível carregar os membros.")}</p>`);
            return;
        }

        const memberTagsMissingAttacks = new Set();
        globalMissedAttacks.forEach(w => {
            if (!w.is_latest) return;
            (w.missed_attacks_members || []).forEach(m => {
                if (m.tag) memberTagsMissingAttacks.add(m.tag);
            });
        });

        const featured = [];
        const regular = [];
        data.members.forEach(m => {
            if (m.cwl_status === 'priority' || m.admin_border === true) featured.push(m);
            else regular.push(m);
        });

        const buildMemberCard = (m) => {
            const hasMissedAttack = memberTagsMissingAttacks.has(m.tag);
            const watchlistClass = m.isOnWatchlist ? 'on-watchlist' : '';
            const missedAttackClass = hasMissedAttack ? 'missed-attack-member' : '';
            const watchlistIconHtml = m.isOnWatchlist ? '<span class="watchlist-icon" style="color:var(--color-warning);">&#9888;</span>' : '';
            const missedAttackIconHtml = hasMissedAttack ? '<span class="missed-attack-icon-member" style="color:var(--color-danger);" data-tooltip="Este membro não realizou todos os ataques na última guerra!">&#9888;</span>' : '';
            const watchlistTooltipHtml = m.isOnWatchlist
                ? `<span class="watchlist-tooltip">
                    <strong>Em Observação!</strong><br>
                    Motivo: ${escapeHtml(m.watchlistReason || 'Não especificado')}<br>
                    ${m.watchlistDetails ? `Detalhes: ${escapeHtml(m.watchlistDetails)}` : ''}
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
            const lastWarHtml = `<span title="Esta é a data da última guerra conhecida">${icon('sword')} ${escapeHtml(lastWarDateFormatted)}</span>`;

            const isPriority = m.cwl_status === 'priority';
            const priorityClass = isPriority ? 'vip-golden-card' : '';
            const vipRibbonHtml = isPriority ? `<div class="vip-ribbon">${icon('star')} TITULAR</div>` : '';

            const isAdminBorder = m.admin_border === true;
            const adminBorderClass = isAdminBorder ? 'vip-admin-border' : '';
            const adminRibbonHtml = isAdminBorder ? `<div class="vip-ribbon" style="background:linear-gradient(90deg,#ff0040,#b300ff,#00fff9);color:#fff;">${icon('shield')} ADMIN</div>` : '';

            return `
            <div class="member-card ${watchlistClass} ${priorityClass} ${adminBorderClass} ${missedAttackClass}" data-th="${escapeHtml(m.town_hall || '?')}" data-name="${escapeHtml((m.name || '').toLowerCase())}">
                ${vipRibbonHtml}${adminRibbonHtml}
                <div class="member-card-header" data-player-tag="${escapeHtml(m.tag || '')}">
                    <img src="${getAssetUrl('buildings/home-village', 'town_hall', m.town_hall || 1)}" alt="CV${escapeHtml(m.town_hall || '?')}" class="member-th-icon" onerror="this.onerror=null; this.src=DEFAULT_BADGE_URL; this.style.height='40px';">
                    <div class="member-info">
                        <h4>${escapeHtml(m.name || 'N/A')} ${watchlistIconHtml} ${missedAttackIconHtml}</h4>
                        <p>${escapeHtml(m.role || 'Membro')} • ${icon('trophy')} ${m.trophies || 0}</p>
                    </div>
                    ${watchlistTooltipHtml}
                </div>
                <div class="member-card-stats">
                    <span>Doadas: ${m.donations || 0}</span>
                    <span>Recebidas: ${m.received || 0}</span>
                    ${lastWarHtml} </div>
                <div class="member-card-note">
                    <div class="note-container note-priority-${notePriority}">
                        <span class="note-text">${escapeHtml(noteText)}</span>
                        <input type="text" class="note-input" value="${escapeHtml(m.note || '')}" style="display: none;">
                        <div class="priority-selector">
                            ${['green', 'yellow', 'red', 'none'].map(prio => `
                                <button class="priority-btn priority-${prio} ${prio === notePriority ? 'active' : ''}" data-priority="${prio}">
                                    ${prio === 'green' ? '✓' : prio === 'yellow' ? '!' : prio === 'red' ? '✗' : '×'}
                                </button>
                            `).join('')}
                        </div>
                    </div>
                </div>
                <div class="member-cwl-status" data-player-tag="${escapeHtml(m.tag || '')}">
                    <label>CWL:</label>
                    <div class="cwl-status-selector">
                        <button class="cwl-status-btn ${m.cwl_status === 'priority' ? 'active' : ''}" data-status="priority" title="Titular Absoluto (IA fura-fila)">${icon('star')} Fixo</button>
                        <button class="cwl-status-btn ${m.cwl_status === 'active' ? 'active' : ''}" data-status="active">Ativo</button>
                        <button class="cwl-status-btn ${m.cwl_status === 'backup' ? 'active' : ''}" data-status="backup">Reserva</button>
                    </div>
                    ${userIsAdmin ? `<button class="admin-border-btn ${isAdminBorder ? 'active' : ''}" data-player-tag="${escapeHtml(m.tag || '')}" title="Borda Animada de Admin">${icon('shield')} Admin</button>` : ''}
                </div>
            </div>`;
        };

        const featuredSection = featured.length
            ? `<div class="members-section">
                <div class="members-separator members-separator-featured">
                    <span class="members-separator-icon">${icon('star')}</span>
                    Fixos &amp; Admins
                    <span class="members-separator-count">${featured.length}</span>
                </div>
                <div class="members-grid">${featured.map(buildMemberCard).join('')}</div>
            </div>`
            : '';

        const regularSection = regular.length
            ? `<div class="members-section">
                <div class="members-separator">
                    <span class="members-separator-icon">${icon('shield')}</span>
                    Demais Membros
                    <span class="members-separator-count">${regular.length}</span>
                </div>
                <div class="members-grid">${regular.map(buildMemberCard).join('')}</div>
            </div>`
            : '';

        setHtml(membersGridEl, featuredSection + regularSection);

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
        document.querySelectorAll('.members-section').forEach(section => {
            const cards = [...section.querySelectorAll('.member-card')];
            const visible = cards.filter(c => c.style.display !== 'none').length;
            section.style.display = visible > 0 ? 'block' : 'none';
            const countEl = section.querySelector('.members-separator-count');
            if (countEl) countEl.textContent = visible;
        });
    }

    filterNameInput?.addEventListener('input', applyMemberFilters); 
    filterTHInput?.addEventListener('input', applyMemberFilters);

    function attachMemberEventListeners() {
        membersGridEl?.querySelectorAll('.member-card-header').forEach(header => {
            header.replaceWith(header.cloneNode(true)); 
        });
        membersGridEl?.querySelectorAll('.member-card-header').forEach(header => {
            header.addEventListener('click', () => openMemberProfileModal(header.dataset.playerTag));
        });

        if (!userIsAdmin) {
            return;
        }

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
        membersGridEl?.querySelectorAll('.admin-border-btn').forEach(btn => {
            btn.replaceWith(btn.cloneNode(true));
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
        membersGridEl?.querySelectorAll('.admin-border-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const playerTag = btn.dataset.playerTag;
                const isActive = btn.classList.contains('active');
                const newState = !isActive;
                btn.classList.toggle('active', newState);
                const success = await setPlayerAdminBorder(playerTag, newState);
                if (!success) {
                    alert('Erro ao salvar borda admin. Tente novamente.');
                    btn.classList.toggle('active', !newState);
                } else {
                    loadAllData();
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

    async function setPlayerAdminBorder(playerTag, enabled) {
        try {
            const response = await fetchData(`admin_border/${encodeURIComponent(playerTag)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            });
            return response && !response.error;
        } catch (e) {
            console.error("Erro ao definir borda admin:", e);
            return false;
        }
    }

    function formatTenure(joinedAtIso) {
        if (!joinedAtIso) return '—';
        const joined = new Date(joinedAtIso);
        if (isNaN(joined.getTime())) return '—';
        const now = new Date();
        let years = now.getFullYear() - joined.getFullYear();
        let months = now.getMonth() - joined.getMonth();
        let days = now.getDate() - joined.getDate();
        if (days < 0) {
            months -= 1;
            const prevMonth = new Date(now.getFullYear(), now.getMonth(), 0);
            days += prevMonth.getDate();
        }
        if (months < 0) {
            years -= 1;
            months += 12;
        }
        const parts = [];
        if (years > 0) parts.push(`${years} ${years === 1 ? 'ano' : 'anos'}`);
        if (months > 0) parts.push(`${months} ${months === 1 ? 'mês' : 'meses'}`);
        if (days > 0 || parts.length === 0) parts.push(`${days} ${days === 1 ? 'dia' : 'dias'}`);
        return parts.join(', ');
    }

    async function openMemberProfileModal(playerTag) {
        if (!playerTag || !memberProfileModal || !memberProfileContent) return;
        
        setHtml(memberProfileContent, '<div class="loading-spinner" style="margin: 40px auto;"></div><p style="text-align:center;">Conectando-se ao Modelo de Machine Learning...</p>');
        memberProfileModal.style.display = 'block';

        let basicData = {};
        if (globalMembersList && globalMembersList.length > 0) {
            basicData = globalMembersList.find(m => m.tag === playerTag) || {};
        } else {
            const membersData = await fetchData('members');
            if (membersData && !membersData.error && membersData.members) {
                basicData = membersData.members.find(m => m.tag === playerTag) || {};
            }
        }

        let detailedData = await fetchData(`player_profile/${encodeURIComponent(playerTag)}`);
        if (!detailedData || detailedData.error) {
             setHtml(memberProfileContent, `<p class="message-box">${escapeHtml(detailedData?.error || 'Erro ao comunicar com a IA e Supercell.')}</p>`);
             return;
        }

        const profileData = { ...basicData, ...detailedData };

        let lastWarDateFormatted = 'Sem Registro';
        if (profileData.last_war_date) {
            try {
                lastWarDateFormatted = new Date(profileData.last_war_date).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
            } catch (e) { lastWarDateFormatted = 'Inválida'; }
        }

        const isJoinedEstimate = profileData.membership_source === 'war_estimate';
        let joinedDateFormatted = 'Indeterminado';
        let tenureText = '—';
        if (profileData.joined_at) {
            try {
                const joinedDate = new Date(profileData.joined_at);
                if (isNaN(joinedDate.getTime())) throw new Error('invalid');
                joinedDateFormatted = joinedDate.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
                tenureText = formatTenure(profileData.joined_at);
            } catch (e) { joinedDateFormatted = 'Inválida'; }
        }

        const heroImageMap = {
            'barbarian king': 'barbarian king',
            'archer queen': 'archer queen',
            'grand warden': 'grand warden',
            'royal champion': 'royal champion',
            'minion prince': 'minion prince',
            'dragon duke': 'dragon duke'
        };

        const heroesHtml = profileData.heroes?.length > 0 ? profileData.heroes.map(hero => {
            const heroName = heroImageMap[(hero.name || '').toLowerCase()] || hero.name;
            const imgSrc = heroName ? getAssetUrl('heroes', heroName) : DEFAULT_BADGE_URL;
            return `
                <div class="hero-item-new">
                    <img src="${imgSrc}" alt="${escapeHtml(hero.name)}" onerror="this.src='${DEFAULT_BADGE_URL}'">
                    <div class="hero-lvl-box">${hero.level} <span style="font-size:0.7em;color:var(--color-text-secondary);">/ ${hero.max_level}</span></div>
                </div>`;
        }).join('') : '<p class="message-box" style="width:100%;">Nenhum herói da vila principal encontrado.</p>';

        const cwlStatus = profileData.cwl_status || 'active';
        const adminBorderEnabled = profileData.admin_border === true;
        
        const cwlStatusHtml = userIsAdmin ? `
            <div class="member-cwl-status" data-player-tag="${escapeHtml(profileData.tag || '')}" style="margin-bottom: 20px;">
                <label>Status na CWL:</label>
                <div class="cwl-status-selector">
                    <button class="cwl-status-btn ${cwlStatus === 'priority' ? 'active' : ''}" data-status="priority">${icon('star')} Fixo</button>
                    <button class="cwl-status-btn ${cwlStatus === 'active' ? 'active' : ''}" data-status="active">Ativo</button>
                    <button class="cwl-status-btn ${cwlStatus === 'backup' ? 'active' : ''}" data-status="backup">Backup</button>
                </div>
                <button class="admin-border-btn ${adminBorderEnabled ? 'active' : ''}" data-player-tag="${escapeHtml(profileData.tag || '')}" title="Borda Animada de Admin">${icon('shield')} Admin</button>
            </div>` : `
            <div class="member-cwl-status" style="margin-bottom: 20px; justify-content: flex-start; gap: 15px;">
                <label>Status CWL:</label>
                <span style="color: ${cwlStatus === 'priority' ? 'var(--color-accent)' : (cwlStatus === 'active' ? 'var(--color-success)' : 'var(--color-warning)')}; font-weight:bold;">${cwlStatus === 'priority' ? icon('star') + ' Titular Fixo' : (cwlStatus === 'active' ? 'Ativo' : 'Banco de Reservas')}</span>
                ${adminBorderEnabled ? '<span style="color:#b300ff;font-weight:bold;">' + icon('shield') + ' Admin</span>' : ''}
            </div>`;

        const hitrate = profileData.hitrate || { total_wars: 0, attacks_made: 0, attacks_missed: 0, total_stars: 0, three_star_attacks: 0, avg_destruction: 0 };
        const totalPossiveis = hitrate.attacks_made + hitrate.attacks_missed;
        const txParticipacao = totalPossiveis > 0 ? Math.round((hitrate.attacks_made / totalPossiveis) * 100) : 0;
        const tx3Estrelas = hitrate.attacks_made > 0 ? Math.round((hitrate.three_star_attacks / hitrate.attacks_made) * 100) : 0;
        const mediaEstrelas = hitrate.attacks_made > 0 ? (hitrate.total_stars / hitrate.attacks_made).toFixed(1) : "0.0";

        let corParticipacao = 'text-danger';
        if (txParticipacao >= 90) corParticipacao = 'text-success';
        else if (txParticipacao >= 50) corParticipacao = 'text-warning';

        // INTEGRAÇÃO COM O K-MEANS DO PYTHON
        const mlTier = profileData.tier || "Aguardando Dados";
        const mlProb = profileData.attack_probability !== undefined ? profileData.attack_probability : 0;
        
        let tierColor = "#a0aec0"; 
        let tierGlow = "rgba(160, 174, 192, 0.2)";
        if (mlTier.includes("General")) { tierColor = "#ffd700"; tierGlow = "rgba(255, 215, 0, 0.4)"; }
        else if (mlTier.includes("Especialista")) { tierColor = "#2ecc71"; tierGlow = "rgba(46, 204, 113, 0.4)"; }
        else if (mlTier.includes("Instável")) { tierColor = "#f39c12"; tierGlow = "rgba(243, 156, 18, 0.4)"; }
        else if (mlTier.includes("Risco") || mlTier.includes("Descartável")) { tierColor = "#e74c3c"; tierGlow = "rgba(231, 76, 60, 0.4)"; }

        const tierIcon = mlTier.includes("General") ? icon('trophy') : mlTier.includes("Especialista") ? icon('flag') : mlTier.includes("Instável") ? icon('sword') : mlTier.includes("Risco") || mlTier.includes("Descartável") ? icon('noStar') : icon('star');

        const brainMapHtml = `
            <div class="ia-diagnosis-card" style="--tier-color: ${tierColor}; --tier-glow: ${tierGlow};">
                <div class="ia-bg-icon" style="font-size:6rem;opacity:0.05;">IA</div>
                <div class="ia-scanline"></div>

                <div class="ia-header">
                    <div class="ia-header-left">
                        <span class="ai-indicator"></span>
                        <span class="ia-title">Diagnóstico Neural IA</span>
                    </div>
                    <span class="ia-wars-count">Base: Últimas ${hitrate.total_wars} Guerras</span>
                </div>

                <div class="ia-tier-section">
                    <div class="ia-tier-badge">
                        <span class="ia-tier-icon">${tierIcon}</span>
                        <div class="ia-tier-info">
                            <span class="ia-tier-label">Classificação (K-Means)</span>
                            <strong class="ia-tier-name" style="color: ${tierColor};">${escapeHtml(mlTier)}</strong>
                        </div>
                    </div>
                    <div class="ia-tier-badge ia-conf-badge">
                        <span class="ia-tier-icon"><img src="/assets/icons/Icon_HV_Sword.png" class="icon-sm"></span>
                        <div class="ia-tier-info">
                            <span class="ia-tier-label">Confiabilidade (R.Forest)</span>
                            <strong class="ia-conf-value" style="color: ${tierColor};">${mlProb.toFixed(1)}%</strong>
                        </div>
                    </div>
                </div>

                <div class="ia-metrics">
                    <div class="ia-metric ${corParticipacao}">
                        <span class="ia-metric-icon">${icon('flag')}</span>
                        <div class="ia-metric-body">
                            <span class="ia-metric-label">Assiduidade</span>
                            <strong class="ia-metric-value">${txParticipacao}%</strong>
                            <span class="ia-metric-sub">${hitrate.attacks_made}/${totalPossiveis} ataques</span>
                        </div>
                    </div>
                    <div class="ia-metric text-gold">
                        <span class="ia-metric-icon">${icon('sword')}</span>
                        <div class="ia-metric-body">
                            <span class="ia-metric-label">Poder de Fogo</span>
                            <strong class="ia-metric-value">${mediaEstrelas} ${icon('star')}</strong>
                            <span class="ia-metric-sub">Destruição Média: ${hitrate.avg_destruction}%</span>
                        </div>
                    </div>
                    <div class="ia-metric text-info">
                        <span class="ia-metric-icon">${icon('flag')}</span>
                        <div class="ia-metric-body">
                            <span class="ia-metric-label">Precisão Cirúrgica</span>
                            <strong class="ia-metric-value">${tx3Estrelas}%</strong>
                            <span class="ia-metric-sub">${hitrate.three_star_attacks} 3⭐</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const hasPercentil = typeof profileData.rank_trophies === 'number' && typeof profileData.rank_donations === 'number';
        const percentilHtml = hasPercentil ? `
            <div class="profile-percentil">
                <span class="profile-percentil-item">${icon('trophy')} Top ${profileData.pct_trophies}% em troféus <strong>(${profileData.rank_trophies}º)</strong></span>
                <span class="profile-percentil-item">${icon('goldPass')} Top ${profileData.pct_donations}% em doações <strong>(${profileData.rank_donations}º)</strong></span>
            </div>` : '';

        const warHistoryList = profileData.war_history || [];
        const warHistoryHtml = warHistoryList.length > 0 ? `
            <h3 class="profile-section-title">Carteira de Combate</h3>
            <div class="war-history-list">
                ${warHistoryList.map(w => {
                    const resultClass = w.result === 'Vitória' ? 'wh-win' : w.result === 'Derrota' ? 'wh-lose' : 'wh-tie';
                    const resultIcon = w.result === 'Vitória' ? icon('trophy') : w.result === 'Derrota' ? icon('noStar') : icon('shield');
                    let whDateFormatted = '—';
                    if (w.end_time_iso) {
                        try {
                            whDateFormatted = new Date(w.end_time_iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit' });
                        } catch (e) { whDateFormatted = '—'; }
                    }
                    return `
                    <div class="war-history-row">
                        <span class="war-history-result ${resultClass}">${resultIcon}</span>
                        <div class="war-history-info">
                            <strong>${escapeHtml(w.opponent_name || 'Desconhecido')}</strong>
                            <span>${escapeHtml(whDateFormatted)}${w.is_cwl ? ' • CWL' : ''}</span>
                        </div>
                        <div class="war-history-stats">
                            <span class="wh-stars">${w.stars} ${icon('star')}</span>
                            <span>${w.destruction || 0}%</span>
                            ${w.attacks_missed > 0 ? `<span class="wh-missed">${w.attacks_missed} perdido(s)</span>` : `<span class="wh-ok">completo</span>`}
                        </div>
                    </div>`;
                }).join('')}
            </div>` : '';

        setHtml(memberProfileContent, `
            <div class="profile-header-new">
                <div class="profile-league-badge">
                    <img src="${profileData.league_icon || DEFAULT_BADGE_URL}" alt="${escapeHtml(profileData.league || 'Liga')}" title="${escapeHtml(profileData.league || 'Sem Liga')}">
                </div>
                <div class="profile-title-new">
                    <h2>${escapeHtml(profileData.name || '?')} <img src="${getAssetUrl('buildings/home-village', 'town_hall', profileData.town_hall || 1)}" class="profile-th-icon" alt="CV" title="CV ${profileData.town_hall}" onerror="this.src=DEFAULT_BADGE_URL;"></h2>
                    <span class="profile-tag-new">${escapeHtml(profileData.tag || '#?')}</span>
                    <span class="profile-role-new">${escapeHtml(profileData.role || 'Membro')}</span>
                </div>
            </div>

            <div class="profile-stats-cards">
                <div class="p-card"><span class="p-icon">${icon('trophy')}</span><span class="p-val">${profileData.trophies || 0}</span><span class="p-label">Troféus</span></div>
                <div class="p-card"><span class="p-icon">${icon('flag')}</span><span class="p-val">${profileData.donations || 0}</span><span class="p-label">Doadas</span></div>
                <div class="p-card"><span class="p-icon">${icon('out')}</span><span class="p-val">${profileData.received || 0}</span><span class="p-label">Recebidas</span></div>
                <div class="p-card" title="Última guerra registrada no sistema">
                    <span class="p-icon">${icon('shield')}</span>
                    <span class="p-val" style="font-size:1em; margin-top:5px;">${escapeHtml(lastWarDateFormatted)}</span>
                    <span class="p-label">Últ. Guerra</span>
                </div>
                <div class="p-card" title="${isJoinedEstimate ? 'Data estimada pela 1ª guerra registrada no sistema' : 'Data de entrada no clã'}">
                    <span class="p-icon">${icon('in')}</span>
                    <span class="p-val" style="font-size:1em; margin-top:5px;">${escapeHtml(joinedDateFormatted)}${isJoinedEstimate ? '<span style="color:var(--color-text-secondary);font-size:0.8em;" title="Data estimada pela 1ª guerra registrada">*</span>' : ''}</span>
                    <span class="p-label">Entrada</span>
                </div>
                <div class="p-card" title="Tempo de casa (período atual no clã)">
                    <span class="p-icon">${icon('planet')}</span>
                    <span class="p-val" style="font-size:1em; margin-top:5px;">${escapeHtml(tenureText)}</span>
                    <span class="p-label">Tempo de Casa</span>
                </div>
            </div>
            
            ${percentilHtml}
            ${cwlStatusHtml}
            ${brainMapHtml}

            ${(globalMissedAttacks.filter(w => (w.missed_attacks_members || []).some(m => m.tag === profileData.tag)).length > 0) ? `
            <h3 class="profile-section-title">Registro de Ataques Perdidos</h3>
            <div style="background:rgba(0,0,0,0.25);border-radius:var(--border-radius-base);padding:15px;border:1px solid var(--color-border);margin-bottom:25px;">
                ${globalMissedAttacks.filter(w => (w.missed_attacks_members || []).some(m => m.tag === profileData.tag)).map(w => {
                    const playerMissed = w.missed_attacks_members.find(m => m.tag === profileData.tag);
                    if (!playerMissed) return '';
                    return `
                    <div style="display:flex;justify-content:space-between;align-items:center;padding:10px;border-bottom:1px solid var(--color-divider);gap:10px;">
                        <div style="display:flex;align-items:center;gap:10px;">
                            <span style="font-size:1.3em;">${icon('sword')}</span>
                            <div>
                                <strong style="color:var(--color-text-main);">vs ${escapeHtml(w.opponent_name || 'Desconhecido')}</strong><br>
                                <span style="font-size:0.85em;color:var(--color-text-secondary);">${escapeHtml(w.end_date || 'Data?')}</span>
                            </div>
                        </div>
                        <div style="text-align:right;">
                            <span style="background:rgba(255,0,64,0.2);color:var(--neon-red);padding:4px 10px;border-radius:4px;font-weight:700;font-size:0.9em;">
                                ${playerMissed.attacks_left} ataque(s) perdido(s)
                            </span>
                        </div>
                    </div>`;
                }).join('')}
            </div>` : ''}

            ${warHistoryHtml}

            <h3 class="profile-section-title">Progresso de Heróis</h3>
            <div class="profile-heroes-grid">
                ${heroesHtml}
            </div>

            ${profileData.pets?.length > 0 ? `
            <h3 class="profile-section-title">Pets</h3>
            <div class="profile-heroes-grid">
                ${profileData.pets.map(pet => {
                    const imgSrc = getAssetUrl('pets', pet.name);
                    return `
                        <div class="hero-item-new">
                            <img src="${imgSrc}" alt="${escapeHtml(pet.name)}" onerror="this.src='${DEFAULT_BADGE_URL}'">
                            <div class="hero-lvl-box">${pet.level} <span style="font-size:0.7em;color:var(--color-text-secondary);">/ ${pet.max_level}</span></div>
                        </div>`;
                }).join('')}
            </div>` : ''}

            ${profileData.troops?.length > 0 ? `
            <h3 class="profile-section-title">Tropas</h3>
            <div class="profile-heroes-grid">
                ${profileData.troops.map(troop => {
                    const imgSrc = getAssetUrl('troops', troop.name);
                    return `
                        <div class="hero-item-new">
                            <img src="${imgSrc}" alt="${escapeHtml(troop.name)}" onerror="this.src='${DEFAULT_BADGE_URL}'">
                            <div class="hero-lvl-box">${troop.level} <span style="font-size:0.7em;color:var(--color-text-secondary);">/ ${troop.max_level}</span></div>
                        </div>`;
                }).join('')}
            </div>` : ''}

            ${profileData.spells?.length > 0 ? `
            <h3 class="profile-section-title">Feitiços</h3>
            <div class="profile-heroes-grid">
                ${profileData.spells.map(spell => {
                    const imgSrc = getAssetUrl('spells', spell.name);
                    return `
                        <div class="hero-item-new">
                            <img src="${imgSrc}" alt="${escapeHtml(spell.name)}" onerror="this.src='${DEFAULT_BADGE_URL}'">
                            <div class="hero-lvl-box">${spell.level} <span style="font-size:0.7em;color:var(--color-text-secondary);">/ ${spell.max_level}</span></div>
                        </div>`;
                }).join('')}
            </div>` : ''}

            ${profileData.equipment?.length > 0 ? `
            <h3 class="profile-section-title">Equipamentos</h3>
            <div class="profile-heroes-grid">
                ${profileData.equipment.map(eq => {
                    const imgSrc = getAssetUrl('equipment', eq.name);
                    return `
                        <div class="hero-item-new">
                            <img src="${imgSrc}" alt="${escapeHtml(eq.name)}" onerror="this.src='${DEFAULT_BADGE_URL}'">
                            <div class="hero-lvl-box">${eq.level} <span style="font-size:0.7em;color:var(--color-text-secondary);">/ ${eq.max_level}</span></div>
                        </div>`;
                }).join('')}
            </div>` : ''}

            <div class="profile-actions-bar" style="display:flex; gap:10px; margin-top:15px; flex-wrap:wrap; justify-content:center;">
                <button class="control-btn profile-upgrade-btn" data-tag="${escapeHtml(profileData.tag)}" style="background:linear-gradient(135deg,#b300ff,#ff00aa); color:#fff; border:none; padding:8px 16px; border-radius:6px; cursor:pointer; font-family:'Rajdhani',sans-serif; font-weight:600; font-size:0.9em;">
                    Upgrades
                </button>
                ${userIsAdmin ? `<button class="control-btn profile-export-btn" data-tag="${escapeHtml(profileData.tag)}" data-name="${escapeHtml(profileData.name)}" style="background:linear-gradient(135deg,#00fff9,#0080ff); color:#fff; border:none; padding:8px 16px; border-radius:6px; cursor:pointer; font-family:'Rajdhani',sans-serif; font-weight:600; font-size:0.9em;">
                    Exportar
                </button>` : ''}
            </div>

            <div class="profile-chart-container">
                <h3 class="profile-section-title">Radar de Performance</h3>
                <div class="radar-chart-wrapper">
                    <canvas id="trophyChart"></canvas>
                </div>
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
                         fetchData('members').then(d => { if(d && !d.error){ globalMembersList = d.members; populateMembersList(d); } });
                    }
                });
            });
            memberProfileContent.querySelectorAll('.admin-border-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const playerTag = btn.dataset.playerTag;
                    const isActive = btn.classList.contains('active');
                    const newState = !isActive;
                    btn.classList.toggle('active', newState);
                    const success = await setPlayerAdminBorder(playerTag, newState);
                    if (!success) {
                        alert('Erro ao salvar borda admin.');
                        btn.classList.toggle('active', !newState);
                    } else {
                        fetchData('members').then(d => { if(d && !d.error){ globalMembersList = d.members; populateMembersList(d); } });
                    }
                });
            });
        }

        const upgradeTranslations = {
            'Town Hall': 'Prefeitura',
            'Cannon': 'Canhão', 'Archer Tower': 'Torre Arqueira', 'Mortar': 'Morteiro',
            'Wizard Tower': 'Torre Mago', 'Air Defense': 'Defesa Aérea', 'Tesla': 'Torre Tesla',
            'Bomb Tower': 'Torre Bomba', 'Inferno Tower': 'Torre Inferno', 'X-Bow': 'Balista',
            'Eagle Artillery': 'Águia Artilheira', 'Scattershot': 'Tiroteio', 'Builder Hut': 'Cabana Construtor',
            'Hidden Tesla': 'Torre Tesla', 'Giga Tesla': 'Torre Giga', 'Giga Inferno': 'Inferno Giga',
            'Spell Tower': 'Torre Feitiço', 'Monolith': 'Monólito',
            'Barbarian': 'Bárbaro', 'Archer': 'Arqueira', 'Goblin': 'Goblin', 'Giant': 'Gigante',
            'Wall Breaker': 'Rompe Muros', 'Balloon': 'Globo', 'Wizard': 'Mago', 'Healer': 'Curandeira',
            'Dragon': 'Dragão', 'PEKKA': 'P.E.K.K.A.', 'Baby Dragon': 'Bebê Dragão', 'Miner': 'Mineiro',
            'Electro Dragon': 'Elétro Dragão', 'Yeti': 'Yeti', 'Dragon Rider': 'Cavaleiro Dragão',
            'Electro Titan': 'Titã Elétrica', 'Root Rider': 'Cavaleiro Raiz',
            'Minion': 'Esbirro', 'Hog Rider': 'Jinete Porco', 'Valkyrie': 'Valquíria',
            'Golem': 'Golem', 'Witch': 'Bruxa', 'Lava Hound': 'Cão de Lava', 'Bowler': 'Boleador',
            'Ice Golem': 'Golem de Gelo', 'Headhunter': 'Caçadora',
            'Apprentice Warden': 'Sentinela Aprendiz', 'Druid': 'Druida',
            'Super Barbarian': 'Super Bárbaro', 'Super Archer': 'Super Arqueira', 'Super Giant': 'Super Gigante',
            'Sneaky Goblin': 'Goblin Sorrateiro', 'Super Wall Breaker': 'Super Rompe Muros', 'Super Wizard': 'Super Mago',
            'Inferno Dragon': 'Dragão Inferno', 'Super Miner': 'Super Mineiro', 'Super Bowler': 'Super Boleador',
            'Ice Hound': 'Cão de Gelo', 'Super Dragon': 'Super Dragão',
            'Raged Barbarian': 'Bárbaro Irritado', 'Sneaky Archer': 'Arqueira Sorrateira',
            'Beta Minion': 'Esbirro Beta', 'Boxer Giant': 'Gigante Boxeador', 'Bomber': 'Bombardeiro',
            'Power P.E.K.K.A': 'P.E.K.K.A Poderosa', 'Cannon Cart': 'Canhão Carroça',
            'Drop Ship': 'Nave Desembarque', 'Night Witch': 'Bruxa Noturna',
            'Thrower': 'Arremessadora', 'Troop Launcher': 'Lançadora Tropas',
            'Furnace': 'Fornalha', 'Meteor Golem': 'Golem Meteoro', 'Sky Wagon': 'Carroça Voadora',
            'Wall Wrecker': 'Aríete', 'Battle Blimp': 'Dirigível de Guerra',
            'Stone Slammer': 'Esmaga Pedras', 'Siege Barracks': 'Quartel de Cerco',
            'Log Launcher': 'Lançadora de Toras', 'Battle Drill': 'Perfuratriz de Guerra',
            'Barbarian King': 'Rei Bárbaro', 'Archer Queen': 'Rainha Arqueira', 'Grand Warden': 'Grande Sentinela',
            'Royal Champion': 'Campeã Real', 'Minion Prince': 'Príncipe Esbirro',
            'Battle Machine': 'Máquina de Guerra', 'Battle Copter': 'Helicóptero de Guerra',
            'Lightning Spell': 'Feitiço Raio', 'Healing Spell': 'Feitiço Cura', 'Rage Spell': 'Feitiço Fúria',
            'Jump Spell': 'Feitiço Salto', 'Freeze Spell': 'Feitiço Congelar', 'Clone Spell': 'Feitiço Clone',
            'Invisibility Spell': 'Feitiço Invisibilidade', 'Bat Spell': 'Feitiço Morcego',
            'Recall Spell': 'Feitiço Recolher', 'Poison Spell': 'Feitiço Veneno', 'Earthquake Spell': 'Feitiço Terremoto',
            'Haste Spell': 'Feitiço Pressa', 'Skeleton Spell': 'Feitiço Esqueleto',
            'Lightning': 'Feitiço Raio', 'Healing': 'Feitiço Cura', 'Rage': 'Feitiço Fúria',
            'Jump': 'Feitiço Salto', 'Freeze': 'Feitiço Congelar', 'Clone': 'Feitiço Clone',
            'Invisibility': 'Feitiço Invisibilidade', 'Bat': 'Feitiço Morcego',
            'Recall': 'Feitiço Recolher', 'Poison': 'Feitiço Veneno', 'Earthquake': 'Feitiço Terremoto',
            'Haste': 'Feitiço Pressa', 'Skeleton': 'Feitiço Esqueleto',
            'Revive Spell': 'Feitiço Reviver', 'Totem Spell': 'Feitiço Totem',
            'Overgrowth Spell': 'Feitiço Vegetação', 'Ice Block Spell': 'Feitiço Bloco Gelo',
            'Revive': 'Feitiço Reviver', 'Totem': 'Feitiço Totem',
            'Overgrowth': 'Feitiço Vegetação', 'Ice Block': 'Feitiço Bloco Gelo',
            'L.A.S.S.I.': 'L.A.S.S.I.', 'L.A.S.S.I': 'L.A.S.S.I.', 'Electro Owl': 'Coruja Elétrica', 'Mighty Yak': 'Yak Poderoso',
            'Unicorn': 'Unicórnio', 'Frosty': 'Congelado', 'Diggy': 'Cavador', 'Poison Lizard': 'Lagarto Venenoso',
            'Spirit Fox': 'Raposa Espiritual', 'Angry Jelly': 'Geléia Nervosa', 'Sneezer': 'Espirrador', 'Sneezy': 'Espirrador',
            'Gingerbread Pup': 'Filhote Pão Mel', 'Phoenix': 'Fênix', 'Toad': 'Sapo',
            'Life Gem': 'Gema Vida', 'Rage Gem': 'Gema Fúria', 'Healing Tome': 'Tomo Cura', 'Eternal Tome': 'Tomo Eterno',
            'Stun Trap': 'Armadilha Atordoar', 'Tornado Trap': 'Armadilha Tornado',
            'Seeking Air Mine': 'Mina Aérea Busca', 'Skeleton Trap': 'Armadilha Esqueleto',
            'Giant Bomb': 'Bomba Gigante', 'Air Bomb': 'Bomba Aérea',
            'Bomb': 'Bomba', 'Spring Trap': 'Armadilha Mola',
            'Barracks': 'Quartel', 'Army Camp': 'Acampamento', 'Laboratory': 'Laboratório',
            'Spell Factory': 'Fábrica Feitiços', 'Dark Barracks': 'Quartel Negro', 'Dark Spell Factory': 'Fábrica Feitiços Negro',
            'Clan Castle': 'Castelo Clã', 'Silo': 'Silo', 'Workshop': 'Oficina',
            'Pet House': 'Casa Companheiros', 'Blacksmith': 'Ferreiro',
            'Gold Mine': 'Mina Ouro', 'Elixir Collector': 'Coletor Elixir', 'Dark Elixir Drill': 'Perfuratriz Elixir N',
            'Gold Storage': 'Armazém Ouro', 'Elixir Storage': 'Armazém Elixir', 'Dark Elixir Storage': 'Armazém Elixir N',
            'Militia': 'Milícia',
        };
        function translateName(name) {
            const t = upgradeTranslations[name];
            return t || name;
        }

        memberProfileContent.querySelector('.profile-upgrade-btn')?.addEventListener('click', async (e) => {
            const tag = e.target.dataset.tag;
            if (!tag) return;

            let existing = memberProfileContent.querySelector('.profile-upgrades-container');
            if (existing) {
                existing.remove();
                return;
            }

            try {
                const data = await fetchData('player_upgrades/' + encodeURIComponent(tag));
                if (data.error) { alert('ERRO: ' + data.error); return; }

                const hasCosts = data.total_gold || data.total_elixir || data.total_dark_elixir;
                const hasTime = data.total_time_seconds && data.total_time_seconds > 0;

                const groups = {};
                for (const u of (data.upgrades || [])) {
                    const type = u.item_type || 'other';
                    u.displayName = translateName(u.name);
                    if (!groups[type]) groups[type] = [];
                    groups[type].push(u);
                }

                const typeIcons = { building: icon('flag'), troop: icon('sword'), hero: icon('trophy'), spell: icon('star'), pet: icon('flag'), equipment: icon('shield') };
                const typeLabels = { building: 'Construções', troop: 'Tropas', hero: 'Heróis', spell: 'Feitiços', pet: 'Companheiros', equipment: 'Equipamentos' };

                let thLabel = data.current_th;
                if (data.target_th && data.target_th !== data.current_th) {
                    thLabel += ` → TH${data.target_th}`;
                }
                let upgradesHtml = `<div class="profile-upgrades-container" style="margin-top:15px;padding:14px;background:rgba(0,255,249,0.1);border:1px solid rgba(0,255,249,0.4);border-radius:10px;box-shadow:0 0 15px rgba(0,255,249,0.15);">`;
                upgradesHtml += `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <h4 style="margin:0;color:#00fff9;text-shadow:0 0 10px rgba(0,255,249,0.4);">Upgrades — ${escapeHtml(data.name)}</h4>
                    <span style="color:#0ff;font-size:0.85em;background:rgba(0,255,249,0.1);padding:2px 10px;border-radius:10px;border:1px solid rgba(0,255,249,0.3);">TH${thLabel}</span>
                    <span style="font-size:0.75em;color:#888;background:rgba(255,255,255,0.05);padding:0 8px;border-radius:4px;">${data._has_th_table === true ? '<img src="/assets/icons/Icon_HV_Podium.png" class="icon-sm"> v4.2.1' : data._has_th_table === false ? 'GeniusLib antiga' : ''}</span>
                </div>`;
                upgradesHtml += `<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;font-size:0.9em;color:#fff;">`;
                upgradesHtml += `<span style="background:rgba(255,255,255,0.06);padding:2px 10px;border-radius:6px;">${data.total_upgrades} upgrades</span>`;
                if (hasCosts) {
                    if (data.total_gold) upgradesHtml += `<span style="background:rgba(255,255,255,0.06);padding:2px 10px;border-radius:6px;">${data.total_gold.toLocaleString()} Ouro</span>`;
                    if (data.total_elixir) upgradesHtml += `<span style="background:rgba(255,255,255,0.06);padding:2px 10px;border-radius:6px;">${data.total_elixir.toLocaleString()} Elixir</span>`;
                    if (data.total_dark_elixir) upgradesHtml += `<span style="background:rgba(255,255,255,0.06);padding:2px 10px;border-radius:6px;">${data.total_dark_elixir.toLocaleString()} Elixir N</span>`;
                } else {
                    upgradesHtml += `<span style="background:rgba(255,255,255,0.06);padding:2px 10px;border-radius:6px;color:#ffaa00;">Custos não disponíveis</span>`;
                }
                if (hasTime) {
                    upgradesHtml += `<span style="background:rgba(255,255,255,0.06);padding:2px 10px;border-radius:6px;">~${data.estimated_real_time_days} dias (${data.builder_count} construtores)</span>`;
                }
                upgradesHtml += `</div>`;

                for (const [type, items] of Object.entries(groups)) {
                    const icon = typeIcons[type] || '<img src="/assets/icons/Icon_HV_Shield.png" class="icon-sm">';
                    const label = typeLabels[type] || type;
                    const withCostType = type === 'building' || type === 'troop' || type === 'hero';
                    upgradesHtml += `<details style="margin-bottom:4px;" ${type === 'building' ? 'open' : ''}>
                        <summary style="cursor:pointer;color:#ff66cc;font-weight:600;font-size:0.9em;">${icon} ${label} <span style="color:#aaa;font-weight:400;">(${items.length})</span></summary>
                        <div style="max-height:250px;overflow-y:auto;margin-top:4px;padding-left:8px;background:rgba(0,0,0,0.2);border-radius:6px;padding:4px 6px;">`;
                    for (const u of items) {
                        let costs = [];
                        if (u.gold) costs.push(`${u.gold.toLocaleString()} O`);
                        if (u.elixir) costs.push(`${u.elixir.toLocaleString()} E`);
                        if (u.dark_elixir) costs.push(`${u.dark_elixir.toLocaleString()} EN`);
                        upgradesHtml += `<div style="padding:3px 0;font-size:0.88em;color:#eee;border-bottom:1px solid rgba(255,255,255,0.06);display:flex;justify-content:space-between;align-items:center;">
                            <span>${u.displayName} <span style="color:#999;font-size:0.9em;">${u.from_level} → ${u.to_level}</span></span>
                            <span style="color:#0ff;font-size:0.85em;">${costs.length ? costs.join(' ') : ''}</span>
                        </div>`;
                    }
                    upgradesHtml += `</div></details>`;
                }

                upgradesHtml += `<div style="text-align:right;margin-top:8px;">
                    <button onclick="this.closest('.profile-upgrades-container').remove()" style="background:rgba(255,0,170,0.15);border:1px solid #ff00aa;color:#ff66cc;padding:5px 16px;border-radius:6px;cursor:pointer;font-size:0.85em;transition:0.2s;" onmouseover="this.style.background='rgba(255,0,170,0.3)'" onmouseout="this.style.background='rgba(255,0,170,0.15)'">Fechar</button>
                </div>`;
                upgradesHtml += `</div>`;

                memberProfileContent.querySelector('.profile-actions-bar').insertAdjacentHTML('afterend', upgradesHtml);
            } catch (err) {
                alert('ERRO: Erro ao buscar upgrades.');
            }
        });

        memberProfileContent.querySelector('.profile-export-btn')?.addEventListener('click', async (e) => {
            const tag = e.target.dataset.tag;
            const name = e.target.dataset.name;
            if (!tag) return;
            try {
                const profileData = await fetchData('player_profile/' + encodeURIComponent(tag));
                if (profileData.error) { alert('ERRO: ' + profileData.error); return; }
                const json = JSON.stringify(profileData, null, 2);
                const blob = new Blob([json], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${name || tag}_profile.json`.replace(/[^a-zA-Z0-9_#]/g, '_');
                a.click();
                URL.revokeObjectURL(url);
            } catch (err) {
                alert('ERRO: Erro ao exportar.');
            }
        });

        if (memberTrophyChart) memberTrophyChart.destroy();
        const radarCanvas = document.getElementById('trophyChart');
        if (!radarCanvas) return;

        const hr = profileData.hitrate || {};
        const totalWars = (hr.attacks_made || 0) + (hr.attacks_missed || 0);

        const poderFogo = hr.attacks_made > 0 ? Math.min((hr.total_stars / hr.attacks_made) / 3 * 100, 100) : 0;
        const precisao = hr.attacks_made > 0 ? Math.min((hr.three_star_attacks / hr.attacks_made) * 100, 100) : 0;
        const assiduidade = totalWars > 0 ? Math.min((hr.attacks_made / totalWars) * 100, 100) : 0;
        const confiabilidade = profileData.attack_probability !== undefined ? Math.min(profileData.attack_probability * 100, 100) : 50;
        const destruicao = hr.avg_destruction ? Math.min(parseFloat(hr.avg_destruction), 100) : 0;
        const doacoesNorm = Math.min(((profileData.donations || 0) / 5000) * 100, 100);

        const neonCyan = 'rgba(0, 255, 249, 1)';
        const neonPink = 'rgba(255, 0, 170, 1)';
        const neonBg = 'rgba(0, 255, 249, 0.08)';
        const gridColor = 'rgba(0, 255, 249, 0.15)';

        memberTrophyChart = new Chart(radarCanvas.getContext('2d'), {
            type: 'radar',
            data: {
                labels: ['Poder de Fogo', 'Precisão 3⭐', 'Assiduidade', 'Confiabilidade IA', 'Destruição', 'Doações'],
                datasets: [{
                    data: [poderFogo, precisao, assiduidade, confiabilidade, destruicao, doacoesNorm],
                    backgroundColor: 'rgba(0, 255, 249, 0.08)',
                    borderColor: neonCyan,
                    borderWidth: 2,
                    pointBackgroundColor: neonCyan,
                    pointBorderColor: '#0a0a0f',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 7
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: {
                        min: 0,
                        max: 100,
                        ticks: { display: false },
                        grid: { color: gridColor, circular: true },
                        angleLines: { color: gridColor },
                        pointLabels: {
                            color: '#d4d4e8',
                            font: { family: "'Rajdhani', sans-serif", size: 12, weight: '500' }
                        }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.raw.toFixed(1)}%`
                        }
                    }
                }
            }
        });
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

    document.querySelectorAll('.ranked-tab-button').forEach(button => {
        button?.addEventListener('click', () => {
            const parent = button.closest('.ranked-tabs');
            if (!parent) return;
            const section = parent.closest('.ranked-card');
            if (!section) return;
            section.querySelectorAll('.ranked-tab-button').forEach(btn => btn.classList.remove('ranked-tab-active'));
            button.classList.add('ranked-tab-active');
            const tabId = button.dataset.rankedTab;
            section.querySelectorAll('.ranked-tab-content').forEach(content => {
                content.classList.toggle('ranked-tab-active', content.id === tabId);
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

            if (membersData && !membersData.error) {
                globalMembersList = membersData.members; 
                populateMembersList(membersData);
            }
            
            if (currentWarDetailsData) {
                populateWarDetails(currentWarDetailsData, 'war-details-nav', false);
                window.__warData = currentWarDetailsData.war_data || {};
            }
            const warState = currentWarDetailsData?.war_data?.status || '';
            if (warAdvisorData) populateWarAdvisorPlan(warAdvisorData, warState); 
            if (missedAttacksData && !missedAttacksData.error) {
                populateMissedAttacksHistory(missedAttacksData);
                globalMissedAttacks = missedAttacksData.wars_with_missed_attacks || [];
            }
            if (warLogData && !warLogData.error) populateWarLog(warLogData);
            if (cwlPlanData) populateCwlData(cwlPlanData); 
            if (highlightsData && !highlightsData.error) populateHighlights(highlightsData); 
            if (capitalData) populateCapitalData(capitalData);
            if (clanGamesData) populateClanGamesData(clanGamesData);

            updateLastUpdated();
            initTooltips();
            addWarWarningTooltips();
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

    async function refreshActiveSection() {
        const activeId = currentActiveSectionId;
        if (!activeId) return;
        try {
            const statusData = await fetch('/api/status').then(res => res.ok ? res.json() : { is_admin: false }).catch(() => ({ is_admin: false }));
            userIsAdmin = statusData.is_admin || false;

            const s = activeId;
            if (s === 'clan-info-nav') {
                const d = await fetchData('clan');
                populateClanInfo(d);
                const wl = await fetchData('war_log');
                if (wl && !wl.error) populateWarLog(wl);
            } else if (s === 'highlights-nav') {
                const d = await fetchData('highlights');
                if (d && !d.error) populateHighlights(d);
            } else if (s === 'war-details-nav') {
                const [wd, wa] = await Promise.all([fetchData('current_war_details'), fetchData('war_advisor_plan')]);
                if (wd) {
                    populateWarDetails(wd, 'war-details-nav', false);
                    window.__warData = wd.war_data || {};
                }
                const warState = wd?.war_data?.status || '';
                if (wa) populateWarAdvisorPlan(wa, warState);
            } else if (s === 'attacks-remaining-nav') {
                const d = await fetchData('missed_attacks_history');
                if (d && !d.error) populateMissedAttacksHistory(d);
            } else if (s === 'cwl-info-nav') {
                const d = await fetchData('cwl/generate_plan', { method: 'POST' });
                if (d) populateCwlData(d);
            } else if (s === 'clan-games-nav') {
                const d = await fetchData('clan_games');
                if (d) populateClanGamesData(d);
            } else if (s === 'capital-nav') {
                const d = await fetchData('capital');
                if (d) populateCapitalData(d);
            } else if (s === 'war-log-nav') {
                const d = await fetchData('war_log');
                if (d && !d.error) populateWarLog(d);
            } else if (s === 'members-list-nav') {
                const [d, ma] = await Promise.all([fetchData('members'), fetchData('missed_attacks_history')]);
                if (d && !d.error) { globalMembersList = d.members; populateMembersList(d); }
                if (ma && !ma.error) { globalMissedAttacks = ma.wars_with_missed_attacks || []; }
            } else if (s === 'ranked-nav') {
                const [d, ts] = await Promise.all([fetchData('members'), fetchData('tournament')]);
                if (d && !d.error) { populateRankedActivity(d); populateRankedStats(d); }
                if (ts && !ts.error) populateRankedTournament(ts);
            }
            updateLastUpdated();
        } catch (e) {
            console.error('Erro no refresh seletivo:', e);
        }
    }

    // === LEGEND LEAGUE TAB ===
    const legendPlayerTagEl = document.getElementById('legendPlayerTag');
    const legendFetchBtnEl = document.getElementById('legendFetchBtn');
    const legendErrorEl = document.getElementById('legendError');
    const legendLoadingEl = document.getElementById('legendLoading');
    const legendContentEl = document.getElementById('legendContent');

    function escapeHtmlLegend(str) {
        if (!str) return '-';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    document.getElementById('legendArmyStats').addEventListener('click', function(ev) {
        const btn = ev.target.closest('.army-copy-btn');
        if (!btn || !btn.dataset.armyCode) return;
        navigator.clipboard.writeText(btn.dataset.armyCode).then(() => {
            btn.textContent = '✓ Copiado!';
            btn.classList.add('copied');
            setTimeout(() => { btn.textContent = 'Copiar'; btn.classList.remove('copied'); }, 2000);
        });
    });

    function populateLegendSummary(data) {
        setText(legendErrorEl, '');
        legendErrorEl.style.display = 'none';
        legendContentEl.style.display = 'block';

        const winRate = data.win_rate;
        const atkAvgDestruction = data.attacks?.avg_destruction;
        const atkAvgStars = data.attacks?.avg_stars;
        const consistency = data.consistency;

        setText(document.getElementById('legendWinRate'), winRate !== undefined && winRate !== null ? `${winRate}%` : '-');
        setText(document.getElementById('legendAvgDestruction'), atkAvgDestruction !== undefined && atkAvgDestruction !== null ? `${atkAvgDestruction}%` : '-');
        setText(document.getElementById('legendAvgStars'), atkAvgStars !== undefined && atkAvgStars !== null ? `${atkAvgStars}` : '-');
        setText(document.getElementById('legendConsistency'), consistency !== undefined && consistency !== null ? `${consistency}%` : '-');

        const atkContainer = document.getElementById('legendAttackStats');
        if (data.attacks && data.attacks.total_attacks > 0) {
            const a = data.attacks;
            setHtml(atkContainer, `
                <div class="legend-detail-grid">
                    <div class="legend-detail-item"><span>Total de Ataques:</span><strong>${a.total_attacks}</strong></div>
                    <div class="legend-detail-item"><span>Vitórias:</span><strong>${a.wins}</strong></div>
                    <div class="legend-detail-item"><span>Derrotas:</span><strong>${a.losses}</strong></div>
                    <div class="legend-detail-item"><span>Estrelas Médias:</span><strong>${a.avg_stars}</strong></div>
                    <div class="legend-detail-item"><span>Destruição Média:</span><strong>${a.avg_destruction}%</strong></div>
                    <div class="legend-detail-item"><span>Total Estrelas:</span><strong>${a.total_stars}</strong></div>
                </div>
            `);
        } else {
            setHtml(atkContainer, '<p class="message-box">Nenhum ataque registrado.</p>');
        }

        const defContainer = document.getElementById('legendDefenseStats');
        if (data.defenses && data.defenses.total_defenses > 0) {
            const d = data.defenses;
            setHtml(defContainer, `
                <div class="legend-detail-grid">
                    <div class="legend-detail-item"><span>Total de Defesas:</span><strong>${d.total_defenses}</strong></div>
                    <div class="legend-detail-item"><span>Vitórias Defensivas:</span><strong>${d.wins}</strong></div>
                    <div class="legend-detail-item"><span>Derrotas Defensivas:</span><strong>${d.losses}</strong></div>
                    <div class="legend-detail-item"><span>Estrelas Concedidas Médias:</span><strong>${d.avg_stars_received}</strong></div>
                    <div class="legend-detail-item"><span>Destruição Concedida Média:</span><strong>${d.avg_destruction_received}%</strong></div>
                    <div class="legend-detail-item"><span>Total Estrelas Recebidas:</span><strong>${d.total_stars_received}</strong></div>
                </div>
            `);
        } else {
            setHtml(defContainer, '<p class="message-box">Nenhuma defesa registrada.</p>');
        }

        const lootContainer = document.getElementById('legendLootStats');
        if (data.loot && data.loot.total_looted > 0) {
            const l = data.loot;
            setHtml(lootContainer, `
                <div class="legend-detail-grid">
                    <div class="legend-detail-item"><span>Total Saqueado:</span><strong>${l.total_looted.toLocaleString()}</strong></div>
                    <div class="legend-detail-item"><span>Ouro Total:</span><strong>${l.total_gold.toLocaleString()}</strong></div>
                    <div class="legend-detail-item"><span>Elixir Total:</span><strong>${l.total_elixir.toLocaleString()}</strong></div>
                    <div class="legend-detail-item"><span>Elixir Negro Total:</span><strong>${l.total_dark.toLocaleString()}</strong></div>
                    <div class="legend-detail-item"><span>Saque Médio:</span><strong>${l.avg_per_attack.toLocaleString()}</strong></div>
                </div>
            `);
        } else {
            setHtml(lootContainer, '<p class="message-box">Nenhum saque registrado.</p>');
        }

        const armyContainer = document.getElementById('legendArmyStats');
        if (data.attacks && data.attacks.total_attacks > 0 && data._raw_entries && data._raw_entries.length > 0) {
            const armyMap = {};
            const armyCodes = {};
            data._raw_entries.forEach(e => {
                if (e.army && (e.army.troops?.length || e.army.spells?.length || e.army.heroes?.length)) {
                    const key = JSON.stringify(e.army);
                    if (!armyMap[key]) {
                        armyMap[key] = { army: e.army, count: 0, totalStars: 0, totalDestruction: 0, attacks: 0 };
                        armyCodes[key] = e.army_share_code || null;
                    }
                    armyMap[key].count++;
                    armyMap[key].totalStars += (e.stars || 0);
                    armyMap[key].totalDestruction += (e.destruction_percentage || 0);
                    armyMap[key].attacks++;
                }
            });
            const sorted = Object.values(armyMap).sort((a, b) => b.count - a.count);
            if (sorted.length > 0) {
                function renderHeroRow(h) {
                    let html = `<span class="army-hero-name">${escapeHtmlLegend(h.name)}</span>`;
                    if (h.pet) html += `<span class="army-hero-detail"> + ${escapeHtmlLegend(h.pet)}</span>`;
                    if (h.equipment && h.equipment.length > 0) {
                        html += `<span class="army-hero-detail"> (${h.equipment.map(eq => escapeHtmlLegend(eq)).join(', ')})</span>`;
                    }
                    return `<div class="army-hero-row">${icon('trophy')} ${html}</div>`;
                }
                function renderTroopBadge(t) {
                    return `<span class="army-troop-badge"><span class="army-troop-qty">${t.quantity}x</span> ${escapeHtmlLegend(t.name)}</span>`;
                }
                function renderArmyCard(entry, idx) {
                    const a = entry.army;
                    const avgStars = entry.attacks > 0 ? (entry.totalStars / entry.attacks).toFixed(1) : '-';
                    const avgDestruction = entry.attacks > 0 ? (entry.totalDestruction / entry.attacks).toFixed(0) : '-';
                    const code = armyCodes[JSON.stringify(a)];
                    let copyBtn = '';
                    if (code) {
                        copyBtn = `<button class="army-copy-btn" data-army-code="${escapeHtmlLegend(code)}" title="Copiar código para importar no Clash">Copiar</button>`;
                    }
                    let statsPills = '';
                    if (entry.attacks > 0) {
                        statsPills += `<span class="army-stat-pill stars">${icon('star')} ${avgStars}</span>`;
                        statsPills += `<span class="army-stat-pill destruction">${avgDestruction}%</span>`;
                    }
                    statsPills += `<span class="army-stat-pill usage">${entry.count}x usado</span>`;
                    let html = `<div class="army-card">
                        <div class="army-card-header">
                            <div>
                                <div class="army-card-title">Exército #${idx + 1}</div>
                                <div class="army-card-meta">${entry.attacks} ataque${entry.attacks !== 1 ? 's' : ''} registrado${entry.attacks !== 1 ? 's' : ''}</div>
                            </div>
                            ${copyBtn}
                        </div>
                        <div class="army-stats-row">${statsPills}</div>`;
                    if (a.heroes && a.heroes.length > 0) {
                        html += `<div class="army-section-label">Heróis</div><div>${a.heroes.map(renderHeroRow).join('')}</div>`;
                    }
                    if (a.troops && a.troops.length > 0) {
                        html += `<div class="army-section-label">Tropas</div><div class="army-items-grid">${a.troops.map(renderTroopBadge).join('')}</div>`;
                    }
                    if (a.spells && a.spells.length > 0) {
                        html += `<div class="army-section-label">Feitiços</div><div class="army-items-grid">${a.spells.map(renderTroopBadge).join('')}</div>`;
                    }
                    html += '</div>';
                    return html;
                }
                const threeStar = sorted.filter(e => e.attacks > 0 && (e.totalStars / e.attacks) >= 2.8);
                const twoStar = sorted.filter(e => e.attacks > 0 && (e.totalStars / e.attacks) >= 1.5 && (e.totalStars / e.attacks) < 2.8);
                const other = sorted.filter(e => e.attacks === 0 || (e.totalStars / e.attacks) < 1.5);
                let finalHtml = '';
                if (sorted.length <= 2 || threeStar.length === 0 || twoStar.length === 0) {
                    finalHtml = sorted.map((e, i) => renderArmyCard(e, i)).join('');
                } else {
                    if (threeStar.length > 0) {
                        finalHtml += `<div class="army-section"><div class="army-section-title">${icon('trophy')} Exércitos com 3 Estrelas (média)</div>${threeStar.map((e, i) => renderArmyCard(e, i)).join('')}</div>`;
                    }
                    if (twoStar.length > 0) {
                        finalHtml += `<div class="army-section"><div class="army-section-title">${icon('star')} Exércitos com 2+ Estrelas (média)</div>${twoStar.map((e, i) => renderArmyCard(e, i + threeStar.length)).join('')}</div>`;
                    }
                    if (other.length > 0) {
                        finalHtml += `<div class="army-section"><div class="army-section-title">Outros</div>${other.map((e, i) => renderArmyCard(e, i + threeStar.length + twoStar.length)).join('')}</div>`;
                    }
                }
                setHtml(armyContainer, finalHtml);
            } else {
                setHtml(armyContainer, '<div class="army-empty">Códigos de exército não disponíveis nos battle logs.</div>');
            }
        } else {
            setHtml(armyContainer, '<div class="army-empty">Nenhum exército registrado.</div>');
        }

        const historyContainer = document.getElementById('legendHistoryStats');
        setHtml(historyContainer, '<p class="message-box">Carregando histórico...</p>');
    }

    async function loadLegendHistory(tag) {
        const historyContainer = document.getElementById('legendHistoryStats');
        try {
            const histData = await fetchData(`legend/history?tag=${encodeURIComponent(tag)}`);
            if (histData.error) {
                setHtml(historyContainer, `<p class="message-box">${escapeHtmlLegend(histData.error)}</p>`);
            } else if (histData.progression && histData.progression.total_seasons > 0) {
                const p = histData.progression;
                let trendHtml = '';
                if (p.trophy_trend && p.trophy_trend.length > 0) {
                    const maxT = Math.max(...p.trophy_trend.map(t => t.trophies)) || 1;
                    trendHtml = '<div class="legend-detail-grid" style="margin-top:12px;">' +
                        p.trophy_trend.slice(-10).map(t => {
                            const pct = Math.round((t.trophies / maxT) * 100);
                            const label = t.season_label || `S${t.season}`;
                            return `<div class="legend-detail-item" style="flex-direction:column; gap:4px;">
                                <span style="font-size:0.7rem;">${label} — #${t.placement}</span>
                                <div style="width:100%; background:rgba(255,255,255,0.1); border-radius:4px; height:8px;">
                                    <div style="width:${pct}%; height:100%; background:var(--neon-cyan); border-radius:4px;"></div>
                                </div>
                                <strong>${t.trophies} troféus</strong>
                            </div>`;
                        }).join('') + '</div>';
                }
                setHtml(historyContainer, `
                    <div class="legend-detail-grid">
                        <div class="legend-detail-item"><span>Temporadas:</span><strong>${p.total_seasons}</strong></div>
                        <div class="legend-detail-item"><span>Melhor Troféus:</span><strong>${p.best_trophies}</strong></div>
                        <div class="legend-detail-item"><span>Piores Troféus:</span><strong>${p.worst_trophies}</strong></div>
                        <div class="legend-detail-item"><span>Média Troféus:</span><strong>${p.avg_trophies}</strong></div>
                        <div class="legend-detail-item"><span>Melhor Colocação:</span><strong>#${p.best_placement}</strong></div>
                        <div class="legend-detail-item"><span>Win Rate Ataque:</span><strong>${p.avg_attack_win_rate}%</strong></div>
                        <div class="legend-detail-item"><span>Win Rate Defesa:</span><strong>${p.avg_defense_win_rate}%</strong></div>
                        <div class="legend-detail-item"><span>Total Estrelas:</span><strong>${p.total_attack_stars}</strong></div>
                    </div>
                    ${trendHtml}
                `);
            } else {
                setHtml(historyContainer, '<p class="message-box">Nenhum histórico disponível.</p>');
            }
        } catch (e) {
            setHtml(historyContainer, '<p class="message-box">Erro ao carregar histórico.</p>');
        }
    }

    async function loadLegendData() {
        const tag = legendPlayerTagEl.value.trim();
        if (!tag) {
            setText(legendErrorEl, 'Informe a tag do jogador.');
            legendErrorEl.style.display = 'block';
            return;
        }

        legendLoadingEl.style.display = 'block';
        legendErrorEl.style.display = 'none';
        legendContentEl.style.display = 'none';

        try {
            const data = await fetchData(`legend?tag=${encodeURIComponent(tag)}`);
            legendLoadingEl.style.display = 'none';

            if (data.error) {
                setText(legendErrorEl, data.error);
                legendErrorEl.style.display = 'block';
                return;
            }

            populateLegendSummary(data);
            loadLegendHistory(tag);
        } catch (e) {
            legendLoadingEl.style.display = 'none';
            setText(legendErrorEl, 'Erro ao carregar dados da Legend League.');
            legendErrorEl.style.display = 'block';
        }
    }

    if (legendFetchBtnEl) {
        legendFetchBtnEl.addEventListener('click', loadLegendData);
    }
    if (legendPlayerTagEl) {
        legendPlayerTagEl.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') loadLegendData();
        });
    }

    // === RANKED SECTION ===
    function populateRankedActivity(data) {
        const container = document.getElementById('rankedActivityContent');
        if (!container || !data || !data.members) return;

        const members = data.members;
        const active = [];
        const partial = [];
        const inactive = [];

        members.forEach(m => {
            const lastWar = m.last_war_date ? new Date(m.last_war_date) : null;
            const daysSinceWar = lastWar ? Math.floor((Date.now() - lastWar.getTime()) / (1000 * 60 * 60 * 24)) : 999;
            const hasDonations = (m.donations || 0) > 0;
            const isOnWatchlist = m.isOnWatchlist;

            let status = 'active';
            if (daysSinceWar > 15 || isOnWatchlist) status = 'inactive';
            else if (daysSinceWar > 7 || !hasDonations) status = 'partial';

            const memberInfo = { name: m.name, th: m.town_hall, trophies: m.trophies, league: m.league || 'N/A', donations: m.donations || 0, daysSinceWar, isOnWatchlist };
            if (status === 'active') active.push(memberInfo);
            else if (status === 'partial') partial.push(memberInfo);
            else inactive.push(memberInfo);
        });

        active.sort((a, b) => b.donations - a.donations);
        partial.sort((a, b) => b.daysSinceWar - a.daysSinceWar);
        inactive.sort((a, b) => a.name.localeCompare(b.name));

        let html = '<div class="ranked-member-list">';
        
        if (active.length > 0) {
            html += `<div class="ranked-summary-box"><div class="ranked-summary-title">🟢 Ativos (${active.length})</div></div>`;
            active.slice(0, 10).forEach(m => {
                html += `<div class="ranked-member-item active">
                    <span class="ranked-member-name">${escapeHtml(m.name)}</span>
                    <div class="ranked-member-stats">
                        <span class="ranked-member-stat"><img src="/assets/icons/Icon_HV_Podium.png" alt="*"> ${m.trophies}t</span>
                        <span class="ranked-member-stat">${m.league}</span>
                        <span class="ranked-member-stat"><img src="/assets/icons/Icon_HV_Sword.png" alt="*"> ${m.daysSinceWar}d</span>
                        <span class="ranked-member-stat">${m.donations} doações</span>
                    </div>
                </div>`;
            });
        }

        if (partial.length > 0) {
            html += `<div class="ranked-summary-box"><div class="ranked-summary-title">🟡 Parciais (${partial.length})</div></div>`;
            partial.slice(0, 5).forEach(m => {
                html += `<div class="ranked-member-item partial">
                    <span class="ranked-member-name">${escapeHtml(m.name)}</span>
                    <div class="ranked-member-stats">
                        <span class="ranked-member-stat">${m.daysSinceWar}d sem guerra</span>
                        <span class="ranked-member-stat">${m.donations} doações</span>
                        ${m.isOnWatchlist ? '<span class="ranked-member-stat">⚠️ Observação</span>' : ''}
                    </div>
                </div>`;
            });
        }

        if (inactive.length > 0) {
            html += `<div class="ranked-summary-box"><div class="ranked-summary-title">🔴 Inativos (${inactive.length})</div></div>`;
            inactive.slice(0, 5).forEach(m => {
                html += `<div class="ranked-member-item inactive">
                    <span class="ranked-member-name">${escapeHtml(m.name)}</span>
                    <div class="ranked-member-stats">
                        <span class="ranked-member-stat">${m.daysSinceWar}d sem guerra</span>
                        <span class="ranked-member-stat">${m.donations} doações</span>
                        ${m.isOnWatchlist ? '<span class="ranked-member-stat">⚠️ Observação</span>' : ''}
                    </div>
                </div>`;
            });
        }

        html += '</div>';
        container.innerHTML = html;
    }

    function populateRankedTournament(data) {
        const container = document.getElementById('rankedTournamentContent');
        if (!container || !data) {
            if (container) container.innerHTML = '<div class="message-box">Nenhum dado de torneio disponível.</div>';
            return;
        }

        let html = '<div class="ranked-member-list">';
        
        if (data.promotions && data.promotions.length > 0) {
            html += `<div class="ranked-summary-box"><div class="ranked-summary-title">📈 Promoções (${data.promotions.length})</div></div>`;
            data.promotions.slice(0, 10).forEach(m => {
                html += `<div class="ranked-member-item active">
                    <span class="ranked-member-name">${escapeHtml(m.name)}</span>
                    <div class="ranked-member-stats">
                        <span class="ranked-member-stat ranked-promo">↑ ${m.old_league} → ${m.new_league}</span>
                        <span class="ranked-member-stat">${m.trophy_diff > 0 ? '+' : ''}${m.trophy_diff}t</span>
                    </div>
                </div>`;
            });
        }

        if (data.demotions && data.demotions.length > 0) {
            html += `<div class="ranked-summary-box"><div class="ranked-summary-title">📉 Rebaixamentos (${data.demotions.length})</div></div>`;
            data.demotions.slice(0, 10).forEach(m => {
                html += `<div class="ranked-member-item inactive">
                    <span class="ranked-member-name">${escapeHtml(m.name)}</span>
                    <div class="ranked-member-stats">
                        <span class="ranked-member-stat ranked-demo">↓ ${m.old_league} → ${m.new_league}</span>
                        <span class="ranked-member-stat">${m.trophy_diff}t</span>
                    </div>
                </div>`;
            });
        }

        if (data.unchanged && data.unchanged.length > 0) {
            html += `<div class="ranked-summary-box"><div class="ranked-summary-title">🏆 Top 5 do Clã</div></div>`;
            data.unchanged.slice(0, 5).forEach((m, i) => {
                html += `<div class="ranked-member-item">
                    <span class="ranked-member-name">${i+1}. ${escapeHtml(m.name)}</span>
                    <div class="ranked-member-stats">
                        <span class="ranked-member-stat"><img src="/assets/icons/Icon_HV_Podium.png" alt="*"> ${m.new_trophies}t</span>
                        <span class="ranked-member-stat">${m.new_league}</span>
                    </div>
                </div>`;
            });
        }

        html += '</div>';
        container.innerHTML = html;
    }

    function populateRankedStats(data) {
        const container = document.getElementById('rankedStatsContent');
        if (!container || !data || !data.members) return;

        const members = data.members;
        const total = members.length;
        const totalTrophies = members.reduce((s, m) => s + (m.trophies || 0), 0);
        const totalDonations = members.reduce((s, m) => s + (m.donations || 0), 0);
        const totalReceived = members.reduce((s, m) => s + (m.donations_received || 0), 0);
        const avgTrophies = total ? Math.round(totalTrophies / total) : 0;
        const avgDonations = total ? Math.round(totalDonations / total) : 0;

        const thMap = {};
        const leagueMap = {};
        members.forEach(m => {
            const th = m.town_hall || '?';
            thMap[th] = (thMap[th] || 0) + 1;
            const lg = m.league || 'N/A';
            leagueMap[lg] = (leagueMap[lg] || 0) + 1;
        });

        const thSorted = Object.entries(thMap).sort((a, b) => parseInt(b[0]) - parseInt(a[0]));
        const leagueSorted = Object.entries(leagueMap).sort((a, b) => b[1] - a[1]);

        let html = '<div class="ranked-member-list">';

        html += `<div class="ranked-summary-box"><div class="ranked-summary-title">📊 Resumo Geral</div></div>`;
        html += `<div class="ranked-member-item">
            <span class="ranked-member-name">Membros</span>
            <div class="ranked-member-stats"><span class="ranked-member-stat">${total}</span></div>
        </div>`;
        html += `<div class="ranked-member-item">
            <span class="ranked-member-name">Tropheus Totais</span>
            <div class="ranked-member-stats"><span class="ranked-member-stat"><img src="/assets/icons/Icon_HV_Podium.png" alt="*"> ${totalTrophies.toLocaleString()} (média ${avgTrophies})</span></div>
        </div>`;
        html += `<div class="ranked-member-item">
            <span class="ranked-member-name">Doações Totais</span>
            <div class="ranked-member-stats"><span class="ranked-member-stat">${totalDonations.toLocaleString()} (média ${avgDonations})</span></div>
        </div>`;
        html += `<div class="ranked-member-item">
            <span class="ranked-member-name">Recebidos Totais</span>
            <div class="ranked-member-stats"><span class="ranked-member-stat">${totalReceived.toLocaleString()}</span></div>
        </div>`;

        if (thSorted.length > 0) {
            html += `<div class="ranked-summary-box"><div class="ranked-summary-title">🏗️ Town Halls</div></div>`;
            thSorted.forEach(([th, count]) => {
                const pct = Math.round((count / total) * 100);
                html += `<div class="ranked-member-item">
                    <span class="ranked-member-name">TH${th}</span>
                    <div class="ranked-member-stats">
                        <span class="ranked-member-stat">${count} membros (${pct}%)</span>
                    </div>
                </div>`;
            });
        }

        if (leagueSorted.length > 0) {
            html += `<div class="ranked-summary-box"><div class="ranked-summary-title">🏆 Ligas</div></div>`;
            leagueSorted.forEach(([lg, count]) => {
                html += `<div class="ranked-member-item">
                    <span class="ranked-member-name">${lg}</span>
                    <div class="ranked-member-stats">
                        <span class="ranked-member-stat">${count} membros</span>
                    </div>
                </div>`;
            });
        }

        html += '</div>';
        container.innerHTML = html;
    }

    loadAllData();
    setInterval(refreshActiveSection, 60000); 
});
