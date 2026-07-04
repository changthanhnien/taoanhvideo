// api_shim.js - Intercepts window.fetch and routes to Qt WebChannel
(function() {
    console.log("[api_shim.js] Initializing Qt WebChannel API Shim...");

    const originalFetch = window.fetch;
    
    // Polyfill for QWebChannel if not loaded yet
    window.qtBridge = null;
    window._qtBridgeQueue = [];

    new QWebChannel(qt.webChannelTransport, function(channel) {
        window.qtBridge = channel.objects.qtBridge;
        console.log("[api_shim.js] qtBridge connected:", window.qtBridge);
        
        // Flush queue
        while (window._qtBridgeQueue.length > 0) {
            const req = window._qtBridgeQueue.shift();
            window.fetch(req.url, req.opt).then(req.resolve).catch(req.reject);
        }
        
        if (window.qtBridge && window.qtBridge.ready) {
            window.qtBridge.ready();
        }
    });

    window.fetch = function(url, opt) {
        opt = opt || {};
        // Only intercept /api/ routes
        if (!url.startsWith('/api/')) {
            return originalFetch(url, opt);
        }

        console.log(`[api_shim.js] Intercepted fetch: ${url}`);

        return new Promise(function(resolve, reject) {
            if (!window.qtBridge) {
                console.log("[api_shim.js] qtBridge not ready, queueing " + url + "...");
                window._qtBridgeQueue.push({ url: url, opt: opt, resolve: resolve, reject: reject });
                return;
            }

            var payload = {};
            var isFormData = false;

            if (opt.body && opt.body instanceof FormData) {
                isFormData = true;
                var files = [];
                // Safer iteration over FormData
                var formDataEntries = Array.from(opt.body.entries());
                for (var i = 0; i < formDataEntries.length; i++) {
                    var key = formDataEntries[i][0];
                    var value = formDataEntries[i][1];
                    if (value instanceof File) {
                        files.push({
                            name: value.name,
                            size: value.size,
                            type: value.type,
                            path: value.path || ""
                        });
                    } else {
                        payload[key] = value;
                    }
                }
                payload["_files"] = files;
            } else if (opt.body) {
                try {
                    payload = JSON.parse(opt.body);
                } catch (e) {
                    payload = { raw: opt.body };
                }
            }

            var requestData = JSON.stringify(payload);
            
            try {
                window.qtBridge.dispatch(url, requestData, function(responseStr) {
                    console.log("[api_shim.js] Response for " + url + ":", responseStr);
                    var res = new Response(responseStr, {
                        status: 200,
                        headers: { 'Content-Type': 'application/json' }
                    });
                    resolve(res);
                });
            } catch (err) {
                console.error("[api_shim.js] Error in dispatch for " + url + ":", err);
                resolve(new Response(JSON.stringify({ success: false, error: err.toString() })));
            }
        });
    };

    // Runtime UI fixes for unmodified main.js and index.html
    setTimeout(() => {
        const btnDownloadAll = document.getElementById('btn-download-all');
        if (btnDownloadAll && !btnDownloadAll.dataset.shimBound) {
            btnDownloadAll.dataset.shimBound = '1';
            btnDownloadAll.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.href = '/api/download_all';
            });
        }

        const observer = new MutationObserver((mutations) => {
            const progressVideoName = document.getElementById('progress-video-name');
            if (progressVideoName && progressVideoName.innerText === 'Đã hoàn thành toàn bộ danh sách!') {
                if (!window.__batchFinishedFired) {
                    window.__batchFinishedFired = true;
                    setTimeout(() => {
                        const btnRefresh = document.getElementById('btn-refresh-files');
                        if (btnRefresh) btnRefresh.click();
                    }, 100);
                }
            } else {
                window.__batchFinishedFired = false;
            }
        });
        
        const modal = document.getElementById('progress-modal');
        if (modal) {
            observer.observe(modal, { childList: true, subtree: true, characterData: true });
        }
    }, 500);

})();
