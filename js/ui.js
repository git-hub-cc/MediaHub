// ui.js (Refined to Mimic Modal Logic)

import * as data from './data.js';

// --- 区域: DOM 元素引用 ---

export const ui = {
    movieGrid: document.getElementById('movie-grid'),
    modal: document.getElementById('details-modal'),
    closeModalBtn: document.querySelector('.modal .close-button'),
    loadingIndicator: document.getElementById('loading-indicator'),
    searchBox: document.getElementById('search-box'),
    modalContent: {
        fanart: document.getElementById('modal-fanart'),
        poster: document.getElementById('modal-poster'),
        title: document.getElementById('modal-title'),
        meta: document.getElementById('modal-meta'),
        directorsWriters: document.getElementById('modal-directors-writers'),
        plot: document.getElementById('modal-plot'),
        cast: document.getElementById('modal-cast'),
        studios: document.getElementById('modal-studios'),
        versions: document.getElementById('modal-versions'),
    },
    playerModal: document.getElementById('player-modal'),
    playerOptions: document.getElementById('player-options'),
    playbackPathInput: document.getElementById('playback-path-input'),
    copyPathButton: document.getElementById('copy-path-button'),
    closePlayerModalBtn: document.querySelector('.modal-small .close-button-small'),
    appInstallToast: document.getElementById('app-install-toast'),
    settingsButton: document.getElementById('settings-button'),
    settingsPanel: document.getElementById('settings-panel'),
    settingsCloseButton: document.getElementById('settings-close-button'),
    settingsOverlay: document.getElementById('settings-overlay'),
    settingsBaseUrlList: document.getElementById('base-url-list'),
    addBaseUrlButton: document.getElementById('add-base-url-button'),
    saveStatus: document.getElementById('save-status'),
    buildSearchIndexButton: document.getElementById('build-search-index-button'),
    indexStatus: document.getElementById('index-status'),
    loadTvShowsButton: document.getElementById('load-tvshows-button'),
    tvShowsStatus: document.getElementById('tvshows-status'),
    templates: {
        movieCard: document.getElementById('movie-card-template'),
        playerOption: document.getElementById('player-option-template'),
        castMember: document.getElementById('cast-member-template'),
        studioItem: document.getElementById('studio-item-template'),
        versionItem: document.getElementById('version-item-template'),
        baseUrlItem: document.getElementById('base-url-item-template'),
    }
};

// --- 区域: 状态变量 (UI 相关) ---
let toastTimeout;
let saveDebounceTimeout;
const EPISODES_PER_PAGE = 5;
let currentTvShowSeasonDataMap = new Map();
let currentTvShowActiveSeasonName = '';
let currentTvShowEpisodePage = 0;
let wasSearchActive = false; // 新增：用于跟踪搜索状态，以管理历史记录

// --- 区域: UI 渲染函数 ---

/**
 * 向网格中追加一批影视卡片。
 * @param {Array} batch - 要渲染的媒体对象数组。
 */
export function appendMovies(batch) {
    const fragment = document.createDocumentFragment();
    const template = ui.templates.movieCard.content;

    batch.forEach((mediaItem) => {
        const mainFile = mediaItem.files[0];
        const posterPath = mainFile?.poster || data.placeholderImage;

        const clone = template.cloneNode(true);
        const card = clone.querySelector('.card');
        const img = clone.querySelector('img');
        const titleOverlay = clone.querySelector('.title-overlay');

        card.dataset.index = data.fullMovies.indexOf(mediaItem);
        img.src = data.cleanPath(posterPath);
        img.alt = mediaItem.title;
        titleOverlay.textContent = mediaItem.title;

        fragment.appendChild(clone);
    });
    ui.movieGrid.appendChild(fragment);
}

/**
 * 渲染指定季的剧集列表和分页。
 * @param {HTMLElement} containerElement - 剧集列表的容器元素。
 */
async function renderEpisodesForActiveSeason(containerElement) {
    containerElement.innerHTML = '';
    const episodesPromise = currentTvShowSeasonDataMap.get(currentTvShowActiveSeasonName);
    const episodes = await Promise.resolve(episodesPromise);

    if (!episodes || episodes.length === 0) {
        containerElement.innerHTML = '<p class="error-text">本季暂无剧集信息。</p>';
        return;
    }

    const totalPages = Math.ceil(episodes.length / EPISODES_PER_PAGE);
    const start = currentTvShowEpisodePage * EPISODES_PER_PAGE;
    const episodesToDisplay = episodes.slice(start, start + EPISODES_PER_PAGE);

    const episodeUl = document.createElement('ul');
    episodeUl.className = 'episode-list';
    episodesToDisplay.forEach(episode => {
        const episodeLi = document.createElement('li');
        episodeLi.className = 'episode-item';
        episodeLi.innerHTML = `
            <div class="episode-info">
                <strong>E${episode.episode || '?'}: ${episode.title}</strong>
                <p class="episode-plot">${episode.plot || episode.outline || '暂无简介。'}</p>
            </div>
            <button class="play-episode-button" data-strm="${episode.strm || ''}">▶ 播放</button>
        `;
        episodeUl.appendChild(episodeLi);
    });
    containerElement.appendChild(episodeUl);

    // 分页控件
    const paginationDiv = document.createElement('div');
    paginationDiv.className = 'pagination-controls';
    paginationDiv.innerHTML = `
        <button class="prev-episode-page" ${currentTvShowEpisodePage === 0 ? 'disabled' : ''}>上一页</button>
        <span>第 ${currentTvShowEpisodePage + 1} / ${totalPages} 页</span>
        <button class="next-episode-page" ${currentTvShowEpisodePage >= totalPages - 1 ? 'disabled' : ''}>下一页</button>
    `;
    containerElement.appendChild(paginationDiv);
}


// --- 区域: UI 组件与交互 ---

/**
 * 显示一个 Toast 消息。
 * @param {string} message - 要显示的消息 (支持 HTML)。
 * @param {number} duration - 显示时长 (毫秒)。
 */
export function showToast(message, duration = 7000) {
    clearTimeout(toastTimeout);
    ui.appInstallToast.innerHTML = message;
    ui.appInstallToast.classList.add('show');
    toastTimeout = setTimeout(() => {
        ui.appInstallToast.classList.remove('show');
    }, duration);
}

/** 尝试调用本地播放器 */
function invokePlayer({ scheme, fallbackUrl, name }) {
    let handlerFired = false;
    const blurHandler = () => { handlerFired = true; };
    window.addEventListener('blur', blurHandler, { once: true });
    setTimeout(() => {
        window.removeEventListener('blur', blurHandler);
        if (!handlerFired) {
            showToast(`未能启动 ${name}。如果尚未安装，请 <a href="${fallbackUrl}" target="_blank" rel="noopener noreferrer">点击这里下载</a>。`);
        }
    }, 1500);
    window.location.href = scheme;
}

/**
 * 隐藏所有模态框和遮罩层。
 * @param {boolean} fromPopState - 是否由浏览器的 popstate 事件触发。
 * @returns {boolean} 如果有任何模态框被关闭，则返回 true。
 */
function hideAllOverlays(fromPopState = false) {
    let closedAny = false;
    const overlays = [
        { el: ui.modal, state: 'details' },
        { el: ui.playerModal, state: 'player' },
        { el: ui.settingsPanel, state: 'settings', class: 'open' }
    ];

    overlays.forEach(overlay => {
        const isOpen = overlay.class ? overlay.el.classList.contains(overlay.class) : overlay.el.style.display !== 'none';
        if (isOpen) {
            closedAny = true;
            if (overlay.class) {
                overlay.el.classList.remove(overlay.class);
                ui.settingsOverlay.classList.remove('show');
            } else {
                overlay.el.style.display = 'none';
            }
            if (!fromPopState && history.state && history.state.modal === overlay.state) {
                history.back();
            }
        }
    });

    if (closedAny) {
        document.body.classList.remove('body-no-scroll');
    }
    return closedAny;
}

/** 切换设置面板的显示/隐藏 */
function toggleSettingsPanel(show) {
    if (show) {
        ui.settingsPanel.classList.add('open');
        ui.settingsOverlay.classList.add('show');
        document.body.classList.add('body-no-scroll');
        history.pushState({ modal: 'settings' }, '', '');
    } else {
        hideAllOverlays();
    }
}

/** 显示播放器选择模态框 */
async function showPlayerModal(strmPath) {
    document.body.classList.add('body-no-scroll');
    ui.playerModal.style.display = 'flex';
    history.pushState({ modal: 'player' }, '', '');
    ui.playbackPathInput.value = '正在读取...';
    ui.playerOptions.innerHTML = '';
    ui.copyPathButton.disabled = true;

    if (!strmPath || strmPath === 'null') {
        ui.playbackPathInput.value = '无有效播放路径。';
        ui.playerOptions.innerHTML = '<p class="error-text">当前媒体没有可用的播放路径。</p>';
        return;
    }

    const finalPath = await data.getFinalPlaybackPath(strmPath);
    if (!finalPath) {
        ui.playbackPathInput.value = '读取STRM文件失败';
        ui.playerOptions.innerHTML = '<p class="error-text">无法加载播放路径。</p>';
        return;
    }

    ui.copyPathButton.disabled = false;
    const encodedPlayerUrl = encodeURI(finalPath);
    const encodedParameterUrl = encodeURIComponent(finalPath);
    ui.playbackPathInput.value = encodedPlayerUrl;

    const players = [
        { name: 'PotPlayer', scheme: `potplayer://${encodedPlayerUrl}`, fallbackUrl: 'https://potplayer.daum.net/' },
        { name: 'VLC', scheme: `vlc://${encodedPlayerUrl}`, fallbackUrl: 'https://www.videolan.org/vlc/' },
        { name: 'IINA', scheme: `iina://weblink?url=${encodedParameterUrl}`, fallbackUrl: 'https://iina.io/' },
        { name: 'MPV', scheme: `mpv://${encodedPlayerUrl}`, fallbackUrl: 'https://mpv.io/' }
    ];

    const template = ui.templates.playerOption.content;
    const fragment = document.createDocumentFragment();
    players.forEach(player => {
        const clone = template.cloneNode(true);
        const button = clone.querySelector('button');
        button.textContent = player.name;
        button.dataset.scheme = player.scheme;
        button.dataset.fallback = player.fallbackUrl;
        fragment.appendChild(clone);
    });
    ui.playerOptions.appendChild(fragment);
}

/** 显示影视详情模态框 */
async function showMovieDetails(mediaItem) {
    if (!mediaItem) return;

    // 清理内容
    [ui.modalContent.poster, ui.modalContent.meta, ui.modalContent.directorsWriters,
        ui.modalContent.plot, ui.modalContent.cast, ui.modalContent.studios, ui.modalContent.versions]
        .forEach(el => { if(el) el.innerHTML = ''; });

    document.body.classList.add('body-no-scroll');
    ui.modal.style.display = 'block';
    history.pushState({ modal: 'details' }, '', '');

    const mainFile = mediaItem.files[0];
    ui.modalContent.fanart.style.backgroundImage = mainFile?.fanart ? `url('${data.cleanPath(mainFile.fanart)}')` : 'none';
    ui.modalContent.poster.innerHTML = `<img src="${data.cleanPath(mainFile?.poster || data.placeholderImage)}" alt="海报">`;
    ui.modalContent.title.textContent = mediaItem.title;
    ui.modalContent.plot.innerHTML = '<p class="error-text">正在加载详情...</p>';

    // 根据类型（电影/电视剧）渲染不同内容
    if (mediaItem.type === 'tvshow') {
        renderTvShowDetails(mediaItem);
    } else {
        renderMovieDetails(mediaItem);
    }

    // 异步加载并显示NFO详细信息
    const nfoToParse = mainFile.tvshow_nfo || mainFile.nfo;
    if (nfoToParse) {
        const nfoData = await data.parseNFO(nfoToParse);
        if (nfoData) renderNfoDetails(nfoData, mediaItem.path);
        else ui.modalContent.plot.innerHTML = '<p class="error-text">未能加载 NFO 元数据。</p>';
    } else {
        ui.modalContent.plot.innerHTML = '<p class="error-text">未找到 NFO 元数据文件。</p>';
    }
}

/** 渲染电影版本列表 */
function renderMovieDetails(mediaItem) {
    ui.modalContent.versions.innerHTML = '<h3>可用版本</h3>';
    const template = ui.templates.versionItem.content;
    const fragment = document.createDocumentFragment();
    mediaItem.files.forEach(file => {
        if (file.strm) {
            const versionLabel = file.strm.split(/\\|\//).pop().replace(/\.strm$/i, '');
            const clone = template.cloneNode(true);
            const item = clone.querySelector('.version-item');
            item.textContent = versionLabel;
            item.dataset.strmPath = file.strm;
            fragment.appendChild(clone);
        }
    });
    ui.modalContent.versions.appendChild(fragment);
}

/** 渲染电视剧季、集列表 */
function renderTvShowDetails(mediaItem) {
    ui.modalContent.versions.innerHTML = '<h3>剧集列表</h3>';
    const seasonTabsContainer = document.createElement('div');
    seasonTabsContainer.className = 'season-tabs';
    const episodeListContainer = document.createElement('div');
    episodeListContainer.className = 'episode-list-container';
    ui.modalContent.versions.append(seasonTabsContainer, episodeListContainer);

    currentTvShowSeasonDataMap.clear();
    currentTvShowActiveSeasonName = '';
    currentTvShowEpisodePage = 0;

    const seasonNfoGroups = mediaItem.files[0].nfo;
    const seasonStrmGroups = mediaItem.files[0].strm;
    if (!seasonNfoGroups || !Array.isArray(seasonNfoGroups) || seasonNfoGroups.length === 0) {
        episodeListContainer.innerHTML = '<p class="error-text">未能加载剧集列表。</p>';
        return;
    }

    const seasonNamesOrder = [];
    seasonNfoGroups.forEach((seasonNfoObject, seasonIndex) => {
        const seasonName = Object.keys(seasonNfoObject)[0];
        if (!seasonName) return;

        seasonNamesOrder.push(seasonName);
        const episodeNfoPaths = seasonNfoObject[seasonName];
        const episodeStrmPaths = seasonStrmGroups?.[seasonIndex]?.[seasonName] || [];

        const episodesPromises = episodeNfoPaths.map(async (nfoRelativePath, epIndex) => {
            const nfoData = await data.parseEpisodeNFO(`${mediaItem.path}\\${nfoRelativePath}`);
            return {
                title: nfoData?.title || nfoRelativePath.split(/\\|\//).pop().replace(/\.nfo$/i, ''),
                episode: nfoData?.episode || (epIndex + 1).toString(),
                plot: nfoData?.plot,
                outline: nfoData?.outline,
                strm: episodeStrmPaths[epIndex] ? `${mediaItem.path}\\${episodeStrmPaths[epIndex]}` : null,
            };
        });
        currentTvShowSeasonDataMap.set(seasonName, Promise.all(episodesPromises));
    });

    seasonNamesOrder.forEach((seasonName, index) => {
        const seasonButton = document.createElement('button');
        seasonButton.textContent = seasonName.replace(/【.*?】/g, '').trim();
        seasonButton.className = 'season-tab-button';
        seasonButton.dataset.seasonName = seasonName;
        seasonTabsContainer.appendChild(seasonButton);
        if (index === 0) {
            seasonButton.classList.add('active');
            currentTvShowActiveSeasonName = seasonName;
            renderEpisodesForActiveSeason(episodeListContainer);
        }
    });
}

/**
 * 渲染从 NFO 解析出的详细信息
 * @param {object} nfoData - 解析后的 NFO 数据
 * @param {string} mediaPath - 媒体文件所在的父目录路径
 */
function renderNfoDetails(nfoData, mediaPath) {
    const { actors = [], genre = [], studio = [], plot, year, rating, runtime, director, writer } = nfoData;
    let metaHtml = [
        year,
        rating > 0 ? `⭐ ${Number(rating).toFixed(1)}` : null,
        runtime ? `🕒 ${runtime} 分钟` : null,
        genre.length > 0 ? genre.join(' / ') : null
    ].filter(Boolean).map(item => `<span>${item}</span>`).join('');
    ui.modalContent.meta.innerHTML = metaHtml;

    ui.modalContent.plot.innerHTML = plot ? `<p>${plot.replace(/\n/g, '<br>')}</p>` : '<p>暂无剧情简介。</p>';

    let dwHtml = '';
    if (director?.length) dwHtml += `<p><strong>导演:</strong> ${director.join(', ')}</p>`;
    if (writer?.length) dwHtml += `<p><strong>编剧:</strong> ${writer.join(', ')}</p>`;
    ui.modalContent.directorsWriters.innerHTML = dwHtml;

    if (actors.length > 0) {
        ui.modalContent.cast.innerHTML = '<h3>演员</h3><div class="cast-list"></div>';
        const castList = ui.modalContent.cast.querySelector('.cast-list');
        const fragment = document.createDocumentFragment();
        actors.slice(0, 20).forEach(actor => {
            const clone = ui.templates.castMember.content.cloneNode(true);
            const memberDiv = clone.querySelector('.cast-member');
            const cleanName = actor.name.split('-tmdb-')[0];
            memberDiv.dataset.actorName = cleanName;

            let finalActorThumbSrc = data.placeholderActor;

            if (actor.thumb) {
                if (actor.thumb.startsWith('http') || actor.thumb.startsWith('data:')) {
                    finalActorThumbSrc = actor.thumb;
                } else {
                    finalActorThumbSrc = data.cleanPath(`${mediaPath}\\${actor.thumb}`);
                }
            } else {
                finalActorThumbSrc = data.getPersonImage(actor.name);
            }

            memberDiv.querySelector('img').src = finalActorThumbSrc;
            memberDiv.querySelector('.name').textContent = cleanName;
            memberDiv.querySelector('.role').textContent = actor.role;
            fragment.appendChild(clone);
        });
        castList.appendChild(fragment);
    }

    if (studio.length > 0) {
        ui.modalContent.studios.innerHTML = '<h3>制片厂</h3><div class="studio-list"></div>';
        const studioList = ui.modalContent.studios.querySelector('.studio-list');
        const fragment = document.createDocumentFragment();
        studio.forEach(studioName => {
            const studioLogo = data.allStudios[studioName];
            if(studioLogo) {
                const clone = ui.templates.studioItem.content.cloneNode(true);
                const img = clone.querySelector('img');
                img.src = studioLogo;
                img.alt = studioName;
                img.title = studioName;
                img.dataset.studioName = studioName;
                fragment.appendChild(clone);
            }
        });
        studioList.appendChild(fragment);
    }
}


// --- 区域: 搜索与过滤 ---

/** 更新搜索框的占位符文本 */
export function updateSearchPlaceholder() {
    const placeholders = {
        indexed: '搜索影视、演员、制片厂...',
        tvLoaded: '搜索影视...',
        default: '搜索电影...'
    };
    if (data.isSearchIndexBuilt) ui.searchBox.placeholder = placeholders.indexed;
    else if (data.isTvShowsLoaded) ui.searchBox.placeholder = placeholders.tvLoaded;
    else ui.searchBox.placeholder = placeholders.default;
}

/**
 * 处理搜索框输入事件，并智能管理浏览器历史记录。
 */
function handleSearch() {
    const searchTerm = ui.searchBox.value.toLowerCase().trim();
    const isNowActive = searchTerm !== '';

    // 状态转换：从无搜索到有搜索
    if (isNowActive && !wasSearchActive) {
        // 创建一个历史记录条目来代表“正在搜索”的状态
        history.pushState({ searchActive: true }, '', window.location.href);
    }
    // 状态转换：从有搜索到无搜索（用户手动清空）
    else if (!isNowActive && wasSearchActive) {
        // 如果当前历史记录就是我们的“搜索”条目，则通过后退来移除它
        if (history.state && history.state.searchActive) {
            history.back();
        }
    }
    wasSearchActive = isNowActive; // 更新状态

    // 执行过滤逻辑
    let filteredMovies;
    if (!searchTerm) {
        filteredMovies = data.fullMovies;
    } else {
        filteredMovies = data.fullMovies.filter(m => {
            if (m.title.toLowerCase().includes(searchTerm)) return true;
            if (data.isSearchIndexBuilt && m.metadata) {
                if (m.metadata.actors.some(name => name.toLowerCase().includes(searchTerm))) return true;
                if (m.metadata.studio.some(name => name.toLowerCase().includes(searchTerm))) return true;
            }
            return false;
        });
    }

    data.scroller.instance.dataArray = filteredMovies;
    data.scroller.instance.reset();
    data.scroller.instance.loadNextBatch();
}

/**
 * 处理浏览器的后退事件 (popstate)。
 * 优先关闭模态框。如果无模态框，则检查是否应清空搜索。
 */
function handlePopState(event) {
    // 1. 优先处理模态框
    const didCloseOverlay = hideAllOverlays(true);
    if (didCloseOverlay) {
        return; // 模态框被关闭，任务完成
    }

    // 2. 如果没有模态框，则处理搜索状态
    // 当 popstate 触发时，表示历史记录已改变。如果此时搜索框仍有内容，
    // 说明用户是从“搜索激活”状态后退的，UI需要同步更新以反映这个变化。
    if (ui.searchBox.value.trim() !== '') {
        ui.searchBox.value = '';
        // 触发 handleSearch 来更新 UI 并同步 wasSearchActive 状态
        handleSearch();
    }
}


// --- 区域: 事件监听器设置 ---

/** 统一设置应用的所有事件监听器 */
export function setupEventListeners() {
    window.addEventListener('scroll', () => {
        const isScrollable = document.documentElement.scrollHeight > window.innerHeight;
        const isOverlayOpen = ui.modal.style.display !== 'none'
            || ui.playerModal.style.display !== 'none'
            || ui.settingsPanel.classList.contains('open');

        if (!isOverlayOpen && isScrollable && (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 500)) {
            data.scroller.instance?.loadNextBatch();
        }
    }, { passive: true });

    ui.movieGrid.addEventListener('click', e => {
        const card = e.target.closest('.card.movie-card[data-index]');
        if (card) {
            showMovieDetails(data.fullMovies[card.dataset.index]);
        }
    });

    ui.closeModalBtn.addEventListener('click', () => hideAllOverlays());
    ui.modal.addEventListener('click', e => { if (e.target === ui.modal) hideAllOverlays(); });
    ui.closePlayerModalBtn.addEventListener('click', () => hideAllOverlays());
    ui.playerModal.addEventListener('click', e => { if (e.target === ui.playerModal) hideAllOverlays(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') hideAllOverlays(); });

    // 监听 popstate 事件以处理浏览器后退按钮
    window.addEventListener('popstate', handlePopState);

    ui.searchBox.addEventListener('input', handleSearch);

    ui.copyPathButton.addEventListener('click', () => {
        ui.playbackPathInput.select(); document.execCommand('copy');
        showToast('路径已复制到剪贴板', 3000);
    });
    ui.playerOptions.addEventListener('click', e => {
        const button = e.target.closest('button[data-scheme]');
        if (button) invokePlayer(button.dataset);
    });

    ui.modalContent.versions.addEventListener('click', e => {
        const version = e.target.closest('.version-item[data-strm-path]');
        if (version) showPlayerModal(version.dataset.strmPath);

        const seasonTab = e.target.closest('.season-tab-button[data-season-name]');
        if (seasonTab) {
            document.querySelectorAll('.season-tab-button.active').forEach(b => b.classList.remove('active'));
            seasonTab.classList.add('active');
            currentTvShowActiveSeasonName = seasonTab.dataset.seasonName;
            currentTvShowEpisodePage = 0;
            renderEpisodesForActiveSeason(ui.modalContent.versions.querySelector('.episode-list-container'));
        }

        const episodePlayBtn = e.target.closest('.play-episode-button[data-strm]');
        if (episodePlayBtn) showPlayerModal(episodePlayBtn.dataset.strm);

        const episodePageBtn = e.target.closest('.pagination-controls button');
        if(episodePageBtn) {
            const isNext = episodePageBtn.classList.contains('next-episode-page');
            currentTvShowEpisodePage += isNext ? 1 : -1;
            renderEpisodesForActiveSeason(ui.modalContent.versions.querySelector('.episode-list-container'));
        }
    });

    const createSearchClickHandler = (selector, key) => (e) => {
        const element = e.target.closest(selector);
        if (element && element.dataset[key]) {
            hideAllOverlays();
            ui.searchBox.value = element.dataset[key];
            handleSearch();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    };
    ui.modalContent.cast.addEventListener('click', createSearchClickHandler('.cast-member', 'actorName'));
    ui.modalContent.studios.addEventListener('click', createSearchClickHandler('img', 'studioName'));

    ui.settingsButton.addEventListener('click', () => toggleSettingsPanel(true));
    ui.settingsCloseButton.addEventListener('click', () => hideAllOverlays());
    ui.settingsOverlay.addEventListener('click', () => hideAllOverlays());

    ui.addBaseUrlButton.addEventListener('click', () => {
        const newItem = ui.templates.baseUrlItem.content.cloneNode(true);
        ui.settingsBaseUrlList.appendChild(newItem);
        ui.settingsBaseUrlList.lastElementChild.querySelector('input').focus();
    });

    const saveBaseUrlSettings = () => {
        const urls = Array.from(ui.settingsBaseUrlList.querySelectorAll('input[type="text"]'))
            .map(input => input.value.trim()).filter(Boolean);
        data.settings.baseUrl = urls;
        data.saveSettings();
        data.baseUrlRoundRobinIndex = 0;

        ui.saveStatus.textContent = '已保存';
        ui.saveStatus.style.opacity = '1';
        setTimeout(() => { ui.saveStatus.style.opacity = '0'; }, 2000);
    };

    ui.settingsBaseUrlList.addEventListener('click', e => {
        if (e.target.matches('.delete-url-button')) {
            e.target.closest('.base-url-item').remove();
            saveBaseUrlSettings();
        }
    });

    ui.settingsBaseUrlList.addEventListener('input', e => {
        if (e.target.matches('input[type="text"]')) {
            clearTimeout(saveDebounceTimeout);
            saveDebounceTimeout = setTimeout(saveBaseUrlSettings, 500);
        }
    });

    ui.buildSearchIndexButton.addEventListener('click', data.buildSearchIndexAndPersist);
    ui.loadTvShowsButton.addEventListener('click', data.loadTvShowsData);
}

/** 根据当前数据状态更新UI（主要是按钮和占位符） */
export function updateInitialUI() {
    updateSearchPlaceholder();
    ui.settingsBaseUrlList.innerHTML = '';
    const urls = Array.isArray(data.settings.baseUrl) ? data.settings.baseUrl : [];
    if (urls.length === 0) {
        ui.settingsBaseUrlList.appendChild(ui.templates.baseUrlItem.content.cloneNode(true));
    } else {
        urls.forEach(url => {
            const clone = ui.templates.baseUrlItem.content.cloneNode(true);
            clone.querySelector('input').value = url;
            ui.settingsBaseUrlList.appendChild(clone);
        });
    }

    ui.buildSearchIndexButton.disabled = data.isSearchIndexBuilt;
    ui.indexStatus.textContent = data.isSearchIndexBuilt ? '索引已建立。' : '索引未建立。';
    ui.loadTvShowsButton.disabled = data.isTvShowsLoaded;
    ui.tvShowsStatus.textContent = data.isTvShowsLoaded ? '电视剧数据已加载。' : '电视剧数据未加载。';
}