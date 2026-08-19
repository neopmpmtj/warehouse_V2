const DB_NAME = "centcompras";
const DB_VERSION = 1;

const PRODUCT_STORE = "products";
const META_STORE = "sync_metadata";


function openDatabase() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onupgradeneeded = function (event) {
            const db = event.target.result;

            if (!db.objectStoreNames.contains(PRODUCT_STORE)) {
                db.createObjectStore(PRODUCT_STORE, {
                    keyPath: "id"
                });
            }

            if (!db.objectStoreNames.contains(META_STORE)) {
                db.createObjectStore(META_STORE, {
                    keyPath: "key"
                });
            }
        };

        request.onsuccess = function () {
            resolve(request.result);
        };

        request.onerror = function () {
            reject(request.error);
        };
    });
}

async function saveProducts(products, catalogUpdatedAt) {
    const db = await openDatabase();

    return new Promise((resolve, reject) => {
        const transaction = db.transaction(
            [PRODUCT_STORE, META_STORE],
            "readwrite"
        );

        const productStore = transaction.objectStore(PRODUCT_STORE);
        const metaStore = transaction.objectStore(META_STORE);

        productStore.clear();

        for (const product of products) {
            productStore.put(product);
        }

        metaStore.put({
            key: "last_updated",
            value: new Date().toISOString()
        });

        if (catalogUpdatedAt) {
            metaStore.put({
                key: "catalog_updated_at",
                value: catalogUpdatedAt
            });
        } else {
            metaStore.delete("catalog_updated_at");
        }

        transaction.oncomplete = function () {
            resolve();
        };

        transaction.onerror = function () {
            reject(transaction.error);
        };
    });
}

async function getCachedProducts() {
    const db = await openDatabase();

    return new Promise((resolve, reject) => {
        const transaction = db.transaction(
            PRODUCT_STORE,
            "readonly"
        );

        const store = transaction.objectStore(PRODUCT_STORE);

        const request = store.getAll();

        request.onsuccess = function () {
            resolve(request.result);
        };

        request.onerror = function () {
            reject(request.error);
        };
    });
}

async function getSyncMetadata(key) {
    const db = await openDatabase();

    return new Promise((resolve, reject) => {
        const transaction = db.transaction(
            META_STORE,
            "readonly"
        );

        const store = transaction.objectStore(META_STORE);
        const request = store.get(key);

        request.onsuccess = function () {
            resolve(request.result ? request.result.value : null);
        };

        request.onerror = function () {
            reject(request.error);
        };
    });
}
