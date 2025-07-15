// main.js

import { InfiniteScroller } from './virtual-scroll.js';
import { BATCH_SIZE, placeholderImage, placeholderActor } from './constants.js';
import { getFromIndexedDB, saveToIndexedDB, STORE_NAMES } from './indexedDBHelper.js'; // 导入 IndexedDB 辅助函数和常量

// --- 全局数据存储 ---
let allMovies = [], fullMovies = [];
// 影视详情页仍需人物和合集信息
let allPeople = {};
// let allCollections = {}; // 移除：不再使用 collections_summary.json
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

// START 新增：搜索索引状态 - 已移至此处，确保在 initialize 之前定义
let isSearchIndexBuilt = false;
const SEARCH_INDEX_BUILT_KEY = 'isSearchIndexBuilt'; // localStorage key
const INITIAL_SEARCH_PLACEHOLDER = '搜索影视...';
const ENHANCED_SEARCH_PLACEHOLDER = '搜索影视、演员、制片厂...';
// END 新增：搜索索引状态


// TV show specific state for modal
let currentTvShowSeasonDataMap = new Map(); // Stores all parsed episode data, keyed by season name (e.g., "Season 1", "积木英语Alphablocks第三季")
let currentTvShowActiveSeasonName = ''; // To remember which season tab is active
let currentTvShowEpisodePage = 0; // Current page for the active season
const EPISODES_PER_PAGE = 5; // Define episodes per page constant

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
        // collectionLink: document.getElementById('modal-collection-link'), // 移除：不再显示合集链接
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
    // START 新增：搜索索引UI元素
    buildSearchIndexButton: document.getElementById('build-search-index-button'),
    indexStatus: document.getElementById('index-status'),
    // END 新增：搜索索引UI元素
    // 优化：缓存模板引用
    templates: {
        movieCard: document.getElementById('movie-card-template'),
        playerOption: document.getElementById('player-option-template'),
        // collectionBanner: document.getElementById('collection-banner-template'), // 移除：不再使用合集横幅模板
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

/**
 * Cleans a file path for URL usage (replaces backslashes, encodes URI components).
 * This function is crucial for paths originating from AList's JSON output.
 * @param {string} path - The original file path.
 * @returns {string} The URL-friendly path.
 */
function cleanPath(path) {
    // Replace backslashes with forward slashes for URLs
    // Then encode URI components, but keep forward slashes unencoded as they are path separators
    // Also decode common characters like spaces, parentheses, etc., which AList's paths might already have encoded,
    // to avoid double encoding.
    // However, for fetching, we generally want it fully encoded. Let's stick to the simpler version from demo.html
    // which just handles backslashes and standard encoding.
    return encodeURIComponent(path.replace(/\\/g, '/')).replace(/%2F/g, '/');
}


// --- NFO 解析函数 (保留，用于详情页 fallback) ---
// This function parses a generic NFO (movie or tvshow summary) and returns a structured object.
async function parseNFO(nfoPath) {
    try {
        const response = await fetch(cleanPath(nfoPath)); // Use cleanPath for fetching
        if (!response.ok) {
            console.warn(`NFO file not found: ${response.statusText} for ${nfoPath}`);
            return null;
        }
        const xmlText = await response.text();
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(xmlText, "text/xml");
        const errorNode = xmlDoc.querySelector("parsererror");
        if (errorNode) {
            console.warn("Error parsing XML:", errorNode.textContent, `from ${nfoPath}`);
            return null;
        }

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
            collection: get('set > name'), // 仍保留，因为NFO中可能包含
            actors: Array.from(xmlDoc.querySelectorAll('actor')).map(actor => ({
                name: actor.querySelector('name')?.textContent || '',
                role: actor.querySelector('role')?.textContent || '',
                thumb: actor.querySelector('thumb')?.textContent || '',
            })),
            streams
        };
    } catch (error) {
        console.warn(`Error parsing NFO file ${nfoPath}:`, error);
        return null;
    }
}

// --- New: Episode NFO parsing function ---
// This function specifically parses an episode NFO and returns a simple object with episode details.
async function parseEpisodeNFO(nfoPath) {
    try {
        const response = await fetch(cleanPath(nfoPath));
        if (!response.ok) {
            // console.warn(`Failed to fetch episode NFO: ${nfoPath} (Status: ${response.status})`); // Suppress in production
            return null;
        }
        const xmlText = await response.text();
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(xmlText, "text/xml");
        const errorNode = xmlDoc.querySelector("parsererror");
        if (errorNode) {
            // console.warn("Error parsing episode XML:", errorNode.textContent); // Suppress in production
            return null;
        }

        const title = xmlDoc.querySelector('title')?.textContent || '';
        const episode = xmlDoc.querySelector('episode')?.textContent || '';
        const plot = xmlDoc.querySelector('plot')?.textContent || '';
        const outline = xmlDoc.querySelector('outline')?.textContent || ''; // Also retrieve outline

        return { title, episode, plot, outline }; // Return all relevant fields
    } catch (error) {
        // console.warn(`Error fetching or parsing episode NFO ${nfoPath}:`, error); // Suppress in production
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
        showToast("设置保存失败：浏览器存储空间不足或被禁用。", 5000);
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
            // Ensure baseUrl is an array, even if loaded as a single string from older format
            if (settings.baseUrl && !Array.isArray(settings.baseUrl)) {
                settings.baseUrl = [settings.baseUrl];
            }
        }
    } catch (e) {
        console.error("无法从 localStorage 加载设置:", e);
    }

    ui.settingsBaseUrlList.innerHTML = '';

    const urls = Array.isArray(settings.baseUrl) ? settings.baseUrl : [];
    // If no URLs are configured, add a default empty input field
    if (urls.length === 0) {
        ui.settingsBaseUrlList.appendChild(createBaseUrlInput());
    } else {
        urls.forEach(url => {
            ui.settingsBaseUrlList.appendChild(createBaseUrlInput(url));
        });
    }
}

/**
 * Loads the search index status from localStorage and updates UI.
 */
function loadSearchIndexStatus() {
    isSearchIndexBuilt = localStorage.getItem(SEARCH_INDEX_BUILT_KEY) === 'true';
    if (isSearchIndexBuilt) {
        ui.buildSearchIndexButton.disabled = true;
        ui.indexStatus.textContent = '索引已建立。';
        ui.searchBox.placeholder = ENHANCED_SEARCH_PLACEHOLDER;
    } else {
        ui.buildSearchIndexButton.disabled = false;
        ui.indexStatus.textContent = '索引未建立。';
        ui.searchBox.placeholder = INITIAL_SEARCH_PLACEHOLDER;
    }
}

function toggleSettingsPanel(show) {
    ui.settingsPanel.classList.toggle('open', show);
    ui.settingsOverlay.classList.toggle('show', show);
    // Control body scroll when modal/panel is open
    document.body.classList.toggle('body-no-scroll', show);
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

    batch.forEach((mediaItem) => {
        // mediaItem is now either a movie or a tvshow object
        const mainFile = Array.isArray(mediaItem.files) ? mediaItem.files[0] : mediaItem.files;
        const posterPath = mainFile?.poster || placeholderImage; // 'poster' key is already full path after transformation

        // START MODIFICATION: 检查如果封面是占位图，则跳过渲染
        // 原始代码已移除此处的条件跳过，确保所有搜索到的项目都能被渲染
        // if (posterPath === placeholderImage) {
        //     // console.log(`Skipping media item "${mediaItem.title}" due to missing poster.`); // 可选：用于调试
        //     return; // 跳过当前媒体项，不将其渲染到页面上
        // }
        // END MODIFICATION

        const clone = template.cloneNode(true);
        const card = clone.querySelector('.card');
        const img = clone.querySelector('img');
        const titleOverlay = clone.querySelector('.title-overlay');

        card.dataset.index = fullMovies.indexOf(mediaItem);
        // Use cleanPath for image source to ensure correct URL for local files
        img.src = cleanPath(posterPath);
        img.alt = mediaItem.title;
        titleOverlay.textContent = mediaItem.title;

        fragment.appendChild(clone);
    });
    ui.movieGrid.appendChild(fragment);
}

// --- START 改进：搜索索引持久化和加载 ---
async function buildSearchIndexAndPersist() {
    if (isSearchIndexBuilt) {
        showToast('搜索索引已建立，无需重复构建。', 3000);
        return;
    }

    ui.buildSearchIndexButton.disabled = true;
    ui.indexStatus.textContent = '正在解析元数据... (0%)';
    showToast('正在构建搜索索引，请勿关闭页面。此过程可能需要几分钟。', 10000);

    const BATCH_SIZE_NFO_PARSE = 20; // Process NFOs in smaller batches
    let parsedCount = 0;
    const totalMediaItems = fullMovies.length;
    const searchMetadataCache = []; // Array to store simplified metadata for persistence

    try {
        for (let i = 0; i < totalMediaItems; i += BATCH_SIZE_NFO_PARSE) {
            const batch = fullMovies.slice(i, i + BATCH_SIZE_NFO_PARSE);

            const nfoPromises = batch.map(async (mediaItem, batchIndex) => {
                const mainFile = Array.isArray(mediaItem.files) ? mediaItem.files[0] : mediaItem.files;
                // Determine which NFO path to use for parsing (tvshow_nfo for TV shows, nfo for movies)
                const nfoPath = mediaItem.type === 'tvshow' ? mainFile?.tvshow_nfo : mainFile?.nfo;

                if (nfoPath) {
                    const nfoData = await parseNFO(nfoPath);
                    if (nfoData) {
                        // Clean actor names for search (remove TMDB IDs)
                        const actors = nfoData.actors?.map(a => a.name.split('-tmdb-')[0]) || [];
                        const studio = nfoData.studio || [];
                        // Attach to in-memory mediaItem for immediate use
                        mediaItem.metadata = { actors, studio };
                        // Also prepare for persistence
                        searchMetadataCache[i + batchIndex] = {
                            actors,
                            studio
                        };
                    } else {
                        mediaItem.metadata = { actors: [], studio: [] }; // Ensure metadata exists even if NFO fails
                        searchMetadataCache[i + batchIndex] = { actors: [], studio: [] };
                    }
                } else {
                    mediaItem.metadata = { actors: [], studio: [] }; // Ensure metadata exists if no NFO path
                    searchMetadataCache[i + batchIndex] = { actors: [], studio: [] };
                }
            });

            await Promise.allSettled(nfoPromises);

            parsedCount += batch.length;
            const progress = Math.min(Math.floor((parsedCount / totalMediaItems) * 100), 100);
            ui.indexStatus.textContent = `正在解析元数据... (${progress}%)`;
        }

        // Persist the simplified search metadata
        localStorage.setItem('searchMetadataCache', JSON.stringify(searchMetadataCache));
        isSearchIndexBuilt = true;
        localStorage.setItem(SEARCH_INDEX_BUILT_KEY, 'true');

        ui.indexStatus.textContent = '索引已建立。';
        ui.searchBox.placeholder = ENHANCED_SEARCH_PLACEHOLDER;
        showToast('搜索索引构建完成！现在可以使用增强搜索功能。', 5000);
        console.log("NFO parsing finished. Search index built successfully.");
        handleSearch(); // Re-run search with enhanced capabilities
    } catch (error) {
        console.error("Error building search index:", error);
        isSearchIndexBuilt = false; // Mark as failed
        localStorage.removeItem(SEARCH_INDEX_BUILT_KEY); // Clear potentially incomplete flag
        localStorage.removeItem('searchMetadataCache'); // Clear incomplete cache
        ui.indexStatus.textContent = `索引构建失败: ${error.message}`;
        ui.searchBox.placeholder = INITIAL_SEARCH_PLACEHOLDER;
        showToast(`搜索索引构建失败: ${error.message}`, 10000);
    } finally {
        ui.buildSearchIndexButton.disabled = false;
    }
}

/**
 * Loads persisted search metadata and attaches it to `fullMovies`.
 * Should be called after `fullMovies` is populated from `media_index.json`.
 */
function loadPersistedSearchMetadata() {
    if (!isSearchIndexBuilt) return;

    try {
        const cachedMetadata = localStorage.getItem('searchMetadataCache');
        if (cachedMetadata) {
            const parsedCache = JSON.parse(cachedMetadata);
            if (parsedCache.length === fullMovies.length) {
                fullMovies.forEach((item, index) => {
                    item.metadata = parsedCache[index];
                });
                console.log("Persisted search metadata loaded successfully.");
            } else {
                console.warn("Cached metadata length mismatch with current media list. Rebuilding index might be necessary.");
                isSearchIndexBuilt = false;
                localStorage.removeItem(SEARCH_INDEX_BUILT_KEY);
                localStorage.removeItem('searchMetadataCache');
                loadSearchIndexStatus(); // Update UI
            }
        } else {
            // If flag is true but cache is missing, something is off. Reset.
            console.warn("Search index flag is true but cache is missing. Resetting index status.");
            isSearchIndexBuilt = false;
            localStorage.removeItem(SEARCH_INDEX_BUILT_KEY);
            localStorage.removeItem('searchMetadataCache');
            loadSearchIndexStatus(); // Update UI
        }
    } catch (e) {
        console.error("Error loading persisted search metadata:", e);
        // On error, clear state to prompt user to rebuild
        isSearchIndexBuilt = false;
        localStorage.removeItem(SEARCH_INDEX_BUILT_KEY);
        localStorage.removeItem('searchMetadataCache');
        loadSearchIndexStatus(); // Update UI
    }
}
// END 改进：搜索索引持久化和加载


// --- 数据获取与初始化 ---
async function initialize() {
    ui.loadingIndicator.textContent = '正在加载基础数据，首次加载5分钟预计，数据量在100MB...'; // 更具体的提示
    ui.loadingIndicator.style.display = 'block';
    try {
        loadSettings(); // 加载用户设置
        loadSearchIndexStatus(); // 调用已正确定义的函数

        // Function to try IndexedDB first, then fetch from network and cache
        const getDataWithCache = async (storeName, filePath) => {
            try {
                const cachedData = await getFromIndexedDB(storeName);
                if (cachedData) {
                    console.log(`[Cache] 从 IndexedDB 加载 ${storeName}`);
                    // showToast(`从本地缓存加载 ${storeName}.`, 1000); // Too verbose, keep console log
                    return cachedData;
                }
            } catch (dbError) {
                console.warn(`[Cache Error] IndexedDB 读取 ${storeName} 失败，将从网络获取:`, dbError);
                showToast(`本地缓存读取 ${storeName} 失败，将从网络重新加载。`, 3000);
            }

            ui.loadingIndicator.textContent = `正在从网络加载 ${storeName}...`; // Update loading status
            const response = await fetch(filePath);
            if (!response.ok) {
                throw new Error(`无法加载 ${filePath}: ${response.statusText}`);
            }
            const data = await response.json();
            try {
                await saveToIndexedDB(storeName, data);
                console.log(`[Cache] 已将 ${storeName} 保存到 IndexedDB`);
                showToast(`已成功缓存 ${storeName}。`, 2000);
            } catch (dbError) {
                console.error(`[Cache Error] 保存 ${storeName} 到 IndexedDB 失败:`, dbError);
                showToast(`无法保存 ${storeName} 到本地缓存。`, 3000);
            }
            return data;
        };

        // Changed to fetch media_index.json using the new caching mechanism
        const [mediaIndexData, peopleData, studioData] = await Promise.all([
            getDataWithCache(STORE_NAMES.MEDIA_INDEX, 'data/media_index.json'),
            getDataWithCache(STORE_NAMES.PEOPLE_SUMMARY, 'data/people_summary.json'),
            getDataWithCache(STORE_NAMES.STUDIOS_SUMMARY, 'data/studios_summary.json')
        ]);

        let transformedMedia = [];

        // Helper to safely get the first item from a potentially array-like field, or undefined
        const getFirstItem = (item, prop) => {
            const value = item[prop];
            return Array.isArray(value) && value.length > 0 ? value[0] : value;
        };

        // Process Movies
        const rawMovies = mediaIndexData.movies || [];
        const transformedMovies = rawMovies.map(rawMovie => {
            const title = rawMovie.path.split('\\').pop();
            const files = (Array.isArray(rawMovie.files) ? rawMovie.files : [rawMovie.files]).map(file => ({
                // Construct full relative paths for files
                poster: rawMovie.path + '\\' + getFirstItem(file, 'poster_image'), // Ensure single poster
                nfo: rawMovie.path + '\\' + getFirstItem(file, 'nfo'), // Ensure single nfo
                strm: rawMovie.path + '\\' + getFirstItem(file, 'strm'), // Ensure single strm
                fanart: getFirstItem(file, 'fanart_image') ? rawMovie.path + '\\' + getFirstItem(file, 'fanart_image') : undefined // Ensure single fanart if present
            }));
            return { title, type: 'movie', path: rawMovie.path, files, metadata: null }; // Added metadata placeholder
        });
        transformedMedia.push(...transformedMovies);

        // Process TV Shows
        const rawTvShows = mediaIndexData.tv_shows || [];
        const transformedTvShows = rawTvShows.map(rawTvShow => {
            const title = rawTvShow.path.split('\\').pop();
            const mainFile = rawTvShow.files[0] || {}; // Assuming the first object in files array holds primary info

            return {
                title: title,
                type: 'tvshow', // Important flag to distinguish
                path: rawTvShow.path, // Keep the base path
                files: [{ // Simplified files for card display and basic modal info
                    // Apply getFirstItem for single-valued fields
                    poster: getFirstItem(mainFile, 'poster_image') ? rawTvShow.path + '\\' + getFirstItem(mainFile, 'poster_image') : undefined,
                    fanart: getFirstItem(mainFile, 'fanart_image') ? rawTvShow.path + '\\' + getFirstItem(mainFile, 'fanart_image') : undefined,
                    tvshow_nfo: getFirstItem(mainFile, 'tvshow_nfo') ? rawTvShow.path + '\\' + getFirstItem(mainFile, 'tvshow_nfo') : undefined, // Main show NFO
                    // Pass along the complex nfo/strm structures for episodes as they are (arrays of objects)
                    nfo: mainFile.nfo,
                    strm: mainFile.strm
                }],
                rawTvShowData: rawTvShow, // Store the full raw data for detailed modal display
                metadata: null // Added metadata placeholder
            };
        });
        transformedMedia.push(...transformedTvShows);


        fullMovies = transformedMedia; // fullMovies now contains both movies and tv shows

        // START 新增：如果搜索索引已构建，则加载持久化的元数据
        if (isSearchIndexBuilt) {
            ui.loadingIndicator.textContent = '正在应用现有搜索索引...';
            loadPersistedSearchMetadata();
        }
        // END 新增：如果搜索索引已构建...


        // 随机排序
        shuffleArray(fullMovies); // Still shuffles all media types

        allMovies = [...fullMovies]; // allMovies now contains both movies and tv shows

        allPeople = peopleData; // 使用从缓存/网络获取的数据
        allStudios = studioData; // 使用从缓存/网络获取的数据

        movieScroller = new InfiniteScroller({ container: ui.movieGrid, dataArray: allMovies, renderBatchFunc: appendMovies, batchSize: BATCH_SIZE, loadingIndicator: ui.loadingIndicator });

        ui.loadingIndicator.style.display = 'none';
        setupEventListeners();
        movieScroller.loadNextBatch();

    } catch (error) {
        ui.loadingIndicator.textContent = `加载失败: ${error.message}`;
        console.error("加载数据时出错:", error);
        showToast(`应用启动失败: ${error.message}`, 10000);
    }
}

// --- 筛选逻辑 (功能将受限，但代码保留) ---
// Note: Filtering by metadata (collection, person) will only work reliably if that metadata is pre-indexed.
// With current NFO parsing on demand, this will only effectively filter by title.
function applyMovieFilter({ type, value, description }) {
    clearMovieFilter(false);
    let filterFn;
    // Due to dynamic NFO parsing, these filters are not effective without pre-indexed metadata
    // For full functionality, `mediaItem.metadata` would need to be populated during initialization
    if (type === 'collection') { filterFn = mediaItem => mediaItem.metadata?.collection === value; }
    else if (type === 'person') { filterFn = mediaItem => mediaItem.metadata?.actors?.some(actor => actor.name === value); }
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

// --- 搜索逻辑 (已增强) ---
function handleSearch() {
    const searchTerm = ui.searchBox.value.toLowerCase().trim();
    if (ui.filterStatus.style.display !== 'none') clearMovieFilter(false);

    if (!searchTerm) {
        allMovies = [...fullMovies];
    } else {
        // Enhanced Search: Title, Actors, Studios
        allMovies = fullMovies.filter(m => {
            // 1. Check Title
            const title = m.title.toLowerCase();
            if (title.includes(searchTerm)) return true;

            // 2. Check Metadata (Actors and Studios), which is now pre-loaded or persisted
            if (isSearchIndexBuilt && m.metadata) { // Only perform enhanced search if index is built
                // Check Actors
                const actorsMatch = m.metadata.actors.some(actorName =>
                    actorName.toLowerCase().includes(searchTerm) // actorName is already clean string
                );
                if (actorsMatch) return true;

                // Check Studios
                const studiosMatch = m.metadata.studio.some(studioName =>
                    studioName.toLowerCase().includes(searchTerm)
                );
                if (studiosMatch) return true;

                // Optional: Check Directors/Writers if desired and added to persisted metadata
                // const directorsMatch = m.metadata.director.some(name => name.toLowerCase().includes(searchTerm));
                // if (directorsMatch) return true;
            }

            return false;
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

    // START 新增：构建搜索索引按钮的事件监听
    ui.buildSearchIndexButton.addEventListener('click', buildSearchIndexAndPersist);
    // END 新增：构建搜索索引按钮的事件监听
}

// --- 元数据索引构建函数 (已删除) ---

// --- 数据查找辅助函数 ---
function getPersonImage(personName) {
    if (!personName) return placeholderActor;
    if (allPeople[personName]) return allPeople[personName];
    const key = Object.keys(allPeople).find(k => k.startsWith(personName + '-tmdb-'));
    // MODIFICATION START: `people_summary.json` paths should be used directly
    return key ? allPeople[key] : placeholderActor; // `allPeople[key]` is already a direct TMDB URL
    // MODIFICATION END
}

// --- 播放器弹窗 ---
async function showPlayerModal(strmPath) {
    document.body.classList.add('body-no-scroll');
    ui.playerModal.style.display = 'flex';
    ui.playbackPathInput.value = '正在读取...';
    ui.playerOptions.innerHTML = '';

    // If strmPath is not provided or is an invalid type for direct playback (e.g., for TV show summary)
    if (!strmPath || typeof strmPath !== 'string' || strmPath === 'null') { // Added 'null' check
        ui.playbackPathInput.value = '此媒体类型无法直接播放或未提供有效播放路径。';
        ui.copyPathButton.disabled = true; // Disable copy button
        ui.playerOptions.innerHTML = '<p class="error-text">当前剧集或版本没有可用的播放路径。</p>'; // Improved message
        return; // Exit early
    }
    ui.copyPathButton.disabled = false; // Enable copy button for valid strmPath

    try {
        const response = await fetch(cleanPath(strmPath)); // Use cleanPath for fetching STRM
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
            // Find the best base URL to replace based on known prefixes
            let replaced = false;
            for (let i = 0; i < settings.baseUrl.length; i++) {
                const currentBaseUrlIndex = (baseUrlRoundRobinIndex + i) % settings.baseUrl.length;
                const currentBaseUrl = settings.baseUrl[currentBaseUrlIndex];

                // If the decodedPath starts with the DEFAULT_URL_PREFIX, replace it
                if (decodedPath.startsWith(DEFAULT_URL_PREFIX)) {
                    finalPath = decodedPath.replace(DEFAULT_URL_PREFIX, currentBaseUrl);
                    baseUrlRoundRobinIndex = (currentBaseUrlIndex + 1) % settings.baseUrl.length; // Update for next time
                    replaced = true;
                    break; // Found and replaced, exit loop
                }
            }
            // If DEFAULT_URL_PREFIX was not found, but custom URLs are configured, try to append
            // This case might be more complex if original STRM paths are relative or arbitrary.
            // For now, if no replacement happened, stick with the original decodedPath.
            // A more robust solution might involve parsing the actual URL in the STMR file content.
            // The current iteration of STRM parsing (just reading content as URL) assumes absolute URLs.
            // So, no changes here for appending.
            if (!replaced && !decodedPath.startsWith('http')) { // Assuming relative path if no http
                // This is a basic assumption. AList paths might not always be relative.
                // For safety, if it's not starting with http/https, we might prepend the first custom base URL.
                // However, this could lead to incorrect paths if the STRM contains a full but different domain.
                // Keeping it simple as per original demo logic: if it's not the default, just pass it through.
                // The current iteration of STRM parsing (just reading content as URL) assumes absolute URLs.
                // So, no changes here for appending.
            }
        }

        const encodedPlayerUrl = encodeURI(finalPath);
        const encodedParameterUrl = encodeURIComponent(finalPath); // For players that encode parameters separately

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
        ui.playerOptions.innerHTML = '<p class="error-text">无法加载STRM播放路径。</p>';
        console.error('Failed to load STRM file:', error);
    }
}

// Helper function to render episodes for the currently active season and page
const renderEpisodesForActiveSeason = async (containerElement) => { // Made async
    containerElement.innerHTML = ''; // Clear previous episodes

    // Ensure episodes are awaited if they are still a Promise from initial parsing
    const episodesPromise = currentTvShowSeasonDataMap.get(currentTvShowActiveSeasonName);
    const episodes = await Promise.resolve(episodesPromise); // Resolve the promise if it's still one

    if (!episodes || episodes.length === 0) {
        containerElement.innerHTML = '<p class="error-text">本季暂无剧集信息。</p>';
        return;
    }

    const totalEpisodes = episodes.length;
    const totalPages = Math.ceil(totalEpisodes / EPISODES_PER_PAGE);

    const start = currentTvShowEpisodePage * EPISODES_PER_PAGE;
    const end = Math.min(start + EPISODES_PER_PAGE, totalEpisodes);
    const episodesToDisplay = episodes.slice(start, end);

    const episodeUl = document.createElement('ul');
    episodeUl.classList.add('episode-list');

    episodesToDisplay.forEach(episode => {
        const episodeLi = document.createElement('li');
        episodeLi.className = 'episode-item';
        episodeLi.innerHTML = `
            <div class="episode-info">
                <strong>E${episode.episode !== 'N/A' ? episode.episode : '?'}: ${episode.title}</strong>
                <p class="episode-plot">${episode.plot || episode.outline || '暂无简介。'}</p>
            </div>
            <button class="play-episode-button" data-strm="${episode.strm}">▶ 播放</button>
        `;
        episodeUl.appendChild(episodeLi);
    });
    containerElement.appendChild(episodeUl);

    // Add pagination controls
    const paginationDiv = document.createElement('div');
    paginationDiv.className = 'pagination-controls';
    paginationDiv.innerHTML = `
        <button id="prev-episode-page" ${currentTvShowEpisodePage === 0 ? 'disabled' : ''}>上一页</button>
        <span>第 ${currentTvShowEpisodePage + 1} / ${totalPages} 页</span>
        <button id="next-episode-page" ${currentTvShowEpisodePage >= totalPages - 1 ? 'disabled' : ''}>下一页</button>
    `;
    containerElement.appendChild(paginationDiv);

    paginationDiv.querySelector('#prev-episode-page').addEventListener('click', () => {
        if (currentTvShowEpisodePage > 0) {
            currentTvShowEpisodePage--;
            renderEpisodesForActiveSeason(containerElement);
        }
    });
    paginationDiv.querySelector('#next-episode-page').addEventListener('click', () => {
        if (currentTvShowEpisodePage < totalPages - 1) {
            currentTvShowEpisodePage++;
            renderEpisodesForActiveSeason(containerElement);
        }
    });

    // Add click listener for episode play buttons
    episodeUl.querySelectorAll('.play-episode-button').forEach(button => {
        button.addEventListener('click', (e) => {
            const strmPath = e.target.dataset.strm;
            // Handle null strmPath gracefully
            if (strmPath === 'null' || !strmPath) {
                showToast('当前剧集没有可用的播放路径。', 3000);
                console.warn('Attempted to play episode with no valid strm path:', episode);
            } else {
                showPlayerModal(strmPath);
            }
        });
    });
};


// --- 弹窗详情逻辑 ---
async function showMovieDetails(mediaItem) {
    if (!mediaItem) return;

    const clearContent = (el) => { if(el) el.innerHTML = ''; };
    [
        ui.modalContent.poster, ui.modalContent.meta, ui.modalContent.directorsWriters,
        // ui.modalContent.collectionLink, // 移除：不再清空合集链接
        ui.modalContent.plot, ui.modalContent.cast,
        ui.modalContent.studios, ui.modalContent.versions
    ].forEach(clearContent);

    const mainFile = Array.isArray(mediaItem.files) ? mediaItem.files[0] : mediaItem.files;

    ui.modalContent.fanart.style.backgroundImage = mainFile?.fanart ? `url('${cleanPath(mainFile.fanart)}')` : 'none';
    ui.modalContent.poster.innerHTML = `<img src="${cleanPath(mainFile?.poster || placeholderImage)}" alt="海报">`;
    ui.modalContent.title.textContent = mediaItem.title;
    ui.modalContent.plot.innerHTML = '<p class="error-text">正在加载详情...</p>';

    // Conditional handling for Movies vs. TV Shows
    if (mediaItem.type === 'tvshow') {
        ui.modalContent.versions.innerHTML = '<h3>剧集列表</h3>'; // Rephrase
        const tvShowPath = mediaItem.path;
        // mainFile now directly contains nfo and strm structures thanks to the previous transformation
        const seasonNfoGroups = mainFile.nfo; // This is the array of objects (e.g., [{"Season 1": [...]}, {"Season 2": [...]}] )
        const seasonStrmGroups = mainFile.strm; // This is the array of objects

        const seasonTabsContainer = document.createElement('div');
        seasonTabsContainer.className = 'season-tabs';
        ui.modalContent.versions.appendChild(seasonTabsContainer);

        const episodeListContainer = document.createElement('div');
        episodeListContainer.className = 'episode-list-container';
        ui.modalContent.versions.appendChild(episodeListContainer);

        // Clear previous TV show specific state
        currentTvShowSeasonDataMap.clear();
        currentTvShowActiveSeasonName = '';
        currentTvShowEpisodePage = 0;

        if (seasonNfoGroups && Array.isArray(seasonNfoGroups) && seasonNfoGroups.length > 0 &&
            seasonStrmGroups && Array.isArray(seasonStrmGroups) && seasonStrmGroups.length === seasonNfoGroups.length) {

            const seasonNamesOrder = []; // To maintain the order of seasons for tab creation
            seasonNfoGroups.forEach((seasonNfoObject, seasonIndex) => {
                for (const seasonName in seasonNfoObject) { // Loop through the single key in each season object
                    seasonNamesOrder.push(seasonName);
                    const episodeNfoPaths = seasonNfoObject[seasonName]; // Get array of NFO paths for this season
                    // Correspondingly get STRM paths for this season
                    const seasonStrmObjectForThisSeason = seasonStrmGroups[seasonIndex];
                    const episodeStrmPaths = seasonStrmObjectForThisSeason ? seasonStrmObjectForThisSeason[seasonName] : null;


                    if (!episodeStrmPaths || !Array.isArray(episodeStrmPaths) || episodeNfoPaths.length !== episodeStrmPaths.length) {
                        console.warn(`Mismatch or missing STRM files for season "${seasonName}". Falling back or marking as not playable.`);
                        // For now, we will proceed, but episode.strm might be undefined if episodeStrmPaths is short
                    }

                    // --- Collect promises for this season's episodes ---
                    const episodesForThisSeasonPromises = episodeNfoPaths.map(async (nfoRelativePath, epIndex) => {
                        const fullEpisodeNfoPath = tvShowPath + '\\' + nfoRelativePath;
                        const fullEpisodeStrmPath = (episodeStrmPaths && episodeStrmPaths[epIndex]) ? (tvShowPath + '\\' + episodeStrmPaths[epIndex]) : null;

                        const episodeNfoData = await parseEpisodeNFO(fullEpisodeNfoPath);
                        return {
                            title: episodeNfoData?.title || nfoRelativePath.split('\\').pop().replace(/\.(nfo|strm)$/i, ''), // Clean name from file if no NFO title
                            episode: episodeNfoData?.episode || (epIndex + 1).toString(), // Fallback to index if no episode number in NFO
                            plot: episodeNfoData?.plot || episodeNfoData?.outline || '暂无简介。',
                            strm: fullEpisodeStrmPath // Can be null if no corresponding strm
                        };
                    });

                    // Store the promise result directly in the map
                    currentTvShowSeasonDataMap.set(seasonName, Promise.all(episodesForThisSeasonPromises)); // Store the promise
                }
            });

            // After initiating all parsing, create tabs and activate the first one
            let firstSeasonButtonCreated = false;
            for (const seasonName of seasonNamesOrder) {
                const seasonButton = document.createElement('button');
                // Clean up season name for display: remove bracketed content like file size
                const cleanSeasonDisplayName = seasonName.replace(/【.*?】/g, '').trim();
                seasonButton.textContent = cleanSeasonDisplayName;
                seasonButton.className = 'season-tab-button';
                seasonTabsContainer.appendChild(seasonButton);

                const activateSeason = async () => { // Make activateSeason async
                    currentTvShowActiveSeasonName = seasonName;
                    currentTvShowEpisodePage = 0; // Reset page on tab change
                    document.querySelectorAll('.season-tab-button').forEach(btn => btn.classList.remove('active'));
                    seasonButton.classList.add('active');

                    // Await the episodes for this season before rendering
                    const episodesToRender = await Promise.resolve(currentTvShowSeasonDataMap.get(seasonName));
                    currentTvShowSeasonDataMap.set(seasonName, episodesToRender); // Store the resolved data
                    renderEpisodesForActiveSeason(episodeListContainer);
                };

                seasonButton.addEventListener('click', activateSeason);

                if (!firstSeasonButtonCreated) {
                    activateSeason(); // Activate the first season by default
                    firstSeasonButtonCreated = true;
                }
            }

            // If no seasons were found or parsed after setup
            if (!firstSeasonButtonCreated) {
                episodeListContainer.innerHTML = '<p class="error-text">未能加载剧集列表或没有可用的季。</p>';
            }

        } else {
            episodeListContainer.innerHTML = '<p class="error-text">未能加载剧集列表或文件结构不匹配。</p>';
        }

    } else { // It's a movie
        // Versions list for movies
        if (mediaItem.files.length > 0) {
            ui.modalContent.versions.innerHTML = '<h3>可用版本</h3>';
            const template = ui.templates.versionItem.content;
            const fragment = document.createDocumentFragment();
            mediaItem.files.forEach((file) => { // Use movie.files directly for movies
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
    }

    document.body.classList.add('body-no-scroll');
    ui.modal.style.display = 'block';

    // Load NFO data for details. We always fetch the NFO for display purposes if not already fully cached.
    // The `mediaItem.metadata` used for search might be a simplified version.
    const nfoToParse = mainFile.tvshow_nfo || mainFile.nfo;
    let nfoData = null;
    if (nfoToParse) {
        nfoData = await parseNFO(nfoToParse);
    }

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

        // 移除：合集链接部分，因为 collections_summary.json 已被移除，且不再显示合集横幅
        // ... (collection code removed) ...


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

                // MODIFICATION START: Handle actor image source conditionally
                let finalActorThumbSrc;
                if (actor.thumb) {
                    // If actor.thumb exists, check if it's already a full URL (http/https/data URI)
                    if (actor.thumb.startsWith('http://') || actor.thumb.startsWith('https://') || actor.thumb.startsWith('data:')) {
                        finalActorThumbSrc = actor.thumb; // It's a direct URL, use it as is
                    } else {
                        // Assume it's a local path from NFO that needs cleaning
                        finalActorThumbSrc = cleanPath(actor.thumb); // Apply cleanPath to ensure proper URL encoding and slashes
                    }
                } else {
                    // If actor.thumb is empty, fall back to `people_summary.json`
                    // `getPersonImage()` now returns a direct TMDB URL, so no `cleanPath` is applied here
                    finalActorThumbSrc = getPersonImage(actor.name);
                }
                memberDiv.querySelector('img').src = finalActorThumbSrc || placeholderActor;
                // MODIFICATION END

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
                    // 修复：studioLogo本身就是完整的URL，不需要cleanPath
                    img.src = studioLogo; // <-- 这一行被修改
                    img.alt = studioName;
                    img.title = studioName;

                    // START MODIFICATION: Add click listener for studio images
                    img.style.cursor = 'pointer'; // Indicate it's clickable
                    img.addEventListener('click', () => {
                        hideAllModals();
                        ui.searchBox.value = studioName; // Set search box value to studio name
                        handleSearch(); // Trigger search
                        window.scrollTo({ top: 0, behavior: 'smooth' }); // Scroll to top
                    });
                    // END MODIFICATION

                    fragment.appendChild(clone);
                }
            });
            studioListContainer.appendChild(fragment);
        }
    } else {
        ui.modalContent.plot.innerHTML = '<p class="error-text">未能加载 NFO 元数据。</p>';
    }
}

// --- 启动应用 ---
document.addEventListener('DOMContentLoaded', initialize);