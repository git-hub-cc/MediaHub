// indexedDBHelper.js

const DB_NAME = 'MediaHubDB';
const DB_VERSION = 1;
const STORE_NAMES = {
    MEDIA_INDEX: 'media_index',
    PEOPLE_SUMMARY: 'people_summary',
    STUDIOS_SUMMARY: 'studios_summary'
};

let db = null;

/**
 * Opens the IndexedDB database. Creates object stores if necessary.
 * @returns {Promise<IDBDatabase>} A promise that resolves with the IDBDatabase instance.
 */
function openDB() {
    return new Promise((resolve, reject) => {
        if (db) {
            resolve(db);
            return;
        }

        const request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onupgradeneeded = (event) => {
            const newDb = event.target.result;
            // Create object stores if they don't exist
            for (const key in STORE_NAMES) {
                if (!newDb.objectStoreNames.contains(STORE_NAMES[key])) {
                    newDb.createObjectStore(STORE_NAMES[key]);
                    console.log(`IndexedDB: Created object store ${STORE_NAMES[key]}`);
                }
            }
        };

        request.onsuccess = (event) => {
            db = event.target.result;
            resolve(db);
        };

        request.onerror = (event) => {
            console.error('IndexedDB error:', event.target.errorCode, event.target.error);
            reject(new Error('Failed to open IndexedDB'));
        };
    });
}

/**
 * Retrieves data from a specified IndexedDB object store.
 * @param {string} storeName The name of the object store.
 * @returns {Promise<any>} A promise that resolves with the retrieved data, or undefined if not found.
 */
async function getFromIndexedDB(storeName) {
    try {
        const database = await openDB();
        const transaction = database.transaction([storeName], 'readonly');
        const store = transaction.objectStore(storeName);
        // We store the whole JSON under its store name as key (assuming single entry per store)
        const request = store.get(storeName);

        return new Promise((resolve, reject) => {
            request.onsuccess = (event) => {
                resolve(event.target.result);
            };
            request.onerror = (event) => {
                console.error(`Error getting from IndexedDB store ${storeName}:`, event.target.error);
                reject(event.target.error);
            };
        });
    } catch (error) {
        console.error('Error accessing IndexedDB for get:', error);
        throw error; // Re-throw to be caught by the caller
    }
}

/**
 * Saves data to a specified IndexedDB object store.
 * @param {string} storeName The name of the object store.
 * @param {any} data The data to save.
 * @returns {Promise<void>} A promise that resolves when the data is saved.
 */
async function saveToIndexedDB(storeName, data) {
    try {
        const database = await openDB();
        const transaction = database.transaction([storeName], 'readwrite');
        const store = transaction.objectStore(storeName);
        // Store the whole JSON under its store name as key
        const request = store.put(data, storeName);

        return new Promise((resolve, reject) => {
            request.onsuccess = () => {
                resolve();
            };
            request.onerror = (event) => {
                console.error(`Error saving to IndexedDB store ${storeName}:`, event.target.error);
                reject(event.target.error);
            };
        });
    } catch (error) {
        console.error('Error accessing IndexedDB for save:', error);
        throw error; // Re-throw to be caught by the caller
    }
}

// The clearMovies function is not used by main.js in the current implementation,
// as data is replaced by 'put' and specific stores are managed.
// If a global clear is needed, it would need to iterate through all stores or delete the DB.

export { getFromIndexedDB, saveToIndexedDB, STORE_NAMES };