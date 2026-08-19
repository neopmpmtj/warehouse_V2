async function getItems() {
    const response = await fetch("/api/items/");

    if (!response.ok) {
        throw new Error("Server unavailable");
    }

    return response.json();
}


function formatCatalogTimestamp(isoTimestamp) {
    if (!isoTimestamp) {
        return "unknown time";
    }

    return new Date(isoTimestamp).toLocaleString();
}


function displayCatalogStatus(catalogUpdatedAt, fromCache) {
    const statusElement = document.getElementById("catalog-status");

    if (!statusElement) {
        return;
    }

    const timestampText = formatCatalogTimestamp(catalogUpdatedAt);

    if (fromCache) {
        statusElement.textContent =
            `Catalogue cached at ${timestampText}. Stock may be outdated until you reconnect.`;
        return;
    }

    statusElement.textContent = `Catalogue updated at ${timestampText}.`;
}


function displayItems(items) {
    const tableBody = document.getElementById("product-table-body");

    tableBody.replaceChildren();

    for (const item of items) {
        const row = document.createElement("tr");

        const idCell = document.createElement("td");
        idCell.textContent = item.id;

        const descriptionCell = document.createElement("td");
        descriptionCell.textContent = item.description;

        const stockCell = document.createElement("td");
        stockCell.textContent = item.stock;

        row.append(
            idCell,
            descriptionCell,
            stockCell
        );

        tableBody.appendChild(row);
    }
}


async function loadItems() {
    try {
        const data = await getItems();

        await saveProducts(data.items, data.catalog_updated_at);

        displayItems(data.items);
        displayCatalogStatus(data.catalog_updated_at, false);

        console.log("Items loaded from server");

    } catch (error) {
        const cachedProducts = await getCachedProducts();
        const catalogUpdatedAt = await getSyncMetadata("catalog_updated_at");

        displayItems(cachedProducts);

        if (cachedProducts.length === 0) {
            const statusElement = document.getElementById("catalog-status");
            if (statusElement) {
                statusElement.textContent = "No cached items available offline.";
            }
        } else {
            displayCatalogStatus(catalogUpdatedAt, true);
        }

        console.log("Items loaded from IndexedDB");
    }
}


loadItems();


window.addEventListener("online", () => {
    console.log("Connection restored. Refreshing items...");
    loadItems();
});


setInterval(() => {
    if (navigator.onLine) {
        loadItems();
    }
}, 30000);
