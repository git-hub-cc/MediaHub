// main.js

import { InfiniteScroller } from './virtual-scroll.js';
import { BATCH_SIZE, placeholderImage, placeholderActor } from './constants.js';
// 移除了 indexedDBHelper 的导入

// --- 全局数据存储 ---
let allMovies = [], fullMovies = [];
// 影视详情页仍需人物和合集信息
let allPeople = {};
let allCollections = {};
let allStudios = {};

// --- 滚动器实例 ---
let movieScroller;

// --- 状态管理 ---
let toastTimeout;
// 将 baseUrl 修改为数组以支持多个路径，并添加轮询索引
const settings = {
    baseUrl: ["http://gc89925.com:5678","http://duyunos.com:7003","http://whtyh.cn:5678","http://43.159.54.70:5678"]
};
let baseUrlRoundRobinIndex = 0;
const DEFAULT_URL_PREFIX = 'http://xiaoya.host:5678';
// 移除了 INDEX_TIMESTAMP_KEY

// --- DOM 元素获取 ---
const ui = {
    movieGrid: document.getElementById('movie-grid'),
    modal: document.getElementById('details-modal'),
    closeModalBtn: document.querySelector('.modal .close-button'),
    loadingIndicator: document.getElementById('loading-indicator'),
    searchBox: document.getElementById('search-box'),
    filterStatus: document.getElementById('filter-status'),
    filterText: document.getElementById('filter-text'),
    clearFilterBtn: document.getElementById('clear-filter'),
    modalContent: {
        fanart: document.getElementById('modal-fanart'),
        poster: document.getElementById('modal-poster'),
        title: document.getElementById('modal-title'),
        meta: document.getElementById('modal-meta'),
        directorsWriters: document.getElementById('modal-directors-writers'),
        collectionLink: document.getElementById('modal-collection-link'),
        plot: document.getElementById('modal-plot'),
        cast: document.getElementById('modal-cast'),
        studios: document.getElementById('modal-studios'),
        streamDetails: document.getElementById('modal-stream-details'),
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
    // 移除了 buildIndexButton 和 indexStatus 的引用
    // 优化：缓存模板引用
    templates: {
        movieCard: document.getElementById('movie-card-template'),
        playerOption: document.getElementById('player-option-template'),
        collectionBanner: document.getElementById('collection-banner-template'),
        castMember: document.getElementById('cast-member-template'),
        studioItem: document.getElementById('studio-item-template'),
        versionItem: document.getElementById('version-item-template'),
        streamInfoBox: document.getElementById('stream-info-box-template'),
        baseUrlItem: document.getElementById('base-url-item-template'),
    }
};

// --- 数组随机排序函数 (Fisher-Yates Shuffle) ---
function shuffleArray(array) {
    let currentIndex = array.length, randomIndex;
    while (currentIndex !== 0) {
        randomIndex = Math.floor(Math.random() * currentIndex);
        currentIndex--;
        [array[currentIndex], array[randomIndex]] = [
            array[randomIndex], array[currentIndex]];
    }
    return array;
}

// --- NFO 解析函数 (保留，用于详情页 fallback) ---
async function parseNFO(nfoPath) {
    try {
        const response = await fetch(nfoPath);
        if (!response.ok) throw new Error(`NFO file not found: ${response.statusText}`);
        const xmlText = await response.text();
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(xmlText, "text/xml");
        const get = (tag) => xmlDoc.querySelector(tag)?.textContent || '';
        const getAll = (tag, parent = xmlDoc) => Array.from(parent.querySelectorAll(tag)).map(el => el.textContent);
        const fileinfo = xmlDoc.querySelector('fileinfo streamdetails');
        const streams = { video: [], audio: [], subtitle: [] };
        if(fileinfo){
            fileinfo.querySelectorAll('video, audio, subtitle').forEach(stream => {
                const type = stream.tagName;
                const details = {};
                for (const node of stream.children) {
                    details[node.tagName.toLowerCase()] = node.textContent;
                }
                streams[type].push(details);
            });
        }
        return {
            title: get('title'), originaltitle: get('originaltitle'), plot: get('plot'), rating: get('rating'),
            year: get('year'), runtime: get('runtime'), director: getAll('director'), writer: getAll('writer'),
            studio: getAll('studio'), genre: getAll('genre'),
            collection: get('set > name'),
            actors: Array.from(xmlDoc.querySelectorAll('actor')).map(actor => ({
                name: actor.querySelector('name')?.textContent || '',
                role: actor.querySelector('role')?.textContent || '',
                thumb: actor.querySelector('thumb')?.textContent || '',
            })),
            streams
        };
    } catch (error) {
        console.error(`Error parsing NFO file ${nfoPath}:`, error);
        return null;
    }
}

// --- UI 辅助函数 ---
function showToast(message, duration = 7000) {
    clearTimeout(toastTimeout);
    ui.appInstallToast.innerHTML = message;
    ui.appInstallToast.classList.add('show');
    toastTimeout = setTimeout(() => {
        ui.appInstallToast.classList.remove('show');
    }, duration);
}

// --- 智能播放器调用 ---
function invokePlayer({ scheme, fallbackUrl, name }) {
    let handlerFired = false;
    const blurHandler = () => { handlerFired = true; };
    window.addEventListener('blur', blurHandler);
    setTimeout(() => {
        window.removeEventListener('blur', blurHandler);
        if (!handlerFired) {
            showToast(`未能启动 ${name}。如果尚未安装，请 <a href="${fallbackUrl}" target="_blank" rel="noopener noreferrer">点击这里下载</a>。`);
        }
    }, 1500);
    window.location.href = scheme;
}

// --- 设置逻辑 ---
let saveStatusTimeout;
let saveDebounceTimeout;

function saveSettings() {
    try {
        localStorage.setItem('mediaLibrarySettings', JSON.stringify(settings));
    } catch (e) {
        console.error("无法保存设置到 localStorage:", e);
    }
}

function saveBaseUrlSettings() {
    const urlInputs = ui.settingsBaseUrlList.querySelectorAll('input[type="text"]');
    const urls = Array.from(urlInputs)
        .map(input => input.value.trim())
        .filter(url => url);

    settings.baseUrl = urls;
    saveSettings();
    baseUrlRoundRobinIndex = 0;

    ui.saveStatus.textContent = '已保存';
    ui.saveStatus.style.opacity = '1';
    clearTimeout(saveStatusTimeout);
    saveStatusTimeout = setTimeout(() => { ui.saveStatus.style.opacity = '0'; }, 2000);
}

function createBaseUrlInput(url = '') {
    const template = ui.templates.baseUrlItem.content;
    const clone = template.cloneNode(true);
    const input = clone.querySelector('input');
    input.value = url;
    return clone;
}

function loadSettings() {
    try {
        const savedSettings = localStorage.getItem('mediaLibrarySettings');
        if (savedSettings) {
            Object.assign(settings, JSON.parse(savedSettings));
            if (settings.baseUrl && !Array.isArray(settings.baseUrl)) {
                settings.baseUrl = [settings.baseUrl];
            }
        }
    } catch (e) {
        console.error("无法从 localStorage 加载设置:", e);
    }

    ui.settingsBaseUrlList.innerHTML = '';

    const urls = Array.isArray(settings.baseUrl) ? settings.baseUrl : [];
    urls.forEach(url => {
        ui.settingsBaseUrlList.appendChild(createBaseUrlInput(url));
    });
}

function toggleSettingsPanel(show) {
    ui.settingsPanel.classList.toggle('open', show);
    ui.settingsOverlay.classList.toggle('show', show);
}

// --- 统一的模态框关闭函数 ---
function hideAllModals() {
    ui.modal.style.display = 'none';
    ui.playerModal.style.display = 'none';
    document.body.classList.remove('body-no-scroll');
}

// --- 渲染函数 ---
function appendMovies(batch) {
    const fragment = document.createDocumentFragment();
    const template = ui.templates.movieCard.content;

    batch.forEach((movie) => {
        const mainFile = Array.isArray(movie.files) ? movie.files[0] : movie.files;
        const posterPath = mainFile?.poster || placeholderImage;
        const clone = template.cloneNode(true);
        const card = clone.querySelector('.card');
        const img = clone.querySelector('img');
        const titleOverlay = clone.querySelector('.title-overlay');

        card.dataset.index = fullMovies.indexOf(movie);
        img.src = encodeURI(posterPath);
        img.alt = movie.title;
        titleOverlay.textContent = movie.title;

        fragment.appendChild(clone);
    });
    ui.movieGrid.appendChild(fragment);
}

// --- 数据获取与初始化 (已简化) ---
async function initialize() {
    ui.loadingIndicator.textContent = '正在初始化数据...';
    ui.loadingIndicator.style.display = 'block';
    try {
        loadSettings(); // 加载用户设置
        const [movieRes, peopleRes, collectionRes, studioRes] = await Promise.all([
            fetch('data/movie_summary.json'), fetch('data/people_summary.json'),
            fetch('data/collections_summary.json'), fetch('data/studios_summary.json')
        ]);
        if (!movieRes.ok || !peopleRes.ok || !collectionRes.ok || !studioRes.ok) throw new Error('部分或全部数据文件加载失败');

        // 直接从 JSON 加载电影数据
        const baseMovies = (await movieRes.json()).map(movie => {
            if (movie.files && !Array.isArray(movie.files)) {
                movie.files = [movie.files];
            }
            return movie;
        });

        fullMovies = baseMovies;

        // 随机排序
        shuffleArray(fullMovies);

        allMovies = [...fullMovies];

        allPeople = await peopleRes.json();
        allCollections = await collectionRes.json();
        allStudios = await studioRes.json();

        movieScroller = new InfiniteScroller({ container: ui.movieGrid, dataArray: allMovies, renderBatchFunc: appendMovies, batchSize: BATCH_SIZE, loadingIndicator: ui.loadingIndicator });

        ui.loadingIndicator.style.display = 'none';
        setupEventListeners();
        movieScroller.loadNextBatch();

    } catch (error) {
        ui.loadingIndicator.textContent = `加载失败: ${error.message}`;
        console.error("加载数据时出错:", error);
    }
}

// --- 筛选逻辑 (功能将受限，但代码保留) ---
function applyMovieFilter({ type, value, description }) {
    clearMovieFilter(false);
    let filterFn;
    // 注意：由于没有索引，movie.metadata 将为空，这些筛选将无法生效
    if (type === 'collection') { filterFn = movie => movie.metadata?.collection === value; }
    else if (type === 'person') { filterFn = movie => movie.metadata?.actors?.some(actor => actor.name === value); }
    if (filterFn) {
        allMovies = fullMovies.filter(filterFn);
        movieScroller.dataArray = allMovies; movieScroller.reset(); movieScroller.loadNextBatch();
        ui.filterText.textContent = description; ui.filterStatus.style.display = 'flex'; ui.searchBox.value = '';
    }
}
function clearMovieFilter(resetView = true) {
    allMovies = [...fullMovies]; ui.filterStatus.style.display = 'none'; ui.filterText.textContent = '';
    if (resetView) {
        movieScroller.dataArray = allMovies; movieScroller.reset(); movieScroller.loadNextBatch();
    }
}

// --- 搜索逻辑 (功能将受限，但代码保留) ---
function handleSearch() {
    const searchTerm = ui.searchBox.value.toLowerCase().trim();
    if (ui.filterStatus.style.display !== 'none') clearMovieFilter(false);

    if (!searchTerm) {
        allMovies = [...fullMovies];
    } else {
        // 注意：由于没有索引，只有标题搜索会有效
        allMovies = fullMovies.filter(m => {
            const title = m.title.toLowerCase();
            const originalTitle = m.metadata?.originaltitle?.toLowerCase() || '';
            const plot = m.metadata?.plot?.toLowerCase() || '';
            const hasActor = m.metadata?.actors?.some(a => a.name.toLowerCase().split('-tmdb-')[0].includes(searchTerm)) || false;
            const hasDirector = m.metadata?.director?.some(d => d.toLowerCase().split('-tmdb-')[0].includes(searchTerm)) || false;
            const hasWriter = m.metadata?.writer?.some(w => w.toLowerCase().split('-tmdb-')[0].includes(searchTerm)) || false;

            return title.includes(searchTerm) ||
                originalTitle.includes(searchTerm) ||
                plot.includes(searchTerm) ||
                hasActor || hasDirector || hasWriter;
        });
    }
    movieScroller.dataArray = allMovies;
    movieScroller.reset();
    movieScroller.loadNextBatch();
}

// --- 事件监听 (已简化) ---
function setupEventListeners() {
    ui.searchBox.addEventListener('input', handleSearch);
    ui.clearFilterBtn.addEventListener('click', () => clearMovieFilter(true));

    window.addEventListener('scroll', () => {
        if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 500) {
            movieScroller?.loadNextBatch();
        }
    }, { passive: true });

    document.querySelector('main').addEventListener('click', (e) => {
        const card = e.target.closest('.card.movie-card');
        if (!card) return;
        const { index } = card.dataset;
        if (index) {
            showMovieDetails(fullMovies[index]);
        }
    });

    // Modal closing listeners
    ui.closeModalBtn.addEventListener('click', hideAllModals);
    ui.modal.addEventListener('click', (e) => { if (e.target === ui.modal) hideAllModals(); });
    ui.closePlayerModalBtn.addEventListener('click', hideAllModals);
    ui.playerModal.addEventListener('click', (e) => { if (e.target === ui.playerModal) hideAllModals(); });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            hideAllModals();
            toggleSettingsPanel(false);
        }
    });

    // Player functionality listeners
    ui.copyPathButton.addEventListener('click', () => {
        ui.playbackPathInput.select(); document.execCommand('copy');
        showToast('路径已复制到剪贴板', 3000);
    });
    ui.playerOptions.addEventListener('click', (e) => {
        const button = e.target.closest('button');
        if (button) { invokePlayer({ scheme: button.dataset.scheme, fallbackUrl: button.dataset.fallback, name: button.textContent }); }
    });

    // Actor click listener in details modal
    ui.modalContent.cast.addEventListener('click', e => {
        const castMember = e.target.closest('.cast-member[data-actor-name]');
        if (castMember) {
            const actorName = castMember.dataset.actorName;
            hideAllModals();
            ui.searchBox.value = actorName;
            handleSearch();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    });

    // Settings Panel Listeners
    ui.settingsButton.addEventListener('click', () => toggleSettingsPanel(true));
    ui.settingsCloseButton.addEventListener('click', () => toggleSettingsPanel(false));
    ui.settingsOverlay.addEventListener('click', () => toggleSettingsPanel(false));

    ui.addBaseUrlButton.addEventListener('click', () => {
        const newItem = createBaseUrlInput();
        ui.settingsBaseUrlList.appendChild(newItem);
        ui.settingsBaseUrlList.lastElementChild.querySelector('input').focus();
    });

    ui.settingsBaseUrlList.addEventListener('click', e => {
        if (e.target.matches('.delete-url-button')) {
            e.target.closest('.base-url-item').remove();
            saveBaseUrlSettings();
        }
    });

    ui.settingsBaseUrlList.addEventListener('input', e => {
        if (e.target.matches('input[type="text"]')) {
            clearTimeout(saveDebounceTimeout);
            saveDebounceTimeout = setTimeout(() => {
                saveBaseUrlSettings();
            }, 500);
        }
    });

    // 移除了 buildIndexButton 的事件监听
}

// --- 元数据索引构建函数 (已删除) ---

// --- 数据查找辅助函数 ---
function getPersonImage(personName) {
    if (!personName) return placeholderActor;
    if (allPeople[personName]) return allPeople[personName];
    const key = Object.keys(allPeople).find(k => k.startsWith(personName + '-tmdb-'));
    return key ? allPeople[key] : placeholderActor;
}

// --- 播放器弹窗 ---
async function showPlayerModal(strmPath) {
    document.body.classList.add('body-no-scroll');
    ui.playerModal.style.display = 'flex';
    ui.playbackPathInput.value = '正在读取...';
    ui.playerOptions.innerHTML = '';

    try {
        const response = await fetch(strmPath);
        if (!response.ok) throw new Error('STRM file not found');

        const rawPath = (await response.text()).trim();
        let decodedPath;

        try {
            decodedPath = decodeURIComponent(rawPath);
        } catch (e) {
            console.warn("路径解码失败，将使用原始路径:", rawPath, e);
            decodedPath = rawPath;
        }

        let finalPath = decodedPath;
        if (Array.isArray(settings.baseUrl) && settings.baseUrl.length > 0) {
            if (baseUrlRoundRobinIndex >= settings.baseUrl.length) {
                baseUrlRoundRobinIndex = 0;
            }
            const currentBaseUrl = settings.baseUrl[baseUrlRoundRobinIndex];
            finalPath = finalPath.replace(DEFAULT_URL_PREFIX, currentBaseUrl);
            baseUrlRoundRobinIndex = (baseUrlRoundRobinIndex + 1) % settings.baseUrl.length;
        }

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

    } catch(error) {
        ui.playbackPathInput.value = '读取STRM文件失败';
        console.error('Failed to load STRM file:', error);
    }
}

// --- 弹窗详情逻辑 ---
async function showMovieDetails(movie) {
    if (!movie) return;

    const clearContent = (el) => { if(el) el.innerHTML = ''; };
    [
        ui.modalContent.poster, ui.modalContent.meta, ui.modalContent.directorsWriters,
        ui.modalContent.collectionLink, ui.modalContent.plot, ui.modalContent.cast,
        ui.modalContent.studios, ui.modalContent.versions
    ].forEach(clearContent);

    // movie.metadata 现在将始终为空，所以我们依赖 NFO fallback
    const { files: fileList = [] } = movie;
    const mainFile = fileList[0] || {};

    ui.modalContent.fanart.style.backgroundImage = mainFile.fanart ? `url('${encodeURI(mainFile.fanart)}')` : 'none';
    ui.modalContent.poster.innerHTML = `<img src="${encodeURI(mainFile.poster || placeholderImage)}" alt="海报">`;
    ui.modalContent.title.textContent = movie.title;
    ui.modalContent.plot.innerHTML = '<p class="error-text">正在加载剧情简介...</p>';

    // 版本列表
    if (fileList.length > 0) {
        ui.modalContent.versions.innerHTML = '<h3>可用版本</h3>';
        const template = ui.templates.versionItem.content;
        const fragment = document.createDocumentFragment();
        fileList.forEach((file) => {
            if (file.strm) {
                const versionLabel = file.strm.split('/').pop().replace(/\.strm$/i, '');
                const clone = template.cloneNode(true);
                const item = clone.querySelector('.version-item');
                item.textContent = versionLabel;
                item.dataset.strmPath = file.strm;
                item.addEventListener('click', () => showPlayerModal(file.strm));
                fragment.appendChild(clone);
            }
        });
        ui.modalContent.versions.appendChild(fragment);
    }

    document.body.classList.add('body-no-scroll');
    ui.modal.style.display = 'block';

    // 异步加载 NFO 数据来填充详细信息
    if (mainFile.nfo) {
        const nfoData = await parseNFO(mainFile.nfo);
        if (nfoData) {
            const { actors = [], genre: genres = [], studio: studiosList = [], plot, year, rating, runtime, collection, director, writer } = nfoData;

            let metaHtml = '';
            if (year) metaHtml += `<span>${year}</span>`;
            if (rating > 0) metaHtml += `<span>⭐ ${Number(rating).toFixed(1)}</span>`;
            if (runtime) metaHtml += `<span>🕒 ${runtime} 分钟</span>`;
            if (genres?.length > 0) metaHtml += `<span>${genres.join(' / ')}</span>`;
            ui.modalContent.meta.innerHTML = metaHtml;

            ui.modalContent.plot.innerHTML = plot ? `<p>${plot.replace(/\n/g, '<br>')}</p>` : '<p>暂无剧情简介。</p>';

            let dwHtml = '';
            if (director?.length) dwHtml += `<p><strong>导演:</strong> ${director.join(', ')}</p>`;
            if (writer?.length) dwHtml += `<p><strong>编剧:</strong> ${writer.join(', ')}</p>`;
            ui.modalContent.directorsWriters.innerHTML = dwHtml;

            // 剩下的UI填充逻辑与之前类似，但使用从NFO解析的数据
            if (collection && allCollections[collection]) {
                const collectionData = allCollections[collection];
                const template = ui.templates.collectionBanner.content;
                const clone = template.cloneNode(true);
                const banner = clone.querySelector('.collection-banner');
                banner.addEventListener('click', (e) => { e.preventDefault(); /* 筛选功能已失效 */ });
                banner.style.cursor = 'default'; // 移除点击手势
                banner.querySelector('.collection-poster').src = encodeURI(collectionData.poster || placeholderImage);
                banner.querySelector('p').textContent = collection.split('-tmdb-')[0];
                ui.modalContent.collectionLink.appendChild(clone);
            }

            if (actors?.length > 0) {
                ui.modalContent.cast.innerHTML = '<h3>演员</h3><div class="cast-list"></div>';
                const castListContainer = ui.modalContent.cast.querySelector('.cast-list');
                const template = ui.templates.castMember.content;
                const fragment = document.createDocumentFragment();
                actors.slice(0, 20).forEach(actor => {
                    const clone = template.cloneNode(true);
                    const memberDiv = clone.querySelector('.cast-member');
                    const cleanActorName = actor.name.split('-tmdb-')[0];

                    // Make actor clickable to trigger a search
                    memberDiv.dataset.actorName = cleanActorName;
                    memberDiv.style.cursor = 'pointer';
                    memberDiv.title = `搜索演员: ${cleanActorName}`;

                    memberDiv.querySelector('img').src = encodeURI(actor.thumb || getPersonImage(actor.name));
                    memberDiv.querySelector('.name').textContent = cleanActorName;
                    memberDiv.querySelector('.role').textContent = actor.role;
                    fragment.appendChild(clone);
                });
                castListContainer.appendChild(fragment);
            }

            if (studiosList?.length > 0) {
                ui.modalContent.studios.innerHTML = '<h3>制片厂</h3><div class="studio-list"></div>';
                const studioListContainer = ui.modalContent.studios.querySelector('.studio-list');
                const template = ui.templates.studioItem.content;
                const fragment = document.createDocumentFragment();
                studiosList.forEach(studioName => {
                    const studioLogo = allStudios[studioName];
                    if (studioLogo) {
                        const clone = template.cloneNode(true);
                        const img = clone.querySelector('img');
                        img.src = encodeURI(studioLogo);
                        img.alt = studioName;
                        img.title = studioName;
                        fragment.appendChild(clone);
                    }
                });
                studioListContainer.appendChild(fragment);
            }
        }
    }
}

// --- 启动应用 ---
document.addEventListener('DOMContentLoaded', initialize);