// data.js

import { getFromIndexedDB, saveToIndexedDB, STORE_NAMES } from './indexedDBHelper.js';
import { ui, showToast, updateSearchPlaceholder } from './ui.js';

// --- 区域: 常量定义 ---

/** 每次无限滚动加载的数据条目数量 */
export const BATCH_SIZE = 80;
/** 当电影海报缺失时使用的占位符图片 */
export const placeholderImage = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxODAiIGhlaWdodD0iMjcwIiB2aWV3Qm94PSIwIDAgMTgwIDI3MCI+PHJlY3Qgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgZmlsbD0iIzFlMWUxZSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmaWxsPSIjN2Y3ZjdmIiBmb250LXNpemU9IjE2cHgiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGFsaWdubWVudC1iYXNlbGluZT0ibWlkZGxlIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiI+Tm8gSW1hZ2U8L3RleHQ+PC9zdmc+';
/** 当演员头像缺失时使用的占位符图片 */
export const placeholderActor = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIiB2aWV3Qm94PSIwIDAgMTAwIDEwMCI+PGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgcj0iNTAiIGZpbGw9IiMzMzMiLz48cGF0aCBkPSJNNTAsNTBDNTAsMzUgNjUsMjAgNjUsMjBTNTEsMzUgNTEsNTBDNTEsNjUgMzUsODAgMzUsODBTNzUsNjUgNzUsNTBaTTUwLDYwQTM4LDM4IDAgMCAwIDUwLDYwWiIgZmlsbD0iIzY2NiIvPjwvc3ZnPg==';
/** 电影索引文件路径 */
export const MOVIE_INDEX_FILE = 'data/movies_index.json';
/** 电视剧索引文件路径 */
export const TVSHOW_INDEX_FILE = 'data/tvshows_index.json';
/** 默认的小雅 URL 前缀，用于替换 */
const DEFAULT_URL_PREFIX = 'http://xiaoya.host:5678';


// --- 区域: 全局状态管理 ---

/** 存储所有原始加载的影视数据 */
export let fullMovies = [];
/** 存储当前筛选或搜索后的影视数据 */
export let allMovies = [];
/** 存储所有人物的摘要信息 */
export let allPeople = {};
/** 存储所有制片厂的摘要信息 */
export let allStudios = {};

/** 应用设置 */
export const settings = {
    baseUrl: ["http://gc89925.com:5678","http://duyunos.com:7003","http://whtyh.cn:5678","http://43.159.54.70:5678"]
};
/** Base URL 轮询索引 */
export let baseUrlRoundRobinIndex = 0;

/** 搜索索引是否已构建的状态 */
export let isSearchIndexBuilt = false;
/** 电视剧数据是否已加载的状态 */
export let isTvShowsLoaded = false;
/** localStorage Key: 搜索索引构建状态 */
export const SEARCH_INDEX_BUILT_KEY = 'isSearchIndexBuilt';
/** localStorage Key: 电视剧加载状态 */
export const TVSHOWS_LOADED_KEY = 'isTvShowsLoaded';

/** 无限滚动器实例的占位符，由 app.js 初始化 */
export const scroller = {};

// --- 区域: 实用工具函数 ---

/** Fisher-Yates 随机排序数组 */
export function shuffleArray(array) {
    let currentIndex = array.length, randomIndex;
    while (currentIndex !== 0) {
        randomIndex = Math.floor(Math.random() * currentIndex);
        currentIndex--;
        [array[currentIndex], array[randomIndex]] = [array[randomIndex], array[currentIndex]];
    }
    return array;
}

/** 清理文件路径以适配 URL */
export function cleanPath(path) {
    if (!path) return '';
    return encodeURIComponent(path.replace(/\\/g, '/')).replace(/%2F/g, '/');
}

/**
 * 根据优先级列表从可能的数组中选择最佳的海报图片。
 * @param {string|string[]} posterImageValue - poster_image 字段的值。
 * @returns {string|null} 最佳的海报文件名，或 null。
 */
function selectBestPoster(posterImageValue) {
    if (!posterImageValue) return null;
    if (typeof posterImageValue === 'string') return posterImageValue;
    if (!Array.isArray(posterImageValue)) return null;

    const priorityOrder = ['poster.jpg', 'movie.jpg', 'cover.jpg', 'folder.jpg'];
    for (const priorityName of priorityOrder) {
        if (posterImageValue.includes(priorityName)) return priorityName;
    }
    return posterImageValue.length > 0 ? posterImageValue[0] : null;
}

/**
 * 根据优先级列表从可能的数组中选择最佳的 Fanart 图片。
 * @param {string|string[]} fanartImageValue - fanart_image 字段的值。
 * @returns {string|null} 最佳的 Fanart 文件名，或 null。
 */
function selectBestFanart(fanartImageValue) {
    if (!fanartImageValue) return null;
    if (typeof fanartImageValue === 'string') return fanartImageValue;
    if (!Array.isArray(fanartImageValue)) return null;

    const priorityOrder = ['fanart.jpg', 'banner.jpg'];
    for (const priorityName of priorityOrder) {
        if (fanartImageValue.includes(priorityName)) return priorityName;
    }
    return fanartImageValue.length > 0 ? fanartImageValue[0] : null;
}

/**
 * 读取 STRM 文件内容并替换为最终播放地址
 * @param {string} strmPath - STRM 文件的路径
 * @returns {Promise<string|null>} 返回最终的播放地址，或在失败时返回 null
 */
export async function getFinalPlaybackPath(strmPath) {
    try {
        const response = await fetch(cleanPath(strmPath));
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
            for (let i = 0; i < settings.baseUrl.length; i++) {
                const currentBaseUrlIndex = (baseUrlRoundRobinIndex + i) % settings.baseUrl.length;
                const currentBaseUrl = settings.baseUrl[currentBaseUrlIndex];
                if (decodedPath.startsWith(DEFAULT_URL_PREFIX)) {
                    finalPath = decodedPath.replace(DEFAULT_URL_PREFIX, currentBaseUrl);
                    baseUrlRoundRobinIndex = (currentBaseUrlIndex + 1) % settings.baseUrl.length;
                    break;
                }
            }
        }
        return finalPath;
    } catch (error) {
        console.error('加载 STRM 文件失败:', error);
        return null;
    }
}


// --- 区域: 数据解析 ---

/**
 * 解析通用的 NFO 文件 (电影或电视剧总览)。
 * @param {string} nfoPath - NFO 文件的路径。
 * @returns {Promise<object|null>} 解析后的数据对象，或 null。
 */
export async function parseNFO(nfoPath) {
    try {
        const response = await fetch(cleanPath(nfoPath));
        if (!response.ok) return null;
        const xmlText = await response.text();
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(xmlText, "text/xml");
        if (xmlDoc.querySelector("parsererror")) return null;

        const get = (tag) => xmlDoc.querySelector(tag)?.textContent || '';
        const getAll = (tag) => Array.from(xmlDoc.querySelectorAll(tag)).map(el => el.textContent);

        return {
            title: get('title'), plot: get('plot'), rating: get('rating'), year: get('year'),
            runtime: get('runtime'), director: getAll('director'), writer: getAll('writer'),
            studio: getAll('studio'), genre: getAll('genre'),
            actors: Array.from(xmlDoc.querySelectorAll('actor')).map(actor => ({
                name: actor.querySelector('name')?.textContent || '',
                role: actor.querySelector('role')?.textContent || '',
                thumb: actor.querySelector('thumb')?.textContent || '',
            })),
        };
    } catch (error) {
        console.warn(`解析 NFO 文件 ${nfoPath} 出错:`, error);
        return null;
    }
}

/**
 * 解析电视剧单集的 NFO 文件。
 * @param {string} nfoPath - 剧集 NFO 文件的路径。
 * @returns {Promise<object|null>} 解析后的剧集数据对象，或 null。
 */
export async function parseEpisodeNFO(nfoPath) {
    try {
        const response = await fetch(cleanPath(nfoPath));
        if (!response.ok) return null;
        const xmlText = await response.text();
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(xmlText, "text/xml");
        if (xmlDoc.querySelector("parsererror")) return null;

        return {
            title: xmlDoc.querySelector('title')?.textContent || '',
            episode: xmlDoc.querySelector('episode')?.textContent || '',
            plot: xmlDoc.querySelector('plot')?.textContent || '',
            outline: xmlDoc.querySelector('outline')?.textContent || '',
        };
    } catch (error) {
        return null;
    }
}


// --- 区域: 数据处理与转换 ---

/**
 * 将从 JSON 文件读取的原始媒体数据转换为应用内部使用的数据结构。
 * @param {Array} rawMediaArray - 原始媒体对象数组。
 * @param {string} type - 'movie' 或 'tvshow'。
 * @returns {Array} 转换后的媒体对象数组。
 */
function processRawMediaData(rawMediaArray, type) {
    return rawMediaArray.map(rawItem => {
        const title = rawItem.path.split(/\\|\//).pop();
        const mainFile = rawItem.files[0] || {};

        if (type === 'movie') {
            const files = (Array.isArray(rawItem.files) ? rawItem.files : [rawItem.files]).map(file => {
                const bestPoster = selectBestPoster(file.poster_image);
                const bestFanart = selectBestFanart(file.fanart_image);
                return {
                    poster: bestPoster ? `${rawItem.path}\\${bestPoster}` : undefined,
                    fanart: bestFanart ? `${rawItem.path}\\${bestFanart}` : undefined,
                    nfo: `${rawItem.path}\\${file.nfo}`,
                    strm: `${rawItem.path}\\${file.strm}`,
                };
            });
            return { title, type: 'movie', path: rawItem.path, files, metadata: null };
        }

        if (type === 'tvshow') {
            const bestPoster = selectBestPoster(mainFile.poster_image);
            const bestFanart = selectBestFanart(mainFile.fanart_image);
            return {
                title, type: 'tvshow', path: rawItem.path,
                files: [{
                    poster: bestPoster ? `${rawItem.path}\\${bestPoster}` : undefined,
                    fanart: bestFanart ? `${rawItem.path}\\${bestFanart}` : undefined,
                    tvshow_nfo: mainFile.tvshow_nfo ? `${rawItem.path}\\${mainFile.tvshow_nfo}` : undefined,
                    nfo: mainFile.nfo,
                    strm: mainFile.strm,
                }],
                metadata: null
            };
        }
        return null;
    }).filter(Boolean);
}


// --- 区域: 核心数据加载 ---

/**
 * 加载应用设置，优先从 localStorage 读取。
 */
export function loadSettings() {
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
}

/**
 * 保存应用设置到 localStorage。
 */
export function saveSettings() {
    try {
        localStorage.setItem('mediaLibrarySettings', JSON.stringify(settings));
    } catch (e) {
        console.error("无法保存设置到 localStorage:", e);
        showToast("设置保存失败：浏览器存储空间不足或被禁用。", 5000);
    }
}


/**
 * 应用数据初始化总函数，负责加载所有必需的数据。
 */
export async function initializeData() {
    loadSettings();
    isTvShowsLoaded = localStorage.getItem(TVSHOWS_LOADED_KEY) === 'true';
    isSearchIndexBuilt = localStorage.getItem(SEARCH_INDEX_BUILT_KEY) === 'true';

    // 优先从 IndexedDB 加载数据
    const cachedMedia = await getFromIndexedDB(STORE_NAMES.MEDIA_INDEX);
    if (cachedMedia && cachedMedia.length > 0) {
        fullMovies = cachedMedia;
        isTvShowsLoaded = fullMovies.some(item => item.type === 'tvshow');
        localStorage.setItem(TVSHOWS_LOADED_KEY, String(isTvShowsLoaded));
        console.log(`[缓存] 从 IndexedDB 加载了 ${fullMovies.length} 项媒体数据。`);
    } else {
        // 否则从网络获取基础电影数据
        console.log(`[网络] 从 ${MOVIE_INDEX_FILE} 加载初始电影数据。`);
        ui.loadingIndicator.textContent = `正在加载 ${MOVIE_INDEX_FILE}...`;
        const response = await fetch(MOVIE_INDEX_FILE);
        if (!response.ok) throw new Error(`无法加载 ${MOVIE_INDEX_FILE}`);
        const moviesData = await response.json();
        fullMovies = processRawMediaData(moviesData.movies || [], 'movie');
        await saveToIndexedDB(STORE_NAMES.MEDIA_INDEX, fullMovies);
        isTvShowsLoaded = false;
        localStorage.setItem(TVSHOWS_LOADED_KEY, 'false');
    }

    // 加载人物和制片厂数据（带缓存）
    const getDataWithCache = async (storeName, filePath) => {
        let data = await getFromIndexedDB(storeName);
        if (data) {
            console.log(`[缓存] 从 IndexedDB 加载 ${storeName}。`);
            return data;
        }
        ui.loadingIndicator.textContent = `正在加载 ${filePath}...`;
        const response = await fetch(filePath);
        if (!response.ok) throw new Error(`无法加载 ${filePath}`);
        data = await response.json();
        await saveToIndexedDB(storeName, data);
        return data;
    };
    allPeople = await getDataWithCache(STORE_NAMES.PEOPLE_SUMMARY, 'data/people_summary.json');
    allStudios = await getDataWithCache(STORE_NAMES.STUDIOS_SUMMARY, 'data/studios_summary.json');

    // 如果搜索索引已构建，则加载它
    if (isSearchIndexBuilt) {
        ui.loadingIndicator.textContent = '正在应用搜索索引...';
        loadPersistedSearchMetadata();
    }

    // 数据准备就绪
    shuffleArray(fullMovies);
    allMovies = [...fullMovies];
}


// --- 区域: 扩展数据加载 ---

/**
 * 从网络加载电视剧数据，并与现有数据合并。
 */
export async function loadTvShowsData() {
    if (isTvShowsLoaded) {
        showToast('电视剧数据已加载。');
        return;
    }

    ui.loadTvShowsButton.disabled = true;
    ui.tvShowsStatus.textContent = '正在加载...';
    showToast('正在加载电视剧数据，请稍候...', 10000);

    try {
        const response = await fetch(TVSHOW_INDEX_FILE);
        if (!response.ok) throw new Error(`加载 ${TVSHOW_INDEX_FILE} 失败`);
        const tvShowsJson = await response.json();
        const transformedTvShows = processRawMediaData(tvShowsJson.tv_shows || [], 'tvshow');

        // 合并数据
        fullMovies = [...fullMovies.filter(item => item.type === 'movie'), ...transformedTvShows];
        shuffleArray(fullMovies);
        allMovies = [...fullMovies];

        await saveToIndexedDB(STORE_NAMES.MEDIA_INDEX, fullMovies);
        isTvShowsLoaded = true;
        localStorage.setItem(TVSHOWS_LOADED_KEY, 'true');

        scroller.instance.dataArray = allMovies;
        scroller.instance.reset();
        scroller.instance.loadNextBatch();

        showToast('电视剧数据加载完成！', 5000);
    } catch (error) {
        console.error("加载电视剧数据出错:", error);
        showToast(`加载电视剧失败: ${error.message}`, 10000);
        isTvShowsLoaded = false;
        localStorage.setItem(TVSHOWS_LOADED_KEY, 'false');
    } finally {
        updateSearchPlaceholder();
        ui.loadTvShowsButton.disabled = isTvShowsLoaded;
        ui.tvShowsStatus.textContent = isTvShowsLoaded ? '电视剧数据已加载。' : '电视剧数据未加载。';
    }
}


// --- 区域: 搜索索引管理  ---

/**
 * 从 localStorage 加载持久化的搜索元数据并应用到 fullMovies。
 */
function loadPersistedSearchMetadata() {
    try {
        const cachedMetadata = localStorage.getItem('searchMetadataCache');
        if (cachedMetadata) {
            const parsedCache = JSON.parse(cachedMetadata);
            if (parsedCache.length === fullMovies.length) {
                fullMovies.forEach((item, index) => {
                    item.metadata = parsedCache[index];
                });
                console.log("成功加载持久化的搜索元数据。");
            } else {
                console.warn("缓存的元数据与当前媒体列表长度不匹配，建议重建索引。");
                isSearchIndexBuilt = false;
                localStorage.removeItem(SEARCH_INDEX_BUILT_KEY);
            }
        }
    } catch (e) {
        console.error("加载持久化搜索元数据失败:", e);
        isSearchIndexBuilt = false;
        localStorage.removeItem(SEARCH_INDEX_BUILT_KEY);
    }
}

/**
 * 从预加载的人物摘要中查找图片，如果找不到则返回占位符。
 * 这是处理 NFO 文件中缺少 <thumb> 标签时的重要备用方案。
 * @param {string} personName - 演员的姓名，可能带有 TMDB ID。
 * @returns {string} 完整的图片 URL 或 Base64 占位符。
 */
export function getPersonImage(personName) {
    if (!personName || !allPeople) return placeholderActor;
    // 1. 尝试直接匹配
    if (allPeople[personName]) {
        return allPeople[personName];
    }
    // 2. 如果直接匹配失败，尝试查找以该名字开头的键（处理 "名字-tmdb-id" 的情况）
    const key = Object.keys(allPeople).find(k => k.startsWith(personName + '-tmdb-'));
    return key ? allPeople[key] : placeholderActor;
}

/**
 * 构建搜索索引（解析所有 NFO）并持久化到 localStorage。
 */
export async function buildSearchIndexAndPersist() {
    if (!isTvShowsLoaded) {
        showToast('请先加载电视剧数据，再构建完整索引。', 5000);
        await loadTvShowsData();
        if (!isTvShowsLoaded) {
            showToast('电视剧数据加载失败，无法构建索引。', 5000);
            return;
        }
    }
    if (isSearchIndexBuilt) {
        showToast('搜索索引已存在。');
        return;
    }

    ui.buildSearchIndexButton.disabled = true;
    ui.indexStatus.textContent = '正在构建索引 (0%)...';
    showToast('正在构建全量搜索索引，此过程可能需要几分钟，请勿关闭页面。', 15000);

    const BATCH_SIZE_NFO = 20;
    const searchMetadataCache = new Array(fullMovies.length);

    try {
        for (let i = 0; i < fullMovies.length; i += BATCH_SIZE_NFO) {
            const batch = fullMovies.slice(i, i + BATCH_SIZE_NFO);
            const nfoPromises = batch.map(async (mediaItem, batchIndex) => {
                const mainFile = mediaItem.files[0];
                const nfoPath = mediaItem.type === 'tvshow' ? mainFile?.tvshow_nfo : mainFile?.nfo;
                if (!nfoPath) {
                    searchMetadataCache[i + batchIndex] = { actors: [], studio: [] };
                    return;
                }
                const nfoData = await parseNFO(nfoPath);
                const metadata = {
                    actors: nfoData?.actors?.map(a => a.name.split('-tmdb-')[0]) || [],
                    studio: nfoData?.studio || [],
                };
                mediaItem.metadata = metadata;
                searchMetadataCache[i + batchIndex] = metadata;
            });

            await Promise.allSettled(nfoPromises);

            const progress = Math.min(Math.floor(((i + batch.length) / fullMovies.length) * 100), 100);
            ui.indexStatus.textContent = `正在构建索引 (${progress}%)...`;
        }

        localStorage.setItem('searchMetadataCache', JSON.stringify(searchMetadataCache));
        isSearchIndexBuilt = true;
        localStorage.setItem(SEARCH_INDEX_BUILT_KEY, 'true');

        ui.indexStatus.textContent = '索引已建立。';
        showToast('搜索索引构建完成！', 5000);
        updateSearchPlaceholder();

    } catch (error) {
        console.error("构建搜索索引失败:", error);
        localStorage.removeItem(SEARCH_INDEX_BUILT_KEY);
        localStorage.removeItem('searchMetadataCache');
        isSearchIndexBuilt = false;
        ui.indexStatus.textContent = `索引构建失败: ${error.message}`;
    } finally {
        ui.buildSearchIndexButton.disabled = isSearchIndexBuilt;
    }
}