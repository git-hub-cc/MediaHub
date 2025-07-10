// indexedDBHelper.js

const DB_NAME = 'mediaLibraryDB';
const DB_VERSION = 1;
const STORE_NAME = 'movies';
const KEY = 'fullMovieList'; // We'll store the entire movie array as a single entry

let dbPromise = null;

function openDB() {
    if (dbPromise) {
        return dbPromise;
    }
    dbPromise = new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: 'id' });
            }
        };

        request.onsuccess = (event) => {
            resolve(event.target.result);
        };

        request.onerror = (event) => {
            console.error('IndexedDB error:', event.target.errorCode);
            reject(event.target.error);
        };
    });
    return dbPromise;
}

/**
 * 将完整的电影数组保存到 IndexedDB。
 * @param {Array} movies - 要保存的电影数组。
 * @returns {Promise<void>}
 */
export async function saveMovies(movies) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction(STORE_NAME, 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.put({ id: KEY, data: movies });

        transaction.oncomplete = () => {
            resolve();
        };

        transaction.onerror = (event) => {
            console.error('Error saving movies to IndexedDB:', event.target.error);
            reject(event.target.error);
        };
    });
}

/**
 * 从 IndexedDB 中获取电影数组。
 * @returns {Promise<Array|null>} 返回电影数组，如果不存在则返回 null。
 */
export async function getMovies() {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction(STORE_NAME, 'readonly');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.get(KEY);

        request.onsuccess = (event) => {
            if (event.target.result) {
                resolve(event.target.result.data);
            } else {
                resolve(null);
            }
        };

        request.onerror = (event) => {
            console.error('Error getting movies from IndexedDB:', event.target.error);
            reject(event.target.error);
        };
    });
}

/**
 * 清空 IndexedDB 中的电影数据。
 * @returns {Promise<void>}
 */
export async function clearMovies() {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction(STORE_NAME, 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.clear();

        transaction.oncomplete = () => {
            resolve();
        };

        transaction.onerror = (event) => {
            console.error('Error clearing movies from IndexedDB:', event.target.error);
            reject(event.target.error);
        };
    });
}