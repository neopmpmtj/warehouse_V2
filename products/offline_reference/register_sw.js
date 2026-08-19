async function registerServiceWorker() {
    if ("serviceWorker" in navigator) {
        try {
            await navigator.serviceWorker.register(
                "/service-worker.js"
            );

            console.log("Service Worker registered");

        } catch (error) {
            console.error(
                "Service Worker registration failed:",
                error
            );
        }
    }
}


registerServiceWorker();
