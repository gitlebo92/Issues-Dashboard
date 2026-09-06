/*
 * Makes a Dahua camera web UI work through /issues/camera-proxy/<unit>/<target>/.
 *
 * The camera app assumes it owns the origin: it requests root-relative URLs such as
 * /jsCore/app.js and /RPC2, and keeps its session in cookies and localStorage. Behind
 * the proxy those URLs miss the camera entirely, and several cameras in one grid would
 * otherwise share (and overwrite) each other's session state.
 */
(function () {
    var cfg = window.__workToolCamera;
    if (!cfg || cfg.ready) {
        return;
    }
    cfg.ready = true;

    cfg.errors = [];
    cfg.rpc = [];
    cfg.vendor = String(cfg.vendor || "dahua").toLowerCase();

    function isHikvision() {
        if (cfg.vendor === "hikvision") {
            return true;
        }
        // Runtime fallback when vendor was not stamped into the page config.
        return !!(
            document.getElementById("username")
            && document.getElementById("password")
            && (
                document.querySelector("button.login-btn")
                || /\/doc\/page\/login\.asp/i.test(location.pathname || "")
            )
        );
    }

    // Hikvision Live/PTZ need ActiveX in real IE. In the proxied Edge/Chrome tile we:
    //  - hide the "download plugin" flash early
    //  - after login, land on Configuration once
    //  - if the user opens Live View / PTZ, fill #main_plugin with substream JPEGs
    //  - Smart Event / VCA draw pages: never JPEG into #main_plugin; show Open IE CTA
    function installHikvisionConfigAssist() {
        if (cfg.hikConfigAssist) {
            return;
        }
        cfg.hikConfigAssist = true;

        var PLUGIN_NAG_SELECTORS = [
            ".pluginLink",
            "#main_plugin .txtTip",
            "#main_plugin table.txtTip",
            "#main_plugin .plugin",
            "#main_plugin .noPlugin",
            ".download-plugin",
            ".plugin-download",
            ".noPlugin",
            ".noPluginTip",
            ".downloadPlugin",
            "[class*='downloadPlugin']",
            "[class*='DownloadPlugin']",
            "[class*='plugin-tip']",
            "[ng-bind*='downloadPlugin']",
            "[ng-bind*='noPlugin']",
            "[ng-show*='bNoPlugin']",
            "[ng-if*='bNoPlugin']",
            "[ng-bind*='laPlugin']",
            "a[ng-click*='downloadPlugin']",
            "label[ng-bind*='downloadPlugin']",
            "label[ng-bind*='noPlugin']"
        ].join(",");

        var ANALYTICS_LABEL_RE = new RegExp(
            [
                "smart\\s*event",
                "intrusion",
                "line\\s*cross",
                "crossing\\s*detection",
                "region\\s*entrance",
                "region\\s*exiting",
                "region\\s*exit",
                "unattended\\s*baggage",
                "object\\s*removal",
                "\\bvca\\b",
                "video\\s*content\\s*analys",
                "draw\\s*(area|line|region|rule)",
                "rule\\s*drawing"
            ].join("|"),
            "i"
        );

        function injectPluginHideStyle() {
            if (document.getElementById("worktool-hik-hide-plugin")) {
                return;
            }
            var style = document.createElement("style");
            style.id = "worktool-hik-hide-plugin";
            style.textContent = [
                PLUGIN_NAG_SELECTORS + " {",
                "  display: none !important;",
                "  visibility: hidden !important;",
                "}",
                "#worktool-hik-jpeg {",
                "  display: block;",
                "  width: 100%;",
                "  height: 100%;",
                "  min-height: 240px;",
                "  object-fit: contain;",
                "  background: #000;",
                "  position: relative;",
                "  z-index: 5;",
                "}",
                "#worktool-hik-analytics-banner {",
                "  position: sticky;",
                "  top: 0;",
                "  z-index: 10050;",
                "  display: flex;",
                "  flex-wrap: wrap;",
                "  align-items: center;",
                "  gap: 8px;",
                "  padding: 8px 10px;",
                "  background: #1e3a5f;",
                "  color: #e2e8f0;",
                "  border-bottom: 1px solid #3b82f6;",
                "  font: 12px/1.35 Segoe UI, Arial, sans-serif;",
                "}",
                "#worktool-hik-analytics-banner button {",
                "  background: #2563eb;",
                "  color: #fff;",
                "  border: 0;",
                "  border-radius: 4px;",
                "  padding: 6px 10px;",
                "  cursor: pointer;",
                "  font: 12px Segoe UI, Arial, sans-serif;",
                "}",
                "#worktool-hik-analytics-banner button:hover { background: #1d4ed8; }"
            ].join("\n");
            (document.head || document.documentElement).appendChild(style);
        }

        function looksLikePluginNag(node) {
            if (!node || node.nodeType !== 1) {
                return false;
            }
            var text = String(node.textContent || "").toLowerCase().replace(/\s+/g, " ").trim();
            if (!text || text.length > 160) {
                return false;
            }
            return (
                (text.indexOf("download") >= 0 && (text.indexOf("plugin") >= 0 || text.indexOf("addon") >= 0))
                || text.indexOf("please install") >= 0
                || text.indexOf("webcomponents") >= 0
            );
        }

        function hidePluginNags() {
            injectPluginHideStyle();
            var tips = document.querySelectorAll(PLUGIN_NAG_SELECTORS);
            for (var i = 0; i < tips.length; i += 1) {
                tips[i].style.setProperty("display", "none", "important");
                tips[i].style.setProperty("visibility", "hidden", "important");
            }
            var plugin = document.getElementById("main_plugin");
            if (plugin) {
                var kids = plugin.querySelectorAll("div, table, p, span, a, label");
                for (var k = 0; k < kids.length; k += 1) {
                    if (kids[k].id === "worktool-hik-jpeg") {
                        continue;
                    }
                    if (looksLikePluginNag(kids[k])) {
                        kids[k].style.setProperty("display", "none", "important");
                    }
                }
            }
        }

        function shortLabel(node) {
            if (!node || node.nodeType !== 1) {
                return "";
            }
            var label = "";
            if (node.getAttribute) {
                label = String(
                    node.getAttribute("title")
                    || node.getAttribute("aria-label")
                    || node.getAttribute("data-i18n")
                    || node.getAttribute("ng-bind")
                    || ""
                );
            }
            if (!label && node.childNodes && node.childNodes.length <= 4) {
                label = String(node.textContent || "");
            }
            return label.toLowerCase().replace(/\s+/g, " ").trim();
        }

        function textLooksLikeAnalytics(text) {
            return ANALYTICS_LABEL_RE.test(String(text || ""));
        }

        function isAnalyticsDrawContext() {
            var pathBlob = [
                location.pathname || "",
                location.hash || "",
                location.search || ""
            ].join(" ");
            if (textLooksLikeAnalytics(pathBlob)) {
                return true;
            }
            if (cfg.hikAnalyticsDraw) {
                // Sticky until Live/preview clears it — covers Angular config.asp routes.
                return true;
            }
            // Only active/selected items + page titles (not the whole left-nav tree).
            var nodes = document.querySelectorAll(
                ".active, .selected, .cur, .current, .on, [aria-selected='true'],"
                + " h1, h2, h3, .title, .page-title, .breadcrumb, .nav-title"
            );
            for (var i = 0; i < nodes.length; i += 1) {
                var t = shortLabel(nodes[i]) || String(nodes[i].textContent || "")
                    .toLowerCase().replace(/\s+/g, " ").trim();
                if (t && t.length <= 64 && textLooksLikeAnalytics(t)) {
                    return true;
                }
            }
            return false;
        }

        function shouldStayOnCurrentPage() {
            return !!(cfg.hikStayOnLive || cfg.hikAnalyticsDraw || cfg.hikConfigClicked || isAnalyticsDrawContext());
        }

        function wantsLiveVideo() {
            // Drawing VCA rules needs the ActiveX surface — never wipe it with JPEG.
            if (isAnalyticsDrawContext()) {
                return false;
            }
            var path = location.pathname || "";
            // JPEG only on Live View (preview.asp). Config / Smart Event pages must keep
            // #main_plugin free for the plugin draw surface (or the Open IE banner).
            if (!/\/doc\/page\/preview\.asp/i.test(path)) {
                return false;
            }
            return !!(cfg.hikStayOnLive || cfg.hikConfigClicked);
        }

        function jpegHost() {
            var plugin = document.getElementById("main_plugin");
            if (plugin) {
                return plugin;
            }
            return (
                document.getElementById("main_img")
                || document.getElementById("img")
                || document.querySelector(".main-content, .content, #content")
            );
        }

        function stopJpegLive() {
            var img = document.getElementById("worktool-hik-jpeg");
            if (img && img.parentNode) {
                img.parentNode.removeChild(img);
            }
            cfg.hikJpegBusy = false;
        }

        function directCameraUrl() {
            return String(cfg.origin || cfg.directUrl || "").replace(/\/?$/, "/");
        }

        function openDirectIeTab() {
            var url = directCameraUrl();
            if (!url) {
                window.alert("No direct camera URL available for Open IE.");
                return;
            }
            try {
                if (window.parent && window.parent !== window) {
                    window.parent.postMessage({
                        type: "workToolOpenCameraIe",
                        url: url
                    }, "*");
                    return;
                }
            } catch (err) {
                cfg.hikOpenIePostError = String(err);
            }
            var win = window.open(url, "_blank");
            if (win) {
                try {
                    win.opener = null;
                } catch (err) {
                    // ignore
                }
            } else {
                window.alert("Pop-up blocked. Allow pop-ups, or use Open IE on the tile header.");
            }
        }

        function ensureAnalyticsBanner() {
            injectPluginHideStyle();
            var banner = document.getElementById("worktool-hik-analytics-banner");
            if (!isAnalyticsDrawContext()) {
                if (banner) {
                    banner.style.display = "none";
                }
                return;
            }
            stopJpegLive();
            if (!banner) {
                banner = document.createElement("div");
                banner.id = "worktool-hik-analytics-banner";
                banner.innerHTML = (
                    "<span>Drawing intrusion / line-cross rules needs the ActiveX plugin "
                    + "(not available in this tile iframe). Open this camera in Edge IE mode.</span>"
                );
                var btn = document.createElement("button");
                btn.type = "button";
                btn.textContent = "Open IE";
                btn.addEventListener("click", function (event) {
                    event.preventDefault();
                    event.stopPropagation();
                    openDirectIeTab();
                });
                banner.appendChild(btn);
                var host = document.body || document.documentElement;
                if (host.firstChild) {
                    host.insertBefore(banner, host.firstChild);
                } else {
                    host.appendChild(banner);
                }
            }
            banner.style.display = "flex";
        }

        function ensureJpegLive() {
            if (!wantsLiveVideo()) {
                if (isAnalyticsDrawContext()) {
                    stopJpegLive();
                    ensureAnalyticsBanner();
                }
                return;
            }
            var banner = document.getElementById("worktool-hik-analytics-banner");
            if (banner) {
                banner.style.display = "none";
            }
            hidePluginNags();
            var host = jpegHost();
            if (!host) {
                return;
            }
            var img = document.getElementById("worktool-hik-jpeg");
            if (!img || img.parentNode !== host) {
                // Keep replacing plugin nag markup Angular re-inserts into #main_plugin.
                var existing = host.querySelectorAll("object, embed, .pluginLink, .txtTip");
                for (var e = 0; e < existing.length; e += 1) {
                    existing[e].style.setProperty("display", "none", "important");
                }
                if (!img) {
                    img = document.createElement("img");
                    img.id = "worktool-hik-jpeg";
                    img.alt = "live";
                }
                host.style.minHeight = "240px";
                host.style.height = host.style.height || "100%";
                host.style.background = "#000";
                host.appendChild(img);
                cfg.hikJpegChannel = cfg.hikJpegChannel || 102;
                cfg.hikJpegBusy = false;
            }
            if (cfg.hikJpegBusy) {
                return;
            }
            cfg.hikJpegBusy = true;
            var channel = cfg.hikJpegChannel || 102;
            var url = String(cfg.prefix || "").replace(/\/$/, "")
                + "/ISAPI/Streaming/channels/" + channel
                + "/picture?t=" + Date.now();
            var probe = new Image();
            probe.onload = function () {
                img.src = probe.src;
                cfg.hikJpegBusy = false;
                cfg.directStream = true;
            };
            probe.onerror = function () {
                if (channel === 102) {
                    cfg.hikJpegChannel = 101;
                } else if (channel === 101) {
                    cfg.hikJpegChannel = 102;
                }
                cfg.hikJpegBusy = false;
            };
            probe.src = url;
        }

        function nodeLooksLikeLiveNav(node) {
            if (!node || node.nodeType !== 1) {
                return false;
            }
            var attr = String(
                (node.getAttribute && (
                    node.getAttribute("ng-click")
                    || node.getAttribute("href")
                    || node.getAttribute("data-i18n")
                    || node.getAttribute("ng-bind")
                    || ""
                )) || ""
            );
            if (
                /jumpTo\(\s*['\"]preview['\"]/i.test(attr)
                || /preview\.asp/i.test(attr)
                || /['\"]preview['\"]/i.test(attr)
                || /live\s*view/i.test(attr)
                || /ptz/i.test(attr)
            ) {
                return true;
            }
            // Prefer short labels from the clicked control, not huge containers.
            var label = shortLabel(node);
            if (!label || label.length > 40) {
                return false;
            }
            return (
                label === "live view"
                || label === "live"
                || label === "preview"
                || label.indexOf("live view") >= 0
                || /^ptz\b/.test(label)
                || label.indexOf("ptz") >= 0 && label.length < 20
            );
        }

        function nodeLooksLikeAnalyticsNav(node) {
            if (!node || node.nodeType !== 1) {
                return false;
            }
            var attr = String(
                (node.getAttribute && (
                    node.getAttribute("ng-click")
                    || node.getAttribute("href")
                    || node.getAttribute("data-i18n")
                    || node.getAttribute("ng-bind")
                    || node.getAttribute("ui-sref")
                    || ""
                )) || ""
            );
            if (textLooksLikeAnalytics(attr)) {
                return true;
            }
            var label = shortLabel(node);
            if (!label || label.length > 56) {
                return false;
            }
            return textLooksLikeAnalytics(label);
        }

        function markUserNavIntent(event) {
            var node = event.target;
            if (node && node.closest && node.closest("#worktool-hik-analytics-banner")) {
                return;
            }
            var depth = 0;
            while (node && node !== document && depth < 10) {
                if (node.id === "worktool-hik-analytics-banner") {
                    return;
                }
                if (nodeLooksLikeAnalyticsNav(node)) {
                    cfg.hikAnalyticsDraw = true;
                    cfg.hikConfigClicked = true;
                    // Stay on Smart Event pages — never bounce back to Configuration root.
                    stopJpegLive();
                    setTimeout(ensureAnalyticsBanner, 50);
                    setTimeout(ensureAnalyticsBanner, 300);
                    return;
                }
                if (nodeLooksLikeLiveNav(node)) {
                    cfg.hikStayOnLive = true;
                    cfg.hikAnalyticsDraw = false;
                    // Do not clear config intent permanently — just stop redirecting away.
                    cfg.hikConfigClicked = true;
                    setTimeout(ensureJpegLive, 50);
                    setTimeout(ensureJpegLive, 300);
                    return;
                }
                node = node.parentNode;
                depth += 1;
            }
        }
        document.addEventListener("click", markUserNavIntent, true);

        function goConfig() {
            if (shouldStayOnCurrentPage()) {
                return true;
            }
            if (/\/doc\/page\/config\.asp/i.test(location.pathname || "")) {
                cfg.hikConfigClicked = true;
                return true;
            }
            var links = document.querySelectorAll("#nav a, .nav a, a, li, span, button");
            for (var i = 0; i < links.length; i += 1) {
                var attr = links[i].getAttribute("ng-click") || "";
                var href = links[i].getAttribute("href") || "";
                var text = (links[i].textContent || "").trim().toLowerCase();
                if (text.length > 40) {
                    continue;
                }
                if (
                    /jumpTo\(\s*['\"]config['\"]\s*\)/i.test(attr)
                    || /config\.asp/i.test(href)
                    || text === "configuration"
                    || text === "config"
                ) {
                    try {
                        links[i].click();
                        cfg.hikConfigClicked = true;
                        return true;
                    } catch (err) {
                        cfg.hikConfigError = String(err);
                    }
                }
            }
            if (/\/doc\/page\/preview\.asp/i.test(location.pathname || "")) {
                var prefix = String(cfg.prefix || "").replace(/\/$/, "");
                cfg.hikConfigClicked = true;
                location.href = prefix + "/doc/page/config.asp";
                return true;
            }
            return false;
        }

        function syncLivePathIntent() {
            var path = location.pathname || "";
            // After the one-time config landing, staying on / returning to preview means Live.
            if (cfg.hikConfigClicked && /\/doc\/page\/preview\.asp/i.test(path)) {
                cfg.hikStayOnLive = true;
                cfg.hikAnalyticsDraw = false;
            }
            var pathBlob = [
                location.pathname || "",
                location.hash || "",
                location.search || ""
            ].join(" ");
            if (textLooksLikeAnalytics(pathBlob)) {
                cfg.hikAnalyticsDraw = true;
            }
        }

        function tick() {
            hidePluginNags();
            try {
                window.scrollTo(0, 0);
            } catch (err) {
                // ignore
            }
            syncLivePathIntent();
            if (isAnalyticsDrawContext()) {
                stopJpegLive();
                ensureAnalyticsBanner();
            } else {
                ensureJpegLive();
            }
            if (shouldStayOnCurrentPage()) {
                return;
            }
            if (
                /\/doc\/page\/preview\.asp/i.test(location.pathname || "")
                || (!loginForm() && /\/doc\/page\//i.test(location.pathname || ""))
            ) {
                goConfig();
            }
        }

        injectPluginHideStyle();
        hidePluginNags();
        if (!document.body) {
            document.addEventListener("DOMContentLoaded", function () {
                injectPluginHideStyle();
                hidePluginNags();
            });
        }
        try {
            var obs = new MutationObserver(function () {
                hidePluginNags();
                if (isAnalyticsDrawContext()) {
                    stopJpegLive();
                    ensureAnalyticsBanner();
                    return;
                }
                if (cfg.hikStayOnLive || /\/doc\/page\/preview\.asp/i.test(location.pathname || "")) {
                    ensureJpegLive();
                }
            });
            obs.observe(document.documentElement, { childList: true, subtree: true });
        } catch (err) {
            cfg.hikObsError = String(err);
        }
        var hikTickMs = 350;
        var hikTickTimer = setInterval(function hikTick() {
            tick();
        }, hikTickMs);
        setTimeout(tick, 50);
        setTimeout(tick, 200);
        // After the first minute on Config/Live JPEG, poll less often — MutationObserver
        // still catches DOM nags; this only reduces busy tick CPU.
        setTimeout(function () {
            if (hikTickMs === 1200) {
                return;
            }
            hikTickMs = 1200;
            clearInterval(hikTickTimer);
            hikTickTimer = setInterval(function hikTick() {
                tick();
            }, hikTickMs);
        }, 60000);
    }

    // Install ASAP (before XHR/storage hooks) so nags stay hidden while the app boots.
    if (isHikvision()) {
        installHikvisionConfigAssist();
    }

    // Some firmwares (e.g. RD3175 Camera 1) omit webCaps.isShowCanvasPlayer, so the
    // UI stays on OCX and shows "please download addon". Sibling cameras on the same
    // unit often advertise the canvas player — force H5 for the proxied grid.
    if (!isHikvision()) {
    (function forceHtml5Player() {
        var caps = window.webCaps;
        if (!caps || typeof caps !== "object") {
            caps = {};
        }
        caps.isShowCanvasPlayer = true;
        try {
            Object.defineProperty(window, "webCaps", {
                configurable: true,
                enumerable: true,
                get: function () {
                    return caps;
                },
                set: function (value) {
                    caps = value && typeof value === "object" ? value : {};
                    caps.isShowCanvasPlayer = true;
                }
            });
        } catch (err) {
            cfg.webCapsHookError = String(err);
        }

        var globalObj = window.global;
        function patchGlobal(target) {
            if (!target || typeof target !== "object") {
                return target;
            }
            target.supportH5Player = function () {
                return true;
            };
            return target;
        }
        if (globalObj) {
            patchGlobal(globalObj);
        }
        try {
            Object.defineProperty(window, "global", {
                configurable: true,
                enumerable: true,
                get: function () {
                    return globalObj;
                },
                set: function (value) {
                    globalObj = patchGlobal(value);
                }
            });
        } catch (err) {
            cfg.globalHookError = String(err);
        }

        function keepH5() {
            if (caps && typeof caps === "object") {
                caps.isShowCanvasPlayer = true;
            }
            if (window.global) {
                patchGlobal(window.global);
            }
            if (window.webApp && window.webApp.playMode && window.webApp.playMode !== "h5") {
                window.webApp.playMode = "h5";
                cfg.forcedPlayModeH5 = true;
            }
            if (window.plugin && window.plugin.type === "ocx") {
                window.plugin.type = "";
            }
            var tips = document.querySelectorAll(".download-plugin");
            for (var i = 0; i < tips.length; i += 1) {
                tips[i].style.display = "none";
            }
        }
        keepH5();
        // Fast while the OCX UI is still fighting us; back off once H5 sticks.
        var h5Ms = 200;
        var h5Timer = setInterval(function keepH5Tick() {
            keepH5();
            var settled = !!(
                cfg.forcedPlayModeH5
                || (window.webApp && window.webApp.playMode === "h5")
            );
            var want = settled ? 2000 : 200;
            if (want !== h5Ms) {
                h5Ms = want;
                clearInterval(h5Timer);
                h5Timer = setInterval(keepH5Tick, h5Ms);
            }
        }, h5Ms);
    }());
    }

    // Newer firmware hides the home "AI" tile when ProductDefinition says
    // MainIntelliScreen.SupportHide. That flag is set on these cameras even though
    // the AI pages work; clear it before the home menu evaluates its conditions.
    function revealAiHomeTile(target) {
        if (!target || typeof target !== "object") {
            return;
        }
        try {
            target.HideMainScreen = false;
            if (!target.MainIntelliScreen || typeof target.MainIntelliScreen !== "object") {
                target.MainIntelliScreen = {};
            }
            target.MainIntelliScreen.SupportHide = false;
        } catch (err) {
            cfg.aiRevealError = String(err);
        }
    }

    function watchProductDefinition(app) {
        if (!app || app._workToolAiWatch) {
            return;
        }
        app._workToolAiWatch = true;
        revealAiHomeTile(app.PD);
        try {
            var current = app.PD;
            Object.defineProperty(app, "PD", {
                configurable: true,
                enumerable: true,
                get: function () {
                    return current;
                },
                set: function (value) {
                    current = value;
                    revealAiHomeTile(current);
                }
            });
            if (current) {
                revealAiHomeTile(current);
            }
        } catch (err) {
            cfg.aiWatchError = String(err);
        }
    }

    var pdTimer = setInterval(function () {
        if (window.webApp) {
            watchProductDefinition(window.webApp);
            revealAiHomeTile(window.webApp.PD);
            if (window.webApp._workToolAiWatch) {
                clearInterval(pdTimer);
            }
        }
    }, 200);

    window.addEventListener("error", function (event) {
        cfg.errors.push("err " + (event.message || "") + " @" + String(event.filename || "").slice(-28) + ":" + event.lineno);
    });
    window.addEventListener("unhandledrejection", function (event) {
        var text;
        try {
            text = JSON.stringify(event.reason);
        } catch (err) {
            text = String(event.reason);
        }
        cfg.errors.push("rej " + String(text).slice(0, 300));
    });
    var xhrSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function (payload) {
        var request = this;
        var method = "";
        try {
            method = JSON.parse(payload).method || "";
        } catch (err) {
            method = "";
        }
        if (method) {
            request.addEventListener("load", function () {
                var note = request.status + " " + method;
                try {
                    var parsed = JSON.parse(request.responseText);
                    if (parsed.result === false) {
                        note += " FAIL " + JSON.stringify(parsed.error || {}).slice(0, 90)
                            + " REQ " + String(payload).slice(0, 200);
                    }
                } catch (err) {
                    note += " <unparsed>";
                }
                cfg.rpc.push(note);
            });
        }
        return xhrSend.apply(this, arguments);
    };

    var PREFIX = String(cfg.prefix || "").replace(/\/$/, "");
    var ORIGIN = String(cfg.origin || "").replace(/\/$/, "");
    var NS = PREFIX + "::";
    var SHIM_PATH = "/static/camera_shim.js";

    function rewrite(url) {
        if (typeof url !== "string" || !url) {
            return url;
        }
        var out = url;
        if (ORIGIN && out.indexOf(ORIGIN) === 0) {
            out = out.slice(ORIGIN.length) || "/";
        }
        // Loaders such as seajs resolve module ids against the page origin first.
        if (out.indexOf(location.origin) === 0) {
            out = out.slice(location.origin.length) || "/";
        }
        if (out.charAt(0) !== "/" || out.charAt(1) === "/") {
            return out;
        }
        if (out === PREFIX || out.indexOf(PREFIX + "/") === 0) {
            return out;
        }
        // Newer firmware serves its own bundle from /static/, so only this script and
        // the proxy routes themselves are left alone.
        if (out.indexOf("/issues/camera-proxy/") === 0 || out.indexOf(SHIM_PATH) === 0) {
            return out;
        }
        return PREFIX + out;
    }
    cfg.rewrite = rewrite;

    var xhrOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url) {
        var args = Array.prototype.slice.call(arguments);
        args[1] = rewrite(url);
        return xhrOpen.apply(this, args);
    };

    if (window.fetch) {
        var nativeFetch = window.fetch;
        window.fetch = function (input, init) {
            if (typeof input === "string") {
                input = rewrite(input);
            } else if (input && typeof input.url === "string") {
                input = new Request(rewrite(input.url), input);
            }
            return nativeFetch.call(window, input, init);
        };
    }

    // Runs inside each worker the camera app starts. Workers get their own global
    // scope, so the rewrites installed above do not reach them, and the video
    // decoder worker requests its code and stream with root-relative URLs.
    function workerPrelude(config) {
        function rewriteInWorker(url) {
            var out = String(url || "");
            if (out.charAt(0) !== "/" || out.charAt(1) === "/") {
                return out;
            }
            if (out === config.prefix || out.indexOf(config.prefix + "/") === 0) {
                return config.pageOrigin + out;
            }
            return config.pageOrigin + config.prefix + out;
        }
        // ffmpegasm.js asks for ffmpegasm.js.mem next to itself (/module/), but
        // the camera serves that file at the site root.
        self.Module = self.Module || {};
        self.Module.locateFile = function (path) {
            var name = String(path || "").split("/").pop();
            // Some cameras keep ffmpegasm assets under /module/, others at root.
            var folder = name.indexOf("ffmpegasm") === 0 ? "/module/" : "/";
            return config.pageOrigin + config.prefix + folder + name;
        };
        var nativeImport = self.importScripts;
        self.importScripts = function () {
            return nativeImport.apply(self, Array.prototype.map.call(arguments, rewriteInWorker));
        };
        if (self.fetch) {
            var nativeFetch = self.fetch;
            self.fetch = function (input, init) {
                return nativeFetch.call(
                    self,
                    typeof input === "string" ? rewriteInWorker(input) : input,
                    init
                );
            };
        }
        if (self.XMLHttpRequest) {
            var nativeOpen = XMLHttpRequest.prototype.open;
            XMLHttpRequest.prototype.open = function (method, url) {
                var args = Array.prototype.slice.call(arguments);
                args[1] = rewriteInWorker(url);
                return nativeOpen.apply(this, args);
            };
        }
        if (self.WebSocket && config.wsOrigin) {
            var NativeSocket = self.WebSocket;
            var plugin = /^wss?:\/\/(127\.0\.0\.1|localhost):(23450|23490)/i;
            var Redirected = function (url, protocols) {
                var target = String(url || "");
                if (plugin.test(target)) {
                    return {
                        readyState: 3,
                        send: function () {},
                        close: function () {},
                        addEventListener: function () {},
                        removeEventListener: function () {}
                    };
                }
                if (target.indexOf(config.wsOrigin) !== 0) {
                    var path = target.replace(/^wss?:\/\/[^/]*/i, "") || "/";
                    if (path.indexOf(config.prefix + "/") === 0) {
                        path = path.slice(config.prefix.length);
                    }
                    if (/rtspoverwebsocket/i.test(path) || path === "/" || path === "") {
                        path = "/rtspoverwebsocket";
                    }
                    target = config.wsOrigin + path;
                }
                return protocols === undefined
                    ? new NativeSocket(target)
                    : new NativeSocket(target, protocols);
            };
            Redirected.prototype = NativeSocket.prototype;
            ["CONNECTING", "OPEN", "CLOSING", "CLOSED"].forEach(function (name) {
                Redirected[name] = NativeSocket[name];
            });
            self.WebSocket = Redirected;
        }
    }

    // The H5 player decodes video in a Web Worker. Its URL is either built from the
    // app's public path ("/"), which 404s on the dashboard, or a blob whose code
    // resolves imports against the dashboard root; either way the pane stays black
    // with no error, so both forms are re-pointed at the camera here.
    ["Worker", "SharedWorker"].forEach(function (name) {
        var Native = window[name];
        if (!Native) {
            return;
        }
        function Wrapped(url, options) {
            var target = rewrite(String(url));
            if (/^blob:/i.test(String(url))) {
                target = withPrelude(target);
            }
            return options === undefined ? new Native(target) : new Native(target, options);
        }
        Wrapped.prototype = Native.prototype;
        window[name] = Wrapped;
    });

    function withPrelude(blobUrl) {
        try {
            var request = new XMLHttpRequest();
            request.open("GET", blobUrl, false);
            request.send();
            var config = JSON.stringify({
                prefix: PREFIX,
                wsOrigin: String(cfg.wsOrigin || ""),
                pageOrigin: String(location.origin || "")
            });
            var source = "(" + workerPrelude.toString() + ")(" + config + ");\n" + request.responseText;
            return URL.createObjectURL(new Blob([source], { type: "application/javascript" }));
        } catch (err) {
            cfg.workerError = String(err);
            return blobUrl;
        }
    }

    var setAttribute = Element.prototype.setAttribute;
    Element.prototype.setAttribute = function (name, value) {
        if (/^(src|href|action)$/i.test(String(name))) {
            value = rewrite(value);
        }
        return setAttribute.call(this, name, value);
    };

    function patchUrlProperty(ctor, prop) {
        if (!ctor) {
            return;
        }
        var desc = Object.getOwnPropertyDescriptor(ctor.prototype, prop);
        if (!desc || !desc.set) {
            return;
        }
        Object.defineProperty(ctor.prototype, prop, {
            configurable: true,
            enumerable: desc.enumerable,
            get: desc.get,
            set: function (value) {
                desc.set.call(this, rewrite(value));
            }
        });
    }
    patchUrlProperty(window.HTMLScriptElement, "src");
    patchUrlProperty(window.HTMLImageElement, "src");
    patchUrlProperty(window.HTMLIFrameElement, "src");
    patchUrlProperty(window.HTMLLinkElement, "href");
    patchUrlProperty(window.HTMLAnchorElement, "href");
    patchUrlProperty(window.HTMLFormElement, "action");

    // Live video runs over a WebSocket, which the HTTP proxy cannot forward. Point it
    // at the camera directly; it only works when the browser can reach the camera, and
    // falls back to a stalled video pane when it cannot.
    function installWebSocketProxy() {
        if (!window.WebSocket || !cfg.wsOrigin) {
            return false;
        }
        if (cfg._ProxiedWebSocket && window.WebSocket === cfg._ProxiedWebSocket) {
            return true;
        }
        var NativeWebSocket = cfg._NativeWebSocket || window.WebSocket;
        cfg._NativeWebSocket = NativeWebSocket;
        cfg.sockets = cfg.sockets || [];
        // Newer firmware probes a local OCX helper. If that socket ever opens, the
        // app switches playMode to "ocx" and the iframe live view stays black.
        var LOCAL_PLUGIN = /^wss?:\/\/(127\.0\.0\.1|localhost):(23450|23490)/i;
        function deadPluginSocket() {
            var sock = {
                readyState: 3,
                bufferedAmount: 0,
                extensions: "",
                protocol: "",
                url: "",
                send: function () {},
                close: function () {},
                addEventListener: function () {},
                removeEventListener: function () {}
            };
            Object.defineProperty(sock, "onopen", { value: null, writable: true });
            Object.defineProperty(sock, "onclose", { value: null, writable: true });
            Object.defineProperty(sock, "onerror", { value: null, writable: true });
            Object.defineProperty(sock, "onmessage", { value: null, writable: true });
            return sock;
        }
        var ProxiedWebSocket = function (url, protocols) {
            var target = String(url || "");
            if (LOCAL_PLUGIN.test(target)) {
                cfg.sockets.push("blocked-plugin " + target);
                return deadPluginSocket();
            }
            // The player builds its URL from the page host and a port the camera
            // reports for itself, so neither half can be trusted here.
            if (target.indexOf(cfg.wsOrigin) !== 0) {
                var path = target.replace(/^wss?:\/\/[^/]*/i, "") || "/";
                if (path.indexOf(PREFIX + "/") === 0) {
                    path = path.slice(PREFIX.length);
                }
                if (/httpprivateoverwebsocket/i.test(path)) {
                    path = "/httpprivateoverwebsocket";
                } else if (/rtspoverwebsocket/i.test(path) || path === "/" || path === "") {
                    path = "/rtspoverwebsocket";
                }
                target = cfg.wsOrigin + path;
            }
            cfg.sockets.push(target);
            return protocols === undefined
                ? new NativeWebSocket(target)
                : new NativeWebSocket(target, protocols);
        };
        ProxiedWebSocket.prototype = NativeWebSocket.prototype;
        ["CONNECTING", "OPEN", "CLOSING", "CLOSED"].forEach(function (name) {
            ProxiedWebSocket[name] = NativeWebSocket[name];
        });
        cfg._ProxiedWebSocket = ProxiedWebSocket;
        window.WebSocket = ProxiedWebSocket;
        return true;
    }
    installWebSocketProxy();
    // Some camera scripts redefine WebSocket later; keep ours in place.
    // Check often until ours sticks, then rarely.
    var wsMs = 1000;
    var wsTimer = setInterval(function wsCheck() {
        installWebSocketProxy();
        var ours = cfg._ProxiedWebSocket && window.WebSocket === cfg._ProxiedWebSocket;
        var want = ours ? 5000 : 1000;
        if (want !== wsMs) {
            wsMs = want;
            clearInterval(wsTimer);
            wsTimer = setInterval(wsCheck, wsMs);
        }
    }, wsMs);

    var cookieDesc = Object.getOwnPropertyDescriptor(Document.prototype, "cookie");
    if (cookieDesc && cookieDesc.set) {
        Object.defineProperty(document, "cookie", {
            configurable: true,
            get: function () {
                return cookieDesc.get.call(document);
            },
            set: function (value) {
                var cleaned = String(value)
                    .replace(/;\s*path\s*=[^;]*/gi, "")
                    .replace(/;\s*domain\s*=[^;]*/gi, "");
                cookieDesc.set.call(document, cleaned + "; path=" + PREFIX + "/");
            }
        });
    }

    function namespaced(real) {
        function keys() {
            var out = [];
            for (var i = 0; i < real.length; i += 1) {
                var key = real.key(i);
                if (key && key.indexOf(NS) === 0) {
                    out.push(key.slice(NS.length));
                }
            }
            return out;
        }
        var api = {
            getItem: function (key) {
                return real.getItem(NS + key);
            },
            setItem: function (key, value) {
                real.setItem(NS + key, value);
            },
            get: function (key) {
                return real.getItem(NS + key);
            },
            set: function (key, value) {
                real.setItem(NS + key, value);
            },
            removeItem: function (key) {
                real.removeItem(NS + key);
            },
            key: function (index) {
                var found = keys()[index];
                return found === undefined ? null : found;
            },
            clear: function () {
                keys().forEach(function (key) {
                    real.removeItem(NS + key);
                });
            }
        };
        return new Proxy(api, {
            get: function (target, prop) {
                if (prop === "length") {
                    return keys().length;
                }
                if (prop in target) {
                    return target[prop];
                }
                if (typeof prop !== "string") {
                    return undefined;
                }
                return real.getItem(NS + prop);
            },
            set: function (target, prop, value) {
                real.setItem(NS + String(prop), String(value));
                return true;
            },
            deleteProperty: function (target, prop) {
                real.removeItem(NS + String(prop));
                return true;
            },
            has: function (target, prop) {
                return prop in target || real.getItem(NS + String(prop)) !== null;
            }
        });
    }
    try {
        var localShim = namespaced(window.localStorage);
        var sessionShim = namespaced(window.sessionStorage);
        Object.defineProperty(window, "localStorage", {
            configurable: true,
            get: function () {
                return localShim;
            }
        });
        Object.defineProperty(window, "sessionStorage", {
            configurable: true,
            get: function () {
                return sessionShim;
            }
        });
    } catch (err) {
        cfg.storageIsolated = false;
    }

    var login = { tries: 0, clicks: 0, clickedAt: 0, timer: 0 };
    cfg.login = login;

    // The page ships hidden copies of several dialogs, so ids are not unique;
    // only the on-screen login form should be touched.
    function pickVisible(selector) {
        var nodes = document.querySelectorAll(selector);
        for (var i = 0; i < nodes.length; i += 1) {
            if (nodes[i].offsetParent !== null) {
                return nodes[i];
            }
        }
        return null;
    }

    function legacyLoginForm() {
        var user = pickVisible("#login_user");
        var pass = pickVisible("#login_psw");
        var button = pickVisible('[btn-for="onLogin"]');
        if (!user || !pass || !button) {
            return null;
        }
        return { user: user, pass: pass, button: button, react: false };
    }

    // Hikvision Angular login (#username / #password / .login-btn).
    function hikvisionLoginForm() {
        var user = document.getElementById("username");
        var pass = document.getElementById("password");
        var button = document.querySelector("button.login-btn")
            || document.querySelector("button.btn-primary.login-btn");
        if (!user || !pass || !button) {
            return null;
        }
        return { user: user, pass: pass, button: button, hikvision: true };
    }

    function hikvisionLoginScope() {
        if (!window.angular) {
            return null;
        }
        var user = document.getElementById("username");
        if (!user) {
            return null;
        }
        try {
            var scope = window.angular.element(user).scope();
            while (scope && typeof scope.login !== "function") {
                scope = scope.$parent;
            }
            return scope || null;
        } catch (err) {
            cfg.angularError = String(err);
            return null;
        }
    }

    // ng-model ignores plain .value writes; set the controller scope then call login().
    function submitHikvisionLogin() {
        var scope = hikvisionLoginScope();
        if (!scope) {
            return false;
        }
        var userEl = document.getElementById("username");
        var passEl = document.getElementById("password");
        function applyCreds() {
            scope.username = String(cfg.user || "");
            scope.password = String(cfg.pass || "");
            if (userEl) {
                userEl.value = scope.username;
            }
            if (passEl) {
                passEl.value = scope.password;
            }
        }
        try {
            if (scope.$$phase || (scope.$root && scope.$root.$$phase)) {
                applyCreds();
            } else {
                scope.$apply(applyCreds);
            }
        } catch (err) {
            applyCreds();
            cfg.angularError = String(err);
        }
        if (!scope.username || !scope.password) {
            cfg.hikLoginEmpty = true;
            return false;
        }
        try {
            scope.login();
            cfg.hikLoginEmpty = false;
            return true;
        } catch (err) {
            cfg.clickError = String(err);
            return false;
        }
    }

    // Newer firmware ships a React/Ant Design login with generated ids.
    function modernLoginForm() {
        var pass = pickVisible('input[id^="PasswordInput"]');
        var button = pickVisible("button.login-button");
        if (!pass || !button) {
            return null;
        }
        var user = null;
        var candidates = document.querySelectorAll("input.ant-input");
        for (var i = 0; i < candidates.length; i += 1) {
            if (candidates[i] !== pass && candidates[i].offsetParent !== null) {
                user = candidates[i];
                break;
            }
        }
        if (!user) {
            return null;
        }
        return { user: user, pass: pass, button: button, react: true };
    }

    function loginForm() {
        return hikvisionLoginForm() || legacyLoginForm() || modernLoginForm();
    }

    function loginRequestSent() {
        if ((cfg.rpc || []).some(function (note) {
            return /login|RPC2_Login|SessionLogin|userCheck/i.test(note);
        })) {
            return true;
        }
        return performance.getEntriesByType("resource").some(function (entry) {
            return /RPC2(_Login)?|SessionLogin|ISAPI\/Security|userCheck/i.test(entry.name);
        });
    }

    function fire(el, type) {
        // The camera's own handlers throw on synthetic events; that must not
        // abort the rest of the login sequence.
        try {
            el.dispatchEvent(new Event(type, { bubbles: true }));
        } catch (err) {
            cfg.eventError = String(err);
        }
    }

    // React tracks input values itself, so assigning .value directly is ignored
    // unless the native setter is used.
    function setValue(form, el, value) {
        el.focus();
        if (form.hikvision) {
            el.value = value;
            try {
                if (window.angular) {
                    var ngEl = window.angular.element(el);
                    var scope = ngEl.scope && ngEl.scope();
                    if (scope) {
                        scope.$apply(function () {
                            if (el.id === "username") {
                                scope.username = value;
                            }
                            if (el.id === "password") {
                                scope.password = value;
                            }
                        });
                    }
                }
            } catch (err) {
                cfg.angularError = String(err);
            }
        } else if (form.react) {
            var desc = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value");
            if (desc && desc.set) {
                desc.set.call(el, value);
            } else {
                el.value = value;
            }
        } else {
            el.value = value;
            try {
                var jq = window.jQuery || window.$;
                if (jq) {
                    var widget = jq(el);
                    if (widget.data("dui-textfield") && widget.textfield) {
                        widget.textfield("value", value);
                    }
                    if (widget.data("dui-password") && widget.password) {
                        widget.password("value", value);
                    }
                }
            } catch (err) {
                cfg.widgetError = String(err);
            }
        }
        fire(el, "input");
        fire(el, "change");
    }

    function legacyWidgetsReady(form) {
        if (form.react) {
            return true;
        }
        var jq = window.jQuery || window.$;
        if (!jq) {
            return login.tries > 40;
        }
        try {
            var widget = jq(form.pass);
            return !!(widget.data("dui-password") || widget.data("dui-textfield"));
        } catch (err) {
            return login.tries > 40;
        }
    }

    function stop(reason) {
        login.done = reason;
        if (login.timer) {
            clearInterval(login.timer);
            login.timer = 0;
        }
    }

    // Stream index conventions differ by UI generation:
    //  - Legacy seajs playPreview(channel, stream): 0=main, 1=sub1
    //  - React plugin.open / player.play(stream, channel): 1=main, 2=sub1
    //    (RTSP subtype = stream - 1). Preferring "1" on React is still Main —
    //    that was why dual Panoramic/Detail tiles stayed crisp.
    function usesReactStreamIndex() {
        // React Live: plugin.open / player.play are 1-based (1=main, 2=sub1).
        // Legacy seajs playPreview is 0-based (0=main, 1=sub1). Detect React via
        // H5 refs — do not treat bare plugin.open as React (legacy also has it).
        if (legacyH5Modules().length) {
            return false;
        }
        if (window.plugin && window.plugin.comp && window.plugin.comp.H5ref) {
            return true;
        }
        var reacted = false;
        eachH5Player(function () {
            reacted = true;
        });
        return reacted;
    }

    function preferredLiveStream() {
        return usesReactStreamIndex() ? 2 : 1;
    }

    function shouldForcePreferredStream() {
        // Remap firmware's default Main→Sub1 during boot only. Stop immediately
        // once the user picks a stream so Main/Sub clicks stick.
        if (cfg.userPickedStream) {
            return false;
        }
        if (!cfg.subStreamGuardUntil) {
            cfg.subStreamGuardUntil = Date.now() + 12000;
        }
        return Date.now() < cfg.subStreamGuardUntil;
    }

    function markStreamSettled() {
        // Used by the legacy replay loop so we don't keep re-calling playPreview.
        // open/play patches still remap until the guard window or user intent.
        cfg.subStreamSettled = true;
        cfg.forcedStream = preferredLiveStream();
    }

    function markUserPickedStream(event) {
        if (cfg._syntheticStreamClick) {
            return;
        }
        var node = event.target;
        var depth = 0;
        while (node && node !== document && depth < 12) {
            if (node.getAttribute && /^onConnect/i.test(node.getAttribute("btn-for") || "")) {
                cfg.userPickedStream = true;
                cfg.subStreamSettled = true;
                return;
            }
            // React Live dropdown: .streamList .item → playVideo(evt, 1|2|…)
            if (node.classList && node.classList.contains("item")) {
                var list = node.parentNode;
                if (list && list.classList && list.classList.contains("streamList")) {
                    cfg.userPickedStream = true;
                    cfg.subStreamSettled = true;
                    return;
                }
            }
            var label = (node.textContent || "").replace(/\s+/g, " ").trim();
            if (
                /^(main\s*stream|sub\s*streams?\s*[1234])$/i.test(label)
                && (!node.children || node.children.length <= 1)
            ) {
                cfg.userPickedStream = true;
                cfg.subStreamSettled = true;
                return;
            }
            node = node.parentNode;
            depth += 1;
        }
    }

    document.addEventListener("click", markUserPickedStream, true);

    function clickExactLabel(textRe) {
        var nodes = document.querySelectorAll("a, span, div, label, li, p");
        var clicked = 0;
        cfg._syntheticStreamClick = true;
        try {
            for (var i = 0; i < nodes.length; i += 1) {
                var el = nodes[i];
                if (el.children && el.children.length > 1) {
                    continue;
                }
                var text = (el.textContent || "").replace(/\s+/g, " ").trim();
                if (!textRe.test(text)) {
                    continue;
                }
                if (el.offsetParent === null && el.getClientRects().length === 0) {
                    continue;
                }
                // React stream picker items must go through playVideo; bare
                // clicks on hidden labels only fight the dropdown.
                if (el.closest && el.closest(".streamList")) {
                    continue;
                }
                try {
                    el.click();
                    clicked += 1;
                } catch (err) {
                    // ignore
                }
            }
        } finally {
            cfg._syntheticStreamClick = false;
        }
        return clicked;
    }

    function ensureSubStreamSelected() {
        if (cfg.userPickedStream) {
            return liveStreamIndexFromUi();
        }
        var preferred = preferredLiveStream();
        // React Live: do not synthetic-click Sub Stream labels. Firmware opens
        // via plugin.open(stream,…); our open/play patches remap Main→Sub1.
        if (usesReactStreamIndex()) {
            if (!cfg.subStreamGuardUntil) {
                cfg.subStreamGuardUntil = Date.now() + 12000;
            }
            return preferred;
        }
        var main = document.querySelector('a[btn-for="onConnectMain"]');
        var extra1 = document.querySelector('a[btn-for="onConnectExtra"][index="1"]');
        if (extra1) {
            var buttons = document.querySelectorAll("a[btn-for^=onConnect]");
            for (var i = 0; i < buttons.length; i += 1) {
                buttons[i].classList.remove("current", "last");
            }
            extra1.classList.add("current", "last");
            if (main) {
                main.classList.remove("current", "last");
            }
        } else if (!cfg.subLabelClicked) {
            // Legacy dual-channel text tree only — click once, then stop.
            cfg.subLabelClicked = clickExactLabel(/^sub\s*streams?\s*1$/i) > 0;
        }
        if (!cfg.subStreamGuardUntil) {
            cfg.subStreamGuardUntil = Date.now() + 12000;
        }
        return preferred;
    }

    function liveStreamIndexFromUi() {
        var current = document.querySelector("a[btn-for^=onConnect].current");
        if (current && current.getAttribute("index") != null) {
            var idx = Number(current.getAttribute("index"));
            if (!isNaN(idx)) {
                return idx;
            }
        }
        if (usesReactStreamIndex()) {
            if (window.plugin && typeof plugin.stream === "number" && plugin.stream > 0) {
                return plugin.stream;
            }
            var fromPlayer = null;
            eachH5Player(function (player) {
                if (fromPlayer != null) {
                    return;
                }
                if (typeof player.subtype === "number" && player.subtype >= 0) {
                    fromPlayer = player.subtype + 1;
                }
            });
            if (fromPlayer != null) {
                return fromPlayer;
            }
            return preferredLiveStream();
        }
        if (window.plugin && typeof plugin.stream === "number" && plugin.stream >= 0) {
            // OCX/plugin.stream is 1=main; legacy playPreview wants 0=main.
            return plugin.stream > 0 ? plugin.stream - 1 : 0;
        }
        return preferredLiveStream();
    }

    function liveStreamIndex() {
        if (cfg.userPickedStream) {
            return liveStreamIndexFromUi();
        }
        return ensureSubStreamSelected();
    }

    function patchPluginOpen(plugin) {
        if (!plugin || typeof plugin.open !== "function" || plugin._workToolOpen) {
            return;
        }
        var originalOpen = plugin.open.bind(plugin);
        plugin.open = function (stream, channel, view, deviceId) {
            var args = Array.prototype.slice.call(arguments);
            if (shouldForcePreferredStream()) {
                args[0] = preferredLiveStream();
            }
            return originalOpen.apply(this, args);
        };
        plugin._workToolOpen = true;
    }

    // Tunnel/private-signal mode aims video at the dashboard host. That path
    // never starts a stream behind the proxy, so point the player at the camera.
    function cameraHostPort() {
        var host = String(cfg.origin || "").replace(/^https?:\/\//i, "");
        var parts = host.split(":");
        return { ip: parts[0], port: Number(parts[1] || 80) };
    }

    function applyCameraEndpoint(plugin, dest) {
        plugin.isInner = true;
        plugin.ip = dest.ip;
        plugin.port = dest.port;
        plugin.svrPort = dest.port;
        if (!plugin.info) {
            return;
        }
        plugin.info.isPrivateSignal = false;
        plugin.info.Tunnel = false;
        if (!plugin.info.deviceConfig) {
            return;
        }
        plugin.info.deviceConfig.Tunnel = { Enable: false };
        if (plugin.info.deviceConfig.rtspOverTls) {
            plugin.info.deviceConfig.rtspOverTls.enable = false;
            plugin.info.deviceConfig.rtspOverTls.port = dest.port;
        }
        if (plugin.info.deviceConfig.https) {
            plugin.info.deviceConfig.https.port = dest.port;
        }
    }

    function eachH5Player(callback) {
        var root = window.plugin && window.plugin.comp && window.plugin.comp.H5ref
            && window.plugin.comp.H5ref.current;
        var refs = root && root.H5PlayerRef;
        if (!refs) {
            return 0;
        }
        var count = 0;
        Object.keys(refs).forEach(function (key) {
            var node = refs[key];
            var player = node && node.current ? node.current : node;
            if (player && typeof player.play === "function") {
                callback(player, count);
                count += 1;
            }
        });
        return count;
    }

    function patchH5Player(player, dest) {
        player.RTSPOverTlsPort = 0;
        player.port = dest.port;
        if (typeof player.setOptions === "function") {
            player.setOptions({
                ip: dest.ip,
                port: dest.port,
                svrPort: dest.port,
                isInner: true
            });
        }
        if (typeof player.setInfo === "function") {
            player.setInfo({
                isPrivateSignal: false,
                Tunnel: false,
                deviceConfig: {
                    Tunnel: { Enable: false },
                    rtspOverTls: { enable: false, port: dest.port },
                    https: { enable: false, port: dest.port }
                }
            });
        }
        if (player.info) {
            player.info.isPrivateSignal = false;
            player.info.Tunnel = false;
        }
        if (player.options) {
            player.options.ip = dest.ip;
            player.options.port = dest.port;
            player.options.svrPort = dest.port;
            player.options.isInner = true;
        }
        if (typeof player.play === "function" && !player._workToolPlay) {
            var originalPlay = player.play.bind(player);
            player.play = function (stream) {
                var args = Array.prototype.slice.call(arguments);
                if (shouldForcePreferredStream()) {
                    args[0] = preferredLiveStream();
                }
                return originalPlay.apply(this, args);
            };
            player._workToolPlay = true;
        }
    }

    function legacyH5Modules() {
        var found = [];
        var cache = window.seajs && window.seajs.cache;
        if (!cache) {
            return found;
        }
        Object.keys(cache).forEach(function (key) {
            if (!/h5player/i.test(key)) {
                return;
            }
            var mod = cache[key] && cache[key].exports;
            if (mod && typeof mod === "object") {
                found.push(mod);
            }
        });
        return found;
    }

    function isLegacyPreviewActive() {
        // Prefer the active top tab. Before the tab widget marks anything current,
        // allow play so first-load is not blocked.
        var current = document.querySelector("ul.u-tab.main > li.current[data-for]")
            || document.querySelector(".u-tab.main > li.current[data-for]")
            || document.querySelector("li.current[data-for]");
        if (current) {
            var name = current.getAttribute("data-for") || "";
            // Live (and PTZ) keep video; Setting / Alarm / etc. must not be covered.
            return name === "preview" || name === "ptz";
        }
        return !!(
            document.getElementById("preview_video")
            || document.querySelector(".main-video")
        );
    }

    function h5Container() {
        return document.getElementById("h5playerContainer");
    }

    function forceHideH5Overlay() {
        var el = h5Container();
        if (!el) {
            return;
        }
        el.style.setProperty("display", "none", "important");
        el.style.setProperty("visibility", "hidden", "important");
        el.style.setProperty("pointer-events", "none", "important");
        el.style.top = "-10000px";
    }

    function clearForcedH5Overlay() {
        var el = h5Container();
        if (!el) {
            return;
        }
        el.style.removeProperty("display");
        el.style.removeProperty("visibility");
        el.style.removeProperty("pointer-events");
    }

    function isLegacyH5Playing() {
        try {
            var playing = window.webApp && window.webApp.H5Playing;
            if (playing && typeof playing === "object" && Object.keys(playing).length) {
                return true;
            }
        } catch (err) {
            // ignore
        }
        var el = h5Container();
        if (!el || el.style.display === "none") {
            return false;
        }
        var media = el.querySelector("canvas, video");
        if (!media) {
            return false;
        }
        var rect = el.getBoundingClientRect();
        return rect.width > 40 && rect.height > 40 && rect.top > -1000;
    }

    function patchLegacyH5(dest) {
        var modules = legacyH5Modules();
        modules.forEach(function (mod) {
            // Firmware re-reads location.port (the dashboard :5098) into y.port before
            // building rtsp://ip:port/cam/realmonitor — that breaks 3k cams on :11080+.
            // Pin ip/port to the real camera endpoint.
            try {
                Object.defineProperty(mod, "ip", {
                    configurable: true,
                    enumerable: true,
                    get: function () {
                        return dest.ip;
                    },
                    set: function () {}
                });
                Object.defineProperty(mod, "port", {
                    configurable: true,
                    enumerable: true,
                    get: function () {
                        return dest.port;
                    },
                    set: function () {}
                });
            } catch (err) {
                mod.ip = dest.ip;
                mod.port = dest.port;
            }
            mod.wsprotocol = "ws";
            if (typeof mod.reGetIpPort === "function" && !mod._workToolReGet) {
                mod.reGetIpPort = function () {
                    // no-op: defineProperty getters keep camera endpoint
                };
                mod._workToolReGet = true;
            }
            if (typeof mod.playPreview === "function" && !mod._workToolPlayPreview) {
                var originalPlay = mod.playPreview.bind(mod);
                mod.playPreview = function (channel, stream) {
                    // Late WASM callbacks can re-show the overlay after Setting is open.
                    if (!isLegacyPreviewActive()) {
                        forceHideH5Overlay();
                        return;
                    }
                    clearForcedH5Overlay();
                    var args = Array.prototype.slice.call(arguments);
                    if (shouldForcePreferredStream()) {
                        args[1] = preferredLiveStream();
                        ensureSubStreamSelected();
                        return originalPlay.apply(mod, args);
                    }
                    return originalPlay.apply(mod, args);
                };
                mod._workToolPlayPreview = true;
            }
            if (typeof mod.cover === "function" && !mod._workToolCover) {
                var originalCover = mod.cover.bind(mod);
                mod.cover = function () {
                    if (!isLegacyPreviewActive()) {
                        forceHideH5Overlay();
                        return false;
                    }
                    clearForcedH5Overlay();
                    return originalCover.apply(mod, arguments);
                };
                mod._workToolCover = true;
            }
            if (typeof mod.hide === "function" && !mod._workToolHide) {
                var originalHide = mod.hide.bind(mod);
                mod.hide = function () {
                    var result = originalHide.apply(mod, arguments);
                    forceHideH5Overlay();
                    cfg.legacyNeedsReplay = true;
                    return result;
                };
                mod._workToolHide = true;
            }
            if (typeof mod.recoverOptionsProps === "function") {
                try {
                    mod.recoverOptionsProps({ splayerIp: dest.ip, splayerPort: dest.port });
                } catch (err) {
                    cfg.legacyH5Error = String(err);
                }
            }
        });
        if (modules.length) {
            cfg.patchedLegacyReGet = true;
        }
        return modules.length;
    }

    function legacyLivePane() {
        // Native cover target is .main-video; on these builds that is #preview_video.
        var preview = document.getElementById("preview_video")
            || document.querySelector(".main-video");
        if (!preview) {
            return null;
        }
        // The live pane is only position:relative with no height; behind the proxy
        // it often stays at 0px, so the H5 player never gets a real cover target.
        if (preview.offsetHeight < 50) {
            var top = Math.max(0, Math.floor(preview.getBoundingClientRect().top) || 60);
            var height = Math.max(240, window.innerHeight - top - 8);
            var container = preview.parentElement;
            if (container && /main-video-container/i.test(container.className || "")) {
                container.style.height = height + "px";
                container.style.minHeight = height + "px";
            }
            preview.style.height = height + "px";
            preview.style.minHeight = height + "px";
            preview.style.width = "100%";
        }
        return preview.offsetHeight >= 50 ? preview : null;
    }

    function syncLegacyH5Stream(plugin, dest) {
        if (!window.webApp || window.webApp.playMode !== "h5") {
            return false;
        }
        var mods = legacyH5Modules();
        if (!mods.length) {
            return false;
        }
        var mod = mods[0];
        patchLegacyH5(dest);

        if (!isLegacyPreviewActive()) {
            // leave() hides behind an init Deferred; if that stalls (or a late
            // playPreview callback fires), Setting stays covered. Force-hide.
            try {
                if (typeof mod.hide === "function" && !cfg.legacyForcedHidden) {
                    mod.hide();
                }
            } catch (err) {
                cfg.streamError = String(err);
            }
            forceHideH5Overlay();
            cfg.legacyForcedHidden = true;
            cfg.legacyNeedsReplay = true;
            cfg.playedViews = false;
            return false;
        }

        if (cfg.legacyForcedHidden) {
            clearForcedH5Overlay();
            cfg.legacyForcedHidden = false;
        }

        var pane = legacyLivePane();
        if (!pane || typeof mod.playPreview !== "function") {
            return false;
        }

        var playing = isLegacyH5Playing();
        var now = Date.now();
        var due = !cfg.legacyPlayAt || (now - cfg.legacyPlayAt) > 2500;
        // Re-force substream only until settled or the user picks a stream.
        // Continuous forceSub was overriding Main/Sub clicks in the Live UI.
        var forceSub = !cfg.userPickedStream
            && !cfg.subStreamSettled
            && shouldForcePreferredStream();
        if (cfg.legacyNeedsReplay || ((!playing || forceSub) && due)) {
            try {
                clearForcedH5Overlay();
                var streamIdx = liveStreamIndex();
                var channels = 1;
                try {
                    channels = Math.max(1, Number(window.webApp.CHANNEL_NUMBER) || 1);
                } catch (err) {
                    channels = 1;
                }
                // Some dual Panoramic/Detail firmwares leave CHANNEL_NUMBER at 1
                // even with two live panes — prefer the larger of DOM panes / CHANNEL.
                try {
                    var panes = document.querySelectorAll(
                        ".h5-player, .h5player, canvas.vjs-tech, .ws-player, [class*='h5Player']"
                    ).length;
                    if (panes > channels) {
                        channels = Math.min(panes, 4);
                    }
                } catch (err) {
                    // ignore
                }
                if (channels > 1 && typeof mod.setVisibleViews === "function") {
                    try {
                        mod.setVisibleViews(channels);
                    } catch (err) {
                        // ignore
                    }
                }
                // Dual-channel 3300+ units (panoramic + detail) need every channel
                // on substream 1, matching native _playH5's per-channel loop.
                for (var ch = 0; ch < channels; ch += 1) {
                    mod.playPreview(
                        ch,
                        streamIdx,
                        pane,
                        null,
                        ch,
                        0
                    );
                }
                cfg.legacyPlayAt = now;
                cfg.legacyNeedsReplay = false;
                cfg.legacyPlayAttempts = (cfg.legacyPlayAttempts || 0) + 1;
                cfg.directStream = true;
                cfg.legacyChannels = channels;
                if (forceSub) {
                    markStreamSettled();
                }
            } catch (err) {
                cfg.streamError = String(err);
                return false;
            }
        } else if (playing && typeof mod.cover === "function") {
            try {
                mod.cover(pane);
            } catch (err) {
                // ignore cover jitter
            }
        }

        if (playing) {
            cfg.playedViews = true;
            cfg.directStream = true;
            return true;
        }
        // Keep retrying until frames appear; do not treat the first call as done.
        return false;
    }

    function preferDirectStream() {
        var plugin = window.plugin;
        if (!plugin || !cfg.origin || loginForm()) {
            return false;
        }
        var dest = cameraHostPort();
        applyCameraEndpoint(plugin, dest);
        patchPluginOpen(plugin);
        patchLegacyH5(dest);
        if (!cfg.patchedGetPort && typeof plugin.getPort === "function") {
            var origGetPort = plugin.getPort.bind(plugin);
            plugin.getPort = function () {
                return Promise.resolve(origGetPort(false)).then(function (result) {
                    applyCameraEndpoint(plugin, dest);
                    return result;
                });
            };
            cfg.patchedGetPort = true;
        }
        if (!cfg.patchedSetInfo && typeof plugin.setInfo === "function") {
            var originalSetInfo = plugin.setInfo.bind(plugin);
            plugin.setInfo = function (info) {
                originalSetInfo(info);
                applyCameraEndpoint(plugin, dest);
            };
            cfg.patchedSetInfo = true;
        }
        if (!cfg.playedViews) {
            var started = eachH5Player(function (player, idx) {
                patchH5Player(player, dest);
                try {
                    var view = typeof player.viewIndex === "number" ? player.viewIndex : idx;
                    player.play(liveStreamIndex(), view);
                } catch (err) {
                    cfg.streamError = String(err);
                }
            });
            // Legacy UI (RD3407/RD3547 fisheye): seajs h5player, not React refs.
            if (!started) {
                started = syncLegacyH5Stream(plugin, dest) ? 1 : 0;
            }
            if (started) {
                cfg.playedViews = true;
                cfg.directStream = true;
                if (!cfg.userPickedStream) {
                    markStreamSettled();
                }
            }
        } else {
            eachH5Player(function (player) {
                patchH5Player(player, dest);
            });
            patchLegacyH5(dest);
            // Keep overlay in sync with Live vs Setting even after first play.
            if (window.webApp && window.webApp.playMode === "h5") {
                syncLegacyH5Stream(plugin, dest);
            } else {
                legacyLivePane();
            }
        }
        return cfg.directStream;
    }

    var streamIntervalMs = 200;
    var streamTimer = setInterval(function streamTick() {
        if (isHikvision()) {
            installHikvisionConfigAssist();
            return;
        }
        preferDirectStream();
        if (login.tries > 480) {
            clearInterval(streamTimer);
            return;
        }
        // Once live is up and substream settled, stop hammering playPreview.
        var settled = !!(cfg.subStreamSettled || cfg.userPickedStream);
        var wantMs = (cfg.playedViews && settled && !loginForm()) ? 1500 : 200;
        if (wantMs !== streamIntervalMs) {
            streamIntervalMs = wantMs;
            clearInterval(streamTimer);
            streamTimer = setInterval(streamTick, streamIntervalMs);
        }
    }, streamIntervalMs);

    function attempt() {
        login.tries += 1;
        if (login.tries > 480) {
            stop("timeout");
            return;
        }
        var form = loginForm();
        if (!form) {
            if (login.clicks > 0) {
                stop("logged-in");
            }
            return;
        }
        if (login.clicks > 0) {
            // Hikvision: first click often fired before ng-model was bound (empty
            // username/password). Retry while still on the login page.
            if (form.hikvision && /login\.asp/i.test(location.pathname || "")) {
                var scope = hikvisionLoginScope();
                if (!scope || !scope.username || scope.username !== cfg.user) {
                    login.clicks = 0;
                    login.done = "";
                    if (login.timer === 0 && cfg.user) {
                        login.timer = setInterval(attempt, 250);
                    }
                    return;
                }
                if (loginRequestSent() || /preview\.asp|config\.asp/i.test(location.pathname || "")) {
                    stop("submitted");
                }
                return;
            }
            if (loginRequestSent() || form.hikvision) {
                stop("submitted");
            }
            return;
        }
        // Wait until the camera app has bound its login handler. Clicking earlier
        // can submit empty fields and burn lockout attempts.
        if (
            !form.hikvision
            && typeof window.webApp === "undefined"
            && typeof window.plugin === "undefined"
        ) {
            return;
        }
        if (!form.hikvision && !legacyWidgetsReady(form)) {
            return;
        }
        if (form.hikvision) {
            if (!hikvisionLoginScope()) {
                return;
            }
            if (!submitHikvisionLogin()) {
                return;
            }
            login.clicks += 1;
            login.clickedAt = Date.now();
            return;
        }
        setValue(form, form.user, cfg.user);
        setValue(form, form.pass, cfg.pass);
        form.user.blur();
        form.pass.blur();
        login.clicks += 1;
        login.clickedAt = Date.now();
        try {
            form.button.click();
        } catch (err) {
            cfg.clickError = String(err);
        }
    }

    function visibleWithText(text) {
        var nodes = document.querySelectorAll("a, button, li, span, div");
        for (var i = 0; i < nodes.length; i += 1) {
            var node = nodes[i];
            if (
                node.offsetParent !== null
                && node.children.length === 0
                && (node.textContent || "").trim() === text
            ) {
                return node;
            }
        }
        return null;
    }

    // Ends the camera-side session so the grid can drop a camera without leaving it
    // logged in. Both UI generations are handled: the old one has a Logout menu entry,
    // the new one hides it behind the account menu.
    cfg.logout = function () {
        stop("logged-out");
        var direct = pickVisible('[btn-for="onLogout"]') || visibleWithText("Logout");
        if (direct) {
            direct.click();
            return true;
        }
        var account = visibleWithText(cfg.user);
        if (account) {
            account.click();
            setTimeout(function () {
                var item = visibleWithText("Logout");
                if (item) {
                    item.click();
                }
            }, 400);
            return true;
        }
        return false;
    };

    if (cfg.user) {
        login.timer = setInterval(attempt, 250);
    }
}());
