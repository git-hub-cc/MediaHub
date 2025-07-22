// indexedDBHelper.js

// =============================================================================
// == 区域: 数据库常量
// =============================================================================

const DB_NAME = 'MediaHubDB'; // 数据库名称
const DB_VERSION = 1; // 数据库版本
const STORE_NAMES = {
    MEDIA_INDEX: 'media_index',
    PEOPLE_SUMMARY: 'people_summary',
    STUDIOS_SUMMARY: 'studios_summary'
};

// =============================================================================
// == 区域: 数据库连接管理
// =============================================================================

// 全局数据库连接实例，避免重复打开
let db = null;

/**
 * 打开 IndexedDB 数据库。如果数据库或对象存储不存在，则会进行创建。
 * @returns {Promise<IDBDatabase>} 返回一个 Promise，解析为 IDBDatabase 实例。
 */
function openDB() {
    // 如果连接已存在，则直接返回，实现连接复用
    if (db) {
        return Promise.resolve(db);
    }

    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);

        // 当数据库版本需要升级或首次创建时调用
        request.onupgradeneeded = (event) => {
            const newDb = event.target.result;
            // 遍历所有预定义的存储名称，如果不存在则创建
            Object.values(STORE_NAMES).forEach(storeName => {
                if (!newDb.objectStoreNames.contains(storeName)) {
                    newDb.createObjectStore(storeName);
                    console.log(`IndexedDB: 已创建对象存储 "${storeName}"`);
                }
            });
        };

        // 数据库成功打开
        request.onsuccess = (event) => {
            db = event.target.result;
            resolve(db);
        };

        // 数据库打开失败
        request.onerror = (event) => {
            console.error('IndexedDB 错误:', event.target.errorCode, event.target.error);
            reject(new Error('打开 IndexedDB 失败'));
        };
    });
}

// =============================================================================
// == 区域: 数据操作 (CRUD)
// =============================================================================

/**
 * 将 IndexedDB 请求（IDBRequest）封装成 Promise。
 * 这是一个内部辅助函数，用于简化异步操作。
 * @param {IDBRequest} request - IndexedDB 请求对象。
 * @returns {Promise<any>} 返回一个 Promise，在请求成功时解析为结果，失败时拒绝。
 * @private
 */
function _promisifyRequest(request) {
    return new Promise((resolve, reject) => {
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

/**
 * 从指定的 IndexedDB 对象存储中检索数据。
 * @param {string} storeName 对象存储的名称。
 * @returns {Promise<any>} 返回一个 Promise，解析为检索到的数据；如果未找到，则为 undefined。
 */
async function getFromIndexedDB(storeName) {
    try {
        const database = await openDB();
        const transaction = database.transaction(storeName, 'readonly');
        const store = transaction.objectStore(storeName);
        // 假设每个存储区只存一个整体数据，使用存储区名称作为键
        return await _promisifyRequest(store.get(storeName));
    } catch (error) {
        console.error(`从 IndexedDB 存储区 [${storeName}] 获取数据时出错:`, error);
        throw error; // 向上抛出错误，以便调用者可以处理
    }
}

/**
 * 将数据保存到指定的 IndexedDB 对象存储中。
 * @param {string} storeName 对象存储的名称。
 * @param {any} data 要保存的数据。
 * @returns {Promise<void>} 返回一个 Promise，在数据成功保存后解析。
 */
async function saveToIndexedDB(storeName, data) {
    try {
        const database = await openDB();
        const transaction = database.transaction(storeName, 'readwrite');
        const store = transaction.objectStore(storeName);
        // 使用存储区名称作为键来存储数据，会覆盖同键的旧数据
        return await _promisifyRequest(store.put(data, storeName));
    } catch (error) {
        console.error(`向 IndexedDB 存储区 [${storeName}] 保存数据时出错:`, error);
        throw error; // 向上抛出错误
    }
}

export { getFromIndexedDB, saveToIndexedDB, STORE_NAMES };