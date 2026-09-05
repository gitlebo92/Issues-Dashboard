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
    setInterval(installWebSocketProxy, 1000);

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
        return legacyLoginForm() || modernLoginForm();
    }

    function loginRequestSent() {
        if ((cfg.rpc || []).some(function (note) {
            return /login|RPC2_Login/i.test(note);
        })) {
            return true;
        }
        return performance.getEntriesByType("resource").some(function (entry) {
            return /RPC2(_Login)?/i.test(entry.name);
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
        if (form.react) {
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

    function patchLegacyH5(dest) {
        var modules = legacyH5Modules();
        modules.forEach(function (mod) {
            mod.ip = dest.ip;
            mod.port = dest.port;
            mod.wsprotocol = "ws";
            if (typeof mod.reGetIpPort === "function" && !cfg.patchedLegacyReGet) {
                mod.reGetIpPort = function () {
                    mod.ip = dest.ip;
                    mod.port = dest.port;
                };
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

    function preferDirectStream() {
        var plugin = window.plugin;
        if (!plugin || !cfg.origin || loginForm()) {
            return false;
        }
        var dest = cameraHostPort();
        applyCameraEndpoint(plugin, dest);
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
                    player.play(plugin.stream || 1, view);
                } catch (err) {
                    cfg.streamError = String(err);
                }
            });
            // Legacy UI (RD3547 fisheye): seajs h5player, not React refs.
            if (!started && window.webApp && window.webApp.playMode === "h5") {
                var mods = legacyH5Modules();
                if (mods.length) {
                    try {
                        var livePane = document.getElementById("h5_canvas_0")
                            || document.querySelector("#viewArea, #videoContent, .video-content, #content");
                        if (typeof mods[0].playPreview === "function") {
                            mods[0].playPreview(
                                plugin.channel || 0,
                                plugin.stream || 1,
                                livePane || document.body,
                                null,
                                0,
                                0
                            );
                            started = 1;
                        } else if (typeof plugin.open === "function") {
                            plugin.open(plugin.stream || 1, plugin.channel || 0, 1);
                            started = 1;
                        }
                    } catch (err) {
                        cfg.streamError = String(err);
                    }
                }
            }
            if (started) {
                cfg.playedViews = true;
                cfg.directStream = true;
            }
        } else {
            eachH5Player(function (player) {
                patchH5Player(player, dest);
            });
            patchLegacyH5(dest);
        }
        return cfg.directStream;
    }

    var streamTimer = setInterval(function () {
        preferDirectStream();
        if (login.tries > 480) {
            clearInterval(streamTimer);
        }
    }, 200);

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
            if (loginRequestSent()) {
                stop("submitted");
            }
            return;
        }
        // Wait until the camera app has bound its login handler. Clicking earlier
        // can submit empty fields and burn lockout attempts.
        if (typeof window.webApp === "undefined" && typeof window.plugin === "undefined") {
            return;
        }
        if (!legacyWidgetsReady(form)) {
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
