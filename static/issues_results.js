        const ERP_WRITES_DISABLED_TITLE =
            "ERP writes disabled (set DISABLE_ERP_WRITES=0 in .env to enable)";
        function disableErpWriteControl(el) {
            if (!erpWritesDisabled || !el) {
                return el;
            }
            el.disabled = true;
            el.classList.add("is-disabled");
            el.setAttribute("aria-disabled", "true");
            el.title = ERP_WRITES_DISABLED_TITLE;
            return el;
        }
        const consoleEl = document.getElementById("console");
        const consoleSearchEl = document.getElementById("console_search");
        const consoleClearBtn = document.getElementById("console_clear");
        const consoleMatchCountEl = document.getElementById("console_match_count");
        const listSearchEl = document.getElementById("list_search");
        const listMatchCountEl = document.getElementById("list_match_count");
        const listViewToggle = document.getElementById("list_view_toggle");
        const showAllListsBtn = document.getElementById("show_all_lists");
        const showOneListBtn = document.getElementById("show_one_list");
        const listCategoryWrap = document.getElementById("list_category_wrap");
        const listCategoryToggle = document.getElementById("list_category_toggle");
        const listCategoryToggleText = document.getElementById("list_category_toggle_text");
        const listCategoryOptions = document.getElementById("list_category_options");
        const panelModeEl = document.getElementById("panel_mode");
        const clearCheckboxesBtn = document.getElementById("clear_checkboxes");
        const pullErpBtn = document.getElementById("pull_erp");
        const updateWeatherBtn = document.getElementById("update_weather");
        const clearCheckboxesModal = document.getElementById("clear_checkboxes_modal");
        const clearCheckboxesCancel = document.getElementById("clear_checkboxes_cancel");
        const clearCheckboxesConfirm = document.getElementById("clear_checkboxes_confirm");
        const patchUpdateModal = document.getElementById("patch_update_modal");
        const patchUpdateMessage = document.getElementById("patch_update_message");
        const patchUpdateCancel = document.getElementById("patch_update_cancel");
        const patchUpdateConfirm = document.getElementById("patch_update_confirm");
        let patchUpdateUnit = "";
        let patchUpdateButton = null;
        const genericConfirmModal = document.getElementById("generic_confirm_modal");
        const genericConfirmTitle = document.getElementById("generic_confirm_title");
        const genericConfirmMessage = document.getElementById("generic_confirm_message");
        const genericConfirmCancel = document.getElementById("generic_confirm_cancel");
        const genericConfirmAction = document.getElementById("generic_confirm_action");
        let genericConfirmHandler = null;

        function closeGenericConfirmModal() {
            genericConfirmModal.classList.remove("is-open");
            genericConfirmHandler = null;
        }

        function openGenericConfirmModal(title, message, actionLabel, onConfirm) {
            genericConfirmTitle.textContent = title;
            genericConfirmMessage.textContent = message;
            genericConfirmAction.textContent = actionLabel;
            genericConfirmAction.disabled = false;
            genericConfirmHandler = onConfirm;
            genericConfirmModal.classList.add("is-open");
            genericConfirmCancel.focus();
        }

        genericConfirmCancel.addEventListener("click", closeGenericConfirmModal);
        genericConfirmAction.addEventListener("click", function () {
            const handler = genericConfirmHandler;
            closeGenericConfirmModal();
            if (handler) {
                handler();
            }
        });
        genericConfirmModal.addEventListener("click", function (event) {
            if (event.target === genericConfirmModal) {
                closeGenericConfirmModal();
            }
        });

        const securityFixModal = document.getElementById("security_fix_modal");
        const securityFixMessage = document.getElementById("security_fix_message");
        const securityFixJump = document.getElementById("security_fix_jump");
        const securityFixJumpSelect = document.getElementById("security_fix_jump_select");
        const securityFixJumpVersionRow = document.getElementById("security_fix_jump_version_row");
        const securityFixJumpVersionInput = document.getElementById("security_fix_jump_version");
        const securityFixLog = document.getElementById("security_fix_log");
        const securityFixDriverCheck = document.getElementById("security_fix_driver_check");
        const securityFixCancel = document.getElementById("security_fix_cancel");
        const securityFixAction = document.getElementById("security_fix_action");
        const securityFixForceClear = document.getElementById("security_fix_force_clear");
        let securityFixUnit = "";
        let securityFixButton = null;
        let securityFixVersion = null;
        let securityFixPhase = "start";
        let securityFixToken = null;
        let securityFixLockedByOther = false;
        // Maps the server-persisted job phase back to the client wizard phase
        // that should run next, so a page refresh can resume mid-wizard.
        const SECURITY_FIX_RESUME_PHASE = {
            start: "start",
            step1_done: "awaiting_webui",
            step2_done: "awaiting_reboot",
            step2_failed: "awaiting_webui",
            shutdown_done: "awaiting_shutdown",
            shutdown_failed: "awaiting_reboot",
            finish_done: "verify",
            finish_failed: "awaiting_shutdown",
            verify_done: "restart",
            verify_warning: "restart",
            verify_failed: "verify",
        };
        const createDeploymentModal = document.getElementById("create_deployment_modal");
        const createDeploymentMessage = document.getElementById("create_deployment_message");
        const createDeploymentCancel = document.getElementById("create_deployment_cancel");
        const createDeploymentConfirm = document.getElementById("create_deployment_confirm");
        const createDeploymentSuccessModal = document.getElementById("create_deployment_success_modal");
        const createDeploymentSuccessLink = document.getElementById("create_deployment_success_link");
        const createDeploymentSuccessOk = document.getElementById("create_deployment_success_ok");
        let createDeploymentProjectId = "";
        let createDeploymentSubject = "";
        let createDeploymentButton = null;
        const createTerminationModal = document.getElementById("create_termination_modal");
        const createTerminationMessage = document.getElementById("create_termination_message");
        const createTerminationCancel = document.getElementById("create_termination_cancel");
        const createTerminationConfirm = document.getElementById("create_termination_confirm");
        let createTerminationIssueId = "";
        let createTerminationSubject = "";
        let createTerminationButton = null;
        const createRelocationModal = document.getElementById("create_relocation_modal");
        const createRelocationMessage = document.getElementById("create_relocation_message");
        const createRelocationCancel = document.getElementById("create_relocation_cancel");
        const createRelocationConfirm = document.getElementById("create_relocation_confirm");
        let createRelocationIssueId = "";
        let createRelocationSubject = "";
        let createRelocationButton = null;
        const siteActionModal = document.getElementById("site_action_modal");
        const siteActionTitle = document.getElementById("site_action_title");
        const siteActionMessage = document.getElementById("site_action_message");
        const siteActionCancel = document.getElementById("site_action_cancel");
        const siteActionConfirm = document.getElementById("site_action_confirm");
        let siteActionKind = "";
        let siteActionSubject = "";
        let siteActionSiteId = "";
        let siteActionButton = null;
        const clearMuCoordinatesModal = document.getElementById("clear_mu_coordinates_modal");
        const clearMuCoordinatesMessage = document.getElementById("clear_mu_coordinates_message");
        const clearMuCoordinatesCancel = document.getElementById("clear_mu_coordinates_cancel");
        const clearMuCoordinatesConfirm = document.getElementById("clear_mu_coordinates_confirm");
        let clearMuCoordinatesSubject = "";
        let clearMuCoordinatesUnit = "";
        let clearMuCoordinatesMu = "";
        let clearMuCoordinatesButton = null;
        const clearMuSiteModal = document.getElementById("clear_mu_site_modal");
        const clearMuSiteMessage = document.getElementById("clear_mu_site_message");
        const clearMuSiteCancel = document.getElementById("clear_mu_site_cancel");
        const clearMuSiteConfirm = document.getElementById("clear_mu_site_confirm");
        let clearMuSiteSubject = "";
        let clearMuSiteUnit = "";
        let clearMuSiteMu = "";
        let clearMuSiteButton = null;
        const createRefurbishModal = document.getElementById("create_refurbish_modal");
        const createRefurbishMessage = document.getElementById("create_refurbish_message");
        const createRefurbishList = document.getElementById("create_refurbish_list");
        const createRefurbishCancel = document.getElementById("create_refurbish_cancel");
        const createRefurbishConfirm = document.getElementById("create_refurbish_confirm");
        let createRefurbishSubject = "";
        let createRefurbishUnit = "";
        let createRefurbishButton = null;
        const techChecksModal = document.getElementById("tech_checks_modal");
        const techChecksMessage = document.getElementById("tech_checks_message");
        const techChecksTaskList = document.getElementById("tech_checks_task_list");
        const techChecksCancel = document.getElementById("tech_checks_cancel");
        const techChecksConfirm = document.getElementById("tech_checks_confirm");
        [
            createDeploymentConfirm,
            createTerminationConfirm,
            createRelocationConfirm,
            siteActionConfirm,
            clearMuCoordinatesConfirm,
            clearMuSiteConfirm,
            createRefurbishConfirm,
            techChecksConfirm,
        ].forEach(disableErpWriteControl);
        let techChecksProjectId = "";
        let techChecksSubject = "";
        let techChecksButton = null;
        const statusEl = document.getElementById("status");
        const progressFillEl = document.getElementById("progress_fill");
        const progressLabelEl = document.getElementById("progress_label");
        const consoleLines = [];

        // The console used to grow without bound while renderConsole()
        // re-joined the whole array on every append — a 300-second long ping
        // plus a validation run made the pane visibly lag. Keep a bounded
        // buffer and drop the oldest lines.
        const CONSOLE_MAX_LINES = 5000;
        const CONSOLE_TRIM_CHUNK = 500;

        // Mirrors console output into the Graphs modal's own Output pane
        // while that modal is open — every consoleLines.push from a button
        // goes through here, so no action needs changing. Lines streamed
        // from the server's shared job (validation, background pollers) are
        // pushed with consoleEchoMuted set (handleSharedEvents) and stay
        // out of it. graphsConsoleEcho is filled in once the modal's code
        // has loaded; until then it's a no-op.
        let consoleEchoMuted = false;
        let graphsConsoleEcho = null;
        consoleLines.push = function () {
            if (!consoleEchoMuted && graphsConsoleEcho) {
                graphsConsoleEcho(arguments);
            }
            return Array.prototype.push.apply(this, arguments);
        };

        function trimConsoleLines() {
            if (consoleLines.length > CONSOLE_MAX_LINES) {
                // Trim in chunks so this is amortised rather than per-line.
                const excess = consoleLines.length - CONSOLE_MAX_LINES + CONSOLE_TRIM_CHUNK;
                consoleLines.splice(0, excess);
                consoleLines.unshift(
                    "… earlier output trimmed (console keeps the last "
                    + CONSOLE_MAX_LINES.toLocaleString() + " lines) …"
                );
            }
        }

        // ---- Toasts ---------------------------------------------------------
        // Replaces notifyError(). Every caller already pushes its message to
        // the console and statusEl, so this is a third, non-blocking surface
        // rather than a modal that freezes the tab mid-stream.
        const TOAST_TIMEOUT_MS = 6000;
        // Andrew, 2026-09-23: errors used to stay until clicked away — a
        // single failure vanishing before you looked up was worse than one
        // you had to dismiss. Real usage skewed the other way: a bulk
        // action (Find All, etc.) can fire a whole stack of these at once,
        // and every one of them is already durable in the console/status
        // line, so losing an unread toast costs nothing. Errors now auto-
        // dismiss the same as everything else, just slower and only if
        // nobody moused over it — moving the mouse onto one counts as
        // "seen" and leaves it up, same contract as the opt-in
        // autoDismissIfNotHoveredMs option below.
        const TOAST_ERROR_AUTO_DISMISS_MS = 5000;
        let toastStackEl = null;

        function ensureToastStack() {
            if (!toastStackEl) {
                toastStackEl = document.createElement("div");
                toastStackEl.className = "toast-stack";
                toastStackEl.setAttribute("role", "status");
                toastStackEl.setAttribute("aria-live", "polite");
                document.body.appendChild(toastStackEl);
            }
            return toastStackEl;
        }

        function notify(message, kind, options) {
            const text = String(message == null ? "" : message).trim();
            if (!text) {
                return null;
            }
            const stack = ensureToastStack();
            const toast = document.createElement("div");
            toast.className = "toast" + (kind ? " is-" + kind : "");
            toast.textContent = text;

            if (options && options.actionLabel && options.onAction) {
                const action = document.createElement("button");
                action.type = "button";
                action.className = "toast-action";
                action.textContent = options.actionLabel;
                action.addEventListener("click", function () {
                    options.onAction();
                    toast.remove();
                });
                toast.appendChild(action);
            }

            const close = document.createElement("button");
            close.type = "button";
            close.className = "toast-close";
            close.setAttribute("aria-label", "Dismiss");
            close.textContent = "×";
            close.addEventListener("click", function () {
                toast.remove();
            });
            toast.appendChild(close);
            stack.appendChild(toast);

            // Dismiss automatically if nobody so much as moused over it —
            // moving the mouse onto it counts as "seen," same as clicking
            // × would, so it's left up after that instead of vanishing
            // mid-read. Used for every error toast by default (see
            // TOAST_ERROR_AUTO_DISMISS_MS above) and available per-call via
            // options.autoDismissIfNotHoveredMs for a non-error toast that
            // wants the same treatment (currently just the Power vs Cell
            // Outage glyph's finding — see openPowerVsCellRowDetail).
            function armAutoDismiss(ms) {
                let hovered = false;
                toast.addEventListener("mouseenter", function () {
                    hovered = true;
                });
                window.setTimeout(function () {
                    if (!hovered) {
                        toast.remove();
                    }
                }, ms);
            }

            if (options && options.persist) {
                // No timer at all — only the × closes it. For content
                // someone needs to screenshot (e.g. the 5-day forecast
                // glyph's click handler below): a native `title` tooltip
                // vanishes on almost any keypress, including the Shift in
                // Win+Shift+S, so it can never survive long enough to
                // actually capture.
            } else if (options && options.autoDismissIfNotHoveredMs) {
                armAutoDismiss(options.autoDismissIfNotHoveredMs);
            } else if (kind === "error") {
                armAutoDismiss(TOAST_ERROR_AUTO_DISMISS_MS);
            } else {
                window.setTimeout(function () {
                    toast.remove();
                }, TOAST_TIMEOUT_MS);
            }
            return toast;
        }

        function notifyError(message, options) {
            return notify(message, "error", options);
        }

        const ticketStateStorageKey = "workToolIssueCheckboxesV1_" + workToolPort;
        const unitToolsStorageKey = "workToolUnitToolsV1_" + workToolPort;
        let localTicketState = {};
        // Worked/Skipped, shared across every browser via /issues/ticket-state
        // (everything else in localTicketState — LED caches, the local
        // "resolved" staging checkbox — stays per-browser; those are UI cache,
        // not triage state a teammate needs to see).
        let serverTicketState = {};
        let serverEventCursor = 0;
        let serverVersion = 0;
        let validationRunId = "";
        let initialValidationComplete = false;
        let statePollInFlight = false;
        let consoleFollow = true;

        try {
            localTicketState = JSON.parse(
                window.localStorage.getItem(ticketStateStorageKey) || "{}"
            );
        } catch (ignore) {
            localTicketState = {};
        }

        function escapeHtml(text) {
            return text
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;");
        }

        function highlightMatch(text, query) {
            if (!query) {
                return escapeHtml(text);
            }
            const lower = text.toLowerCase();
            const q = query.toLowerCase();
            let result = "";
            let cursor = 0;
            let idx = lower.indexOf(q);
            while (idx !== -1) {
                result += escapeHtml(text.slice(cursor, idx));
                result += "<mark>" + escapeHtml(text.slice(idx, idx + q.length)) + "</mark>";
                cursor = idx + q.length;
                idx = lower.indexOf(q, cursor);
            }
            result += escapeHtml(text.slice(cursor));
            return result;
        }

        function collectSearchMatches(lines, query) {
            const q = query.toLowerCase();
            const include = new Array(lines.length).fill(false);
            const checkingRe = /^Checking\s+/i;
            const sectionEndRe = /^(Validating\s|Up Steady|Offline compute|Down Full|Scrypted outage|Speaker outage|Camera outage|Panel issues|Camera View|Monitoring Hours)/i;

            for (let i = 0; i < lines.length; i++) {
                if (lines[i].toLowerCase().indexOf(q) !== -1) {
                    include[i] = true;
                }
            }

            // For unit searches: keep the full check block after "Checking UNIT..."
            // so ping status lines (which omit the unit name) stay visible.
            for (let i = 0; i < lines.length; i++) {
                if (!checkingRe.test(lines[i]) || lines[i].toLowerCase().indexOf(q) === -1) {
                    continue;
                }
                for (let j = i + 1; j < lines.length; j++) {
                    if (checkingRe.test(lines[j]) || sectionEndRe.test(lines[j])) {
                        break;
                    }
                    include[j] = true;
                }
            }

            const matches = [];
            for (let i = 0; i < lines.length; i++) {
                if (include[i]) {
                    matches.push(lines[i]);
                }
            }
            return matches;
        }

        const KNOWN_WEATHER_REGIONS = {
            LAX: true,
            OAK: true,
            HOU: true,
            PHX: true,
            SLC: true,
            DEN: true,
        };
        const REGION_WEATHER_HISTORY = {
            LAX: { slug: "los-angeles", name: "Los Angeles" },
            OAK: { slug: "oakland", name: "Oakland" },
            HOU: { slug: "houston", name: "Houston" },
            PHX: { slug: "phoenix", name: "Phoenix" },
            SLC: { slug: "salt-lake-city", name: "Salt Lake City" },
            DEN: { slug: "denver", name: "Denver" },
        };
        // WEATHER_V2 (2026-09-15): keyed by UNIT now, not region — each
        // ticket's icon shows its own trailer/site GPS reading (see
        // work_tool.get_weather_for_units) instead of a shared per-metro
        // one. regionFromSubject/REGION_WEATHER_HISTORY below are kept
        // for the unrelated "Weather (History)" link, which points at a
        // named-city page (timeanddate.com has no per-GPS equivalent) —
        // that's the only place subject-region parsing still matters.
        const weatherByUnit = {};
        let weatherRefreshTimer = null;
        let weatherAutoRefreshTimer = null;
        const WEATHER_CACHE_MS = 30 * 60 * 1000;
        const WEATHER_AUTO_REFRESH_MS = 30 * 60 * 1000;

        function regionFromSubject(subject) {
            const text = String(subject || "").trim().toUpperCase();
            if (!text) {
                return "";
            }
            const match = text.match(/^(LAX|OAK|HOU|PHX|SLC|DEN)\b/);
            return match ? match[1] : "";
        }

        function applyWeatherToIcon(el, data) {
            if (!el || !data) {
                return;
            }
            const icon = data.icon || "cloud";
            el.className = "wx-icon wx-" + icon;
            const weatherTitle = data.message
                || (
                    (data.unit || el.dataset.unit || "")
                    + ": "
                    + (data.temperature_label || "?")
                    + ", "
                    + (data.conditions || "?")
                );
            el.title = weatherTitle + " — click for site weather";
            el.classList.remove("wx-pending");
            el.classList.remove("wx-loading");
            if (el.id === "graphs_wx_icon") {
                renderGraphsWeatherText(data);
            }
        }

        function runGetWeatherForEntry(entry, triggerEl) {
            if (!entry || !entry.unit) {
                return;
            }
            const isIcon = !!(triggerEl && triggerEl.classList && triggerEl.classList.contains("wx-icon"));
            const isButton = !!(triggerEl && triggerEl.tagName === "BUTTON");
            if (isIcon) {
                triggerEl.classList.add("wx-loading");
            }
            if (isButton) {
                triggerEl.disabled = true;
                triggerEl.textContent = "Loading...";
            }
            statusEl.textContent = "Getting weather for " + entry.unit + "...";
            fetch("/issues/weather/" + encodeURIComponent(entry.unit), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    subject: entry.ticketSubject || entry.subject || "",
                }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const line = data.message
                        || (
                            "Weather for "
                            + (data.unit || entry.unit)
                            + ": "
                            + (data.temperature_label || "?")
                            + ", "
                            + (data.conditions || "?")
                        );
                    consoleLines.push(line);
                    renderConsole(true);
                    statusEl.textContent = line;
                    applyGetWeatherToEntryIcons(entry, data, triggerEl);
                })
                .catch(function (error) {
                    const message = "Weather (Current) failed: " + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    if (isIcon) {
                        triggerEl.classList.remove("wx-loading");
                    }
                    if (isButton) {
                        triggerEl.disabled = false;
                        triggerEl.textContent = "Weather (Current)";
                    }
                });
        }

        // Same "el.setAttribute('role','button') + tabIndex=0 + Enter/Space
        // keydown" treatment as wireWeatherIconClick below, factored out for
        // the six command-menu status glyphs (alarm/power/shading/
        // dead-panel/VRM-freshness/power-vs-cell) — they're plain <span>s
        // with a click listener already attached at creation, so rather
        // than duplicating each one's handler body into a second keydown
        // listener, this just re-dispatches through el.click() on
        // activation, running whatever click listener is already there.
        function wireGlyphKeyboardActivation(el) {
            el.setAttribute("role", "button");
            el.tabIndex = 0;
            el.addEventListener("keydown", function (event) {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    el.click();
                }
            });
        }

        function wireWeatherIconClick(el, entry) {
            if (!el || el.dataset.wxWired === "1") {
                return;
            }
            el.dataset.wxWired = "1";
            el.setAttribute("role", "button");
            el.tabIndex = 0;
            el.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                runGetWeatherForEntry(entry, el);
            });
            el.addEventListener("keydown", function (event) {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    event.stopPropagation();
                    runGetWeatherForEntry(entry, el);
                }
            });
        }

        function applyGetWeatherToEntryIcons(entry, data, menuButton) {
            if (!data || !entry || !entry.unit) {
                return;
            }
            const unit = entry.unit;
            const payload = {
                unit: unit,
                icon: data.icon || "cloud",
                temperature_label: data.temperature_label,
                conditions: data.conditions,
                message: data.message || "",
                _fetchedAt: Date.now(),
            };
            weatherByUnit[unit] = payload;
            document.querySelectorAll(
                '.wx-icon[data-unit="' + unit + '"]'
            ).forEach(function (el) {
                applyWeatherToIcon(el, payload);
            });
            const row = menuButton && menuButton.closest
                ? menuButton.closest("li.ticket-row")
                : null;
            if (!row) {
                return;
            }
            let iconEl = row.querySelector(".wx-icon");
            if (!iconEl) {
                const rowBody = row.querySelector(".ticket-row-body");
                if (!rowBody) {
                    return;
                }
                iconEl = document.createElement("span");
                iconEl.className = "wx-icon wx-pending";
                iconEl.dataset.unit = unit;
                iconEl.dataset.subject = entry.ticketSubject || entry.subject || "";
                iconEl.setAttribute("aria-hidden", "true");
                const label = rowBody.querySelector(".ticket-label");
                if (label) {
                    rowBody.insertBefore(iconEl, label);
                } else {
                    rowBody.appendChild(iconEl);
                }
                wireWeatherIconClick(iconEl, entry);
            }
            applyWeatherToIcon(iconEl, payload);
        }

        function appendWeatherIcon(rowBody, entry) {
            const unit = entry && entry.unit;
            if (!unit) {
                return;
            }
            const el = document.createElement("span");
            el.className = "wx-icon wx-pending";
            el.dataset.unit = unit;
            // Carried along so refreshTicketWeather's bulk request can
            // pass it to _resolve_unit_weather_coords, same as any other
            // per-unit weather call — the icon's own subject context, not
            // used to parse a region out of it any more.
            el.dataset.subject = entry.ticketSubject || entry.subject || "";
            el.setAttribute("aria-hidden", "true");
            const cached = weatherByUnit[unit];
            if (cached) {
                applyWeatherToIcon(el, cached);
            } else {
                el.title = unit + " weather — click for site weather";
            }
            wireWeatherIconClick(el, entry);
            rowBody.appendChild(el);
        }

        function scheduleTicketWeatherRefresh() {
            if (weatherRefreshTimer) {
                clearTimeout(weatherRefreshTimer);
            }
            weatherRefreshTimer = setTimeout(function () {
                // Never force here (page load, or any list re-render) — the
                // server-side cache (_UNIT_WEATHER_CACHE, 30 min TTL) is
                // shared across every tab and every tech, and force:true
                // bypasses it entirely. This used to force on the first
                // refresh after every page load, which combined with the
                // auto-refresh timer below (same bug, every 30 min, every
                // open tab) burned through Open-Meteo's free-tier DAILY
                // quota (caught live, 2026-09-23: "Daily API request limit
                // exceeded" — every weather feature in the app, including
                // Battery Outlook's forecast, stayed dead for the rest of
                // that day). A normal (non-forced) refresh still shows
                // weather on first load — it just reuses another tab's
                // still-fresh cache entry instead of re-asking Open-Meteo
                // for data nothing has invalidated.
                refreshTicketWeather();
            }, 250);
        }

        function refreshTicketWeather(options) {
            const force = !!(options && options.force);
            weatherRefreshTimer = null;
            const needed = {};
            document.querySelectorAll(".wx-icon[data-unit]").forEach(function (el) {
                const unit = el.dataset.unit;
                if (unit) {
                    needed[unit] = el.dataset.subject || "";
                }
            });
            const unitList = Object.keys(needed);
            if (!unitList.length) {
                return Promise.resolve({ skipped: true });
            }
            const now = Date.now();
            if (!force) {
                unitList.forEach(function (unit) {
                    const cached = weatherByUnit[unit];
                    if (cached) {
                        document.querySelectorAll(
                            '.wx-icon[data-unit="' + unit + '"]'
                        ).forEach(function (el) {
                            applyWeatherToIcon(el, cached);
                        });
                    }
                });
            }
            const toFetch = force
                ? unitList
                : unitList.filter(function (unit) {
                    const cached = weatherByUnit[unit];
                    return !cached || (now - (cached._fetchedAt || 0) > WEATHER_CACHE_MS);
                });
            if (!toFetch.length) {
                return Promise.resolve({ skipped: true });
            }
            return fetch("/issues/weather-bulk-units", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    units: toFetch.map(function (unit) {
                        return { unit: unit, subject: needed[unit] };
                    }),
                    force: force,
                }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const units = data.units || {};
                    Object.keys(units).forEach(function (unit) {
                        const payload = units[unit];
                        if (!payload) {
                            return; // no resolvable GPS for this unit — leave it pending, not a failure
                        }
                        payload._fetchedAt = Date.now();
                        weatherByUnit[unit] = payload;
                        document.querySelectorAll(
                            '.wx-icon[data-unit="' + unit + '"]'
                        ).forEach(function (el) {
                            applyWeatherToIcon(el, payload);
                        });
                    });
                    return data;
                })
                .catch(function () {
                    // Keep pending placeholders; do not alert on bulk weather failures.
                    return { ok: false };
                });
        }

        function startWeatherAutoRefresh() {
            if (weatherAutoRefreshTimer) {
                return;
            }
            // Not forced — see scheduleTicketWeatherRefresh's comment.
            // Every open tab hitting this same 30-minute mark with
            // force:true was the main driver of the Open-Meteo daily
            // quota exhaustion; a normal refresh still catches anything
            // actually stale, just without redundantly re-fetching what
            // another tab (or this one, moments ago) already has cached.
            weatherAutoRefreshTimer = window.setInterval(function () {
                refreshTicketWeather();
            }, WEATHER_AUTO_REFRESH_MS);
        }

        startWeatherAutoRefresh();

        function renderConsole(scrollToBottom) {
            trimConsoleLines();
            const query = (consoleSearchEl.value || "").trim();
            if (!query) {
                consoleEl.textContent = consoleLines.join("\n") + (consoleLines.length ? "\n" : "");
                consoleMatchCountEl.textContent = "";
            } else {
                const matches = collectSearchMatches(consoleLines, query);
                consoleEl.innerHTML = matches.length
                    ? matches.map(function (line) {
                        return highlightMatch(line, query);
                    }).join("\n") + "\n"
                    : "";
                consoleMatchCountEl.textContent = matches.length
                    ? matches.length + " matching line" + (matches.length === 1 ? "" : "s")
                    : "No matches";
            }
            if (scrollToBottom && consoleFollow) {
                consoleEl.scrollTop = consoleEl.scrollHeight;
            }
        }

        consoleEl.addEventListener("scroll", function () {
            const nearBottom = consoleEl.scrollHeight - consoleEl.scrollTop - consoleEl.clientHeight < 40;
            consoleFollow = nearBottom;
        });

        consoleSearchEl.addEventListener("input", function () {
            renderConsole(false);
        });

        consoleClearBtn.addEventListener("click", function () {
            consoleLines.length = 0;
            renderConsole(false);
        });

        const snapshotModal = document.getElementById("snapshot_modal");
        const snapshotPanel = document.getElementById("snapshot_panel");
        const snapshotViewport = document.getElementById("snapshot_viewport");
        const snapshotImg = document.getElementById("snapshot_img");
        const snapshotStatus = document.getElementById("snapshot_status");
        const snapshotCopyBtn = document.getElementById("snapshot_copy_btn");
        const snapshotZoomOutBtn = document.getElementById("snapshot_zoom_out_btn");
        const snapshotZoomInBtn = document.getElementById("snapshot_zoom_in_btn");
        const snapshotZoomResetBtn = document.getElementById("snapshot_zoom_reset_btn");
        const snapshotCloseBtn = document.getElementById("snapshot_close_btn");
        const snapshotTicketBtn = document.getElementById("snapshot_ticket_btn");
        let snapshotObjectUrl = "";
        let snapshotBlob = null;

        // ---- Fisheye snapshot zoom/pan ------------------------------------
        // Scroll-wheel/drag zoom on the already-fetched image, no extra
        // camera calls — Copy to clipboard then crops to whatever's
        // currently visible in the viewport instead of the full circle
        // (see snapshotVisibleCropToPngBlob), so "zoom in on that van" is a
        // real cropped capture, not just a bigger on-screen view.
        const SNAPSHOT_ZOOM_MIN = 1;
        const SNAPSHOT_ZOOM_MAX = 6;
        let snapshotZoom = 1;
        let snapshotPanX = 0;
        let snapshotPanY = 0;
        let snapshotDragging = false;
        let snapshotDragStartX = 0;
        let snapshotDragStartY = 0;
        let snapshotPanStartX = 0;
        let snapshotPanStartY = 0;

        function clampSnapshotPan() {
            const baseW = snapshotImg.clientWidth || 0;
            const baseH = snapshotImg.clientHeight || 0;
            const viewportW = snapshotViewport.clientWidth || 0;
            const viewportH = snapshotViewport.clientHeight || 0;
            const scaledW = baseW * snapshotZoom;
            const scaledH = baseH * snapshotZoom;
            if (scaledW <= viewportW) {
                snapshotPanX = (viewportW - scaledW) / 2;
            } else {
                snapshotPanX = Math.min(0, Math.max(viewportW - scaledW, snapshotPanX));
            }
            if (scaledH <= viewportH) {
                snapshotPanY = (viewportH - scaledH) / 2;
            } else {
                snapshotPanY = Math.min(0, Math.max(viewportH - scaledH, snapshotPanY));
            }
        }

        function applySnapshotTransform() {
            clampSnapshotPan();
            snapshotImg.style.transform =
                "translate(" + snapshotPanX + "px, " + snapshotPanY + "px) scale(" + snapshotZoom + ")";
        }

        function resetSnapshotZoom() {
            snapshotZoom = SNAPSHOT_ZOOM_MIN;
            snapshotPanX = 0;
            snapshotPanY = 0;
            applySnapshotTransform();
        }

        // Keeps the point under (viewportX, viewportY) fixed on screen
        // while changing zoom level — the usual "zoom to cursor" feel.
        function zoomSnapshotTo(nextZoom, viewportX, viewportY) {
            const clamped = Math.min(SNAPSHOT_ZOOM_MAX, Math.max(SNAPSHOT_ZOOM_MIN, nextZoom));
            if (clamped === snapshotZoom) {
                return;
            }
            const localX = (viewportX - snapshotPanX) / snapshotZoom;
            const localY = (viewportY - snapshotPanY) / snapshotZoom;
            snapshotPanX = viewportX - clamped * localX;
            snapshotPanY = viewportY - clamped * localY;
            snapshotZoom = clamped;
            applySnapshotTransform();
        }

        function zoomSnapshotAtCenter(factor) {
            const rect = snapshotViewport.getBoundingClientRect();
            zoomSnapshotTo(snapshotZoom * factor, rect.width / 2, rect.height / 2);
        }

        snapshotViewport.addEventListener("wheel", function (event) {
            if (snapshotImg.hidden) {
                return;
            }
            event.preventDefault();
            const rect = snapshotViewport.getBoundingClientRect();
            const factor = event.deltaY < 0 ? 1.2 : 1 / 1.2;
            zoomSnapshotTo(snapshotZoom * factor, event.clientX - rect.left, event.clientY - rect.top);
        }, { passive: false });

        snapshotViewport.addEventListener("mousedown", function (event) {
            if (snapshotImg.hidden || snapshotZoom <= SNAPSHOT_ZOOM_MIN) {
                return;
            }
            snapshotDragging = true;
            snapshotDragStartX = event.clientX;
            snapshotDragStartY = event.clientY;
            snapshotPanStartX = snapshotPanX;
            snapshotPanStartY = snapshotPanY;
            snapshotViewport.classList.add("is-panning");
            event.preventDefault();
        });
        window.addEventListener("mousemove", function (event) {
            if (!snapshotDragging) {
                return;
            }
            snapshotPanX = snapshotPanStartX + (event.clientX - snapshotDragStartX);
            snapshotPanY = snapshotPanStartY + (event.clientY - snapshotDragStartY);
            applySnapshotTransform();
        });
        window.addEventListener("mouseup", function () {
            if (!snapshotDragging) {
                return;
            }
            snapshotDragging = false;
            snapshotViewport.classList.remove("is-panning");
        });
        snapshotViewport.addEventListener("dblclick", function (event) {
            event.stopPropagation();
            resetSnapshotZoom();
        });
        snapshotZoomInBtn.addEventListener("click", function (event) {
            event.stopPropagation();
            zoomSnapshotAtCenter(1.5);
        });
        snapshotZoomOutBtn.addEventListener("click", function (event) {
            event.stopPropagation();
            zoomSnapshotAtCenter(1 / 1.5);
        });
        snapshotZoomResetBtn.addEventListener("click", function (event) {
            event.stopPropagation();
            resetSnapshotZoom();
        });

        function setSnapshotTicketLink(ticketUrl) {
            if (ticketUrl) {
                snapshotTicketBtn.href = ticketUrl;
                snapshotTicketBtn.classList.remove("is-disabled");
                snapshotTicketBtn.removeAttribute("aria-disabled");
                snapshotTicketBtn.hidden = false;
                snapshotTicketBtn.title = "Open ticket in ERP";
            } else {
                snapshotTicketBtn.href = "#";
                snapshotTicketBtn.classList.add("is-disabled");
                snapshotTicketBtn.setAttribute("aria-disabled", "true");
                snapshotTicketBtn.hidden = true;
                snapshotTicketBtn.removeAttribute("title");
            }
        }

        function resetSnapshotCopyButton() {
            snapshotCopyBtn.disabled = true;
            snapshotCopyBtn.textContent = "Copy to clipboard";
        }

        function closeFisheyeSnapshot() {
            snapshotModal.classList.remove("is-open");
            snapshotImg.hidden = true;
            snapshotImg.onload = null;
            snapshotImg.onerror = null;
            snapshotImg.removeAttribute("src");
            snapshotBlob = null;
            resetSnapshotCopyButton();
            setSnapshotTicketLink("");
            resetSnapshotZoom();
            if (snapshotObjectUrl) {
                URL.revokeObjectURL(snapshotObjectUrl);
                snapshotObjectUrl = "";
            }
        }

        function snapshotImgToPngBlob(img) {
            return new Promise(function (resolve, reject) {
                if (!img || !img.complete || !img.naturalWidth || !img.naturalHeight) {
                    reject(new Error("Snapshot is not ready to copy"));
                    return;
                }
                const canvas = document.createElement("canvas");
                canvas.width = img.naturalWidth;
                canvas.height = img.naturalHeight;
                canvas.getContext("2d").drawImage(img, 0, 0);
                canvas.toBlob(function (pngBlob) {
                    if (!pngBlob) {
                        reject(new Error("Could not convert snapshot"));
                        return;
                    }
                    resolve(pngBlob);
                }, "image/png");
            });
        }

        // Same idea as snapshotImgToPngBlob, but only the portion of the
        // image currently visible inside a zoomed/panned viewport — maps
        // the viewport's on-screen rect back to natural image pixels (via
        // the img's unscaled CSS size, since a CSS transform never changes
        // clientWidth/clientHeight) and draws just that region, so Copy
        // captures the actual zoomed-in crop at full source resolution
        // instead of a screenshot of on-screen pixels.
        function snapshotVisibleCropToPngBlob(img, viewport, zoom, panX, panY) {
            return new Promise(function (resolve, reject) {
                if (!img || !img.complete || !img.naturalWidth || !img.naturalHeight) {
                    reject(new Error("Snapshot is not ready to copy"));
                    return;
                }
                if (!zoom || zoom <= 1.001) {
                    snapshotImgToPngBlob(img).then(resolve, reject);
                    return;
                }
                const baseW = img.clientWidth || img.naturalWidth;
                const baseH = img.clientHeight || img.naturalHeight;
                const viewportW = viewport.clientWidth || 0;
                const viewportH = viewport.clientHeight || 0;
                const cssToNaturalX = img.naturalWidth / baseW;
                const cssToNaturalY = img.naturalHeight / baseH;
                const localX0 = Math.max(0, Math.min(baseW, (0 - panX) / zoom));
                const localY0 = Math.max(0, Math.min(baseH, (0 - panY) / zoom));
                const localX1 = Math.max(0, Math.min(baseW, (viewportW - panX) / zoom));
                const localY1 = Math.max(0, Math.min(baseH, (viewportH - panY) / zoom));
                const naturalX0 = localX0 * cssToNaturalX;
                const naturalY0 = localY0 * cssToNaturalY;
                const naturalW = Math.max(1, (localX1 - localX0) * cssToNaturalX);
                const naturalH = Math.max(1, (localY1 - localY0) * cssToNaturalY);
                const canvas = document.createElement("canvas");
                canvas.width = Math.round(naturalW);
                canvas.height = Math.round(naturalH);
                canvas.getContext("2d").drawImage(
                    img,
                    naturalX0, naturalY0, naturalW, naturalH,
                    0, 0, canvas.width, canvas.height
                );
                canvas.toBlob(function (pngBlob) {
                    if (!pngBlob) {
                        reject(new Error("Could not convert snapshot"));
                        return;
                    }
                    resolve(pngBlob);
                }, "image/png");
            });
        }

        function copyPngViaCopyEvent(pngBlob) {
            return new Promise(function (resolve, reject) {
                let copyError = null;

                function onCopy(event) {
                    event.preventDefault();
                    const clipboardData = event.clipboardData;
                    if (!clipboardData || !clipboardData.items || !window.ClipboardItem) {
                        copyError = new Error("Image clipboard not supported");
                        return;
                    }
                    try {
                        clipboardData.clearData();
                        clipboardData.items.clear();
                        clipboardData.items.add(new ClipboardItem({
                            "image/png": pngBlob,
                        }));
                    } catch (err) {
                        copyError = err;
                    }
                }

                document.addEventListener("copy", onCopy, true);
                try {
                    const ok = document.execCommand("copy");
                    document.removeEventListener("copy", onCopy, true);
                    if (copyError) {
                        reject(copyError);
                    } else if (ok) {
                        resolve();
                    } else {
                        reject(new Error("Copy was blocked by the browser"));
                    }
                } catch (err) {
                    document.removeEventListener("copy", onCopy, true);
                    reject(err);
                }
            });
        }

        function copyPngViaHtmlDataUrl(pngBlob) {
            return new Promise(function (resolve, reject) {
                const reader = new FileReader();
                reader.onload = function () {
                    const dataUrl = reader.result;
                    let copyError = null;

                    function onCopy(event) {
                        event.preventDefault();
                        try {
                            event.clipboardData.clearData();
                            event.clipboardData.setData(
                                "text/html",
                                '<img src="' + dataUrl + '" alt="Fisheye snapshot">'
                            );
                            event.clipboardData.setData("text/plain", "");
                        } catch (err) {
                            copyError = err;
                        }
                    }

                    document.addEventListener("copy", onCopy, true);
                    try {
                        const ok = document.execCommand("copy");
                        document.removeEventListener("copy", onCopy, true);
                        if (copyError) {
                            reject(copyError);
                        } else if (ok) {
                            resolve();
                        } else {
                            reject(new Error("Copy was blocked by the browser"));
                        }
                    } catch (err) {
                        document.removeEventListener("copy", onCopy, true);
                        reject(err);
                    }
                };
                reader.onerror = function () {
                    reject(new Error("Could not read snapshot for copy"));
                };
                reader.readAsDataURL(pngBlob);
            });
        }

        function writeSnapshotToClipboard(pngBlob) {
            if (!pngBlob || !pngBlob.size) {
                return Promise.reject(new Error("Snapshot data is empty"));
            }
            const typedBlob = pngBlob.type === "image/png"
                ? pngBlob
                : new Blob([pngBlob], { type: "image/png" });

            if (window.isSecureContext && navigator.clipboard && window.ClipboardItem) {
                return navigator.clipboard.write([
                    new ClipboardItem({
                        "image/png": Promise.resolve(typedBlob),
                    }),
                ]);
            }
            if (window.ClipboardItem) {
                return copyPngViaCopyEvent(typedBlob).catch(function () {
                    return copyPngViaHtmlDataUrl(typedBlob);
                });
            }
            return copyPngViaHtmlDataUrl(typedBlob);
        }

        function copyFisheyeSnapshotToClipboard() {
            if (!snapshotBlob) {
                return;
            }
            snapshotCopyBtn.disabled = true;
            snapshotCopyBtn.textContent = "Copying...";
            const copyPromise = snapshotVisibleCropToPngBlob(
                snapshotImg, snapshotViewport, snapshotZoom, snapshotPanX, snapshotPanY
            ).then(writeSnapshotToClipboard);
            const timeoutPromise = new Promise(function (_, reject) {
                window.setTimeout(function () {
                    reject(new Error("Copy timed out"));
                }, 10000);
            });
            Promise.race([copyPromise, timeoutPromise])
                .then(function () {
                    snapshotCopyBtn.textContent = "Copied!";
                    snapshotCopyBtn.disabled = false;
                    window.setTimeout(function () {
                        snapshotCopyBtn.textContent = "Copy to clipboard";
                    }, 2000);
                })
                .catch(function (err) {
                    resetSnapshotCopyButton();
                    let message = err && err.message ? err.message : String(err);
                    if (!window.isSecureContext) {
                        message += " (This page is not on HTTPS or localhost; try opening it as http://127.0.0.1 instead of the machine name.)";
                    }
                    notifyError("Copy failed: " + message);
                });
        }

        // ---- Camera snapshot grid (non-Scrypted camera-outage follow-up) ------
        // Not real RTSP video — browsers can't play that protocol directly,
        // and standing up an actual RTSP->HLS/WebRTC transcode relay per
        // camera is a genuinely new subsystem this deliberately doesn't
        // build blind. Instead each tile is the same camera_snapshot proxy
        // the Fisheye Snapshot modal already uses, just re-fetched every
        // CAMERA_GRID_REFRESH_MS — close enough to "live" to spot a dead
        // camera at a glance next to its siblings, using infrastructure
        // that's already proven working. Built and cached lazily (not
        // template markup like snapshot_modal/graphs_modal) since this is
        // the one modal in the app with no fixed camera count to lay out
        // ahead of time.
        // The gap AFTER one snapshot finishes (load or error) before firing
        // the next one for that tile — not a blind fixed-clock interval.
        // Verified live, 2026-09-23 (RD3231, real hardware): a single
        // camera snapshot through the proxy takes 3-10+ seconds end to
        // end (Digest auth round trip + the camera's own on-demand JPEG
        // capture), nowhere close to fast enough for a flat setInterval.
        // The grid previously reassigned every tile's img.src on a blind
        // 1.5s clock regardless of whether the last request had actually
        // finished — the browser cancels an in-flight image request the
        // moment .src is reassigned, so a still-loading snapshot was
        // aborted before it could ever complete, and onload essentially
        // never fired. This is why the grid read as "never functions" —
        // every tile stayed stuck on "Unreachable"/a broken image
        // regardless of whether the camera itself was actually fine.
        // Self-pacing off each tile's own completion instead means a slow
        // camera just refreshes less often, rather than aborting itself.
        const CAMERA_GRID_REFRESH_MS = 3000;
        let cameraGridModalEl = null;
        let cameraGridTimers = [];
        let cameraGridActive = false;

        function stopCameraGridTimers() {
            cameraGridActive = false;
            cameraGridTimers.forEach(function (timer) { window.clearTimeout(timer); });
            cameraGridTimers = [];
        }

        function closeCameraGridModal() {
            if (cameraGridModalEl) {
                cameraGridModalEl.classList.remove("is-open");
            }
            stopCameraGridTimers();
        }

        function ensureCameraGridModal() {
            if (cameraGridModalEl) {
                return cameraGridModalEl;
            }
            const overlay = document.createElement("div");
            overlay.className = "camera-grid-modal";
            const panel = document.createElement("div");
            panel.className = "camera-grid-panel";
            const head = document.createElement("div");
            head.className = "camera-grid-head";
            const title = document.createElement("span");
            title.className = "camera-grid-title";
            const closeBtn = document.createElement("button");
            closeBtn.type = "button";
            closeBtn.className = "action-btn";
            closeBtn.textContent = "Close";
            closeBtn.addEventListener("click", closeCameraGridModal);
            head.appendChild(title);
            head.appendChild(closeBtn);
            const body = document.createElement("div");
            body.className = "camera-grid-body";
            panel.appendChild(head);
            panel.appendChild(body);
            overlay.appendChild(panel);
            overlay.addEventListener("click", function (event) {
                if (event.target === overlay) {
                    closeCameraGridModal();
                }
            });
            document.body.appendChild(overlay);
            cameraGridModalEl = overlay;
            return overlay;
        }

        function openCameraSnapshotGrid(unit) {
            if (!unit) {
                return;
            }
            document.querySelectorAll("details.command-menu[open]").forEach(function (menu) {
                menu.open = false;
            });
            const modal = ensureCameraGridModal();
            const title = modal.querySelector(".camera-grid-title");
            const body = modal.querySelector(".camera-grid-body");
            title.textContent = "Camera Grid — " + unit + " (auto-refreshing snapshots, not live video — each one can take several seconds)";
            body.innerHTML = "Loading cameras...";
            stopCameraGridTimers();
            cameraGridActive = true;
            modal.classList.add("is-open");

            fetch("/issues/cameras/" + encodeURIComponent(unit))
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    if (!cameraGridActive) {
                        // Closed again before the camera list even came back.
                        return;
                    }
                    const cameras = data.cameras || [];
                    body.innerHTML = "";
                    if (!cameras.length) {
                        body.textContent = "No cameras configured for " + unit;
                        return;
                    }
                    cameras.forEach(function (camera) {
                        const tile = document.createElement("div");
                        tile.className = "camera-grid-tile";
                        const label = document.createElement("div");
                        label.className = "camera-grid-tile-label";
                        label.textContent = camera.label;
                        const img = document.createElement("img");
                        img.alt = camera.label;
                        const status = document.createElement("div");
                        status.className = "camera-grid-tile-status";
                        tile.appendChild(img);
                        tile.appendChild(label);
                        tile.appendChild(status);
                        body.appendChild(tile);

                        const snapshotUrl = "/issues/camera-snapshot/" + encodeURIComponent(unit)
                            + "/" + encodeURIComponent(camera.target);
                        // Chained off completion, not a blind clock — see
                        // CAMERA_GRID_REFRESH_MS's own comment above for
                        // why. Each tile paces itself off how long ITS OWN
                        // camera actually takes to answer, instead of every
                        // tile firing on the same fixed beat regardless of
                        // whether the last request ever finished.
                        function scheduleNext() {
                            if (!cameraGridActive) {
                                return;
                            }
                            cameraGridTimers.push(window.setTimeout(refresh, CAMERA_GRID_REFRESH_MS));
                        }
                        img.addEventListener("load", function () {
                            tile.classList.remove("is-down");
                            status.textContent = "";
                            scheduleNext();
                        });
                        img.addEventListener("error", function () {
                            tile.classList.add("is-down");
                            status.textContent = "Unreachable";
                            scheduleNext();
                        });
                        function refresh() {
                            if (!cameraGridActive) {
                                return;
                            }
                            img.src = snapshotUrl + "?t=" + Date.now();
                        }
                        refresh();
                    });
                })
                .catch(function (error) {
                    body.textContent = "Failed to load cameras: " + (error.message || error);
                });
        }

        // Copy one already-loaded <img> to the clipboard as PNG — same two
        // steps copyFisheyeSnapshotToClipboard uses (re-encode via canvas,
        // then write), factored out so open360Snapshot's per-tile copy
        // buttons can reuse it instead of duplicating the clipboard dance.
        function copyImgToClipboard(img, btn) {
            const original = btn.textContent;
            btn.disabled = true;
            btn.textContent = "Copying...";
            const copyPromise = snapshotImgToPngBlob(img).then(writeSnapshotToClipboard);
            const timeoutPromise = new Promise(function (_, reject) {
                window.setTimeout(function () {
                    reject(new Error("Copy timed out"));
                }, 10000);
            });
            Promise.race([copyPromise, timeoutPromise])
                .then(function () {
                    btn.textContent = "Copied!";
                    btn.disabled = false;
                    window.setTimeout(function () {
                        btn.textContent = original;
                    }, 2000);
                })
                .catch(function (err) {
                    btn.textContent = original;
                    btn.disabled = false;
                    notifyError("Copy failed: " + (err.message || err));
                });
        }

        // "360 Snapshot" — every camera on the unit EXCEPT fisheye, each
        // fetched once (not the live-refreshing Camera Grid) and shown
        // together so a tech can look around the unit at a glance. Built
        // for checking sky/cloud conditions against a weather-driven
        // alert (Battery Outlook, Power vs Cell) without driving out —
        // fisheye faces the panels/ground, not the horizon, so it's
        // excluded on purpose. Reuses the Camera Grid's own modal/CSS
        // (ensureCameraGridModal, .camera-grid-*) since the tile layout is
        // identical; only the fetch-once-and-stop behavior differs.
        function open360Snapshot(unit, triggerBtn) {
            if (!unit) {
                return;
            }
            document.querySelectorAll("details.command-menu[open]").forEach(function (menu) {
                menu.open = false;
            });
            const modal = ensureCameraGridModal();
            const title = modal.querySelector(".camera-grid-title");
            const body = modal.querySelector(".camera-grid-body");
            title.textContent = "360 Snapshot — " + unit
                + " (captured just now, fisheye excluded, PTZ cameras tilt up toward the sky and return after)";
            body.innerHTML = "Loading cameras...";
            stopCameraGridTimers();
            modal.classList.add("is-open");

            // Backend already refuses a concurrent request per-camera (see
            // work_tool.camera_sky_snapshot's lock), but disabling the
            // button that started this batch too avoids a tech seeing a
            // confusing "already in progress" error from mashing it twice.
            // Re-enabled once every camera's fetch has settled, success or
            // not.
            const triggerBtnOriginalText = triggerBtn ? triggerBtn.textContent : null;
            if (triggerBtn) {
                triggerBtn.disabled = true;
                triggerBtn.textContent = "Working...";
            }
            const cameraFetches = [];

            fetch("/issues/cameras/" + encodeURIComponent(unit))
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const cameras = (data.cameras || []).filter(function (camera) {
                        return camera.target !== "fisheye";
                    });
                    body.innerHTML = "";
                    if (!cameras.length) {
                        body.textContent = "No non-fisheye cameras configured for " + unit;
                        return;
                    }
                    cameras.forEach(function (camera) {
                        const tile = document.createElement("div");
                        tile.className = "camera-grid-tile";
                        const label = document.createElement("div");
                        label.className = "camera-grid-tile-label";
                        label.textContent = camera.label;
                        const img = document.createElement("img");
                        img.alt = camera.label;
                        const status = document.createElement("div");
                        status.className = "camera-grid-tile-status";
                        const copyBtn = document.createElement("button");
                        copyBtn.type = "button";
                        copyBtn.className = "action-btn";
                        copyBtn.textContent = "Copy to clipboard";
                        copyBtn.disabled = true;
                        copyBtn.addEventListener("click", function () {
                            copyImgToClipboard(img, copyBtn);
                        });
                        tile.appendChild(img);
                        tile.appendChild(label);
                        tile.appendChild(status);
                        tile.appendChild(copyBtn);
                        body.appendChild(tile);

                        // PTZ cameras take a few extra seconds here — the
                        // route tilts up, shoots, then GotoPresets back to
                        // wherever it started (see work_tool.camera_sky_snapshot)
                        // before the response even comes back.
                        status.classList.add("is-info");
                        status.textContent = "Checking sky...";
                        const snapshotUrl = "/issues/camera-sky-snapshot/" + encodeURIComponent(unit)
                            + "/" + encodeURIComponent(camera.target);
                        const cameraFetch = fetch(snapshotUrl + "?t=" + Date.now())
                            .then(function (response) {
                                if (!response.ok) {
                                    return response.text().then(function (text) {
                                        throw new Error(text || ("HTTP " + response.status));
                                    });
                                }
                                const tilted = response.headers.get("X-Camera-Tilted") === "1";
                                const restored = response.headers.get("X-Camera-Restored") === "1";
                                return response.blob().then(function (blob) {
                                    return { blob: blob, tilted: tilted, restored: restored };
                                });
                            })
                            .then(function (result) {
                                const blob = result.blob;
                                const url = URL.createObjectURL(blob);
                                img.onload = function () {
                                    copyBtn.disabled = false;
                                    if (result.tilted && !result.restored) {
                                        // The tilt/snapshot succeeded but the camera
                                        // couldn't be confirmed back on its original
                                        // preset — surface this loudly rather than
                                        // silently reporting success (see
                                        // work_tool.camera_sky_snapshot's was_restored).
                                        tile.classList.add("is-down");
                                        status.classList.remove("is-info");
                                        status.textContent = "Tilted — restore unconfirmed, check camera manually";
                                        notifyError(
                                            camera.label + " on " + unit
                                                + ": tilted toward sky but the return-to-preset "
                                                + "could not be confirmed — verify it manually"
                                        );
                                    } else {
                                        status.classList.add("is-info");
                                        status.textContent = result.tilted ? "Tilted toward sky" : "";
                                    }
                                };
                                img.onerror = function () {
                                    tile.classList.add("is-down");
                                    status.classList.remove("is-info");
                                    status.textContent = "Could not display image";
                                };
                                img.src = url;
                            })
                            .catch(function (error) {
                                tile.classList.add("is-down");
                                status.classList.remove("is-info");
                                status.textContent = error && error.message ? error.message : "Unreachable";
                            });
                        cameraFetches.push(cameraFetch);
                    });
                })
                .catch(function (error) {
                    body.textContent = "Failed to load cameras: " + (error.message || error);
                })
                .finally(function () {
                    Promise.allSettled(cameraFetches).finally(function () {
                        if (triggerBtn) {
                            triggerBtn.disabled = false;
                            triggerBtn.textContent = triggerBtnOriginalText;
                        }
                    });
                });
        }

        function openFisheyeSnapshot(unit, ticketUrl) {
            document.querySelectorAll("details.command-menu[open]").forEach(function (menu) {
                menu.open = false;
            });
            setSnapshotTicketLink(ticketUrl || "");
            snapshotStatus.textContent = "Loading snapshot for " + unit + "...";
            snapshotStatus.hidden = false;
            snapshotImg.hidden = true;
            snapshotBlob = null;
            resetSnapshotCopyButton();
            resetSnapshotZoom();
            snapshotModal.classList.add("is-open");
            if (snapshotObjectUrl) {
                URL.revokeObjectURL(snapshotObjectUrl);
                snapshotObjectUrl = "";
            }
            fetch("/issues/fisheye/" + encodeURIComponent(unit))
                .then(function (response) {
                    if (!response.ok) {
                        return response.text().then(function (text) {
                            throw new Error(text || ("HTTP " + response.status));
                        });
                    }
                    return response.blob();
                })
                .then(function (blob) {
                    snapshotBlob = blob;
                    snapshotObjectUrl = URL.createObjectURL(blob);
                    snapshotImg.onload = function () {
                        snapshotCopyBtn.disabled = false;
                        resetSnapshotZoom();
                    };
                    snapshotImg.onerror = function () {
                        resetSnapshotCopyButton();
                        snapshotStatus.textContent = "Snapshot failed: could not display image";
                        snapshotStatus.hidden = false;
                        snapshotImg.hidden = true;
                    };
                    snapshotImg.src = snapshotObjectUrl;
                    snapshotImg.hidden = false;
                    snapshotStatus.hidden = true;
                })
                .catch(function (err) {
                    snapshotStatus.textContent = "Snapshot failed: " + (err.message || err);
                    snapshotStatus.hidden = false;
                    snapshotImg.hidden = true;
                    resetSnapshotCopyButton();
                });
        }

        snapshotCopyBtn.addEventListener("click", function (event) {
            event.stopPropagation();
            copyFisheyeSnapshotToClipboard();
        });
        snapshotTicketBtn.addEventListener("click", function (event) {
            event.stopPropagation();
            if (snapshotTicketBtn.classList.contains("is-disabled")) {
                event.preventDefault();
            }
        });
        snapshotCloseBtn.addEventListener("click", function (event) {
            event.stopPropagation();
            closeFisheyeSnapshot();
        });
        snapshotPanel.addEventListener("click", function (event) {
            event.stopPropagation();
        });
        snapshotModal.addEventListener("click", function () {
            closeFisheyeSnapshot();
        });
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                closeFisheyeSnapshot();
                document.querySelectorAll("details.command-menu").forEach(function (menu) {
                    menu.open = false;
                });
            }
        });
        document.addEventListener("click", function (event) {
            // The guided tour opens a menu itself to point at (see
            // tourOpenFirstRowMenu) and its own Next/Back/Skip controls live
            // outside that menu by design — without this check, every click
            // on those controls read as "clicked outside the menu, close
            // it," so the tour's own highlight ring would end up circling a
            // menu that had just silently closed underneath it (caught live:
            // "guided tour is bugged, doesn't open cmd window like it thinks
            // it does" — the Status row/Validate/Weather/... steps all rely
            // on the menu this closed).
            //
            // Gated on tourActive alone, NOT on where the click landed —
            // tourRenderCallout rebuilds the callout (innerHTML = "") to
            // build the NEXT step synchronously inside this same click's
            // own handler, which runs before this document-level listener
            // sees the event (it's still the same click, still bubbling).
            // That detaches the just-clicked Next/Back button from the
            // document before it gets here, so event.target.closest(...)
            // can no longer find its way back up to .tour-callout — traced
            // live with a temporary HTMLDetailsElement.prototype.open probe
            // (an earlier version of this fix checked
            // event.target.closest(".tour-callout, .tour-backdrop") and
            // still failed for exactly this reason). tourActive alone is
            // safe: the full-page backdrop (pointer-events:auto) blocks
            // every other click during the tour, so nothing legitimate
            // needs this listener while it's running, and endTour() closes
            // the tour-opened menu explicitly on its way out regardless of
            // how the tour ends.
            if (tourActive) {
                return;
            }
            document.querySelectorAll("details.command-menu").forEach(function (menu) {
                if (!menu.contains(event.target)) {
                    menu.open = false;
                }
            });
        });

        function clearCommandMenuPosition(menu) {
            const items = menu.querySelector(".command-menu-items");
            if (!items) {
                return;
            }
            items.style.position = "";
            items.style.left = "";
            items.style.top = "";
            items.style.right = "";
            items.style.zIndex = "";
        }

        function placeCommandMenu(menu) {
            const items = menu.querySelector(".command-menu-items");
            const summary = menu.querySelector("summary");
            if (!items || !summary || !menu.open) {
                return;
            }
            updateCommandMenuContext(menu);
            const rect = summary.getBoundingClientRect();
            const menuWidth = Math.max(items.offsetWidth || 0, 170);
            items.style.position = "fixed";
            items.style.zIndex = "2000";
            const left = rect.left;
            items.style.left = Math.max(8, Math.min(left, window.innerWidth - menuWidth - 8)) + "px";
            items.style.right = "auto";
            items.style.top = (rect.bottom + 4) + "px";
            const menuRect = items.getBoundingClientRect();
            if (menuRect.bottom > window.innerHeight - 8) {
                items.style.top = Math.max(8, rect.top - menuRect.height - 4) + "px";
            }
        }

        function placeOpenCommandMenus() {
            document.querySelectorAll("details.command-menu[open]").forEach(placeCommandMenu);
        }

        window.addEventListener("scroll", placeOpenCommandMenus, true);
        window.addEventListener("resize", placeOpenCommandMenus);

        const issueListIds = [
            "false_positives",
            "nuc_down",
            "truly_down",
            "scrypted_outage",
            "speaker_outage",
            "camera_outage",
            "panel_issues",
            "camera_view",
            "on_hold",
            "monitoring_hours",
            "termination",
            "relocation",
            "footage_request",
        ];
        const projectListIds = ["projects_open", "projects_in_progress", "projects_prep"];
        const listIds = issueListIds.concat(projectListIds);
        const bounceSwitchListIds = new Set([
            "false_positives",
            "nuc_down",
            "scrypted_outage",
            "speaker_outage",
            "camera_outage",
            "on_hold",
            "monitoring_hours",
            "termination",
            "relocation",
            "footage_request",
            "projects_open",
            "projects_in_progress",
        ]);
        const filterableIssueListIds = issueListIds.concat(["discarded_tickets"]);
        const filterableListIds = filterableIssueListIds.concat(projectListIds);
        let panelMode = "issues";
        const listState = {};
        let discardedState = [];
        let issuePollTimer = null;
        let issuePollInFlight = false;
        let unitToolsInFlight = false;
        let unitToolsEntry = null;
        let unitToolsSearchTimer = null;
        let lastLoadedUnitToolsQuery = "";
        let teamResolvedIds = new Set();
        // "Resolve Selected" toolbar action: gathers every ticket whose Resolved
        // checkbox is checked (across all issue lists) and finalizes them —
        // checking Resolved no longer removes a ticket from the list by itself.
        const resolveSelectedBtn = document.getElementById("resolve_selected");
        const resolveSelectedCountEl = document.getElementById("resolve_selected_count");

        function getResolvedCheckedEntries() {
            const entries = [];
            issueListIds.forEach(function (id) {
                (listState[id] || []).forEach(function (entry) {
                    if (entry.resolved) {
                        entries.push(entry);
                    }
                });
            });
            return entries;
        }

        function updateResolveSelectedButton() {
            const count = getResolvedCheckedEntries().length;
            resolveSelectedCountEl.textContent = String(count);
            resolveSelectedBtn.disabled = count === 0;
        }

        resolveSelectedBtn.addEventListener("click", function () {
            const entries = getResolvedCheckedEntries();
            if (!entries.length) {
                return;
            }
            resolveSelectedBtn.disabled = true;
            entries.forEach(function (entry) {
                markIssueResolved(entry);
            });
            updateResolveSelectedButton();
        });
        let resolvedTodayCount = 0;
        const ticketsResolvedEl = document.getElementById("tickets_resolved");
        const ticketsWorkedEl = document.getElementById("tickets_worked");
        const ticketsSkippedEl = document.getElementById("tickets_skipped");
        const statsStripEl = document.getElementById("stats_strip");
        const DOWN_STATS_LISTS = [
            { id: "nuc_down", label: "Offline compute" },
            { id: "scrypted_outage", label: "Scrypted outage" },
            { id: "speaker_outage", label: "Speaker outage" },
            { id: "camera_outage", label: "Camera outage" },
            { id: "truly_down", label: "Down full" },
            { id: "panel_issues", label: "Panel issues" },
        ];
        let busyUnitsCount = 0;
        // Previous poll's counts, so the stats strip can show a delta
        // (▲/▼ since last check) instead of only the instant value. Purely
        // informational — no click handler reads this, same as the rest of
        // the strip's read-only intent.
        let previousStatsCounts = null;

        function statsDeltaHtml(id, current) {
            if (!previousStatsCounts || !(id in previousStatsCounts)) {
                return "";
            }
            const diff = current - previousStatsCounts[id];
            if (diff === 0) {
                return "";
            }
            const cls = diff > 0 ? "is-up" : "is-down";
            const arrow = diff > 0 ? "▲" : "▼";
            return " <span class=\"stats-delta " + cls + "\">" + arrow + Math.abs(diff) + "</span>";
        }

        listIds.forEach(function (id) {
            listState[id] = [];
        });

        const listHeadingLabels = {
            false_positives: "Up Steady",
            nuc_down: "Offline compute",
            truly_down: "Down Full",
            scrypted_outage: "Scrypted outage",
            speaker_outage: "Speaker outage",
            camera_outage: "Camera outage",
            panel_issues: "Panel issues",
            camera_view: "Camera View",
            on_hold: "On Hold",
            monitoring_hours: "Monitoring Hours",
            termination: "Termination",
            relocation: "Relocation",
            footage_request: "Footage Request",
            projects_open: "Open",
            projects_in_progress: "In Progress",
            projects_prep: "Deployment Prep",
        };

        issueListIds.forEach(function (id) {
            if (id === "termination" || id === "relocation" || id === "monitoring_hours" || id === "footage_request") {
                return;
            }
            const listEl = document.getElementById(id);
            const heading = listEl && listEl.closest(".list-section")
                ? listEl.closest(".list-section").querySelector("h2")
                : null;
            if (!heading || heading.querySelector(".list-revalidate-btn")) {
                return;
            }
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "list-revalidate-btn";
            btn.textContent = "Revalidate";
            btn.title = "Re-check tickets in " + (listHeadingLabels[id] || id);
            btn.addEventListener("click", function () {
                revalidateList(id, btn);
            });
            heading.appendChild(btn);
        });

        function currentPanelMode() {
            const value = panelModeEl && panelModeEl.value;
            return value === "projects" || value === "reports" ? value : "issues";
        }


        function isProjectsList(id) {
            return (
                id === "projects_open"
                || id === "projects_in_progress"
                || id === "projects_prep"
            );
        }

        function isNocProjectsList(id) {
            return id === "projects_open" || id === "projects_in_progress";
        }

        function isPrepProjectsList(id) {
            return id === "projects_prep";
        }

        function isTerminationProjectSubject(subject) {
            const text = String(subject || "");
            if (/noc\s+termination\b/i.test(text)) {
                return true;
            }
            return /\btermination\b/i.test(text) && !/\bdeployment\b/i.test(text);
        }

        function isRelocationProjectSubject(subject) {
            const text = String(subject || "");
            if (/noc\s+relocation\b/i.test(text)) {
                return true;
            }
            return /\brelocation\b/i.test(text)
                && !/\bdeployment\b/i.test(text)
                && !/\btermination\b/i.test(text);
        }

        function isDeploymentProjectSubject(subject) {
            return /noc\s+deployment\b/i.test(String(subject || ""));
        }

        const issueCategoryOptions = [
            { value: "false_positives", label: "Up Steady" },
            { value: "nuc_down", label: "Offline compute" },
            { value: "scrypted_outage", label: "Scrypted outage" },
            { value: "speaker_outage", label: "Speaker outage" },
            { value: "camera_outage", label: "Camera outage" },
            { value: "truly_down", label: "Down Full" },
            { value: "panel_issues", label: "Panel issues" },
            { value: "camera_view", label: "Camera View" },
            { value: "on_hold", label: "On Hold" },
            { value: "monitoring_hours", label: "Monitoring Hours" },
            { value: "termination", label: "Termination" },
            { value: "relocation", label: "Relocation" },
            { value: "footage_request", label: "Footage Request" },
            { value: "discarded_tickets", label: "Miscellaneous" },
        ];
        const projectCategoryOptions = [
            { value: "projects_open", label: "Open" },
            { value: "projects_in_progress", label: "In Progress" },
            { value: "projects_prep", label: "Deployment Prep" },
        ];
        // Same All-lists/One-list shape as Issues/Projects, for Reports —
        // each of the seven fleet-wide checks is its own "list" here too.
        // value is the report's own <ul> id (not a listState key — reports
        // don't use listState; their row count comes straight off the
        // rendered DOM instead, see reportListRowCount).
        const reportCategoryOptions = [
            { value: "flap_report_list", label: "Flap Report" },
            { value: "zabbix_flap_report_list", label: "Zabbix Flap Report" },
            { value: "camera_outage_report_list", label: "Camera Outage Report" },
            { value: "units_unplugged_list", label: "Units Unplugged" },
            { value: "shaded_units_list", label: "Shaded Units" },
            { value: "dead_panel_list", label: "Dead Panels" },
            { value: "vrm_freshness_list", label: "VRM Disconnected" },
            { value: "battery_outlook_list", label: "Battery Outlook" },
            { value: "power_infra_list", label: "Power & Infra Alerts" },
            { value: "alarm_frequency_list", label: "Alarm Frequency" },
            { value: "recovery_email_report_list", label: "Recovery Emails" },
        ];
        const reportListIds = reportCategoryOptions.map(function (item) { return item.value; });
        // The five fleet-wide VRM checks (renderFleetReportRow) tag every
        // row with data-search-text; Flap Report/Power & Infra Alerts/
        // Alarm Frequency render their own row shapes and don't. Listed
        // explicitly rather than inferred from "0 rows currently have
        // data-search-text" — that would also be true of a searchable
        // report that's simply empty right now, which should still show
        // its own "no cached results"/"none" placeholder regardless of
        // the search box, not disappear along with it. See applyListFilters.
        const reportSearchableListIds = new Set([
            "units_unplugged_list", "shaded_units_list", "dead_panel_list",
            "vrm_freshness_list", "battery_outlook_list", "recovery_email_report_list",
        ]);

        // Which lists are currently selected. An empty set means "no filter"
        // — every list shows. The stats strip at the top of the page is the
        // filter UI: its chips are the buttons, so there is no separate row.
        let selectedIssueLists = new Set();
        let selectedProjectLists = new Set();
        let selectedReportLists = new Set();
        // Complete-state per list, previously stashed on the <option> elements
        // the old category dropdown owned.
        const listCompleteState = {};

        function currentSelectedLists() {
            const mode = currentPanelMode();
            if (mode === "projects") {
                return selectedProjectLists;
            }
            if (mode === "reports") {
                return selectedReportLists;
            }
            return selectedIssueLists;
        }

        function toggleListFilter(id) {
            const selected = currentSelectedLists();
            if (selected.has(id)) {
                selected.delete(id);
            } else {
                selected.add(id);
            }
            applyListFilters();
        }

        function clearListFilter() {
            currentSelectedLists().clear();
            applyListFilters();
        }

        // ---- All lists / One list + the multi-select category menu -----------
        // "All lists" shows everything. "One list" filters to whatever is
        // ticked in the dropdown — which now takes several lists at once, each
        // with its ticket count. Selection lives in the same Sets the filter
        // pass reads, so nothing else had to change.
        const listCategoryInputs = {};

        function filteringEnabled() {
            return !!(showOneListBtn && showOneListBtn.classList.contains("is-active"));
        }

        function currentCategoryOptions() {
            const mode = currentPanelMode();
            if (mode === "projects") {
                return projectCategoryOptions;
            }
            if (mode === "reports") {
                return reportCategoryOptions;
            }
            return issueCategoryOptions;
        }

        // Reports don't populate listState (see reportCategoryOptions) —
        // their row count comes straight off what's actually rendered.
        // "li:not(.empty)" excludes the "Click Refresh to load..." /
        // "Loading cached results..." placeholder row every report list
        // starts with.
        function reportListRowCount(listId) {
            const el = document.getElementById(listId);
            return el ? el.querySelectorAll("li:not(.empty)").length : 0;
        }

        function renderListCategoryMenu() {
            if (!listCategoryOptions) {
                return;
            }
            listCategoryOptions.innerHTML = "";
            Object.keys(listCategoryInputs).forEach(function (key) {
                delete listCategoryInputs[key];
            });

            currentCategoryOptions().forEach(function (item) {
                const row = document.createElement("label");
                row.className = "list-category-option";

                const box = document.createElement("input");
                box.type = "checkbox";
                box.value = item.value;
                box.addEventListener("change", function () {
                    const selected = currentSelectedLists();
                    if (box.checked) {
                        selected.add(item.value);
                    } else {
                        selected.delete(item.value);
                    }
                    applyListFilters();
                });

                const label = document.createElement("span");
                label.className = "option-label";
                label.textContent = item.label;

                const count = document.createElement("span");
                count.className = "option-count";
                count.textContent = "0";

                row.appendChild(box);
                row.appendChild(label);
                row.appendChild(count);
                listCategoryOptions.appendChild(row);
                listCategoryInputs[item.value] = { input: box, row: row, count: count };
            });

            const actions = document.createElement("div");
            actions.className = "list-category-actions";
            const selectAll = document.createElement("button");
            selectAll.type = "button";
            selectAll.textContent = "Select all";
            selectAll.addEventListener("click", function () {
                const selected = currentSelectedLists();
                currentCategoryOptions().forEach(function (item) {
                    selected.add(item.value);
                });
                applyListFilters();
            });
            const clearBtn = document.createElement("button");
            clearBtn.type = "button";
            clearBtn.textContent = "Clear";
            clearBtn.addEventListener("click", function () {
                currentSelectedLists().clear();
                applyListFilters();
            });
            const doneBtn = document.createElement("button");
            doneBtn.type = "button";
            doneBtn.textContent = "Done";
            doneBtn.addEventListener("click", closeListCategoryMenu);
            actions.appendChild(selectAll);
            actions.appendChild(clearBtn);
            actions.appendChild(doneBtn);
            listCategoryOptions.appendChild(actions);

            syncListControls();
        }

        // Keep the toggle buttons, the dropdown label and every checkbox in
        // step with the selection. Safe to call on every filter pass.
        function syncListControls() {
            const filtering = filteringEnabled();
            const selected = currentSelectedLists();

            if (showAllListsBtn && showOneListBtn) {
                showAllListsBtn.classList.toggle("is-active", !filtering);
                showAllListsBtn.setAttribute("aria-pressed", filtering ? "false" : "true");
                showOneListBtn.classList.toggle("is-active", filtering);
                showOneListBtn.setAttribute("aria-pressed", filtering ? "true" : "false");
            }
            if (listCategoryWrap) {
                listCategoryWrap.hidden = !filtering;
            }

            currentCategoryOptions().forEach(function (item) {
                const parts = listCategoryInputs[item.value];
                if (!parts) {
                    return;
                }
                const total = currentPanelMode() === "reports"
                    ? reportListRowCount(item.value)
                    : (listState[item.value] || []).length;
                const isSelected = selected.has(item.value);
                parts.input.checked = isSelected;
                parts.count.textContent = String(total);
                parts.row.classList.toggle("is-selected", isSelected);
                parts.row.classList.toggle("is-empty", total === 0 && !isSelected);
                parts.row.classList.toggle(
                    "is-complete", !!listCompleteState[item.value] && total > 0
                );
            });

            if (listCategoryToggleText) {
                const names = currentCategoryOptions()
                    .filter(function (item) { return selected.has(item.value); })
                    .map(function (item) { return item.label; });
                let text;
                if (!names.length) {
                    text = "Select lists";
                } else if (names.length === 1) {
                    text = names[0];
                } else if (names.length === currentCategoryOptions().length) {
                    text = "All " + names.length + " lists";
                } else {
                    text = names.length + " lists selected";
                }
                listCategoryToggleText.textContent = text;
                listCategoryToggleText.title = names.join(", ");
            }
        }

        function openListCategoryMenu() {
            if (!listCategoryWrap) {
                return;
            }
            listCategoryWrap.classList.add("is-open");
            listCategoryToggle.setAttribute("aria-expanded", "true");
        }

        function closeListCategoryMenu() {
            if (!listCategoryWrap) {
                return;
            }
            listCategoryWrap.classList.remove("is-open");
            listCategoryToggle.setAttribute("aria-expanded", "false");
        }

        function setListView(filtering) {
            if (filtering) {
                showOneListBtn.classList.add("is-active");
                showAllListsBtn.classList.remove("is-active");
                // Opening "One list" with nothing ticked would blank the page,
                // so start from the first list that actually has rows —
                // reports don't populate listState, so their own row count
                // (reportListRowCount) stands in for it there.
                const selected = currentSelectedLists();
                const reportsMode = currentPanelMode() === "reports";
                if (!selected.size) {
                    const firstWithTickets = currentCategoryOptions().find(function (item) {
                        return reportsMode
                            ? reportListRowCount(item.value) > 0
                            : (listState[item.value] || []).length > 0;
                    }) || currentCategoryOptions()[0];
                    if (firstWithTickets) {
                        selected.add(firstWithTickets.value);
                    }
                }
            } else {
                showOneListBtn.classList.remove("is-active");
                showAllListsBtn.classList.add("is-active");
                closeListCategoryMenu();
            }
            applyListFilters();
        }

        if (showAllListsBtn && showOneListBtn) {
            showAllListsBtn.addEventListener("click", function () {
                setListView(false);
            });
            showOneListBtn.addEventListener("click", function () {
                setListView(true);
            });
            listCategoryToggle.addEventListener("click", function (event) {
                event.stopPropagation();
                if (listCategoryWrap.classList.contains("is-open")) {
                    closeListCategoryMenu();
                } else {
                    openListCategoryMenu();
                }
            });
            // Ticking several boxes in a row must not close the menu.
            listCategoryOptions.addEventListener("click", function (event) {
                event.stopPropagation();
            });
            document.addEventListener("click", function (event) {
                if (listCategoryWrap && !listCategoryWrap.contains(event.target)) {
                    closeListCategoryMenu();
                }
            });
            document.addEventListener("keydown", function (event) {
                if (event.key === "Escape") {
                    closeListCategoryMenu();
                }
            });
        }

        function applyPanelMode() {
            panelMode = currentPanelMode();
            const projectsMode = panelMode === "projects";
            const reportsMode = panelMode === "reports";
            // Reports is its own page with its OWN All-lists/One-list
            // selection (see reportCategoryOptions) — the list-view toggle
            // and Select Lists dropdown apply there too now, so they're
            // NOT hidden for reportsMode. Search stays up too — every
            // fleet report row now carries a unit in data-search-text (see
            // renderFleetReportRow), the same applyListFilters() pass that
            // already filters ticket rows. The rest (checkboxes, ERP pull,
            // weather) still don't apply — R/W/S and ERP pull/weather have
            // no meaning for a fleet-wide check.
            if (clearCheckboxesBtn) {
                clearCheckboxesBtn.hidden = projectsMode || reportsMode;
            }
            if (updateWeatherBtn) {
                updateWeatherBtn.hidden = reportsMode;
            }
            if (resolveSelectedBtn) {
                resolveSelectedBtn.hidden = reportsMode;
            }
            if (pullErpBtn) {
                pullErpBtn.hidden = reportsMode;
            }
            renderListCategoryMenu();
            if (pullErpBtn && initialValidationComplete && !issuePollInFlight) {
                pullErpBtn.textContent = projectsMode ? "Pull Projects" : "Pull Issues";
                pullErpBtn.title = projectsMode
                    ? "Refresh Open/In Progress NOC projects from ERP now"
                    : "Refresh Open/Monitoring/On Hold tickets from ERP now";
            }
            if (reportsMode) {
                ensureReportsLoaded();
            }
            // applyListFilters() decides each report section's visibility
            // too (data-panel="reports" + reportListIds), respecting
            // whatever's selected in One-list mode — see its own body.
            applyListFilters();
        }

        function clearUnitToolsSection() {
            const section = document.getElementById("unit_tools_section");
            const el = document.getElementById("unit_tools");
            const countEl = document.getElementById("unit_tools_count");
            if (el) {
                el.innerHTML =
                    '<li class="empty">No matching tickets — search a unit for tools</li>';
            }
            if (section) {
                section.hidden = true;
            }
            if (countEl) {
                countEl.textContent = "";
            }
            unitToolsEntry = null;
            lastLoadedUnitToolsQuery = "";
        }

        function scheduleUnitToolsFromSearch(query, matchCount) {
            if (unitToolsSearchTimer) {
                clearTimeout(unitToolsSearchTimer);
                unitToolsSearchTimer = null;
            }
            const rawQuery = String(query || "").trim();
            if (!rawQuery) {
                clearUnitToolsSection();
                return;
            }
            if (matchCount > 0) {
                const section = document.getElementById("unit_tools_section");
                if (section) {
                    section.hidden = true;
                }
                return;
            }
            const normalizedQuery = rawQuery.toLowerCase();
            if (
                lastLoadedUnitToolsQuery === normalizedQuery
                && unitToolsEntry
                && unitToolsEntry.unit
            ) {
                // Unit Tools lives on the Issues panel — reported live:
                // searching a unit with no ticket matches while on the
                // Reports panel rendered (and tried to open) its command
                // menu into a section that's only ever shown on Issues, so
                // it stayed hidden and looked like nothing happened at all
                // ("just filters"). Same "switch panel first" fix the Flap
                // Report / Power & Infra Alerts row openers already use —
                // switching triggers applyPanelMode -> applyListFilters,
                // which reveals the section itself once inActivePanel is
                // true, so no manual section.hidden flip is needed here.
                if (panelModeEl && panelModeEl.value !== "issues") {
                    panelModeEl.value = "issues";
                    applyPanelMode();
                } else {
                    const section = document.getElementById("unit_tools_section");
                    if (section) {
                        section.hidden = false;
                    }
                }
                return;
            }
            unitToolsSearchTimer = window.setTimeout(function () {
                unitToolsSearchTimer = null;
                if (listSearchEl.value.trim().toLowerCase() !== normalizedQuery) {
                    return;
                }
                // Same "switch panel first" fix as above, for the first
                // load of a unit (not yet cached) — without this, loadUnitTools
                // still rendered and opened the command menu, just inside a
                // section that stayed hidden on a non-Issues panel.
                if (panelModeEl && panelModeEl.value !== "issues") {
                    panelModeEl.value = "issues";
                    applyPanelMode();
                }
                loadUnitTools(rawQuery, true);
                const toolsSection = document.getElementById("unit_tools_section");
                if (toolsSection && toolsSection.scrollIntoView) {
                    toolsSection.scrollIntoView({ behavior: "smooth", block: "start" });
                }
            }, 400);
        }

        function applyListFilters() {
            const query = listSearchEl.value.trim().toLowerCase();
            const rawQuery = listSearchEl.value.trim();
            const activePanelMode = currentPanelMode();
            const projectsMode = activePanelMode === "projects";
            // "All lists" shows everything; "One list" narrows to whatever is
            // ticked in the dropdown (one list or several).
            const selectedLists = currentSelectedLists();
            const filtering = filteringEnabled() && selectedLists.size > 0;
            let matchCount = 0;

            filterableListIds.forEach(function (id) {
                const listEl = document.getElementById(id);
                if (!listEl) {
                    return;
                }
                const sectionEl = listEl.closest(".list-section");
                const sectionPanel = sectionEl
                    ? (sectionEl.getAttribute("data-panel") || "issues")
                    : "issues";
                // filterableListIds never includes a "reports" section, but
                // spelling this out as a real three-way match (not just
                // "if not projects, must be issues") keeps that true by
                // construction rather than by omission.
                const inActivePanel = sectionPanel === activePanelMode;
                const rows = Array.from(listEl.querySelectorAll("[data-search-text]"));
                let visibleRows = 0;

                rows.forEach(function (row) {
                    const matches = !query || row.dataset.searchText.indexOf(query) !== -1;
                    row.hidden = !matches;
                    if (matches) {
                        visibleRows += 1;
                    }
                });

                const selected = !filtering || selectedLists.has(id);
                const sectionVisible = inActivePanel && selected && (!query || visibleRows > 0);
                if (sectionEl) {
                    sectionEl.hidden = !sectionVisible;
                }
                if (inActivePanel && selected && query) {
                    matchCount += visibleRows;
                }
            });

            // Same All-lists/One-list shape as above, for the seven report
            // sections, PLUS the same per-row text search the ticket lists
            // get above — every fleet report row now carries a unit in
            // data-search-text (see renderFleetReportRow), so a query
            // narrows Reports down to matching units too, not just a
            // whole-section toggle.
            const inReportsMode = activePanelMode === "reports";
            reportListIds.forEach(function (listId) {
                const listEl = document.getElementById(listId);
                const sectionEl = listEl ? listEl.closest(".list-section") : null;
                if (!sectionEl) {
                    return;
                }
                const selected = !filtering || selectedLists.has(listId);
                const searchable = reportSearchableListIds.has(listId);
                let visibleRows = 0;
                if (searchable && listEl) {
                    const rows = Array.from(listEl.querySelectorAll("[data-search-text]"));
                    rows.forEach(function (row) {
                        const matches = !query || row.dataset.searchText.indexOf(query) !== -1;
                        row.hidden = !matches;
                        if (matches) {
                            visibleRows += 1;
                        }
                    });
                }
                const sectionVisible = inReportsMode && selected && (!searchable || !query || visibleRows > 0);
                sectionEl.hidden = !sectionVisible;
                if (inReportsMode && selected && searchable && query) {
                    matchCount += visibleRows;
                }
            });

            if (query) {
                if (matchCount === 0) {
                    listMatchCountEl.textContent = "No ticket matches";
                } else {
                    listMatchCountEl.textContent =
                        matchCount + (matchCount === 1 ? " match" : " matches");
                }
            } else {
                listMatchCountEl.textContent = "";
            }

            renderStatsStrip();
            syncListControls();
            scheduleUnitToolsFromSearch(rawQuery, matchCount);
        }

        listSearchEl.addEventListener("input", applyListFilters);
        if (panelModeEl) {
            panelModeEl.addEventListener("change", applyPanelMode);
        }

        function persistLocalTicketState() {
            try {
                window.localStorage.setItem(
                    ticketStateStorageKey,
                    JSON.stringify(localTicketState)
                );
            } catch (ignore) {
                // Checkbox state remains in this tab if browser storage is unavailable.
            }
        }

        function openClearCheckboxesModal() {
            clearCheckboxesModal.classList.add("is-open");
            clearCheckboxesCancel.focus();
        }

        function closeClearCheckboxesModal() {
            clearCheckboxesModal.classList.remove("is-open");
            clearCheckboxesBtn.focus();
        }

        function clearTicketCheckboxes() {
            Object.keys(localTicketState).forEach(function (key) {
                const saved = localTicketState[key];
                if (!saved) {
                    return;
                }
                saved.worked = false;
                saved.skipped = false;
            });
            persistLocalTicketState();
            listIds.forEach(function (id) {
                (listState[id] || []).forEach(function (entry) {
                    entry.worked = false;
                    entry.skipped = false;
                });
                renderList(id);
            });
            updateTicketCounts();
            closeClearCheckboxesModal();
            serverTicketState = {};
            fetch("/issues/ticket-state/clear", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({}),
            }).catch(function () {
                // Local state is already cleared; next pollTicketState() retries the sync.
            });
        }

        clearCheckboxesBtn.addEventListener("click", openClearCheckboxesModal);
        pullErpBtn.disabled = true;
        pullErpBtn.title = "Wait for initial validation to finish";
        pullErpBtn.addEventListener("click", function () {
            pollForNewIssues({ force: true, manual: true });
        });
        if (updateWeatherBtn) {
            updateWeatherBtn.addEventListener("click", function () {
                if (updateWeatherBtn.disabled) {
                    return;
                }
                updateWeatherBtn.disabled = true;
                updateWeatherBtn.textContent = "Updating…";
                refreshTicketWeather({ force: true }).finally(function () {
                    updateWeatherBtn.disabled = false;
                    updateWeatherBtn.textContent = "Update Weather";
                });
            });
        }
        clearCheckboxesCancel.addEventListener("click", closeClearCheckboxesModal);
        clearCheckboxesConfirm.addEventListener("click", clearTicketCheckboxes);
        clearCheckboxesModal.addEventListener("click", function (event) {
            if (event.target === clearCheckboxesModal) {
                closeClearCheckboxesModal();
            }
        });
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && clearCheckboxesModal.classList.contains("is-open")) {
                closeClearCheckboxesModal();
            }
            if (event.key === "Escape" && patchUpdateModal.classList.contains("is-open")) {
                closePatchUpdateModal();
            }
            if (event.key === "Escape" && genericConfirmModal.classList.contains("is-open")) {
                closeGenericConfirmModal();
            }
            if (event.key === "Escape" && graphsModal.classList.contains("is-open")) {
                closeGraphsModal();
            }
            // Fallback for every other .confirm-modal (security_fix,
            // create_deployment(+success), create_termination,
            // create_relocation, site_action, clear_mu_coordinates,
            // clear_mu_site, create_refurbish, tech_checks) — roughly half
            // the app's confirm dialogs had no Escape handling at all
            // until now, each needing its own hand-wired case above like
            // the five before this one. Rather than adding ten more near-
            // identical blocks (and the eleventh, twelfth, ... every time a
            // new one is added), this clicks the open modal's own Cancel
            // button (or OK, for a pure-acknowledgment modal with no
            // Cancel, e.g. create_deployment_success) — reusing whatever
            // cleanup that modal's own click handler already does instead
            // of duplicating it, so nothing here can drift out of sync
            // with what "Cancel" actually does for a given modal.
            if (event.key === "Escape") {
                const openModal = document.querySelector(".confirm-modal.is-open");
                if (openModal) {
                    const dismissBtn = openModal.querySelector(".confirm-cancel") || openModal.querySelector(".confirm-ok");
                    if (dismissBtn) {
                        dismissBtn.click();
                    }
                }
            }
        });

        function unitSupportsLinux(entry) {
            return !!(entry && entry.hasScrypted);
        }

        function unitSupportsSnucReboot(entry) {
            return !!(entry && entry.unit && entry.hasPve);
        }

        function unitSupportsNucReboot(entry) {
            return !!(entry && entry.unit && !entry.hasPve);
        }

        function appendRebootComputeButton(parent, label, endpoint, entry, options) {
            const confirmMessage = options && options.confirmMessage;
            const rebootBtn = document.createElement("button");
            rebootBtn.type = "button";
            rebootBtn.className = "action-btn";
            rebootBtn.textContent = label;
            function fireReboot() {
                rebootBtn.disabled = true;
                rebootBtn.textContent = "Rebooting...";
                statusEl.textContent = label + " for " + entry.unit + "...";
                fetch(endpoint + encodeURIComponent(entry.unit), {
                    method: "POST",
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        const line = label + " for " + entry.unit + ": "
                            + (data.message || "Restarting");
                        consoleLines.push(line);
                        renderConsole(true);
                        statusEl.textContent = line;
                    })
                    .catch(function (error) {
                        const message = label + " failed: " + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        rebootBtn.disabled = false;
                        rebootBtn.textContent = label;
                    });
            }
            rebootBtn.addEventListener("click", function () {
                if (confirmMessage) {
                    openGenericConfirmModal(label + "?", confirmMessage, label, fireReboot);
                } else {
                    fireReboot();
                }
            });
            parent.appendChild(rebootBtn);
            return rebootBtn;
        }

        function appendNucMenuItems(nucMenu, entry) {
            appendRebootComputeButton(
                nucMenu,
                "Reboot NUC",
                "/issues/reboot-nuc/",
                entry,
                { confirmMessage: "This will reboot the NUC on " + entry.unit + ", interrupting compute/services briefly." }
            );

            const uptimeBtn = document.createElement("button");
            uptimeBtn.type = "button";
            uptimeBtn.className = "action-btn";
            uptimeBtn.textContent = "Uptime";
            uptimeBtn.addEventListener("click", function () {
                uptimeBtn.disabled = true;
                uptimeBtn.textContent = "Checking...";
                statusEl.textContent = "NUC uptime for " + entry.unit + "...";
                fetch("/issues/nuc-uptime/" + encodeURIComponent(entry.unit), {
                    method: "POST",
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        const output = data.output || "";
                        consoleLines.push("NUC uptime for " + entry.unit + ":");
                        if (output) {
                            output.split(/\r?\n/).forEach(function (line) {
                                if (line) {
                                    consoleLines.push(line);
                                }
                            });
                        } else {
                            consoleLines.push("(no output)");
                        }
                        renderConsole(true);
                        statusEl.textContent = "NUC uptime for " + entry.unit
                            + (output ? ": " + output.replace(/\s+/g, " ").trim() : " — no output");
                    })
                    .catch(function (error) {
                        const message = "Uptime failed: " + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        uptimeBtn.disabled = false;
                        uptimeBtn.textContent = "Uptime";
                    });
            });
            nucMenu.appendChild(uptimeBtn);
            appendLongPingNucButton(nucMenu, entry);

            const chkdskBtn = document.createElement("button");
            chkdskBtn.type = "button";
            chkdskBtn.className = "action-btn";
            chkdskBtn.textContent = "chkdsk (read-only)";
            chkdskBtn.title = "Run read-only chkdsk on the NUC over SSH";
            chkdskBtn.addEventListener("click", function () {
                const raw = window.prompt(
                    "Drive letter to check (read-only chkdsk):",
                    "C"
                );
                if (raw == null) {
                    return;
                }
                let drive = String(raw || "").trim().toUpperCase();
                drive = drive.replace(/[:\\/]/g, "");
                if (!/^[A-Z]$/.test(drive)) {
                    notifyError("Enter a single drive letter (A-Z).");
                    return;
                }
                chkdskBtn.disabled = true;
                chkdskBtn.textContent = "Running...";
                statusEl.textContent = "chkdsk " + drive + ": (read-only) on "
                    + entry.unit + "...";
                fetch("/issues/chkdsk/" + encodeURIComponent(entry.unit), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ drive: drive }),
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        const header = "chkdsk "
                            + drive
                            + ": (read-only) for "
                            + (data.unit || entry.unit)
                            + " — "
                            + (data.message || "done");
                        consoleLines.push(header);
                        const output = data.output || "";
                        if (output) {
                            output.split(/\r?\n/).forEach(function (line) {
                                if (line) {
                                    consoleLines.push(line);
                                }
                            });
                        } else {
                            consoleLines.push("(no output)");
                        }
                        renderConsole(true);
                        statusEl.textContent = header;
                    })
                    .catch(function (error) {
                        const message = "chkdsk failed: " + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        chkdskBtn.disabled = false;
                        chkdskBtn.textContent = "chkdsk (read-only)";
                    });
            });
            nucMenu.appendChild(chkdskBtn);
        }

        // Streams /issues/scrypted-ram-folder-stream/<unit> (see
        // stream_scrypted_ram_folder_status) into the console — shared by
        // the "Get Ram Folder" button and the camera-outage glyph's click
        // handler below, so a tech gets the actual per-camera/room detail
        // either way instead of the glyph only opening Scrypted/Platform
        // and leaving them to go find the button themselves. `btn` is
        // optional — the glyph has no button of its own to disable/relabel.
        // "entry" is optional (the camera-outage glyph's own shortcut call
        // omits a button but still wants the LED side effect below) — when
        // given, a confirmed-unreachable camera found during the check
        // flips this unit's LED to yellow (never moves it to a different
        // list — see the sentinel-line comment in
        // work_tool.stream_scrypted_ram_folder_status). Andrew's own
        // request, 2026-10-01.
        const RAM_FOLDER_RESULT_PREFIX = "__RAM_FOLDER_RESULT__ ";
        function runGetRamFolder(unit, btn, entry) {
            if (btn) {
                btn.disabled = true;
                btn.textContent = "Checking...";
            }
            statusEl.textContent = "Checking RAM folders for " + unit + "...";
            consoleLines.push("Get Ram Folder " + unit + " starting...");
            renderConsole(true);
            let lastLine = "";
            let ramFolderResult = null;
            // Pulls the trailing machine-readable result line out of the
            // stream — pushed to consoleLines only when it's NOT that line,
            // so the sentinel itself never shows up in the console.
            function handleLine(line) {
                if (line.indexOf(RAM_FOLDER_RESULT_PREFIX) === 0) {
                    try {
                        ramFolderResult = JSON.parse(line.slice(RAM_FOLDER_RESULT_PREFIX.length));
                    } catch (ignore) {
                        // Malformed sentinel — just skip the LED side effect below.
                    }
                    return;
                }
                consoleLines.push(line);
                lastLine = line;
            }
            return fetch("/issues/scrypted-ram-folder-stream/" + encodeURIComponent(unit), {
                method: "POST",
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("HTTP " + response.status);
                    }
                    if (!response.body || !response.body.getReader) {
                        return response.text().then(function (text) {
                            String(text || "").split(/\r?\n/).forEach(function (line) {
                                if (line) {
                                    handleLine(line);
                                }
                            });
                            renderConsole(true);
                        });
                    }
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();
                    let buffer = "";
                    function readChunk() {
                        return reader.read().then(function (result) {
                            if (result.done) {
                                if (buffer) {
                                    handleLine(buffer);
                                    renderConsole(true);
                                }
                                return;
                            }
                            buffer += decoder.decode(result.value, { stream: true });
                            const parts = buffer.split(/\r?\n/);
                            buffer = parts.pop() || "";
                            const before = consoleLines.length;
                            parts.forEach(function (line) {
                                if (line) {
                                    handleLine(line);
                                }
                            });
                            if (consoleLines.length > before) {
                                renderConsole(true);
                            }
                            return readChunk();
                        });
                    }
                    return readChunk();
                })
                .then(function () {
                    const failed = /not populating|failed/i.test(lastLine);
                    statusEl.textContent = lastLine || ("Get Ram Folder finished for " + unit);
                    if (failed) {
                        notify(lastLine, "error");
                    }
                    if (entry && ramFolderResult && ramFolderResult.any_camera_unreachable) {
                        entry.ledStatus = "yellow";
                        propagateLedFromEntry(entry);
                    }
                })
                .catch(function (error) {
                    const message = "Get Ram Folder failed: " + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    if (btn) {
                        btn.disabled = false;
                        btn.textContent = "Get Ram Folder";
                    }
                });
        }

        // Streams /issues/camera-rooms/<unit> results into the console —
        // shared by the Cameras menu's own button and the Scrypted menu's
        // copy (Get Ram Folder's room-vs-camera output reads a lot more
        // clearly once you know which room is which camera). `btn` is
        // optional, same convention as runGetRamFolder.
        function runGetCameraRooms(unit, btn) {
            if (btn) {
                btn.disabled = true;
                btn.textContent = "Checking...";
            }
            statusEl.textContent = "Checking camera rooms for " + unit + "...";
            return fetch("/issues/camera-rooms/" + encodeURIComponent(unit), { method: "POST" })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const cameras = data.cameras || [];
                    consoleLines.push("Camera rooms for " + unit + ":");
                    cameras.forEach(function (camera) {
                        consoleLines.push(
                            "  " + camera.label + ": "
                            + (camera.room
                                ? camera.room + (camera.source === "inferred" ? " (inferred)" : "")
                                : "FAILED — " + (camera.error || "unknown error"))
                        );
                    });
                    renderConsole(true);
                    statusEl.textContent = "Camera rooms for " + unit + " — see console";
                })
                .catch(function (error) {
                    const message = "Get Camera Rooms failed: " + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    if (btn) {
                        btn.disabled = false;
                        btn.textContent = "Get Camera Rooms";
                    }
                });
        }

        function appendScryptedLinuxMenuItems(scryptedLinuxMenu, entry) {
            const checkPatchBtn = document.createElement("button");
            checkPatchBtn.type = "button";
            checkPatchBtn.className = "action-btn";
            checkPatchBtn.textContent = "Check Patch Version";
            checkPatchBtn.addEventListener("click", function () {
                checkPatchBtn.disabled = true;
                checkPatchBtn.textContent = "Checking...";
                statusEl.textContent = "Checking patch version for " + entry.unit + "...";
                fetch("/issues/check-patch/" + encodeURIComponent(entry.unit), {
                    method: "POST",
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        const line = data.up_to_date
                            ? ("Patch version for " + entry.unit + " is "
                                + (data.date || "") + " — up to date")
                            : ("Patch version for " + entry.unit + " is "
                                + (data.date || "unknown")
                                + " — expected " + (data.expected_date || ""));
                        consoleLines.push(line);
                        if (data.package) {
                            consoleLines.push("Package: " + data.package);
                        }
                        renderConsole(true);
                        statusEl.textContent = line;
                    })
                    .catch(function (error) {
                        const message = "Check Patch Version failed: "
                            + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        checkPatchBtn.disabled = false;
                        checkPatchBtn.textContent = "Check Patch Version";
                    });
            });
            scryptedLinuxMenu.appendChild(checkPatchBtn);

            // Renamed from "Service Status" and moved here from Diagnostics
            // — this is a Scrypted-platform-specific check (which of the 16
            // platform services are active), so it belongs with the rest of
            // the Scrypted box's own tools rather than the generic
            // connectivity/camera checks in Diagnostics. Andrew's own
            // request, 2026-10-01.
            if (entry && entry.hasPve) {
                appendDiagnosticButton(scryptedLinuxMenu, entry, {
                    label: "Platform Status",
                    title: "Which platform services are actually running — check this before Restart All Services",
                    endpoint: "/issues/service-status/",
                    detailLines: function (data) {
                        return (data.services || []).map(function (svc) {
                            return (svc.ok ? "✓ " : "× ")
                                + svc.short + " — " + svc.state
                                + (svc.sub_state ? " (" + svc.sub_state + ")" : "");
                        });
                    },
                });
            }

            // NVMe SMART health on the PVE host — read-only (smartctl -a
            // reports, it does not start a self-test), so it sits with the
            // diagnostics rather than under Power / Disruptive Actions.
            if (entry && entry.hasPve) {
                const nvmeBtn = document.createElement("button");
                nvmeBtn.type = "button";
                nvmeBtn.className = "action-btn";
                nvmeBtn.textContent = "NVMe Health (PVE)";
                nvmeBtn.title = "smartctl -a on the PVE host boot drive — wear, spare, errors, temperature";
                nvmeBtn.addEventListener("click", function () {
                    nvmeBtn.disabled = true;
                    nvmeBtn.textContent = "Reading SMART...";
                    statusEl.textContent = "Reading NVMe health for " + entry.unit + "...";
                    fetch("/issues/pve-nvme-health/" + encodeURIComponent(entry.unit), {
                        method: "POST",
                    })
                        .then(function (response) {
                            return response.json().then(function (data) {
                                if (!response.ok || !data.ok) {
                                    throw new Error(data.error || ("HTTP " + response.status));
                                }
                                return data;
                            });
                        })
                        .then(function (data) {
                            const summary = data.summary
                                || ("NVMe health for " + entry.unit);
                            consoleLines.push(summary);
                            if (data.model) {
                                consoleLines.push(
                                    "  Drive: " + data.model
                                    + (data.serial ? " (" + data.serial + ")" : "")
                                    + " on " + (data.device || "")
                                );
                            }
                            const detail = [
                                ["Overall health", data.overall_health],
                                ["Critical warning", data.critical_warning],
                                ["Percentage used", data.percentage_used],
                                ["Available spare", data.available_spare],
                                ["Temperature (C)", data.temperature_c],
                                ["Warning temp threshold hit (min)", data.warning_temp_time],
                                ["Critical temp threshold hit (min)", data.critical_temp_time],
                                ["Power on hours", data.power_on_hours],
                                ["Unsafe shutdowns", data.unsafe_shutdowns],
                                ["Media errors", data.media_errors],
                            ];
                            detail.forEach(function (pair) {
                                if (pair[1] !== undefined && pair[1] !== null && pair[1] !== "") {
                                    consoleLines.push("  " + pair[0] + ": " + pair[1]);
                                }
                            });
                            renderConsole(true);
                            statusEl.textContent = summary;
                            if (data.status && data.status !== "ok") {
                                notify(summary, data.status === "fail" ? "error" : "warning");
                            }
                        })
                        .catch(function (error) {
                            const message = "NVMe Health failed: " + (error.message || error);
                            consoleLines.push(message);
                            renderConsole(true);
                            statusEl.textContent = message;
                            notifyError(message);
                        })
                        .finally(function () {
                            nvmeBtn.disabled = false;
                            nvmeBtn.textContent = "NVMe Health (PVE)";
                        });
                });
                scryptedLinuxMenu.appendChild(nvmeBtn);

                // Three separate, read-only checks rather than one combined
                // button — each answers a different question and has a
                // different data source, so a tech can run just the one
                // they need instead of always paying for all three. See
                // pve_kernel_io_errors/pve_boot_errors/pve_filesystem_health
                // in work_tool/diagnostics.py for what each SSHes for.
                const kernelIoBtn = document.createElement("button");
                kernelIoBtn.type = "button";
                kernelIoBtn.className = "action-btn";
                kernelIoBtn.textContent = "Kernel I/O Errors (PVE)";
                kernelIoBtn.title = "dmesg + journalctl -k grepped for storage I/O/NVMe/ATA/filesystem error signatures";
                kernelIoBtn.addEventListener("click", function () {
                    statusEl.textContent = "Checking kernel I/O errors for " + entry.unit + "...";
                    quickFetch(
                        kernelIoBtn, "Kernel I/O Errors",
                        "/issues/pve-kernel-io-errors/" + encodeURIComponent(entry.unit),
                        function (data) {
                            const lines = [data.summary || ("Kernel I/O errors for " + entry.unit)];
                            (data.dmesg_lines || []).forEach(function (line) {
                                lines.push("  [dmesg] " + line);
                            });
                            (data.journal_lines || []).forEach(function (line) {
                                lines.push("  [journal] " + line);
                            });
                            return lines.join("\n");
                        },
                        function (data) {
                            if (data.status && data.status !== "ok") {
                                notify(data.summary, data.status === "fail" ? "error" : "warning");
                            }
                        }
                    );
                });
                scryptedLinuxMenu.appendChild(kernelIoBtn);

                const bootErrBtn = document.createElement("button");
                bootErrBtn.type = "button";
                bootErrBtn.className = "action-btn";
                bootErrBtn.textContent = "Boot Errors (PVE)";
                bootErrBtn.title = "journalctl -b -p err — every error-or-worse journal entry since the PVE host's last boot, any subsystem (not just kernel-tagged ones)";
                bootErrBtn.addEventListener("click", function () {
                    statusEl.textContent = "Checking boot errors for " + entry.unit + "...";
                    quickFetch(
                        bootErrBtn, "Boot Errors",
                        "/issues/pve-boot-errors/" + encodeURIComponent(entry.unit),
                        function (data) {
                            const lines = [data.summary || ("Boot errors for " + entry.unit)];
                            (data.lines || []).forEach(function (line) {
                                lines.push("  " + line);
                            });
                            return lines.join("\n");
                        },
                        function (data) {
                            if (data.status && data.status !== "ok") {
                                notify(data.summary, data.status === "fail" ? "error" : "warning");
                            }
                        }
                    );
                });
                scryptedLinuxMenu.appendChild(bootErrBtn);

                const fsHealthBtn = document.createElement("button");
                fsHealthBtn.type = "button";
                fsHealthBtn.className = "action-btn";
                fsHealthBtn.textContent = "Filesystem Mount Health (PVE)";
                fsHealthBtn.title = "findmnt / lsblk — is root (or any other mounted device) already read-only?";
                fsHealthBtn.addEventListener("click", function () {
                    statusEl.textContent = "Checking filesystem health for " + entry.unit + "...";
                    quickFetch(
                        fsHealthBtn, "Filesystem Mount Health",
                        "/issues/pve-filesystem-health/" + encodeURIComponent(entry.unit),
                        function (data) {
                            const lines = [data.summary || ("Filesystem health for " + entry.unit)];
                            lines.push(
                                "  Root: " + (data.root_fs_source || "?")
                                + " (" + (data.root_fs_fstype || "?") + ") "
                                + (data.root_fs_options || "")
                            );
                            return lines.join("\n");
                        },
                        function (data) {
                            if (data.status && data.status !== "ok") {
                                notify(data.summary, "error");
                            }
                        }
                    );
                });
                scryptedLinuxMenu.appendChild(fsHealthBtn);

                const linkStatsBtn = document.createElement("button");
                linkStatsBtn.type = "button";
                linkStatsBtn.className = "action-btn";
                linkStatsBtn.textContent = "Link Stats (PVE)";
                linkStatsBtn.title = "ip -s link — per-interface RX/TX stats; any interface with dropped packets or errors is called out first";
                linkStatsBtn.addEventListener("click", function () {
                    statusEl.textContent = "Reading link stats for " + entry.unit + "...";
                    quickFetch(
                        linkStatsBtn, "Link Stats",
                        "/issues/pve-link-stats/" + encodeURIComponent(entry.unit),
                        function (data) {
                            const lines = [data.summary || ("Link stats for " + entry.unit)];
                            const flagged = data.flagged_interfaces || [];
                            const all = data.interfaces || [];
                            // Isolate the flagged interfaces in their own
                            // section, ahead of the full list — the whole
                            // point of flagging them is so a box with a
                            // dozen interfaces (physical NICs, the bond,
                            // the bridge, per-VM taps) doesn't need every
                            // row eyeballed by hand.
                            if (flagged.length) {
                                lines.push("  Flagged:");
                                flagged.forEach(function (iface) {
                                    lines.push(
                                        "  ⚠ " + iface.name + " (" + iface.state + ") — "
                                        + "RX errors=" + iface.rx_errors + " dropped=" + iface.rx_dropped
                                        + " over=" + iface.rx_over_errors
                                        + " | TX errors=" + iface.tx_errors + " dropped=" + iface.tx_dropped
                                        + " carrier=" + iface.tx_carrier_errors + " collisions=" + iface.tx_collisions
                                    );
                                });
                            }
                            lines.push("  All interfaces:");
                            all.forEach(function (iface) {
                                lines.push(
                                    "  " + (iface.flagged ? "⚠ " : "   ") + iface.name
                                    + " (" + iface.state + "): RX " + iface.rx_packets + " pkt"
                                    + ", TX " + iface.tx_packets + " pkt"
                                );
                            });
                            return lines.join("\n");
                        },
                        function (data) {
                            if (data.status && data.status !== "ok") {
                                notify(data.summary, "warning");
                            }
                        }
                    );
                });
                scryptedLinuxMenu.appendChild(linkStatsBtn);

                appendLongPingPveButton(scryptedLinuxMenu, entry);
            }

            const updatePatchBtn = document.createElement("button");
            updatePatchBtn.type = "button";
            updatePatchBtn.className = "action-btn";
            updatePatchBtn.textContent = "Update Patch Version";
            updatePatchBtn.addEventListener("click", function () {
                openPatchUpdateModal(entry.unit, updatePatchBtn);
            });
            scryptedLinuxMenu.appendChild(updatePatchBtn);

            const noAudioBtn = document.createElement("button");
            noAudioBtn.type = "button";
            noAudioBtn.className = "action-btn";
            noAudioBtn.textContent = "Set No Audio";
            noAudioBtn.title = "Enable No Audio on Fisheye / C1-180 / C2-180";
            noAudioBtn.addEventListener("click", function () {
                noAudioBtn.disabled = true;
                noAudioBtn.textContent = "Setting...";
                statusEl.textContent = "Setting No Audio for " + entry.unit + "...";
                fetch("/issues/scrypted-no-audio/" + encodeURIComponent(entry.unit), {
                    method: "POST",
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        const devices = data.devices || [];
                        const summary = "Set No Audio for " + entry.unit
                            + ": "
                            + devices.map(function (item) {
                                return (item.name || "?") + "=" + (item.status || "?");
                            }).join(", ");
                        consoleLines.push(summary);
                        devices.forEach(function (item) {
                            if (item.message) {
                                consoleLines.push(
                                    "  " + (item.name || "?") + ": " + item.message
                                );
                            }
                        });
                        renderConsole(true);
                        statusEl.textContent = summary;
                    })
                    .catch(function (error) {
                        const message = "Set No Audio failed: " + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        noAudioBtn.disabled = false;
                        noAudioBtn.textContent = "Set No Audio";
                    });
            });
            scryptedLinuxMenu.appendChild(noAudioBtn);

            const ramFolderBtn = document.createElement("button");
            ramFolderBtn.type = "button";
            ramFolderBtn.className = "action-btn";
            ramFolderBtn.textContent = "Get Ram Folder";
            ramFolderBtn.title = "Check each camera's /mnt/ram/cameras/<room>/fullsize is actually populating";
            ramFolderBtn.addEventListener("click", function () {
                runGetRamFolder(entry.unit, ramFolderBtn, entry);
            });
            scryptedLinuxMenu.appendChild(ramFolderBtn);

            // Same button as the Cameras menu (runGetCameraRooms) — handy
            // here too since it's what turns Get Ram Folder's room names
            // into actual camera identities.
            const roomsBtnScrypted = document.createElement("button");
            roomsBtnScrypted.type = "button";
            roomsBtnScrypted.className = "action-btn";
            roomsBtnScrypted.textContent = "Get Camera Rooms";
            roomsBtnScrypted.title = "Each camera's configured room, from its own SMTP Sender field (Dahua only)";
            roomsBtnScrypted.addEventListener("click", function () {
                runGetCameraRooms(entry.unit, roomsBtnScrypted);
            });
            scryptedLinuxMenu.appendChild(roomsBtnScrypted);

            // Disruptive/service-interrupting actions live in their own
            // submenu, separate from the routine diagnostic buttons above.
            // (appendCommandSubmenu is defined locally inside the two menu
            // builders that call into this function, so it's built inline here.)
            const powerActionsSubmenu = document.createElement("details");
            powerActionsSubmenu.className = "command-submenu";
            const powerActionsSummary = document.createElement("summary");
            powerActionsSummary.textContent = "Power / Disruptive Actions";
            powerActionsSubmenu.appendChild(powerActionsSummary);
            const powerActionsMenu = document.createElement("div");
            powerActionsMenu.className = "command-submenu-items";
            powerActionsSubmenu.appendChild(powerActionsMenu);
            scryptedLinuxMenu.appendChild(powerActionsSubmenu);

            if (unitSupportsSnucReboot(entry)) {
                appendRebootComputeButton(
                    powerActionsMenu,
                    "Reboot Scrypted",
                    "/issues/reboot-scrypted/",
                    entry,
                    { confirmMessage: "This will reboot the Scrypted box on " + entry.unit + ", interrupting recording/streaming briefly." }
                );
                appendRebootComputeButton(
                    powerActionsMenu,
                    "Reboot PVE",
                    "/issues/reboot-pve/",
                    entry,
                    { confirmMessage: "This will reboot the entire PVE host on " + entry.unit + ", taking every VM on it down briefly." }
                );
            }

            const securityFixBtn = document.createElement("button");
            securityFixBtn.type = "button";
            securityFixBtn.className = "action-btn";
            securityFixBtn.textContent = "Security Update Fix";
            securityFixBtn.title = "Guided GPU-passthrough kernel security update fix";
            securityFixBtn.addEventListener("click", function () {
                openSecurityFixModal(entry.unit, securityFixBtn);
            });
            powerActionsMenu.appendChild(securityFixBtn);

            const restartServicesBtn = document.createElement("button");
            restartServicesBtn.type = "button";
            restartServicesBtn.className = "action-btn";
            restartServicesBtn.textContent = "Restart All Services";
            restartServicesBtn.title = "Restart all platform services on the Scrypted box";
            function fireRestartServices() {
                restartServicesBtn.disabled = true;
                restartServicesBtn.textContent = "Restarting...";
                statusEl.textContent = "Restarting all services on " + entry.unit + "...";
                fetch("/issues/restart-services/" + encodeURIComponent(entry.unit), {
                    method: "POST",
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        const message = data.message || ("Restarted all services on " + entry.unit);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                    })
                    .catch(function (error) {
                        const message = "Restart All Services failed: " + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        restartServicesBtn.disabled = false;
                        restartServicesBtn.textContent = "Restart All Services";
                    });
            }
            restartServicesBtn.addEventListener("click", function () {
                openGenericConfirmModal(
                    "Restart All Services?",
                    "This will restart all 16 platform services on " + entry.unit
                        + " (including the Docker engine), briefly interrupting recording/streaming/alerts on this unit.",
                    "Restart All Services",
                    fireRestartServices
                );
            });
            powerActionsMenu.appendChild(restartServicesBtn);
        }

        function appendLinuxCommandMenus(commandItems, entry) {
            const showScrypted = unitSupportsLinux(entry);
            const showNuc = unitSupportsNucReboot(entry);
            if (!showScrypted && !showNuc) {
                return;
            }
            if (showNuc) {
                const nucMenu = appendCommandSubmenu(commandItems, "NUC");
                appendNucMenuItems(nucMenu, entry);
            }
            if (showScrypted) {
                const linuxMenu = appendCommandSubmenu(commandItems, "Linux");
                const scryptedLinuxMenu = appendCommandSubmenu(linuxMenu, "Scrypted");
                appendScryptedLinuxMenuItems(scryptedLinuxMenu, entry);
            }
        }

        // Keyed by "<unit>::<kind>" (kind: "router"/"nuc"/"pve"/
        // "camera:<target>") — a long ping against one target on a unit
        // must not collide with, or get silently cancelled by, one
        // against a different target on the same unit (see
        // _start_long_ping's own comment on this same pairing server-side).
        const longPingByUnit = {};

        function longPingStateKey(unit, kind) {
            return unit + "::" + kind;
        }

        function appendGetCarrierButton(parentMenu, entry) {
            const carrierBtn = document.createElement("button");
            carrierBtn.type = "button";
            carrierBtn.className = "action-btn";
            carrierBtn.textContent = "Get Carrier";
            if (!entry || !entry.unit) {
                carrierBtn.disabled = true;
                carrierBtn.title = "No unit on this ticket";
                parentMenu.appendChild(carrierBtn);
                return;
            }
            carrierBtn.title = "Lookup cell carrier from v19 SIM ICCID prefix";
            carrierBtn.addEventListener("click", function () {
                carrierBtn.disabled = true;
                carrierBtn.textContent = "Looking up...";
                statusEl.textContent = "Getting carrier for " + entry.unit + "...";
                fetch("/issues/carrier/" + encodeURIComponent(entry.unit), {
                    method: "POST",
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        const label = data.carrier || ((data.carriers || []).join(" / ")) || "?";
                        const line = "Carrier for " + (data.unit || entry.unit) + ": " + label;
                        consoleLines.push(line);
                        (data.sims || []).forEach(function (sim) {
                            const bits = [
                                "  SIM " + (sim.iccid || "?"),
                                "prefix " + (sim.prefix || "?"),
                                (sim.carrier || "unknown"),
                            ];
                            if (sim.address) {
                                bits.push(sim.address);
                            }
                            consoleLines.push(bits.join(" — "));
                        });
                        (data.unknown_iccids || []).forEach(function (iccid) {
                            consoleLines.push("  Unknown prefix for ICCID " + iccid);
                        });
                        renderConsole(true);
                        statusEl.textContent = line;
                    })
                    .catch(function (error) {
                        const message = "Get Carrier failed: " + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        carrierBtn.disabled = false;
                        carrierBtn.textContent = "Get Carrier";
                    });
            });
            parentMenu.appendChild(carrierBtn);
        }

        function appendWeatherCommandMenu(parentMenu, entry) {
            const weatherMenu = appendCommandSubmenu(parentMenu, "Weather");

            const currentBtn = document.createElement("button");
            currentBtn.type = "button";
            currentBtn.className = "action-btn";
            currentBtn.textContent = "Weather (Current)";
            if (!entry || !entry.unit) {
                currentBtn.disabled = true;
                currentBtn.title = "No unit on this ticket";
            } else {
                currentBtn.title = "Current weather from site GPS (trailer fallback)";
                currentBtn.addEventListener("click", function () {
                    runGetWeatherForEntry(entry, currentBtn);
                });
            }
            weatherMenu.appendChild(currentBtn);

            // Just the multi-day outlook — deliberately NOT the same
            // endpoint "Battery Outlook (Experimental)" below uses.
            // Andrew's own request, 2026-09-29: that one always pays for
            // a VRM installations+diagnostics lookup up front even though
            // its forecast half is GPS-only (ERP site/trailer address
            // geocoding) and never needed VRM — wasted latency, and a
            // hard dependency on VRM being up, for a tech who only wants
            // the weather. /issues/weather-forecast/<unit> shares that
            // same coordinate resolution but never touches VRM at all
            // (see work_tool.unit_weather_forecast).
            const forecastBtn = document.createElement("button");
            forecastBtn.type = "button";
            forecastBtn.className = "action-btn";
            forecastBtn.textContent = "Weather (Forecast)";
            if (!entry || !entry.unit) {
                forecastBtn.disabled = true;
                forecastBtn.title = "No unit on this ticket";
            } else {
                forecastBtn.title = "Next 5 days' cloud outlook for this unit's location (no VRM lookup)";
                forecastBtn.addEventListener("click", function () {
                    forecastBtn.disabled = true;
                    forecastBtn.textContent = "Checking...";
                    statusEl.textContent = "Weather forecast for " + entry.unit + "...";
                    const subject = entry.ticketSubject || entry.subject || "";
                    fetch("/issues/weather-forecast/" + encodeURIComponent(entry.unit), {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ subject: subject }),
                    })
                        .then(function (response) {
                            return response.json().then(function (data) {
                                if (!response.ok || !data.ok) {
                                    throw new Error(data.error || ("HTTP " + response.status));
                                }
                                return data;
                            });
                        })
                        .then(function (data) {
                            const forecast = data.forecast || [];
                            const headline = forecast.length
                                ? entry.unit + " — " + (data.cloudy_days != null && data.forecast_days != null
                                    ? data.cloudy_days + "/" + data.forecast_days + " cloudy day(s)"
                                    : "forecast")
                                : entry.unit + " — no forecast available";
                            consoleLines.push(headline);
                            forecast.forEach(function (day) {
                                consoleLines.push(
                                    "  " + day.date + ": " + day.conditions
                                    + (day.cloud_cover_mean != null
                                        ? " (" + Math.round(day.cloud_cover_mean) + "% cloud)"
                                        : "")
                                    + (day.cloudy ? " — cloudy" : "")
                                );
                            });
                            if (data.weather_error) {
                                consoleLines.push("  Forecast unavailable: " + data.weather_error);
                            }
                            renderConsole(true);
                            statusEl.textContent = headline;
                            notify(headline + (forecast.length ? "\n" + forecastTooltipText(forecast) : ""), null);
                        })
                        .catch(function (error) {
                            const message = "Weather forecast failed: " + (error.message || error);
                            consoleLines.push(message);
                            renderConsole(true);
                            statusEl.textContent = message;
                            notifyError(message);
                        })
                        .finally(function () {
                            forecastBtn.disabled = false;
                            forecastBtn.textContent = "Weather (Forecast)";
                        });
                });
            }
            weatherMenu.appendChild(forecastBtn);

            const region = regionFromSubject(
                (entry && (entry.ticketSubject || entry.subject)) || ""
            );
            const historyInfo = REGION_WEATHER_HISTORY[region];
            if (historyInfo) {
                const historyLink = document.createElement("a");
                historyLink.className = "action-btn";
                historyLink.href =
                    "https://www.timeanddate.com/weather/usa/"
                    + historyInfo.slug
                    + "/historic";
                historyLink.target = "_blank";
                historyLink.rel = "noopener noreferrer";
                historyLink.textContent = "Weather (History)";
                historyLink.title =
                    "Historic weather for " + historyInfo.name + " (" + region + ")";
                weatherMenu.appendChild(historyLink);
            } else {
                const historyBtn = document.createElement("button");
                historyBtn.type = "button";
                historyBtn.className = "action-btn";
                historyBtn.textContent = "Weather (History)";
                historyBtn.disabled = true;
                historyBtn.title = "No known region in subject (LAX/OAK/HOU/PHX/SLC/DEN)";
                weatherMenu.appendChild(historyBtn);
            }

            // Experimental: correlates this trailer's VRM battery SOC with
            // the cloud outlook for its site/trailer location. Errors
            // cleanly (e.g. "no VRM installation found") on units with no
            // matching trailer, so this stays unconditional rather than
            // trying to guess client-side which units have one.
            const batteryBtn = document.createElement("button");
            batteryBtn.type = "button";
            batteryBtn.className = "action-btn";
            batteryBtn.textContent = "Battery Outlook (Experimental)";
            if (!entry || !entry.unit) {
                batteryBtn.disabled = true;
                batteryBtn.title = "No unit on this ticket";
            } else {
                batteryBtn.title = "VRM battery SOC vs. the multi-day cloud outlook — experimental, read-only";
                batteryBtn.addEventListener("click", function () {
                    batteryBtn.disabled = true;
                    batteryBtn.textContent = "Checking...";
                    statusEl.textContent = "Battery outlook for " + entry.unit + "...";
                    const subject = entry.ticketSubject || entry.subject || "";
                    fetch("/issues/battery-outlook/" + encodeURIComponent(entry.unit), {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ subject: subject }),
                    })
                        .then(function (response) {
                            return response.json().then(function (data) {
                                if (!response.ok || !data.ok) {
                                    throw new Error(data.error || ("HTTP " + response.status));
                                }
                                return data;
                            });
                        })
                        .then(function (data) {
                            consoleLines.push(data.summary || ("Battery outlook for " + entry.unit));
                            if (data.ac_power_detail) {
                                consoleLines.push("  AC power (" + data.ac_power_label + "): " + data.ac_power_detail);
                            }
                            (data.forecast || []).forEach(function (day) {
                                consoleLines.push(
                                    "  " + day.date + ": " + day.conditions
                                    + (day.cloud_cover_mean != null
                                        ? " (" + Math.round(day.cloud_cover_mean) + "% cloud)"
                                        : "")
                                    + (day.cloudy ? " — cloudy" : "")
                                );
                            });
                            if (data.weather_error) {
                                consoleLines.push("  Forecast unavailable: " + data.weather_error);
                            }
                            if (data.soc_error) {
                                consoleLines.push("  Battery %: " + data.soc_error);
                            }
                            renderConsole(true);
                            statusEl.textContent = data.summary || ("Battery outlook complete for " + entry.unit);
                        })
                        .catch(function (error) {
                            const message = "Battery outlook failed: " + (error.message || error);
                            consoleLines.push(message);
                            renderConsole(true);
                            statusEl.textContent = message;
                            notifyError(message);
                        })
                        .finally(function () {
                            batteryBtn.disabled = false;
                            batteryBtn.textContent = "Battery Outlook (Experimental)";
                        });
                });
            }
            weatherMenu.appendChild(batteryBtn);
        }

        // ---- Graphs (experimental) --------------------------------------------
        // One modal, two data sources: Battery (VRM) and Network Latency
        // (Zabbix ping history) — same inline-SVG renderer either way. One
        // axis, one series per chart (never dual-axis — these are different
        // units), a thin rounded line in the app's existing accent color,
        // and a hover crosshair+tooltip since a static line alone doesn't
        // expose values.
        const graphsModal = document.getElementById("graphs_modal");
        const graphsTitle = document.getElementById("graphs_title");
        const graphsSubtitle = document.getElementById("graphs_subtitle");
        const graphsInfoLineEl = document.getElementById("graphs_info_line");
        const graphsBatteryGlyphEl = document.getElementById("graphs_battery_glyph");
        const graphsForecastGlyphEl = document.getElementById("graphs_forecast_glyph");
        const graphsTicketLineEl = document.getElementById("graphs_ticket_line");
        const graphsTicketLinkEl = document.getElementById("graphs_ticket_link");
        const graphsHours = document.getElementById("graphs_hours");
        const graphsRefreshBtn = document.getElementById("graphs_refresh");
        const graphs360Btn = document.getElementById("graphs_360_snapshot");
        const graphsDeviceMenuEl = document.getElementById("graphs_device_menu");
        const graphsVerdictLineEl = document.getElementById("graphs_verdict_line");
        const graphsVerdictBadgeEl = document.getElementById("graphs_verdict_badge");
        const graphsVerdictLabelEl = document.getElementById("graphs_verdict_label");
        const graphsVerdictTextEl = document.getElementById("graphs_verdict_text");
        const graphsVerdictFactsEl = document.getElementById("graphs_verdict_facts");
        const graphsVerdictMoreBtn = document.getElementById("graphs_verdict_more");
        const graphsVerdictRecheckBtn = document.getElementById("graphs_verdict_recheck");
        const graphsAlarmChipEl = document.getElementById("graphs_alarm_chip");
        const graphsPlugChipEl = document.getElementById("graphs_plug_chip");
        const graphsVrmChipEl = document.getElementById("graphs_vrm_chip");
        const graphsFlapChipEl = document.getElementById("graphs_flap_chip");
        const graphsUptimeRefreshBtn = document.getElementById("graphs_uptime_refresh");
        const graphsClose = document.getElementById("graphs_close");
        const graphsCloseX = document.getElementById("graphs_close_x");
        const graphsBody = document.getElementById("graphs_body");
        let graphsUnit = "";
        let graphsSubject = "";
        // {startMs, endMs, label} or null — the specific window a finding
        // (Diagnostic Header's View Graph action) wants drawn on every
        // chart in the modal, so the tech sees the flagged period against
        // the actual data instead of re-finding it by eye. Set by
        // openGraphsModal's optional 4th argument; every other caller
        // (Graphs submenu, report rows) omits it and gets a plain chart.
        let graphsHighlightRange = null;
        // Array of {tMs, label, kind} — individual points in time worth
        // marking on every chart, distinct from graphsHighlightRange's
        // shaded WINDOW (a duration). Set by openGraphsModal's optional
        // 6th argument (a single marker object or an array of them) —
        // currently only openPowerVsCellRowDetail uses it, to mark when
        // the switch itself came back up AND when the ticket was opened,
        // alongside the shaded loss window, so how all three relate (or
        // don't) is visible on the graph, not just in the summary text.
        // `kind` is optional and only changes styling (see
        // renderLineChart's marker drawing / .battery-chart-marker.is-*).
        let graphsMarkers = [];
        // A fleet report row is keyed by its MU trailer (the actual VRM
        // installation), not the RD/FD head a tech would recognize from a
        // ticket subject — opening a graph straight from one of those rows
        // used to show a bare "MU9062", or worse "MU9062 (VRM: MU9062)"
        // once the VRM lookup echoed the same name back. Set by
        // openGraphsModal's optional 5th argument (e.g. "RD9062(MU9062)")
        // when the caller already knows the head; every other caller omits
        // it and the subtitle falls back to the plain unit, unchanged.
        let graphsDisplayLabel = null;
        // Free-text info line shown right under the subtitle — set by
        // openGraphsModal's optional 7th argument. Persists across a
        // Window/Refresh change the same as graphsHighlightRange/
        // graphsMarkers (loadGraphs never touches it). Currently just
        // switch uptime (see openPowerVsCellRowDetail) — the toast/console
        // line it also gets pushed to scrolls away; this stays on screen
        // as long as the graph itself does.
        let graphsInfoLine = null;
        // VRM battery %, shown next to the switch-uptime info line in
        // network mode only (same "power outage vs cell outage" context
        // the uptime line already serves — the battery reading is exactly
        // the other half of "is this actually a power problem"). Same
        // small colored pill as the command menu's own battery glyph (see
        // applyBatteryGlyphFromCache/batterySocTier) — reused here rather
        // than a plain text line, per Andrew's own request, 2026-10-01.
        // Fetched fresh on every open via loadGraphsBatteryLine.
        let graphsBatteryRequestId = 0;
        // Each mode: what to fetch, how to read the response, and the fixed
        // chart order (never dual-axis, so no metric is ever combined with
        // another on one chart — see GRAPH_MODES below).
        // Each mode's own hour options — VRM's /stats keeps real history to
        // 30 days (checked: unit_battery_history caps there); Zabbix goes
        // further (90d) but switches to hourly trend averages past 7 days,
        // since its raw per-poll history isn't kept that long (checked
        // live: still there 25 days back, gone by 30).
        const BATTERY_HOURS_OPTIONS = [
            { value: 24, label: "Last 24 hours" },
            { value: 72, label: "Last 3 days" },
            { value: 168, label: "Last 7 days" },
            { value: 720, label: "Last 30 days" },
        ];
        const NETWORK_HOURS_OPTIONS = [
            // A short window matters more here than on the battery graphs —
            // packet loss/response time can spike and clear in well under an
            // hour, and a real ~30-minute outage all but disappears at the
            // default 7-day width (caught live: a coworker's Zabbix graph,
            // zoomed to ~6 hours, showed an obvious flat 100%-loss plateau
            // that the same unit's 7-day view here only showed as a
            // hairline spike — same underlying data, just too compressed to
            // read as "blatant" the way theirs was).
            { value: 6, label: "Last 6 hours" },
            { value: 12, label: "Last 12 hours" },
            { value: 24, label: "Last 24 hours" },
            { value: 72, label: "Last 3 days" },
            { value: 168, label: "Last 7 days" },
            { value: 720, label: "Last 30 days (hourly avg)" },
            { value: 2160, label: "Last 90 days (hourly avg)" },
        ];
        // Mirrors work_tool._format_age — a graph's own subtitle is the one
        // place "how old is this VRM data" needs to read naturally rather
        // than as a raw number, since a technician reads it, not code.
        function formatAgeShort(ageSeconds) {
            if (ageSeconds == null) {
                return "unknown";
            }
            const seconds = Math.max(0, ageSeconds);
            if (seconds < 3600) {
                const minutes = Math.round(seconds / 60);
                return minutes + " minute" + (minutes === 1 ? "" : "s");
            }
            if (seconds < 86400) {
                return (seconds / 3600).toFixed(1) + " hours";
            }
            return (seconds / 86400).toFixed(1) + " days";
        }
        const GRAPH_MODES = {
            battery: {
                titleText: "Battery Graphs",
                endpoint: "/issues/battery-history/",
                order: ["system_overview", "voltage", "soc", "current", "pv_power", "yield_today"],
                loadingText: "Loading from VRM...",
                failureLabel: "Battery Graphs",
                hoursOptions: BATTERY_HOURS_OPTIONS,
                subtitle: function (unit, data) {
                    let text = unit;
                    // Skip the "(VRM: X)" echo when X is already sitting
                    // right there in the unit text — either because unit
                    // IS the bare installation name (opened straight off a
                    // fleet report row with no resolved head, e.g. "MU9062")
                    // or because it's the RD(MU) display label
                    // (graphsDisplayLabel) that already spells it out, e.g.
                    // "RD9062(MU9062)" — either way, repeating it a second
                    // time added nothing.
                    if (data.installation_name && text.indexOf(data.installation_name) === -1) {
                        text += " (VRM: " + data.installation_name + ")";
                    }
                    // "fresh" is the expected case and stays quiet — only
                    // call out VRM's own last-report age when it's NOT
                    // fresh, so a stale reading can't be mistaken for a
                    // live one just because a graph is on screen.
                    if (data.vrm_freshness && data.vrm_freshness !== "fresh") {
                        text += " — VRM last reported " + formatAgeShort(data.vrm_last_seen_seconds_ago)
                            + " ago (" + data.vrm_freshness + ")";
                    }
                    return text;
                },
            },
            network: {
                titleText: "Network Latency Graphs",
                endpoint: "/issues/network-latency-history/",
                order: ["router_response", "router_loss", "switch_response", "switch_loss"],
                loadingText: "Loading from Zabbix...",
                failureLabel: "Network Latency Graphs",
                hoursOptions: NETWORK_HOURS_OPTIONS,
                subtitle: function (unit, data) {
                    return unit + " — Router/Switch ICMP checks"
                        + (data.resolution ? " (" + data.resolution + ")" : "");
                },
            },
        };
        let graphsMode = "battery";

        function renderLineChart(container, points, options) {
            const width = 640;
            const height = 130;
            const padding = { top: 8, right: 10, bottom: 8, left: 46 };
            const plotW = width - padding.left - padding.right;
            const plotH = height - padding.top - padding.bottom;
            container.innerHTML = "";

            if (!points || !points.length) {
                const empty = document.createElement("div");
                empty.className = "battery-chart-empty";
                empty.textContent = "No data for this window.";
                container.appendChild(empty);
                return;
            }

            const svgNS = "http://www.w3.org/2000/svg";
            const dataXMin = Math.min.apply(null, points.map(function (p) { return p.t; }));
            const dataXMax = Math.max.apply(null, points.map(function (p) { return p.t; }));
            const dataYs = points.map(function (p) { return p.v; });

            // A straight line drawn across a real data gap (the unit
            // stopped reporting for a while) visually claims continuity
            // that was never there — exactly the "hide the disconnect"
            // failure this whole review is about, just in chart form.
            // Breaking the path instead of connecting across a gap that's
            // well beyond the series' own normal spacing makes the gap
            // itself visible rather than smoothing over it. The threshold
            // is derived from THIS series' own median spacing (never a
            // fixed number — a 15-min-interval window and an hourly-trend
            // one have very different normal cadences) with a 30-minute
            // floor so ordinary polling jitter never triggers a false break.
            // Computed once off the full series — unaffected by zoom.
            const gaps = [];
            for (let i = 1; i < points.length; i++) {
                gaps.push(points[i].t - points[i - 1].t);
            }
            gaps.sort(function (a, b) { return a - b; });
            const medianGap = gaps.length ? gaps[Math.floor(gaps.length / 2)] : 0;
            const gapThresholdMs = Math.max(medianGap * 4, 30 * 60 * 1000);

            // Scroll-to-zoom state — a view window into [dataXMin, dataXMax].
            // Starts full width; scrolling narrows/widens it around the
            // cursor's own time position and Y auto-rescales to whatever's
            // currently visible, same as most interactive chart tools.
            // Independent per chart (its own closure/SVG) — deliberately
            // not linked across the modal's stacked charts, which would
            // need real shared state this modal doesn't have today.
            let viewMin = dataXMin;
            let viewMax = dataXMax;
            // Below this span there's nothing meaningfully narrower to
            // show — Zabbix's own finest native poll interval is ~3 min.
            const MIN_SPAN_MS = 3 * 60 * 1000;
            // Click-and-drag panning once zoomed in — outer-scope (not
            // re-declared in draw()) so a drag survives the SVG rebuild
            // each pan step triggers (draw() tears down and recreates the
            // overlay it started on).
            let isDragging = false;
            let dragStartClientX = 0;
            let dragStartViewMin = viewMin;
            let dragStartViewMax = viewMax;

            container.style.position = "relative";
            const svg = document.createElementNS(svgNS, "svg");
            svg.setAttribute("viewBox", "0 0 " + width + " " + height);
            svg.setAttribute("class", "battery-chart-svg");
            svg.setAttribute("role", "img");
            container.appendChild(svg);

            const tooltip = document.createElement("div");
            tooltip.className = "battery-chart-tooltip";
            tooltip.hidden = true;
            container.appendChild(tooltip);

            const zoomHint = document.createElement("div");
            zoomHint.className = "battery-chart-zoom-hint";
            zoomHint.textContent = "scroll to zoom · dbl-click to reset";
            container.appendChild(zoomHint);

            function draw() {
                svg.innerHTML = "";
                svg.setAttribute(
                    "aria-label",
                    options.label + ": " + points.length + " readings, "
                        + dataYs[0].toFixed(1) + " to " + dataYs[dataYs.length - 1].toFixed(1) + " " + options.unit
                );

                // Y rescales to whatever's actually in view, not the
                // series' full range — falls back to the full range if
                // the current window happens to contain zero points
                // (a real gap zoomed into).
                const visible = points.filter(function (p) { return p.t >= viewMin && p.t <= viewMax; });
                const ys = (visible.length ? visible : points).map(function (p) { return p.v; });
                const yMinRaw = Math.min.apply(null, ys);
                const yMaxRaw = Math.max.apply(null, ys);
                const yPad = (yMaxRaw - yMinRaw) * 0.12 || Math.abs(yMaxRaw) * 0.05 || 1;
                const yLo = yMinRaw - yPad;
                const yHi = yMaxRaw + yPad;

                function xPos(t) {
                    return padding.left + (viewMax === viewMin ? plotW / 2 : (t - viewMin) / (viewMax - viewMin) * plotW);
                }
                function yPos(v) {
                    return padding.top + (yHi === yLo ? plotH / 2 : (yHi - v) / (yHi - yLo) * plotH);
                }

                // The finding's own time window (see the Diagnostic Header's
                // "View Graph" action) — drawn first so grid/line/threshold
                // all render on top of it. Silently does nothing if the
                // window doesn't overlap the current view at all (e.g. a
                // shading window from hours ago while zoomed into a recent
                // few minutes).
                if (
                    options.highlightRange
                    && options.highlightRange.endMs >= viewMin
                    && options.highlightRange.startMs <= viewMax
                ) {
                    const hx1 = xPos(Math.max(options.highlightRange.startMs, viewMin));
                    const hx2 = xPos(Math.min(options.highlightRange.endMs, viewMax));
                    const highlightRect = document.createElementNS(svgNS, "rect");
                    highlightRect.setAttribute("x", hx1);
                    highlightRect.setAttribute("y", padding.top);
                    highlightRect.setAttribute("width", Math.max(1, hx2 - hx1));
                    highlightRect.setAttribute("height", plotH);
                    highlightRect.setAttribute("class", "battery-chart-highlight");
                    svg.appendChild(highlightRect);
                    if (options.highlightRange.label) {
                        const highlightLabel = document.createElementNS(svgNS, "text");
                        highlightLabel.textContent = options.highlightRange.label;
                        highlightLabel.setAttribute("x", (hx1 + hx2) / 2);
                        highlightLabel.setAttribute("y", padding.top + 9);
                        highlightLabel.setAttribute("class", "battery-chart-highlight-label");
                        highlightLabel.setAttribute("text-anchor", "middle");
                        svg.appendChild(highlightLabel);
                    }
                }

                // Individual points in time — see renderLineChart's
                // `markers` option, e.g. "switch came back up" and "ticket
                // opened" (openPowerVsCellRowDetail) — drawn alongside
                // (not instead of) any highlight range above, so how an
                // outage, a reboot, and a ticket's own timing relate is
                // visible on the graph itself, not just in the summary
                // text. Labels anchor at the bottom (the highlight's own
                // label sits near the top) and stack upward per marker so
                // two that land close together don't overlap each other.
                (options.markers || []).forEach(function (marker, markerIndex) {
                    if (!marker || marker.tMs < viewMin || marker.tMs > viewMax) {
                        return;
                    }
                    const mx = xPos(marker.tMs);
                    const kindClass = marker.kind ? (" is-" + marker.kind) : "";
                    const markerLine = document.createElementNS(svgNS, "line");
                    markerLine.setAttribute("x1", mx);
                    markerLine.setAttribute("x2", mx);
                    markerLine.setAttribute("y1", padding.top);
                    markerLine.setAttribute("y2", height - padding.bottom);
                    markerLine.setAttribute("class", "battery-chart-marker" + kindClass);
                    svg.appendChild(markerLine);
                    if (marker.label) {
                        const markerLabel = document.createElementNS(svgNS, "text");
                        markerLabel.textContent = marker.label;
                        markerLabel.setAttribute("x", mx);
                        markerLabel.setAttribute("y", height - padding.bottom - 4 - markerIndex * 12);
                        markerLabel.setAttribute("class", "battery-chart-marker-label" + kindClass);
                        markerLabel.setAttribute(
                            "text-anchor",
                            mx > width - 100 ? "end" : (mx < 100 ? "start" : "middle")
                        );
                        svg.appendChild(markerLabel);
                    }
                });

                [0, 0.5, 1].forEach(function (frac) {
                    const y = padding.top + frac * plotH;
                    const line = document.createElementNS(svgNS, "line");
                    line.setAttribute("x1", padding.left);
                    line.setAttribute("x2", width - padding.right);
                    line.setAttribute("y1", y);
                    line.setAttribute("y2", y);
                    line.setAttribute("class", "battery-chart-grid");
                    svg.appendChild(line);
                    const label = document.createElementNS(svgNS, "text");
                    label.textContent = (yHi - frac * (yHi - yLo)).toFixed(1);
                    label.setAttribute("x", padding.left - 6);
                    label.setAttribute("y", y + 3);
                    label.setAttribute("class", "battery-chart-axis-label");
                    label.setAttribute("text-anchor", "end");
                    svg.appendChild(label);
                });

                // Reference lines (e.g. a low-battery cutoff) — only ever
                // added by the caller for a metric where a fixed number is
                // actually meaningful regardless of system (SOC is a % of
                // capacity on any battery; a voltage cutoff would need to
                // know the trailer's system voltage first, which nothing here
                // currently knows reliably, so no threshold is drawn for
                // voltage — see renderGraphs).
                (options.thresholds || []).forEach(function (threshold) {
                    if (threshold.value < yLo || threshold.value > yHi) {
                        return;
                    }
                    const y = yPos(threshold.value);
                    const line = document.createElementNS(svgNS, "line");
                    line.setAttribute("x1", padding.left);
                    line.setAttribute("x2", width - padding.right);
                    line.setAttribute("y1", y);
                    line.setAttribute("y2", y);
                    line.setAttribute("class", "battery-chart-threshold");
                    svg.appendChild(line);
                    if (threshold.label) {
                        const label = document.createElementNS(svgNS, "text");
                        label.textContent = threshold.label;
                        label.setAttribute("x", width - padding.right - 4);
                        label.setAttribute("y", y - 3);
                        label.setAttribute("class", "battery-chart-threshold-label");
                        label.setAttribute("text-anchor", "end");
                        svg.appendChild(label);
                    }
                });

                // Drawn from the FULL points array, not just the visible
                // window — xPos naturally pushes an off-view point outside
                // the viewBox, which clips (SVG's default overflow:hidden
                // on the root), so the path still looks right at a zoomed
                // edge without needing to slice the data first.
                const pathD = points.map(function (p, i) {
                    const isGapStart = i > 0 && (p.t - points[i - 1].t) > gapThresholdMs;
                    return (i === 0 || isGapStart ? "M" : "L") + xPos(p.t).toFixed(1) + "," + yPos(p.v).toFixed(1);
                }).join(" ");
                const path = document.createElementNS(svgNS, "path");
                path.setAttribute("d", pathD);
                path.setAttribute("class", "battery-chart-line");
                path.setAttribute("fill", "none");
                svg.appendChild(path);

                const crosshair = document.createElementNS(svgNS, "line");
                crosshair.setAttribute("class", "battery-chart-crosshair");
                crosshair.setAttribute("y1", padding.top);
                crosshair.setAttribute("y2", height - padding.bottom);
                crosshair.style.display = "none";
                svg.appendChild(crosshair);

                const dot = document.createElementNS(svgNS, "circle");
                dot.setAttribute("r", 3.5);
                dot.setAttribute("class", "battery-chart-dot");
                dot.style.display = "none";
                svg.appendChild(dot);

                const overlay = document.createElementNS(svgNS, "rect");
                overlay.setAttribute("x", padding.left);
                overlay.setAttribute("y", padding.top);
                overlay.setAttribute("width", plotW);
                overlay.setAttribute("height", plotH);
                overlay.setAttribute("fill", "transparent");
                // Re-applied every draw() (the overlay itself is rebuilt
                // each time) — reflects whether a drag is currently in
                // progress on THIS chart.
                overlay.style.cursor = isDragging ? "grabbing" : "grab";
                svg.appendChild(overlay);

                function timeAtClientX(clientX) {
                    const rect = svg.getBoundingClientRect();
                    const svgX = (clientX - rect.left) / rect.width * width;
                    const frac = Math.min(1, Math.max(0, (svgX - padding.left) / plotW));
                    return viewMin + frac * (viewMax - viewMin);
                }

                function nearestPoint(clientX) {
                    const t = timeAtClientX(clientX);
                    let nearest = points[0];
                    let bestDiff = Infinity;
                    points.forEach(function (p) {
                        const diff = Math.abs(p.t - t);
                        if (diff < bestDiff) {
                            bestDiff = diff;
                            nearest = p;
                        }
                    });
                    return nearest;
                }

                overlay.addEventListener("mousemove", function (event) {
                    // A drag in progress moves the view itself — the
                    // crosshair/tooltip tracking the cursor at the same
                    // time would just be confusing noise on top of that.
                    if (isDragging) {
                        return;
                    }
                    const nearest = nearestPoint(event.clientX);
                    const x = xPos(nearest.t);
                    const y = yPos(nearest.v);
                    crosshair.setAttribute("x1", x);
                    crosshair.setAttribute("x2", x);
                    crosshair.style.display = "";
                    dot.setAttribute("cx", x);
                    dot.setAttribute("cy", y);
                    dot.style.display = "";
                    tooltip.hidden = false;
                    tooltip.textContent = new Date(nearest.t).toLocaleString() + " — "
                        + nearest.v.toFixed(2) + " " + options.unit;
                    const leftPct = (x / width) * 100;
                    tooltip.style.left = Math.min(Math.max(leftPct, 5), 75) + "%";
                });
                overlay.addEventListener("mouseleave", function () {
                    crosshair.style.display = "none";
                    dot.style.display = "none";
                    tooltip.hidden = true;
                });

                // Scroll to zoom, centered on the cursor's own time
                // position — narrows/widens [viewMin, viewMax] and
                // redraws. preventDefault (needs {passive:false} — wheel
                // listeners default to passive) so this doesn't ALSO
                // scroll the graphs modal itself while the cursor's over
                // a chart.
                overlay.addEventListener("wheel", function (event) {
                    event.preventDefault();
                    if (dataXMax === dataXMin) {
                        return;
                    }
                    const cursorT = timeAtClientX(event.clientX);
                    const zoomFactor = event.deltaY < 0 ? 0.8 : 1.25;
                    const currentSpan = viewMax - viewMin;
                    const span = Math.max(MIN_SPAN_MS, Math.min(dataXMax - dataXMin, currentSpan * zoomFactor));
                    const ratio = span / currentSpan;
                    let newMin = cursorT - (cursorT - viewMin) * ratio;
                    let newMax = newMin + span;
                    if (newMin < dataXMin) {
                        newMin = dataXMin;
                        newMax = newMin + span;
                    }
                    if (newMax > dataXMax) {
                        newMax = dataXMax;
                        newMin = newMax - span;
                    }
                    viewMin = Math.max(dataXMin, newMin);
                    viewMax = Math.min(dataXMax, newMax);
                    zoomHint.classList.toggle("is-zoomed", viewMin > dataXMin || viewMax < dataXMax);
                    draw();
                }, { passive: false });

                overlay.addEventListener("dblclick", function () {
                    if (viewMin === dataXMin && viewMax === dataXMax) {
                        return;
                    }
                    viewMin = dataXMin;
                    viewMax = dataXMax;
                    zoomHint.classList.remove("is-zoomed");
                    draw();
                });

                // Click-and-drag to pan once zoomed in — content follows
                // the cursor (drag right reveals what was off-screen to
                // the left), same convention most chart/map tools use.
                // mousemove/mouseup live on document, not the overlay: a
                // drag calls draw() on every step (to show the pan live),
                // which tears down and rebuilds this exact overlay, so a
                // listener attached to IT specifically would stop
                // receiving events mid-drag; document-level listeners
                // don't have that problem, and also let the drag continue
                // even if the cursor strays outside the small chart area.
                // Added only while a drag is active and removed the
                // moment it ends, so nothing accumulates across re-renders.
                function onDragMove(event) {
                    if (!isDragging) {
                        return;
                    }
                    const rect = svg.getBoundingClientRect();
                    const svgDeltaX = (event.clientX - dragStartClientX) / rect.width * width;
                    const msPerSvgUnit = (dragStartViewMax - dragStartViewMin) / plotW;
                    const deltaMs = svgDeltaX * msPerSvgUnit;
                    const span = dragStartViewMax - dragStartViewMin;
                    let newMin = dragStartViewMin - deltaMs;
                    let newMax = dragStartViewMax - deltaMs;
                    if (newMin < dataXMin) {
                        newMin = dataXMin;
                        newMax = newMin + span;
                    }
                    if (newMax > dataXMax) {
                        newMax = dataXMax;
                        newMin = newMax - span;
                    }
                    viewMin = newMin;
                    viewMax = newMax;
                    draw();
                }
                function onDragEnd() {
                    if (!isDragging) {
                        return;
                    }
                    isDragging = false;
                    document.removeEventListener("mousemove", onDragMove);
                    document.removeEventListener("mouseup", onDragEnd);
                    // Re-applies the cursor on whichever overlay is
                    // current (a drag's own onDragMove calls draw() on
                    // every step, so "this" draw()'s overlay may already
                    // be stale by the time the drag ends) — without this,
                    // the cursor would stay stuck on "grabbing" until
                    // something else happens to redraw the chart.
                    draw();
                }
                overlay.addEventListener("mousedown", function (event) {
                    // Only a plain, unmodified left-drag pans — ctrl/meta/
                    // shift-click stay free for whatever the browser or a
                    // future feature wants them for.
                    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey) {
                        return;
                    }
                    event.preventDefault();
                    isDragging = true;
                    dragStartClientX = event.clientX;
                    dragStartViewMin = viewMin;
                    dragStartViewMax = viewMax;
                    // Instant feedback — draw() only reapplies the cursor
                    // on its own next call (the first onDragMove), which
                    // could lag a real drag's first movement.
                    overlay.style.cursor = "grabbing";
                    document.addEventListener("mousemove", onDragMove);
                    document.addEventListener("mouseup", onDragEnd);
                });
            }

            draw();
        }

        // "System overview" — VRM's own Installation-data widget: one
        // Solar-yield bar per calendar day (left kWh axis) plus a Battery
        // SOC min-max band per day (right % axis). Static (no zoom/pan,
        // unlike renderLineChart) — each day is already one discrete bar,
        // not a dense time series, so there's nothing to zoom into.
        function renderDailyOverviewChart(container, rows) {
            const width = 640;
            const height = 170;
            const padding = { top: 10, right: 40, bottom: 26, left: 46 };
            const plotW = width - padding.left - padding.right;
            const plotH = height - padding.top - padding.bottom;
            container.innerHTML = "";

            const usableRows = (rows || []).filter(function (r) { return r && r.date; });
            if (!usableRows.length) {
                const empty = document.createElement("div");
                empty.className = "battery-chart-empty";
                empty.textContent = "No data for this window.";
                container.appendChild(empty);
                return;
            }

            const svgNS = "http://www.w3.org/2000/svg";
            const svg = document.createElementNS(svgNS, "svg");
            svg.setAttribute("viewBox", "0 0 " + width + " " + height);
            svg.setAttribute("class", "battery-chart-svg");
            svg.setAttribute("role", "img");
            svg.setAttribute(
                "aria-label",
                "Installation data: " + usableRows.length + " day(s), Solar kWh and Battery SOC %"
            );
            container.appendChild(svg);

            const kwhValues = usableRows.map(function (r) { return r.solar_kwh; }).filter(function (v) { return v != null; });
            const kwhMax = Math.max.apply(null, kwhValues.length ? kwhValues : [1]) * 1.15 || 1;

            const slotW = plotW / usableRows.length;
            function slotCenter(i) {
                return padding.left + slotW * (i + 0.5);
            }
            function yKwh(v) {
                return padding.top + plotH - (v / kwhMax) * plotH;
            }
            function ySoc(v) {
                return padding.top + plotH - (Math.max(0, Math.min(100, v)) / 100) * plotH;
            }

            // Solar bars first, same "Solar"/"Battery" legend colors as
            // VRM's own widget.
            const barW = Math.max(2, slotW * 0.55);
            usableRows.forEach(function (row, i) {
                if (row.solar_kwh == null) {
                    return;
                }
                const bar = document.createElementNS(svgNS, "rect");
                const y = yKwh(row.solar_kwh);
                bar.setAttribute("x", slotCenter(i) - barW / 2);
                bar.setAttribute("y", y);
                bar.setAttribute("width", barW);
                bar.setAttribute("height", Math.max(0, padding.top + plotH - y));
                bar.setAttribute("class", "daily-overview-solar-bar");
                svg.appendChild(bar);
            });

            // Battery SOC band drawn LAST (on top of the bars) — a
            // continuous ribbon across whichever days actually have SOC
            // data (a day with no reading just breaks the ribbon rather
            // than interpolating across a real gap, same reasoning
            // renderLineChart's own gap handling uses), so the line
            // reads as a continuous trend rather than getting broken up
            // by whichever bar happens to be tallest that day.
            let bandRun = [];
            function flushBand() {
                if (bandRun.length < 2) {
                    bandRun = [];
                    return;
                }
                const top = bandRun.map(function (p) { return p.x + "," + ySoc(p.max); });
                const bottom = bandRun.slice().reverse().map(function (p) { return p.x + "," + ySoc(p.min); });
                const band = document.createElementNS(svgNS, "polygon");
                band.setAttribute("points", top.concat(bottom).join(" "));
                band.setAttribute("class", "daily-overview-soc-band");
                svg.appendChild(band);
                const midLine = document.createElementNS(svgNS, "polyline");
                midLine.setAttribute(
                    "points",
                    bandRun.map(function (p) { return p.x + "," + ySoc((p.min + p.max) / 2); }).join(" ")
                );
                midLine.setAttribute("class", "daily-overview-soc-line");
                svg.appendChild(midLine);
                bandRun = [];
            }
            usableRows.forEach(function (row, i) {
                if (row.soc_min == null || row.soc_max == null) {
                    flushBand();
                    return;
                }
                bandRun.push({ x: slotCenter(i), min: row.soc_min, max: row.soc_max });
            });
            flushBand();

            // Day labels along the bottom — short "10 Sep" form, same as
            // the flap-timeline's own date formatting elsewhere.
            usableRows.forEach(function (row, i) {
                const label = document.createElementNS(svgNS, "text");
                const d = new Date(row.date + "T00:00:00Z");
                label.textContent = d.toLocaleDateString(undefined, { day: "numeric", month: "short", timeZone: "UTC" });
                label.setAttribute("x", slotCenter(i));
                label.setAttribute("y", height - 8);
                label.setAttribute("class", "battery-chart-axis-label");
                label.setAttribute("text-anchor", "middle");
                svg.appendChild(label);
            });

            // Left (kWh) and right (%) axis labels — just min/max/mid, not
            // a full tick ladder; this panel is read at a glance, not
            // zoomed into like the per-metric charts below it.
            [0, kwhMax].forEach(function (v) {
                const label = document.createElementNS(svgNS, "text");
                label.textContent = v.toFixed(1);
                label.setAttribute("x", padding.left - 6);
                label.setAttribute("y", yKwh(v) + (v === 0 ? 0 : 8));
                label.setAttribute("class", "battery-chart-axis-label");
                label.setAttribute("text-anchor", "end");
                svg.appendChild(label);
            });
            [0, 50, 100].forEach(function (v) {
                const label = document.createElementNS(svgNS, "text");
                label.textContent = v + "%";
                label.setAttribute("x", width - padding.right + 6);
                label.setAttribute("y", ySoc(v) + (v === 0 ? 0 : (v === 100 ? 8 : 4)));
                label.setAttribute("class", "battery-chart-axis-label");
                svg.appendChild(label);
            });

            const legend = document.createElement("div");
            legend.className = "daily-overview-legend";
            legend.innerHTML =
                '<span class="daily-overview-legend-item"><span class="daily-overview-legend-swatch is-solar"></span>Solar</span>'
                + '<span class="daily-overview-legend-item"><span class="daily-overview-legend-swatch is-battery"></span>Battery</span>';
            container.appendChild(legend);
        }

        function renderGraphs(data) {
            const modeConfig = GRAPH_MODES[graphsMode];
            graphsBody.innerHTML = "";
            modeConfig.order.forEach(function (key) {
                if (key === "system_overview") {
                    const rows = data.daily_overview || [];
                    if (!rows.length) {
                        return;
                    }
                    const overviewBlock = document.createElement("div");
                    overviewBlock.className = "battery-chart-block";
                    const overviewHeading = document.createElement("div");
                    overviewHeading.className = "battery-chart-heading";
                    const overviewTitle = document.createElement("span");
                    overviewTitle.textContent = "Installation data";
                    overviewHeading.appendChild(overviewTitle);
                    overviewBlock.appendChild(overviewHeading);
                    const overviewContainer = document.createElement("div");
                    overviewContainer.className = "battery-chart-container";
                    overviewBlock.appendChild(overviewContainer);
                    renderDailyOverviewChart(overviewContainer, rows);
                    graphsBody.appendChild(overviewBlock);
                    return;
                }
                const chart = (data.charts || {})[key];
                if (!chart) {
                    return;
                }
                const block = document.createElement("div");
                block.className = "battery-chart-block";
                const heading = document.createElement("div");
                heading.className = "battery-chart-heading";
                const title = document.createElement("span");
                title.textContent = chart.label
                    + (chart.latest != null ? " — " + chart.latest.toFixed(2) + " " + chart.unit + " now" : "");
                heading.appendChild(title);
                const range = document.createElement("span");
                range.className = "battery-chart-range";
                range.textContent = (chart.min != null && chart.max != null)
                    ? ("min " + chart.min.toFixed(2) + " / max " + chart.max.toFixed(2) + " " + chart.unit)
                    : "";
                heading.appendChild(range);
                block.appendChild(heading);
                if (!(chart.points || []).length) {
                    const empty = document.createElement("div");
                    empty.className = "battery-chart-empty";
                    empty.textContent = chart.error ? ("Unavailable: " + chart.error) : "No data for this window.";
                    block.appendChild(empty);
                } else {
                    const chartContainer = document.createElement("div");
                    chartContainer.className = "battery-chart-container";
                    block.appendChild(chartContainer);
                    renderLineChart(
                        chartContainer,
                        chart.points.map(function (p) { return { t: p.t, v: p.v }; }),
                        {
                            label: chart.label,
                            unit: chart.unit,
                            // SOC is the one metric here where a fixed
                            // reference line is defensible regardless of
                            // system (12V/24V/48V) — it's already a % of
                            // capacity. 20% is a conventional low-battery
                            // cutoff for lead/AGM and a conservative one for
                            // lithium, so it reads as "worth a look," not
                            // "definitely dying," on either chemistry.
                            thresholds: key === "soc" ? [{ value: 20, label: "20% low-battery reference" }] : [],
                            highlightRange: graphsHighlightRange,
                            markers: graphsMarkers,
                        }
                    );
                }
                graphsBody.appendChild(block);
            });
        }

        // Bumped on every loadGraphs() call and captured by each in-flight
        // request — a response only touches the DOM if it's still the
        // most recent request when it lands. Without this, closing the
        // modal for unit A (slow request still in flight) and opening it
        // for unit B (faster request) could let A's late response
        // silently overwrite B's just-rendered charts with no indication
        // anything went wrong. Caught in this session's own audit, not
        // reported live — fixing proactively.
        let graphsRequestSeq = 0;
        function loadGraphs() {
            const unit = graphsUnit;
            if (!unit) {
                return;
            }
            const requestSeq = ++graphsRequestSeq;
            const modeConfig = GRAPH_MODES[graphsMode];
            const hours = graphsHours.value || 24;
            graphsBody.innerHTML = "";
            const loading = document.createElement("div");
            loading.className = "battery-chart-empty";
            loading.textContent = modeConfig.loadingText;
            graphsBody.appendChild(loading);
            fetch(modeConfig.endpoint + encodeURIComponent(unit), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ hours: hours, subject: graphsSubject }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    if (requestSeq !== graphsRequestSeq) {
                        return;
                    }
                    graphsSubtitle.textContent = modeConfig.subtitle(graphsDisplayLabel || unit, data)
                        + " — last " + hours + " hour(s)";
                    renderGraphs(data);
                })
                .catch(function (error) {
                    if (requestSeq !== graphsRequestSeq) {
                        return;
                    }
                    graphsBody.innerHTML = "";
                    const errEl = document.createElement("div");
                    errEl.className = "battery-chart-empty";
                    errEl.textContent = modeConfig.failureLabel + " failed: " + (error.message || error);
                    graphsBody.appendChild(errEl);
                });
        }

        // Resolved/Worked/Skipped, when this modal was opened from a
        // ticket row that has them (currently just the Power vs Cell
        // Outage badge — see setGraphsRwsSource, called right after
        // openGraphsModal by openPowerVsCellRowDetail). graphsSourceEntry
        // is the SAME object reference renderList's own listState holds,
        // so mutating it here and re-rendering graphsSourceListId is
        // exactly what the row's own checkboxes do — no separate sync
        // path to keep correct.
        const graphsRwsRow = document.getElementById("graphs_rws_row");
        const graphsResolveBox = document.getElementById("graphs_resolve_box");
        const graphsWorkedBox = document.getElementById("graphs_worked_box");
        const graphsSkipBox = document.getElementById("graphs_skip_box");
        let graphsSourceEntry = null;
        let graphsSourceListId = null;

        function clearGraphsRwsSource() {
            graphsSourceEntry = null;
            graphsSourceListId = null;
            if (graphsRwsRow) {
                graphsRwsRow.hidden = true;
            }
        }

        function setGraphsRwsSource(entry, listId) {
            graphsSourceEntry = entry;
            graphsSourceListId = listId;
            if (!graphsRwsRow || !entry) {
                return;
            }
            graphsRwsRow.hidden = false;
            graphsResolveBox.checked = !!entry.resolved;
            graphsWorkedBox.checked = !!entry.worked;
            graphsSkipBox.checked = !!entry.skipped;
        }

        // Same choke point every row's own R/W/S handler ends on
        // (saveEntryState + re-render + the bulk-resolve button's count) —
        // see renderList's own resolveBox/workedBox/skipBox handlers.
        function afterGraphsRwsChange(entry) {
            saveEntryState(entry);
            if (graphsSourceListId) {
                renderList(graphsSourceListId);
            }
            updateResolveSelectedButton();
        }

        if (graphsResolveBox) {
            graphsResolveBox.addEventListener("change", function () {
                const entry = graphsSourceEntry;
                if (!entry) {
                    return;
                }
                entry.resolved = graphsResolveBox.checked;
                if (entry.resolved) {
                    entry.worked = false;
                    entry.skipped = false;
                    entry.isNew = false;
                    graphsWorkedBox.checked = false;
                    graphsSkipBox.checked = false;
                }
                afterGraphsRwsChange(entry);
            });
        }
        if (graphsWorkedBox) {
            graphsWorkedBox.addEventListener("change", function () {
                const entry = graphsSourceEntry;
                if (!entry) {
                    return;
                }
                entry.worked = graphsWorkedBox.checked;
                if (entry.worked) {
                    entry.resolved = false;
                    entry.skipped = false;
                    entry.isNew = false;
                    graphsResolveBox.checked = false;
                    graphsSkipBox.checked = false;
                }
                afterGraphsRwsChange(entry);
                pushTicketState(entry);
            });
        }
        if (graphsSkipBox) {
            graphsSkipBox.addEventListener("change", function () {
                const entry = graphsSourceEntry;
                if (!entry) {
                    return;
                }
                entry.skipped = graphsSkipBox.checked;
                if (entry.skipped) {
                    entry.resolved = false;
                    entry.worked = false;
                    entry.isNew = false;
                    graphsResolveBox.checked = false;
                    graphsWorkedBox.checked = false;
                }
                afterGraphsRwsChange(entry);
                pushTicketState(entry);
            });
        }

        // Reuses the Power vs Cell row badge already sitting in the row
        // (dataset.unit) to find it again, instead of holding a direct DOM
        // reference that a background poll's re-render could go stale —
        // Andrew's own request, 2026-09-22: closing the graph modal used
        // to drop you wherever the page happened to be scrolled, with no
        // way back to the row that opened it.
        function scrollToGraphsSourceRow() {
            if (!graphsSourceListId || !graphsSourceEntry || !graphsSourceEntry.unit) {
                return;
            }
            const listEl = document.getElementById(graphsSourceListId);
            if (!listEl) {
                return;
            }
            const unit = String(graphsSourceEntry.unit).toUpperCase();
            const badge = listEl.querySelector(
                '.power-vs-cell-row-badge[data-unit="' + unit + '"]'
            );
            const row = badge && badge.closest("li.ticket-row");
            if (!row) {
                return;
            }
            row.scrollIntoView({ behavior: "smooth", block: "center" });
            row.classList.add("just-viewed-row");
            window.setTimeout(function () {
                row.classList.remove("just-viewed-row");
            }, 2000);
        }

        // Same accordion sections (Open/Diagnostics/Router/Art/Switch/NUC/
        // Linux) and the same appendXCommandMenu builder functions as the
        // per-ticket command menu, just the subset that makes sense next
        // to a device/network graph (not Validate/Weather/Cameras/Set
        // Fields). Replaces the old flat Get ART Contacts/Open Mesh/Open
        // VRM button row — those three are reachable through Art/Open now,
        // collapsed by default instead of three always-visible buttons.
        // Andrew's own request, 2026-10-01.
        //
        // No entry is available in graphsUnit/graphsSubject alone (they're
        // bare strings — see openGraphsModal), so this fetches one fresh
        // via /issues/unit-context/<unit>, same call
        // ensureMultiUnitChooser's own unit-switch dropdown already makes
        // for exactly this reason (see loadUnitInto). The ticket subject
        // (when this graph was opened from one) is layered on top so
        // VRM/ERP resolution gets the more precise "RD####(MU####)"
        // context instead of the bare unit-context lookup's subject-less
        // fallback.
        let graphsDeviceMenuRequestId = 0;

        // Search box for the rail's command menus — the same
        // createCommandSearch the row menu uses. It sits outside
        // #graphs_device_menu (rebuilt on every load) and searches it.
        // Escape on an empty box is left alone, so it closes the modal.
        const graphsCommandSearch = graphsDeviceMenuEl
            ? createCommandSearch(function () { return graphsDeviceMenuEl; }, null)
            : null;
        if (graphsCommandSearch) {
            graphsDeviceMenuEl.parentNode.insertBefore(graphsCommandSearch.el, graphsDeviceMenuEl);
        }

        function renderGraphsDeviceMenu(entry) {
            if (!graphsDeviceMenuEl) {
                return;
            }
            graphsDeviceMenuEl.innerHTML = "";
            // Everything the row's quick menu has, so the modal is a
            // superset of it (Andrew's request, 2026-10-03: the unit button
            // opens this modal; the row's ▾ is just a shortcut).
            appendValidateCommandMenu(graphsDeviceMenuEl, entry);
            appendWeatherCommandMenu(graphsDeviceMenuEl, entry);
            appendCamerasCommandMenu(graphsDeviceMenuEl, entry);
            appendOpenCommandMenu(graphsDeviceMenuEl, entry);
            appendDiagnosticsCommandMenu(graphsDeviceMenuEl, entry);
            appendRouterCommandMenu(graphsDeviceMenuEl, entry);
            appendArtMenu(graphsDeviceMenuEl, entry);
            appendSwitchCommandMenu(graphsDeviceMenuEl, entry);
            // Set Fields acts on the ticket, so it uses the row's own entry
            // (issue id, list) — only when opened from a ticket row.
            if (graphsSourceEntry && graphsSourceListId) {
                appendSetFieldsCommandMenu(graphsDeviceMenuEl, graphsSourceEntry, graphsSourceListId);
            }
            appendLinuxCommandMenus(graphsDeviceMenuEl, entry); // NUC + Linux, each self-gated on entry
            // Typed before the menus finished loading? Apply it now.
            if (graphsCommandSearch && graphsCommandSearch.input.value) {
                graphsCommandSearch.refilter();
            }
        }

        function loadGraphsDeviceMenu(unit, subject) {
            if (!graphsDeviceMenuEl) {
                return;
            }
            const requestId = ++graphsDeviceMenuRequestId;
            graphsDeviceMenuEl.innerHTML = "";
            if (!unit) {
                return;
            }
            const hint = document.createElement("div");
            hint.className = "unit-tools-hint";
            hint.textContent = "Loading device menu...";
            graphsDeviceMenuEl.appendChild(hint);
            fetch("/issues/unit-context/" + encodeURIComponent(unit))
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    if (requestId !== graphsDeviceMenuRequestId) {
                        return; // modal moved on to a different unit/mode while this was in flight
                    }
                    const entry = makeListEntry(data);
                    entry.ticketSubject = subject || entry.ticketSubject;
                    renderGraphsDeviceMenu(entry);
                })
                .catch(function (error) {
                    if (requestId !== graphsDeviceMenuRequestId) {
                        return;
                    }
                    graphsDeviceMenuEl.innerHTML = "";
                    const err = document.createElement("div");
                    err.className = "unit-tools-hint";
                    err.textContent = "Could not load device menu: " + (error.message || error);
                    graphsDeviceMenuEl.appendChild(err);
                });
        }

        // The Power vs Cell finding, kept on screen in the modal header —
        // it used to live only in a toast that fades after 5s, while the
        // graph it explains stayed open. Badge + verdict in words + the
        // server's own summary; null hides it (every other opener).
        // Every verdict the check can return gets words and a glyph; only
        // power/cell get a status colour. tone picks the CSS class.
        const POWER_VS_CELL_VERDICT_DISPLAY = {
            power_outage: { glyph: "⚡", label: "Power outage", tone: "power_outage" },
            cell_outage: { glyph: "📶", label: "Cell outage", tone: "cell_outage" },
            inconclusive: { glyph: "?", label: "Inconclusive", tone: "none" },
            no_recent_outage: { glyph: "✓", label: "No recent outage", tone: "none" },
        };

        // Current site weather inside the verdict card (Andrew's request,
        // 2026-10-06): sun vs cloud is half of reading a power-vs-cell call
        // on a solar trailer. The icon carries data-unit like a row's
        // .wx-icon, so refreshTicketWeather fetches and fills it through
        // the same shared cache; applyWeatherToIcon then calls
        // renderGraphsWeatherText for the words. Shown only once weather
        // has actually arrived — an empty placeholder would read as "no
        // weather". The row keeps its own icon.
        const graphsWeatherWrapEl = document.getElementById("graphs_verdict_wx");
        const graphsWeatherIconEl = document.getElementById("graphs_wx_icon");
        const graphsWeatherTextEl = document.getElementById("graphs_wx_text");

        function renderGraphsWeatherText(data) {
            if (!graphsWeatherWrapEl || !data) {
                return;
            }
            graphsWeatherTextEl.textContent = [data.temperature_label, data.conditions]
                .filter(Boolean).join(" ");
            graphsWeatherWrapEl.title = graphsWeatherIconEl.title;
            graphsWeatherWrapEl.hidden = false;
        }

        function renderGraphsWeather(unit, subject) {
            if (!graphsWeatherWrapEl) {
                return;
            }
            graphsWeatherWrapEl.hidden = true;
            graphsWeatherTextEl.textContent = "";
            graphsWeatherIconEl.className = "wx-icon wx-pending";
            if (!unit) {
                delete graphsWeatherIconEl.dataset.unit;
                return;
            }
            graphsWeatherIconEl.dataset.unit = unit;
            graphsWeatherIconEl.dataset.subject = subject || "";
            const cached = weatherByUnit[unit];
            if (cached) {
                applyWeatherToIcon(graphsWeatherIconEl, cached);
                if (Date.now() - (cached._fetchedAt || 0) <= WEATHER_CACHE_MS) {
                    return;
                }
            }
            // Just this unit, not refreshTicketWeather: that batches every
            // row still waiting on weather, and the modal would sit blank
            // until the slowest of them resolved. Same endpoint and server
            // cache, so it costs Open-Meteo nothing extra.
            fetch("/issues/weather-bulk-units", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ units: [{ unit: unit, subject: subject || "" }] }),
            })
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    const payload = data && data.ok && (data.units || {})[unit];
                    if (!payload) {
                        return; // no resolvable GPS — leave the weather out
                    }
                    payload._fetchedAt = Date.now();
                    weatherByUnit[unit] = payload;
                    document.querySelectorAll('.wx-icon[data-unit="' + unit + '"]').forEach(function (el) {
                        applyWeatherToIcon(el, payload);
                    });
                })
                .catch(function () {});
        }

        if (graphsWeatherWrapEl) {
            graphsWeatherWrapEl.setAttribute("role", "button");
            graphsWeatherWrapEl.tabIndex = 0;
            const runGraphsWeather = function (event) {
                event.preventDefault();
                event.stopPropagation();
                if (graphsUnit) {
                    runGetWeatherForEntry({ unit: graphsUnit, ticketSubject: graphsSubject }, graphsWeatherIconEl);
                }
            };
            graphsWeatherWrapEl.addEventListener("click", runGraphsWeather);
            graphsWeatherWrapEl.addEventListener("keydown", function (event) {
                if (event.key === "Enter" || event.key === " ") {
                    runGraphsWeather(event);
                }
            });
        }

        // null/unknown hides the line (every opener but the row badge).
        function renderGraphsVerdict(info) {
            if (!graphsVerdictLineEl) {
                return;
            }
            const verdict = info && info.verdict;
            const display = POWER_VS_CELL_VERDICT_DISPLAY[verdict];
            if (!display) {
                graphsVerdictLineEl.hidden = true;
                graphsVerdictLineEl.className = "graphs-verdict";
                return;
            }
            graphsVerdictLineEl.hidden = false;
            graphsVerdictLineEl.className = "graphs-verdict is-" + display.tone;
            graphsVerdictBadgeEl.className = "graphs-verdict-badge is-" + display.tone;
            graphsVerdictBadgeEl.textContent = display.glyph;
            graphsVerdictLabelEl.textContent = display.label;
            if (graphsVerdictRecheckBtn) {
                graphsVerdictRecheckBtn.disabled = false;
            }
            // Short facts from the sweep's structured fields; the full
            // sentence-length summary stays one click (or hover) away.
            graphsVerdictFactsEl.innerHTML = "";
            graphsVerdictFactPieces(info).forEach(function (piece) {
                const fact = document.createElement("span");
                fact.className = "graphs-verdict-fact";
                fact.textContent = piece.text;
                fact.title = piece.title || "";
                graphsVerdictFactsEl.appendChild(fact);
            });
            graphsVerdictTextEl.textContent = info.summary || "";
            graphsVerdictTextEl.hidden = true;
            graphsVerdictMoreBtn.hidden = !info.summary;
            graphsVerdictMoreBtn.setAttribute("aria-expanded", "false");
            graphsVerdictMoreBtn.textContent = "Details";
            graphsVerdictLineEl.title = info.summary || "";
        }

        // The verdict line while a check is running ("pending") or after it
        // failed ("error"), with the message in words.
        function renderGraphsVerdictStatus(kind, message) {
            if (!graphsVerdictLineEl) {
                return;
            }
            graphsVerdictLineEl.hidden = false;
            graphsVerdictLineEl.className = "graphs-verdict is-" + kind;
            graphsVerdictBadgeEl.className = "graphs-verdict-badge is-none";
            graphsVerdictBadgeEl.textContent = kind === "pending" ? "∿" : "!";
            graphsVerdictLabelEl.textContent = kind === "pending" ? "Checking…" : "Check failed";
            graphsVerdictFactsEl.innerHTML = "";
            const fact = document.createElement("span");
            fact.className = "graphs-verdict-fact";
            fact.textContent = message;
            graphsVerdictFactsEl.appendChild(fact);
            graphsVerdictTextEl.hidden = true;
            graphsVerdictTextEl.textContent = "";
            graphsVerdictMoreBtn.hidden = true;
            graphsVerdictLineEl.title = message;
            if (graphsVerdictRecheckBtn) {
                graphsVerdictRecheckBtn.disabled = kind === "pending";
            }
        }

        // "09-26 16:55" in the browser's local time — short enough for a chip.
        function shortStamp(ms) {
            const d = new Date(ms);
            const pad = function (n) { return String(n).padStart(2, "0"); };
            return pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
        }

        function graphsVerdictFactPieces(info) {
            const pieces = [];
            if (info.loss_window_start != null && info.loss_window_end != null) {
                const startMs = info.loss_window_start * 1000;
                const endMs = info.loss_window_end * 1000;
                // A sub-minute window would read "08:43 → 08:43 (0m)".
                pieces.push({
                    text: endMs - startMs < 60000
                        ? "Loss at " + shortStamp(startMs) + " (under 1m)"
                        : "Loss " + shortStamp(startMs) + " → " + shortStamp(endMs)
                            + " (" + formatUptimeDuration((endMs - startMs) / 1000) + ")",
                    title: "The loss window this verdict is based on (shaded on the graphs).",
                });
            }
            if (info.ticket_created_at != null) {
                pieces.push({
                    text: "Ticket " + formatAgeShort(Date.now() / 1000 - info.ticket_created_at) + " old",
                    title: "Ticket opened " + new Date(info.ticket_created_at * 1000).toLocaleString(),
                });
            }
            return pieces;
        }

        if (graphsVerdictMoreBtn) {
            graphsVerdictMoreBtn.addEventListener("click", function () {
                const open = graphsVerdictTextEl.hidden;
                graphsVerdictTextEl.hidden = !open;
                graphsVerdictMoreBtn.setAttribute("aria-expanded", open ? "true" : "false");
                graphsVerdictMoreBtn.textContent = open ? "Hide details" : "Details";
            });
        }

        // ---- Output pane -----------------------------------------------------
        // What the buttons you press in this modal print, so you don't have
        // to close it to read the main Stdout behind it. Fed by the
        // consoleLines.push hook near the top (graphsConsoleEcho). Cleared
        // each time the modal opens; capped so a long ping can't grow it
        // forever.
        const graphsConsoleWrapEl = document.getElementById("graphs_console_wrap");
        const graphsConsoleEl = document.getElementById("graphs_console");
        const graphsConsoleClearBtn = document.getElementById("graphs_console_clear");
        const GRAPHS_CONSOLE_MAX_LINES = 500;
        const graphsConsoleLines = [];
        let graphsConsoleRenderQueued = false;

        function renderGraphsConsole() {
            graphsConsoleRenderQueued = false;
            if (!graphsConsoleEl) {
                return;
            }
            // Follow the bottom unless the tech has scrolled up to read.
            const atBottom = graphsConsoleEl.scrollHeight - graphsConsoleEl.scrollTop - graphsConsoleEl.clientHeight < 24;
            graphsConsoleEl.textContent = graphsConsoleLines.join("\n");
            graphsConsoleWrapEl.hidden = graphsConsoleLines.length === 0;
            if (atBottom) {
                graphsConsoleEl.scrollTop = graphsConsoleEl.scrollHeight;
            }
        }

        function clearGraphsConsole() {
            graphsConsoleLines.length = 0;
            renderGraphsConsole();
        }

        graphsConsoleEcho = function (lines) {
            if (!graphsModal.classList.contains("is-open")) {
                return;
            }
            Array.prototype.forEach.call(lines, function (line) {
                graphsConsoleLines.push(String(line));
            });
            if (graphsConsoleLines.length > GRAPHS_CONSOLE_MAX_LINES) {
                graphsConsoleLines.splice(0, graphsConsoleLines.length - GRAPHS_CONSOLE_MAX_LINES);
            }
            // Batch: actions often push several lines then renderConsole().
            if (!graphsConsoleRenderQueued) {
                graphsConsoleRenderQueued = true;
                window.requestAnimationFrame(renderGraphsConsole);
            }
        };

        if (graphsConsoleClearBtn) {
            graphsConsoleClearBtn.addEventListener("click", clearGraphsConsole);
        }

        // ---- Stats strip ----------------------------------------------------
        // Small status chips under the uptime line. Each is shown only when
        // it has something to say, and each carries words + a glyph, not
        // just a colour. Everything here is data the dashboard already has
        // or already fetches for this modal — no new checks.
        function setGraphsChip(el, text, tier, title) {
            if (!el) {
                return;
            }
            if (!text) {
                el.hidden = true;
                return;
            }
            el.hidden = false;
            el.textContent = text;
            el.className = "graphs-chip is-" + tier + (el === graphsFlapChipEl ? " graphs-flap-chip" : "");
            el.title = title || "";
        }

        function resetGraphsStats() {
            [graphsAlarmChipEl, graphsPlugChipEl, graphsVrmChipEl, graphsFlapChipEl].forEach(function (el) {
                if (el) {
                    el.hidden = true;
                }
            });
        }

        // Active Zabbix/VRM alert — the fleet poll's cache, so free to read.
        function renderGraphsAlarmChip(unit) {
            const key = String(unit || "").toUpperCase();
            const info = powerInfraAlarmedUnits[key];
            setGraphsChip(graphsAlarmChipEl, info ? "⚠ Active alert" : "", "danger",
                info ? powerInfraAlertSummaryText(key, info) : "");
        }

        // AC power + VRM freshness ride on the /issues/power-status
        // response loadGraphsBatteryLine already fetches for the battery %.
        // Same "only the two real verdicts" rule as the command menu's plug
        // glyph (POWER_GLYPH_VISIBLE_STATUSES).
        function renderGraphsPowerChips(data) {
            const status = data && data.ac_power_status;
            if (status === "present") {
                setGraphsChip(graphsPlugChipEl, "🔌 AC power on", "ok", data.summary || "");
            } else if (status === "not_detected") {
                setGraphsChip(graphsPlugChipEl, "🔌 No AC power", "warn", data.summary || "");
            } else {
                setGraphsChip(graphsPlugChipEl, "");
            }
            const freshness = data && data.vrm_freshness;
            if (freshness === "stale" || freshness === "disconnected") {
                const age = data.vrm_last_seen_seconds_ago != null
                    ? " (" + formatAgeShort(data.vrm_last_seen_seconds_ago) + " old)" : "";
                setGraphsChip(graphsVrmChipEl, "VRM " + freshness, "warn",
                    "VRM data is " + freshness + age + " — battery/AC readings may be out of date.");
            } else {
                setGraphsChip(graphsVrmChipEl, "");
            }
        }

        // Validation-history flaps over the last FLAP_ROW_DAYS — the same
        // /issues/unit-history read and cache the command menu's flap row
        // uses, drawn as a chip plus the same little timeline bar.
        let graphsFlapRequestId = 0;

        function renderGraphsFlapChip(summary) {
            if (!graphsFlapChipEl) {
                return;
            }
            if (!summary || !summary.checks) {
                setGraphsChip(graphsFlapChipEl, "");
                return;
            }
            const flapping = summary.transitions >= FLAP_ROW_MIN_TRANSITIONS;
            const label = flapping
                ? "↯ Flapping · " + summary.transitions + " flips / " + FLAP_ROW_DAYS + "d"
                : "✓ Steady · " + summary.transitions + " flip" + (summary.transitions === 1 ? "" : "s") + " / " + FLAP_ROW_DAYS + "d";
            setGraphsChip(graphsFlapChipEl, label, flapping ? "warn" : "idle",
                summary.down_checks + " of " + summary.checks + " checks down in the last " + FLAP_ROW_DAYS
                + " days (this dashboard's own validations). Last check " + (summary.last_seen || "unknown") + ".");
            graphsFlapChipEl.appendChild(renderFlapTimelineBar(summary.timeline, FLAP_ROW_DAYS));
        }

        function loadGraphsFlapChip(unit) {
            const requestId = ++graphsFlapRequestId;
            const key = String(unit || "").toUpperCase();
            if (!key) {
                return;
            }
            const cached = flapRowCache[key];
            if (cached && (Date.now() - cached.fetchedAt) < FLAP_ROW_CACHE_MS) {
                renderGraphsFlapChip(cached.summary);
                return;
            }
            fetch("/issues/unit-history/" + encodeURIComponent(key) + "?days=" + FLAP_ROW_DAYS + "&limit=1")
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    flapRowCache[key] = { summary: (data && data.ok) ? data.summary : null, fetchedAt: Date.now() };
                })
                .catch(function () {
                    flapRowCache[key] = { summary: null, fetchedAt: Date.now() };
                })
                .finally(function () {
                    if (requestId === graphsFlapRequestId) {
                        renderGraphsFlapChip(flapRowCache[key].summary);
                    }
                });
        }

        // Outage/recovery email indicator. Reads the server's cached result
        // of the hourly Recovery Email Check (/issues/recovery-email-status),
        // so opening the modal costs one small GET. Every state carries a
        // glyph and words, not just a colour. Clicking re-runs the whole
        // check (it pings every unit on the ART report, so it takes a few
        // minutes) and polls until it finishes.
        const graphsEmailStatusEl = document.getElementById("graphs_email_status");
        const RECOVERY_EMAIL_STATUS_DISPLAY = {
            needs_initial_email: {
                text: "✉ Outage email needed", tier: "danger",
                detail: "Unit is down and no outage email has been sent.",
            },
            needs_recovery_email: {
                text: "✉ Recovery email needed", tier: "warn",
                detail: "Outage email was sent and the unit is back up — send the recovery email.",
            },
            potential_false_positive: {
                text: "? No emails · unit back up", tier: "alert",
                detail: "No outage or recovery email was sent, and the unit is back up — possibly a false positive.",
            },
            pending_recovery: {
                text: "✉ Outage sent · awaiting recovery", tier: "idle",
                detail: "Outage email was sent; the unit isn't back up yet, so no recovery email is due.",
            },
            email_status_up_to_date: {
                text: "✓ Emails sent", tier: "ok",
                detail: "Outage and recovery emails have both been sent.",
            },
        };
        const RECOVERY_EMAIL_POLL_MS = 10 * 1000;
        const RECOVERY_EMAIL_POLL_GIVE_UP_MS = 20 * 60 * 1000;
        let graphsEmailRequestId = 0;
        let graphsEmailPollTimer = null;

        function setGraphsEmailPill(text, tier, title) {
            graphsEmailStatusEl.hidden = false;
            graphsEmailStatusEl.textContent = text;
            graphsEmailStatusEl.className = "graphs-email-status is-" + tier;
            graphsEmailStatusEl.title = title;
        }

        function renderGraphsEmailStatus(unit, data) {
            if (!graphsEmailStatusEl) {
                return;
            }
            const key = String(unit || "").toUpperCase();
            if (!data || !key) {
                graphsEmailStatusEl.hidden = true;
                return;
            }
            const checkedText = data.checked_at
                ? "Checked " + new Date(data.checked_at * 1000).toLocaleString() + " (runs hourly)"
                : "";
            const errorText = data.error ? "Last check failed: " + data.error : "";
            const recheckText = "Click to re-run the check now (pings every unit on the ART report, takes a few minutes).";
            graphsEmailStatusEl.disabled = !!data.running;
            if (data.running && !(data.by_unit || {})[key]) {
                setGraphsEmailPill("✉ Checking email status...", "idle",
                    "Recovery email check is running." + (checkedText ? "\n" + checkedText : ""));
                return;
            }
            const info = (data.by_unit || {})[key];
            if (!info) {
                if (!data.checked_at) {
                    // Never completed a check: say so, rather than staying
                    // silent, which would read as "no email needed".
                    setGraphsEmailPill(
                        data.error ? "✉ Email check failed" : "✉ Email status not checked yet",
                        "idle",
                        (errorText || "The recovery email check hasn't run since the service started.")
                            + "\n" + recheckText
                    );
                    return;
                }
                // Checked, and this unit isn't on the outage report at all.
                graphsEmailStatusEl.hidden = true;
                return;
            }
            const display = RECOVERY_EMAIL_STATUS_DISPLAY[info.status];
            if (!display) {
                graphsEmailStatusEl.hidden = true;
                return;
            }
            const lines = [display.detail];
            if (info.subject) {
                lines.push("Ticket: " + info.subject + (info.issue_id ? " (" + info.issue_id + ")" : ""));
            }
            if (checkedText) {
                lines.push(checkedText);
            }
            if (errorText) {
                lines.push(errorText + " — showing the last good result.");
            }
            lines.push(data.running ? "Re-check running..." : recheckText);
            setGraphsEmailPill(display.text + (data.running ? " ⟳" : ""), display.tier, lines.join("\n"));
        }

        function fetchRecoveryEmailStatus() {
            return fetch("/issues/recovery-email-status").then(function (response) {
                return response.json().then(function (data) {
                    if (!response.ok || !data.ok) {
                        throw new Error(data.error || ("HTTP " + response.status));
                    }
                    rememberRecoveryEmailStatus(data);
                    return data;
                });
            });
        }

        // ---- Row ✉ glyph ------------------------------------------------------
        // The same status on the ticket row's unit button, so a unit that
        // needs an email is visible without opening the modal (Andrew's
        // request, 2026-10-06). Alert-only like the shading/dead-panel
        // glyphs: shown just for the three states where something has to be
        // sent; "awaiting recovery" and "emails sent" stay modal-only. The
        // suffix (! / ?) says which state it is, so it never rests on colour.
        // Click opens the ERP ticket the email belongs on, which is the ART
        // report's ticket and not always the row's own (RD3083, 2026-10-06).
        const RECOVERY_EMAIL_ROW_GLYPH = {
            needs_initial_email: { text: "✉!", tier: "danger" },
            needs_recovery_email: { text: "✉", tier: "warn" },
            potential_false_positive: { text: "✉?", tier: "alert" },
        };
        const RECOVERY_EMAIL_ROW_POLL_MS = 5 * 60 * 1000;
        let recoveryEmailRowStatus = null;

        function rememberRecoveryEmailStatus(data) {
            // A check that has never finished has nothing to show; keep
            // whatever the last good result was.
            if (!data || !data.by_unit || !data.checked_at) {
                return;
            }
            recoveryEmailRowStatus = data;
            document.querySelectorAll(".unit-email-glyph").forEach(applyRowEmailGlyph);
        }

        function applyRowEmailGlyph(el) {
            const unit = String(el.dataset.unit || "").toUpperCase();
            const info = recoveryEmailRowStatus && unit ? recoveryEmailRowStatus.by_unit[unit] : null;
            const glyph = info && RECOVERY_EMAIL_ROW_GLYPH[info.status];
            if (!glyph) {
                el.hidden = true;
                el.dataset.url = "";
                return;
            }
            const display = RECOVERY_EMAIL_STATUS_DISPLAY[info.status];
            el.hidden = false;
            el.textContent = glyph.text;
            el.className = "unit-email-glyph is-" + glyph.tier;
            el.dataset.url = info.url || "";
            const lines = [display.text.replace(/^\S+\s/, "") + " — " + display.detail];
            if (info.subject) {
                lines.push("Ticket: " + info.subject + (info.issue_id ? " (" + info.issue_id + ")" : ""));
            }
            if (recoveryEmailRowStatus.checked_at) {
                lines.push("Checked " + new Date(recoveryEmailRowStatus.checked_at * 1000).toLocaleString() + " (runs hourly)");
            }
            lines.push(info.url ? "(click to open that ticket in ERP)" : "(click to open the unit)");
            el.title = lines.join("\n");
        }

        function pollRecoveryEmailStatusForRows() {
            fetchRecoveryEmailStatus()
                .catch(function () {})
                .finally(function () {
                    window.setTimeout(pollRecoveryEmailStatusForRows, RECOVERY_EMAIL_ROW_POLL_MS);
                });
        }
        pollRecoveryEmailStatusForRows();

        function stopGraphsEmailPoll() {
            if (graphsEmailPollTimer) {
                window.clearTimeout(graphsEmailPollTimer);
                graphsEmailPollTimer = null;
            }
        }

        function loadGraphsEmailStatus(unit) {
            stopGraphsEmailPoll();
            const requestId = ++graphsEmailRequestId;
            if (!graphsEmailStatusEl) {
                return;
            }
            graphsEmailStatusEl.hidden = true;
            if (!unit) {
                return;
            }
            fetchRecoveryEmailStatus()
                .then(function (data) {
                    if (requestId !== graphsEmailRequestId) {
                        return;
                    }
                    renderGraphsEmailStatus(unit, data);
                    if (data.running) {
                        pollGraphsEmailStatus(unit, requestId, Date.now());
                    }
                })
                .catch(function () {
                    if (requestId !== graphsEmailRequestId) {
                        return;
                    }
                    graphsEmailStatusEl.hidden = true;
                });
        }

        // Re-reads the cache until the running check finishes, only while
        // the modal is still showing the same unit (requestId bumps on
        // every open and on close).
        function pollGraphsEmailStatus(unit, requestId, startedMs) {
            stopGraphsEmailPoll();
            graphsEmailPollTimer = window.setTimeout(function () {
                graphsEmailPollTimer = null;
                if (requestId !== graphsEmailRequestId) {
                    return;
                }
                fetchRecoveryEmailStatus()
                    .then(function (data) {
                        if (requestId !== graphsEmailRequestId) {
                            return;
                        }
                        renderGraphsEmailStatus(unit, data);
                        if (data.running && Date.now() - startedMs < RECOVERY_EMAIL_POLL_GIVE_UP_MS) {
                            pollGraphsEmailStatus(unit, requestId, startedMs);
                            return;
                        }
                        if (!data.running) {
                            const info = (data.by_unit || {})[String(unit).toUpperCase()];
                            const display = info && RECOVERY_EMAIL_STATUS_DISPLAY[info.status];
                            consoleLines.push("Recovery email check finished — " + unit + ": "
                                + (data.error ? "check failed: " + data.error
                                    : display ? display.text : "not on the outage report"));
                            renderConsole(true);
                        }
                    })
                    .catch(function () {
                        if (requestId === graphsEmailRequestId) {
                            pollGraphsEmailStatus(unit, requestId, startedMs);
                        }
                    });
            }, RECOVERY_EMAIL_POLL_MS);
        }

        if (graphsEmailStatusEl) {
            graphsEmailStatusEl.addEventListener("click", function () {
                const unit = graphsUnit;
                const requestId = graphsEmailRequestId;
                if (!unit || graphsEmailStatusEl.disabled) {
                    return;
                }
                graphsEmailStatusEl.disabled = true;
                fetch("/issues/recovery-email-status/refresh", { method: "POST" })
                    .then(function (response) { return response.json(); })
                    .then(function (data) {
                        if (!data || !data.ok) {
                            throw new Error((data && data.error) || "refresh failed");
                        }
                        consoleLines.push(data.started
                            ? "Recovery email check started — pings every unit on the ART report, a few minutes."
                            : "Recovery email check already running — waiting for it to finish.");
                        renderConsole(true);
                        statusEl.textContent = "Recovery email check running...";
                        if (requestId !== graphsEmailRequestId) {
                            return;
                        }
                        graphsEmailStatusEl.textContent = graphsEmailStatusEl.textContent.replace(/ ⟳$/, "") + " ⟳";
                        pollGraphsEmailStatus(unit, requestId, Date.now());
                    })
                    .catch(function (error) {
                        graphsEmailStatusEl.disabled = false;
                        notify("Could not start the recovery email check: "
                            + ((error && error.message) || error) + ". Try again, or use the Recovery Email Check page.", "error");
                    });
            });
        }

        // The rail's notes box, built lazily on first open and reused —
        // reloaded only when the unit changes, so reopening the same unit
        // keeps any unsaved text instead of refetching over it.
        const graphsNotesEl = document.getElementById("graphs_notes");
        let graphsNotesBox = null;

        function loadGraphsNotes(unit) {
            if (!graphsNotesEl) {
                return;
            }
            graphsNotesEl.hidden = !unit;
            if (!unit) {
                return;
            }
            if (!graphsNotesBox) {
                graphsNotesBox = createUnitNotesBox();
                graphsNotesEl.appendChild(graphsNotesBox);
            }
            if (graphsNotesBox.dataset.unit !== unit) {
                loadUnitNote(graphsNotesBox, unit);
            }
        }

        function renderGraphsInfoLine() {
            graphsInfoLineEl.textContent = graphsInfoLine || "";
            graphsInfoLineEl.hidden = !graphsInfoLine;
        }

        // Exact same pill as the command menu's own battery glyph — same
        // classes, same batterySocTier 4-tier scale, same "click to open
        // VRM" — just driven by a direct fetch here instead of the cached
        // checkAndApplyPowerGlyph machinery, since this modal has no
        // commandMenu element for that to key off of.
        function renderGraphsBatteryGlyph(percent) {
            if (!graphsBatteryGlyphEl) {
                return;
            }
            if (percent == null) {
                graphsBatteryGlyphEl.hidden = true;
                return;
            }
            const tier = batterySocTier(percent);
            graphsBatteryGlyphEl.hidden = false;
            graphsBatteryGlyphEl.className = "command-battery-glyph is-" + tier;
            graphsBatteryGlyphEl.textContent = Math.round(percent) + "%";
            graphsBatteryGlyphEl.title = "Battery " + percent.toFixed(0) + "% (" + tier.replace("-", " ") + ")\n(click to open VRM)";
        }

        function loadGraphsBatteryLine(unit) {
            const requestId = ++graphsBatteryRequestId;
            fetch("/issues/power-status/" + encodeURIComponent(unit), { method: "POST" })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    if (requestId !== graphsBatteryRequestId) {
                        return; // modal moved on to a different unit/mode while this was in flight
                    }
                    // "When available" — plenty of real installations report
                    // battery voltage/current but no percentage SOC at all
                    // (a Hub-1/Cerbo GX combo) — same convention as the
                    // command-menu's own battery glyph (applyBatteryGlyphFromCache).
                    renderGraphsBatteryGlyph(data.battery_soc_percent);
                    renderGraphsPowerChips(data);
                })
                .catch(function () {
                    if (requestId !== graphsBatteryRequestId) {
                        return;
                    }
                    renderGraphsBatteryGlyph(null);
                    renderGraphsPowerChips(null);
                });
        }

        // Picks the smallest Window option that reaches back to the earliest
        // highlight/marker (or the widest available if none does). With
        // onlyWiden, never shrinks a window the tech already widened — used
        // when a verdict lands after the modal is already open.
        function widenGraphsWindowToCover(modeConfig, onlyWiden) {
            if (!graphsHighlightRange && !graphsMarkers.length) {
                return;
            }
            const earliestMs = Math.min(
                graphsHighlightRange ? graphsHighlightRange.startMs : Infinity,
                graphsMarkers.length
                    ? Math.min.apply(null, graphsMarkers.map(function (m) { return m.tMs; }))
                    : Infinity
            );
            const neededHours = Math.ceil((Date.now() - earliestMs) / 3600000) + 2;
            const covering = modeConfig.hoursOptions
                .filter(function (opt) { return Number(opt.value) >= neededHours; })
                .sort(function (a, b) { return Number(a.value) - Number(b.value); })[0];
            const widest = modeConfig.hoursOptions
                .slice()
                .sort(function (a, b) { return Number(b.value) - Number(a.value); })[0];
            const target = covering || widest;
            if (!target) {
                return;
            }
            if (onlyWiden && Number(target.value) <= Number(graphsHours.value)) {
                return;
            }
            graphsHours.value = String(target.value);
        }

        function openGraphsModal(unit, mode, subject, highlightRange, displayLabel, markers, infoLine, ticketUrl) {
            clearGraphsRwsSource();
            graphsMode = GRAPH_MODES[mode] ? mode : "battery";
            const modeConfig = GRAPH_MODES[graphsMode];
            graphsUnit = unit || "";
            graphsSubject = subject || "";
            graphsHighlightRange = highlightRange || null;
            graphsDisplayLabel = displayLabel || null;
            // Tolerates a single marker object (every caller before this
            // one passed one) or an array of them.
            graphsMarkers = (Array.isArray(markers) ? markers : (markers ? [markers] : [])).filter(Boolean);
            graphsInfoLine = infoLine || null;
            renderGraphsVerdict(null);
            // Only the row badge (openPowerVsCellRowDetail) sets these back.
            graphsPowerVsCellContext = null;
            graphsUnitSwitchState = null;
            if (graphsUnitSwitchEl) {
                graphsUnitSwitchEl.hidden = true;
                graphsUnitSwitchEl.innerHTML = "";
            }
            graphsPowerVsCellRequestId += 1;
            if (graphsVerdictRecheckBtn) {
                graphsVerdictRecheckBtn.hidden = true;
            }
            renderGraphsBatteryGlyph(null);
            resetGraphsStats();
            renderGraphsAlarmChip(unit);
            loadGraphsFlapChip(unit);
            clearGraphsConsole();
            // Bump regardless of mode so an in-flight fetch from whatever
            // was open before this can't land its battery glyph here after
            // the fact (e.g. a quick network -> battery -> network re-open).
            graphsBatteryRequestId += 1;
            renderGraphsInfoLine();
            // Reset every open, not just power-vs-cell's — a stale is-warn/
            // is-danger tier from a previous power-vs-cell open must not
            // leak into an unrelated shading/dead-panel graph that reuses
            // this same element right after.
            graphsInfoLineEl.className = "graphs-info-line";
            graphsTicketLinkEl.href = ticketUrl || "#";
            graphsTicketLineEl.hidden = !ticketUrl;
            graphsTitle.firstChild.textContent = modeConfig.titleText + " ";
            graphsSubtitle.textContent = graphsDisplayLabel || unit || "";
            const previousValue = graphsHours.value;
            graphsHours.innerHTML = "";
            modeConfig.hoursOptions.forEach(function (opt) {
                const optionEl = document.createElement("option");
                optionEl.value = opt.value;
                optionEl.textContent = opt.label;
                graphsHours.appendChild(optionEl);
            });
            // Keep the previously-picked window when the new mode still
            // offers it (e.g. switching graph types without losing "7 days"),
            // otherwise fall back to the mode's first/default option.
            if (modeConfig.hoursOptions.some(function (opt) { return String(opt.value) === previousValue; })) {
                graphsHours.value = previousValue;
            }
            // A highlight (or marker) from hours/days ago is useless if the
            // default window doesn't even reach back that far — widen to
            // the smallest option that covers the EARLIEST of them all
            // (they can be far apart — see openPowerVsCellRowDetail, where
            // the switch's own reboot and the ticket's own creation time
            // can each land days from the loss window they're being
            // compared against), or the widest available if none do.
            widenGraphsWindowToCover(modeConfig, false);
            // A snapshot from the surrounding cameras (not fisheye) is how
            // a tech visually confirms the cloud cover behind either a
            // "power outage" verdict (network mode) or a shading/dead-panel
            // one (battery mode) — shown in both, right where that verdict
            // is already on screen.
            graphs360Btn.hidden = false;
            loadGraphsNotes(graphsUnit);
            loadGraphsEmailStatus(graphsUnit);
            renderGraphsWeather(graphsUnit, graphsSubject);
            if (graphsCommandSearch) {
                graphsCommandSearch.clear();
            }
            loadGraphsDeviceMenu(graphsUnit, graphsSubject);
            // Only network mode ever shows switch uptime in the info line
            // (openPowerVsCellRowDetail and the plain Network Latency
            // Graphs button are its only two callers) — reset here every
            // open so a leftover shading/dead-panel infoLine from a
            // previous open can't leave the refresh button visible next to
            // unrelated text.
            graphsUptimeRefreshBtn.hidden = graphsMode !== "network";
            // VRM battery % pill alongside the switch-uptime info line,
            // same "cell vs power outage" context and same network-mode-
            // only scope as the uptime line/refresh button right above —
            // see loadGraphsBatteryLine/renderGraphsBatteryGlyph. Stays
            // hidden when VRM has no reading for this unit.
            if (graphsMode === "network" && graphsUnit) {
                loadGraphsBatteryLine(graphsUnit);
            }
            // Network mode only ("cell vs power outage") — Andrew's own
            // request, 2026-09-28: whether a storm was rolling through is
            // exactly the context a power-outage-vs-cell-outage verdict
            // benefits from, not something every graph mode needs.
            if (graphsForecastGlyphEl) {
                if (graphsMode === "network") {
                    applyGraphsForecastGlyph(graphsUnit, graphsSubject);
                } else {
                    graphsForecastGlyphEl.hidden = true;
                }
            }
            graphsModal.classList.add("is-open");
            // Ready to type a command straight away (Andrew's request,
            // 2026-10-02). After is-open, since a hidden input can't take
            // focus. Escape on the empty box still closes the modal.
            if (graphsCommandSearch) {
                graphsCommandSearch.input.focus({ preventScroll: true });
            }
            loadGraphs();
        }

        function closeGraphsModal() {
            graphsModal.classList.remove("is-open");
            // Bumping the ids stops any email-status poll for this unit and
            // drops a Power vs Cell result still in flight.
            graphsEmailRequestId += 1;
            graphsPowerVsCellRequestId += 1;
            stopGraphsEmailPoll();
            // Drop the modal's weather icon out of the bulk refresh.
            renderGraphsWeather("");
            scrollToGraphsSourceRow();
            clearGraphsRwsSource();
        }

        // ART report 152 (Site Contacts) in an easy-copy-paste popup — the
        // Art -> "Get site contacts" button still logs to stdout, but
        // reaching for contacts usually means pasting them straight into
        // an email or a ticket note, so the same rows also land in a
        // pre-selected textarea. Copy uses execCommand rather than
        // navigator.clipboard because the dashboard is served over plain
        // http on a LAN IP, which isn't a secure context.
        const siteContactsModal = document.getElementById("site_contacts_modal");
        const siteContactsTitleEl = document.getElementById("site_contacts_title");
        const siteContactsRowsEl = document.getElementById("site_contacts_rows");
        const siteContactsCopiedEl = document.getElementById("site_contacts_copied");
        const siteContactsCopyBtn = document.getElementById("site_contacts_copy");
        const siteContactsCloseBtn = document.getElementById("site_contacts_close");
        const SITE_CONTACT_EMAIL_RE = /[A-Z0-9._%+'-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;
        let siteContactsFullText = "";
        let siteContactsCopiedTimer = null;

        // Plain-text copy through the copy event, same reason as the image
        // copies above: plain http on a LAN IP has no navigator.clipboard.
        // Needs a user gesture (a click/double-click/key press) to work.
        function copyPlainText(text) {
            let wrote = false;
            function onCopy(event) {
                event.preventDefault();
                event.clipboardData.setData("text/plain", text);
                wrote = true;
            }
            document.addEventListener("copy", onCopy, true);
            try {
                document.execCommand("copy");
            } catch (ignore) {
                wrote = false;
            } finally {
                document.removeEventListener("copy", onCopy, true);
            }
            return wrote;
        }

        function showSiteContactsCopied(message, ok) {
            siteContactsCopiedEl.textContent = message;
            siteContactsCopiedEl.classList.toggle("is-error", !ok);
            if (siteContactsCopiedTimer) {
                window.clearTimeout(siteContactsCopiedTimer);
            }
            siteContactsCopiedTimer = window.setTimeout(function () {
                siteContactsCopiedEl.textContent = "";
            }, 4000);
        }

        // Comma-separated, never semicolons: the addresses get pasted into
        // Frappe/ERP's send-email To/CC fields, which split on commas and
        // break on ";" (Andrew, 2026-10-05).
        function copySiteContactEmails(row, emails) {
            const ok = copyPlainText(emails.join(", "));
            const selection = window.getSelection && window.getSelection();
            if (selection) {
                selection.removeAllRanges(); // a double-click also selects a word
            }
            if (ok) {
                row.classList.add("just-copied");
                window.setTimeout(function () { row.classList.remove("just-copied"); }, 1200);
                showSiteContactsCopied("Copied " + emails.length + " email"
                    + (emails.length === 1 ? "" : "s") + " (" + row.dataset.label + ")", true);
            } else {
                showSiteContactsCopied("Copy was blocked by the browser — select the addresses and press Ctrl+C", false);
            }
        }

        function siteContactRow(line) {
            const emails = line.match(SITE_CONTACT_EMAIL_RE) || [];
            if (!emails.length) {
                const row = document.createElement("div");
                row.className = "site-contacts-row";
                row.textContent = line;
                return row;
            }
            // Label is whatever precedes the first address ("TO: CC:"),
            // so the row reads the same as the report did.
            const label = line.slice(0, line.search(SITE_CONTACT_EMAIL_RE)).replace(/[\s:]+$/, "").trim();
            const row = document.createElement("button");
            row.type = "button";
            row.className = "site-contacts-row is-email";
            row.dataset.label = label || "emails";
            row.title = "Double-click (or Enter) to copy just these "
                + emails.length + " address" + (emails.length === 1 ? "" : "es");
            const labelEl = document.createElement("span");
            labelEl.className = "site-contacts-label";
            labelEl.textContent = label;
            const emailsEl = document.createElement("span");
            emailsEl.className = "site-contacts-emails";
            emailsEl.textContent = emails.join(", ");
            const hintEl = document.createElement("span");
            hintEl.className = "site-contacts-copy-hint";
            hintEl.setAttribute("aria-hidden", "true");
            hintEl.textContent = "⧉";
            row.appendChild(labelEl);
            row.appendChild(emailsEl);
            row.appendChild(hintEl);
            row.addEventListener("dblclick", function (event) {
                event.preventDefault();
                copySiteContactEmails(row, emails);
            });
            row.addEventListener("keydown", function (event) {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    copySiteContactEmails(row, emails);
                }
            });
            return row;
        }

        function openSiteContactsModal(title, text) {
            if (!siteContactsModal) {
                return;
            }
            siteContactsTitleEl.textContent = title;
            siteContactsFullText = text || "";
            siteContactsCopiedEl.textContent = "";
            siteContactsRowsEl.innerHTML = "";
            siteContactsFullText.split("\n\n").forEach(function (block, index) {
                if (index > 0) {
                    const sep = document.createElement("div");
                    sep.className = "site-contacts-sep";
                    siteContactsRowsEl.appendChild(sep);
                }
                block.split("\n").forEach(function (line) {
                    if (line.trim()) {
                        siteContactsRowsEl.appendChild(siteContactRow(line));
                    }
                });
            });
            siteContactsModal.classList.add("is-open");
            siteContactsRowsEl.scrollTop = 0;
            const firstEmailRow = siteContactsRowsEl.querySelector(".is-email");
            (firstEmailRow || siteContactsCopyBtn).focus();
        }

        function closeSiteContactsModal() {
            if (siteContactsModal) {
                siteContactsModal.classList.remove("is-open");
            }
        }

        if (siteContactsModal) {
            siteContactsCopyBtn.addEventListener("click", function () {
                const ok = copyPlainText(siteContactsFullText);
                showSiteContactsCopied(ok ? "Copied everything to clipboard"
                    : "Copy was blocked by the browser — select the text and press Ctrl+C", ok);
            });
            siteContactsCloseBtn.addEventListener("click", closeSiteContactsModal);
            siteContactsModal.addEventListener("click", function (event) {
                if (event.target === siteContactsModal) {
                    closeSiteContactsModal();
                }
            });
            // Capture phase, so Escape closes only this popup and not the
            // Graphs modal underneath it (the shared Escape handler would
            // otherwise close both in one keypress).
            document.addEventListener("keydown", function (event) {
                if (event.key === "Escape" && siteContactsModal.classList.contains("is-open")) {
                    event.stopImmediatePropagation();
                    closeSiteContactsModal();
                }
            }, true);
        }

        // ---- My Stats (per-tech ticket counts) ---------------------------
        // No login system, so "tech" is a free-text name typed once and
        // stored in this browser (localStorage) — sent along with
        // Resolved/Worked/Skipped so tech_stats.py can count tickets per
        // person instead of per browser tab. See that module's docstring
        // for why a typed name beats trying to key off IP address
        // (DHCP/VPN/roaming laptops churn IPs in a way a name doesn't) —
        // IP is still recorded server-side as a debugging breadcrumb, just
        // never the primary identity. Andrew's own request, 2026-10-01.
        const TECH_STATS_NAME_KEY = "workToolTechName";
        const techStatsModal = document.getElementById("tech_stats_modal");
        const techStatsNameInput = document.getElementById("tech_stats_name_input");
        const techStatsWhoSelect = document.getElementById("tech_stats_who_select");
        const techStatsRefreshBtn = document.getElementById("tech_stats_refresh");
        const techStatsLastEventEl = document.getElementById("tech_stats_last_event");
        const techStatsGridEl = document.getElementById("tech_stats_grid");
        const techStatsCloseBtn = document.getElementById("tech_stats_close");
        const myStatsBtn = document.getElementById("my_stats_btn");

        function getTechName() {
            try {
                return (window.localStorage.getItem(TECH_STATS_NAME_KEY) || "").trim();
            } catch (ignore) {
                return "";
            }
        }

        function setTechName(name) {
            const clean = String(name || "").trim();
            try {
                if (clean) {
                    window.localStorage.setItem(TECH_STATS_NAME_KEY, clean);
                } else {
                    window.localStorage.removeItem(TECH_STATS_NAME_KEY);
                }
            } catch (ignore) {
                // Name just won't persist across reloads.
            }
            return clean;
        }

        const TECH_STATS_WINDOWS = [
            ["week", "Last 7 days"],
            ["month", "Last 30 days"],
            ["year", "Last 365 days"],
            ["all_time", "All time"],
        ];

        function renderTechStatsGrid(summary) {
            if (!techStatsGridEl) {
                return;
            }
            techStatsGridEl.innerHTML = "";
            TECH_STATS_WINDOWS.forEach(function (pair) {
                const key = pair[0];
                const label = pair[1];
                const counts = (summary && summary[key]) || { resolved: 0, worked: 0, skipped: 0, total: 0 };
                const card = document.createElement("div");
                card.className = "tech-stats-card";
                const title = document.createElement("h3");
                title.textContent = label;
                card.appendChild(title);
                const total = document.createElement("div");
                total.className = "tech-stats-total";
                total.textContent = String(counts.total || 0);
                card.appendChild(total);
                const breakdown = document.createElement("div");
                breakdown.className = "tech-stats-breakdown";
                breakdown.textContent = "Resolved " + (counts.resolved || 0)
                    + " · Worked " + (counts.worked || 0)
                    + " · Skipped " + (counts.skipped || 0);
                card.appendChild(breakdown);
                techStatsGridEl.appendChild(card);
            });
        }

        function loadTechStats(tech) {
            if (!techStatsLastEventEl) {
                return;
            }
            if (!tech) {
                renderTechStatsGrid(null);
                techStatsLastEventEl.textContent = "Type your name above to see your stats.";
                techStatsLastEventEl.hidden = false;
                return;
            }
            techStatsLastEventEl.textContent = "Loading...";
            techStatsLastEventEl.hidden = false;
            fetch("/issues/tech-stats?tech=" + encodeURIComponent(tech))
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    renderTechStatsGrid(data);
                    techStatsLastEventEl.textContent = data.last_event
                        ? ("Last ticket action: " + data.last_event)
                        : ("No ticket actions recorded yet for " + tech + ".");
                })
                .catch(function (error) {
                    techStatsLastEventEl.textContent = "Could not load stats: " + (error.message || error);
                    renderTechStatsGrid(null);
                });
        }

        function populateTechStatsWhoSelect() {
            if (!techStatsWhoSelect) {
                return;
            }
            techStatsWhoSelect.innerHTML = "";
            const meOption = document.createElement("option");
            meOption.value = "__me__";
            meOption.textContent = "Me";
            techStatsWhoSelect.appendChild(meOption);
            fetch("/issues/tech-stats/techs")
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    const techs = (data && data.techs) || [];
                    const me = getTechName().toLowerCase();
                    techs.forEach(function (row) {
                        if (me && String(row.tech).toLowerCase() === me) {
                            return;
                        }
                        const option = document.createElement("option");
                        option.value = row.tech;
                        option.textContent = row.tech + " (" + row.count + ")";
                        techStatsWhoSelect.appendChild(option);
                    });
                })
                .catch(function () {
                    // Picker just stays at "Me" if the list fetch fails.
                });
        }

        function currentTechStatsSelection() {
            const value = techStatsWhoSelect ? techStatsWhoSelect.value : "__me__";
            if (!value || value === "__me__") {
                return getTechName();
            }
            return value;
        }

        function openTechStatsModal() {
            if (!techStatsModal) {
                return;
            }
            const name = getTechName();
            if (techStatsNameInput) {
                techStatsNameInput.value = name;
            }
            populateTechStatsWhoSelect();
            loadTechStats(name);
            techStatsModal.classList.add("is-open");
        }

        function closeTechStatsModal() {
            if (techStatsModal) {
                techStatsModal.classList.remove("is-open");
            }
        }

        if (myStatsBtn) {
            myStatsBtn.addEventListener("click", openTechStatsModal);
        }
        if (techStatsCloseBtn) {
            techStatsCloseBtn.addEventListener("click", closeTechStatsModal);
        }
        if (techStatsModal) {
            techStatsModal.addEventListener("click", function (event) {
                if (event.target === techStatsModal) {
                    closeTechStatsModal();
                }
            });
        }
        if (techStatsNameInput) {
            techStatsNameInput.addEventListener("change", function () {
                const name = setTechName(techStatsNameInput.value);
                techStatsNameInput.value = name;
                populateTechStatsWhoSelect();
                loadTechStats(name);
            });
        }
        if (techStatsWhoSelect) {
            techStatsWhoSelect.addEventListener("change", function () {
                loadTechStats(currentTechStatsSelection());
            });
        }
        if (techStatsRefreshBtn) {
            techStatsRefreshBtn.addEventListener("click", function () {
                loadTechStats(currentTechStatsSelection());
            });
        }

        if (graphsClose) {
            graphsClose.addEventListener("click", closeGraphsModal);
        }
        if (graphsCloseX) {
            graphsCloseX.addEventListener("click", closeGraphsModal);
        }
        if (graphsRefreshBtn) {
            graphsRefreshBtn.addEventListener("click", loadGraphs);
        }
        if (graphs360Btn) {
            graphs360Btn.addEventListener("click", function () {
                open360Snapshot(graphsUnit, graphs360Btn);
            });
        }
        if (graphsBatteryGlyphEl) {
            // Same "click to open VRM" action as the command menu's own
            // battery glyph (see openVrmForEntry) — a synthetic entry since
            // this modal only ever has the bare unit/subject, not a full
            // resolved one.
            graphsBatteryGlyphEl.addEventListener("click", function () {
                openVrmForEntry({ unit: graphsUnit, ticketSubject: graphsSubject });
            });
            wireGlyphKeyboardActivation(graphsBatteryGlyphEl);
        }
        if (graphsUptimeRefreshBtn) {
            graphsUptimeRefreshBtn.addEventListener("click", function () {
                if (!graphsUnit) {
                    return;
                }
                const original = graphsUptimeRefreshBtn.textContent;
                graphsUptimeRefreshBtn.disabled = true;
                graphsUptimeRefreshBtn.textContent = "…";
                fetch("/issues/robofiber-uptime/" + encodeURIComponent(graphsUnit), { method: "POST" })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        applyFreshSwitchUptime(graphsUnit, data, null);
                        const info = powerVsCellAlarmedUnits[graphsUnit.toUpperCase()];
                        if (info) {
                            graphsInfoLine = powerVsCellUptimeDetailText(info);
                            renderGraphsInfoLine();
                            graphsInfoLineEl.className = "graphs-info-line";
                            applyGraphsInfoLineUptimeTier(info);
                        }
                        statusEl.textContent = "Switch uptime refreshed for " + graphsUnit;
                    })
                    .catch(function (error) {
                        const message = "Switch uptime refresh failed: " + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        graphsUptimeRefreshBtn.disabled = false;
                        graphsUptimeRefreshBtn.textContent = original;
                    });
            });
        }
        if (graphsModal) {
            graphsModal.addEventListener("click", function (event) {
                if (event.target === graphsModal) {
                    closeGraphsModal();
                }
            });
        }

        function appendRouterPingButton(parentMenu, entry, label, mode) {
            const pingBtn = document.createElement("button");
            pingBtn.type = "button";
            pingBtn.className = "action-btn";
            pingBtn.textContent = label;
            if (!entry || !entry.unit) {
                pingBtn.disabled = true;
                pingBtn.title = "No unit on this ticket";
                parentMenu.appendChild(pingBtn);
                return;
            }
            pingBtn.title = mode === "fixed"
                ? "Ping router 4 times"
                : "Ping router up to 4 times; stop on first reply";
            pingBtn.addEventListener("click", function () {
                pingBtn.disabled = true;
                pingBtn.textContent = "Pinging...";
                statusEl.textContent = label + " for " + entry.unit + "...";
                fetch("/issues/ping-router/" + encodeURIComponent(entry.unit), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ mode: mode }),
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        const state = data.reachable ? "UP" : "DOWN";
                        const header = label
                            + " for "
                            + (data.unit || entry.unit)
                            + (data.ip ? (" (" + data.ip + ")") : "")
                            + " — "
                            + state;
                        consoleLines.push(header);
                        String(data.output || "").split(/\r?\n/).forEach(function (line) {
                            if (line) {
                                consoleLines.push(line);
                            }
                        });
                        renderConsole(true);
                        statusEl.textContent = header;
                    })
                    .catch(function (error) {
                        const message = label + " failed: " + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        pingBtn.disabled = false;
                        pingBtn.textContent = label;
                    });
            });
            parentMenu.appendChild(pingBtn);
        }

        function setLongPingButtonState(btn, active, label) {
            if (!btn) {
                return;
            }
            btn.classList.toggle("is-active", !!active);
            btn.textContent = active ? "Stop " + label : label;
            btn.title = active
                ? "Stop continuous ping"
                : "Continuous ping (ping IP -t); auto-stops after 30 minutes";
        }

        function stopLongPingForUnit(unit, kind, btn, label) {
            const key = longPingStateKey(unit, kind);
            const state = longPingByUnit[key];
            if (!state) {
                setLongPingButtonState(btn, false, label);
                return Promise.resolve();
            }
            const jobId = state.jobId;
            if (state.abortController) {
                try {
                    state.abortController.abort();
                } catch (ignore) {
                    // ignore
                }
            }
            return fetch("/issues/ping-router-long/" + encodeURIComponent(jobId) + "/stop", {
                method: "POST",
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    consoleLines.push(
                        label + " stopped for "
                        + (data.unit || unit)
                        + (data.ip ? (" (" + data.ip + ")") : "")
                        + " — "
                        + (data.reason || data.message || "cancelled")
                    );
                    renderConsole(true);
                    statusEl.textContent = label + " stopped for " + unit;
                })
                .catch(function (error) {
                    const message = "Stop " + label + " failed: " + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                })
                .finally(function () {
                    delete longPingByUnit[key];
                    setLongPingButtonState(btn, false, label);
                });
        }

        function startLongPingForUnit(unit, kind, startUrl, btn, label) {
            const key = longPingStateKey(unit, kind);
            setLongPingButtonState(btn, true, label);
            statusEl.textContent = "Starting " + label + " for " + unit + "...";
            return fetch(startUrl, {
                method: "POST",
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const jobId = data.job_id;
                    const abortController = new AbortController();
                    longPingByUnit[key] = {
                        jobId: jobId,
                        abortController: abortController,
                        button: btn,
                    };
                    const header = label + " started for "
                        + (data.unit || unit)
                        + (data.ip ? (" (" + data.ip + ")") : "")
                        + " — auto-stop "
                        + Math.round((data.max_seconds || 1800) / 60)
                        + " min";
                    consoleLines.push(header);
                    renderConsole(true);
                    statusEl.textContent = header;
                    return fetch(
                        "/issues/ping-router-long/"
                        + encodeURIComponent(jobId)
                        + "/stream",
                        { signal: abortController.signal }
                    ).then(function (response) {
                        if (!response.ok) {
                            throw new Error("HTTP " + response.status);
                        }
                        if (!response.body || !response.body.getReader) {
                            return response.text().then(function (text) {
                                String(text || "").split(/\r?\n/).forEach(function (line) {
                                    if (line) {
                                        consoleLines.push(line);
                                    }
                                });
                                renderConsole(true);
                            });
                        }
                        const reader = response.body.getReader();
                        const decoder = new TextDecoder();
                        let buffer = "";
                        function readChunk() {
                            return reader.read().then(function (result) {
                                if (result.done) {
                                    if (buffer) {
                                        consoleLines.push(buffer);
                                        renderConsole(true);
                                    }
                                    return;
                                }
                                buffer += decoder.decode(result.value, { stream: true });
                                const parts = buffer.split(/\r?\n/);
                                buffer = parts.pop() || "";
                                parts.forEach(function (line) {
                                    if (line) {
                                        consoleLines.push(line);
                                    }
                                });
                                if (parts.length) {
                                    renderConsole(true);
                                    statusEl.textContent = label + " running for " + unit + "...";
                                }
                                return readChunk();
                            });
                        }
                        return readChunk();
                    });
                })
                .catch(function (error) {
                    if (error && error.name === "AbortError") {
                        return;
                    }
                    const message = label + " failed: " + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    const state = longPingByUnit[key];
                    if (state && state.button === btn) {
                        delete longPingByUnit[key];
                    }
                    setLongPingButtonState(btn, !!longPingByUnit[key], label);
                });
        }

        // Shared by Long Ping Router/NUC/PVE/Camera — each caller just
        // supplies a kind (for the per-target job-state key), a label, and
        // how to build the start URL for a given unit.
        function appendLongPingButton(parentMenu, entry, options) {
            const pingBtn = document.createElement("button");
            pingBtn.type = "button";
            pingBtn.className = "action-btn";
            if (!entry || !entry.unit) {
                setLongPingButtonState(pingBtn, false, options.label);
                pingBtn.disabled = true;
                pingBtn.title = "No unit on this ticket";
                parentMenu.appendChild(pingBtn);
                return;
            }
            const key = longPingStateKey(entry.unit, options.kind);
            const active = !!longPingByUnit[key];
            setLongPingButtonState(pingBtn, active, options.label);
            if (active) {
                longPingByUnit[key].button = pingBtn;
            }
            pingBtn.addEventListener("click", function () {
                if (longPingByUnit[key]) {
                    stopLongPingForUnit(entry.unit, options.kind, pingBtn, options.label);
                    return;
                }
                startLongPingForUnit(entry.unit, options.kind, options.buildStartUrl(entry.unit), pingBtn, options.label);
            });
            parentMenu.appendChild(pingBtn);
        }

        function appendLongPingRouterButton(parentMenu, entry) {
            appendLongPingButton(parentMenu, entry, {
                kind: "router",
                label: "Long Ping Router",
                buildStartUrl: function (unit) {
                    return "/issues/ping-router-long/" + encodeURIComponent(unit);
                },
            });
        }

        function appendLongPingNucButton(parentMenu, entry) {
            appendLongPingButton(parentMenu, entry, {
                kind: "nuc",
                label: "Long Ping NUC",
                buildStartUrl: function (unit) {
                    return "/issues/ping-nuc-long/" + encodeURIComponent(unit);
                },
            });
        }

        function appendLongPingPveButton(parentMenu, entry) {
            appendLongPingButton(parentMenu, entry, {
                kind: "pve",
                label: "Long Ping PVE",
                buildStartUrl: function (unit) {
                    return "/issues/ping-pve-long/" + encodeURIComponent(unit);
                },
            });
        }

        function appendLongPingCameraButton(parentMenu, entry, camera) {
            appendLongPingButton(parentMenu, entry, {
                kind: "camera:" + camera.target,
                label: "Long Ping " + (camera.label || camera.target),
                buildStartUrl: function (unit) {
                    return "/issues/ping-camera-long/" + encodeURIComponent(unit)
                        + "/" + encodeURIComponent(camera.target);
                },
            });
        }

        // "Test All Emails" — same start/stop-toggle, stream-to-console
        // shape as Long Ping Router above (see startLongPingForUnit),
        // just backed by a timed loop on the server (work_tool.
        // start_camera_test_email_loop) instead of a live subprocess:
        // there's no continuous stdout to tail here, each tick is a
        // handful of discrete camera calls, so the server streams its
        // own queued output lines instead.
        const emailTestLoopByUnit = {};

        function setEmailTestLoopButtonState(btn, active) {
            if (!btn) {
                return;
            }
            btn.classList.toggle("is-active", !!active);
            btn.textContent = active ? "Stop Test All Emails" : "Test All Emails";
            btn.title = active
                ? "Stop the repeating test-email loop"
                : "Send one test email per camera, repeating every 30s; auto-stops after 10 minutes";
        }

        function stopEmailTestLoopForUnit(unit, btn) {
            const state = emailTestLoopByUnit[unit];
            if (!state) {
                setEmailTestLoopButtonState(btn, false);
                return Promise.resolve();
            }
            const jobId = state.jobId;
            if (state.abortController) {
                try {
                    state.abortController.abort();
                } catch (ignore) {
                    // ignore
                }
            }
            return fetch("/issues/camera-test-email-loop/" + encodeURIComponent(jobId) + "/stop", {
                method: "POST",
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    consoleLines.push(
                        "Test email loop stopped for "
                        + (data.unit || unit)
                        + " — "
                        + (data.reason || data.message || "cancelled")
                    );
                    renderConsole(true);
                    statusEl.textContent = "Test email loop stopped for " + unit;
                })
                .catch(function (error) {
                    const message = "Stop test email loop failed: " + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                })
                .finally(function () {
                    delete emailTestLoopByUnit[unit];
                    setEmailTestLoopButtonState(btn, false);
                });
        }

        function startEmailTestLoopForUnit(unit, btn) {
            setEmailTestLoopButtonState(btn, true);
            statusEl.textContent = "Starting test email loop for " + unit + "...";
            return fetch("/issues/camera-test-email-loop/" + encodeURIComponent(unit), {
                method: "POST",
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const jobId = data.job_id;
                    const abortController = new AbortController();
                    emailTestLoopByUnit[unit] = {
                        jobId: jobId,
                        abortController: abortController,
                        button: btn,
                    };
                    const header = "Test email loop started for "
                        + (data.unit || unit)
                        + " — " + (data.camera_count || 0) + " camera(s), every "
                        + (data.interval_seconds || 30) + "s (auto-stop "
                        + Math.round((data.max_seconds || 1800) / 60) + " min)";
                    consoleLines.push(header);
                    renderConsole(true);
                    statusEl.textContent = header;
                    return fetch(
                        "/issues/camera-test-email-loop/"
                        + encodeURIComponent(jobId)
                        + "/stream",
                        { signal: abortController.signal }
                    ).then(function (response) {
                        if (!response.ok) {
                            throw new Error("HTTP " + response.status);
                        }
                        if (!response.body || !response.body.getReader) {
                            return response.text().then(function (text) {
                                String(text || "").split(/\r?\n/).forEach(function (line) {
                                    if (line) {
                                        consoleLines.push(line);
                                    }
                                });
                                renderConsole(true);
                            });
                        }
                        const reader = response.body.getReader();
                        const decoder = new TextDecoder();
                        let buffer = "";
                        function readChunk() {
                            return reader.read().then(function (result) {
                                if (result.done) {
                                    if (buffer) {
                                        consoleLines.push(buffer);
                                        renderConsole(true);
                                    }
                                    return;
                                }
                                buffer += decoder.decode(result.value, { stream: true });
                                const parts = buffer.split(/\r?\n/);
                                buffer = parts.pop() || "";
                                parts.forEach(function (line) {
                                    if (line) {
                                        consoleLines.push(line);
                                    }
                                });
                                if (parts.length) {
                                    renderConsole(true);
                                    statusEl.textContent = "Test email loop running for " + unit + "...";
                                }
                                return readChunk();
                            });
                        }
                        return readChunk();
                    });
                })
                .catch(function (error) {
                    if (error && error.name === "AbortError") {
                        return;
                    }
                    const message = "Test email loop failed: " + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    const state = emailTestLoopByUnit[unit];
                    if (state && state.button === btn) {
                        delete emailTestLoopByUnit[unit];
                    }
                    setEmailTestLoopButtonState(btn, !!emailTestLoopByUnit[unit]);
                });
        }

        function appendTestAllEmailsButton(parentMenu, entry) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "action-btn";
            if (!entry || !entry.unit) {
                setEmailTestLoopButtonState(btn, false);
                btn.disabled = true;
                btn.title = "No unit on this ticket";
                parentMenu.appendChild(btn);
                return;
            }
            const active = !!emailTestLoopByUnit[entry.unit];
            setEmailTestLoopButtonState(btn, active);
            if (active) {
                emailTestLoopByUnit[entry.unit].button = btn;
            }
            btn.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                if (emailTestLoopByUnit[entry.unit]) {
                    stopEmailTestLoopForUnit(entry.unit, btn);
                    return;
                }
                startEmailTestLoopForUnit(entry.unit, btn);
            });
            parentMenu.appendChild(btn);
        }

        function appendRouterCommandMenu(commandItems, entry) {
            const routerMenu = appendCommandSubmenu(commandItems, "Router");
            appendGetCarrierButton(routerMenu, entry);
            appendRouterPingButton(routerMenu, entry, "Quick Validate", "quick");
            appendRouterPingButton(routerMenu, entry, "Ping Router", "fixed");
            appendLongPingRouterButton(routerMenu, entry);
        }

        function openSitePageHref(entry) {
            const direct = erpSiteHref(entry && entry.siteId);
            if (direct) {
                return direct;
            }
            const unit = (entry && entry.unit) || "-";
            let href = "/issues/site-page/" + encodeURIComponent(unit);
            const params = new URLSearchParams();
            if (entry && entry.ticketSubject) {
                params.set("subject", entry.ticketSubject);
            }
            // A project's title names the real site but its Component
            // often has no Site linked yet (new deployments, prep work,
            // swaps, some in-flight terminations) — see
            // resolve_dashboard_site_id's own docstring. Signal this so
            // the backend searches the title against ERP Site names
            // first instead of failing on the unit's own missing link.
            if (entry && entry.projectId) {
                params.set("is_project", "1");
            }
            const query = params.toString();
            if (query) {
                href += "?" + query;
            }
            return href;
        }

        function shieldSiteHref(siteId) {
            const site = String(siteId || "").trim();
            if (!site || !workTLD) {
                return "";
            }
            return "https://shield." + workTLD + "/site/" + encodeURIComponent(site);
        }

        function erpSiteHref(siteId) {
            const site = String(siteId || "").trim();
            if (!site || !workTLD) {
                return "";
            }
            return "https://erp." + workTLD + "/app/site/" + encodeURIComponent(site);
        }

        function eventRecordsHref(unit) {
            const code = String(unit || "").trim().replace(/^SC-/i, "");
            if (!code) {
                return "";
            }
            if (!workTLD) {
                return "/issues/event-records/" + encodeURIComponent(code);
            }
            const params = new URLSearchParams({
                component: '["like","SC-' + code + '%"]',
                creation: '["Timespan","last 7 days"]',
            });
            return "https://erp." + workTLD + "/app/event-record?" + params.toString();
        }

        function appendOpenSitePageButton(openMenu, entry) {
            const hasLookup = !!(entry && (entry.unit || entry.ticketSubject));
            if (!hasLookup) {
                const siteBtn = document.createElement("button");
                siteBtn.type = "button";
                siteBtn.className = "action-btn";
                siteBtn.textContent = "Open Site Page";
                siteBtn.disabled = true;
                siteBtn.title = "No unit or project subject to resolve Site ID";
                openMenu.appendChild(siteBtn);
                return;
            }
            const siteBtn = document.createElement("a");
            siteBtn.className = "action-btn";
            siteBtn.href = openSitePageHref(entry);
            siteBtn.target = "_blank";
            siteBtn.rel = "noopener noreferrer";
            siteBtn.textContent = "Open Site Page";
            siteBtn.title = "Open ERP Site page";
            openMenu.appendChild(siteBtn);
        }

        function shieldComponentHref(code) {
            const raw = String(code || "").trim();
            if (!raw || !workTLD) {
                return "";
            }
            const body = raw.toUpperCase().indexOf("SC-") === 0 ? raw.slice(3) : raw;
            if (!body) {
                return "";
            }
            return "https://shield." + workTLD + "/component/SC-"
                + encodeURIComponent(body.replace(/\s+/g, "").toUpperCase());
        }

        function unitKindFromEntry(entry) {
            const unit = String((entry && entry.unit) || "").trim().toUpperCase();
            if (/^MU\d+/.test(unit)) {
                return "MU";
            }
            if (/^FD\d+/.test(unit)) {
                return "FD";
            }
            if (/^RD\d+/.test(unit)) {
                return "RD";
            }
            return "";
        }

        function attachedMuFromEntry(entry) {
            if (!entry) {
                return "";
            }
            const kind = unitKindFromEntry(entry);
            if (kind === "MU") {
                return String(entry.unit || "").trim().toUpperCase();
            }
            if (entry.vrmMu) {
                const digits = String(entry.vrmMu).replace(/\D/g, "");
                if (digits) {
                    return "MU" + digits;
                }
            }
            const subject = String(entry.ticketSubject || "");
            const paren = subject.match(/\b(?:RD|FD)\s*\d+\s*\(\s*(MU\s*\d+)\s*\)/i);
            if (paren) {
                return paren[1].replace(/\s+/g, "").toUpperCase();
            }
            const bare = subject.match(/\bMU\s*(\d{3,6})\b/i);
            if (bare && (kind === "RD" || kind === "FD")) {
                return "MU" + bare[1];
            }
            return "";
        }

        function appendShieldMenu(openMenu, entry) {
            const shieldMenu = appendCommandSubmenu(openMenu, "Shield");
            const unit = entry && entry.unit ? String(entry.unit).trim() : "";
            const kind = unitKindFromEntry(entry);

            if (unit) {
                const siteBtn = document.createElement("a");
                siteBtn.className = "action-btn";
                const directShield = shieldSiteHref(entry.siteId);
                const shieldParams = new URLSearchParams();
                if (entry.ticketSubject) {
                    shieldParams.set("subject", entry.ticketSubject);
                }
                // See openSitePageHref's own comment — a project's title
                // is the reliable source of its Site, not the unit's
                // Component link.
                if (entry.projectId) {
                    shieldParams.set("is_project", "1");
                }
                const shieldQuery = shieldParams.toString();
                siteBtn.href = directShield || (
                    "/issues/shield/" + encodeURIComponent(unit)
                    + (shieldQuery ? ("?" + shieldQuery) : "")
                );
                siteBtn.target = "_blank";
                siteBtn.rel = "noopener noreferrer";
                siteBtn.textContent = "Open Site";
                siteBtn.title = directShield
                    ? ("Open Shield site " + entry.siteId)
                    : ("Open Shield site for " + unit);
                shieldMenu.appendChild(siteBtn);
            } else {
                const siteBtn = document.createElement("button");
                siteBtn.type = "button";
                siteBtn.className = "action-btn";
                siteBtn.textContent = "Open Site";
                siteBtn.disabled = true;
                siteBtn.title = "No unit to resolve Shield site";
                shieldMenu.appendChild(siteBtn);
            }

            if (kind === "RD" || kind === "FD" || kind === "MU") {
                const headHref = shieldComponentHref(unit);
                const headLabel = kind === "MU"
                    ? "Open MU Component"
                    : (kind === "FD" ? "Open FD Component" : "Open RD Component");
                if (headHref) {
                    const headBtn = document.createElement("a");
                    headBtn.className = "action-btn";
                    headBtn.href = headHref;
                    headBtn.target = "_blank";
                    headBtn.rel = "noopener noreferrer";
                    headBtn.textContent = headLabel;
                    headBtn.title = headHref;
                    shieldMenu.appendChild(headBtn);
                } else {
                    const headBtn = document.createElement("button");
                    headBtn.type = "button";
                    headBtn.className = "action-btn";
                    headBtn.textContent = headLabel;
                    headBtn.disabled = true;
                    headBtn.title = "workTLD is not set";
                    shieldMenu.appendChild(headBtn);
                }
            }

            // MU units are the trailer — no separate trailer button.
            if (kind === "MU") {
                return;
            }

            const trailerMu = attachedMuFromEntry(entry);
            const trailerHref = trailerMu ? shieldComponentHref(trailerMu) : "";
            if (trailerHref) {
                const trailerBtn = document.createElement("a");
                trailerBtn.className = "action-btn";
                trailerBtn.href = trailerHref;
                trailerBtn.target = "_blank";
                trailerBtn.rel = "noopener noreferrer";
                trailerBtn.textContent = "Open Trailer Component";
                trailerBtn.title = trailerHref;
                shieldMenu.appendChild(trailerBtn);
                return;
            }

            const trailerBtn = document.createElement("button");
            trailerBtn.type = "button";
            trailerBtn.className = "action-btn";
            trailerBtn.textContent = "Open Trailer Component";
            trailerBtn.disabled = true;
            trailerBtn.title = "No trailer attached";
            shieldMenu.appendChild(trailerBtn);

            if (!unit || (kind !== "RD" && kind !== "FD")) {
                return;
            }
            // ACRD / missing subject MU: ask ERP; enable if a parent trailer exists.
            let lookupUrl = "/issues/attached-mu/" + encodeURIComponent(unit);
            if (entry.ticketSubject) {
                lookupUrl += "?subject=" + encodeURIComponent(entry.ticketSubject);
            }
            fetch(lookupUrl)
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("HTTP " + response.status);
                    }
                    return response.json();
                })
                .then(function (data) {
                    const mu = data && data.mu ? String(data.mu) : "";
                    const url = (data && data.url) || shieldComponentHref(mu);
                    if (!mu || !url || !trailerBtn.parentNode) {
                        return;
                    }
                    const link = document.createElement("a");
                    link.className = "action-btn";
                    link.href = url;
                    link.target = "_blank";
                    link.rel = "noopener noreferrer";
                    link.textContent = "Open Trailer Component";
                    link.title = url;
                    trailerBtn.parentNode.replaceChild(link, trailerBtn);
                })
                .catch(function () {
                    // Keep disabled "No trailer attached".
                });
        }

        // ART report 152 (Site Contacts) is every contact in the company
        // with no server-side filter — the button pulls the whole thing
        // and the server (work_tool.get_art_site_contacts) filters it down
        // to this ticket's own site before it ever reaches here. Its own
        // top-level submenu, a peer of Open/Shield rather than nested
        // inside either — this isn't a "go look at ERP/Shield" link, it's
        // a distinct ART data pull.
        function appendArtMenu(commandItems, entry) {
            const artMenu = appendCommandSubmenu(commandItems, "Art");
            const unit = entry && entry.unit ? String(entry.unit).trim() : "";
            const contactsBtn = document.createElement("button");
            contactsBtn.type = "button";
            contactsBtn.className = "action-btn";
            contactsBtn.textContent = "Get site contacts";
            if (!unit) {
                contactsBtn.disabled = true;
                contactsBtn.title = "No unit to resolve a site for";
                artMenu.appendChild(contactsBtn);
                return;
            }
            contactsBtn.title = "Pull ART report 152 (Site Contacts), filtered to this ticket's own site";
            contactsBtn.addEventListener("click", function () {
                contactsBtn.disabled = true;
                contactsBtn.textContent = "Fetching...";
                statusEl.textContent = "Fetching ART site contacts for " + unit + "...";
                const subject = (entry && (entry.ticketSubject || entry.subject)) || "";
                fetch("/issues/art-site-contacts/" + encodeURIComponent(unit), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ subject: subject }),
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        const contacts = data.contacts || [];
                        const header = "ART site contacts for " + data.site_name
                            + " (" + contacts.length + "):";
                        consoleLines.push(header);
                        const popupBlocks = [];
                        if (!contacts.length) {
                            const none = "(no rows matched " + data.site_column + " = \""
                                + data.site_name + "\")";
                            consoleLines.push(none);
                            popupBlocks.push(none);
                        } else {
                            contacts.forEach(function (contact) {
                                const keys = Object.keys(contact);
                                consoleLines.push(
                                    "  " + keys
                                        .map(function (key) { return key + ": " + contact[key]; })
                                        .join(" | ")
                                );
                                popupBlocks.push(keys
                                    .map(function (key) { return key + ": " + contact[key]; })
                                    .join("\n"));
                            });
                        }
                        renderConsole(true);
                        statusEl.textContent = header;
                        notify(header, contacts.length ? "info" : "error");
                        openSiteContactsModal(
                            unit + " — " + data.site_name + " (" + contacts.length + ")",
                            popupBlocks.join("\n\n")
                        );
                    })
                    .catch(function (error) {
                        const message = "Get site contacts failed: " + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        contactsBtn.disabled = false;
                        contactsBtn.textContent = "Get site contacts";
                    });
            });
            artMenu.appendChild(contactsBtn);
        }

        function erpComponentHref(code) {
            const raw = String(code || "").trim();
            if (!raw || !workTLD) {
                return "";
            }
            const body = raw.toUpperCase().indexOf("SC-") === 0 ? raw.slice(3) : raw;
            if (!body) {
                return "";
            }
            return "https://erp." + workTLD + "/app/component/SC-"
                + encodeURIComponent(body.replace(/\s+/g, "").toUpperCase());
        }

        function appendErpMenu(openMenu, entry) {
            const erpMenu = appendCommandSubmenu(openMenu, "ERP");
            const unit = entry && entry.unit ? String(entry.unit).trim() : "";
            const kind = unitKindFromEntry(entry);

            appendOpenEventRecordsButton(erpMenu, entry);
            appendOpenSitePageButton(erpMenu, entry);

            if (kind === "RD" || kind === "FD" || kind === "MU") {
                const headHref = erpComponentHref(unit);
                const headLabel = kind === "MU"
                    ? "Open MU Component"
                    : (kind === "FD" ? "Open FD Component" : "Open RD Component");
                if (headHref) {
                    const headBtn = document.createElement("a");
                    headBtn.className = "action-btn";
                    headBtn.href = headHref;
                    headBtn.target = "_blank";
                    headBtn.rel = "noopener noreferrer";
                    headBtn.textContent = headLabel;
                    headBtn.title = headHref;
                    erpMenu.appendChild(headBtn);
                } else {
                    const headBtn = document.createElement("button");
                    headBtn.type = "button";
                    headBtn.className = "action-btn";
                    headBtn.textContent = headLabel;
                    headBtn.disabled = true;
                    headBtn.title = "workTLD is not set";
                    erpMenu.appendChild(headBtn);
                }
            }

            if (kind === "MU") {
                return;
            }

            const trailerMu = attachedMuFromEntry(entry);
            const trailerHref = trailerMu ? erpComponentHref(trailerMu) : "";
            if (trailerHref) {
                const trailerBtn = document.createElement("a");
                trailerBtn.className = "action-btn";
                trailerBtn.href = trailerHref;
                trailerBtn.target = "_blank";
                trailerBtn.rel = "noopener noreferrer";
                trailerBtn.textContent = "Open Trailer Component";
                trailerBtn.title = trailerHref;
                erpMenu.appendChild(trailerBtn);
                return;
            }

            const trailerBtn = document.createElement("button");
            trailerBtn.type = "button";
            trailerBtn.className = "action-btn";
            trailerBtn.textContent = "Open Trailer Component";
            trailerBtn.disabled = true;
            trailerBtn.title = "No trailer attached";
            erpMenu.appendChild(trailerBtn);

            if (!unit || (kind !== "RD" && kind !== "FD")) {
                return;
            }
            let lookupUrl = "/issues/attached-mu/" + encodeURIComponent(unit);
            if (entry.ticketSubject) {
                lookupUrl += "?subject=" + encodeURIComponent(entry.ticketSubject);
            }
            fetch(lookupUrl)
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("HTTP " + response.status);
                    }
                    return response.json();
                })
                .then(function (data) {
                    const mu = data && data.mu ? String(data.mu) : "";
                    const url = erpComponentHref(mu);
                    if (!mu || !url || !trailerBtn.parentNode) {
                        return;
                    }
                    const link = document.createElement("a");
                    link.className = "action-btn";
                    link.href = url;
                    link.target = "_blank";
                    link.rel = "noopener noreferrer";
                    link.textContent = "Open Trailer Component";
                    link.title = url;
                    trailerBtn.parentNode.replaceChild(link, trailerBtn);
                })
                .catch(function () {
                    // Keep disabled "No trailer attached".
                });
        }

        function appendOpenEventRecordsButton(openMenu, entry) {
            if (!entry || !entry.unit) {
                const eventsBtn = document.createElement("button");
                eventsBtn.type = "button";
                eventsBtn.className = "action-btn";
                eventsBtn.textContent = "Open Event Records";
                eventsBtn.disabled = true;
                eventsBtn.title = "No unit on this ticket";
                openMenu.appendChild(eventsBtn);
                return;
            }
            const eventsBtn = document.createElement("a");
            eventsBtn.className = "action-btn";
            eventsBtn.href = eventRecordsHref(entry.unit);
            eventsBtn.target = "_blank";
            eventsBtn.rel = "noopener noreferrer";
            eventsBtn.textContent = "Open Event Records";
            eventsBtn.title = "Open ERP Event Records for SC-" + entry.unit + "% (last 7 days)";
            openMenu.appendChild(eventsBtn);
        }

        function appendOpenScryptedButton(openMenu, entry) {
            if (!entry || !entry.hasScrypted) {
                return;
            }
            if (entry.scryptedUrl) {
                const scryptedBtn = document.createElement("a");
                scryptedBtn.className = "action-btn";
                scryptedBtn.href = entry.scryptedUrl;
                scryptedBtn.target = "_blank";
                scryptedBtn.rel = "noopener noreferrer";
                scryptedBtn.textContent = "Open Scrypted";
                openMenu.appendChild(scryptedBtn);
            } else {
                const scryptedBtn = document.createElement("button");
                scryptedBtn.type = "button";
                scryptedBtn.className = "action-btn";
                scryptedBtn.textContent = "Open Scrypted";
                scryptedBtn.disabled = true;
                scryptedBtn.title = "No Scrypted URL available for this unit";
                openMenu.appendChild(scryptedBtn);
            }
            // NVR view (@scrypted/nvr) — separate plugin UI from the core
            // one above (@scrypted/core), same host/port, just a different
            // endpoint path. Andrew's own request, 2026-09-30.
            if (entry.scryptedNvrUrl) {
                const scryptedNvrBtn = document.createElement("a");
                scryptedNvrBtn.className = "action-btn";
                scryptedNvrBtn.href = entry.scryptedNvrUrl;
                scryptedNvrBtn.target = "_blank";
                scryptedNvrBtn.rel = "noopener noreferrer";
                scryptedNvrBtn.textContent = "Open Scrypted NVR";
                openMenu.appendChild(scryptedNvrBtn);
            } else {
                const scryptedNvrBtn = document.createElement("button");
                scryptedNvrBtn.type = "button";
                scryptedNvrBtn.className = "action-btn";
                scryptedNvrBtn.textContent = "Open Scrypted NVR";
                scryptedNvrBtn.disabled = true;
                scryptedNvrBtn.title = "No Scrypted URL available for this unit";
                openMenu.appendChild(scryptedNvrBtn);
            }
        }

        function entryHasRdInSubject(entry) {
            const subject = String((entry && entry.ticketSubject) || "");
            const unit = String((entry && entry.unit) || "");
            if (/\bRD\s*\d+/i.test(subject)) {
                return true;
            }
            return /^RD\d+/i.test(unit);
        }

        function appendOpenVrmButton(openMenu, entry) {
            if (!entry || !entryHasRdInSubject(entry)) {
                return;
            }
            let url = entry.vrmUrl || "";
            let searchLabel = entry.vrmMu || "";
            if (!url) {
                const subject = String(entry.ticketSubject || "");
                const muMatch = subject.match(/\bMU\s*(\d{4})\b/i);
                if (muMatch) {
                    searchLabel = muMatch[1];
                    url = "https://vrm.victronenergy.com/installation-overview?search="
                        + encodeURIComponent(searchLabel);
                } else if (entry.unit) {
                    searchLabel = entry.unit;
                    url = "https://vrm.victronenergy.com/installation-overview?search="
                        + encodeURIComponent(entry.unit);
                }
            }
            if (!url) {
                return;
            }
            const vrmBtn = document.createElement("a");
            vrmBtn.className = "action-btn";
            vrmBtn.href = url;
            vrmBtn.target = "_blank";
            vrmBtn.rel = "noopener noreferrer";
            vrmBtn.textContent = "Open VRM";
            vrmBtn.title = searchLabel
                ? ("Open VRM search for " + searchLabel)
                : "Open VRM";
            openMenu.appendChild(vrmBtn);
        }

        function openBlankTab(url) {
            // Do not pass noopener in windowFeatures — Chrome then always returns
            // null, which we used to treat as "popup blocked" even when the tab opened.
            const win = window.open(url, "_blank");
            if (win) {
                try {
                    win.opener = null;
                } catch (err) {
                    /* ignore */
                }
            }
            return win;
        }

        function launchUnitCameras(unit, target, triggerEl, allTargets) {
            if (!unit) {
                notifyError("Open cameras failed: No unit");
                return;
            }
            if (target === "all") {
                const launchUrl = "/issues/cameras-launch/" + encodeURIComponent(unit);
                const win = openBlankTab(launchUrl);
                if (!win) {
                    notifyError(
                        "Pop-up blocked. Allow pop-ups for this site to open cameras."
                    );
                    return;
                }
                const count = (allTargets || []).length;
                const line = "Opened camera launcher for " + unit
                    + (count ? (" (" + count + " cameras)") : "");
                consoleLines.push(line);
                renderConsole(true);
                statusEl.textContent = line;
                return;
            }
            const url = "/issues/camera/"
                + encodeURIComponent(unit)
                + "/"
                + encodeURIComponent(target);
            const win = openBlankTab(url);
            if (!win) {
                notifyError(
                    "Pop-up blocked. Allow pop-ups for this site to open cameras."
                );
                return;
            }
            const line = "Opened camera " + target + " for " + unit;
            consoleLines.push(line);
            renderConsole(true);
            statusEl.textContent = line;
        }

        function wireCameraLaunchButton(button, unit, target, getAllTargets) {
            button.type = "button";
            button.className = "action-btn";
            button.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                launchUnitCameras(
                    unit,
                    target,
                    button,
                    getAllTargets ? getAllTargets() : null
                );
            });
            return button;
        }

        // ---- Quick actions ---------------------------------------------------
        // The handful of actions worth reaching without opening Commands and
        // walking two or three submenus. EDIT THIS ARRAY to change which
        // appear, in what order, or to drop the row entirely (set it to []).
        //
        //   id      - unique key
        //   label   - button text (keep it short; these sit on every row)
        //   title   - tooltip
        //   show    - optional (entry) => bool gate
        //   run     - (entry, btn) => void, for POST-style actions
        //   href    - (entry) => url string, for link-style actions
        const QUICK_ACTIONS = [
            {
                id: "validate",
                label: "Validate",
                title: "Validate (Quick) — same as Commands → Validate → Validate (Quick); "
                    + "pings every camera instead, for a Camera Outage row",
                busyLabel: "…",
                run: function (entry, btn, listId) {
                    if (entry.isCamera) {
                        runValidateCameraOutageQuickAction(entry, btn);
                        return;
                    }
                    // issue_id/source_list_id let the backend keep the
                    // shared job's own copy of this ticket in sync with
                    // whatever Validate just found — without them this
                    // result only ever updates this browser's view, and
                    // the next shared-state poll silently reverts it
                    // back to server truth (see _sync_shared_validate_
                    // result). Caught live, 2026-09-25 (RD3563): this row
                    // button never sent either, so a Quick Validate that
                    // found the unit fully down kept reporting it
                    // correctly in the console while the ticket silently
                    // stayed put in Up Steady — the exact RD3059 bug that
                    // button's OWN command-menu sibling was already fixed
                    // for, just not this one.
                    quickFetch(
                        btn, "Validate", "/issues/validate-unit/" + encodeURIComponent(entry.unit),
                        function (data) {
                            const category = data.category === "stale_vpn"
                                ? "truly_down"
                                : (data.category || "");
                            const connectivityLed = {
                                false_positives: "green",
                                nuc_down: "yellow",
                                scrypted_outage: "yellow",
                                truly_down: "red",
                            };
                            if (connectivityLed[category]) {
                                entry.ledStatus = connectivityLed[category];
                            }
                            return "Validated " + entry.unit
                                + (data.category ? (" → " + (listHeadingLabels[data.category] || data.category)) : "")
                                + (data.output ? ("\n" + data.output) : "");
                        },
                        function () {
                            propagateLedFromEntry(entry);
                        },
                        { issue_id: entry.issueId || "", source_list_id: listId || "" }
                    );
                },
            },
            {
                id: "switch_uptime",
                label: "Switch Uptime",
                title: "Switch / Robofiber uptime",
                busyLabel: "…",
                run: function (entry, btn) {
                    quickFetch(
                        btn, "Switch Uptime", "/issues/robofiber-uptime/" + encodeURIComponent(entry.unit),
                        function (data) {
                            const head = "Switch uptime " + (data.unit || entry.unit)
                                + (data.ip ? (" (" + data.ip + ")") : "");
                            const body = (data.lines || []).filter(Boolean).join("\n") || data.output || "";
                            return body ? (head + "\n" + body) : head;
                        },
                        function (data) {
                            const li = btn.closest("li");
                            const commandMenu = li && li.querySelector(".command-menu");
                            applyFreshSwitchUptime(entry.unit, data, commandMenu);
                        }
                    );
                },
            },
            {
                id: "vrm",
                label: "VRM",
                title: "Open VRM for this unit",
                show: function (entry) {
                    return !!quickVrmUrl(entry);
                },
                href: quickVrmUrl,
            },
            {
                id: "mesh",
                label: "Mesh",
                title: "Open MeshCentral for this unit",
                show: function (entry) {
                    return !!entry.unit;
                },
                href: function (entry) {
                    return meshBaseUrl + encodeURIComponent(entry.unit);
                },
            },
            {
                id: "snapshot",
                label: "Snap",
                title: "Fisheye snapshot",
                show: function (entry) {
                    return !!entry.unit;
                },
                run: function (entry) {
                    openFisheyeSnapshot(entry.unit, entry.url || "");
                },
            },
        ];

        function quickVrmUrl(entry) {
            if (!entry || !entryHasRdInSubject(entry)) {
                return "";
            }
            if (entry.vrmUrl) {
                return entry.vrmUrl;
            }
            const subject = String(entry.ticketSubject || "");
            const muMatch = subject.match(/\bMU\s*(\d{4})\b/i);
            const search = muMatch ? muMatch[1] : (entry.unit || "");
            return search
                ? ("https://vrm.victronenergy.com/installation-overview?search=" + encodeURIComponent(search))
                : "";
        }

        // Shared "Open VRM" action for the status-row glyphs (Plugged In /
        // VRM Disconnected) — same URL quickVrmUrl and appendOpenVrmButton
        // already use, just triggered by a glyph click instead of a
        // dedicated button/link.
        function openVrmForEntry(entry) {
            const url = quickVrmUrl(entry);
            if (!url) {
                notifyError("Open VRM failed: no VRM link available for this unit");
                return;
            }
            const win = openBlankTab(url);
            if (!win) {
                notifyError("Pop-up blocked. Allow pop-ups for this site to open VRM.");
                return;
            }
            const line = "Opened VRM for " + (entry.unit || "unit");
            consoleLines.push(line);
            renderConsole(true);
            statusEl.textContent = line;
        }

        // Shared POST-and-log used by the quick buttons. Keeps them to a few
        // lines each and routes every outcome through the console + toasts.
        // afterSuccess is optional — a side effect beyond the console/toast
        // (currently just the Switch Uptime action refreshing the command
        // menu's own uptime line via applyFreshSwitchUptime).
        function quickFetch(btn, label, endpoint, formatter, afterSuccess, requestBody) {
            const original = btn.textContent;
            btn.disabled = true;
            btn.textContent = "…";
            const fetchInit = { method: "POST" };
            if (requestBody) {
                fetchInit.headers = { "Content-Type": "application/json" };
                fetchInit.body = JSON.stringify(requestBody);
            }
            fetch(endpoint, fetchInit)
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const text = formatter(data);
                    String(text).split(/\r?\n/).forEach(function (line) {
                        if (line) {
                            consoleLines.push(line);
                        }
                    });
                    renderConsole(true);
                    statusEl.textContent = String(text).split(/\r?\n/)[0] || (label + " complete");
                    if (afterSuccess) {
                        afterSuccess(data);
                    }
                })
                .catch(function (error) {
                    const message = label + " failed: " + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    btn.disabled = false;
                    btn.textContent = original;
                });
        }

        // The row-level "Validate" quick action, for a camera-outage row,
        // pings every camera on the ticket instead of the generic router/
        // compute check — a plain connectivity Validate tells a tech
        // nothing new here (the router and compute are already up; that's
        // WHY this ticket is camera-outage, not down full/offline compute),
        // while a camera ping is exactly the check this row exists for.
        // Mirrors the Validate submenu's own "Ping All Cameras" button
        // (same per-camera fetch, same state update) but re-renders the
        // list afterward instead of reaching into that submenu's own LED
        // elements, which don't exist yet this early in the row build.
        function runValidateCameraOutageQuickAction(entry, btn) {
            const members = entry.cameraGroupMembers || [entry];
            const original = btn.textContent;
            btn.disabled = true;
            btn.textContent = "…";
            statusEl.textContent = "Pinging " + members.length + " camera(s) on " + entry.unit + "...";
            Promise.all(members.map(function (member) {
                return fetch(
                    "/issues/ping-camera/" + encodeURIComponent(member.unit)
                        + "/" + encodeURIComponent(member.cameraTarget),
                    { method: "POST" }
                )
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        member.cameraUp = data.camera_up === true;
                        saveEntryState(member);
                        consoleLines.push(
                            member.cameraLabel + " is " + (member.cameraUp ? "up" : "down")
                                + ": " + member.unit
                        );
                    })
                    .catch(function (error) {
                        consoleLines.push(
                            member.cameraLabel + " ping failed: " + (error.message || error)
                        );
                    });
            })).then(function () {
                renderConsole(true);
                const upCount = members.filter(function (m) { return m.cameraUp === true; }).length;
                statusEl.textContent = entry.unit + " — " + upCount + "/" + members.length + " camera(s) up";
                renderList("camera_outage");
            }).finally(function () {
                btn.disabled = false;
                btn.textContent = original;
            });
        }

        function appendQuickActions(parent, entry, listId) {
            if (!entry || !entry.unit || !QUICK_ACTIONS.length) {
                return;
            }
            const wrap = document.createElement("span");
            wrap.className = "quick-actions";
            QUICK_ACTIONS.forEach(function (action) {
                if (action.show && !action.show(entry)) {
                    return;
                }
                let btn;
                if (action.href) {
                    const url = action.href(entry);
                    if (!url) {
                        return;
                    }
                    btn = document.createElement("a");
                    btn.href = url;
                    btn.target = "_blank";
                    btn.rel = "noopener noreferrer";
                } else {
                    btn = document.createElement("button");
                    btn.type = "button";
                    btn.addEventListener("click", function (event) {
                        event.preventDefault();
                        event.stopPropagation();
                        action.run(entry, btn, listId);
                    });
                }
                btn.className = "quick-btn";
                btn.textContent = action.label;
                btn.title = action.title || action.label;
                wrap.appendChild(btn);
            });
            if (wrap.childElementCount) {
                parent.appendChild(wrap);
            }
        }

        // ---- Power & Infra alarm glyph ----------------------------------------
        // A cheap, frequent poll of the scheduled Zabbix+VRM cache (never hits
        // either API itself — see /issues/power-infra-alerts/cached) lights up
        // a ⚠ on a unit's Commands button the moment either system flags it,
        // without waiting for someone to open the Power & Infra Alerts panel.
        let powerInfraAlarmedUnits = {};

        const ZABBIX_SEVERITY_LABELS = ["Not classified", "Info", "Warning", "Average", "High", "Disaster"];

        // Each raw problem here is a genuinely still-OPEN Zabbix problem
        // (combined_power_infra_alerts now goes through problem.get, not a
        // history scan — see that function's docstring), so "count" means
        // "N distinct trigger instances with this device+name are open
        // right now" (e.g. the same disk-latency check firing on several
        // mounts), and clock is each instance's own start time. Grouping
        // keeps the EARLIEST clock so "how long has this been happening"
        // reflects the longest-standing instance, not the newest.
        function dedupeZabbixProblems(problems) {
            const byKey = new Map();
            (problems || []).forEach(function (p) {
                const key = p.device + "|" + p.name;
                const existing = byKey.get(key);
                if (existing) {
                    existing.count += 1;
                    existing.severity = Math.max(existing.severity, p.severity);
                    if (p.clock && (!existing.firstClock || p.clock < existing.firstClock)) {
                        existing.firstClock = p.clock;
                    }
                } else {
                    byKey.set(key, {
                        device: p.device, name: p.name, severity: p.severity, count: 1,
                        firstClock: p.clock || null,
                    });
                }
            });
            return Array.from(byKey.values()).sort(function (a, b) { return b.severity - a.severity; });
        }

        function formatDurationSince(clockSeconds) {
            if (!clockSeconds) {
                return "";
            }
            const seconds = Math.max(0, Date.now() / 1000 - clockSeconds);
            if (seconds < 3600) {
                return Math.round(seconds / 60) + "m";
            }
            if (seconds < 86400) {
                return (seconds / 3600).toFixed(1) + "h";
            }
            return (seconds / 86400).toFixed(1) + "d";
        }

        // Shared by the glyph's hover title and its click toast, so hover and
        // click always agree on what "the alarm" actually is.
        function powerInfraAlertSummaryText(unit, info) {
            const lines = [];
            if (info.corroborated) {
                lines.push("Zabbix AND VRM both flag " + unit + " — likely a power issue, not just software/network.");
            }
            dedupeZabbixProblems(info.zabbixProblems).forEach(function (g) {
                const duration = formatDurationSince(g.firstClock);
                lines.push("Zabbix — " + g.device + ": " + g.name
                    + (g.count > 1 ? " (×" + g.count + ")" : "")
                    + " [" + (ZABBIX_SEVERITY_LABELS[g.severity] || g.severity) + "]"
                    + (duration ? " — open " + duration : ""));
            });
            if (info.vrmAlarm) {
                const soc = info.vrmAlarm.battery_soc ? (" — SOC " + info.vrmAlarm.battery_soc) : "";
                const age = info.vrmAlarm.last_seen_age_minutes != null
                    ? (" (seen " + info.vrmAlarm.last_seen_age_minutes + "m ago)")
                    : "";
                lines.push("VRM — " + info.vrmAlarm.installation_name + ": " + info.vrmAlarm.alarm_detail + soc + age);
            }
            return lines.join("\n");
        }

        // The status row (unit/subject header aside) has no border or
        // background of its own beyond the divider under it, so an empty
        // row would still leave a stray horizontal line with nothing above
        // it. Hidden whenever both glyphs are — called after either one
        // changes, since either alone can make the row go from empty to
        // non-empty or back.
        function refreshCommandMenuStatusRowVisibility(commandMenu) {
            const row = commandMenu.querySelector(".command-menu-status");
            if (!row) {
                return;
            }
            const alarmGlyph = row.querySelector(".command-alarm-glyph");
            const powerGlyph = row.querySelector(".command-power-glyph");
            const shadingGlyph = row.querySelector(".command-shading-glyph");
            const cameraOutageGlyph = row.querySelector(".command-camera-outage-glyph");
            const deadPanelGlyph = row.querySelector(".command-dead-panel-glyph");
            const batteryGlyph = row.querySelector(".command-battery-glyph");
            const vrmFreshnessGlyph = row.querySelector(".command-vrm-freshness-glyph");
            const forecastGlyph = row.querySelector(".command-forecast-glyph");
            const powerVsCellGlyph = row.querySelector(".command-power-vs-cell-glyph");
            // The connectivity LED (see renderList) has no hidden/shown
            // toggle of its own — once it's present at all, it's always
            // showing a real status (including the neutral idle color),
            // so it alone is enough to keep the row visible.
            const led = row.querySelector(".speaker-led");
            const anyVisible = (alarmGlyph && !alarmGlyph.hidden) || (powerGlyph && !powerGlyph.hidden)
                || (shadingGlyph && !shadingGlyph.hidden) || (cameraOutageGlyph && !cameraOutageGlyph.hidden)
                || (deadPanelGlyph && !deadPanelGlyph.hidden)
                || (batteryGlyph && !batteryGlyph.hidden) || (vrmFreshnessGlyph && !vrmFreshnessGlyph.hidden)
                || (forecastGlyph && !forecastGlyph.hidden) || (powerVsCellGlyph && !powerVsCellGlyph.hidden)
                || !!led;
            row.hidden = !anyVisible;
        }

        function applyPowerInfraGlyph(commandMenu) {
            const glyph = commandMenu.querySelector(".command-alarm-glyph");
            if (!glyph) {
                return;
            }
            const unit = String(commandMenu.dataset.unit || "").toUpperCase();
            const info = powerInfraAlarmedUnits[unit];
            if (!info) {
                glyph.hidden = true;
                glyph.title = "";
                refreshCommandMenuStatusRowVisibility(commandMenu);
                return;
            }
            glyph.hidden = false;
            glyph.classList.toggle("is-corroborated", !!info.corroborated);
            glyph.title = powerInfraAlertSummaryText(unit, info) + "\n(click for detail)";
            refreshCommandMenuStatusRowVisibility(commandMenu);
        }

        // ---- Camera outage glyph -----------------------------------------------
        // SNUC-Watch's own signature for "a camera has stopped sending
        // frames": its Linux check on the unit reads the capture buffer
        // directly (an actual camera outage looks different on disk than a
        // network problem does), so this pattern is specific enough to
        // trust as-is — no separate detection call needed, it's already
        // sitting in the same powerInfraAlarmedUnits cache the alarm glyph
        // reads. Percent/minute thresholds vary by device, so those are
        // wildcarded rather than pinned to the one example this was built
        // from ("...below 38% for 30 minutes").
        const CAMERA_OUTAGE_ALERT_PATTERN = /camera image buffer.*remained below.*for \d+ minutes/i;

        function cameraOutageProblemFromInfo(info) {
            const problems = (info && info.zabbixProblems) || [];
            return problems.find(function (problem) {
                return CAMERA_OUTAGE_ALERT_PATTERN.test(String((problem && problem.name) || ""));
            }) || null;
        }

        function applyCameraOutageGlyph(commandMenu) {
            const glyph = commandMenu.querySelector(".command-camera-outage-glyph");
            if (!glyph) {
                return;
            }
            const unit = String(commandMenu.dataset.unit || "").toUpperCase();
            const info = powerInfraAlarmedUnits[unit];
            const problem = cameraOutageProblemFromInfo(info);
            if (!problem) {
                glyph.hidden = true;
                glyph.title = "";
                refreshCommandMenuStatusRowVisibility(commandMenu);
                return;
            }
            glyph.hidden = false;
            let title = problem.name;
            // Only ever ADDS a named culprit, never a "checked, nothing
            // found" negative — a camera whose capture pipeline stalled
            // can still answer pings fine (see
            // unit_camera_outage_ping_check's own docstring), so a clean
            // sweep doesn't mean the alert is wrong, just that this
            // particular follow-up couldn't confirm which camera.
            const cached = cameraOutagePingChecker.cache[unit];
            if (cached && cached.downCameras && cached.downCameras.length) {
                title += "\n\nPing sweep found down: "
                    + cached.downCameras.map(function (camera) { return camera.label; }).join(", ");
            } else if (cached && cached.error) {
                // Distinct from "ran fine, found nothing" — e.g. the whole
                // unit being unreachable looked identical to a clean sweep
                // before this (reported live, RD3421, 2026-09-18: PVE was
                // unreachable, not that the cameras checked out fine).
                title += "\n\nPing sweep failed: " + cached.error;
            }
            // For Scrypted units this is the sharper signal — the Zabbix
            // alert is about the /mnt/ram buffer specifically, and this
            // reads that buffer directly per camera instead of just
            // testing reachability (see checkAndApplyCameraOutageGlyph).
            const ramCached = cameraOutageRamFolderChecker.cache[unit];
            if (ramCached && ramCached.failingCameras && ramCached.failingCameras.length) {
                title += "\n\nRAM folder not populating: "
                    + ramCached.failingCameras.map(function (camera) {
                        return camera.name + (camera.room ? " (" + camera.room + ")" : "");
                    }).join(", ");
            } else if (ramCached && ramCached.error) {
                title += "\n\nRAM folder check failed: " + ramCached.error;
            }
            title += "\n(click to open Scrypted/Platform)";
            glyph.title = title;
            refreshCommandMenuStatusRowVisibility(commandMenu);
        }

        const cameraOutagePingChecker = makeUnitGlyphChecker(
            "/issues/camera-outage-ping/", 5 * 60 * 1000,
            function (data) {
                return { downCameras: data.down_cameras || [] };
            },
            applyCameraOutageGlyph,
        );

        const cameraOutageRamFolderChecker = makeUnitGlyphChecker(
            "/issues/scrypted-ram-folder/", 5 * 60 * 1000,
            function (data) {
                return {
                    failingCameras: (data.cameras || []).filter(function (camera) {
                        return !camera.ok;
                    }),
                };
            },
            applyCameraOutageGlyph,
        );

        function checkAndApplyCameraOutageGlyph(commandMenu) {
            // The glyph itself is free (already-cached alarm data) and
            // shows immediately; the follow-up check is a real network
            // cost, so it only runs when there's actually an alert to
            // explain, not on every menu open regardless.
            applyCameraOutageGlyph(commandMenu);
            const unit = String(commandMenu.dataset.unit || "").toUpperCase();
            if (!cameraOutageProblemFromInfo(powerInfraAlarmedUnits[unit])) {
                return;
            }
            const entry = commandMenuEntries.get(commandMenu);
            if (entry && entry.hasScrypted) {
                cameraOutageRamFolderChecker.checkAndApply(commandMenu);
            } else {
                cameraOutagePingChecker.checkAndApply(commandMenu);
            }
        }

        // ---- Power vs Cell Outage glyph ---------------------------------------
        // Same bulk-cache-plus-periodic-poll shape as powerInfraAlarmedUnits
        // above, deliberately NOT the lazy on-open-fetch pattern the
        // power/shading/dead-panel/forecast glyphs use — the underlying
        // check is SSH-based (see unit_power_vs_cell_outage), so doing it
        // per command-menu-open would hammer a switch every time someone
        // clicked a row. Instead the server sweeps every current Up Steady
        // unit on its own schedule (see POWER_VS_CELL_OUTAGE_REFRESH_SECONDS)
        // and this just polls the cheap cached result.
        let powerVsCellAlarmedUnits = {};

        function powerVsCellSummaryText(unit, info) {
            return (info.summary || "") + "\n(click to re-check now)";
        }

        function applyPowerVsCellGlyph(commandMenu) {
            const glyph = commandMenu.querySelector(".command-power-vs-cell-glyph");
            if (!glyph) {
                return;
            }
            const unit = String(commandMenu.dataset.unit || "").toUpperCase();
            const info = powerVsCellAlarmedUnits[unit];
            // Only power_outage/cell_outage are worth a glyph — inconclusive
            // and no_recent_outage are "checked, nothing to say," same
            // convention as the shading/dead-panel/VRM-freshness glyphs.
            if (!info || (info.verdict !== "power_outage" && info.verdict !== "cell_outage")) {
                glyph.hidden = true;
                glyph.title = "";
                refreshCommandMenuStatusRowVisibility(commandMenu);
                return;
            }
            glyph.hidden = false;
            glyph.textContent = info.verdict === "power_outage" ? "⚡" : "📶";
            glyph.className = "command-power-vs-cell-glyph is-" + info.verdict;
            glyph.title = powerVsCellSummaryText(unit, info);
            refreshCommandMenuStatusRowVisibility(commandMenu);
        }

        // Same finding, shown on the collapsed row itself — see
        // .power-vs-cell-row-badge's own comment for why. Every rendered
        // row's badge carries its unit on dataset.unit so a bulk update
        // (poll or manual sweep) can re-apply to all of them at once, the
        // same way applyPowerVsCellGlyph re-applies to every open command
        // menu.
        //
        // Always shown (Andrew's request, 2026-10-02): it's the way into the
        // Power vs Cell graphs modal, so a unit the sweep found nothing
        // definite for still gets a grey ∿ that opens the modal and runs
        // the check there (see openPowerVsCellRowDetail).
        function applyPowerVsCellRowBadge(badgeEl) {
            const unit = String(badgeEl.dataset.unit || "").toUpperCase();
            const info = unit ? powerVsCellAlarmedUnits[unit] : null;
            badgeEl.hidden = false;
            if (!info || (info.verdict !== "power_outage" && info.verdict !== "cell_outage")) {
                badgeEl.textContent = "∿";
                badgeEl.className = "power-vs-cell-row-badge is-none";
                // Unit first: a multi-unit ticket shows one ∿ per unit.
                const why = unit + " — " + (!info || !info.verdict
                    ? "Power vs Cell: not checked yet."
                    : info.verdict === "no_recent_outage"
                        ? "Power vs Cell: no recent outage window found."
                        : "Power vs Cell: inconclusive.");
                badgeEl.title = why + "\n(click to open the graphs and run the check)";
                syncUnitOpenButtonTitle(badgeEl);
                return;
            }
            badgeEl.textContent = info.verdict === "power_outage" ? "⚡" : "📶";
            badgeEl.className = "power-vs-cell-row-badge is-" + info.verdict;
            badgeEl.title = (info.summary || "") + "\n(click to view graph + uptime)";
            syncUnitOpenButtonTitle(badgeEl);
        }

        // The row's unit button (.unit-open-btn) wraps its badge — its own
        // tooltip leads with what the click does, then the badge's verdict.
        function syncUnitOpenButtonTitle(badgeEl) {
            const btn = badgeEl.closest(".unit-open-btn");
            if (!btn) {
                return;
            }
            const unit = btn.dataset.unit || "";
            btn.title = "Open " + unit + " — graphs, verdict, notes and commands\n"
                + String(badgeEl.title || "").replace(/\n\(click[^)]*\)$/, "");
        }

        // "3d 4h 12m" — a plain compact duration, for the toast/console
        // detail text only (not the device's own pre-formatted
        // switch_uptime_text, which is already stale by the time anyone
        // reads it — see openPowerVsCellRowDetail).
        function formatUptimeDuration(seconds) {
            if (seconds == null || seconds < 0 || !isFinite(seconds)) {
                return "unknown";
            }
            const days = Math.floor(seconds / 86400);
            const hours = Math.floor((seconds % 86400) / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const parts = [];
            if (days) {
                parts.push(days + "d");
            }
            if (days || hours) {
                parts.push(hours + "h");
            }
            parts.push(minutes + "m");
            return parts.join(" ");
        }

        // The sweep's own switch_uptime_text is a snapshot from whenever
        // the sweep last ran — possibly hours ago — so "current uptime"
        // here is extrapolated from it (switch_uptime_seconds + elapsed
        // since checked_at) rather than a fresh SSH round trip, same
        // "good enough without another expensive read" tradeoff as the
        // sweep's own cache-then-poll design.
        function powerVsCellUptimeDetailText(info) {
            if (info.switch_uptime_seconds == null || info.checked_at == null) {
                return "";
            }
            const checkedDate = new Date(info.checked_at * 1000);
            const elapsedSeconds = Math.max(0, (Date.now() - info.checked_at * 1000) / 1000);
            const currentUptimeSeconds = info.switch_uptime_seconds + elapsedSeconds;
            return "Switch uptime when checked (" + checkedDate.toLocaleString() + "): "
                + formatUptimeDuration(info.switch_uptime_seconds)
                + "\nCurrent uptime (est.): " + formatUptimeDuration(currentUptimeSeconds);
        }

        // The always-visible uptime line (NOT alert-gated, unlike the glyph
        // above it reuses the same cache for) — the Up Steady sweep already
        // SSHes every unit's switch for this as a side effect of
        // unit_power_vs_cell_outage, so showing it here on open is free:
        // no new fetch, just reading powerVsCellAlarmedUnits. Silent for
        // any unit the sweep has no entry for (outside Up Steady, or before
        // the sweep's first pass).
        // A switch that's been up this long hasn't rebooted for anything —
        // a power blip, a firmware nudge — in weeks, which is itself worth
        // flagging on sight rather than only when it finally drops offline.
        // Andrew's own thresholds, 2026-09-17. Purely a color on the
        // existing uptime line, not a new check of its own.
        const SWITCH_UPTIME_WARN_DAYS = 20;
        const SWITCH_UPTIME_DANGER_DAYS = 50;

        function applyPowerVsCellUptimeLine(commandMenu) {
            const line = commandMenu.querySelector(".command-menu-uptime");
            if (!line) {
                return;
            }
            const unit = String(commandMenu.dataset.unit || "").toUpperCase();
            const info = powerVsCellAlarmedUnits[unit];
            if (!info || info.switch_uptime_seconds == null || info.checked_at == null) {
                line.hidden = true;
                line.textContent = "";
                line.title = "";
                line.className = "command-menu-uptime";
                return;
            }
            const elapsedSeconds = Math.max(0, (Date.now() - info.checked_at * 1000) / 1000);
            const currentUptimeSeconds = info.switch_uptime_seconds + elapsedSeconds;
            const uptimeDays = currentUptimeSeconds / 86400;
            line.hidden = false;
            line.textContent = "Switch uptime: " + formatUptimeDuration(currentUptimeSeconds) + " (est.)";
            line.title = powerVsCellUptimeDetailText(info) + "\nClick to refresh";
            line.className = "command-menu-uptime" + (
                uptimeDays >= SWITCH_UPTIME_DANGER_DAYS ? " is-danger"
                    : uptimeDays >= SWITCH_UPTIME_WARN_DAYS ? " is-warn" : ""
            );
        }

        // Same SWITCH_UPTIME_WARN_DAYS/DANGER_DAYS tiers as the command
        // menu's own uptime line above, applied to the Graphs modal's
        // info line instead — shared by every opener that has switch-uptime
        // info to show there (openPowerVsCellRowDetail's own "View Graph"
        // and the plain Network Latency Graphs button). Caller must call
        // openGraphsModal (or otherwise reset graphsInfoLineEl's class)
        // first — this only ever adds a tier class on top.
        function applyGraphsInfoLineUptimeTier(info) {
            if (!info || info.switch_uptime_seconds == null || info.checked_at == null) {
                return;
            }
            const elapsedSeconds = Math.max(0, (Date.now() - info.checked_at * 1000) / 1000);
            const uptimeDays = (info.switch_uptime_seconds + elapsedSeconds) / 86400;
            if (uptimeDays >= SWITCH_UPTIME_DANGER_DAYS) {
                graphsInfoLineEl.classList.add("is-danger");
            } else if (uptimeDays >= SWITCH_UPTIME_WARN_DAYS) {
                graphsInfoLineEl.classList.add("is-warn");
            }
        }

        // Feeds a fresh switch-uptime reading (the backend already stashed
        // it in the same cache unit_power_vs_cell_outage reads — see
        // issues_robofiber_uptime's own comment) back into
        // powerVsCellAlarmedUnits, so the command menu's own uptime line
        // (applyPowerVsCellUptimeLine) updates right away instead of
        // showing a pre-reboot number until the next scheduled sweep.
        // Shared by every "Switch Uptime" button — the QUICK_ACTIONS row
        // one, populateUnitToolsCommandMenu's, and renderList's own inline
        // copy — since none of them otherwise touch this cache at all.
        function applyFreshSwitchUptime(unit, data, commandMenu) {
            if (data.switch_uptime_seconds == null) {
                return;
            }
            const key = String(unit || "").toUpperCase();
            if (!key) {
                return;
            }
            powerVsCellAlarmedUnits[key] = Object.assign(
                {}, powerVsCellAlarmedUnits[key] || {},
                {
                    switch_uptime_seconds: data.switch_uptime_seconds,
                    switch_up_since: data.switch_up_since,
                    checked_at: Date.now() / 1000,
                }
            );
            if (commandMenu) {
                applyPowerVsCellUptimeLine(commandMenu);
                applyPowerVsCellGlyph(commandMenu);
            }
        }

        // Row badge click — opens Network Latency Graphs with the loss
        // window that drove the verdict highlighted (same "View Graph"
        // pattern as the shading/dead-panel Diagnostic Header), and surfaces
        // the uptime detail as both a toast and a console line since the
        // graph modal has nowhere of its own to show it.
        // Loss window to shade, plus "switch came back up" / "ticket opened"
        // markers, from one Power vs Cell result. The two markers can land
        // far from the loss window (see the "since rebooted again for an
        // unrelated reason" verdict text), which is exactly when seeing all
        // three on one graph matters most. ticket_created_at is only there
        // when the server resolved the ticket in ERP (issue_id passed and
        // looked up) — see unit_power_vs_cell_outage.
        function powerVsCellGraphOverlays(info) {
            let highlightRange = null;
            if (info.loss_window_start != null && info.loss_window_end != null) {
                highlightRange = {
                    startMs: info.loss_window_start * 1000,
                    endMs: info.loss_window_end * 1000,
                    label: info.verdict === "power_outage" ? "power outage window"
                        : info.verdict === "cell_outage" ? "cell outage window" : "loss window",
                };
            }
            const markers = [];
            if (info.switch_up_since != null) {
                markers.push({ tMs: info.switch_up_since * 1000, label: "switch came back up" });
            }
            if (info.ticket_created_at != null) {
                markers.push({
                    tMs: info.ticket_created_at * 1000,
                    label: "ticket opened",
                    kind: "ticket-created",
                });
            }
            return { highlightRange: highlightRange, markers: markers };
        }

        // Every unit a ticket names, in subject order (RD3079(MU6006)
        // RD3231(MU6007) -> ["RD3079", "RD3231"]), with the row's own unit
        // first if the subject parser missed it. Drives the per-unit row
        // badges and the modal's unit switcher.
        function ticketPowerVsCellUnits(entry) {
            const units = unitsFromTicketSubject((entry && (entry.ticketSubject || entry.subject)) || "")
                .map(function (token) { return token.unit; });
            const own = String((entry && entry.unit) || "").toUpperCase();
            if (own && units.indexOf(own) === -1) {
                units.unshift(own);
            }
            return units;
        }

        // Unit switcher under the Graphs modal's title, for a ticket that
        // names more than one unit: one button per unit with its own verdict
        // glyph; clicking reopens the modal on that unit (same ticket, same
        // R/W/S wiring). Hidden for single-unit tickets and other openers.
        const graphsUnitSwitchEl = document.getElementById("graphs_unit_switch");
        let graphsUnitSwitchState = null;

        function renderGraphsUnitSwitch(currentUnit, units, reopen) {
            graphsUnitSwitchState = { currentUnit: currentUnit, units: units, reopen: reopen };
            if (!graphsUnitSwitchEl) {
                return;
            }
            graphsUnitSwitchEl.innerHTML = "";
            graphsUnitSwitchEl.hidden = units.length < 2;
            if (units.length < 2) {
                return;
            }
            const label = document.createElement("span");
            label.className = "graphs-unit-switch-label";
            label.textContent = "This ticket lists " + units.length + " units:";
            graphsUnitSwitchEl.appendChild(label);
            units.forEach(function (unit) {
                const info = powerVsCellAlarmedUnits[unit];
                const glyph = info && info.verdict === "power_outage" ? "⚡"
                    : info && info.verdict === "cell_outage" ? "📶" : "∿";
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = "graphs-unit-switch-btn";
                const isCurrent = unit === currentUnit;
                btn.setAttribute("aria-pressed", isCurrent ? "true" : "false");
                btn.textContent = unit + " " + glyph;
                btn.title = isCurrent ? "Showing " + unit
                    : "Switch the graphs, verdict and commands to " + unit;
                if (!isCurrent) {
                    btn.addEventListener("click", function () { reopen(unit); });
                }
                graphsUnitSwitchEl.appendChild(btn);
            });
        }

        function isDefinitePowerVsCell(info) {
            return !!(info && (info.verdict === "power_outage" || info.verdict === "cell_outage"));
        }

        // Which unit/ticket the open Graphs modal is showing a Power vs Cell
        // verdict for — set only when opened from the row badge, cleared on
        // every other open (openGraphsModal). graphsPowerVsCellRequestId
        // drops a result that lands after the modal moved on.
        let graphsPowerVsCellContext = null;
        let graphsPowerVsCellRequestId = 0;

        // Row badge click — opens Network Latency Graphs for any ticket.
        // With a power/cell verdict from the sweep, the loss window is
        // shaded and the verdict shown straight away. Without one (never
        // checked, inconclusive, no recent outage), the modal opens on the
        // plain graphs and runs the single-unit check in the background,
        // filling the verdict in when it lands (Andrew's request,
        // 2026-10-02: the modal must be reachable from every ticket).
        function openPowerVsCellRowDetail(unit, subject, ticketUrl, sourceEntry, sourceListId) {
            const key = String(unit || "").toUpperCase();
            const info = powerVsCellAlarmedUnits[key] || null;
            const overlays = info ? powerVsCellGraphOverlays(info) : { highlightRange: null, markers: [] };
            const uptimeText = info ? powerVsCellUptimeDetailText(info) : "";
            // Uptime is also shown in the modal itself (graphs_info_line), not
            // just the toast/console line — those scroll away, and it's the
            // number a tech re-reads while looking at this graph.
            openGraphsModal(unit, "network", subject || "", overlays.highlightRange, null, overlays.markers, uptimeText, ticketUrl || "");
            if (info) {
                applyGraphsInfoLineUptimeTier(info);
            }
            if (sourceEntry) {
                setGraphsRwsSource(sourceEntry, sourceListId);
            }
            graphsPowerVsCellContext = {
                unit: key,
                issueId: (sourceEntry && (sourceEntry.issueId || sourceEntry.issue_id)) || "",
            };
            renderGraphsUnitSwitch(
                key,
                ticketPowerVsCellUnits(sourceEntry || { unit: key, ticketSubject: subject }),
                function (otherUnit) {
                    openPowerVsCellRowDetail(otherUnit, subject, ticketUrl, sourceEntry, sourceListId);
                }
            );
            if (graphsVerdictRecheckBtn) {
                graphsVerdictRecheckBtn.hidden = false;
            }
            if (!isDefinitePowerVsCell(info)) {
                runGraphsPowerVsCellCheck();
                return;
            }
            renderGraphsVerdict(info);
            const message = (info.summary || "") + (uptimeText ? "\n" + uptimeText : "");
            // Main Stdout only — the modal already shows this finding.
            consoleEchoMuted = true;
            consoleLines.push(message);
            consoleEchoMuted = false;
            renderConsole(true);
            // Auto-dismisses after 5s unless moused over — the finding is
            // already open in the graph behind it, so this toast is a
            // convenience, not the only place to read it.
            notify(message, info.status === "warn" ? "error" : "info", { autoDismissIfNotHoveredMs: 5000 });
        }

        // Single-unit Power vs Cell check for the open modal (same endpoint
        // as the command menu's re-check). Read-only: an SSH read of the
        // switch's uptime plus Zabbix ping history. The result also updates
        // the shared cache, so the row badge and command menu pick it up.
        function runGraphsPowerVsCellCheck() {
            const ctx = graphsPowerVsCellContext;
            if (!ctx) {
                return;
            }
            const requestId = ++graphsPowerVsCellRequestId;
            renderGraphsVerdictStatus("pending", "Checking power vs cell for " + ctx.unit + "...");
            fetch("/issues/power-vs-cell-outage/" + encodeURIComponent(ctx.unit), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(ctx.issueId ? { issue_id: ctx.issueId } : {}),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    powerVsCellAlarmedUnits[ctx.unit] = data;
                    document.querySelectorAll(".power-vs-cell-row-badge").forEach(function (badgeEl) {
                        if (String(badgeEl.dataset.unit || "").toUpperCase() === ctx.unit) {
                            applyPowerVsCellRowBadge(badgeEl);
                        }
                    });
                    consoleEchoMuted = true; // the verdict line shows it in the modal
                    consoleLines.push(data.summary || (ctx.unit + " — " + data.verdict));
                    consoleEchoMuted = false;
                    renderConsole(true);
                    if (requestId !== graphsPowerVsCellRequestId) {
                        return; // modal closed or moved on
                    }
                    applyPowerVsCellInfoToGraphs(data);
                })
                .catch(function (error) {
                    if (requestId !== graphsPowerVsCellRequestId) {
                        return;
                    }
                    renderGraphsVerdictStatus("error",
                        "Power vs Cell check failed for " + ctx.unit + ": " + ((error && error.message) || error));
                });
        }

        // A result that landed with the modal already open: update the
        // verdict, uptime line, shading and markers in place (widening the
        // Window if the loss window is older than it shows), without
        // reopening — so notes, search and the Output pane are kept.
        function applyPowerVsCellInfoToGraphs(info) {
            const overlays = powerVsCellGraphOverlays(info);
            graphsHighlightRange = overlays.highlightRange;
            graphsMarkers = overlays.markers;
            const uptimeText = powerVsCellUptimeDetailText(info);
            if (uptimeText) {
                graphsInfoLine = uptimeText;
                renderGraphsInfoLine();
                graphsInfoLineEl.className = "graphs-info-line";
                applyGraphsInfoLineUptimeTier(info);
            }
            renderGraphsVerdict(info);
            if (graphsUnitSwitchState) { // new glyph for this unit's button
                renderGraphsUnitSwitch(graphsUnitSwitchState.currentUnit,
                    graphsUnitSwitchState.units, graphsUnitSwitchState.reopen);
            }
            widenGraphsWindowToCover(GRAPH_MODES[graphsMode], true);
            if (overlays.highlightRange || overlays.markers.length) {
                loadGraphs();
            }
        }

        if (graphsVerdictRecheckBtn) {
            graphsVerdictRecheckBtn.addEventListener("click", runGraphsPowerVsCellCheck);
        }

        // Shared body for every "lazy, on-open, per-unit POST, cached with
        // a TTL, de-duped while in flight" glyph check below — the plug
        // (+battery+VRM-freshness piggybacked on the same fetch), shading,
        // dead-panel and forecast glyphs each used to hand-roll this same
        // cache/inFlight/fetch/finally shape, differing only in the
        // endpoint, TTL, how a response maps onto a cache entry, and what
        // "apply from cache" does to the DOM. Body/POST subject and the
        // null-on-failure fallback are the one behavior every one of them
        // already shared, so that's baked in here rather than passed in.
        //
        // Returns {cache, checkAndApply}; the caller keeps its own
        // `applyXFromCache(commandMenu)` function (unchanged — it reads
        // `cache[unit]` itself, exactly as before, and is also the one
        // spot that may need calling from elsewhere with no fresh fetch —
        // see applyPowerGlyphFromCache's own external call site) and
        // passes it in so this factory can call it after every fetch
        // settles.
        function makeUnitGlyphChecker(endpoint, cacheMs, mapResponse, applyFromCache) {
            const cache = {};
            const inFlight = {};

            function checkAndApply(commandMenu) {
                const unit = String(commandMenu.dataset.unit || "").toUpperCase();
                if (!unit || unit === "MENU") {
                    return;
                }
                const cached = cache[unit];
                if (cached && (Date.now() - cached.fetchedAt) < cacheMs) {
                    applyFromCache(commandMenu);
                    return;
                }
                if (inFlight[unit]) {
                    return;
                }
                inFlight[unit] = true;
                const entry = commandMenuEntries.get(commandMenu);
                const subject = (entry && (entry.ticketSubject || entry.subject)) || "";
                fetch(endpoint + encodeURIComponent(unit), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ subject: subject }),
                })
                    .then(function (response) { return response.json(); })
                    .then(function (data) {
                        // A failed check (SSH/login/connect error) used to
                        // collapse to the exact same {status:null} shape as
                        // "ran fine, found nothing" — indistinguishable in
                        // the tooltip, so "PVE is unreachable" looked
                        // identical to "checked, all clear" (reported live,
                        // RD3421, 2026-09-18). Carrying the error through
                        // lets a caller's applyFromCache show it instead of
                        // staying silent.
                        cache[unit] = (data && data.ok)
                            ? Object.assign(mapResponse(data), { fetchedAt: Date.now() })
                            : { status: null, error: (data && data.error) || "check failed", fetchedAt: Date.now() };
                    })
                    .catch(function (error) {
                        cache[unit] = {
                            status: null,
                            error: (error && error.message) || String(error),
                            fetchedAt: Date.now(),
                        };
                    })
                    .finally(function () {
                        delete inFlight[unit];
                        applyFromCache(commandMenu);
                    });
            }

            return { cache: cache, checkAndApply: checkAndApply };
        }

        // Lazy, on-open power-status check (🔌 glyph) — deliberately NOT a
        // fleet-wide poll like the alarm glyph above, since a real check
        // costs a VRM round trip (sometimes two, if it falls back to the
        // solar-ceiling inference) — only fires for a unit whose menu
        // someone actually opened, and caches briefly so reopening the same
        // unit's menu right after doesn't refetch.
        //
        // Plugged-in or not, full stop — the only two real verdicts. Every
        // other status _ac_power_status_from_diagnostics can return
        // (uncertain/unknown/stale/no_charger_hardware) means "couldn't
        // actually tell," so none of them get a glyph; a tech seeing this
        // dot at all should be able to trust it means one of the two
        // states, not squint at a color/badge combo to work out which kind
        // of "not sure" it is. A null status (fetch failed outright, or the
        // unit has no VRM entry at all) stays hidden the same way.
        const POWER_GLYPH_CACHE_MS = 5 * 60 * 1000;
        const POWER_GLYPH_VISIBLE_STATUSES = {
            present: true, not_detected: true,
        };

        // Same 4-tier coloring as the 20%-low-battery reference already
        // drawn on the SOC graph (see renderGraphs) — 20% is the line
        // between "low" and "low-medium" here too, just extended to a
        // full green/yellow/orange/red scale instead of one cutoff.
        function batterySocTier(percent) {
            if (percent >= 60) {
                return "high";
            }
            if (percent >= 40) {
                return "medium";
            }
            if (percent >= 20) {
                return "low-medium";
            }
            return "low";
        }

        function applyBatteryGlyphFromCache(commandMenu, cached) {
            const glyph = commandMenu.querySelector(".command-battery-glyph");
            if (!glyph) {
                return;
            }
            // "When available" — plenty of real installations report
            // battery voltage/current but no percentage SOC at all (a
            // Hub-1/Cerbo GX combo, checked live this session); this stays
            // hidden rather than showing a misleading "0%" or a dash.
            if (!cached || cached.batterySocPercent == null) {
                glyph.hidden = true;
                return;
            }
            const percent = cached.batterySocPercent;
            const tier = batterySocTier(percent);
            glyph.hidden = false;
            glyph.className = "command-battery-glyph is-" + tier;
            glyph.textContent = Math.round(percent) + "%";
            glyph.title = "Battery " + percent.toFixed(0) + "% (" + tier.replace("-", " ") + ")\n(click to open VRM)";
        }

        function applyVrmFreshnessGlyphFromCache(commandMenu, cached) {
            const glyph = commandMenu.querySelector(".command-vrm-freshness-glyph");
            if (!glyph) {
                return;
            }
            // Alert-only, same convention as shading/dead-panel — "fresh"/
            // "aging" is normal and shows nothing; "unknown" usually means
            // this unit has no VRM installation at all (nothing IS
            // disconnected, there's just nothing to read), so that stays
            // quiet too rather than reading as a false alarm.
            const freshness = cached && cached.vrmFreshness;
            if (freshness !== "stale" && freshness !== "disconnected") {
                glyph.hidden = true;
                return;
            }
            glyph.hidden = false;
            glyph.className = "command-vrm-freshness-glyph is-" + freshness;
            glyph.title = "VRM data is " + freshness
                + (cached.vrmLastSeenSecondsAgo != null ? " (" + formatAgeShort(cached.vrmLastSeenSecondsAgo) + " old)" : "")
                + "\n(click to open VRM)";
        }

        function applyPowerGlyphFromCache(commandMenu) {
            const glyph = commandMenu.querySelector(".command-power-glyph");
            const unit = String(commandMenu.dataset.unit || "").toUpperCase();
            const cached = powerGlyphChecker.cache[unit];
            applyBatteryGlyphFromCache(commandMenu, cached);
            applyVrmFreshnessGlyphFromCache(commandMenu, cached);
            if (!glyph) {
                refreshCommandMenuStatusRowVisibility(commandMenu);
                return;
            }
            if (!cached || !POWER_GLYPH_VISIBLE_STATUSES[cached.status]) {
                glyph.hidden = true;
                refreshCommandMenuStatusRowVisibility(commandMenu);
                return;
            }
            glyph.hidden = false;
            glyph.className = "command-power-glyph is-" + cached.status;
            let title = cached.summary || ("Power status: " + cached.status);
            // Point at the ⚠ glyph rather than repeating its detail here —
            // one line is enough to say "these two don't necessarily
            // agree, go look," without duplicating the whole alert text in
            // two tooltips that would drift out of sync with each other.
            if (powerInfraAlarmedUnits[unit]) {
                title += "\n⚠ Zabbix/VRM also has an active alert on this unit — see the ⚠ for detail";
            }
            title += "\n(click to open VRM)";
            glyph.title = title;
            refreshCommandMenuStatusRowVisibility(commandMenu);
        }

        // One fetch, three glyphs — battery SOC and VRM freshness are
        // already part of this same response (unit_power_status's snapshot
        // carries them regardless, since the AC-power check itself needs
        // vrm_freshness to decide "present" vs "unknown"), so there's no
        // separate checker for either.
        const powerGlyphChecker = makeUnitGlyphChecker(
            "/issues/power-status/", POWER_GLYPH_CACHE_MS,
            function (data) {
                return {
                    status: data.ac_power_status,
                    summary: data.summary,
                    batterySocPercent: data.battery_soc_percent,
                    vrmFreshness: data.vrm_freshness,
                    vrmLastSeenSecondsAgo: data.vrm_last_seen_seconds_ago,
                };
            },
            applyPowerGlyphFromCache,
        );

        function checkAndApplyPowerGlyph(commandMenu) {
            powerGlyphChecker.checkAndApply(commandMenu);
        }

        // Same lazy on-open, cached-per-unit pattern as the plug glyph
        // above — a real check is two VRM /stats calls (a multi-day
        // ceiling window, a recent window), so this only ever fires for a
        // unit whose menu someone actually opened. Unlike the plug glyph,
        // "clear" and "unknown" never show anything — see the CSS/creation
        // comments for why this one is alert-only.
        const SHADING_GLYPH_CACHE_MS = 5 * 60 * 1000;

        function applyShadingGlyphFromCache(commandMenu) {
            const glyph = commandMenu.querySelector(".command-shading-glyph");
            if (!glyph) {
                return;
            }
            const unit = String(commandMenu.dataset.unit || "").toUpperCase();
            const cached = shadingGlyphChecker.cache[unit];
            if (!cached || cached.status !== "shaded") {
                glyph.hidden = true;
                refreshCommandMenuStatusRowVisibility(commandMenu);
                renderDiagnosticHeader(commandMenu);
                return;
            }
            glyph.hidden = false;
            glyph.title = (cached.summary || "Possible shading detected") + "\n(click to view solar graphs)";
            refreshCommandMenuStatusRowVisibility(commandMenu);
            renderDiagnosticHeader(commandMenu);
        }

        const shadingGlyphChecker = makeUnitGlyphChecker(
            "/issues/shading-status/", SHADING_GLYPH_CACHE_MS,
            function (data) {
                return {
                    status: data.shading_status,
                    summary: data.summary,
                    confidence: data.shading_confidence,
                    worstHourUtc: data.shading_worst_hour_utc,
                    windowUtc: data.shading_window_utc,
                };
            },
            applyShadingGlyphFromCache,
        );

        function checkAndApplyShadingGlyph(commandMenu) {
            shadingGlyphChecker.checkAndApply(commandMenu);
        }

        // Same lazy on-open, cached-per-unit, alert-only pattern as the
        // shading glyph above — a real check is a /stats call over
        // history_days plus one over recent_days (see detect_dead_panel).
        const DEAD_PANEL_GLYPH_CACHE_MS = 5 * 60 * 1000;

        function applyDeadPanelGlyphFromCache(commandMenu) {
            const glyph = commandMenu.querySelector(".command-dead-panel-glyph");
            if (!glyph) {
                return;
            }
            const unit = String(commandMenu.dataset.unit || "").toUpperCase();
            const cached = deadPanelGlyphChecker.cache[unit];
            if (!cached || cached.status !== "dead_panel") {
                glyph.hidden = true;
                refreshCommandMenuStatusRowVisibility(commandMenu);
                renderDiagnosticHeader(commandMenu);
                return;
            }
            glyph.hidden = false;
            glyph.title = (cached.summary || "Possible dead/underperforming panel") + "\n(click to view solar graphs)";
            refreshCommandMenuStatusRowVisibility(commandMenu);
            renderDiagnosticHeader(commandMenu);
        }

        const deadPanelGlyphChecker = makeUnitGlyphChecker(
            "/issues/dead-panel-status/", DEAD_PANEL_GLYPH_CACHE_MS,
            function (data) {
                return {
                    status: data.dead_panel_status,
                    summary: data.summary,
                    confidence: data.dead_panel_confidence,
                    recentDays: (data.dead_panel_info && data.dead_panel_info.recent_days) || null,
                };
            },
            applyDeadPanelGlyphFromCache,
        );

        function checkAndApplyDeadPanelGlyph(commandMenu) {
            deadPanelGlyphChecker.checkAndApply(commandMenu);
        }

        // A 5-day cloud-cover date range for a hover tooltip — shared
        // between the command menu's forecast glyph and the Battery
        // Outlook report's own rows, since both read the exact same
        // forecast shape (_fetch_open_meteo_daily_outlook's day list).
        function forecastTooltipText(forecast) {
            if (!forecast || !forecast.length) {
                return "No forecast available";
            }
            return forecast.map(function (day) {
                let dateLabel = day.date || "?";
                if (day.date) {
                    const parsed = new Date(day.date + "T00:00:00");
                    if (!isNaN(parsed.getTime())) {
                        dateLabel = parsed.toLocaleDateString(undefined, {
                            weekday: "short", month: "short", day: "numeric",
                        });
                    }
                }
                const cover = (day.cloud_cover_mean != null)
                    ? Math.round(day.cloud_cover_mean) + "% cloud cover"
                    : "";
                return dateLabel + ": " + (day.conditions || "?")
                    + (cover ? " (" + cover + ")" : "")
                    + (day.cloudy ? " — cloudy" : "");
            }).join("\n");
        }

        // Info glyph, not alert-only like shading/dead-panel/VRM-freshness
        // above — the forecast itself is worth seeing any time it's
        // available, not just when it implies a problem (the risk verdict,
        // separately, is what actually flags something worth a look).
        // Shared by both the command menu's own .command-forecast-glyph
        // (styled directly, like .command-battery-glyph) and the Battery
        // Outlook report row's freestanding .forecast-glyph element.
        // "Forecast for Desert Retreat Oasis Clubhouse (33.765, -116.261) —
        // the site's own GPS". The forecast is taken at the site's (or
        // trailer's) coordinates, which can be far from the ticket's region
        // code — an "LAX" ticket out in the Coachella Valley gets desert
        // weather, not LA's — so the tooltip says where it's for.
        function forecastLocationText(location) {
            if (!location || (!location.name && location.lat == null)) {
                return "";
            }
            const coords = (location.lat != null && location.lon != null)
                ? " (" + Number(location.lat).toFixed(3) + ", " + Number(location.lon).toFixed(3) + ")"
                : "";
            const source = location.source === "site" ? " — the site's own GPS"
                : location.source === "trailer" ? " — the trailer's own GPS" : "";
            return "Forecast for " + (location.name || "this unit") + coords + source;
        }

        // Pulls the location fields off a /issues/battery-outlook response
        // or a Battery Outlook report row.
        function forecastLocationFromData(data) {
            return data ? {
                name: data.location || "",
                lat: data.location_lat,
                lon: data.location_lon,
                source: data.location_source || "",
            } : null;
        }

        function applyForecastGlyphText(glyph, forecast, cloudyDays, forecastDays, label, location) {
            glyph.textContent = "☁ " + (
                cloudyDays != null && forecastDays != null
                    ? (cloudyDays + "/" + forecastDays)
                    : "5-day"
            );
            // Caught live: a pinned/screenshotted forecast toast had no
            // unit or ticket on it at all — nothing to tell one from
            // another once it's cropped into a screenshot on its own.
            const locationText = forecastLocationText(location);
            const header = (label ? (label + "\n") : "") + (locationText ? (locationText + "\n") : "");
            const detailText = header + "Next " + (forecastDays || 5) + " day(s):\n" + forecastTooltipText(forecast);
            glyph.title = detailText + "\n\n(Click to pin this so you can screenshot it.)";
            // Stashed on the element (not just closed over) so the click
            // handler below — wired once — always reads whatever the most
            // recent refresh put here, not whatever forecast was current
            // the first time this glyph was built.
            glyph._forecastDetailText = detailText;
            if (!glyph.dataset.forecastClickWired) {
                glyph.dataset.forecastClickWired = "1";
                glyph.addEventListener("click", function (event) {
                    event.stopPropagation();
                    // A native `title` tooltip disappears on almost any
                    // keypress — including the Shift in Win+Shift+S — so it
                    // can never survive long enough to screenshot. This
                    // toast only closes on the × click, so it will.
                    notify(glyph._forecastDetailText, null, { persist: true });
                });
            }
        }

        function forecastGlyphElement(forecast, cloudyDays, forecastDays, label, location) {
            const glyph = document.createElement("span");
            glyph.className = "forecast-glyph";
            applyForecastGlyphText(glyph, forecast, cloudyDays, forecastDays, label, location);
            return glyph;
        }

        const FORECAST_GLYPH_CACHE_MS = 5 * 60 * 1000;

        function applyForecastGlyphFromCache(commandMenu) {
            const glyph = commandMenu.querySelector(".command-forecast-glyph");
            if (!glyph) {
                return;
            }
            const unit = String(commandMenu.dataset.unit || "").toUpperCase();
            const cached = forecastGlyphChecker.cache[unit];
            if (!cached || !cached.forecast || !cached.forecast.length) {
                glyph.hidden = true;
                refreshCommandMenuStatusRowVisibility(commandMenu);
                return;
            }
            glyph.hidden = false;
            const entry = commandMenuEntries.get(commandMenu);
            const subject = (entry && (entry.ticketSubject || entry.subject)) || "";
            const label = unit + (subject ? " — " + subject : "");
            applyForecastGlyphText(glyph, cached.forecast, cached.cloudyDays, cached.forecastDays, label, cached.location);
            refreshCommandMenuStatusRowVisibility(commandMenu);
        }

        const forecastGlyphChecker = makeUnitGlyphChecker(
            "/issues/battery-outlook/", FORECAST_GLYPH_CACHE_MS,
            function (data) {
                return {
                    forecast: data.forecast,
                    cloudyDays: data.cloudy_days,
                    forecastDays: data.forecast_days,
                    location: forecastLocationFromData(data),
                };
            },
            applyForecastGlyphFromCache,
        );

        function checkAndApplyForecastGlyph(commandMenu) {
            forecastGlyphChecker.checkAndApply(commandMenu);
        }

        // Same 5-day cloud-cover glyph as the command menu's own
        // .command-forecast-glyph and the fleet-report rows' freestanding
        // one (forecastGlyphElement) — reused here for the Network Latency
        // Graphs modal (the "cell vs power outage" one) so a tech can see
        // whether a storm was rolling through around a power-outage
        // verdict without leaving the graph to go open the command menu.
        // Shares forecastGlyphChecker's own cache (keyed by unit) rather
        // than fetching independently, so whichever of the two — this
        // modal or the command menu — warms it first saves the other a
        // round trip.
        function applyGraphsForecastGlyph(unit, subject) {
            if (!graphsForecastGlyphEl) {
                return;
            }
            const key = String(unit || "").trim().toUpperCase();
            if (!key) {
                graphsForecastGlyphEl.hidden = true;
                return;
            }
            const label = unit + (subject ? " — " + subject : "");
            function render() {
                const info = forecastGlyphChecker.cache[key];
                // The fetch below can settle after the modal has already
                // been reopened in another mode or for another unit — don't
                // paint a stale pill onto whatever is open now.
                if (graphsMode !== "network" || String(graphsUnit).toUpperCase() !== key) {
                    return;
                }
                if (!info || !info.forecast || !info.forecast.length) {
                    graphsForecastGlyphEl.hidden = true;
                    return;
                }
                graphsForecastGlyphEl.hidden = false;
                applyForecastGlyphText(graphsForecastGlyphEl, info.forecast, info.cloudyDays, info.forecastDays, label, info.location);
            }
            const cached = forecastGlyphChecker.cache[key];
            if (cached && (Date.now() - cached.fetchedAt) < FORECAST_GLYPH_CACHE_MS) {
                render();
                return;
            }
            graphsForecastGlyphEl.hidden = true;
            fetch("/issues/battery-outlook/" + encodeURIComponent(unit), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ subject: subject || "" }),
            })
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    forecastGlyphChecker.cache[key] = (data && data.ok)
                        ? {
                            forecast: data.forecast, cloudyDays: data.cloudy_days,
                            forecastDays: data.forecast_days, location: forecastLocationFromData(data),
                            fetchedAt: Date.now(),
                        }
                        : { forecast: null, fetchedAt: Date.now() };
                })
                .catch(function () {
                    forecastGlyphChecker.cache[key] = { forecast: null, fetchedAt: Date.now() };
                })
                .finally(render);
        }

        // Lazy, on-open flap check — same "only fires for a unit someone
        // actually opened" reasoning as the glyph checks above, but this one
        // reads unit_history (a local DB query, no device round trip) rather
        // than POSTing to a device-facing endpoint, so it doesn't fit
        // makeUnitGlyphChecker's POST-with-subject-body shape and gets its
        // own small cache/inFlight pair instead. Same days/min-transitions
        // defaults as the Flap Report itself, so "flapping enough to show
        // here" means the same thing in both places.
        const FLAP_ROW_DAYS = 7;
        const FLAP_ROW_MIN_TRANSITIONS = 3;
        const FLAP_ROW_CACHE_MS = 5 * 60 * 1000;
        const flapRowCache = {};
        const flapRowInFlight = {};

        function applyFlapRowFromCache(commandMenu) {
            const row = commandMenu.querySelector(".command-menu-flap");
            if (!row) {
                return;
            }
            const unit = String(commandMenu.dataset.unit || "").toUpperCase();
            const cached = flapRowCache[unit];
            const summary = cached && cached.summary;
            if (!summary || summary.transitions < FLAP_ROW_MIN_TRANSITIONS) {
                row.hidden = true;
                row.innerHTML = "";
                return;
            }
            row.hidden = false;
            row.innerHTML = "";
            const stats = document.createElement("div");
            stats.className = "flap-row-stats";
            stats.textContent = "Flapping: " + summary.transitions + " transition(s) in "
                + FLAP_ROW_DAYS + "d, " + summary.down_checks + "/" + summary.checks
                + " checks down, last seen " + (summary.last_seen || "unknown");
            row.appendChild(stats);
            row.appendChild(renderFlapTimelineBar(summary.timeline, FLAP_ROW_DAYS));
        }

        function checkAndApplyFlapRow(commandMenu) {
            const unit = String(commandMenu.dataset.unit || "").toUpperCase();
            if (!unit || unit === "MENU") {
                return;
            }
            const cached = flapRowCache[unit];
            if (cached && (Date.now() - cached.fetchedAt) < FLAP_ROW_CACHE_MS) {
                applyFlapRowFromCache(commandMenu);
                return;
            }
            if (flapRowInFlight[unit]) {
                return;
            }
            flapRowInFlight[unit] = true;
            fetch(
                "/issues/unit-history/" + encodeURIComponent(unit)
                + "?days=" + FLAP_ROW_DAYS + "&limit=1"
            )
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    flapRowCache[unit] = {
                        summary: (data && data.ok) ? data.summary : null,
                        fetchedAt: Date.now(),
                    };
                })
                .catch(function () {
                    flapRowCache[unit] = { summary: null, fetchedAt: Date.now() };
                })
                .finally(function () {
                    delete flapRowInFlight[unit];
                    applyFlapRowFromCache(commandMenu);
                });
        }

        // ---- Diagnostic Header -------------------------------------------
        // Turns the shading/dead-panel checks that already run on open
        // (above) into a verdict-plus-next-step instead of a bare glyph —
        // same underlying data, just read as a decision rather than a
        // status light. Alert-only: renders nothing on a clean unit.
        //
        // The highlight windows below are a deliberate approximation, not
        // a byte-for-byte replay of the server's own window: the glyph
        // caches only carry the WORST hour / day-count a check found, not
        // its exact start/end timestamps, so "today at that hour" and
        // "the last N days" are close enough to land the shaded band in
        // the right part of the chart without a second round-trip just to
        // fetch the exact window.

        // Arizona (Phoenix) never observes DST, so a UTC hour-of-day
        // converts to it with a plain fixed -7 offset — no per-date lookup
        // needed, unlike a general "this installation's own local time"
        // conversion would (see _shading_status_for_site's own comment on
        // the server side, which this mirrors for the one other place a
        // UTC hour reaches a tech: the Diagnostic Header below).
        function arizonaHourLabel(utcHour) {
            const azHour = ((utcHour - 7) % 24 + 24) % 24;
            return String(azHour).padStart(2, "0") + ":00 MST";
        }

        function buildShadingHighlightRange(cached) {
            if (cached.worstHourUtc == null) {
                return null;
            }
            const now = new Date();
            const start = Date.UTC(
                now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), cached.worstHourUtc, 0, 0
            );
            return { startMs: start, endMs: start + 3600000, label: arizonaHourLabel(cached.worstHourUtc) };
        }

        function buildDeadPanelHighlightRange(cached) {
            const days = cached.recentDays || 14;
            const end = Date.now();
            return { startMs: end - days * 86400000, endMs: end, label: "recent " + days + "d comparison" };
        }

        function diagnosticHeaderScheduleControl(unit, subject) {
            const wrap = document.createElement("span");
            wrap.className = "diagnostic-header-schedule";
            const status = document.createElement("span");
            status.className = "diagnostic-header-schedule-status";
            status.textContent = "Checking snapshot status...";
            wrap.appendChild(status);
            fetch("/issues/shading-snapshot-task/" + encodeURIComponent(unit))
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    wrap.innerHTML = "";
                    const task = data && data.ok ? data.task : null;
                    if (task) {
                        // Already scheduled (or done) — say so instead of
                        // offering to schedule a duplicate.
                        const statusText = document.createElement("span");
                        statusText.className = "diagnostic-header-schedule-status";
                        statusText.textContent = snapshotTaskStatusText(task);
                        wrap.appendChild(statusText);
                        // A captured photo used to only show up on the
                        // separate Shaded Units report page — reported
                        // live: the status text here said "captured" with
                        // no way to actually open it from the ticket
                        // itself. Same thumbnail-click-to-view-full-size
                        // pattern as that report's own row.
                        if (task.has_image) {
                            const thumb = document.createElement("img");
                            thumb.className = "snapshot-thumb";
                            thumb.src = "/issues/shading-snapshot-image/" + task.id;
                            thumb.title = "Click to view full size";
                            thumb.addEventListener("click", function (event) {
                                event.stopPropagation();
                                window.open("/issues/shading-snapshot-image/" + task.id, "_blank");
                            });
                            wrap.appendChild(thumb);
                        }
                        return;
                    }
                    const scheduleBtn = document.createElement("button");
                    scheduleBtn.type = "button";
                    scheduleBtn.className = "action-btn";
                    scheduleBtn.textContent = "Schedule Snapshot";
                    scheduleBtn.title = "Schedule a fisheye-camera photo for the following day's peak-shading hour";
                    scheduleBtn.addEventListener("click", function (event) {
                        event.stopPropagation();
                        scheduleBtn.disabled = true;
                        scheduleBtn.textContent = "Scheduling...";
                        scheduleShadingSnapshot(unit, subject)
                            .then(function (result) {
                                wrap.innerHTML = "";
                                const statusText = document.createElement("span");
                                statusText.className = "diagnostic-header-schedule-status";
                                statusText.textContent = "Scheduled — next attempt "
                                    + (result.next_attempt_at
                                        ? new Date(result.next_attempt_at * 1000).toLocaleString()
                                        : "soon");
                                wrap.appendChild(statusText);
                            })
                            .catch(function (error) {
                                scheduleBtn.disabled = false;
                                scheduleBtn.textContent = "Schedule Snapshot";
                                notifyError("Schedule Snapshot failed: " + (error.message || error));
                            });
                    });
                    wrap.appendChild(scheduleBtn);
                })
                .catch(function () {
                    wrap.innerHTML = "";
                });
            return wrap;
        }

        function renderDiagnosticHeader(commandMenu) {
            const header = commandMenu.querySelector(".command-diagnostic-header");
            if (!header) {
                return;
            }
            const unit = String(commandMenu.dataset.unit || "").toUpperCase();
            const entry = commandMenuEntries.get(commandMenu);
            const subject = (entry && (entry.ticketSubject || entry.subject)) || "";

            const findings = [];
            const shading = shadingGlyphChecker.cache[unit];
            if (shading && shading.status === "shaded") {
                findings.push({ type: "shading", cached: shading });
            }
            const deadPanel = deadPanelGlyphChecker.cache[unit];
            if (deadPanel && deadPanel.status === "dead_panel") {
                findings.push({ type: "dead_panel", cached: deadPanel });
            }

            header.innerHTML = "";
            if (!findings.length) {
                header.hidden = true;
                return;
            }
            header.hidden = false;

            findings.forEach(function (finding) {
                const row = document.createElement("div");
                row.className = "diagnostic-header-row";

                const text = document.createElement("div");
                text.className = "diagnostic-header-text";
                const confidenceText = finding.cached.confidence != null
                    ? finding.cached.confidence + "% confidence" : "";
                const hourText = finding.type === "shading" && finding.cached.worstHourUtc != null
                    ? ", worst hour " + arizonaHourLabel(finding.cached.worstHourUtc) : "";
                text.textContent = (finding.type === "shading" ? "⚠ Possible shading" : "⚠ Possible dead panel")
                    + (confidenceText ? " — " + confidenceText : "") + hourText;
                row.appendChild(text);

                const actions = document.createElement("div");
                actions.className = "diagnostic-header-actions";

                const viewGraphBtn = document.createElement("button");
                viewGraphBtn.type = "button";
                viewGraphBtn.className = "action-btn";
                viewGraphBtn.textContent = "View Graph";
                viewGraphBtn.title = "Opens Battery Graphs with the window this finding is based on highlighted";
                viewGraphBtn.addEventListener("click", function (event) {
                    event.stopPropagation();
                    const range = finding.type === "shading"
                        ? buildShadingHighlightRange(finding.cached)
                        : buildDeadPanelHighlightRange(finding.cached);
                    openGraphsModal(unit, "battery", subject, range);
                });
                actions.appendChild(viewGraphBtn);

                if (finding.type === "shading") {
                    actions.appendChild(diagnosticHeaderScheduleControl(unit, subject));
                }

                row.appendChild(actions);
                header.appendChild(row);
            });
        }

        // Forces the two VRM-backed checks to re-fetch (bypassing their
        // 5-minute cache) instead of waiting for it to expire naturally —
        // used after Run All Diagnostics, a deliberate "check again right
        // now" action.
        function refreshDiagnosticHeader(commandMenu) {
            if (!commandMenu) {
                return;
            }
            const unit = String(commandMenu.dataset.unit || "").toUpperCase();
            delete shadingGlyphChecker.cache[unit];
            delete deadPanelGlyphChecker.cache[unit];
            checkAndApplyShadingGlyph(commandMenu);
            checkAndApplyDeadPanelGlyph(commandMenu);
        }

        function pollPowerInfraAlertsCache() {
            fetch("/issues/power-infra-alerts/cached")
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    const next = {};
                    const rows = data.rows || [];
                    rows.forEach(function (row) {
                        next[String(row.unit || "").toUpperCase()] = {
                            corroborated: !!row.corroborated,
                            zabbix: (row.zabbix_problems || []).length > 0,
                            vrm: !!row.vrm_alarm,
                            zabbixProblems: row.zabbix_problems || [],
                            vrmAlarm: row.vrm_alarm || null,
                        };
                    });
                    // Second pass: an MU trailer row's head_units (its RD/FD
                    // head(s), from the ERP crosswalk) get the SAME info —
                    // deliberately overwriting any plain direct-match entry
                    // those heads already got in the first pass, since the
                    // MU row's zabbix_problems already has the head's own
                    // problems folded in server-side (see
                    // combined_power_infra_alerts) and is therefore always
                    // the more complete of the two.
                    rows.forEach(function (row) {
                        const info = next[String(row.unit || "").toUpperCase()];
                        (row.head_units || []).forEach(function (head) {
                            next[String(head).toUpperCase()] = info;
                        });
                    });
                    powerInfraAlarmedUnits = next;
                    document.querySelectorAll("details.command-menu").forEach(function (commandMenu) {
                        applyPowerInfraGlyph(commandMenu);
                        // Re-apply from the (unchanged) power-status cache too —
                        // its cross-check note depends on powerInfraAlarmedUnits,
                        // which just changed, even though the power reading
                        // itself didn't.
                        applyPowerGlyphFromCache(commandMenu);
                        // Glyph only — NOT a fresh ping sweep on every poll
                        // tick (~45s), that's reserved for an actual menu
                        // open (see checkAndApplyCameraOutageGlyph); this
                        // just re-applies whatever the last sweep already
                        // found, if any.
                        applyCameraOutageGlyph(commandMenu);
                    });
                })
                .catch(function () {})
                .finally(function () {
                    setTimeout(pollPowerInfraAlertsCache, 45000);
                });
        }
        pollPowerInfraAlertsCache();

        // Same shape as pollPowerInfraAlertsCache, off the Up Steady
        // sweep's own cache (never SSHes anything itself — see
        // POWER_VS_CELL_OUTAGE_REFRESH_SECONDS). A slower interval than the
        // alarm poll's 45s is fine: the underlying sweep only refreshes
        // every 30 minutes server-side, so polling faster than that just
        // burns a request for nothing.
        function pollPowerVsCellCache() {
            fetch("/issues/fleet-power-vs-cell-outage/cached")
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    const next = {};
                    (data.rows || []).forEach(function (row) {
                        if (row && row.unit) {
                            next[String(row.unit).toUpperCase()] = row;
                        }
                    });
                    powerVsCellAlarmedUnits = next;
                    document.querySelectorAll("details.command-menu").forEach(function (commandMenu) {
                        applyPowerVsCellGlyph(commandMenu);
                        applyPowerVsCellUptimeLine(commandMenu);
                    });
                    document.querySelectorAll(".power-vs-cell-row-badge").forEach(applyPowerVsCellRowBadge);
                })
                .catch(function () {})
                .finally(function () {
                    setTimeout(pollPowerVsCellCache, 60000);
                });
        }
        pollPowerVsCellCache();

        // Manual "diagnose all" — forces the sweep to run right now instead
        // of waiting for the next scheduled pass, same
        // disable-while-running convention as revalidateList's button.
        // One shared sweep (see _power_vs_cell_sweep_units) now covers Up
        // Steady + Offline compute + Scrypted outage in a single fetch —
        // Andrew's own request, 2026-09-18. Each list still gets its own
        // trigger button (so it's obvious from any of the three sections
        // that this check applies there too), but they all kick the same
        // in-flight sweep rather than three independent ones.
        (function wirePowerVsCellSweepButtons() {
            const btns = [
                "power_vs_cell_sweep_btn", "power_vs_cell_sweep_btn_nuc",
                "power_vs_cell_sweep_btn_scrypted", "power_vs_cell_sweep_btn_truly_down",
            ]
                .map(function (id) { return document.getElementById(id); })
                .filter(Boolean);
            if (!btns.length) {
                return;
            }
            btns.forEach(function (btn) {
                btn.dataset.idleLabel = btn.textContent;
            });
            let inFlight = false;
            function setBusy(busy) {
                btns.forEach(function (btn) {
                    btn.disabled = busy;
                    btn.textContent = busy ? "Diagnosing..." : btn.dataset.idleLabel;
                });
            }
            btns.forEach(function (btn) {
                btn.addEventListener("click", function () {
                    if (inFlight) {
                        return;
                    }
                    inFlight = true;
                    setBusy(true);
                    statusEl.textContent = "Diagnosing Up Steady / Offline compute / Scrypted outage / Down Full units (cell/power)...";
                    fetch("/issues/fleet-power-vs-cell-outage")
                        .then(function (response) {
                            return response.json().then(function (data) {
                                if (!response.ok || !data.ok) {
                                    throw new Error(data.error || ("HTTP " + response.status));
                                }
                                return data;
                            });
                        })
                        .then(function (data) {
                            const rows = data.rows || [];
                            const next = {};
                            rows.forEach(function (row) {
                                if (row && row.unit) {
                                    next[String(row.unit).toUpperCase()] = row;
                                }
                            });
                            powerVsCellAlarmedUnits = next;
                            document.querySelectorAll("details.command-menu").forEach(function (commandMenu) {
                                applyPowerVsCellGlyph(commandMenu);
                                applyPowerVsCellUptimeLine(commandMenu);
                            });
                            document.querySelectorAll(".power-vs-cell-row-badge").forEach(applyPowerVsCellRowBadge);
                            const findings = rows.filter(function (row) {
                                return row.verdict === "power_outage" || row.verdict === "cell_outage";
                            });
                            statusEl.textContent = "Diagnosed " + rows.length + " unit"
                                + (rows.length === 1 ? "" : "s") + " — " + findings.length
                                + " power/cell finding" + (findings.length === 1 ? "" : "s") + ".";
                        })
                        .catch(function (error) {
                            const message = "Power/cell diagnosis failed: " + (error.message || error);
                            consoleLines.push(message);
                            renderConsole(true);
                            statusEl.textContent = message;
                        })
                        .finally(function () {
                            inFlight = false;
                            setBusy(false);
                        });
                });
            });
        })();

        // ---- Busy flag -------------------------------------------------------
        // The per-unit lock already exists server-side; this surfaces it on the
        // row so two people don't start conflicting actions on the same unit.
        let busyUnitsMap = {};

        function appendUnitBusyFlag(parent, entry) {
            if (!entry || !entry.unit) {
                return;
            }
            const flag = document.createElement("span");
            flag.className = "unit-busy-flag";
            flag.dataset.busyUnit = String(entry.unit).toUpperCase();
            flag.hidden = true;
            parent.appendChild(flag);
            applyBusyFlag(flag);
        }

        // Generous on purpose — the multi-step Security Update Fix wizard
        // includes a human-paced wait (confirm the unit is fully shut down
        // before clicking Finish), so a legitimate session can run well
        // past what a single SSH step takes on its own. This is only ever
        // a "worth a second look" flag, never an auto-clear, so erring
        // toward fewer false positives costs nothing.
        const UNIT_BUSY_STALE_MS = 30 * 60 * 1000;
        function applyBusyFlag(flag) {
            const info = busyUnitsMap[flag.dataset.busyUnit];
            if (!info) {
                flag.hidden = true;
                flag.textContent = "";
                flag.classList.remove("is-stale");
                return;
            }
            flag.hidden = false;
            const ageMs = info.started_at ? (Date.now() - info.started_at * 1000) : 0;
            const stale = ageMs > UNIT_BUSY_STALE_MS;
            flag.classList.toggle("is-stale", stale);
            flag.textContent = "⚠ " + (info.action || "in progress")
                + (info.phase ? (" · " + info.phase) : "")
                + (stale ? " (stuck?)" : "");
            flag.title = info.action + " is running on " + flag.dataset.busyUnit
                + " — avoid starting another action on this unit"
                + (stale
                    ? ". This has been running for " + Math.round(ageMs / 60000)
                        + "+ minutes — if it's genuinely stuck, use Force Clear Lock "
                        + "in the Security Update Fix dialog."
                    : "");
        }

        // ---- Read-only diagnostics ------------------------------------------
        // One helper for the "POST, log the result, report status" pattern so
        // each new diagnostic is a few lines of configuration rather than
        // another forty lines of copied fetch boilerplate.
        // Shared by both command-menu builders' "Power vs Cell Outage"
        // button (see appendDiagnosticButton's detailLines) — the extra
        // console lines spelling out exactly what was compared, since the
        // one-line summary alone doesn't show the actual switch-uptime
        // text or the loss window's start/end.
        function powerVsCellOutageDetailLines(data) {
            const lines = [];
            if (data.switch_uptime_text) {
                lines.push("Switch: " + String(data.switch_uptime_text).trim());
            }
            if (data.loss_window_start && data.loss_window_end) {
                lines.push(
                    "Router loss " + data.loss_threshold + "%+ from "
                    + new Date(data.loss_window_start * 1000).toLocaleString()
                    + " to " + new Date(data.loss_window_end * 1000).toLocaleString()
                );
            }
            return lines;
        }

        function appendDiagnosticButton(parent, entry, options) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "action-btn";
            btn.textContent = options.label;
            if (options.title) {
                btn.title = options.title;
            }
            btn.addEventListener("click", function () {
                btn.disabled = true;
                btn.textContent = options.busyLabel || "Checking...";
                statusEl.textContent = options.label + " for " + entry.unit + "...";
                // Optional JSON body, e.g. Power vs Cell Outage passing the
                // ticket's own issue_id so the server can match the loss
                // window against when the ticket was actually opened.
                const bodyPayload = options.body ? options.body(entry) : null;
                const fetchInit = { method: options.method || "POST" };
                if (bodyPayload) {
                    fetchInit.headers = { "Content-Type": "application/json" };
                    fetchInit.body = JSON.stringify(bodyPayload);
                }
                fetch(options.endpoint + encodeURIComponent(entry.unit), fetchInit)
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        const summary = data.summary || (options.label + " complete for " + entry.unit);
                        consoleLines.push(summary);
                        (options.detailLines ? options.detailLines(data) : []).forEach(function (line) {
                            if (line) {
                                consoleLines.push("  " + line);
                            }
                        });
                        renderConsole(true);
                        statusEl.textContent = summary;
                        if (data.status === "fail") {
                            notify(summary, "error");
                        } else if (data.status === "warn") {
                            notify(summary, "warning");
                        }
                        if (options.afterSuccess) {
                            options.afterSuccess(data);
                        }
                    })
                    .catch(function (error) {
                        const message = options.label + " failed: " + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        btn.disabled = false;
                        btn.textContent = options.label;
                    });
            });
            parent.appendChild(btn);
            return btn;
        }

        function appendDiagnosticsCommandMenu(commandItems, entry) {
            if (!entry || !entry.unit) {
                return;
            }
            const diagMenu = appendCommandSubmenu(commandItems, "Diagnostics");

            appendDiagnosticButton(diagMenu, entry, {
                label: "Run All Diagnostics",
                busyLabel: "Running...",
                title: "Every read-only check for this unit in one pass",
                endpoint: "/issues/run-diagnostics/",
                detailLines: function (data) {
                    const lines = (data.problems || []).slice();
                    if (!lines.length) {
                        Object.keys(data.checks || {}).forEach(function (key) {
                            const check = data.checks[key];
                            lines.push(check.label + ": " + (check.ok ? (check.status || "ok") : check.error));
                        });
                    }
                    return lines;
                },
                // run_unit_diagnostics is SSH-based checks only (connectivity,
                // cameras, services, PVE/NUC resources) — it doesn't touch
                // VRM, so it can't hand the Diagnostic Header a shading/
                // dead-panel verdict directly. What it CAN do is prompt a
                // fresh look: force the two VRM-backed checks to re-fetch
                // (bypassing their 5-minute cache) rather than silently
                // waiting for the next natural refresh.
                afterSuccess: function () {
                    refreshDiagnosticHeader(diagMenu.closest(".command-menu"));
                },
            });

            appendDiagnosticButton(diagMenu, entry, {
                label: "Camera Reachability",
                title: "Ping every camera, the fisheye and the speaker at once",
                endpoint: "/issues/camera-matrix/",
                detailLines: function (data) {
                    return (data.endpoints || []).map(function (item) {
                        return (item.reachable ? "✓ " : "× ")
                            + item.label + " (" + item.host + ")";
                    });
                },
            });

            // Hikvision-only: the server re-checks with is_hikvision_unit() and
            // errors cleanly if this guess is ever wrong. Dahua isn't offered
            // here — its cgi-bin analytics endpoint wasn't reachable on this
            // fleet's fisheyes when checked directly.
            if (String(entry.unit || "").toUpperCase().indexOf("MU") === 0) {
                appendDiagnosticButton(diagMenu, entry, {
                    label: "Camera Analytics (Hikvision)",
                    title: "Field/Line Detection rule state read over ISAPI — reports what's configured, not whether it should be",
                    endpoint: "/issues/camera-analytics/",
                    detailLines: function (data) {
                        const lines = [];
                        (data.cameras || []).forEach(function (cam) {
                            Object.keys(cam.rules || {}).forEach(function (key) {
                                const rule = cam.rules[key];
                                let state;
                                if (!rule.reachable) {
                                    state = "unreachable";
                                } else if (rule.enabled == null) {
                                    state = "reachable, state unknown";
                                } else {
                                    state = rule.enabled ? "enabled" : "disabled";
                                }
                                lines.push(
                                    (rule.reachable ? "✓ " : "× ")
                                        + cam.label + " " + rule.label + " — " + state
                                );
                            });
                        });
                        return lines;
                    },
                });
            }

            if (entry.hasPve) {
                appendDiagnosticButton(diagMenu, entry, {
                    label: "PVE Host Resources",
                    title: "Memory, disk, load and VM 101 state on the PVE host",
                    endpoint: "/issues/pve-resources/",
                    detailLines: function (data) {
                        const lines = [];
                        if (data.mem_used_percent != null) {
                            lines.push("Memory: " + data.mem_used_percent + "% used ("
                                + data.mem_used_mb + " / " + data.mem_total_mb + " MB)");
                        }
                        if (data.swap_total_mb) {
                            lines.push("Swap: " + data.swap_used_mb + " / " + data.swap_total_mb + " MB");
                        }
                        if (data.root_disk) {
                            lines.push("Root disk: " + data.root_disk.use_percent + "% used ("
                                + data.root_disk.used + " / " + data.root_disk.size
                                + ", " + data.root_disk.available + " free)");
                        }
                        if (data.load_1m != null) {
                            lines.push("Load: " + data.load_1m + " / " + data.load_5m + " / " + data.load_15m);
                        }
                        if (data.vm101_status) {
                            lines.push("VM 101: " + data.vm101_status);
                        }
                        return lines;
                    },
                });
            } else if (entry.unit) {
                // The NUC half of the fleet had no resource visibility at all
                // before this — PVE units got PVE Host Resources above
                // (plus Platform Status, now on the Scrypted menu), NUC
                // units got nothing.
                appendDiagnosticButton(diagMenu, entry, {
                    label: "NUC Resources",
                    title: "Memory, disk and CPU load on the NUC",
                    endpoint: "/issues/nuc-resources/",
                    detailLines: function (data) {
                        const lines = [];
                        if (data.mem_used_percent != null) {
                            lines.push("Memory: " + data.mem_used_percent + "% used ("
                                + data.mem_used_mb + " / " + data.mem_total_mb + " MB)");
                        }
                        if (data.disk_used_percent != null) {
                            lines.push("C: drive: " + data.disk_used_percent + "% used ("
                                + (data.disk_size_gb - data.disk_free_gb).toFixed(1) + " / "
                                + data.disk_size_gb + " GB)");
                        }
                        if (data.cpu_load_percent != null) {
                            lines.push("CPU load: " + Math.round(data.cpu_load_percent) + "%");
                        }
                        return lines;
                    },
                });
                // Disk health beyond chkdsk: each drive's own health, SMART
                // counters / predict-failure, and 90 days of disk, NTFS and
                // storage-driver events (see work_tool.nuc_disk_health).
                appendDiagnosticButton(diagMenu, entry, {
                    label: "NUC Disk Health",
                    title: "Drive health, SMART counters and disk-failure events on the NUC (read-only, ~10s)",
                    endpoint: "/issues/nuc-disk-health/",
                    detailLines: function (data) {
                        const lines = [];
                        (data.disks || []).forEach(function (d) {
                            const bits = [d.health || "?"];
                            if (d.temperature) {
                                bits.push(d.temperature + "°C" + (d.temperature_max ? " (max " + d.temperature_max + "°C)" : ""));
                            }
                            if (d.wear) {
                                bits.push(d.wear + "% worn");
                            }
                            if (d.read_errors_total != null || d.read_errors_uncorrected != null) {
                                bits.push((d.read_errors_total || 0) + " read errors ("
                                    + (d.read_errors_uncorrected || 0) + " uncorrected)");
                            }
                            if (d.write_errors_uncorrected) {
                                bits.push(d.write_errors_uncorrected + " uncorrected write errors");
                            }
                            if (d.power_on_hours) {
                                bits.push(Number(d.power_on_hours).toLocaleString() + " h powered on");
                            }
                            if (d.predict_failure != null) {
                                bits.push("SMART predict-fail: " + (d.predict_failure ? "YES" : "no"));
                            }
                            lines.push("Drive: " + d.name + " (" + [d.media, d.bus, d.size_gb ? d.size_gb + " GB" : ""]
                                .filter(Boolean).join(", ") + ") — " + bits.join(" · "));
                        });
                        const events = data.events || [];
                        if (!events.length) {
                            lines.push("Disk events (90 days): none");
                        }
                        events.forEach(function (ev) {
                            const mark = ev.tier === "critical" ? "✗ " : ev.tier === "warning" ? "! " : "  ";
                            const when = ev.days_ago != null ? (ev.days_ago < 1 ? "today" : Math.round(ev.days_ago) + "d ago") : "";
                            lines.push(mark + ev.count + "× " + ev.provider + " " + ev.id
                                + (ev.meaning ? " (" + ev.meaning + ")" : "")
                                + (ev.disk ? " on " + ev.disk : "")
                                + (when ? ", last " + when : "")
                                + (ev.message ? " — " + ev.message : ""));
                        });
                        return lines;
                    },
                });
            }

            // History is a GET and has no status field, so it is wired
            // directly rather than through appendDiagnosticButton.
            const historyBtn = document.createElement("button");
            historyBtn.type = "button";
            historyBtn.className = "action-btn";
            historyBtn.textContent = "Unit History";
            historyBtn.title = "Recorded validation results and flap count for this unit";
            historyBtn.addEventListener("click", function () {
                historyBtn.disabled = true;
                historyBtn.textContent = "Loading...";
                fetch("/issues/unit-history/" + encodeURIComponent(entry.unit) + "?days=30&limit=40")
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        const s = data.summary || {};
                        const header = s.checks
                            ? (entry.unit + ": " + s.checks + " checks in the last " + s.days
                                + " days, " + s.down_checks + " down, "
                                + s.transitions + " up/down transitions")
                            : (entry.unit + ": no recorded history yet");
                        consoleLines.push(header);
                        (data.entries || []).slice(0, 40).forEach(function (item) {
                            consoleLines.push(
                                "  " + item.when + "  "
                                + (item.healthy ? "✓" : "×") + "  "
                                + (item.category || item.led || item.kind)
                            );
                        });
                        renderConsole(true);
                        statusEl.textContent = header;
                        if (s.transitions >= 3) {
                            notify(entry.unit + " has flapped " + s.transitions
                                + " times in " + s.days + " days", "warning");
                        }
                    })
                    .catch(function (error) {
                        const message = "Unit History failed: " + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        historyBtn.disabled = false;
                        historyBtn.textContent = "Unit History";
                    });
            });
            diagMenu.appendChild(historyBtn);

            // Direct answer to "is this unit plugged in" — the same question
            // ERP files as an "unplugged" ticket subtype. Used to only exist
            // as a side effect of Battery Outlook under Weather, which
            // nobody would think to check for this. Always toasts (not just
            // on warn/fail) since confirming "yes, it's plugged in" is worth
            // as much as flagging that it isn't.
            const powerStatusBtn = document.createElement("button");
            powerStatusBtn.type = "button";
            powerStatusBtn.className = "action-btn";
            powerStatusBtn.textContent = "Power Status (Plugged In?)";
            powerStatusBtn.title = "Best-effort check of AC/shore power — experimental, see detail for how sure";
            powerStatusBtn.addEventListener("click", function () {
                powerStatusBtn.disabled = true;
                powerStatusBtn.textContent = "Checking...";
                statusEl.textContent = "Power status for " + entry.unit + "...";
                const subjectForLookup = entry.ticketSubject || entry.subject || "";
                fetch("/issues/power-status/" + encodeURIComponent(entry.unit), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ subject: subjectForLookup }),
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        consoleLines.push(data.summary);
                        if (data.ac_power_detail) {
                            consoleLines.push("  " + data.ac_power_detail);
                        }
                        // Cross-check against Zabbix/VRM's OWN independent
                        // read on this unit — already fetched and cached
                        // for the alarm glyph (see pollPowerInfraAlertsCache,
                        // which fans an MU trailer's data out to its RD/FD
                        // head too), so this costs nothing extra and needs
                        // no new heuristic: it's just the two signals shown
                        // side by side, neither one silently overriding the
                        // other. This is exactly where a VRM-side alarm
                        // like "Trailer Unplugged" would show up alongside
                        // our own inferred verdict if the two disagree.
                        const crossCheckInfo = powerInfraAlarmedUnits[String(entry.unit || "").toUpperCase()];
                        let crossCheckText = "";
                        if (crossCheckInfo) {
                            crossCheckText = powerInfraAlertSummaryText(entry.unit, crossCheckInfo);
                            consoleLines.push("  Zabbix/VRM alerts on this unit:");
                            crossCheckText.split("\n").forEach(function (line) {
                                consoleLines.push("    " + line);
                            });
                        }
                        renderConsole(true);
                        statusEl.textContent = data.summary;
                        const toastKind = data.status === "fail" ? "error"
                            : data.status === "warn" ? "warning" : "success";
                        notify(
                            data.summary + (crossCheckText ? "\n\nAlso active for this unit:\n" + crossCheckText : ""),
                            crossCheckText ? "error" : toastKind,
                            {
                                actionLabel: "View Graphs",
                                onAction: function () {
                                    openGraphsModal(entry.unit, "battery", subjectForLookup);
                                },
                            }
                        );
                    })
                    .catch(function (error) {
                        const message = "Power Status failed: " + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        powerStatusBtn.disabled = false;
                        powerStatusBtn.textContent = "Power Status (Plugged In?)";
                    });
            });
            diagMenu.appendChild(powerStatusBtn);

            // Same idea as Power Status, but for the ticket subtype "shaded"
            // instead of "unplugged" — see detect_solar_shading. This is the
            // on-demand equivalent of the passive 🌳 glyph in the status row
            // (which only checks lazily when the menu opens and caches for
            // 5 minutes); this button always does a fresh check right now.
            const shadingStatusBtn = document.createElement("button");
            shadingStatusBtn.type = "button";
            shadingStatusBtn.className = "action-btn";
            shadingStatusBtn.textContent = "Shading Status (Solar Dip?)";
            shadingStatusBtn.title = "Checks this trailer's recent solar output against its own hour-of-day history — experimental";
            shadingStatusBtn.addEventListener("click", function () {
                shadingStatusBtn.disabled = true;
                shadingStatusBtn.textContent = "Checking...";
                statusEl.textContent = "Shading status for " + entry.unit + "...";
                const subjectForLookup = entry.ticketSubject || entry.subject || "";
                fetch("/issues/shading-status/" + encodeURIComponent(entry.unit), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ subject: subjectForLookup }),
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        consoleLines.push(data.summary);
                        if (data.shading_detail) {
                            consoleLines.push("  " + data.shading_detail);
                        }
                        // Same cross-check as Power Status — see its comment.
                        const crossCheckInfo = powerInfraAlarmedUnits[String(entry.unit || "").toUpperCase()];
                        let crossCheckText = "";
                        if (crossCheckInfo) {
                            crossCheckText = powerInfraAlertSummaryText(entry.unit, crossCheckInfo);
                            consoleLines.push("  Zabbix/VRM alerts on this unit:");
                            crossCheckText.split("\n").forEach(function (line) {
                                consoleLines.push("    " + line);
                            });
                        }
                        renderConsole(true);
                        statusEl.textContent = data.summary;
                        const toastKind = data.status === "fail" ? "error"
                            : data.status === "warn" ? "warning" : "success";
                        notify(
                            data.summary + (crossCheckText ? "\n\nAlso active for this unit:\n" + crossCheckText : ""),
                            crossCheckText ? "error" : toastKind,
                            {
                                actionLabel: "View Graphs",
                                onAction: function () {
                                    openGraphsModal(entry.unit, "battery", subjectForLookup);
                                },
                            }
                        );
                    })
                    .catch(function (error) {
                        const message = "Shading Status failed: " + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        shadingStatusBtn.disabled = false;
                        shadingStatusBtn.textContent = "Shading Status (Solar Dip?)";
                    });
            });
            diagMenu.appendChild(shadingStatusBtn);

            // Schedules a fisheye-camera photo of the panels for the
            // FOLLOWING day's peak-shading hour — never fires same-day,
            // and re-confirms the dip is actually happening (see
            // work_tool.verify_shading_dip_now) right before it does,
            // retrying up to a few days before giving up. Requires
            // shading to be actively detected right now (runs the check
            // fresh); see shading_snapshots.py for the whole task model.
            const scheduleSnapshotBtn = document.createElement("button");
            scheduleSnapshotBtn.type = "button";
            scheduleSnapshotBtn.className = "action-btn";
            scheduleSnapshotBtn.textContent = "Schedule Shading Snapshot";
            scheduleSnapshotBtn.title = "If shading is currently detected: schedules a fisheye-camera photo for the following day's peak-shading hour";
            scheduleSnapshotBtn.addEventListener("click", function () {
                scheduleSnapshotBtn.disabled = true;
                scheduleSnapshotBtn.textContent = "Scheduling...";
                statusEl.textContent = "Scheduling shading snapshot for " + entry.unit + "...";
                const subjectForLookup = entry.ticketSubject || entry.subject || "";
                scheduleShadingSnapshot(entry.unit, subjectForLookup)
                    .then(function (data) {
                        const when = data.next_attempt_at
                            ? new Date(data.next_attempt_at * 1000).toLocaleString()
                            : "an upcoming pass";
                        const message = data.created
                            ? "Snapshot scheduled for " + entry.unit + " — next attempt " + when
                            : "A snapshot task for " + entry.unit + " was already pending — next attempt " + when;
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notify(message, "success");
                    })
                    .catch(function (error) {
                        const message = "Schedule Shading Snapshot failed: " + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        scheduleSnapshotBtn.disabled = false;
                        scheduleSnapshotBtn.textContent = "Schedule Shading Snapshot";
                    });
            });
            diagMenu.appendChild(scheduleSnapshotBtn);

            const graphsMenu = appendCommandSubmenu(diagMenu, "Graphs");
            // Graphs is the button someone reaches for most in here — a
            // straight-to-the-data look, not a diagnostic to run and wait
            // on — so it goes first, ahead of the checks appended above
            // (appendCommandSubmenu always appends at the end, which is
            // why this needs an explicit move rather than just being
            // declared first). graphsMenu is the .command-submenu-items
            // div appendCommandSubmenu returns; its parentElement is the
            // actual <details> — that's the whole nested submenu (summary
            // + items) that needs to move, not just its contents.
            diagMenu.insertBefore(graphsMenu.parentElement, diagMenu.firstChild);

            // Moved here from the Switch submenu (both copies — Unit
            // Tools' and renderList's each had their own) per request: it
            // reads as a diagnostic verdict ("is this power or cell"), not
            // a device-specific Switch action, so it belongs with the
            // rest of the diagnostics rather than buried under a specific
            // piece of hardware.
            appendDiagnosticButton(diagMenu, entry, {
                label: "Power vs Cell Outage",
                title: "Compares switch uptime against the router's most recent ~100% ping-loss window to distinguish a power outage from a cell/carrier outage",
                endpoint: "/issues/power-vs-cell-outage/",
                detailLines: powerVsCellOutageDetailLines,
                // When more than one qualifying loss window exists, the
                // server prefers whichever matches this ticket's own ERP
                // creation time over its longest-duration fallback — see
                // unit_power_vs_cell_outage's docstring.
                body: function (e) {
                    return e.issueId ? { issue_id: e.issueId } : null;
                },
                // Same cache-then-reapply this data source already gets
                // from the glyph's own click handler and the fleet sweep —
                // running the check from this button shouldn't leave the
                // glyph/uptime line/row badge showing a stale verdict.
                afterSuccess: function (data) {
                    const unit = String(entry.unit || "").toUpperCase();
                    if (!unit) {
                        return;
                    }
                    powerVsCellAlarmedUnits[unit] = data;
                    const commandMenu = diagMenu.closest(".command-menu");
                    if (commandMenu) {
                        applyPowerVsCellGlyph(commandMenu);
                        applyPowerVsCellUptimeLine(commandMenu);
                    }
                    document.querySelectorAll(".power-vs-cell-row-badge").forEach(function (badgeEl) {
                        if (String(badgeEl.dataset.unit || "").toUpperCase() === unit) {
                            applyPowerVsCellRowBadge(badgeEl);
                        }
                    });
                },
            });

            const batteryGraphsBtn = document.createElement("button");
            batteryGraphsBtn.type = "button";
            batteryGraphsBtn.className = "action-btn";
            batteryGraphsBtn.textContent = "Battery Graphs (Experimental)";
            batteryGraphsBtn.title = "Voltage / SOC / current / solar power over time, from VRM";
            batteryGraphsBtn.addEventListener("click", function () {
                openGraphsModal(entry.unit, "battery", entry.ticketSubject || entry.subject || "");
            });
            graphsMenu.appendChild(batteryGraphsBtn);

            const networkGraphsBtn = document.createElement("button");
            networkGraphsBtn.type = "button";
            networkGraphsBtn.className = "action-btn";
            networkGraphsBtn.textContent = "Network Latency Graphs (Experimental)";
            networkGraphsBtn.title = "Router/Switch ICMP ping response time & loss over time, from Zabbix";
            networkGraphsBtn.addEventListener("click", function () {
                // Same Up-Steady-sweep cache the command menu's own uptime
                // line reads (applyPowerVsCellUptimeLine) and
                // openPowerVsCellRowDetail's own copy of this modal already
                // shows — free here too, no new fetch, and just as silent
                // when the sweep has no entry for this unit yet.
                const unit = String(entry.unit || "").toUpperCase();
                const info = unit ? powerVsCellAlarmedUnits[unit] : null;
                openGraphsModal(
                    entry.unit, "network", entry.ticketSubject || entry.subject || "", null, null, null,
                    info ? powerVsCellUptimeDetailText(info) : null
                );
                applyGraphsInfoLineUptimeTier(info);
            });
            graphsMenu.appendChild(networkGraphsBtn);
        }

        function appendCamerasCommandMenu(commandItems, entry) {
            if (!entry || !entry.unit) {
                return;
            }
            const camerasMenu = appendCommandSubmenu(commandItems, "Cameras");
            const submenu = camerasMenu.parentElement;
            if (submenu) {
                submenu.addEventListener("click", function (event) {
                    event.stopPropagation();
                });
            }

            const fishBtn = document.createElement("button");
            fishBtn.type = "button";
            fishBtn.className = "action-btn";
            fishBtn.textContent = "Fisheye Snapshot";
            if (!entry.fisheyeIp) {
                fishBtn.disabled = true;
                fishBtn.title = "No fisheye IP in net sheet";
            } else {
                fishBtn.addEventListener("click", function (event) {
                    event.preventDefault();
                    event.stopPropagation();
                    openFisheyeSnapshot(entry.unit, entry.url || "");
                });
            }
            camerasMenu.appendChild(fishBtn);

            const threeSixtyBtn = document.createElement("button");
            threeSixtyBtn.type = "button";
            threeSixtyBtn.className = "action-btn";
            threeSixtyBtn.textContent = "360 Snapshot";
            threeSixtyBtn.title = "One snapshot from every camera except fisheye";
            threeSixtyBtn.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                open360Snapshot(entry.unit, threeSixtyBtn);
            });
            camerasMenu.appendChild(threeSixtyBtn);

            // Previously reachable only via a click on the camera-outage
            // status glyph, which only appears under one specific Zabbix
            // condition and only offered this for non-Scrypted (NUC)
            // units — a working feature that was effectively hidden from
            // most of the fleet. Available here for any unit now.
            const cameraGridBtn = document.createElement("button");
            cameraGridBtn.type = "button";
            cameraGridBtn.className = "action-btn";
            cameraGridBtn.textContent = "Camera Grid";
            cameraGridBtn.title = "Live-refreshing snapshot grid of every camera (not real video)";
            cameraGridBtn.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                openCameraSnapshotGrid(entry.unit);
            });
            camerasMenu.appendChild(cameraGridBtn);

            let availableCameraTargets = [];
            const allBtn = wireCameraLaunchButton(
                document.createElement("button"),
                entry.unit,
                "all",
                function () {
                    return availableCameraTargets;
                }
            );
            allBtn.textContent = "Open All Cameras";
            allBtn.disabled = true;
            allBtn.title = "Loading camera list...";
            camerasMenu.appendChild(allBtn);

            appendTestAllEmailsButton(camerasMenu, entry);

            // Each Dahua camera's own configured "room" (everything before
            // "@" in its SMTP Sender, Settings > Network > Email) — see
            // work_tool.camera_rooms for the PTZ-inference rule on
            // Scrypted units. Dahua only for now, same scope as Test Email.
            const roomsBtn = document.createElement("button");
            roomsBtn.type = "button";
            roomsBtn.className = "action-btn";
            roomsBtn.textContent = "Get Camera Rooms";
            roomsBtn.title = "Each camera's configured room, from its own SMTP Sender field (Dahua only)";
            roomsBtn.addEventListener("click", function () {
                runGetCameraRooms(entry.unit, roomsBtn);
            });
            camerasMenu.appendChild(roomsBtn);

            const individualWrap = document.createElement("div");
            individualWrap.className = "camera-launch-list";
            camerasMenu.appendChild(individualWrap);

            if (!submenu) {
                return;
            }
            submenu.addEventListener("toggle", function () {
                if (!submenu.open || individualWrap.dataset.loaded === "1") {
                    return;
                }
                individualWrap.textContent = "Loading cameras...";
                fetch("/issues/cameras/" + encodeURIComponent(entry.unit))
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        individualWrap.innerHTML = "";
                        const cameras = data.cameras || [];
                        if (!cameras.length) {
                            const emptyBtn = document.createElement("button");
                            emptyBtn.type = "button";
                            emptyBtn.className = "action-btn";
                            emptyBtn.textContent = "No cameras in net sheet";
                            emptyBtn.disabled = true;
                            individualWrap.appendChild(emptyBtn);
                            allBtn.title = "No camera IPs configured for this unit";
                            return;
                        }
                        individualWrap.dataset.loaded = "1";
                        availableCameraTargets = cameras.map(function (camera) {
                            return camera.target;
                        });
                        allBtn.disabled = false;
                        allBtn.title = "Open all configured cameras in this browser";
                        cameras.forEach(function (camera) {
                            const cameraBtn = wireCameraLaunchButton(
                                document.createElement("button"),
                                entry.unit,
                                camera.target
                            );
                            cameraBtn.textContent = "Open " + camera.label;
                            cameraBtn.title = camera.host
                                + (camera.port ? (":" + camera.port) : "");
                            individualWrap.appendChild(cameraBtn);
                            appendLongPingCameraButton(individualWrap, entry, camera);

                            if (camera.target === "fisheye") {
                                return;
                            }
                            // Fires the camera's OWN test-email action
                            // against whatever SMTP settings are already
                            // configured on it (Settings > Network >
                            // Email > Test) — confirms delivery actually
                            // works, not just that the settings look
                            // right. Dahua only for now (netApp.
                            // sendTestMail, verified live 2026-09-17);
                            // Hikvision isn't wired up yet and the server
                            // says so plainly rather than silently
                            // failing. Fisheye excluded (see
                            // start_camera_test_email_loop) — its RPC
                            // port refused the connection live, unlike
                            // Camera 1-4 on the same unit/run.
                            const testEmailBtn = document.createElement("button");
                            testEmailBtn.type = "button";
                            testEmailBtn.className = "action-btn";
                            testEmailBtn.textContent = "Test Email (" + camera.label + ")";
                            testEmailBtn.title = "Send a test email from " + camera.label
                                + "'s own configured SMTP settings";
                            testEmailBtn.addEventListener("click", function (event) {
                                event.preventDefault();
                                event.stopPropagation();
                                testEmailBtn.disabled = true;
                                testEmailBtn.textContent = "Sending...";
                                statusEl.textContent = "Sending test email from "
                                    + entry.unit + " " + camera.label + "...";
                                fetch(
                                    "/issues/camera-test-email/" + encodeURIComponent(entry.unit)
                                        + "/" + encodeURIComponent(camera.target),
                                    { method: "POST" }
                                )
                                    .then(function (response) {
                                        return response.json().then(function (data) {
                                            if (!response.ok || !data.ok) {
                                                throw new Error(data.error || ("HTTP " + response.status));
                                            }
                                            return data;
                                        });
                                    })
                                    .then(function (data) {
                                        consoleLines.push(data.message);
                                        renderConsole(true);
                                        statusEl.textContent = data.message;
                                        notify(data.message, "info");
                                    })
                                    .catch(function (error) {
                                        const message = "Test email failed: " + (error.message || error);
                                        consoleLines.push(message);
                                        renderConsole(true);
                                        statusEl.textContent = message;
                                        notifyError(message);
                                    })
                                    .finally(function () {
                                        testEmailBtn.disabled = false;
                                        testEmailBtn.textContent = "Test Email (" + camera.label + ")";
                                    });
                            });
                            individualWrap.appendChild(testEmailBtn);
                        });
                    })
                    .catch(function (error) {
                        individualWrap.innerHTML = "";
                        const errorBtn = document.createElement("button");
                        errorBtn.type = "button";
                        errorBtn.className = "action-btn";
                        errorBtn.textContent = "Could not load cameras";
                        errorBtn.disabled = true;
                        errorBtn.title = error.message || String(error);
                        individualWrap.appendChild(errorBtn);
                    });
            });
        }

        function appendCommandSubmenu(parent, label) {
            const submenu = document.createElement("details");
            submenu.className = "command-submenu";
            const summary = document.createElement("summary");
            summary.textContent = label;
            submenu.appendChild(summary);
            const items = document.createElement("div");
            items.className = "command-submenu-items";
            submenu.appendChild(items);
            parent.appendChild(submenu);
            return items;
        }

        // ---- Command search -------------------------------------------------
        // A "Search commands" box for the per-unit command menu and the Power
        // vs Cell Graphs modal's command rail. It walks the live DOM on every
        // keystroke instead of keeping a registry, so any .action-btn inside a
        // .command-submenu is searchable with no extra wiring.
        //
        // Every typed word must appear in an action's label. Matching a
        // submenu's own name ("cameras") shows everything inside it. Submenus
        // with a match open; the rest hide. Enter runs the action when exactly
        // one is left. Escape clears; Escape on an empty box is left to the
        // caller (closes the row menu, or the modal). Clearing puts every
        // submenu back open/closed exactly as it was.
        const COMMAND_SEARCH_SKIP = ".command-recent, .unit-notes-box, .unit-busy-banner, .command-search";

        function commandSearchMatches(text, terms) {
            const haystack = String(text || "").toLowerCase();
            return terms.every(function (term) { return haystack.indexOf(term) !== -1; });
        }

        function commandSubmenuLabel(details) {
            const summary = details.querySelector(":scope > summary");
            return summary ? summary.textContent : "";
        }

        function commandSearchHide(state, el, hide) {
            if (hide) {
                if (!el.hidden) {
                    el.hidden = true;
                    state.hidden.add(el);
                }
            } else if (state.hidden.has(el)) {
                el.hidden = false;
                state.hidden.delete(el);
            }
        }

        function restoreCommandSearch(state) {
            state.hidden.forEach(function (el) { el.hidden = false; });
            state.hidden.clear();
            if (state.openBefore) {
                state.openBefore.forEach(function (wasOpen, details) {
                    if (details.isConnected) {
                        details.open = wasOpen;
                    }
                });
            }
            state.openBefore = null;
        }

        // Walks up from el through the .command-submenu <details> inside root.
        function forEachCommandSubmenuAncestor(root, details, fn) {
            let walk = details;
            while (walk && root.contains(walk)) {
                fn(walk);
                walk = walk.parentElement && walk.parentElement.closest("details.command-submenu");
            }
        }

        // Returns the visible action buttons (empty when the query is blank).
        function filterCommandMenu(root, query, state) {
            const terms = String(query || "").toLowerCase().split(/\s+/).filter(Boolean);
            if (!terms.length) {
                restoreCommandSearch(state);
                return [];
            }
            const submenus = Array.prototype.filter.call(
                root.querySelectorAll("details.command-submenu"),
                function (details) { return !details.closest(COMMAND_SEARCH_SKIP); }
            );
            if (!state.openBefore) {
                state.openBefore = new Map();
                submenus.forEach(function (details) {
                    state.openBefore.set(details, details.open);
                });
            }
            // Submenus whose own name matches, plus everything nested in them.
            const nameMatched = new Set();
            submenus.forEach(function (details) {
                if (commandSearchMatches(commandSubmenuLabel(details), terms)) {
                    nameMatched.add(details);
                    details.querySelectorAll("details.command-submenu").forEach(function (inner) {
                        nameMatched.add(inner);
                    });
                }
            });
            const visibleSubmenus = new Set();
            const visibleButtons = [];
            root.querySelectorAll(".action-btn").forEach(function (btn) {
                if (btn.closest(COMMAND_SEARCH_SKIP)) {
                    return;
                }
                const parentSubmenu = btn.closest("details.command-submenu");
                const ownSubmenu = parentSubmenu && root.contains(parentSubmenu) ? parentSubmenu : null;
                const show = (ownSubmenu && nameMatched.has(ownSubmenu))
                    || commandSearchMatches(btn.textContent, terms);
                commandSearchHide(state, btn, !show);
                if (show) {
                    visibleButtons.push(btn);
                    forEachCommandSubmenuAncestor(root, ownSubmenu, function (d) { visibleSubmenus.add(d); });
                }
            });
            nameMatched.forEach(function (details) {
                forEachCommandSubmenuAncestor(root, details, function (d) { visibleSubmenus.add(d); });
            });
            submenus.forEach(function (details) {
                const show = visibleSubmenus.has(details);
                commandSearchHide(state, details, !show);
                details.open = show;
            });
            // The Recent strip repeats actions already in the tree.
            root.querySelectorAll(".command-recent").forEach(function (el) {
                commandSearchHide(state, el, true);
            });
            return visibleButtons;
        }

        // Builds the search box. getRoot() returns the element to search
        // (looked up on each keystroke, since menus get rebuilt).
        // onEscapeEmpty runs when Escape is pressed on an empty box; return
        // true from it to say the key was handled.
        function createCommandSearch(getRoot, onEscapeEmpty) {
            const wrap = document.createElement("div");
            wrap.className = "command-search";
            const input = document.createElement("input");
            input.type = "search";
            input.placeholder = "Search commands";
            input.setAttribute("aria-label", "Search commands");
            input.title = "Type to filter. Enter runs the action when only one is left. Esc clears.";
            input.autocomplete = "off";
            input.spellcheck = false;
            const empty = document.createElement("div");
            empty.className = "command-search-empty";
            empty.textContent = "No commands match.";
            empty.hidden = true;
            wrap.appendChild(input);
            wrap.appendChild(empty);
            const state = { hidden: new Set(), openBefore: null };
            let visible = [];

            function apply() {
                const root = getRoot();
                if (!root) {
                    return;
                }
                visible = filterCommandMenu(root, input.value, state);
                empty.hidden = !input.value.trim() || visible.length > 0;
            }

            input.addEventListener("input", apply);
            input.addEventListener("keydown", function (event) {
                if (event.key === "Enter") {
                    event.preventDefault();
                    if (visible.length === 1 && !visible[0].disabled) {
                        visible[0].click();
                    }
                    return;
                }
                if (event.key === "Escape") {
                    if (input.value) {
                        event.preventDefault();
                        event.stopPropagation();
                        input.value = "";
                        apply();
                        return;
                    }
                    if (onEscapeEmpty && onEscapeEmpty()) {
                        event.preventDefault();
                        event.stopPropagation();
                    }
                }
            });

            return {
                el: wrap,
                input: input,
                // Re-run the current query against the live DOM — after a
                // rebuild the old open/closed snapshot no longer applies.
                refilter: function () {
                    state.hidden.clear();
                    state.openBefore = null;
                    apply();
                },
                clear: function () {
                    input.value = "";
                    restoreCommandSearch(state);
                    empty.hidden = true;
                    visible = [];
                },
            };
        }

        // The row menu's search box lives inside .command-menu-items (the
        // floating panel), which the multi-unit chooser and a unit switch
        // rebuild — so this re-inserts it above the Recent strip / first
        // submenu whenever it's missing, and re-runs any query in progress.
        function ensureCommandMenuSearch(commandMenu) {
            const commandItems = commandMenu.querySelector(".command-menu-items");
            if (!commandItems) {
                return null;
            }
            if (!commandMenu._commandSearch) {
                commandMenu._commandSearch = createCommandSearch(
                    function () { return commandMenu.querySelector(".command-menu-items"); },
                    function () {
                        commandMenu.open = false;
                        const summary = commandMenu.querySelector("summary");
                        if (summary) {
                            summary.focus();
                        }
                        return true;
                    }
                );
            }
            const search = commandMenu._commandSearch;
            const anchor = commandItems.querySelector(":scope > .command-recent")
                || commandItems.querySelector(":scope > details.command-submenu");
            if (search.el.parentNode !== commandItems || (anchor && search.el.nextSibling !== anchor)) {
                if (anchor) {
                    commandItems.insertBefore(search.el, anchor);
                } else {
                    commandItems.appendChild(search.el);
                }
            }
            if (search.input.value) {
                search.refilter();
            }
            return search;
        }

        const commandMenuEntries = new WeakMap();

        function commandMenuButtonLabel(entry) {
            return entry && entry.unit ? String(entry.unit) : "Menu";
        }

        // Every unit token in a ticket subject's own leading unit segment —
        // "Region - Unit[/Unit...] - Rest" (see CLAUDE.md's "Unit
        // conventions") — normalized and de-duplicated, in the order they
        // appear. A single-unit subject still returns a one-item array, so
        // callers just check .length > 1 rather than branching on "is this
        // multi-unit" separately. Mirrors work_tool._noc_termination_
        // unit_token_pattern's own token shape (used server-side only for
        // Termination/Relocation project titles, which anchor on a known
        // "kind" keyword after the unit list) but doesn't need a keyword —
        // the unit segment's own position, right after the region code and
        // right before the next " - ", is enough on its own.
        const UNIT_TOKEN_PATTERN = "(?:RD|FD)\\s*\\d+(?:\\([^)]*\\))?|MU\\s*\\d+(?:\\([^)]*\\))?";
        // Units may be separated by "/", ",", "&", "+", "and", or nothing at
        // all — real subjects use every one of these ("RD3079(MU6006)/
        // RD3231(MU6007)", "RD3079(MU6006)RD3231(MU6007)"). Every token
        // starts with RD/FD/MU, so an empty separator is safe.
        const MULTI_UNIT_SEPARATOR_PATTERN = "\\s*(?:[/,&+]|and)?\\s*";
        const MULTI_UNIT_SUBJECT_PATTERN = new RegExp(
            "^[A-Z]{2,5}\\s*-\\s*"
            + "((?:" + UNIT_TOKEN_PATTERN + ")(?:" + MULTI_UNIT_SEPARATOR_PATTERN + "(?:" + UNIT_TOKEN_PATTERN + "))*)"
            + "\\s*-",
            "i"
        );
        function unitsFromTicketSubject(subject) {
            const text = String(subject || "").trim();
            if (!text) {
                return [];
            }
            const match = text.match(MULTI_UNIT_SUBJECT_PATTERN);
            if (!match) {
                return [];
            }
            const tokens = [];
            const seen = new Set();
            (match[1].match(new RegExp(UNIT_TOKEN_PATTERN, "gi")) || []).forEach(function (part) {
                const raw = part.replace(/\s+/g, "").toUpperCase();
                if (!raw) {
                    return;
                }
                const tokenMatch = raw.match(/^((?:RD|FD|MU)\d+)(\(.*\))?$/);
                const unit = tokenMatch ? tokenMatch[1] : raw;
                const label = tokenMatch ? (tokenMatch[1] + (tokenMatch[2] || "")) : raw;
                if (seen.has(unit)) {
                    return;
                }
                seen.add(unit);
                tokens.push({ unit: unit, label: label });
            });
            return tokens;
        }

        // A ticket listing 2+ units (e.g. a Security Update covering a
        // paired RD/MU set at one site) used to just silently pick one and
        // build the whole command menu around it, with no way to reach the
        // other unit(s) from that same row. On first open, if the subject
        // actually lists more than one, insert a unit dropdown right after
        // the status/flap/uptime rows (which stay put — their checks all
        // re-read commandMenu.dataset.unit live, so they keep working as
        // the dropdown switches units) and swap the rest of the menu's
        // content in place for whichever unit is picked, reusing
        // populateUnitToolsCommandMenu — the same full toolkit Unit Tools
        // itself builds — fed by /issues/unit-context/<unit> the same way
        // loadUnitTools already fetches it. This replaces the ticket-
        // specific submenus renderList originally built around the one
        // unit the ticket happened to resolve to first.
        function ensureMultiUnitChooser(commandMenu) {
            if (commandMenu.dataset.skipMultiUnitChooser === "1") {
                return;
            }
            if (commandMenu.dataset.multiUnitChecked === "1") {
                return;
            }
            commandMenu.dataset.multiUnitChecked = "1";
            const entry = commandMenuEntries.get(commandMenu);
            const tokens = unitsFromTicketSubject(entry && (entry.ticketSubject || entry.subject) || "");
            if (tokens.length < 2) {
                return;
            }
            const commandItems = commandMenu.querySelector(".command-menu-items");
            const anchor = commandItems && commandItems.querySelector(".command-menu-uptime");
            if (!anchor) {
                return;
            }
            let node = anchor.nextSibling;
            while (node) {
                const next = node.nextSibling;
                node.remove();
                node = next;
            }

            const pickerWrap = document.createElement("div");
            pickerWrap.className = "unit-tools-hint multi-unit-picker";
            const pickerLabel = document.createElement("span");
            pickerLabel.textContent = "This ticket lists multiple units: ";
            pickerWrap.appendChild(pickerLabel);
            const select = document.createElement("select");
            select.className = "multi-unit-select";
            tokens.forEach(function (token) {
                const opt = document.createElement("option");
                opt.value = token.unit;
                opt.textContent = token.label;
                select.appendChild(opt);
            });
            const startUnit = String((entry && entry.unit) || "").toUpperCase();
            if (tokens.some(function (token) { return token.unit === startUnit; })) {
                select.value = startUnit;
            }
            pickerWrap.appendChild(select);
            commandItems.appendChild(pickerWrap);

            // Everything the toolkit builds goes straight into commandItems
            // (flat, same as every other command menu) rather than a
            // nested wrapper — renderRecentCommands and others below
            // assume .command-submenu elements are DIRECT children of
            // commandItems (its own insertBefore(recentBox, firstSubmenu)
            // requires that), and a nested container broke that: caught
            // live, "Failed to execute 'insertBefore' ... not a child of
            // this node" the moment a fetched unit's toolkit rendered.
            function clearToolkit() {
                let node = pickerWrap.nextSibling;
                while (node) {
                    const next = node.nextSibling;
                    node.remove();
                    node = next;
                }
            }

            function refreshGlyphsForCurrentUnit() {
                checkAndApplyPowerGlyph(commandMenu);
                checkAndApplyShadingGlyph(commandMenu);
                checkAndApplyCameraOutageGlyph(commandMenu);
                checkAndApplyDeadPanelGlyph(commandMenu);
                checkAndApplyForecastGlyph(commandMenu);
                checkAndApplyFlapRow(commandMenu);
                applyPowerVsCellUptimeLine(commandMenu);
            }

            function loadUnitInto(unit, knownEntry) {
                function settle(resolvedEntry) {
                    if (select.value !== unit) {
                        // A later switch already superseded this — drop it.
                        return;
                    }
                    commandMenuEntries.set(commandMenu, resolvedEntry);
                    commandMenu.dataset.unit = resolvedEntry.unit || unit;
                    clearToolkit();
                    populateUnitToolsCommandMenu(commandItems, resolvedEntry);
                    updateCommandMenuContext(commandMenu);
                    refreshGlyphsForCurrentUnit();
                    renderRecentCommands(commandItems);
                    ensureCommandMenuSearch(commandMenu);
                }
                if (knownEntry) {
                    settle(knownEntry);
                    return;
                }
                clearToolkit();
                const loading = document.createElement("div");
                loading.className = "unit-tools-hint";
                loading.textContent = "Loading " + unit + "...";
                commandItems.appendChild(loading);
                fetch("/issues/unit-context/" + encodeURIComponent(unit))
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        settle(makeListEntry(data));
                    })
                    .catch(function (error) {
                        if (select.value !== unit) {
                            return;
                        }
                        clearToolkit();
                        const err = document.createElement("div");
                        err.className = "unit-tools-hint";
                        err.textContent = "Failed to load " + unit + ": " + (error.message || error);
                        commandItems.appendChild(err);
                    });
            }

            select.addEventListener("change", function () {
                loadUnitInto(select.value, null);
            });

            // The entry this menu already had carries the resolved unit's
            // own device info (switch/fisheye/PVE IPs, etc. — see
            // _with_ticket_links) — no fetch needed to show it right away.
            loadUnitInto(select.value, select.value === startUnit ? entry : null);
        }

        function updateCommandMenuContext(commandMenu) {
            const entry = commandMenuEntries.get(commandMenu);
            const commandItems = commandMenu.querySelector(".command-menu-items");
            if (!commandItems) {
                return;
            }
            let contextEl = commandItems.querySelector(".command-menu-context");
            if (!entry) {
                if (contextEl) {
                    contextEl.remove();
                }
                const staleBanner = commandItems.querySelector(".unit-busy-banner");
                if (staleBanner) {
                    staleBanner.remove();
                }
                const staleNotes = commandItems.querySelector(".unit-notes-box");
                if (staleNotes) {
                    staleNotes.remove();
                }
                return;
            }
            if (!contextEl) {
                contextEl = document.createElement("div");
                contextEl.className = "command-menu-context";
                commandItems.insertBefore(contextEl, commandItems.firstChild);
            }
            const unit = entry.unit || "";
            const subject = entry.ticketSubject || "";
            contextEl.innerHTML = "";
            const strong = document.createElement("strong");
            strong.textContent = unit || "Unit tools";
            contextEl.appendChild(strong);
            if (subject) {
                const sub = document.createElement("span");
                sub.textContent = subject.length > 72
                    ? subject.slice(0, 69) + "..."
                    : subject;
                contextEl.appendChild(sub);
            }
            if (unit) {
                refreshUnitStatusPanel(commandItems, unit);
            }
        }

        // The shared per-unit note (/issues/unit-note/<unit>, one JSON file
        // for everyone). Built here once and reused by every command menu
        // (refreshUnitStatusPanel) and the Graphs modal's rail, so a note
        // written in one shows in the other. Ctrl+Enter saves.
        function createUnitNotesBox() {
            const notesBox = document.createElement("div");
            notesBox.className = "unit-notes-box";
            const textarea = document.createElement("textarea");
            textarea.placeholder = "Notes for this unit (visible to everyone)...";
            notesBox.appendChild(textarea);
            const row = document.createElement("div");
            const saveBtn = document.createElement("button");
            saveBtn.type = "button";
            saveBtn.className = "action-btn";
            saveBtn.textContent = "Save Note";
            saveBtn.title = "Save for everyone (Ctrl+Enter). Saving an empty note clears it.";
            const noteStatus = document.createElement("span");
            noteStatus.className = "note-status";
            row.appendChild(saveBtn);
            row.appendChild(noteStatus);
            notesBox.appendChild(row);
            saveBtn.addEventListener("click", function () {
                const unit = notesBox.dataset.unit || "";
                if (!unit) {
                    return;
                }
                saveBtn.disabled = true;
                noteStatus.textContent = "Saving...";
                fetch("/issues/unit-note/" + encodeURIComponent(unit), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ text: textarea.value }),
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        noteStatus.textContent = data.updated_at
                            ? ("Saved " + formatNoteTimestamp(data.updated_at))
                            : "Cleared";
                    })
                    .catch(function (error) {
                        noteStatus.textContent = "Save failed";
                        notify("Could not save the note for " + unit + ": "
                            + ((error && error.message) || error) + ". Your text is still in the box — try Save again.", "error");
                    })
                    .finally(function () {
                        saveBtn.disabled = false;
                    });
            });
            // Marks the box as edited so a slow initial load (loadUnitNote)
            // can't land afterwards and wipe what was typed.
            textarea.addEventListener("input", function () {
                notesBox.dataset.edited = "1";
            });
            textarea.addEventListener("keydown", function (event) {
                if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    if (!saveBtn.disabled) {
                        saveBtn.click();
                    }
                }
            });
            return notesBox;
        }

        function formatNoteTimestamp(isoText) {
            return String(isoText || "").replace("T", " ");
        }

        function loadUnitNote(notesBox, unit) {
            notesBox.dataset.unit = unit || "";
            notesBox.dataset.edited = "";
            const textarea = notesBox.querySelector("textarea");
            const noteStatus = notesBox.querySelector(".note-status");
            textarea.value = "";
            noteStatus.textContent = "";
            if (!unit) {
                return;
            }
            fetch("/issues/unit-note/" + encodeURIComponent(unit))
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    if (notesBox.dataset.unit !== unit || notesBox.dataset.edited) {
                        return;
                    }
                    textarea.value = data.text || "";
                    if (data.updated_at) {
                        noteStatus.textContent = "Saved " + formatNoteTimestamp(data.updated_at);
                    }
                })
                .catch(function () {
                    if (notesBox.dataset.unit !== unit || notesBox.dataset.edited) {
                        return;
                    }
                    // Say so: an empty box after a failed load looks like
                    // "no note," and saving it would wipe the real one.
                    noteStatus.textContent = "Could not load the saved note — saving now would replace it.";
                });
        }

        // Busy banner + per-unit notes, refreshed whenever a per-unit command
        // menu is opened. Shared by every menu surface since they all build
        // their menu through createCommandMenuElement/updateCommandMenuContext.
        function refreshUnitStatusPanel(commandItems, unit) {
            let banner = commandItems.querySelector(".unit-busy-banner");
            let notesBox = commandItems.querySelector(".unit-notes-box");
            const contextEl = commandItems.querySelector(".command-menu-context");
            if (!notesBox) {
                notesBox = createUnitNotesBox();
                if (contextEl && contextEl.nextSibling) {
                    commandItems.insertBefore(notesBox, contextEl.nextSibling);
                } else {
                    commandItems.insertBefore(notesBox, commandItems.firstChild);
                }
            }
            if (!banner) {
                banner = document.createElement("div");
                banner.className = "unit-busy-banner";
                banner.hidden = true;
                commandItems.insertBefore(banner, notesBox);
            }

            if (notesBox.dataset.unit !== unit) {
                loadUnitNote(notesBox, unit);
            }

            banner.dataset.unit = unit;
            fetch("/issues/unit-status/" + encodeURIComponent(unit))
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    if (banner.dataset.unit !== unit) {
                        return;
                    }
                    if (!data.busy) {
                        banner.hidden = true;
                        banner.innerHTML = "";
                        return;
                    }
                    banner.hidden = false;
                    banner.innerHTML = "";
                    const label = document.createElement("div");
                    label.textContent = "⏳ " + (data.action || "Busy")
                        + (data.phase ? (" — " + data.phase) : "");
                    banner.appendChild(label);
                    const clearBtn = document.createElement("button");
                    clearBtn.type = "button";
                    clearBtn.className = "action-btn";
                    clearBtn.textContent = "Force Clear Lock";
                    clearBtn.addEventListener("click", function () {
                        clearBtn.disabled = true;
                        fetch("/issues/unit-lock/" + encodeURIComponent(unit) + "/clear", { method: "POST" })
                            .then(function (response) { return response.json(); })
                            .then(function () {
                                banner.hidden = true;
                                banner.innerHTML = "";
                            })
                            .catch(function () {
                                clearBtn.disabled = false;
                            });
                    });
                    banner.appendChild(clearBtn);
                })
                .catch(function () {});
        }

        function createCommandMenuElement(entry, rowEl, options) {
            const commandMenu = document.createElement("details");
            commandMenu.className = "command-menu";
            // Callers that already resolved one specific unit out of a
            // multi-unit ticket (Unit Tools, a fleet-report row) pass this
            // so the pill/menu don't re-offer the same choice again — see
            // ensureMultiUnitChooser's own comment on this flag.
            const skipMultiUnitChooser = !!(options && options.skipMultiUnitChooser);
            if (skipMultiUnitChooser) {
                commandMenu.dataset.skipMultiUnitChooser = "1";
            }
            const unitLabel = commandMenuButtonLabel(entry);
            commandMenu.dataset.unit = unitLabel;
            const commandSummary = document.createElement("summary");
            // A ticket listing more than one unit gets a visible hint on
            // the pill itself, before it's even opened — see
            // ensureMultiUnitChooser for what opening it actually shows.
            const multiUnitTokens = unitsFromTicketSubject(
                (entry && (entry.ticketSubject || entry.subject)) || ""
            );
            if (!skipMultiUnitChooser && multiUnitTokens.length > 1) {
                commandSummary.textContent = unitLabel + " (+" + (multiUnitTokens.length - 1) + ")";
                commandSummary.title = "This ticket lists " + multiUnitTokens.length
                    + " units — click to choose one";
            } else {
                commandSummary.textContent = unitLabel;
                commandSummary.setAttribute("aria-label", "Commands for " + unitLabel);
            }
            commandMenu.appendChild(commandSummary);
            const commandItems = document.createElement("div");
            commandItems.className = "command-menu-items";
            commandMenu.appendChild(commandItems);

            // The Diagnostic Header — above even the status row, so a real
            // finding is the first thing read, before the unit name even
            // settles in. Built here (empty, hidden) and filled in by
            // renderDiagnosticHeader once the shading/dead-panel checks
            // that already run on open (see checkAndApplyShadingGlyph /
            // checkAndApplyDeadPanelGlyph below) land — a clean unit shows
            // nothing here, same alert-only convention as those checks'
            // own glyphs.
            const diagnosticHeader = document.createElement("div");
            diagnosticHeader.className = "command-diagnostic-header";
            diagnosticHeader.hidden = true;
            commandItems.appendChild(diagnosticHeader);

            // Plug/alarm status lives INSIDE the expanded menu, not on the
            // collapsed summary button — the button is just a label; these
            // are read once someone actually opens the menu, so that's
            // where they show up too. First child of commandItems so they
            // sit above whatever buttons the caller appends next; on the
            // first open, updateCommandMenuContext inserts the unit/subject
            // header above this row, so the settled order reads unit name,
            // then status, then the rest of the menu.
            const statusRow = document.createElement("div");
            statusRow.className = "command-menu-status";
            const alarmGlyph = document.createElement("span");
            alarmGlyph.className = "command-alarm-glyph";
            alarmGlyph.textContent = "⚠";
            alarmGlyph.hidden = true;
            alarmGlyph.addEventListener("click", function (event) {
                event.stopPropagation();
                const unit = String(commandMenu.dataset.unit || "").toUpperCase();
                const info = powerInfraAlarmedUnits[unit];
                if (!info) {
                    return;
                }
                notify(
                    "Active alert — " + unit + "\n" + powerInfraAlertSummaryText(unit, info),
                    "error",
                    {
                        actionLabel: "Open Power & Infra Alerts",
                        onAction: function () {
                            // Power & Infra Alerts lives on the Reports page
                            // now — switch there so it isn't shown mixed in
                            // alongside whatever Issues/Projects lists are
                            // also on screen.
                            if (panelModeEl && panelModeEl.value !== "reports") {
                                panelModeEl.value = "reports";
                                applyPanelMode();
                            }
                            if (!powerInfraLoaded) {
                                loadPowerInfraAlerts();
                            }
                            if (powerInfraSection && powerInfraSection.scrollIntoView) {
                                powerInfraSection.scrollIntoView({ behavior: "smooth", block: "start" });
                            }
                        },
                    }
                );
            });
            wireGlyphKeyboardActivation(alarmGlyph);
            statusRow.appendChild(alarmGlyph);
            const powerGlyph = document.createElement("span");
            powerGlyph.className = "command-power-glyph";
            powerGlyph.textContent = "🔌";
            powerGlyph.hidden = true;
            powerGlyph.addEventListener("click", function (event) {
                event.stopPropagation();
                openVrmForEntry(commandMenuEntries.get(commandMenu));
            });
            wireGlyphKeyboardActivation(powerGlyph);
            statusRow.appendChild(powerGlyph);
            // Shading is a pure alert, unlike the plug glyph — it only
            // ever appears when detect_solar_shading actually found a
            // sustained deficit, never as a quiet "checked, all clear"
            // confirmation (see checkAndApplyShadingGlyph).
            const shadingGlyph = document.createElement("span");
            shadingGlyph.className = "command-shading-glyph";
            shadingGlyph.textContent = "🌳";
            shadingGlyph.hidden = true;
            shadingGlyph.addEventListener("click", function (event) {
                event.stopPropagation();
                const entry = commandMenuEntries.get(commandMenu);
                if (!entry || !entry.unit) {
                    return;
                }
                openGraphsModal(entry.unit, "battery", entry.ticketSubject || entry.subject || "");
                // Also open the shading snapshot photo in its own tab, if
                // one's already been captured for this unit — same "prove
                // it, don't just say it" thumbnail the Diagnostic Header
                // shows (see diagnosticHeaderScheduleControl), just
                // reachable straight from the glyph too. Silent (no
                // toast/error) when there's no task or no image yet —
                // "if they exist" only, not a failure to report.
                fetch("/issues/shading-snapshot-task/" + encodeURIComponent(entry.unit))
                    .then(function (response) { return response.json(); })
                    .then(function (data) {
                        const task = data && data.ok ? data.task : null;
                        if (!task || !task.has_image) {
                            return;
                        }
                        const win = openBlankTab("/issues/shading-snapshot-image/" + task.id);
                        if (!win) {
                            notifyError(
                                "Pop-up blocked. Allow pop-ups for this site to open the shading snapshot."
                            );
                        }
                    })
                    .catch(function () {});
            });
            wireGlyphKeyboardActivation(shadingGlyph);
            statusRow.appendChild(shadingGlyph);
            // A "camera image buffer... remained below X% for N minutes"
            // Zabbix finding (SNUC-Watch) means a camera has stopped
            // sending frames — see checkAndApplyCameraOutageGlyph. Click
            // jumps straight to Scrypted (and Platform, if this is a
            // Scrypted/PVE unit) to go look, same "the indicator IS the
            // shortcut" pattern as the plug/shading glyphs' own clicks.
            const cameraOutageGlyph = document.createElement("span");
            cameraOutageGlyph.className = "command-camera-outage-glyph";
            cameraOutageGlyph.textContent = "📷";
            cameraOutageGlyph.hidden = true;
            cameraOutageGlyph.addEventListener("click", function (event) {
                event.stopPropagation();
                const entry = commandMenuEntries.get(commandMenu);
                if (!entry || !entry.unit) {
                    return;
                }
                if (!entry.hasScrypted) {
                    // NUC units have no Scrypted/Platform to jump to —
                    // show the camera snapshot grid instead, so this
                    // glyph is always a useful shortcut either way.
                    openCameraSnapshotGrid(entry.unit);
                    return;
                }
                let opened = false;
                if (entry.scryptedUrl) {
                    openBlankTab(entry.scryptedUrl);
                    opened = true;
                }
                if (entry.platformUrl) {
                    openBlankTab(entry.platformUrl);
                    opened = true;
                }
                if (!opened) {
                    notifyError("No Scrypted/Platform URL available for this unit");
                }
                // Runs the same check as the Scrypted menu's own "Get Ram
                // Folder" button — this glyph IS the /mnt/ram buffer
                // alert, so a click should get straight to which
                // camera/room is actually the problem, not just open
                // Scrypted and leave that lookup for later.
                runGetRamFolder(entry.unit, null, entry);
            });
            wireGlyphKeyboardActivation(cameraOutageGlyph);
            statusRow.appendChild(cameraOutageGlyph);
            // Same pure-alert treatment as the shading glyph, for
            // detect_dead_panel's own finding (see checkAndApplyDeadPanelGlyph).
            const deadPanelGlyph = document.createElement("span");
            deadPanelGlyph.className = "command-dead-panel-glyph";
            deadPanelGlyph.textContent = "🔧";
            deadPanelGlyph.hidden = true;
            deadPanelGlyph.addEventListener("click", function (event) {
                event.stopPropagation();
                const entry = commandMenuEntries.get(commandMenu);
                if (!entry || !entry.unit) {
                    return;
                }
                openGraphsModal(entry.unit, "battery", entry.ticketSubject || entry.subject || "");
            });
            wireGlyphKeyboardActivation(deadPanelGlyph);
            statusRow.appendChild(deadPanelGlyph);
            // Battery SOC — a small colored pill with the percentage as
            // visible text rather than a bare emoji-circle like its
            // neighbors, since "72%" said outright is faster to read at a
            // glance than a color a tech has to decode. Filled in by
            // applyBatteryGlyphFromCache alongside the plug glyph, off the
            // same /issues/power-status fetch (see checkAndApplyPowerGlyph).
            const batteryGlyph = document.createElement("span");
            batteryGlyph.className = "command-battery-glyph";
            batteryGlyph.hidden = true;
            // Same "Open VRM" action as the Plugged In / VRM Disconnected
            // glyphs (see openVrmForEntry) — the battery % reading comes
            // from VRM in the first place, so clicking it is the natural
            // way to go look at the real graph behind the number.
            batteryGlyph.addEventListener("click", function (event) {
                event.stopPropagation();
                openVrmForEntry(commandMenuEntries.get(commandMenu));
            });
            wireGlyphKeyboardActivation(batteryGlyph);
            statusRow.appendChild(batteryGlyph);
            // VRM freshness — alert-only like shading/dead-panel, shown
            // only for "stale"/"disconnected" (see applyVrmFreshnessGlyphFromCache).
            // Clicking it opens VRM directly, same "Open VRM" action as the
            // Plugged In glyph (see openVrmForEntry) — a disconnected VRM
            // reading is exactly when a tech wants VRM open, not a detour
            // through the Reports list first.
            const vrmFreshnessGlyph = document.createElement("span");
            vrmFreshnessGlyph.className = "command-vrm-freshness-glyph";
            vrmFreshnessGlyph.textContent = "📡";
            vrmFreshnessGlyph.hidden = true;
            vrmFreshnessGlyph.addEventListener("click", function (event) {
                event.stopPropagation();
                openVrmForEntry(commandMenuEntries.get(commandMenu));
            });
            wireGlyphKeyboardActivation(vrmFreshnessGlyph);
            statusRow.appendChild(vrmFreshnessGlyph);
            // Battery Outlook's 5-day cloud forecast — info glyph, shown
            // whenever a forecast resolved at all, not gated on risk (see
            // forecastGlyphElement). Filled in by checkAndApplyForecastGlyph
            // on open, off /issues/battery-outlook — a separate fetch from
            // the power-status one above, since it needs a GPS resolution
            // and an Open-Meteo call the others don't.
            const forecastGlyph = document.createElement("span");
            forecastGlyph.className = "command-forecast-glyph";
            forecastGlyph.hidden = true;
            statusRow.appendChild(forecastGlyph);
            // Power vs Cell Outage — filled in by applyPowerVsCellGlyph off
            // the scheduled sweep's cache (see pollPowerVsCellCache), same
            // bulk pattern as the ⚠ alarm glyph. Click re-runs the
            // single-unit check fresh (same endpoint as the Switch
            // submenu's own button) rather than waiting for the next sweep.
            const powerVsCellGlyph = document.createElement("span");
            powerVsCellGlyph.className = "command-power-vs-cell-glyph";
            powerVsCellGlyph.hidden = true;
            powerVsCellGlyph.addEventListener("click", function (event) {
                event.stopPropagation();
                const unit = String(commandMenu.dataset.unit || "").toUpperCase();
                if (!unit) {
                    return;
                }
                const previousTitle = powerVsCellGlyph.title;
                powerVsCellGlyph.title = "Checking " + unit + "...";
                // issue_id (when known) lets the server prefer the loss
                // window matching when this ticket was actually opened —
                // see unit_power_vs_cell_outage's docstring.
                const glyphEntry = commandMenuEntries.get(commandMenu);
                const glyphIssueId = glyphEntry && glyphEntry.issueId;
                fetch("/issues/power-vs-cell-outage/" + encodeURIComponent(unit), {
                    method: "POST",
                    headers: glyphIssueId ? { "Content-Type": "application/json" } : undefined,
                    body: glyphIssueId ? JSON.stringify({ issue_id: glyphIssueId }) : undefined,
                })
                    .then(function (response) { return response.json(); })
                    .then(function (data) {
                        if (!data.ok) {
                            powerVsCellGlyph.title = previousTitle;
                            notify("Power vs Cell Outage re-check failed for " + unit + ": " + (data.error || "unknown error"), "error");
                            return;
                        }
                        consoleLines.push(data.summary || (unit + " — " + data.verdict));
                        renderConsole(true);
                        // Auto-dismisses after 5s unless moused over — same
                        // "already in the console, this toast is a
                        // convenience" reasoning as openPowerVsCellRowDetail's
                        // own notify call.
                        notify(
                            data.summary || (unit + " — " + data.verdict),
                            data.status === "warn" ? "error" : "info",
                            { autoDismissIfNotHoveredMs: 5000 }
                        );
                        powerVsCellAlarmedUnits[unit] = data;
                        applyPowerVsCellGlyph(commandMenu);
                        applyPowerVsCellUptimeLine(commandMenu);
                    })
                    .catch(function (error) {
                        powerVsCellGlyph.title = previousTitle;
                        notify("Power vs Cell Outage re-check failed for " + unit + ": " + (error.message || error), "error");
                    });
            });
            wireGlyphKeyboardActivation(powerVsCellGlyph);
            statusRow.appendChild(powerVsCellGlyph);
            commandItems.appendChild(statusRow);

            // Flap graph — alert-only like the Diagnostic Header above, not
            // informational like the uptime line below it: a unit only
            // shows a history here once unit_history has recorded enough
            // transitions to call it flapping (see checkAndApplyFlapRow),
            // same threshold as the Flap Report itself.
            const flapRow = document.createElement("div");
            flapRow.className = "command-menu-flap";
            flapRow.hidden = true;
            commandItems.appendChild(flapRow);

            // Switch uptime — informational, not alert-gated (see
            // applyPowerVsCellUptimeLine); sits right under the status row
            // so it's part of the same "what's this unit's situation"
            // glance, without competing with the alert glyphs above it.
            // Clickable to force a fresh SSH read instead of only ever
            // showing the extrapolated-from-the-last-sweep number — same
            // /issues/robofiber-uptime call and cache update the "Switch
            // Uptime" quick action/submenu button already use
            // (applyFreshSwitchUptime), just reachable from the line
            // itself without hunting for that button.
            const uptimeLine = document.createElement("div");
            uptimeLine.className = "command-menu-uptime";
            uptimeLine.hidden = true;
            uptimeLine.addEventListener("click", function (event) {
                event.stopPropagation();
                if (uptimeLine.classList.contains("is-loading")) {
                    return;
                }
                const unit = String(commandMenu.dataset.unit || "").toUpperCase();
                if (!unit) {
                    return;
                }
                const original = uptimeLine.textContent;
                uptimeLine.classList.add("is-loading");
                uptimeLine.textContent = "Refreshing switch uptime...";
                fetch("/issues/robofiber-uptime/" + encodeURIComponent(unit), { method: "POST" })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        applyFreshSwitchUptime(unit, data, commandMenu);
                    })
                    .catch(function (error) {
                        uptimeLine.textContent = original;
                        notifyError("Switch uptime refresh failed for " + unit + ": " + (error.message || error));
                    })
                    .finally(function () {
                        uptimeLine.classList.remove("is-loading");
                    });
            });
            wireGlyphKeyboardActivation(uptimeLine);
            commandItems.appendChild(uptimeLine);

            commandMenuEntries.set(commandMenu, entry);
            wireCommandMenuToggle(commandMenu, rowEl);
            applyPowerInfraGlyph(commandMenu);
            applyCameraOutageGlyph(commandMenu);
            applyPowerVsCellGlyph(commandMenu);
            applyPowerVsCellUptimeLine(commandMenu);
            return {
                commandMenu: commandMenu,
                commandItems: commandItems,
            };
        }

        function wireCommandMenuToggle(commandMenu, li) {
            commandMenu.addEventListener("toggle", function () {
                const sectionEl = commandMenu.closest(".list-section");
                li.classList.toggle("menu-open", commandMenu.open);
                if (sectionEl) {
                    sectionEl.classList.toggle("menu-open", commandMenu.open);
                }
                if (commandMenu.open) {
                    document.querySelectorAll("details.command-menu").forEach(function (menu) {
                        if (menu !== commandMenu) {
                            menu.open = false;
                        }
                    });
                    // Wipes commandItems down to just a unit chooser when
                    // the ticket lists more than one — must run BEFORE
                    // updateCommandMenuContext, which inserts its own
                    // subject/notes header at the top of whatever's there
                    // right after.
                    ensureMultiUnitChooser(commandMenu);
                    updateCommandMenuContext(commandMenu);
                    placeCommandMenu(commandMenu);
                    renderRecentCommands(commandMenu.querySelector(".command-menu-items"));
                    const commandSearch = ensureCommandMenuSearch(commandMenu);
                    placeCommandMenu(commandMenu); // the box adds height
                    if (commandSearch) {
                        commandSearch.input.focus({ preventScroll: true });
                    }
                    checkAndApplyPowerGlyph(commandMenu);
                    checkAndApplyShadingGlyph(commandMenu);
                    checkAndApplyCameraOutageGlyph(commandMenu);
                    checkAndApplyDeadPanelGlyph(commandMenu);
                    checkAndApplyForecastGlyph(commandMenu);
                    checkAndApplyFlapRow(commandMenu);
                    // Re-applied on every open (not just at menu build/poll
                    // time) so "current uptime (est.)" re-extrapolates from
                    // however much time has passed since the sweep last
                    // checked, rather than showing a number that was only
                    // accurate the moment the menu was built.
                    applyPowerVsCellUptimeLine(commandMenu);
                } else {
                    // Next open starts with the full menu, not a stale filter.
                    if (commandMenu._commandSearch) {
                        commandMenu._commandSearch.clear();
                    }
                    clearCommandMenuPosition(commandMenu);
                }
            });
        }

        // ---- Recently-used commands ------------------------------------------
        // The menu is deep (dozens of actions, several submenu levels), so a
        // small "Recent" strip surfaces whichever of those you actually use —
        // no restructuring of the existing tree, just a shortcut to it.
        // Tracked per browser (localStorage), same as the other UI-only state.
        const RECENT_COMMANDS_KEY = "commandMenuRecentActions";
        const RECENT_COMMANDS_MAX = 6;

        function getRecentCommands() {
            try {
                const raw = window.localStorage.getItem(RECENT_COMMANDS_KEY);
                const list = raw ? JSON.parse(raw) : [];
                return Array.isArray(list) ? list.filter(function (item) { return typeof item === "string"; }) : [];
            } catch (ignore) {
                return [];
            }
        }

        function recordRecentCommand(label) {
            const clean = String(label || "").trim();
            if (!clean) {
                return;
            }
            try {
                const list = getRecentCommands().filter(function (item) { return item !== clean; });
                list.unshift(clean);
                window.localStorage.setItem(
                    RECENT_COMMANDS_KEY,
                    JSON.stringify(list.slice(0, RECENT_COMMANDS_MAX))
                );
            } catch (ignore) {
                // localStorage unavailable — recency just won't persist.
            }
        }

        // One delegated listener covers every command menu (both builders
        // below share the same .action-btn contract), so a new action needs
        // no extra wiring to show up here once it's been used.
        document.addEventListener("click", function (event) {
            const btn = event.target.closest(".command-menu-items .action-btn");
            if (btn && !btn.closest(".command-recent")) {
                recordRecentCommand(btn.textContent);
            }
        }, true);

        function renderRecentCommands(commandItems) {
            if (!commandItems) {
                return;
            }
            let recentBox = commandItems.querySelector(".command-recent");
            const matches = [];
            getRecentCommands().forEach(function (label) {
                const original = Array.from(commandItems.querySelectorAll(".action-btn")).find(
                    function (el) {
                        return !el.closest(".command-recent") && el.textContent.trim() === label;
                    }
                );
                // Skip labels that don't apply to this unit (e.g. a PVE-only
                // action recently used elsewhere) rather than show a dead shortcut.
                if (original) {
                    matches.push({ label: label, original: original });
                }
            });
            if (!matches.length) {
                if (recentBox) {
                    recentBox.remove();
                }
                return;
            }
            if (!recentBox) {
                recentBox = document.createElement("div");
                recentBox.className = "command-recent";
                const label = document.createElement("span");
                label.className = "command-recent-label";
                label.textContent = "Recent:";
                recentBox.appendChild(label);
            } else {
                Array.from(recentBox.querySelectorAll(".command-recent-btn")).forEach(function (b) {
                    if (b._syncObserver) {
                        b._syncObserver.disconnect();
                    }
                    b.remove();
                });
            }
            matches.forEach(function (item) {
                const shortcut = document.createElement("button");
                shortcut.type = "button";
                shortcut.className = "action-btn command-recent-btn";
                shortcut.textContent = item.label;
                shortcut.title = "Recently used in this menu";
                shortcut.addEventListener("click", function () {
                    item.original.click();
                });
                // The shortcut only re-triggers the real button's own click
                // handler — that's what actually sets disabled/"Verb-ing..."
                // while the action runs (see e.g. appendValidateButton) —
                // but that happens on the ORIGINAL button, buried in its own
                // submenu, out of sight. Without mirroring it here, clicking
                // "Recent: Validate (Full)" looked like nothing happened
                // (caught live: "recent buttons are lacking the feature" —
                // the running-state feedback wasn't gone, just invisible on
                // the one button anyone was actually looking at).
                const syncRecentState = function () {
                    shortcut.disabled = item.original.disabled;
                    shortcut.textContent = item.original.textContent;
                };
                shortcut._syncObserver = new MutationObserver(syncRecentState);
                shortcut._syncObserver.observe(item.original, {
                    attributes: true, attributeFilter: ["disabled"],
                    childList: true, characterData: true, subtree: true,
                });
                recentBox.appendChild(shortcut);
            });
            const firstSubmenu = commandItems.querySelector(".command-submenu");
            if (firstSubmenu) {
                commandItems.insertBefore(recentBox, firstSubmenu);
            } else if (!recentBox.parentNode) {
                commandItems.appendChild(recentBox);
            }
        }

        // Factored out of populateUnitToolsCommandMenu so the Graphs modal's
        // device-tools accordion (see openGraphsDeviceMenu) can build just
        // this one section without dragging in Validate/Weather/Cameras,
        // which don't make sense next to a network/battery graph. Matches
        // the pattern every other top-level section already follows
        // (appendRouterCommandMenu, appendDiagnosticsCommandMenu,
        // appendArtMenu, appendLinuxCommandMenus) — Open and Switch were
        // just the two still inlined directly in the one caller.
        function appendOpenCommandMenu(commandItems, entry) {
            const openMenu = appendCommandSubmenu(commandItems, "Open");
            appendShieldMenu(openMenu, entry);
            appendErpMenu(openMenu, entry);

            const meshBtn = document.createElement("a");
            meshBtn.className = "action-btn";
            meshBtn.href = meshBaseUrl
                + encodeURIComponent(entry.unit);
            meshBtn.target = "_blank";
            meshBtn.rel = "noopener noreferrer";
            meshBtn.textContent = "Open Mesh";
            openMenu.appendChild(meshBtn);

            const raindanceBtn = document.createElement("a");
            raindanceBtn.className = "action-btn";
            raindanceBtn.href = raindanceBaseUrl
                + encodeURIComponent(entry.unit);
            raindanceBtn.target = "_blank";
            raindanceBtn.rel = "noopener noreferrer";
            raindanceBtn.textContent = "Open Raindance";
            openMenu.appendChild(raindanceBtn);

            if (entry.switchUrl) {
                const switchBtn = document.createElement("a");
                switchBtn.className = "action-btn";
                switchBtn.href = "/issues/switch/" + encodeURIComponent(entry.unit);
                switchBtn.target = "_blank";
                switchBtn.rel = "noopener noreferrer";
                switchBtn.textContent = "Open Switch";
                openMenu.appendChild(switchBtn);
            } else {
                const switchBtn = document.createElement("button");
                switchBtn.type = "button";
                switchBtn.className = "action-btn";
                switchBtn.textContent = "Open Switch";
                switchBtn.disabled = true;
                switchBtn.title = "No switch IP in net sheet";
                openMenu.appendChild(switchBtn);
            }

            // Plain http://<router ip>/ — no login automation (unlike Open
            // Switch), just the router's own web UI, same as typing its IP
            // in manually. No pre-resolved routerUrl on entry (unlike
            // switchUrl), so this always renders as a live link and lets
            // /issues/router/ report "No router IP in net sheet" itself
            // for the rare unit missing one, rather than round-tripping to
            // check first.
            if (entry.unit) {
                const routerBtn = document.createElement("a");
                routerBtn.className = "action-btn";
                routerBtn.href = "/issues/router/" + encodeURIComponent(entry.unit);
                routerBtn.target = "_blank";
                routerBtn.rel = "noopener noreferrer";
                routerBtn.textContent = "Open Router";
                openMenu.appendChild(routerBtn);
            }

            if (entry.hasPve) {
                const pveBtn = document.createElement("a");
                pveBtn.className = "action-btn";
                pveBtn.href = "/issues/pve/" + encodeURIComponent(entry.unit);
                pveBtn.target = "_blank";
                pveBtn.rel = "noopener noreferrer";
                pveBtn.textContent = "Open PVE";
                openMenu.appendChild(pveBtn);
            }

            if (entry.hasPlatform) {
                if (entry.platformUrl) {
                    const platformBtn = document.createElement("a");
                    platformBtn.className = "action-btn";
                    platformBtn.href = entry.platformUrl;
                    platformBtn.target = "_blank";
                    platformBtn.rel = "noopener noreferrer";
                    platformBtn.textContent = "Open Platform";
                    openMenu.appendChild(platformBtn);
                } else {
                    const platformBtn = document.createElement("button");
                    platformBtn.type = "button";
                    platformBtn.className = "action-btn";
                    platformBtn.textContent = "Open Platform";
                    platformBtn.disabled = true;
                    platformBtn.title = "No Scrypted IP in net sheet";
                    openMenu.appendChild(platformBtn);
                }
            }

            if (entry.hasRelay) {
                const relayBtn = document.createElement("a");
                relayBtn.className = "action-btn";
                relayBtn.href = "/issues/relay/" + encodeURIComponent(entry.unit);
                relayBtn.target = "_blank";
                relayBtn.rel = "noopener noreferrer";
                relayBtn.textContent = "Open Relay";
                openMenu.appendChild(relayBtn);
            }

            appendOpenScryptedButton(openMenu, entry);
            appendOpenVrmButton(openMenu, entry);
        }

        function appendSwitchCommandMenu(commandItems, entry) {
            const switchMenu = appendCommandSubmenu(commandItems, "Switch");

            function appendBounceButton(label, endpoint, parentMenu, confirmMessage) {
                const bounceBtn = document.createElement("button");
                bounceBtn.type = "button";
                bounceBtn.className = "action-btn";
                bounceBtn.textContent = label;
                bounceBtn.addEventListener("click", function () {
                    if (confirmMessage) {
                        openGenericConfirmModal(label + "?", confirmMessage, label, function () {
                            executeBounceAction(entry.unit, label, endpoint, bounceBtn);
                        });
                        return;
                    }
                    executeBounceAction(entry.unit, label, endpoint, bounceBtn);
                });
                parentMenu.appendChild(bounceBtn);
            }

            appendBounceButton(
                "Bounce (Relay)",
                "/issues/bounce-switch/",
                switchMenu,
                "This will bounce the relay/switch for " + entry.unit + ". Continue?"
            );

            const uptimeBtn = document.createElement("button");
            uptimeBtn.type = "button";
            uptimeBtn.className = "action-btn";
            uptimeBtn.textContent = "Switch Uptime";
            uptimeBtn.addEventListener("click", function () {
                uptimeBtn.disabled = true;
                uptimeBtn.textContent = "Checking...";
                statusEl.textContent = "Checking switch uptime for " + entry.unit + "...";
                fetch("/issues/robofiber-uptime/" + encodeURIComponent(entry.unit), {
                    method: "POST",
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        const header = "Switch uptime "
                            + (data.unit || entry.unit)
                            + (data.ip ? (" (" + data.ip + ")") : "");
                        consoleLines.push(header);
                        (data.lines || []).forEach(function (line) {
                            if (line) {
                                consoleLines.push(line);
                            }
                        });
                        if (!(data.lines || []).length && data.output) {
                            consoleLines.push(data.output);
                        }
                        renderConsole(true);
                        statusEl.textContent = data.uptime || data.output || header;
                        applyFreshSwitchUptime(entry.unit, data, commandItems.closest(".command-menu"));
                    })
                    .catch(function (error) {
                        const message = "Switch Uptime failed: " + (error.message || error);
                        consoleLines.push(message);
                        renderConsole(true);
                        statusEl.textContent = message;
                        notifyError(message);
                    })
                    .finally(function () {
                        uptimeBtn.disabled = false;
                        uptimeBtn.textContent = "Switch Uptime";
                    });
            });
            switchMenu.appendChild(uptimeBtn);

            function appendRobofiberLogButton(label, endpoint, statusPrefix) {
                const logBtn = document.createElement("button");
                logBtn.type = "button";
                logBtn.className = "action-btn";
                logBtn.textContent = label;
                logBtn.addEventListener("click", function () {
                    logBtn.disabled = true;
                    logBtn.textContent = "Loading...";
                    statusEl.textContent = statusPrefix + " for " + entry.unit + "...";
                    fetch(endpoint + encodeURIComponent(entry.unit), { method: "POST" })
                        .then(function (response) {
                            return response.json().then(function (data) {
                                if (!response.ok || !data.ok) {
                                    throw new Error(data.error || ("HTTP " + response.status));
                                }
                                return data;
                            });
                        })
                        .then(function (data) {
                            const header = label
                                + " — "
                                + (data.unit || entry.unit)
                                + (data.ip ? (" (" + data.ip + ")") : "")
                                + (data.count != null ? (" — " + data.count + " line(s)") : "");
                            consoleLines.push(header);
                            (data.lines || []).forEach(function (line) {
                                if (line) {
                                    consoleLines.push(line);
                                }
                            });
                            if (!(data.lines || []).length && data.output) {
                                consoleLines.push(data.output);
                            }
                            renderConsole(true);
                            statusEl.textContent = header;
                        })
                        .catch(function (error) {
                            const message = label + " failed: " + (error.message || error);
                            consoleLines.push(message);
                            renderConsole(true);
                            statusEl.textContent = message;
                            notifyError(message);
                        })
                        .finally(function () {
                            logBtn.disabled = false;
                            logBtn.textContent = label;
                        });
                });
                switchMenu.appendChild(logBtn);
            }

            appendRobofiberLogButton(
                "Link Up/Down Events",
                "/issues/robofiber-logs-link/",
                "Fetching switch link events"
            );
            appendRobofiberLogButton(
                "Syslog",
                "/issues/robofiber-logs-month/",
                "Fetching switch syslog"
            );
        }

        function populateUnitToolsCommandMenu(commandItems, entry) {
            appendValidateCommandMenu(commandItems, entry);
            appendWeatherCommandMenu(commandItems, entry);
            appendRouterCommandMenu(commandItems, entry);
            appendCamerasCommandMenu(commandItems, entry);
            appendDiagnosticsCommandMenu(commandItems, entry);

            appendOpenCommandMenu(commandItems, entry);
            appendArtMenu(commandItems, entry);
            appendSwitchCommandMenu(commandItems, entry);
            appendLinuxCommandMenus(commandItems, entry);
        }

        // Validate (Quick / Full) — its own builder so the Power vs Cell
        // Graphs modal's rail can show it too (renderGraphsDeviceMenu).
        function appendValidateCommandMenu(commandItems, entry) {
            const cliMenu = appendCommandSubmenu(commandItems, "Validate");

            function appendValidateButton(label, endpoint, isFull) {
                const validateBtn = document.createElement("button");
                validateBtn.type = "button";
                validateBtn.className = "action-btn";
                validateBtn.textContent = label;
                validateBtn.addEventListener("click", function () {
                    validateBtn.disabled = true;
                    validateBtn.textContent = "Validating...";
                    fetch(endpoint + encodeURIComponent(entry.unit), { method: "POST" })
                        .then(function (response) {
                            return response.json().then(function (data) {
                                if (!response.ok || !data.ok) {
                                    throw new Error(data.error || ("HTTP " + response.status));
                                }
                                return data;
                            });
                        })
                        .then(function (data) {
                            if (data.output) {
                                data.output.split(/\r?\n/).forEach(function (line) {
                                    if (line) {
                                        consoleLines.push(line);
                                    }
                                });
                            }
                            if (isFull) {
                                entry.ledStatus = data.led_status || entry.ledStatus;
                                entry.computeLabel = data.compute_label || entry.computeLabel;
                                if (data.speaker_up === true || data.speaker_up === false) {
                                    entry.speakerUp = data.speaker_up;
                                }
                                consoleLines.push(
                                    "Full validate "
                                        + entry.unit
                                        + " — "
                                        + (data.led_status || "unknown")
                                        + (data.multi_down ? " (multi-down)" : "")
                                );
                            } else {
                                const category = data.category === "stale_vpn"
                                    ? "truly_down"
                                    : (data.category || "");
                                const connectivityLed = {
                                    false_positives: "green",
                                    nuc_down: "yellow",
                                    scrypted_outage: "yellow",
                                    truly_down: "red",
                                };
                                if (connectivityLed[category]) {
                                    entry.ledStatus = connectivityLed[category];
                                }
                                consoleLines.push(
                                    "Revalidated "
                                        + entry.unit
                                        + " — "
                                        + (data.category || "unknown").replace(/_/g, " ")
                                );
                            }
                            renderConsole(true);
                            statusEl.textContent = label + " complete for " + entry.unit;
                            propagateLedFromEntry(entry);
                        })
                        .catch(function (error) {
                            notifyError(label + " failed: " + (error.message || error));
                        })
                        .finally(function () {
                            validateBtn.disabled = false;
                            validateBtn.textContent = label;
                        });
                });
                cliMenu.appendChild(validateBtn);
            }

            appendValidateButton("Validate (Quick)", "/issues/validate-unit/", false);
            appendValidateButton("Validate (Full)", "/issues/validate-unit-full/", true);
        }

        function renderUnitToolsRow(entry, openMenu) {
            const section = document.getElementById("unit_tools_section");
            const el = document.getElementById("unit_tools");
            const countEl = document.getElementById("unit_tools_count");
            if (!section || !el) {
                return;
            }
            unitToolsEntry = entry;
            el.innerHTML = "";
            const li = document.createElement("li");
            li.className = "ticket-row ticket-row-no-rws";
            li.dataset.searchText = (entry.unit || "").toLowerCase();

            const actions = document.createElement("div");
            actions.className = "ticket-row-actions";
            const menuParts = createCommandMenuElement(entry, li, { skipMultiUnitChooser: true });
            actions.appendChild(menuParts.commandMenu);
            li.appendChild(actions);

            const rowBody = document.createElement("div");
            rowBody.className = "ticket-row-body";
            const hint = document.createElement("span");
            hint.className = "unit-tools-hint";
            hint.textContent = "Ad-hoc unit commands";
            rowBody.appendChild(hint);
            li.appendChild(rowBody);
            populateUnitToolsCommandMenu(menuParts.commandItems, entry);
            el.appendChild(li);
            if (countEl) {
                countEl.textContent = "(1)";
            }
            section.hidden = false;
            applyListFilters();
            if (openMenu) {
                menuParts.commandMenu.open = true;
                placeCommandMenu(menuParts.commandMenu);
            }
        }

        function loadUnitTools(unit, openMenu) {
            const raw = String(unit || "").trim();
            if (!raw) {
                clearUnitToolsSection();
                return;
            }
            if (unitToolsInFlight) {
                return;
            }
            unitToolsInFlight = true;
            statusEl.textContent = "Loading unit tools for " + raw + "...";
            fetch("/issues/unit-context/" + encodeURIComponent(raw))
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const entry = makeListEntry(data);
                    try {
                        window.localStorage.setItem(unitToolsStorageKey, entry.unit || raw);
                    } catch (ignore) {
                        // localStorage may be unavailable.
                    }
                    lastLoadedUnitToolsQuery = raw.toLowerCase();
                    renderUnitToolsRow(entry, openMenu !== false);
                    statusEl.textContent = data.backfilled
                        ? ("Loaded " + entry.unit + " (netsheet backfilled from v19)")
                        : ("Unit tools for " + entry.unit + " — no matching tickets");
                })
                .catch(function (error) {
                    lastLoadedUnitToolsQuery = "";
                    clearUnitToolsSection();
                    const message = "Unit tools failed: " + (error.message || error);
                    statusEl.textContent = message;
                })
                .finally(function () {
                    unitToolsInFlight = false;
                });
        }

        // ---- Flap Report -------------------------------------------------
        // Fleet-wide "who keeps bouncing" — the API (/issues/flap-report,
        // /issues/history-stats) has existed since the validation-history
        // work, but nothing in the UI showed it. Opening a unit's row reuses
        // the exact ad-hoc "Unit tools" command menu (loadUnitTools) rather
        // than building a second copy of it.
        const flapReportSection = document.getElementById("flap_report_section");
        const flapReportListEl = document.getElementById("flap_report_list");
        const flapReportCountEl = document.getElementById("flap_report_count");
        const flapReportDaysEl = document.getElementById("flap_report_days");
        const flapReportMinEl = document.getElementById("flap_report_min");
        const flapReportRefreshBtn = document.getElementById("flap_report_refresh");
        const flapReportDbStatsEl = document.getElementById("flap_report_db_stats");
        let flapReportLoaded = false;

        // The Flap Report's per-unit history strip — every recorded check
        // in the window (unitStats.timeline, from flap_summary), placed by
        // WHEN it happened rather than evenly spaced by check count, so a
        // burst of flapping on one day reads as a visible cluster instead
        // of being smeared across the whole bar. Ticks can overlap when
        // checks land close together — that's fine, a solid red stretch is
        // exactly what "flapping hard right here" should look like.
        function renderFlapTimelineBar(timeline, days) {
            const bar = document.createElement("div");
            bar.className = "flap-timeline-bar";
            if (!timeline || !timeline.length) {
                bar.classList.add("is-empty");
                return bar;
            }
            const windowMs = Math.max(1, days) * 86400000;
            const startMs = Date.now() - windowMs;
            timeline.forEach(function (point) {
                const tick = document.createElement("span");
                tick.className = "flap-timeline-point is-" + (point.healthy ? "healthy" : "unhealthy");
                const tMs = point.ts * 1000;
                const pct = Math.max(0, Math.min(100, ((tMs - startMs) / windowMs) * 100));
                tick.style.left = pct + "%";
                tick.title = new Date(tMs).toLocaleString() + " — " + (point.healthy ? "healthy" : "unhealthy");
                bar.appendChild(tick);
            });
            return bar;
        }

        // Shared by Flap Report and Power & Infra Alerts: both fleet-wide
        // reports key rows by whatever raw unit code triggered them (mostly
        // MU for Power & Infra Alerts, mostly RD/FD for Flap Report), which
        // on its own leaves a tech guessing which unit that actually is.
        // Same RD####(MU####) shape every ticket subject and the fleet VRM
        // reports (renderFleetReportRow) already use: prefer the known RD/FD
        // head when this row's unit is an MU trailer, else pair the unit
        // with its own attached MU trailer when that's known instead.
        function pairedUnitDisplay(unit, headUnits, muTrailer) {
            const heads = headUnits || [];
            if (heads.length) {
                return { openTarget: heads[0], label: heads[0] + "(" + unit + ")" };
            }
            if (muTrailer) {
                return { openTarget: unit, label: unit + "(" + muTrailer + ")" };
            }
            return { openTarget: unit, label: unit };
        }

        function renderFlapReportRow(unitStats, days) {
            const li = document.createElement("li");
            li.className = "ticket-row ticket-row-no-rws";

            const actions = document.createElement("div");
            actions.className = "ticket-row-actions";
            const paired = pairedUnitDisplay(unitStats.unit, unitStats.head_units, unitStats.mu_trailer);
            const openBtn = document.createElement("button");
            openBtn.type = "button";
            openBtn.className = "action-btn";
            openBtn.textContent = paired.label;
            openBtn.title = "Open Commands for " + paired.openTarget + " in Unit tools";
            openBtn.addEventListener("click", function () {
                listSearchEl.value = paired.openTarget;
                applyListFilters();
                loadUnitTools(paired.openTarget, true);
                // Unit Tools lives on the Issues panel — reported live:
                // clicking this from a Reports-panel row (Flap Report,
                // Power & Infra Alerts, etc.) scrolled toward a [hidden]
                // section with no layout box to scroll to at all, which
                // read as "jumped to the bottom of the page" instead of
                // opening anything. Same "switch panel first" fix as the
                // alarm glyph's own Reports-panel jump above.
                if (panelModeEl && panelModeEl.value !== "issues") {
                    panelModeEl.value = "issues";
                    applyPanelMode();
                }
                const toolsSection = document.getElementById("unit_tools_section");
                if (toolsSection && toolsSection.scrollIntoView) {
                    toolsSection.scrollIntoView({ behavior: "smooth", block: "start" });
                }
            });
            actions.appendChild(openBtn);
            li.appendChild(actions);

            const body = document.createElement("div");
            body.className = "ticket-row-body";
            const stats = document.createElement("span");
            stats.className = "flap-row-stats";
            stats.textContent = unitStats.transitions + " transition(s), "
                + unitStats.down_checks + "/" + unitStats.checks + " checks down, last seen "
                + (unitStats.last_seen || "unknown") + " — currently "
                + (unitStats.currently_healthy ? "healthy" : "unhealthy");
            body.appendChild(stats);
            body.appendChild(renderFlapTimelineBar(unitStats.timeline, days));
            li.appendChild(body);
            return li;
        }

        function loadFlapReport() {
            const days = parseInt(flapReportDaysEl.value, 10) || 7;
            const minTransitions = parseInt(flapReportMinEl.value, 10) || 3;
            flapReportListEl.innerHTML = "";
            const loadingEl = document.createElement("li");
            loadingEl.className = "empty";
            loadingEl.textContent = "Loading...";
            flapReportListEl.appendChild(loadingEl);
            const reportLoad = fetch("/issues/flap-report?days=" + days + "&min_transitions=" + minTransitions)
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    flapReportListEl.innerHTML = "";
                    const units = data.units || [];
                    if (!units.length) {
                        const emptyEl = document.createElement("li");
                        emptyEl.className = "empty";
                        emptyEl.textContent = "No units at or above " + minTransitions
                            + " transitions in the last " + days + " day(s).";
                        flapReportListEl.appendChild(emptyEl);
                    } else {
                        units.forEach(function (unitStats) {
                            flapReportListEl.appendChild(renderFlapReportRow(unitStats, days));
                        });
                    }
                    flapReportCountEl.textContent = "(" + units.length + ")";
                    flapReportLoaded = true;
                })
                .catch(function (error) {
                    flapReportListEl.innerHTML = "";
                    const errEl = document.createElement("li");
                    errEl.className = "empty";
                    errEl.textContent = "Flap report failed: " + (error.message || error);
                    flapReportListEl.appendChild(errEl);
                });
            fetch("/issues/history-stats")
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    if (data && data.ok && flapReportDbStatsEl) {
                        flapReportDbStatsEl.textContent = "History: " + data.events + " events, "
                            + data.units + " units, " + data.size_mb + " MB on disk";
                    }
                })
                .catch(function () {});
            return reportLoad; // ensureReportsLoaded waits on this
        }

        // Zabbix Flap Report — same shape/UI as Flap Report above, but
        // read straight from Zabbix's own Router/Switch trigger history
        // (fleet_zabbix_flap_report) instead of this app's own
        // validation log, so it covers the whole fleet regardless of
        // whether a tech has happened to click Validate recently (see
        // that function's own docstring — caught live, 2026-09-17,
        // RD3336). Reuses renderFlapTimelineBar unchanged (same
        // {ts, healthy} timeline shape) — no unit already known here has
        // an RD/MU pairing to resolve the way Flap Report's does, since
        // the unit code comes straight off the Zabbix host name already.
        const zabbixFlapReportListEl = document.getElementById("zabbix_flap_report_list");
        const zabbixFlapReportCountEl = document.getElementById("zabbix_flap_report_count");
        const zabbixFlapReportDaysEl = document.getElementById("zabbix_flap_report_days");
        const zabbixFlapReportMinEl = document.getElementById("zabbix_flap_report_min");
        const zabbixFlapReportRefreshBtn = document.getElementById("zabbix_flap_report_refresh");
        let zabbixFlapReportLoaded = false;

        function renderZabbixFlapReportRow(unitStats, days) {
            const li = document.createElement("li");
            li.className = "ticket-row ticket-row-no-rws";

            const actions = document.createElement("div");
            actions.className = "ticket-row-actions";
            const openBtn = document.createElement("button");
            openBtn.type = "button";
            openBtn.className = "action-btn";
            openBtn.textContent = unitStats.unit;
            openBtn.title = "Open Commands for " + unitStats.unit + " in Unit tools";
            openBtn.addEventListener("click", function () {
                listSearchEl.value = unitStats.unit;
                applyListFilters();
                loadUnitTools(unitStats.unit, true);
                // Same "switch panel first" fix as Flap Report's own
                // row opener — see its own comment for why.
                if (panelModeEl && panelModeEl.value !== "issues") {
                    panelModeEl.value = "issues";
                    applyPanelMode();
                }
                const toolsSection = document.getElementById("unit_tools_section");
                if (toolsSection && toolsSection.scrollIntoView) {
                    toolsSection.scrollIntoView({ behavior: "smooth", block: "start" });
                }
            });
            actions.appendChild(openBtn);
            li.appendChild(actions);

            const body = document.createElement("div");
            body.className = "ticket-row-body";
            const stats = document.createElement("span");
            stats.className = "flap-row-stats";
            stats.textContent = unitStats.transitions + " transition(s) on " + unitStats.device + ", "
                + formatUptimeDuration(unitStats.down_seconds) + " down total, last seen "
                + (unitStats.last_seen || "unknown") + " — currently "
                + (unitStats.currently_healthy ? "healthy" : "unhealthy");
            body.appendChild(stats);
            body.appendChild(renderFlapTimelineBar(unitStats.timeline, days));
            li.appendChild(body);
            return li;
        }

        function loadZabbixFlapReport() {
            const days = parseInt(zabbixFlapReportDaysEl.value, 10) || 7;
            const minTransitions = parseInt(zabbixFlapReportMinEl.value, 10) || 3;
            zabbixFlapReportListEl.innerHTML = "";
            const loadingEl = document.createElement("li");
            loadingEl.className = "empty";
            loadingEl.textContent = "Loading...";
            zabbixFlapReportListEl.appendChild(loadingEl);
            return fetch("/issues/zabbix-flap-report?days=" + days + "&min_transitions=" + minTransitions)
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    zabbixFlapReportListEl.innerHTML = "";
                    const units = data.units || [];
                    if (!units.length) {
                        const emptyEl = document.createElement("li");
                        emptyEl.className = "empty";
                        emptyEl.textContent = "No units at or above " + minTransitions
                            + " transitions in the last " + days + " day(s).";
                        zabbixFlapReportListEl.appendChild(emptyEl);
                    } else {
                        units.forEach(function (unitStats) {
                            zabbixFlapReportListEl.appendChild(renderZabbixFlapReportRow(unitStats, days));
                        });
                    }
                    zabbixFlapReportCountEl.textContent = "(" + units.length + ")";
                    zabbixFlapReportLoaded = true;
                })
                .catch(function (error) {
                    zabbixFlapReportListEl.innerHTML = "";
                    const errEl = document.createElement("li");
                    errEl.className = "empty";
                    errEl.textContent = "Zabbix flap report failed: " + (error.message || error);
                    zabbixFlapReportListEl.appendChild(errEl);
                });
        }

        if (zabbixFlapReportRefreshBtn) {
            zabbixFlapReportRefreshBtn.addEventListener("click", loadZabbixFlapReport);
        }

        // Camera Outage Report — fleet-wide list of units with the same
        // SNUC-Watch "camera image buffer" alert the camera-outage glyph
        // watches for per unit (see CAMERA_OUTAGE_ALERT_PATTERN). Each row
        // gets its own on-demand "Find Camera" check rather than running
        // one eagerly for every row on load — same restraint as the glyph
        // itself, since it's a real SSH/ping cost per unit.
        const cameraOutageReportListEl = document.getElementById("camera_outage_report_list");
        const cameraOutageReportCountEl = document.getElementById("camera_outage_report_count");
        const cameraOutageReportRefreshBtn = document.getElementById("camera_outage_report_refresh");
        const cameraOutageReportFindAllBtn = document.getElementById("camera_outage_report_find_all");
        const cameraOutageReportStatusEl = document.getElementById("camera_outage_report_status");
        let cameraOutageReportLoaded = false;
        // Reset on every load; "Find All Cameras" runs whatever's in here,
        // one row at a time, rather than firing every unit's SSH/ping check
        // at once (see cameraOutageReportFindAllBtn's own handler below).
        let cameraOutageReportFindFns = [];

        function renderCameraOutageReportRow(row) {
            const li = document.createElement("li");
            li.className = "ticket-row ticket-row-no-rws";

            const actions = document.createElement("div");
            actions.className = "ticket-row-actions";
            const openBtn = document.createElement("button");
            openBtn.type = "button";
            openBtn.className = "action-btn";
            openBtn.textContent = row.unit;
            openBtn.title = "Open Commands for " + row.unit + " in Unit tools";
            openBtn.addEventListener("click", function () {
                listSearchEl.value = row.unit;
                applyListFilters();
                loadUnitTools(row.unit, true);
                if (panelModeEl && panelModeEl.value !== "issues") {
                    panelModeEl.value = "issues";
                    applyPanelMode();
                }
                const toolsSection = document.getElementById("unit_tools_section");
                if (toolsSection && toolsSection.scrollIntoView) {
                    toolsSection.scrollIntoView({ behavior: "smooth", block: "start" });
                }
            });
            actions.appendChild(openBtn);

            const findBtn = document.createElement("button");
            findBtn.type = "button";
            findBtn.className = "action-btn";
            findBtn.textContent = "Find Camera";
            actions.appendChild(findBtn);
            li.appendChild(actions);

            const body = document.createElement("div");
            body.className = "ticket-row-body";
            const stats = document.createElement("span");
            stats.className = "flap-row-stats";
            const duration = formatDurationSince(row.clock);
            stats.textContent = (row.name || "Camera image buffer alert")
                + (duration ? " — open " + duration : "")
                + (row.has_scrypted ? " (Scrypted)" : " (NUC)");
            body.appendChild(stats);
            const resultLine = document.createElement("div");
            resultLine.className = "flap-report-note";
            body.appendChild(resultLine);
            li.appendChild(body);

            // cachedResult (optional) is this unit's entry from the server's
            // scheduled sweep (/issues/camera-outage-report/cached): shown
            // the same way as a live find, without running the check again
            // or logging it to Stdout a second time.
            function runFind(cachedResult) {
                const fromCache = !!(cachedResult && typeof cachedResult === "object" && "ok" in cachedResult);
                findBtn.disabled = true;
                findBtn.textContent = "Checking...";
                resultLine.textContent = "";
                const endpoint = row.has_scrypted
                    ? "/issues/scrypted-ram-folder/"
                    : "/issues/camera-outage-ping/";
                const request = fromCache
                    ? Promise.resolve(cachedResult).then(function (data) {
                        if (!data.ok) {
                            throw new Error(data.error || "check failed");
                        }
                        return data;
                    })
                    : fetch(endpoint + encodeURIComponent(row.unit), { method: "POST" })
                        .then(function (response) {
                            return response.json().then(function (data) {
                                if (!response.ok || !data.ok) {
                                    throw new Error(data.error || ("HTTP " + response.status));
                                }
                                return data;
                            });
                        });
                return request
                    .then(function (data) {
                        // Feeds the SAME cache the glyph tooltip reads
                        // (cameraOutageRamFolderChecker/cameraOutagePingChecker)
                        // so a check run from this report also warms the
                        // tooltip for whenever that unit's own command menu
                        // is next opened, instead of the two staying two
                        // separate, disconnected checks against the unit.
                        let determined = true;
                        if (row.has_scrypted) {
                            const cameras = data.cameras || [];
                            const failing = cameras.filter(function (c) { return !c.ok; });
                            cameraOutageRamFolderChecker.cache[row.unit] = {
                                failingCameras: failing, fetchedAt: Date.now(),
                            };
                            resultLine.textContent = "";
                            if (cameras.length) {
                                // Same per-camera image count "Get Ram
                                // Folder" already streams to the console —
                                // this report's own "Find Camera" used to
                                // only name which camera looked down, not
                                // how many images its folder actually had
                                // (0 vs 3 reads very differently) or, for a
                                // not-populating one, whether the camera
                                // ITSELF still answers a ping — a dead
                                // camera and a live camera whose Scrypted
                                // capture stopped need different fixes, and
                                // "not populating" alone doesn't tell them
                                // apart (see _add_camera_reachability).
                                resultLine.appendChild(document.createTextNode(
                                    (failing.length
                                        ? failing.length + " of " + cameras.length + " camera RAM folder(s) not populating — "
                                        : "All " + cameras.length + " camera RAM folder(s) populating — ")
                                ));
                                cameras.forEach(function (c, i) {
                                    if (i > 0) {
                                        resultLine.appendChild(document.createTextNode(", "));
                                    }
                                    // no_folder (work_tool._add_missing_camera_rows) means
                                    // Scrypted knows about this camera but it has no RAM
                                    // folder on disk at all yet — worth distinguishing from
                                    // a folder that exists but is simply empty.
                                    const label = c.name + (c.no_folder ? " (no folder)" : (c.room ? " (" + c.room + ")" : ""));
                                    const count = c.file_count + " image" + (c.file_count === 1 ? "" : "s");
                                    resultLine.appendChild(document.createTextNode(label + ": " + count));
                                    if (c.ok) {
                                        return;
                                    }
                                    const glyph = document.createElement("span");
                                    glyph.className = "ram-folder-reachability-glyph";
                                    if (c.camera_reachable === true) {
                                        glyph.textContent = " 📷✅ folder issue only";
                                        glyph.title = c.name + " answered a ping — the RAM folder just isn't "
                                            + "populating (likely a Scrypted-side capture issue), not a dead camera.";
                                    } else if (c.camera_reachable === false) {
                                        glyph.textContent = " 📷❌ camera unreachable too";
                                        glyph.title = c.name + " did not answer a ping either — likely "
                                            + "dead/offline, not just a folder/software issue.";
                                    } else {
                                        glyph.textContent = " 📷❓ camera reachability unknown";
                                        glyph.title = "Could not determine whether " + c.name + " itself is "
                                            + "reachable (not mapped to a netsheet target, or the ping itself failed).";
                                    }
                                    resultLine.appendChild(glyph);
                                });
                            } else {
                                resultLine.textContent = "Could not confirm which camera from this check.";
                                determined = false;
                            }
                        } else {
                            const down = data.down_cameras || [];
                            cameraOutagePingChecker.cache[row.unit] = {
                                downCameras: down, fetchedAt: Date.now(),
                            };
                            if (down.length) {
                                resultLine.textContent = "Ping sweep found down: " + down.map(function (c) { return c.label; }).join(", ");
                            } else {
                                resultLine.textContent = "Ping sweep found nothing down — could not confirm which camera from this check.";
                                determined = false;
                            }
                        }
                        // Same "everything lands in the shared console" rule
                        // every other action in this app follows — this one
                        // was only ever shown inline in the report row.
                        if (!fromCache) {
                            consoleLines.push("Find Camera " + row.unit + " — " + resultLine.textContent);
                            renderConsole(true);
                        }
                        document.querySelectorAll('details.command-menu').forEach(function (commandMenu) {
                            if (String(commandMenu.dataset.unit || "").toUpperCase() === row.unit) {
                                applyCameraOutageGlyph(commandMenu);
                            }
                        });
                        // Couldn't pin down which camera (or whether the
                        // unit's even reachable at all) — Andrew's own
                        // request, 2026-09-28: these belong at the bottom,
                        // not mixed in among rows with an actual finding.
                        // appendChild on an element already in the list
                        // moves it rather than duplicating it.
                        if (!determined) {
                            cameraOutageReportListEl.appendChild(li);
                        }
                    })
                    .catch(function (error) {
                        const message = "Find Camera failed for " + row.unit + ": " + (error.message || error);
                        resultLine.textContent = message;
                        if (!fromCache) {
                            consoleLines.push(message);
                            renderConsole(true);
                            notifyError(message);
                        }
                        cameraOutageReportListEl.appendChild(li);
                    })
                    .finally(function () {
                        findBtn.disabled = false;
                        findBtn.textContent = "Find Camera";
                    });
            }
            findBtn.addEventListener("click", function () { runFind(); });
            cameraOutageReportFindFns.push(function () { return runFind(); });
            li._showCachedFind = runFind;

            return li;
        }

        // Opening Reports reads the server's scheduled sweep
        // (/issues/camera-outage-report/cached — the alert list plus every
        // unit's camera find, run last at startup and hourly after), so the
        // findings are already there and nothing runs from the browser.
        // With no cached run yet (sandbox, or just after a restart) it falls
        // back to the live list plus an automatic Find All, as before.
        // Refresh always does the live version (live = true).
        function renderCameraOutageReportUnits(units) {
            cameraOutageReportListEl.innerHTML = "";
            if (!units.length) {
                const emptyEl = document.createElement("li");
                emptyEl.className = "empty";
                emptyEl.textContent = "No units with the camera image buffer alert open right now.";
                cameraOutageReportListEl.appendChild(emptyEl);
            }
            const rowEls = {};
            units.forEach(function (row) {
                const li = renderCameraOutageReportRow(row);
                rowEls[row.unit] = li;
                cameraOutageReportListEl.appendChild(li);
            });
            cameraOutageReportCountEl.textContent = "(" + units.length + ")";
            cameraOutageReportLoaded = true;
            return rowEls;
        }

        function loadCameraOutageReportLive() {
            return fetch("/issues/camera-outage-report")
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    renderCameraOutageReportUnits(data.units || []);
                    if (cameraOutageReportStatusEl) {
                        cameraOutageReportStatusEl.textContent = "Live check just now";
                    }
                    // Auto-run rather than waiting for a manual "Find All
                    // Cameras" click — Andrew's own request, 2026-09-18: a
                    // unit showing up here should already have its
                    // camera/room known by the time anyone looks. One at a
                    // time (see runCameraOutageFindAll).
                    runCameraOutageFindAll();
                });
        }

        function loadCameraOutageReport(live) {
            cameraOutageReportFindFns = [];
            cameraOutageReportListEl.innerHTML = "";
            const loadingEl = document.createElement("li");
            loadingEl.className = "empty";
            loadingEl.textContent = "Loading...";
            cameraOutageReportListEl.appendChild(loadingEl);
            const load = live === true
                ? loadCameraOutageReportLive()
                : fetch("/issues/camera-outage-report/cached")
                    .then(function (response) { return response.json(); })
                    .then(function (data) {
                        if (!data || !data.ok || !data.fetched_at) {
                            return loadCameraOutageReportLive(); // no scheduled run yet
                        }
                        const rowEls = renderCameraOutageReportUnits(data.units || []);
                        const finds = data.finds || {};
                        Object.keys(rowEls).forEach(function (unit) {
                            if (finds[unit] && rowEls[unit]._showCachedFind) {
                                rowEls[unit]._showCachedFind(finds[unit]);
                            }
                        });
                        if (cameraOutageReportStatusEl) {
                            cameraOutageReportStatusEl.textContent = "Checked "
                                + new Date(data.fetched_at * 1000).toLocaleString()
                                + " · runs hourly" + (data.running ? " · re-running now" : "")
                                + (data.error ? " · last run failed: " + data.error : "");
                        }
                    });
            return load.catch(function (error) {
                cameraOutageReportListEl.innerHTML = "";
                const errEl = document.createElement("li");
                errEl.className = "empty";
                errEl.textContent = "Camera outage report failed: " + (error.message || error);
                cameraOutageReportListEl.appendChild(errEl);
            });
        }

        function runCameraOutageFindAll() {
            if (!cameraOutageReportFindFns.length) {
                return;
            }
            if (cameraOutageReportFindAllBtn) {
                cameraOutageReportFindAllBtn.disabled = true;
                cameraOutageReportFindAllBtn.textContent = "Finding...";
            }
            // One at a time, not all at once — this can be a dozen
            // separate units, each opening its own SSH/ping check.
            const fns = cameraOutageReportFindFns.slice();
            function runNext() {
                const fn = fns.shift();
                if (!fn) {
                    if (cameraOutageReportFindAllBtn) {
                        cameraOutageReportFindAllBtn.disabled = false;
                        cameraOutageReportFindAllBtn.textContent = "Find All Cameras";
                    }
                    return;
                }
                return Promise.resolve(fn()).then(runNext);
            }
            runNext();
        }

        if (cameraOutageReportRefreshBtn) {
            cameraOutageReportRefreshBtn.addEventListener("click", function () {
                loadCameraOutageReport(true); // live list + Find All, not the hourly cache
            });
        }

        if (cameraOutageReportFindAllBtn) {
            cameraOutageReportFindAllBtn.addEventListener("click", runCameraOutageFindAll);
        }

        if (flapReportRefreshBtn) {
            flapReportRefreshBtn.addEventListener("click", loadFlapReport);
        }

        // ---- Fleet-wide VRM reports (Units Unplugged / Shaded Units / Dead
        // Panels / VRM Disconnected) — all experimental ------------------------
        // Every VRM installation the fleet has, not just units with a
        // matching open ticket — the earlier ticket-scoped version of the
        // first two reports missed anything without a currently-open
        // ticket of that exact subtype. A live full-fleet check is
        // genuinely expensive (a real VRM call per site, run concurrently,
        // takes on the order of a minute) — see fleet_power_status /
        // fleet_shading_status / fleet_dead_panel_status /
        // fleet_vrm_freshness_status in weather.py — so these poll on a
        // schedule server-side (flask_endpoints.py) into a plain in-memory
        // cache, not a growing database: "keep it up to date without
        // refreshing too often, without taking up space" was the ask, and
        // a dict refreshed on a timer costs zero disk. Opening a report
        // reads that cache instantly; "Check whole fleet now" forces a
        // fresh live pass when you want one, same live/cached split
        // Power & Infra Alerts already uses for the same reason.

        // Expands the SAME inline command menu a ticket row's Commands
        // button does (createCommandMenuElement + populateUnitToolsCommandMenu
        // — the exact pair Unit Tools already uses for an ad-hoc unit
        // search), right where it's clicked. Deliberately NOT the old
        // behavior of jumping to the Unit Tools section at the bottom of
        // the page and opening the menu there — a report can list
        // hundreds of rows, and losing your place in that list to look at
        // one unit's commands was the actual complaint this replaced.
        //
        // A fleet-check row only ever carries VRM/ERP shading/power
        // fields, not the fuller unit context (hasPve, ticket subject,
        // etc.) the shared command menu builders read — so this fetches
        // /issues/unit-context/<unit> (the same call loadUnitTools already
        // makes) lazily, on first click, rather than for every row a
        // report might show.
        // ticketSubject (optional) is layered onto the fetched entry, same as
        // loadGraphsDeviceMenu does, so VRM/ERP resolution gets the ticket's
        // "RD####(MU####)" context instead of the bare unit lookup.
        function attachFleetRowCommandMenu(actions, li, unit, label, trailerUnit, ticketSubject) {
            const openBtn = document.createElement("button");
            openBtn.type = "button";
            openBtn.className = "action-btn";
            openBtn.textContent = label;
            openBtn.title = unit === trailerUnit
                ? "Open Commands for " + unit
                : "Open Commands for " + unit + " (" + trailerUnit + "'s head unit, via ERP)";
            openBtn.addEventListener("click", function () {
                openBtn.disabled = true;
                openBtn.textContent = "Loading...";
                fetch("/issues/unit-context/" + encodeURIComponent(unit))
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        const entry = makeListEntry(data);
                        if (ticketSubject) {
                            entry.ticketSubject = ticketSubject;
                        }
                        const menuParts = createCommandMenuElement(entry, li, { skipMultiUnitChooser: true });
                        // Keep the RD####(MU####) label the report itself
                        // already resolved — commandMenuButtonLabel would
                        // otherwise just show entry.unit (the head alone).
                        menuParts.commandMenu.querySelector("summary").textContent = label;
                        menuParts.commandMenu.setAttribute("aria-label", "Commands for " + label);
                        populateUnitToolsCommandMenu(menuParts.commandItems, entry);
                        openBtn.replaceWith(menuParts.commandMenu);
                        // Same "open immediately" pattern renderUnitToolsRow
                        // uses — placeCommandMenu positions the popover AND
                        // calls updateCommandMenuContext; the native toggle
                        // event (fired by this same assignment in every
                        // browser this app targets) covers the rest
                        // (glyph checks, recent-commands strip).
                        menuParts.commandMenu.open = true;
                        placeCommandMenu(menuParts.commandMenu);
                    })
                    .catch(function (error) {
                        openBtn.disabled = false;
                        openBtn.textContent = label;
                        notifyError("Could not load commands for " + unit + ": " + (error.message || error));
                    });
            });
            actions.appendChild(openBtn);
        }

        function renderFleetReportRow(row) {
            const li = document.createElement("li");
            li.className = "ticket-row ticket-row-no-rws";

            const actions = document.createElement("div");
            actions.className = "ticket-row-actions";
            // A bare MU row is a trailer, not a full unit — show and open
            // its ERP-linked RD/FD head instead when known, the same
            // RD####(MU####) shape every ticket subject already uses
            // (not "MU8083", which is what a trailer with no head context
            // looks like, and reads as if the trailer WERE the unit).
            const headUnits = row.head_units || [];
            const openTarget = headUnits.length ? headUnits[0] : row.unit;
            const openLabel = headUnits.length ? (headUnits[0] + "(" + row.unit + ")") : row.unit;
            attachFleetRowCommandMenu(actions, li, openTarget, openLabel, row.unit);
            li.appendChild(actions);

            // Searchable by unit (either side of an MU/RD pair) and by
            // whatever related ticket got matched in — the list_search box
            // now covers Reports the same way it already covers Issues/
            // Projects (see applyListFilters).
            li.dataset.searchText = [row.unit, openLabel]
                .concat(headUnits)
                .filter(Boolean)
                .join(" ")
                .toLowerCase();

            const body = document.createElement("div");
            body.className = "ticket-row-body fleet-report-body";
            const line = document.createElement("span");
            line.className = "flap-row-stats report-status-" + (row.error ? "fail" : (row.status || "warn"));
            // row.summary already leads with RD####(MU####) when a head is
            // known (see fleet_power_status et al.) — no separate "Head
            // unit" line needed, that would just repeat it.
            line.textContent = row.error ? ("Check failed: " + row.error) : (row.summary || row.unit);
            body.appendChild(line);

            // Every fleet report — flags a maybe-related open ticket found
            // by findOpenTicketForUnits (see relatedTicketEnrichFn, which
            // every FLEET_REPORT_CONFIGS entry uses), which is also what
            // pushed this row to the top of its report.
            if (row.related_ticket) {
                const ticket = row.related_ticket;
                const relatedLine = document.createElement("div");
                relatedLine.className = "snapshot-task-line";
                const badge = document.createElement("span");
                badge.className = "related-ticket-badge";
                badge.textContent = "⚠ possibly related ticket";
                relatedLine.appendChild(badge);
                const ticketLabel = document.createElement("span");
                ticketLabel.textContent = ticket.ticketSubject || ticket.issueId || ticket.unit;
                if (ticket.url) {
                    const ticketLink = document.createElement("a");
                    ticketLink.href = ticket.url;
                    ticketLink.target = "_blank";
                    ticketLink.rel = "noopener noreferrer";
                    ticketLink.textContent = ticketLabel.textContent;
                    relatedLine.appendChild(ticketLink);
                } else {
                    relatedLine.appendChild(ticketLabel);
                }
                body.appendChild(relatedLine);
            }

            // Shaded Units, Dead Panels, AND Battery Outlook rows — all
            // three are read off the same underlying solar-power/battery
            // history (row.shading_status only from _shading_status_for_site,
            // row.dead_panel_status only from _dead_panel_status_for_site,
            // row.risk only from fleet_battery_outlook_status's check_one),
            // so all three get a direct link to the graph the verdict was
            // actually based on rather than requiring the command menu or
            // the per-unit check's own toast first.
            if (row.shading_status !== undefined || row.dead_panel_status !== undefined || row.risk !== undefined) {
                const snapshotLine = document.createElement("div");
                snapshotLine.className = "snapshot-task-line";

                // Same "Battery Graphs" chart (pv_power/yield_today) both
                // detect_solar_shading and detect_dead_panel read.
                // Deliberately row.unit (the MU trailer with the actual
                // VRM installation), not openTarget (its RD/FD head,
                // which has no solar data of its own) — VRM resolution
                // can go head-to-trailer via ERP, but the trailer code
                // itself needs no such indirection. openGraphsModal only
                // needs the unit (+ optional subject, which this report
                // doesn't carry) — no unit-context fetch required first.
                const graphBtn = document.createElement("button");
                graphBtn.type = "button";
                graphBtn.className = "action-btn";
                graphBtn.textContent = "View Solar Graph";
                graphBtn.title = "Opens the Battery Graphs modal (voltage/SOC/current/solar power) used to check this unit";
                graphBtn.addEventListener("click", function () {
                    openGraphsModal(row.unit, "battery", "", null, openLabel);
                });
                snapshotLine.appendChild(graphBtn);
                if (row.forecast && row.forecast.length) {
                    snapshotLine.appendChild(
                        forecastGlyphElement(row.forecast, row.cloudy_days, row.forecast_days, openLabel, forecastLocationFromData(row))
                    );
                }
                body.appendChild(snapshotLine);
            }

            // Shaded Units rows only — the snapshot task for this unit, if
            // one exists, or a one-off Schedule button if the unit is
            // currently flagged shaded and doesn't have one yet.
            if (row.shading_status !== undefined) {
                const snapshotLine = document.createElement("div");
                snapshotLine.className = "snapshot-task-line";

                const task = row.snapshot_task;
                if (task) {
                    const statusText = document.createElement("span");
                    statusText.textContent = snapshotTaskStatusText(task);
                    snapshotLine.appendChild(statusText);
                    if (task.has_image) {
                        const thumb = document.createElement("img");
                        thumb.className = "snapshot-thumb";
                        thumb.src = "/issues/shading-snapshot-image/" + task.id;
                        thumb.title = "Click to view full size";
                        thumb.addEventListener("click", function () {
                            window.open("/issues/shading-snapshot-image/" + task.id, "_blank");
                        });
                        snapshotLine.appendChild(thumb);
                    }
                } else if (row.shading_status === "shaded") {
                    const scheduleBtn = document.createElement("button");
                    scheduleBtn.type = "button";
                    scheduleBtn.className = "action-btn";
                    scheduleBtn.textContent = "Schedule Snapshot";
                    scheduleBtn.title = "Schedule a fisheye-camera photo for the following day's peak-shading hour";
                    scheduleBtn.addEventListener("click", function () {
                        scheduleBtn.disabled = true;
                        scheduleBtn.textContent = "Scheduling...";
                        scheduleShadingSnapshot(row.unit, "")
                            .then(function (data) {
                                notify(
                                    "Snapshot scheduled for " + row.unit + " — next attempt "
                                    + (data.next_attempt_at ? new Date(data.next_attempt_at * 1000).toLocaleString() : "soon"),
                                    "success"
                                );
                                loadFleetReportCached(FLEET_REPORT_CONFIGS.shadedUnits);
                            })
                            .catch(function (error) {
                                notifyError("Schedule Snapshot failed: " + (error.message || error));
                                scheduleBtn.disabled = false;
                                scheduleBtn.textContent = "Schedule Snapshot";
                            });
                    });
                    snapshotLine.appendChild(scheduleBtn);
                }
                body.appendChild(snapshotLine);
            }

            li.appendChild(body);
            return li;
        }

        function snapshotTaskStatusText(task) {
            const nextWhen = task.next_attempt_at ? new Date(task.next_attempt_at * 1000).toLocaleString() : "soon";
            const capturedWhen = task.captured_at ? new Date(task.captured_at * 1000).toLocaleString() : "";
            if (task.status === "pending") {
                let text = "Snapshot scheduled — attempt " + (task.attempts_used + 1) + "/" + task.attempts_total
                    + " on " + nextWhen;
                // attempts_used > 0 means an earlier attempt already ran
                // and didn't produce a photo (dip not reconfirmed, camera
                // fetch failed, etc. — see _run_due_shading_snapshot_tasks)
                // before this one got scheduled. Show why, the same way
                // "exhausted" already does below, instead of silently
                // jumping straight to "attempt 2/3" with no explanation
                // for where attempt 1 went.
                if (task.attempts_used > 0 && task.last_note) {
                    text += " (attempt " + task.attempts_used + " failed: " + task.last_note + ")";
                }
                return text;
            }
            if (task.status === "captured") {
                return "Snapshot captured " + capturedWhen;
            }
            if (task.status === "exhausted") {
                return "Snapshot not captured after " + task.attempts_total + " attempt(s) — "
                    + (task.last_note || "dip never reconfirmed");
            }
            if (task.status === "cancelled") {
                return "Snapshot task cancelled";
            }
            return "Snapshot task: " + task.status;
        }

        function scheduleShadingSnapshot(unit, subject, cameraTarget) {
            return fetch("/issues/schedule-shading-snapshot/" + encodeURIComponent(unit), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ subject: subject || "", camera_target: cameraTarget || "fisheye" }),
            }).then(function (response) {
                return response.json().then(function (data) {
                    if (!response.ok || !data.ok) {
                        throw new Error(data.error || ("HTTP " + response.status));
                    }
                    return data;
                });
            });
        }

        const scheduleSnapshotsBulkBtn = document.getElementById("shaded_units_schedule_snapshots");
        if (scheduleSnapshotsBulkBtn) {
            scheduleSnapshotsBulkBtn.addEventListener("click", function () {
                scheduleSnapshotsBulkBtn.disabled = true;
                scheduleSnapshotsBulkBtn.textContent = "Scheduling...";
                fetch("/issues/schedule-shading-snapshot-bulk", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({}),
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        const message = "Scheduled " + data.scheduled.length + " new snapshot task(s)"
                            + (data.already_pending.length ? ", " + data.already_pending.length + " already pending" : "")
                            + (data.skipped.length ? ", " + data.skipped.length + " skipped (no current shading data)" : "")
                            + ".";
                        consoleLines.push(message);
                        data.scheduled.forEach(function (item) {
                            consoleLines.push(
                                "  " + item.unit + " — next attempt "
                                + new Date(item.next_attempt_at * 1000).toLocaleString()
                            );
                        });
                        renderConsole(true);
                        notify(message, "success");
                        loadFleetReportCached(FLEET_REPORT_CONFIGS.shadedUnits);
                    })
                    .catch(function (error) {
                        notifyError("Schedule Snapshots for Shaded Units failed: " + (error.message || error));
                    })
                    .finally(function () {
                        scheduleSnapshotsBulkBtn.disabled = false;
                        scheduleSnapshotsBulkBtn.textContent = "Schedule Snapshots for Shaded Units";
                    });
            });
        }

        // A VRM-disconnected site with an ALREADY-open issue ticket against
        // it (or its ERP-linked RD/FD head) is worth flagging distinctly —
        // someone's likely already on it, or it explains the silence (unit
        // pulled, relocation, etc.) rather than being a fresh, unseen
        // problem. Checks every currently-loaded issue list (not projects,
        // not discarded), matching either the trailer's own code or any of
        // its resolved head units. Returns the matching ticket entry, or
        // null.
        function findOpenTicketForUnits(units) {
            const wanted = new Set(
                (units || []).filter(Boolean).map(function (u) { return String(u).toUpperCase(); })
            );
            if (!wanted.size) {
                return null;
            }
            for (const id of issueListIds) {
                const entries = listState[id] || [];
                for (const entry of entries) {
                    if (entry.unit && wanted.has(String(entry.unit).toUpperCase())) {
                        return entry;
                    }
                }
            }
            return null;
        }

        // Shared enrichFn/priorityFn pair — every fleet report uses the
        // same "does this unit (or its ERP-linked head) already have an
        // open ticket" check and the same "push it to the very top"
        // priority, so every FLEET_REPORT_CONFIGS entry points at these
        // instead of each re-implementing it.
        function relatedTicketEnrichFn(row) {
            row.related_ticket = findOpenTicketForUnits([row.unit].concat(row.head_units || []));
        }
        function relatedTicketPriorityFn(row) {
            return row.related_ticket ? 0 : 1;
        }

        // sortRank: lower sorts first — puts the actionable finding
        // (unplugged / shaded / dead panel / disconnected) at the top of
        // a list that can run into the hundreds, rather than alphabetical.
        // certainty: within the same finding, highest-confidence rows
        // sort first — the ones most worth a tech's time before the ones
        // that are more of a "worth a look."
        const FLEET_REPORT_CONFIGS = {
            unitsUnplugged: {
                listEl: document.getElementById("units_unplugged_list"),
                countEl: document.getElementById("units_unplugged_count"),
                statusEl: document.getElementById("units_unplugged_status"),
                sectionEl: document.getElementById("units_unplugged_section"),
                refreshBtn: document.getElementById("units_unplugged_refresh"),
                liveEndpoint: "/issues/fleet-power-status",
                cachedEndpoint: "/issues/fleet-power-status/cached",
                emptyText: "No cached results yet — click \"Check whole fleet now.\"",
                sortRank: function (row) {
                    return { not_detected: 0, uncertain: 1, unknown: 2 }[row.ac_power_status];
                },
                certainty: function (row) { return row.ac_power_confidence; },
                // Same "a clean unit is not a finding" fix as
                // vrmFreshness/shadedUnits/deadPanel/batteryOutlook below —
                // this report had no filterFn at all, so "present" (plugged
                // in, all normal) and "no_charger_hardware" (solar+battery
                // trailer with no AC charger to read) rows padded out a
                // report titled Units Unplugged. Kept to the same three
                // tiers sortRank above already treats as the only ranked
                // ones.
                filterFn: function (row) {
                    return row.ac_power_status === "not_detected"
                        || row.ac_power_status === "uncertain"
                        || row.ac_power_status === "unknown";
                },
                enrichFn: relatedTicketEnrichFn,
                priorityFn: relatedTicketPriorityFn,
            },
            shadedUnits: {
                listEl: document.getElementById("shaded_units_list"),
                countEl: document.getElementById("shaded_units_count"),
                statusEl: document.getElementById("shaded_units_status"),
                sectionEl: document.getElementById("shaded_units_section"),
                refreshBtn: document.getElementById("shaded_units_refresh"),
                liveEndpoint: "/issues/fleet-shading-status",
                cachedEndpoint: "/issues/fleet-shading-status/cached",
                emptyText: "No cached results yet — click \"Check whole fleet now.\"",
                sortRank: function (row) {
                    return { shaded: 0 }[row.shading_status];
                },
                certainty: function (row) { return row.shading_confidence; },
                // Only the actual finding — a report titled "Shaded
                // Units" listing every healthy unit too (or ones the
                // check couldn't even reach a verdict on) just buries the
                // ones worth a look.
                filterFn: function (row) { return row.shading_status === "shaded"; },
                enrichFn: relatedTicketEnrichFn,
                priorityFn: relatedTicketPriorityFn,
            },
            deadPanel: {
                listEl: document.getElementById("dead_panel_list"),
                countEl: document.getElementById("dead_panel_count"),
                statusEl: document.getElementById("dead_panel_status"),
                sectionEl: document.getElementById("dead_panel_section"),
                refreshBtn: document.getElementById("dead_panel_refresh"),
                liveEndpoint: "/issues/fleet-dead-panel-status",
                cachedEndpoint: "/issues/fleet-dead-panel-status/cached",
                emptyText: "No cached results yet — click \"Check whole fleet now.\"",
                sortRank: function (row) {
                    return { dead_panel: 0 }[row.dead_panel_status];
                },
                certainty: function (row) { return row.dead_panel_confidence; },
                // Same reasoning as shadedUnits.filterFn above — a
                // healthy array (or one the check couldn't reach a
                // verdict on) isn't a finding.
                filterFn: function (row) { return row.dead_panel_status === "dead_panel"; },
                enrichFn: relatedTicketEnrichFn,
                priorityFn: relatedTicketPriorityFn,
            },
            vrmFreshness: {
                listEl: document.getElementById("vrm_freshness_list"),
                countEl: document.getElementById("vrm_freshness_count"),
                statusEl: document.getElementById("vrm_freshness_status"),
                sectionEl: document.getElementById("vrm_freshness_section"),
                refreshBtn: document.getElementById("vrm_freshness_refresh"),
                liveEndpoint: "/issues/fleet-vrm-freshness",
                cachedEndpoint: "/issues/fleet-vrm-freshness/cached",
                emptyText: "No cached results yet — click \"Check whole fleet now.\"",
                // Same "a clean unit is not a finding" reasoning as
                // shadedUnits/deadPanel's own filterFn below — this report
                // never had one, so it showed the WHOLE fleet (fresh and
                // aging installations included) instead of just the ones
                // actually overdue. Reported live: a page of "fresh"/
                // "aging" rows with only a handful of real disconnected/
                // stale ones mixed in. "unknown" (never reported at all)
                // stays in too — that's arguably the most actionable tier
                // of all, not a clean bill of health — matching the same
                // stale/disconnected/unknown set sortRank below already
                // expected to be the only tiers in this list.
                filterFn: function (row) {
                    return row.vrm_freshness === "stale"
                        || row.vrm_freshness === "disconnected"
                        || row.vrm_freshness === "unknown";
                },
                sortRank: function (row) {
                    return { disconnected: 0, stale: 1, unknown: 2, aging: 3 }[row.vrm_freshness];
                },
                // No confidence score here (freshness is elapsed time, not
                // a probabilistic read) — how overdue the site is IS the
                // certainty proxy: longer silence sorts first within the
                // same tier, and since the tiers themselves are strictly
                // ordered by elapsed-time range (disconnected always
                // longer than stale, stale always longer than aging, aging
                // always longer than fresh), sortRank-then-certainty adds
                // up to one continuous "longest silence at the top" order
                // across the whole list, tier boundaries or not.
                certainty: function (row) { return row.vrm_last_seen_seconds_ago; },
                enrichFn: relatedTicketEnrichFn,
                // Deliberately NO priorityFn here, unlike every other fleet
                // report — this report's whole point is "how overdue is
                // this trailer," so a fresh, ticketed unit pulling ahead of
                // a 3-months-silent one would defeat the report (reported
                // live: exactly that ordering, screenshot showed a page of
                // "fresh" rows before any "disconnected" one).
            },
            batteryOutlook: {
                listEl: document.getElementById("battery_outlook_list"),
                countEl: document.getElementById("battery_outlook_count"),
                statusEl: document.getElementById("battery_outlook_status"),
                sectionEl: document.getElementById("battery_outlook_section"),
                refreshBtn: document.getElementById("battery_outlook_refresh"),
                liveEndpoint: "/issues/fleet-battery-outlook",
                cachedEndpoint: "/issues/fleet-battery-outlook/cached",
                emptyText: "No cached results yet — click \"Check whole fleet now.\"",
                sortRank: function (row) {
                    return { high: 0, elevated: 1 }[row.risk];
                },
                // Not a confidence score — battery_soc_percent itself, but
                // inverted (100 - soc) so the existing "highest certainty
                // first" descending sort still does the right thing here:
                // the lower a unit's charge, the more it's worth a look
                // before ones with more headroom in the same risk tier.
                certainty: function (row) {
                    return row.battery_soc_percent == null ? undefined : 100 - row.battery_soc_percent;
                },
                // Only actual findings — a report titled Battery Outlook
                // listing every low-risk unit too just buries the ones
                // worth a look, same reasoning as shadedUnits/deadPanel.
                filterFn: function (row) { return row.risk === "elevated" || row.risk === "high"; },
                enrichFn: relatedTicketEnrichFn,
                priorityFn: relatedTicketPriorityFn,
            },
        };
        const fleetReportLoadedOnce = {};

        function renderFleetReportRows(config, data) {
            const rows = (config.filterFn ? (data.rows || []).filter(config.filterFn) : (data.rows || []).slice());
            if (config.enrichFn) {
                rows.forEach(config.enrichFn);
            }
            rows.sort(function (a, b) {
                // Ahead of everything else, including the finding's own
                // sortRank — a unit that's already got an open ticket
                // someone's working is worth seeing before ones that
                // aren't, regardless of which finding tier either is in.
                const pa = config.priorityFn ? config.priorityFn(a) : 0;
                const pb = config.priorityFn ? config.priorityFn(b) : 0;
                if (pa !== pb) {
                    return pa - pb;
                }
                const ra = config.sortRank(a);
                const rb = config.sortRank(b);
                const aRanked = ra !== undefined;
                const bRanked = rb !== undefined;
                if (aRanked && bRanked && ra !== rb) {
                    return ra - rb;
                }
                if (aRanked !== bRanked) {
                    return aRanked ? -1 : 1;
                }
                // Same finding (or both unranked) — highest certainty first.
                const ca = config.certainty ? config.certainty(a) : undefined;
                const cb = config.certainty ? config.certainty(b) : undefined;
                const aHasC = typeof ca === "number";
                const bHasC = typeof cb === "number";
                if (aHasC && bHasC && ca !== cb) {
                    return cb - ca;
                }
                if (aHasC !== bHasC) {
                    return aHasC ? -1 : 1;
                }
                return String(a.unit).localeCompare(String(b.unit));
            });
            config.listEl.innerHTML = "";
            if (!rows.length) {
                const emptyEl = document.createElement("li");
                emptyEl.className = "empty";
                emptyEl.textContent = config.emptyText;
                config.listEl.appendChild(emptyEl);
            } else {
                rows.forEach(function (row) {
                    config.listEl.appendChild(renderFleetReportRow(row));
                });
            }
            config.countEl.textContent = "(" + rows.length + ")";
            if (data.fetched_at) {
                const ageSeconds = Date.now() / 1000 - data.fetched_at;
                config.statusEl.textContent = "As of " + formatAgeShort(ageSeconds) + " ago"
                    + (data.error ? " — last poll failed: " + data.error : "");
            } else {
                config.statusEl.textContent = data.error ? ("Last poll failed: " + data.error) : "";
            }
            // Newly-built rows default to visible — re-apply whatever
            // search query is currently active (a manual refresh or the
            // background poll can both land here with one already typed).
            applyListFilters();
        }

        function loadFleetReportCached(config) {
            config.listEl.innerHTML = "";
            const loadingEl = document.createElement("li");
            loadingEl.className = "empty";
            loadingEl.textContent = "Loading cached results...";
            config.listEl.appendChild(loadingEl);
            return fetch(config.cachedEndpoint)
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    if (!data || !data.ok) {
                        throw new Error((data && data.error) || "unknown error");
                    }
                    renderFleetReportRows(config, data);
                })
                .catch(function (error) {
                    config.listEl.innerHTML = "";
                    const errEl = document.createElement("li");
                    errEl.className = "empty";
                    errEl.textContent = "Failed to load cached results: " + (error.message || error);
                    config.listEl.appendChild(errEl);
                });
        }

        function loadFleetReportLive(config) {
            config.refreshBtn.disabled = true;
            const originalLabel = config.refreshBtn.textContent;
            config.refreshBtn.textContent = "Checking whole fleet...";
            config.listEl.innerHTML = "";
            const loadingEl = document.createElement("li");
            loadingEl.className = "empty";
            loadingEl.textContent = "Checking every VRM installation fleet-wide — this takes about a minute...";
            config.listEl.appendChild(loadingEl);
            fetch(config.liveEndpoint)
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error((data && data.error) || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    renderFleetReportRows(config, data);
                })
                .catch(function (error) {
                    config.listEl.innerHTML = "";
                    const errEl = document.createElement("li");
                    errEl.className = "empty";
                    errEl.textContent = "Fleet check failed: " + (error.message || error);
                    config.listEl.appendChild(errEl);
                })
                .finally(function () {
                    config.refreshBtn.disabled = false;
                    config.refreshBtn.textContent = originalLabel;
                });
        }

        Object.keys(FLEET_REPORT_CONFIGS).forEach(function (key) {
            const config = FLEET_REPORT_CONFIGS[key];
            if (config.refreshBtn) {
                config.refreshBtn.addEventListener("click", function () {
                    loadFleetReportLive(config);
                });
            }
        });

        // ---- Reports panel (panel_mode === "reports") -------------------------
        // Reports is a page alongside Issues/Projects, not a separate toolbar
        // dropdown — applyPanelMode shows every [data-panel="reports"] section
        // at once (Flap Report + the five fleet-wide VRM checks) and this
        // lazy-loads each exactly once, the same "don't refetch on every
        // visit" cache-then-load pattern loadFleetReportCached already uses
        // per report.
        // The Camera Outage Report goes last (Andrew's request, 2026-10-02):
        // loading it auto-runs Find All Cameras, an SSH/ping check per unit,
        // so it waits until every other report has finished loading
        // (success or failure — allSettled, so one failed report can't hold
        // it back forever).
        let cameraOutageReportQueued = false;

        function ensureReportsLoaded() {
            const loads = [];
            if (!flapReportLoaded) {
                loads.push(loadFlapReport());
            }
            if (!zabbixFlapReportLoaded) {
                loads.push(loadZabbixFlapReport());
            }
            Object.keys(FLEET_REPORT_CONFIGS).forEach(function (key) {
                if (!fleetReportLoadedOnce[key]) {
                    fleetReportLoadedOnce[key] = true;
                    loads.push(loadFleetReportCached(FLEET_REPORT_CONFIGS[key]));
                }
            });
            if (!powerInfraLoaded) {
                loads.push(loadPowerInfraAlerts());
            }
            if (!alarmFrequencyLoaded) {
                loads.push(loadAlarmFrequency());
            }
            if (!recoveryEmailReportLoaded) {
                loads.push(loadRecoveryEmailReport());
            }
            if (!cameraOutageReportLoaded && !cameraOutageReportQueued) {
                cameraOutageReportQueued = true;
                if (cameraOutageReportListEl && loads.length) {
                    cameraOutageReportListEl.innerHTML = "";
                    const waitingEl = document.createElement("li");
                    waitingEl.className = "empty";
                    waitingEl.textContent = "Waiting for the other reports to finish loading (this one runs last)...";
                    cameraOutageReportListEl.appendChild(waitingEl);
                }
                Promise.allSettled(loads).then(function () {
                    cameraOutageReportQueued = false;
                    loadCameraOutageReport();
                });
            }
        }

        // ---- Power & Infra Alerts (experimental) -----------------------------
        // Zabbix's active problems x VRM's active battery alarms, merged by
        // unit — see combined_power_infra_alerts() for what "corroborated"
        // means and how an MU trailer row also picks up its RD/FD head's own
        // Zabbix problems via a server-side ERP crosswalk.
        const powerInfraSection = document.getElementById("power_infra_section");
        const powerInfraListEl = document.getElementById("power_infra_list");
        const powerInfraCountEl = document.getElementById("power_infra_count");
        const powerInfraRefreshBtn = document.getElementById("power_infra_refresh");
        const powerInfraSourceStatusEl = document.getElementById("power_infra_source_status");
        let powerInfraLoaded = false;

        function renderPowerInfraRow(row) {
            const li = document.createElement("li");
            li.className = "ticket-row ticket-row-no-rws power-infra-row"
                + (row.corroborated ? " is-corroborated" : "");

            const actions = document.createElement("div");
            actions.className = "ticket-row-actions";
            const openBtn = document.createElement("button");
            openBtn.type = "button";
            openBtn.className = "action-btn";
            // A bare MU row here is a trailer, not a full unit — it has no
            // NUC/PVE/cameras of its own, so its Commands menu is mostly
            // empty. When the ERP crosswalk (head_units, from
            // combined_power_infra_alerts) has already found the RD/FD
            // head this trailer is attached to, show and open THAT unit's
            // Commands instead — it's what actually has anything to click,
            // and RD####(MU####) reads as which unit this actually is
            // instead of a bare trailer code. A bare MU with no known head
            // is a legitimate all-in-one unit (the fleet has both), so this
            // only redirects when head_units says so, never on
            // unit-number/prefix guessing alone.
            const paired = pairedUnitDisplay(row.unit, row.head_units, row.mu_trailer);
            const openTarget = paired.openTarget;
            openBtn.textContent = paired.label;
            openBtn.title = openTarget === row.unit
                ? "Open Commands for " + row.unit + " in Unit tools"
                : "Open Commands for " + openTarget + " (" + row.unit + "'s head unit, via ERP) in Unit tools";
            openBtn.addEventListener("click", function () {
                listSearchEl.value = openTarget;
                applyListFilters();
                loadUnitTools(openTarget, true);
                // Unit Tools lives on the Issues panel — reported live:
                // clicking this from a Reports-panel row (Flap Report,
                // Power & Infra Alerts, etc.) scrolled toward a [hidden]
                // section with no layout box to scroll to at all, which
                // read as "jumped to the bottom of the page" instead of
                // opening anything. Same "switch panel first" fix as the
                // alarm glyph's own Reports-panel jump above.
                if (panelModeEl && panelModeEl.value !== "issues") {
                    panelModeEl.value = "issues";
                    applyPanelMode();
                }
                const toolsSection = document.getElementById("unit_tools_section");
                if (toolsSection && toolsSection.scrollIntoView) {
                    toolsSection.scrollIntoView({ behavior: "smooth", block: "start" });
                }
            });
            actions.appendChild(openBtn);
            li.appendChild(actions);

            const body = document.createElement("div");
            body.className = "ticket-row-body";
            const stats = document.createElement("span");
            stats.className = "power-infra-row-stats";

            if (row.corroborated) {
                const tag = document.createElement("span");
                tag.className = "source-tag zabbix";
                tag.textContent = "BOTH";
                stats.appendChild(tag);
                stats.appendChild(document.createTextNode(
                    "Zabbix AND VRM both flag this unit — likely a power issue, not just software/network."
                ));
                stats.appendChild(document.createElement("br"));
            }

            if ((row.zabbix_problems || []).length) {
                const tag = document.createElement("span");
                tag.className = "source-tag zabbix";
                tag.textContent = "ZABBIX";
                stats.appendChild(tag);
                const grouped = dedupeZabbixProblems(row.zabbix_problems);
                const text = grouped.map(function (g) {
                    const duration = formatDurationSince(g.firstClock);
                    return g.device + ": " + g.name
                        + (g.count > 1 ? " (×" + g.count + ")" : "")
                        + " [" + (ZABBIX_SEVERITY_LABELS[g.severity] || g.severity) + "]"
                        + (duration ? " — open " + duration : "");
                }).join("; ");
                stats.appendChild(document.createTextNode(text));
                stats.appendChild(document.createElement("br"));
            }

            if (row.vrm_alarm) {
                const tag = document.createElement("span");
                tag.className = "source-tag vrm";
                tag.textContent = "VRM";
                stats.appendChild(tag);
                const soc = row.vrm_alarm.battery_soc ? (" — SOC " + row.vrm_alarm.battery_soc) : "";
                const age = row.vrm_alarm.last_seen_age_minutes != null
                    ? (" (seen " + row.vrm_alarm.last_seen_age_minutes + "m ago)")
                    : "";
                stats.appendChild(document.createTextNode(row.vrm_alarm.alarm_detail + soc + age));
            }

            if ((row.head_units || []).length) {
                stats.appendChild(document.createElement("br"));
                stats.appendChild(document.createTextNode(
                    "Head unit (via ERP): " + row.head_units.join(", ")
                ));
            }

            body.appendChild(stats);
            li.appendChild(body);
            return li;
        }

        function loadPowerInfraAlerts() {
            powerInfraListEl.innerHTML = "";
            const loadingEl = document.createElement("li");
            loadingEl.className = "empty";
            loadingEl.textContent = "Loading — this checks two external APIs live, may take several seconds...";
            powerInfraListEl.appendChild(loadingEl);
            return fetch("/issues/power-infra-alerts")
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    powerInfraListEl.innerHTML = "";
                    const rows = data.rows || [];
                    if (!rows.length) {
                        const emptyEl = document.createElement("li");
                        emptyEl.className = "empty";
                        emptyEl.textContent = "No active Zabbix problems or VRM battery alarms right now.";
                        powerInfraListEl.appendChild(emptyEl);
                    } else {
                        rows.forEach(function (row) {
                            powerInfraListEl.appendChild(renderPowerInfraRow(row));
                        });
                    }
                    powerInfraCountEl.textContent = "(" + rows.length + ")";
                    const corroboratedCount = rows.filter(function (r) { return r.corroborated; }).length;
                    const statusParts = [corroboratedCount + " corroborated"];
                    if (data.zabbix_error) {
                        statusParts.push("Zabbix: " + data.zabbix_error);
                    }
                    if (data.vrm_error) {
                        statusParts.push("VRM: " + data.vrm_error);
                    }
                    powerInfraSourceStatusEl.textContent = statusParts.join(" — ");
                    powerInfraLoaded = true;
                })
                .catch(function (error) {
                    powerInfraListEl.innerHTML = "";
                    const errEl = document.createElement("li");
                    errEl.className = "empty";
                    errEl.textContent = "Power & Infra Alerts failed: " + (error.message || error);
                    powerInfraListEl.appendChild(errEl);
                });
        }

        if (powerInfraRefreshBtn) {
            powerInfraRefreshBtn.addEventListener("click", loadPowerInfraAlerts);
        }

        // ---- Alarm Frequency (experimental) -----------------------------------
        // Zabbix/VRM only ever show what's active right now; this is the
        // question neither system answers on its own — "has THIS unit's
        // alarm cleared and come back before" — from alarm_history.py,
        // which the scheduled Power & Infra Alerts poll (and this panel's
        // own Refresh, and manual power-infra-alerts fetches) has been
        // quietly recording episodes into since alarm_history.py shipped.
        // Same fleet-wide "repeat offenders" shape as Flap Report, for
        // alarms instead of validation-check health.
        const alarmFrequencySection = document.getElementById("alarm_frequency_section");
        const alarmFrequencyListEl = document.getElementById("alarm_frequency_list");
        const alarmFrequencyCountEl = document.getElementById("alarm_frequency_count");
        const alarmFrequencyDaysEl = document.getElementById("alarm_frequency_days");
        const alarmFrequencyMinEl = document.getElementById("alarm_frequency_min");
        const alarmFrequencyRefreshBtn = document.getElementById("alarm_frequency_refresh");
        const alarmFrequencyDbStatsEl = document.getElementById("alarm_frequency_db_stats");
        let alarmFrequencyLoaded = false;

        function renderAlarmFrequencyRow(row) {
            const li = document.createElement("li");
            li.className = "ticket-row ticket-row-no-rws";

            const actions = document.createElement("div");
            actions.className = "ticket-row-actions";
            const openBtn = document.createElement("button");
            openBtn.type = "button";
            openBtn.className = "action-btn";
            openBtn.textContent = row.unit;
            openBtn.title = "Open Commands for " + row.unit + " in Unit tools";
            openBtn.addEventListener("click", function () {
                listSearchEl.value = row.unit;
                applyListFilters();
                loadUnitTools(row.unit, true);
                // Unit Tools lives on the Issues panel — reported live:
                // clicking this from a Reports-panel row (Flap Report,
                // Power & Infra Alerts, etc.) scrolled toward a [hidden]
                // section with no layout box to scroll to at all, which
                // read as "jumped to the bottom of the page" instead of
                // opening anything. Same "switch panel first" fix as the
                // alarm glyph's own Reports-panel jump above.
                if (panelModeEl && panelModeEl.value !== "issues") {
                    panelModeEl.value = "issues";
                    applyPanelMode();
                }
                const toolsSection = document.getElementById("unit_tools_section");
                if (toolsSection && toolsSection.scrollIntoView) {
                    toolsSection.scrollIntoView({ behavior: "smooth", block: "start" });
                }
            });
            actions.appendChild(openBtn);
            li.appendChild(actions);

            const body = document.createElement("div");
            body.className = "ticket-row-body";
            const stats = document.createElement("span");
            stats.className = "flap-row-stats";
            stats.textContent = row.episodes + " episode(s) across " + row.distinct_alarms + " distinct alarm(s)"
                + (row.currently_open ? " — " + row.currently_open + " open now" : " — none open now")
                + ", last seen " + (row.last_seen || "unknown");
            body.appendChild(stats);
            li.appendChild(body);
            return li;
        }

        function loadAlarmFrequency() {
            const days = parseInt(alarmFrequencyDaysEl.value, 10) || 7;
            const minEpisodes = parseInt(alarmFrequencyMinEl.value, 10) || 2;
            alarmFrequencyListEl.innerHTML = "";
            const loadingEl = document.createElement("li");
            loadingEl.className = "empty";
            loadingEl.textContent = "Loading...";
            alarmFrequencyListEl.appendChild(loadingEl);
            const reportLoad = fetch("/issues/alarm-frequency?days=" + days + "&min_episodes=" + minEpisodes)
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    alarmFrequencyListEl.innerHTML = "";
                    const rows = data.rows || [];
                    if (!rows.length) {
                        const emptyEl = document.createElement("li");
                        emptyEl.className = "empty";
                        emptyEl.textContent = "No units with " + minEpisodes
                            + "+ alarm episodes in the last " + days + " day(s).";
                        alarmFrequencyListEl.appendChild(emptyEl);
                    } else {
                        rows.forEach(function (row) {
                            alarmFrequencyListEl.appendChild(renderAlarmFrequencyRow(row));
                        });
                    }
                    alarmFrequencyCountEl.textContent = "(" + rows.length + ")";
                    alarmFrequencyLoaded = true;
                })
                .catch(function (error) {
                    alarmFrequencyListEl.innerHTML = "";
                    const errEl = document.createElement("li");
                    errEl.className = "empty";
                    errEl.textContent = "Alarm frequency failed: " + (error.message || error);
                    alarmFrequencyListEl.appendChild(errEl);
                });
            fetch("/issues/alarm-history-stats")
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    if (data && data.ok && alarmFrequencyDbStatsEl) {
                        alarmFrequencyDbStatsEl.textContent = "History: " + data.episodes + " episode(s), "
                            + data.open_episodes + " open, " + data.units + " units, " + data.size_mb + " MB on disk";
                    }
                })
                .catch(function () {});
            return reportLoad; // ensureReportsLoaded waits on this
        }

        if (alarmFrequencyRefreshBtn) {
            alarmFrequencyRefreshBtn.addEventListener("click", loadAlarmFrequency);
        }

        // ---- Recovery Emails report -----------------------------------------
        // The same cached per-unit result the Graphs modal's email pill reads
        // (/issues/recovery-email-status, filled hourly after the ART report
        // download), as a fleet list grouped by status, most urgent first.
        // Same pill wording/colours as the modal (RECOVERY_EMAIL_STATUS_DISPLAY)
        // and the same lazy per-unit Commands button as the fleet reports.
        const recoveryEmailReportListEl = document.getElementById("recovery_email_report_list");
        const recoveryEmailReportCountEl = document.getElementById("recovery_email_report_count");
        const recoveryEmailReportStatusEl = document.getElementById("recovery_email_report_status");
        const recoveryEmailReportRefreshBtn = document.getElementById("recovery_email_report_refresh");
        const RECOVERY_EMAIL_REPORT_GROUP_LABELS = {
            needs_initial_email: "Outage email needed",
            needs_recovery_email: "Recovery email needed",
            potential_false_positive: "No emails, unit back up (possible false positive)",
            pending_recovery: "Outage emailed, awaiting recovery",
            email_status_up_to_date: "Emails sent",
        };
        let recoveryEmailReportLoaded = false;
        let recoveryEmailReportPollTimer = null;

        function renderRecoveryEmailReportRow(unit, info) {
            const li = document.createElement("li");
            li.className = "ticket-row ticket-row-no-rws";
            const actions = document.createElement("div");
            actions.className = "ticket-row-actions";
            attachFleetRowCommandMenu(actions, li, unit, unit, unit, info.subject || "");
            li.appendChild(actions);
            li.dataset.searchText = [unit, info.issue_id, info.subject].filter(Boolean).join(" ").toLowerCase();

            const body = document.createElement("div");
            body.className = "ticket-row-body fleet-report-body";
            const display = RECOVERY_EMAIL_STATUS_DISPLAY[info.status];
            if (display) {
                const pill = document.createElement("span");
                pill.className = "graphs-chip is-" + display.tier;
                pill.textContent = display.text;
                pill.title = display.detail;
                body.appendChild(pill);
            }
            if (info.url) {
                const link = document.createElement("a");
                link.href = info.url;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.className = "recovery-email-report-link";
                link.textContent = info.subject || info.issue_id || unit;
                if (info.issue_id) {
                    link.title = info.issue_id;
                }
                body.appendChild(link);
            } else if (info.subject) {
                const subjectEl = document.createElement("span");
                subjectEl.className = "recovery-email-report-link";
                subjectEl.textContent = info.subject;
                body.appendChild(subjectEl);
            }
            li.appendChild(body);
            return li;
        }

        function renderRecoveryEmailReport(data) {
            recoveryEmailReportListEl.innerHTML = "";
            const byUnit = (data && data.by_unit) || {};
            const units = Object.keys(byUnit).sort();
            const checkedText = data && data.checked_at
                ? "Checked " + new Date(data.checked_at * 1000).toLocaleString() + " · runs hourly"
                : "Not checked yet since the service started";
            recoveryEmailReportStatusEl.textContent = (data && data.running ? "Check running… · " : "")
                + checkedText + (data && data.error ? " · last check failed: " + data.error : "");
            if (!units.length) {
                const empty = document.createElement("li");
                empty.className = "empty";
                empty.textContent = data && data.checked_at
                    ? "No units on the ART outage report."
                    : "No result yet. It runs right after the Power vs Cell sweep at startup, then hourly — or click Re-run check now.";
                recoveryEmailReportListEl.appendChild(empty);
                recoveryEmailReportCountEl.textContent = "";
                applyListFilters();
                return;
            }
            let toSend = 0;
            Object.keys(RECOVERY_EMAIL_STATUS_DISPLAY).forEach(function (status) {
                const groupUnits = units.filter(function (unit) { return byUnit[unit].status === status; });
                if (!groupUnits.length) {
                    return;
                }
                if (status === "needs_initial_email" || status === "needs_recovery_email") {
                    toSend += groupUnits.length;
                }
                // The heading carries its rows' search text, so a search
                // keeps a group's heading exactly when one of its rows matches.
                const heading = document.createElement("li");
                heading.className = "report-group-heading";
                heading.textContent = (RECOVERY_EMAIL_REPORT_GROUP_LABELS[status] || status) + " (" + groupUnits.length + ")";
                heading.dataset.searchText = groupUnits.map(function (unit) {
                    const info = byUnit[unit];
                    return [unit, info.issue_id, info.subject].filter(Boolean).join(" ");
                }).join(" ").toLowerCase();
                recoveryEmailReportListEl.appendChild(heading);
                groupUnits.forEach(function (unit) {
                    recoveryEmailReportListEl.appendChild(renderRecoveryEmailReportRow(unit, byUnit[unit]));
                });
            });
            recoveryEmailReportCountEl.textContent = "(" + toSend + " to send)";
            recoveryEmailReportCountEl.title = toSend + " outage/recovery email(s) waiting to be sent, out of "
                + units.length + " unit(s) on the ART report";
            applyListFilters();
        }

        function loadRecoveryEmailReport() {
            recoveryEmailReportLoaded = true;
            return fetchRecoveryEmailStatus()
                .then(function (data) {
                    renderRecoveryEmailReport(data);
                    return data;
                })
                .catch(function (error) {
                    recoveryEmailReportListEl.innerHTML = "";
                    const err = document.createElement("li");
                    err.className = "empty";
                    err.textContent = "Could not load recovery email status: " + ((error && error.message) || error);
                    recoveryEmailReportListEl.appendChild(err);
                    return null;
                });
        }

        // Re-reads the cache every RECOVERY_EMAIL_POLL_MS until the check
        // finishes, then puts the button back.
        function pollRecoveryEmailReport(startedMs) {
            if (recoveryEmailReportPollTimer) {
                window.clearTimeout(recoveryEmailReportPollTimer);
            }
            recoveryEmailReportPollTimer = window.setTimeout(function () {
                recoveryEmailReportPollTimer = null;
                loadRecoveryEmailReport().then(function (data) {
                    const stillRunning = data && data.running
                        && Date.now() - startedMs < RECOVERY_EMAIL_POLL_GIVE_UP_MS;
                    if (stillRunning) {
                        pollRecoveryEmailReport(startedMs);
                        return;
                    }
                    recoveryEmailReportRefreshBtn.disabled = false;
                    recoveryEmailReportRefreshBtn.textContent = "Re-run check now";
                    if (data && !data.running) {
                        consoleLines.push("Recovery email check finished"
                            + (data.error ? " — failed: " + data.error : "") + ".");
                        renderConsole(true);
                    }
                });
            }, RECOVERY_EMAIL_POLL_MS);
        }

        if (recoveryEmailReportRefreshBtn) {
            recoveryEmailReportRefreshBtn.addEventListener("click", function () {
                recoveryEmailReportRefreshBtn.disabled = true;
                recoveryEmailReportRefreshBtn.textContent = "Running…";
                fetch("/issues/recovery-email-status/refresh", { method: "POST" })
                    .then(function (response) { return response.json(); })
                    .then(function (data) {
                        if (!data || !data.ok) {
                            throw new Error((data && data.error) || "refresh failed");
                        }
                        consoleLines.push(data.started
                            ? "Recovery email check started — pings every unit on the ART report, a few minutes."
                            : "Recovery email check already running — waiting for it to finish.");
                        renderConsole(true);
                        statusEl.textContent = "Recovery email check running...";
                        recoveryEmailReportStatusEl.textContent = "Check running…";
                        pollRecoveryEmailReport(Date.now());
                    })
                    .catch(function (error) {
                        recoveryEmailReportRefreshBtn.disabled = false;
                        recoveryEmailReportRefreshBtn.textContent = "Re-run check now";
                        notify("Could not start the recovery email check: "
                            + ((error && error.message) || error) + ". Try again in a moment.", "error");
                    });
            });
        }

        function openPatchUpdateModal(unit, button) {
            patchUpdateUnit = unit || "";
            patchUpdateButton = button || null;
            patchUpdateMessage.textContent =
                "This will SSH to " + patchUpdateUnit
                + " and run the install update command from .env. Continue?";
            patchUpdateModal.classList.add("is-open");
            patchUpdateCancel.focus();
        }

        function closePatchUpdateModal() {
            patchUpdateModal.classList.remove("is-open");
            patchUpdateUnit = "";
            patchUpdateButton = null;
        }

        function runPatchUpdate() {
            const unit = patchUpdateUnit;
            const button = patchUpdateButton;
            closePatchUpdateModal();
            if (!unit) {
                return;
            }
            if (button) {
                button.disabled = true;
                button.textContent = "Updating...";
            }
            statusEl.textContent = "Updating patch version for " + unit + "...";
            consoleLines.push("Update Patch Version " + unit + " starting...");
            renderConsole(true);
            // Streamed live (see stream_update_unit_patch_version) — the
            // install script can run for minutes with real intermediate
            // output; the old all-at-once version left a tech staring at
            // "Updating..." with nothing to look at until it either
            // finished or hit the timeout (reported live, 2026-09-17,
            // after RD3421's own update failed with no visibility into
            // what actually happened). Same reader-loop shape as
            // startLongPingForUnit/startEmailTestLoopForUnit's own streams.
            let lastLine = "";
            fetch("/issues/update-patch-stream/" + encodeURIComponent(unit), { method: "POST" })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("HTTP " + response.status);
                    }
                    if (!response.body || !response.body.getReader) {
                        return response.text().then(function (text) {
                            String(text || "").split(/\r?\n/).forEach(function (line) {
                                if (line) {
                                    consoleLines.push(line);
                                    lastLine = line;
                                }
                            });
                            renderConsole(true);
                        });
                    }
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();
                    let buffer = "";
                    function readChunk() {
                        return reader.read().then(function (result) {
                            if (result.done) {
                                if (buffer) {
                                    consoleLines.push(buffer);
                                    lastLine = buffer;
                                    renderConsole(true);
                                }
                                return;
                            }
                            buffer += decoder.decode(result.value, { stream: true });
                            const parts = buffer.split(/\r?\n/);
                            buffer = parts.pop() || "";
                            parts.forEach(function (line) {
                                if (line) {
                                    consoleLines.push(line);
                                    lastLine = line;
                                }
                            });
                            if (parts.length) {
                                renderConsole(true);
                                statusEl.textContent = "Patch update running for " + unit + "...";
                            }
                            return readChunk();
                        });
                    }
                    return readChunk();
                })
                .then(function () {
                    const failed = /FAILED/.test(lastLine);
                    statusEl.textContent = (failed ? "Patch update FAILED for " : "Patch update finished for ") + unit + ".";
                    if (failed) {
                        notifyError("Patch update failed for " + unit + " — see stdout above for detail");
                    }
                })
                .catch(function (error) {
                    const message = "Update Patch Version failed: " + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    if (button) {
                        button.disabled = false;
                        button.textContent = "Update Patch Version";
                    }
                });
        }

        patchUpdateCancel.addEventListener("click", closePatchUpdateModal);
        patchUpdateConfirm.addEventListener("click", runPatchUpdate);
        patchUpdateModal.addEventListener("click", function (event) {
            if (event.target === patchUpdateModal) {
                closePatchUpdateModal();
            }
        });

        function securityFixLogLine(text) {
            if (!text) {
                return;
            }
            securityFixLog.textContent += (securityFixLog.textContent ? "\n" : "") + text;
            securityFixLog.scrollTop = securityFixLog.scrollHeight;
            consoleLines.push(text);
        }

        function securityFixDriverBadge(label, count, expected) {
            const ok = count === expected;
            const badge = document.createElement("span");
            badge.className = "driver-check-badge is-" + (ok ? "ok" : "fail");
            badge.textContent = (ok ? "✓ " : "✗ ") + label + " " + count + "/" + expected;
            badge.title = ok
                ? label + " grepped the expected " + expected + " — looks right."
                : label + " grepped " + count + ", expected " + expected + " — some drivers did not load.";
            return badge;
        }

        // After Restart All Services, the fix is done and the two things
        // worth checking by eye are the unit's platform (Scrypted's own
        // "system" page) and Scrypted's management console — pull their
        // URLs the same way Unit Tools/the Open submenu do
        // (/issues/unit-context, which already resolves has_platform/
        // platform_url/has_scrypted/scrypted_url from the net sheet) and
        // open both automatically instead of making someone dig into the
        // command menu right after just finishing the wizard.
        function openSecurityFixPlatformAndScrypted(unit) {
            fetch("/issues/unit-context/" + encodeURIComponent(unit))
                .then(function (resp) { return resp.json(); })
                .then(function (data) {
                    if (!data || data.ok === false) {
                        securityFixLogLine(
                            "Could not resolve Platform/Scrypted links for " + unit + ": "
                            + ((data && data.error) || "unknown error")
                        );
                        return;
                    }
                    [
                        { has: data.has_platform, url: data.platform_url, label: "Platform" },
                        { has: data.has_scrypted, url: data.scrypted_url, label: "Scrypted" },
                    ].forEach(function (item) {
                        if (!item.has || !item.url) {
                            securityFixLogLine("No " + item.label + " URL available for " + unit + " — skipped.");
                            return;
                        }
                        // A pop-up blocker can still refuse this — it's not
                        // a direct click, just an async fetch's .then() a
                        // few seconds after the last real one (Restart
                        // Services). window.open returning null/undefined
                        // is exactly how a browser signals "blocked," so
                        // fall back to a dismissable action the user can
                        // click instead of silently doing nothing.
                        const opened = window.open(item.url, "_blank", "noopener,noreferrer");
                        if (opened) {
                            securityFixLogLine("Opened " + item.label + " for " + unit + ".");
                        } else {
                            securityFixLogLine(
                                item.label + " tab for " + unit + " was blocked by the browser's pop-up blocker."
                            );
                            notify(
                                item.label + " for " + unit + " was blocked by the browser's pop-up blocker.",
                                "error",
                                {
                                    actionLabel: "Open " + item.label,
                                    onAction: function () {
                                        window.open(item.url, "_blank", "noopener,noreferrer");
                                    },
                                }
                            );
                        }
                    });
                })
                .catch(function (error) {
                    securityFixLogLine(
                        "Could not resolve Platform/Scrypted links for " + unit + ": " + (error.message || error)
                    );
                });
        }

        // Verify step visual: the VGA/i915 counts security_update_web_verify
        // greps for used to only exist as two plain lines buried in the
        // scrolling log — easy to miss a short count on. Two colored pills
        // instead, so a short count reads as wrong at a glance.
        function renderSecurityFixDriverCheck(data) {
            securityFixDriverCheck.innerHTML = "";
            if (!data || data.vga_counter == null || data.i915_counter == null) {
                securityFixDriverCheck.hidden = true;
                return;
            }
            securityFixDriverCheck.appendChild(
                securityFixDriverBadge("VGA controllers", data.vga_counter, data.vga_expected)
            );
            securityFixDriverCheck.appendChild(
                securityFixDriverBadge("i915 entries", data.i915_counter, data.i915_expected)
            );
            securityFixDriverCheck.hidden = false;
        }

        function securityFixStorageKey(unit) {
            return "security_fix_token_" + unit;
        }

        function saveSecurityFixToken(unit, token) {
            securityFixToken = token || null;
            try {
                if (token) {
                    localStorage.setItem(securityFixStorageKey(unit), token);
                } else {
                    localStorage.removeItem(securityFixStorageKey(unit));
                }
            } catch (e) {
                // Private browsing / storage disabled — the wizard still works,
                // it just won't be able to resume after a refresh.
            }
        }

        function loadSecurityFixToken(unit) {
            try {
                return localStorage.getItem(securityFixStorageKey(unit)) || null;
            } catch (e) {
                return null;
            }
        }

        function securityFixCall(path, body) {
            const payload = Object.assign({}, body || {}, { token: securityFixToken });
            return fetch(path + encodeURIComponent(securityFixUnit), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            }).then(function (response) {
                return response.json().then(function (data) {
                    if (!response.ok || !data.ok) {
                        throw new Error(data.error || ("HTTP " + response.status));
                    }
                    return data;
                });
            });
        }

        function setSecurityFixButton(label, disabled) {
            securityFixAction.textContent = label;
            securityFixAction.disabled = !!disabled;
        }

        // Sets the modal's message + button label for a given client wizard
        // phase, without making a network call. Used both when a step just
        // completed and when resuming an in-flight job after a refresh.
        function applySecurityFixPhaseUI(phase, unit) {
            securityFixPhase = phase;
            // Keep the jump dropdown in sync with wherever the wizard
            // actually is — both when a step completes normally and when
            // the tech picked this phase directly (its own change handler
            // calls this same function). "done" has no matching option;
            // leave the select showing whatever it last did.
            if (securityFixJumpSelect && [...securityFixJumpSelect.options].some(function (opt) { return opt.value === phase; })) {
                securityFixJumpSelect.value = phase;
            }
            if (securityFixJumpVersionRow) {
                securityFixJumpVersionRow.hidden = phase !== "awaiting_shutdown";
            }
            if (phase === "start") {
                securityFixMessage.textContent =
                    "Step 1 of 5: stop VM 101 on PVE and remove the GPU passthrough (hostpci0) "
                    + "config for " + unit + ". Continue?";
                setSecurityFixButton("Run Step 1", false);
            } else if (phase === "awaiting_webui") {
                securityFixMessage.textContent =
                    "Now, on the PVE host web interface: open VM 101 → Console → "
                    + "Start Now. When the GRUB menu appears, go to Advanced Options and "
                    + "select \"Ubuntu, with Linux 6.8.0-138-generic\" specifically — that's "
                    + "the known-good build Step 2 pins; any other kernel is a purge target, "
                    + "not something to boot into. Once it's booted, click Continue.";
                setSecurityFixButton("Continue to Step 2", false);
            } else if (phase === "awaiting_reboot") {
                securityFixMessage.textContent =
                    unit + " is rebooting onto the held kernel. Once it's back up and "
                    + "reachable over SSH, click Continue to confirm the kernel and shut "
                    + "it down for the GPU reassignment.";
                setSecurityFixButton("Confirm Kernel & Shut Down", false);
            } else if (phase === "awaiting_shutdown") {
                securityFixMessage.textContent =
                    unit + " is shutting down. Confirm on PVE (or via ping) that it is "
                    + "fully powered off, then click Continue to reassign the GPU and "
                    + "start the VM back up. Do not continue before it is fully off.";
                setSecurityFixButton("Confirm Shutdown & Finish", false);
            } else if (phase === "verify") {
                securityFixMessage.textContent =
                    "VM 101 is starting back up. Once " + unit + " is reachable again, "
                    + "click Continue to verify the passthrough drivers loaded.";
                setSecurityFixButton("Verify Drivers", false);
            } else if (phase === "restart") {
                securityFixMessage.textContent =
                    "Click Continue to restart all platform services on " + unit + ".";
                setSecurityFixButton("Restart Services", false);
            } else if (phase === "done") {
                securityFixMessage.textContent = "Security update fix complete for " + unit + ".";
                setSecurityFixButton("Done", false);
            }
        }

        function closeSecurityFixModal() {
            securityFixModal.classList.remove("is-open");
            securityFixUnit = "";
            securityFixButton = null;
            securityFixVersion = null;
            securityFixPhase = "start";
            securityFixToken = null;
            securityFixLockedByOther = false;
            securityFixLog.textContent = "";
            securityFixDriverCheck.hidden = true;
            securityFixDriverCheck.innerHTML = "";
            securityFixForceClear.hidden = true;
            securityFixAction.hidden = false;
            securityFixJump.hidden = false;
            securityFixJumpSelect.value = "start";
            securityFixJumpVersionInput.value = "";
            securityFixJumpVersionRow.hidden = true;
        }

        function openSecurityFixModal(unit, button) {
            securityFixUnit = unit || "";
            securityFixButton = button || null;
            securityFixVersion = null;
            securityFixLog.textContent = "";
            securityFixDriverCheck.hidden = true;
            securityFixDriverCheck.innerHTML = "";
            securityFixForceClear.hidden = true;
            securityFixAction.hidden = false;
            securityFixLockedByOther = false;
            securityFixJump.hidden = false;
            securityFixJumpVersionInput.value = "";
            securityFixModal.classList.add("is-open");

            const savedToken = loadSecurityFixToken(securityFixUnit);
            applySecurityFixPhaseUI("start", securityFixUnit);
            securityFixMessage.textContent = "Checking " + securityFixUnit + "'s status...";
            setSecurityFixButton("Checking...", true);

            const statusUrl = "/issues/unit-status/" + encodeURIComponent(securityFixUnit)
                + (savedToken ? ("?token=" + encodeURIComponent(savedToken)) : "");
            fetch(statusUrl)
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    if (!data.busy) {
                        // Nothing in flight — fresh start. Clear any stale token.
                        saveSecurityFixToken(securityFixUnit, null);
                        applySecurityFixPhaseUI("start", securityFixUnit);
                        return;
                    }
                    if (data.is_owner && savedToken) {
                        // Resume our own in-flight job where it left off.
                        securityFixToken = savedToken;
                        securityFixVersion = data.version || null;
                        (data.log || []).forEach(function (line) {
                            securityFixLogLine(line);
                        });
                        const resumePhase = SECURITY_FIX_RESUME_PHASE[data.phase] || "start";
                        applySecurityFixPhaseUI(resumePhase, securityFixUnit);
                        securityFixLogLine(
                            "(Resumed in-progress security fix from a previous session.)"
                        );
                    } else if (data.action === "Security Update Fix") {
                        // Someone else's wizard is running against this unit.
                        securityFixLockedByOther = true;
                        securityFixMessage.textContent =
                            "A security update fix is already in progress on " + securityFixUnit
                            + " (phase: " + (data.phase || "unknown") + "). If that session is "
                            + "gone or stuck, use Force Clear Lock below to release it.";
                        securityFixAction.hidden = true;
                        securityFixJump.hidden = true;
                        securityFixForceClear.hidden = false;
                    } else {
                        // Busy with a different quick action (reboot, restart services).
                        securityFixLockedByOther = true;
                        securityFixMessage.textContent =
                            securityFixUnit + " is busy: " + (data.action || "another action")
                            + ". Wait for it to finish, or use Force Clear Lock if it's stuck.";
                        securityFixAction.hidden = true;
                        securityFixJump.hidden = true;
                        securityFixForceClear.hidden = false;
                    }
                })
                .catch(function () {
                    // Status check failed — fall back to a plain fresh start.
                    applySecurityFixPhaseUI("start", securityFixUnit);
                });
            securityFixCancel.focus();
        }

        function runSecurityFixPhase() {
            const unit = securityFixUnit;
            if (!unit) {
                return;
            }
            if (securityFixPhase === "start") {
                setSecurityFixButton("Running step 1...", true);
                securityFixCall("/issues/security-update-fix/step1/")
                    .then(function (data) {
                        securityFixVersion = data.version;
                        saveSecurityFixToken(unit, data.token);
                        securityFixLogLine(data.message || "Step 1 complete.");
                        applySecurityFixPhaseUI("awaiting_webui", unit);
                    })
                    .catch(function (error) {
                        securityFixLogLine("Step 1 failed: " + (error.message || error));
                        setSecurityFixButton("Retry Step 1", false);
                    });
            } else if (securityFixPhase === "awaiting_webui") {
                setSecurityFixButton("Running step 2...", true);
                securityFixCall("/issues/security-update-fix/step2/")
                    .then(function (data) {
                        securityFixLogLine(data.message || "Step 2 complete.");
                        applySecurityFixPhaseUI("awaiting_reboot", unit);
                    })
                    .catch(function (error) {
                        securityFixLogLine("Step 2 failed: " + (error.message || error));
                        setSecurityFixButton("Retry Step 2", false);
                    });
            } else if (securityFixPhase === "awaiting_reboot") {
                setSecurityFixButton("Shutting down...", true);
                securityFixMessage.textContent = unit + " is shutting down. Please wait...";
                securityFixCall("/issues/security-update-fix/shutdown/")
                    .then(function (data) {
                        securityFixLogLine(data.message || "Shutdown triggered.");
                        applySecurityFixPhaseUI("awaiting_shutdown", unit);
                    })
                    .catch(function (error) {
                        securityFixLogLine("Shutdown step failed: " + (error.message || error));
                        setSecurityFixButton("Retry Shutdown", false);
                    });
            } else if (securityFixPhase === "awaiting_shutdown") {
                // securityFixVersion is already set here for BOTH the
                // normal flow (Step 1's own response, earlier in this
                // function) and a genuine auto-resume (restored from
                // data.version in openSecurityFixModal) — only fall back
                // to the manual input when it's genuinely missing, i.e.
                // reached via the jump dropdown with no Step 1 run this
                // session. Don't silently proceed with nothing either
                // way: Finish's `qm set 101 --hostpci0` needs a real PCI
                // address, not null.
                if (!securityFixVersion) {
                    const manualVersion = securityFixJumpVersionInput.value.trim();
                    if (!manualVersion) {
                        securityFixLogLine("Enter Step 1's saved hostpci0 value above before continuing to Finish.");
                        return;
                    }
                    securityFixVersion = manualVersion;
                }
                setSecurityFixButton("Finishing...", true);
                securityFixCall("/issues/security-update-fix/finish/", { version: securityFixVersion })
                    .then(function (data) {
                        securityFixLogLine(data.message || "GPU reassigned, VM starting.");
                        applySecurityFixPhaseUI("verify", unit);
                    })
                    .catch(function (error) {
                        securityFixLogLine("Finish step failed: " + (error.message || error));
                        setSecurityFixButton("Retry Finish", false);
                    });
            } else if (securityFixPhase === "verify") {
                setSecurityFixButton("Verifying...", true);
                securityFixCall("/issues/security-update-fix/verify/")
                    .then(function (data) {
                        securityFixLogLine(data.message || "Verification complete.");
                        renderSecurityFixDriverCheck(data);
                        applySecurityFixPhaseUI("restart", unit);
                        if (!data.drivers_loaded) {
                            securityFixMessage.textContent =
                                "Some drivers did not load — check the log above. You can still "
                                + "continue to restart services, or Cancel to investigate first.";
                        }
                    })
                    .catch(function (error) {
                        securityFixLogLine("Verify step failed: " + (error.message || error));
                        setSecurityFixButton("Retry Verify", false);
                    });
            } else if (securityFixPhase === "restart") {
                setSecurityFixButton("Restarting...", true);
                securityFixCall("/issues/restart-services/")
                    .then(function (data) {
                        securityFixLogLine(data.message || "Services restarted.");
                        saveSecurityFixToken(unit, null);
                        applySecurityFixPhaseUI("done", unit);
                        renderConsole(true);
                        statusEl.textContent = "Security update fix complete for " + unit + ".";
                        openSecurityFixPlatformAndScrypted(unit);
                    })
                    .catch(function (error) {
                        securityFixLogLine("Restart step failed: " + (error.message || error));
                        setSecurityFixButton("Retry Restart", false);
                    });
            } else {
                closeSecurityFixModal();
            }
        }

        securityFixCancel.addEventListener("click", closeSecurityFixModal);
        securityFixAction.addEventListener("click", runSecurityFixPhase);
        securityFixJumpSelect.addEventListener("change", function () {
            if (!securityFixUnit || securityFixLockedByOther) {
                return;
            }
            applySecurityFixPhaseUI(securityFixJumpSelect.value, securityFixUnit);
        });
        securityFixForceClear.addEventListener("click", function () {
            const unit = securityFixUnit;
            if (!unit) {
                return;
            }
            securityFixForceClear.disabled = true;
            fetch("/issues/unit-lock/" + encodeURIComponent(unit) + "/clear", { method: "POST" })
                .then(function (response) { return response.json(); })
                .then(function () {
                    saveSecurityFixToken(unit, null);
                    securityFixLockedByOther = false;
                    securityFixForceClear.hidden = true;
                    securityFixForceClear.disabled = false;
                    securityFixAction.hidden = false;
                    securityFixJump.hidden = false;
                    applySecurityFixPhaseUI("start", unit);
                })
                .catch(function () {
                    securityFixForceClear.disabled = false;
                });
        });
        securityFixModal.addEventListener("click", function (event) {
            if (event.target === securityFixModal) {
                closeSecurityFixModal();
            }
        });

        function executeBounceAction(unit, label, endpoint, bounceBtn) {
            if (!unit || !endpoint) {
                return;
            }
            if (bounceBtn) {
                bounceBtn.disabled = true;
                bounceBtn.textContent = "Starting...";
            }
            fetch(endpoint + encodeURIComponent(unit), { method: "POST" })
                .then(function (response) {
                    if (!response.ok) {
                        return response.text().then(function (body) {
                            let message = body || ("HTTP " + response.status);
                            try {
                                message = JSON.parse(body).error || message;
                            } catch (ignore) {
                                // plain text error
                            }
                            throw new Error(message);
                        });
                    }
                    if (bounceBtn) {
                        bounceBtn.textContent = "Running...";
                    }
                    let bufferedText = "";
                    function appendOutput(text, finalChunk) {
                        bufferedText += text;
                        const lines = bufferedText.split(/\r?\n/);
                        bufferedText = finalChunk ? "" : lines.pop();
                        lines.forEach(function (line) {
                            if (line) {
                                consoleLines.push(line);
                            }
                        });
                        if (finalChunk && bufferedText) {
                            consoleLines.push(bufferedText);
                            bufferedText = "";
                        }
                        renderConsole(true);
                    }
                    if (!response.body || !response.body.getReader) {
                        return response.text().then(function (text) {
                            appendOutput(text, true);
                        });
                    }
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();
                    function readOutput() {
                        return reader.read().then(function (chunk) {
                            if (chunk.done) {
                                appendOutput(decoder.decode(), true);
                                return;
                            }
                            appendOutput(
                                decoder.decode(chunk.value, { stream: true }),
                                false
                            );
                            return readOutput();
                        });
                    }
                    return readOutput();
                })
                .then(function () {
                    if (bounceBtn) {
                        bounceBtn.textContent = "Finished";
                        window.setTimeout(function () {
                            bounceBtn.disabled = false;
                            bounceBtn.textContent = label;
                        }, 1500);
                    }
                })
                .catch(function (error) {
                    notifyError(label + " failed: " + (error.message || error));
                    if (bounceBtn) {
                        bounceBtn.disabled = false;
                        bounceBtn.textContent = label;
                    }
                });
        }

        function openCreateDeploymentModal(projectId, subject, button) {
            createDeploymentProjectId = projectId || "";
            createDeploymentSubject = subject || "";
            createDeploymentButton = button || null;
            createDeploymentMessage.textContent = subject
                ? ("Create an NOC Deployment project from: " + subject)
                : "Create an NOC Deployment project from the selected Prep project.";
            createDeploymentModal.classList.add("is-open");
            createDeploymentCancel.focus();
        }

        function closeCreateDeploymentModal() {
            createDeploymentModal.classList.remove("is-open");
            createDeploymentProjectId = "";
            createDeploymentSubject = "";
            createDeploymentButton = null;
        }

        function openCreateDeploymentSuccessModal(url, projectName, projects) {
            const messageEl = document.getElementById("create_deployment_success_message");
            const titleEl = document.getElementById("create_deployment_success_title");
            const list = (projects && projects.length)
                ? projects
                : [{ url: url || "", project_name: projectName || "Open project" }];
            titleEl.textContent = list.length > 1
                ? ("Projects successfully created (" + list.length + ")")
                : "Project successfully created";
            messageEl.innerHTML = "";
            list.forEach(function (project, index) {
                if (index) {
                    messageEl.appendChild(document.createElement("br"));
                }
                const link = document.createElement("a");
                link.href = project.url || "#";
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.textContent = project.project_name || project.project_id || "Open project";
                if (!project.url) {
                    link.hidden = true;
                }
                messageEl.appendChild(link);
            });
            createDeploymentSuccessModal.classList.add("is-open");
            createDeploymentSuccessOk.focus();
        }

        function closeCreateDeploymentSuccessModal() {
            createDeploymentSuccessModal.classList.remove("is-open");
        }

        function runCreateDeployment() {
            const projectId = createDeploymentProjectId;
            const subject = createDeploymentSubject;
            const button = createDeploymentButton;
            closeCreateDeploymentModal();
            if (!projectId) {
                return;
            }
            if (button) {
                button.disabled = true;
                button.textContent = "Creating...";
            }
            statusEl.textContent = "Creating Deployment Project...";
            fetch("/issues/create-deployment-project", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    project_id: projectId,
                    subject: subject,
                }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const createdName = data.project_name || data.project_id || "project";
                    consoleLines.push(
                        "Created Deployment Project " + createdName
                        + (data.project_id ? (" (" + data.project_id + ")") : "")
                    );
                    renderConsole(true);
                    statusEl.textContent = "Project successfully created.";
                    openCreateDeploymentSuccessModal(data.url || "", createdName);
                })
                .catch(function (error) {
                    const message = "Create Deployment Project failed: "
                        + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    if (button) {
                        button.disabled = false;
                        button.textContent = "Create Deployment Project";
                    }
                });
        }

        createDeploymentCancel.addEventListener("click", closeCreateDeploymentModal);
        createDeploymentConfirm.addEventListener("click", runCreateDeployment);
        createDeploymentModal.addEventListener("click", function (event) {
            if (event.target === createDeploymentModal) {
                closeCreateDeploymentModal();
            }
        });
        createDeploymentSuccessOk.addEventListener("click", closeCreateDeploymentSuccessModal);
        createDeploymentSuccessModal.addEventListener("click", function (event) {
            if (event.target === createDeploymentSuccessModal) {
                closeCreateDeploymentSuccessModal();
            }
        });
        document.addEventListener("keydown", function (event) {
            if (event.key !== "Escape") {
                return;
            }
            if (createDeploymentModal.classList.contains("is-open")) {
                closeCreateDeploymentModal();
            }
            if (createDeploymentSuccessModal.classList.contains("is-open")) {
                closeCreateDeploymentSuccessModal();
            }
            if (createTerminationModal.classList.contains("is-open")) {
                closeCreateTerminationModal();
            }
            if (createRelocationModal.classList.contains("is-open")) {
                closeCreateRelocationModal();
            }
            if (siteActionModal.classList.contains("is-open")) {
                closeSiteActionModal();
            }
            if (techChecksModal.classList.contains("is-open")) {
                closeTechChecksModal();
            }
            if (clearMuCoordinatesModal.classList.contains("is-open")) {
                closeClearMuCoordinatesModal();
            }
            if (clearMuSiteModal.classList.contains("is-open")) {
                closeClearMuSiteModal();
            }
            if (createRefurbishModal.classList.contains("is-open")) {
                closeCreateRefurbishModal();
            }
        });

        function openCreateTerminationModal(issueId, subject, button) {
            createTerminationIssueId = issueId || "";
            createTerminationSubject = subject || "";
            createTerminationButton = button || null;
            createTerminationMessage.textContent = subject
                ? ("Create an NOC Termination project for each unit in: " + subject)
                : "Create an NOC Termination project for each unit in the selected ticket.";
            createTerminationModal.classList.add("is-open");
            createTerminationCancel.focus();
        }

        function closeCreateTerminationModal() {
            createTerminationModal.classList.remove("is-open");
            createTerminationIssueId = "";
            createTerminationSubject = "";
            createTerminationButton = null;
        }

        function runCreateTermination() {
            const issueId = createTerminationIssueId;
            const subject = createTerminationSubject;
            const button = createTerminationButton;
            closeCreateTerminationModal();
            if (!issueId) {
                return;
            }
            if (button) {
                button.disabled = true;
                button.textContent = "Creating...";
            }
            statusEl.textContent = "Creating Termination Project...";
            fetch("/issues/create-termination-project", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    issue_id: issueId,
                    subject: subject,
                }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const projects = (data.projects && data.projects.length)
                        ? data.projects
                        : [{
                            project_id: data.project_id,
                            project_name: data.project_name,
                            url: data.url,
                        }];
                    projects.forEach(function (project) {
                        consoleLines.push(
                            "Created Termination Project "
                            + (project.project_name || project.project_id || "project")
                            + (project.project_id ? (" (" + project.project_id + ")") : "")
                        );
                    });
                    (data.errors || []).forEach(function (line) {
                        if (line) {
                            consoleLines.push("Create Termination Project warning: " + line);
                        }
                    });
                    renderConsole(true);
                    statusEl.textContent = projects.length > 1
                        ? ("Created " + projects.length + " Termination projects.")
                        : "Project successfully created.";
                    openCreateDeploymentSuccessModal(
                        data.url || "",
                        data.project_name || "",
                        projects
                    );
                })
                .catch(function (error) {
                    const message = "Create Termination Project failed: "
                        + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    if (button) {
                        button.disabled = false;
                        button.textContent = "Create Termination Project";
                    }
                });
        }

        createTerminationCancel.addEventListener("click", closeCreateTerminationModal);
        createTerminationConfirm.addEventListener("click", runCreateTermination);
        createTerminationModal.addEventListener("click", function (event) {
            if (event.target === createTerminationModal) {
                closeCreateTerminationModal();
            }
        });

        function openCreateRelocationModal(issueId, subject, button) {
            createRelocationIssueId = issueId || "";
            createRelocationSubject = subject || "";
            createRelocationButton = button || null;
            createRelocationMessage.textContent = subject
                ? ("Create an NOC Relocation project for each unit in: " + subject)
                : "Create an NOC Relocation project for each unit in the selected ticket.";
            createRelocationModal.classList.add("is-open");
            createRelocationCancel.focus();
        }

        function closeCreateRelocationModal() {
            createRelocationModal.classList.remove("is-open");
            createRelocationIssueId = "";
            createRelocationSubject = "";
            createRelocationButton = null;
        }

        function runCreateRelocation() {
            const issueId = createRelocationIssueId;
            const subject = createRelocationSubject;
            const button = createRelocationButton;
            closeCreateRelocationModal();
            if (!issueId) {
                return;
            }
            if (button) {
                button.disabled = true;
                button.textContent = "Creating...";
            }
            statusEl.textContent = "Creating Relocation Project...";
            fetch("/issues/create-relocation-project", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    issue_id: issueId,
                    subject: subject,
                }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const projects = (data.projects && data.projects.length)
                        ? data.projects
                        : [{
                            project_id: data.project_id,
                            project_name: data.project_name,
                            url: data.url,
                        }];
                    projects.forEach(function (project) {
                        consoleLines.push(
                            "Created Relocation Project "
                            + (project.project_name || project.project_id || "project")
                            + (project.project_id ? (" (" + project.project_id + ")") : "")
                        );
                    });
                    (data.errors || []).forEach(function (line) {
                        if (line) {
                            consoleLines.push("Create Relocation Project warning: " + line);
                        }
                    });
                    renderConsole(true);
                    statusEl.textContent = projects.length > 1
                        ? ("Created " + projects.length + " Relocation projects.")
                        : "Project successfully created.";
                    openCreateDeploymentSuccessModal(
                        data.url || "",
                        data.project_name || "",
                        projects
                    );
                })
                .catch(function (error) {
                    const message = "Create Relocation Project failed: "
                        + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    if (button) {
                        button.disabled = false;
                        button.textContent = "Create Relocation Project";
                    }
                });
        }

        createRelocationCancel.addEventListener("click", closeCreateRelocationModal);
        createRelocationConfirm.addEventListener("click", runCreateRelocation);
        createRelocationModal.addEventListener("click", function (event) {
            if (event.target === createRelocationModal) {
                closeCreateRelocationModal();
            }
        });

        function closeSiteActionModal() {
            siteActionModal.classList.remove("is-open");
            siteActionKind = "";
            siteActionSubject = "";
            siteActionSiteId = "";
            siteActionButton = null;
        }

        function muTrailerFromSubject(subject, unit) {
            const text = String(subject || "");
            const parentMatch = text.match(/\bRD\s*\d+\s*\(\s*MU\s*(\d+)\s*\)/i);
            if (parentMatch) {
                return "MU" + parentMatch[1];
            }
            const unitText = String(unit || "").replace(/\s+/g, "").toUpperCase();
            if (/^MU\d{3,6}$/.test(unitText)) {
                return unitText;
            }
            const muMatch = text.match(/\bMU\s*(\d{3,6})\b/i);
            if (muMatch) {
                return "MU" + muMatch[1];
            }
            return "";
        }

        function openClearMuCoordinatesModal(subject, unit, button) {
            const mu = muTrailerFromSubject(subject, unit);
            if (!mu) {
                notifyError("Could not determine MU trailer from this project subject.");
                return;
            }
            clearMuCoordinatesSubject = subject || "";
            clearMuCoordinatesUnit = unit || "";
            clearMuCoordinatesMu = mu;
            clearMuCoordinatesButton = button || null;
            clearMuCoordinatesMessage.textContent =
                "Set latitude and longitude to 0 on ERP Component SC-" + mu + "?";
            clearMuCoordinatesModal.classList.add("is-open");
            clearMuCoordinatesCancel.focus();
        }

        function closeClearMuCoordinatesModal() {
            clearMuCoordinatesModal.classList.remove("is-open");
            clearMuCoordinatesSubject = "";
            clearMuCoordinatesUnit = "";
            clearMuCoordinatesMu = "";
            if (clearMuCoordinatesButton) {
                clearMuCoordinatesButton.disabled = false;
                clearMuCoordinatesButton.textContent = "Clear MU Coordinates";
            }
            clearMuCoordinatesButton = null;
        }

        function runClearMuCoordinates() {
            const subject = clearMuCoordinatesSubject;
            const unit = clearMuCoordinatesUnit;
            const mu = clearMuCoordinatesMu;
            const button = clearMuCoordinatesButton;
            closeClearMuCoordinatesModal();
            if (button) {
                button.disabled = true;
                button.textContent = "Clearing...";
            }
            statusEl.textContent = "Clearing MU coordinates for " + mu + "...";
            fetch("/issues/clear-mu-coordinates", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    subject: subject,
                    unit: unit,
                    mu: mu,
                }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const line =
                        "Clear MU coordinates — "
                        + (data.component || ("SC-" + mu))
                        + ": ("
                        + (data.old_latitude ?? "—")
                        + ", "
                        + (data.old_longitude ?? "—")
                        + ") -> ("
                        + (data.latitude ?? 0)
                        + ", "
                        + (data.longitude ?? 0)
                        + ")";
                    consoleLines.push(line);
                    renderConsole(true);
                    statusEl.textContent = "MU coordinates cleared for " + (data.mu || mu) + ".";
                })
                .catch(function (error) {
                    const message = "Clear MU coordinates failed: " + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    if (button) {
                        button.disabled = false;
                        button.textContent = "Clear MU Coordinates";
                    }
                });
        }

        clearMuCoordinatesCancel.addEventListener("click", closeClearMuCoordinatesModal);
        clearMuCoordinatesConfirm.addEventListener("click", runClearMuCoordinates);
        clearMuCoordinatesModal.addEventListener("click", function (event) {
            if (event.target === clearMuCoordinatesModal) {
                closeClearMuCoordinatesModal();
            }
        });

        function openClearMuSiteModal(subject, unit, button) {
            const mu = muTrailerFromSubject(subject, unit);
            if (!mu) {
                notifyError("Could not determine MU trailer from this project subject.");
                return;
            }
            clearMuSiteSubject = subject || "";
            clearMuSiteUnit = unit || "";
            clearMuSiteMu = mu;
            clearMuSiteButton = button || null;
            clearMuSiteMessage.textContent =
                "Remove Site link on ERP Component SC-" + mu + "?";
            clearMuSiteModal.classList.add("is-open");
            clearMuSiteCancel.focus();
        }

        function closeClearMuSiteModal() {
            clearMuSiteModal.classList.remove("is-open");
            clearMuSiteSubject = "";
            clearMuSiteUnit = "";
            clearMuSiteMu = "";
            if (clearMuSiteButton) {
                clearMuSiteButton.disabled = false;
                clearMuSiteButton.textContent = "Clear MU Site";
            }
            clearMuSiteButton = null;
        }

        function runClearMuSite() {
            const subject = clearMuSiteSubject;
            const unit = clearMuSiteUnit;
            const mu = clearMuSiteMu;
            const button = clearMuSiteButton;
            closeClearMuSiteModal();
            if (button) {
                button.disabled = true;
                button.textContent = "Clearing...";
            }
            statusEl.textContent = "Clearing MU site link for " + mu + "...";
            fetch("/issues/clear-mu-site", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    subject: subject,
                    unit: unit,
                    mu: mu,
                }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const line =
                        "Clear MU site — "
                        + (data.component || ("SC-" + mu))
                        + ": "
                        + (data.old_site || "(empty)")
                        + " -> "
                        + (data.site || "(empty)")
                        + (data.unchanged ? " (unchanged)" : "");
                    consoleLines.push(line);
                    renderConsole(true);
                    statusEl.textContent = data.unchanged
                        ? "MU site link already empty for " + (data.mu || mu) + "."
                        : "MU site link cleared for " + (data.mu || mu) + ".";
                })
                .catch(function (error) {
                    const message = "Clear MU site failed: " + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    if (button) {
                        button.disabled = false;
                        button.textContent = "Clear MU Site";
                    }
                });
        }

        clearMuSiteCancel.addEventListener("click", closeClearMuSiteModal);
        clearMuSiteConfirm.addEventListener("click", runClearMuSite);
        clearMuSiteModal.addEventListener("click", function (event) {
            if (event.target === clearMuSiteModal) {
                closeClearMuSiteModal();
            }
        });

        function closeCreateRefurbishModal() {
            createRefurbishModal.classList.remove("is-open");
            createRefurbishSubject = "";
            createRefurbishUnit = "";
            createRefurbishList.innerHTML = "";
            if (createRefurbishButton) {
                createRefurbishButton.disabled = false;
                createRefurbishButton.textContent = "Create Refurbish Projects";
            }
            createRefurbishButton = null;
        }

        function openCreateRefurbishModal(preview, subject, unit, button) {
            createRefurbishSubject = subject || "";
            createRefurbishUnit = unit || "";
            createRefurbishButton = button || null;
            const region = preview.region || "?";
            const rd = preview.rd_unit || "?";
            const mu = preview.mu_unit || "";
            createRefurbishMessage.textContent =
                "Region " + region
                + " from Site "
                + (preview.site_name || preview.site_id || "?")
                + ". RD " + rd
                + (mu ? (", MU " + mu) : " (no MU — trailer refurb skipped).");
            createRefurbishList.innerHTML = "";
            (preview.specs || []).forEach(function (spec) {
                const item = document.createElement("li");
                item.textContent =
                    (spec.project_template || "Project")
                    + ": "
                    + (spec.project_name || "");
                createRefurbishList.appendChild(item);
            });
            createRefurbishModal.classList.add("is-open");
            createRefurbishCancel.focus();
        }

        function beginCreateRefurbishProjects(subject, unit, button) {
            if (!subject) {
                notifyError("This project has no subject/title.");
                return;
            }
            if (button) {
                button.disabled = true;
                button.textContent = "Preparing...";
            }
            statusEl.textContent = "Preparing refurbish projects...";
            fetch("/issues/refurbish-projects/preview", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    subject: subject,
                    unit: unit || "",
                }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (preview) {
                    openCreateRefurbishModal(preview, subject, unit, button);
                })
                .catch(function (error) {
                    const message =
                        "Create Refurbish Projects preview failed: "
                        + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    if (button && !createRefurbishModal.classList.contains("is-open")) {
                        button.disabled = false;
                        button.textContent = "Create Refurbish Projects";
                    }
                });
        }

        function runCreateRefurbishProjects() {
            const subject = createRefurbishSubject;
            const unit = createRefurbishUnit;
            const button = createRefurbishButton;
            closeCreateRefurbishModal();
            if (button) {
                button.disabled = true;
                button.textContent = "Creating...";
            }
            statusEl.textContent = "Creating refurbish projects...";
            fetch("/issues/refurbish-projects", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    subject: subject,
                    unit: unit || "",
                }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const projects = data.projects || [];
                    projects.forEach(function (project) {
                        consoleLines.push(
                            "Created Refurbish Project "
                            + (project.project_name || project.project_id || "?")
                        );
                    });
                    (data.errors || []).forEach(function (line) {
                        consoleLines.push("Create Refurbish Projects warning: " + line);
                    });
                    renderConsole(true);
                    statusEl.textContent = projects.length > 1
                        ? ("Created " + projects.length + " refurbish projects.")
                        : ("Created refurbish project " + (data.project_name || "") + ".");
                })
                .catch(function (error) {
                    const message =
                        "Create Refurbish Projects failed: "
                        + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    if (button) {
                        button.disabled = false;
                        button.textContent = "Create Refurbish Projects";
                    }
                });
        }

        createRefurbishCancel.addEventListener("click", closeCreateRefurbishModal);
        createRefurbishConfirm.addEventListener("click", runCreateRefurbishProjects);
        createRefurbishModal.addEventListener("click", function (event) {
            if (event.target === createRefurbishModal) {
                closeCreateRefurbishModal();
            }
        });

        function openSiteActionModal(action, subject, site, button) {
            siteActionKind = action || "";
            siteActionSubject = subject || "";
            siteActionSiteId = (site && site.site_id) || "";
            siteActionButton = button || null;
            const siteLabel = (site && site.site_name)
                ? (site.site_name + " (" + site.site_id + ")")
                : (siteActionSiteId || "unknown site");
            if (action === "terminate") {
                siteActionTitle.textContent = "Terminate Site?";
                siteActionMessage.textContent =
                    "Set Site " + siteLabel
                    + " status to Inactive and Contract End to today.";
                siteActionConfirm.textContent = "Terminate Site";
            } else {
                siteActionTitle.textContent = "Activate Site?";
                siteActionMessage.textContent =
                    "Set Site " + siteLabel
                    + " status to Active and Contract Start to today.";
                siteActionConfirm.textContent = "Activate Site";
            }
            siteActionModal.classList.add("is-open");
            siteActionCancel.focus();
        }

        function beginSiteAction(action, subject, button) {
            if (!subject) {
                notifyError("This project has no subject/title.");
                return;
            }
            const label = action === "terminate" ? "Terminate Site" : "Activate Site";
            if (button) {
                button.disabled = true;
                button.textContent = "Looking up...";
            }
            statusEl.textContent = "Looking up Site for " + label + "...";
            fetch("/issues/lookup-site", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ subject: subject, action: action }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (site) {
                    openSiteActionModal(action, subject, site, button);
                })
                .catch(function (error) {
                    const message = label + " lookup failed: " + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    if (button && !siteActionModal.classList.contains("is-open")) {
                        button.disabled = false;
                        button.textContent = label;
                    } else if (button) {
                        button.disabled = false;
                        button.textContent = label;
                    }
                });
        }

        function runSiteAction() {
            const action = siteActionKind;
            const subject = siteActionSubject;
            const siteId = siteActionSiteId;
            const button = siteActionButton;
            const endpoint = action === "terminate"
                ? "/issues/terminate-site"
                : "/issues/activate-site";
            const label = action === "terminate" ? "Terminate Site" : "Activate Site";
            closeSiteActionModal();
            if (!action || !subject) {
                return;
            }
            if (button) {
                button.disabled = true;
                button.textContent = "Updating...";
            }
            statusEl.textContent = label + "...";
            fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    subject: subject,
                    site_id: siteId,
                }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const line = action === "terminate"
                        ? (
                            "Terminated Site "
                            + (data.site_name || "")
                            + " (" + (data.site_id || "") + ")"
                            + " — Inactive, contract_end=" + (data.contract_end || "")
                        )
                        : (
                            "Activated Site "
                            + (data.site_name || "")
                            + " (" + (data.site_id || "") + ")"
                            + " — Active, contract_start=" + (data.contract_start || "")
                        );
                    consoleLines.push(line);
                    renderConsole(true);
                    statusEl.textContent = line;
                })
                .catch(function (error) {
                    const message = label + " failed: " + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    if (button) {
                        button.disabled = false;
                        button.textContent = label;
                    }
                });
        }

        siteActionCancel.addEventListener("click", closeSiteActionModal);
        siteActionConfirm.addEventListener("click", runSiteAction);
        siteActionModal.addEventListener("click", function (event) {
            if (event.target === siteActionModal) {
                closeSiteActionModal();
            }
        });

        function closeTechChecksModal() {
            techChecksModal.classList.remove("is-open");
            techChecksProjectId = "";
            techChecksSubject = "";
            techChecksButton = null;
            techChecksTaskList.innerHTML = "";
        }

        function openTechChecksModal(preview, projectId, subject, button) {
            techChecksProjectId = projectId || "";
            techChecksSubject = subject || "";
            techChecksButton = button || null;
            const rain = (preview && preview.raindance) || {};
            techChecksMessage.textContent =
                "Project " + (preview.project_id || projectId || "")
                + " · Unit " + (preview.unit || "")
                + " · Raindance " + (rain.issue_id || "")
                + (rain.subject ? (" (" + rain.subject + ")") : "")
                + ". Complete Tech Checks with PASSED, then Cancel N/A Ganz/Dahua tasks with \""
                + ((preview && preview.cancel_comment) || "n/a 180RD unit")
                + "\" on this project only.";
            techChecksTaskList.innerHTML = "";
            const completeHeader = document.createElement("li");
            completeHeader.textContent = "Complete:";
            completeHeader.style.fontWeight = "600";
            completeHeader.style.listStyle = "none";
            completeHeader.style.marginLeft = "-1.25rem";
            techChecksTaskList.appendChild(completeHeader);
            const subjects = (preview && preview.task_subjects)
                || ((preview && preview.tasks) || []).map(function (t) { return t.subject; });
            subjects.forEach(function (taskSubject) {
                const li = document.createElement("li");
                li.textContent = taskSubject;
                techChecksTaskList.appendChild(li);
            });
            const cancelHeader = document.createElement("li");
            cancelHeader.textContent = "Cancel (n/a 180RD unit):";
            cancelHeader.style.fontWeight = "600";
            cancelHeader.style.listStyle = "none";
            cancelHeader.style.marginLeft = "-1.25rem";
            cancelHeader.style.marginTop = "0.5rem";
            techChecksTaskList.appendChild(cancelHeader);
            const cancelSubjects = (preview && preview.cancel_subjects)
                || ((preview && preview.cancel_tasks) || []).map(function (t) { return t.subject; });
            cancelSubjects.forEach(function (taskSubject) {
                const li = document.createElement("li");
                li.textContent = taskSubject;
                techChecksTaskList.appendChild(li);
            });
            techChecksModal.classList.add("is-open");
            techChecksCancel.focus();
        }

        function beginTechChecks(projectId, subject, button) {
            if (!projectId) {
                notifyError("This project has no project id.");
                return;
            }
            if (!subject) {
                notifyError("This project has no subject/title.");
                return;
            }
            if (button) {
                button.disabled = true;
                button.textContent = "Looking up...";
            }
            statusEl.textContent = "Looking up Tech Checks (180 Unit) for " + projectId + "...";
            fetch("/issues/tech-checks/preview", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    project_id: projectId,
                    subject: subject,
                }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (preview) {
                    openTechChecksModal(preview, projectId, subject, button);
                })
                .catch(function (error) {
                    const message = "Tech Checks (180 Unit) lookup failed: "
                        + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    if (button) {
                        button.disabled = false;
                        button.textContent = "Tech Checks (180 Unit)";
                    }
                });
        }

        function runTechChecks() {
            const projectId = techChecksProjectId;
            const subject = techChecksSubject;
            const button = techChecksButton;
            closeTechChecksModal();
            if (!projectId || !subject) {
                return;
            }
            if (button) {
                button.disabled = true;
                button.textContent = "Updating...";
            }
            statusEl.textContent = "Running Tech Checks (180 Unit) on " + projectId + "...";
            fetch("/issues/tech-checks", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    project_id: projectId,
                    subject: subject,
                }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    const results = data.results || [];
                    results.forEach(function (row) {
                        if (row.ok) {
                            consoleLines.push(
                                "Tech Checks (180) "
                                + (row.task_id || "")
                                + " — "
                                + (row.subject || "")
                                + (row.already_completed ? " (already Completed, commented)" : " Completed")
                            );
                        } else {
                            consoleLines.push(
                                "Tech Checks (180) FAILED "
                                + (row.subject || "")
                                + ": "
                                + (row.error || "unknown error")
                            );
                        }
                    });
                    (data.cancel_results || []).forEach(function (row) {
                        if (row.already_cancelled) {
                            consoleLines.push(
                                "Tech Checks (180) cancel ignored "
                                + (row.task_id || "")
                                + " — "
                                + (row.subject || "")
                                + " (already Cancelled)"
                            );
                        } else if (row.ok) {
                            consoleLines.push(
                                "Tech Checks (180) cancelled "
                                + (row.task_id || "")
                                + " — "
                                + (row.subject || "")
                            );
                        } else {
                            consoleLines.push(
                                "Tech Checks (180) cancel skipped "
                                + (row.subject || "")
                                + ": "
                                + (row.error || "unknown error")
                            );
                        }
                    });
                    renderConsole(true);
                    if (data.partial || data.error) {
                        const message = data.error
                            || "Tech Checks (180 Unit) stopped with a partial failure.";
                        statusEl.textContent = message;
                        notifyError(message);
                        return;
                    }
                    const summary =
                        "Tech Checks (180 Unit) completed on "
                        + (data.project_id || projectId)
                        + " using "
                        + (data.raindance_issue_id || "Raindance")
                        + " ("
                        + results.length
                        + " completed, "
                        + (data.cancel_results || []).length
                        + " cancel targets)";
                    statusEl.textContent = summary;
                    consoleLines.push(summary);
                    renderConsole(true);
                })
                .catch(function (error) {
                    const message = "Tech Checks (180 Unit) failed: "
                        + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                    notifyError(message);
                })
                .finally(function () {
                    if (button) {
                        button.disabled = false;
                        button.textContent = "Tech Checks (180 Unit)";
                    }
                });
        }

        techChecksCancel.addEventListener("click", closeTechChecksModal);
        techChecksConfirm.addEventListener("click", runTechChecks);
        techChecksModal.addEventListener("click", function (event) {
            if (event.target === techChecksModal) {
                closeTechChecksModal();
            }
        });

        function updateTicketCounts() {
            let worked = 0;
            let skipped = 0;
            let total = 0;
            filterableIssueListIds.forEach(function (id) {
                (listState[id] || []).forEach(function (entry) {
                    total += 1;
                    if (entry.worked) {
                        worked += 1;
                    }
                    if (entry.skipped) {
                        skipped += 1;
                    }
                });
            });
            ticketsResolvedEl.textContent = "Tickets resolved today: " + resolvedTodayCount;
            ticketsWorkedEl.textContent = total
                ? "Tickets worked: " + worked + " / " + total
                : "Tickets worked: 0";
            ticketsSkippedEl.textContent = total
                ? "Tickets skipped: " + skipped + " / " + total
                : "Tickets skipped: 0";
            updateListCompleteStatus();
            renderStatsStrip();
        }

        // The stats strip is also a filter. Each chip that maps to a list is a
        // button: click it to narrow to that list, click more to combine.
        // "units down/degraded" clears back to everything. The chips and the
        // Lists dropdown drive the same selection Set, and applyListFilters()
        // re-renders both, so ticking a box lights the matching chip and
        // clicking a chip ticks the matching box.
        // "mid-maintenance" is a unit count, not a list, so it stays inert.
        function renderStatsStrip() {
            if (!statsStripEl) {
                return;
            }
            const interactive = currentPanelMode() === "issues";
            const selected = currentSelectedLists();
            const filtering = filteringEnabled();
            statsStripEl.innerHTML = "";

            let downTotal = 0;
            DOWN_STATS_LISTS.forEach(function (item) {
                downTotal += (listState[item.id] || []).length;
            });

            // clear-the-filter chip, first in the row
            const totalChip = document.createElement(interactive ? "button" : "div");
            totalChip.className = "stats-chip" + (downTotal ? " is-warning" : "");
            totalChip.innerHTML = "<strong>" + downTotal + "</strong> units down/degraded"
                + statsDeltaHtml("__total__", downTotal);
            if (interactive) {
                totalChip.type = "button";
                totalChip.classList.add("is-filter");
                const showingAll = !filtering || selected.size === 0;
                totalChip.classList.toggle("is-active", showingAll);
                totalChip.setAttribute("aria-pressed", showingAll ? "true" : "false");
                totalChip.title = showingAll ? "Showing every list" : "Show every list";
                totalChip.addEventListener("click", function () {
                    setListView(false);
                });
            }
            statsStripEl.appendChild(totalChip);

            DOWN_STATS_LISTS.forEach(function (item) {
                const count = (listState[item.id] || []).length;
                const el = document.createElement(interactive ? "button" : "div");
                el.className = "stats-chip" + (count ? " is-warning" : "");
                el.innerHTML = "<strong>" + count + "</strong> " + item.label
                    + statsDeltaHtml(item.id, count);
                if (interactive) {
                    el.type = "button";
                    const isActive = filtering && selected.has(item.id);
                    const isEmpty = count === 0;
                    el.classList.add("is-filter");
                    el.classList.toggle("is-active", isActive);
                    // Empty lists keep their place so the chips never move
                    // position mid-shift, but cannot be selected.
                    el.classList.toggle("is-empty", isEmpty && !isActive);
                    el.disabled = isEmpty && !isActive;
                    el.setAttribute("aria-pressed", isActive ? "true" : "false");
                    el.title = isEmpty
                        ? item.label + " — no tickets"
                        : (isActive
                            ? "Click to stop showing " + item.label
                            : "Show only " + item.label + " (click more than one to combine)");
                    el.addEventListener("click", function () {
                        if (el.disabled) {
                            return;
                        }
                        // Clicking a chip while "All lists" is active has to
                        // turn filtering on, or nothing would appear to happen.
                        if (!filteringEnabled()) {
                            currentSelectedLists().clear();
                            currentSelectedLists().add(item.id);
                            setListView(true);
                            return;
                        }
                        toggleListFilter(item.id);
                    });
                }
                statsStripEl.appendChild(el);
            });

            const busyChip = document.createElement("div");
            busyChip.className = "stats-chip" + (busyUnitsCount ? " is-warning" : "");
            busyChip.innerHTML = "<strong>" + busyUnitsCount + "</strong> mid-maintenance";
            statsStripEl.appendChild(busyChip);

            const nextStatsCounts = { __total__: downTotal };
            DOWN_STATS_LISTS.forEach(function (item) {
                nextStatsCounts[item.id] = (listState[item.id] || []).length;
            });
            previousStatsCounts = nextStatsCounts;
        }

        // One poll feeds both the mid-maintenance count and the per-row busy
        // flags. (There were briefly two separate 20s polls hitting the same
        // endpoint; this is the single one.)
        function pollBusyUnits() {
            fetch("/issues/busy-units")
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    const units = (data && data.units) || [];
                    busyUnitsCount = units.length;
                    const next = {};
                    units.forEach(function (item) {
                        if (item && item.unit) {
                            next[String(item.unit).toUpperCase()] = item;
                        }
                    });
                    busyUnitsMap = next;
                    document.querySelectorAll("[data-busy-unit]").forEach(applyBusyFlag);
                    renderStatsStrip();
                })
                .catch(function () {})
                .finally(function () {
                    setTimeout(pollBusyUnits, 20000);
                });
        }
        pollBusyUnits();

        // Brings in Worked/Skipped changes made from someone else's browser.
        // Same 20s cadence as pollBusyUnits, same self-rescheduling shape.
        function pollTicketState() {
            fetch("/issues/ticket-state")
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    const nextStates = (data && data.states) || {};
                    const changedLists = new Set();
                    listIds.forEach(function (id) {
                        (listState[id] || []).forEach(function (entry) {
                            if (!entry.issueId) {
                                return;
                            }
                            const shared = nextStates[entry.issueId];
                            const nextWorked = !!(shared && shared.worked);
                            const nextSkipped = !!(shared && shared.skipped);
                            if (entry.worked !== nextWorked || entry.skipped !== nextSkipped) {
                                entry.worked = nextWorked;
                                entry.skipped = nextSkipped;
                                saveEntryState(entry);
                                changedLists.add(id);
                            }
                        });
                    });
                    serverTicketState = nextStates;
                    changedLists.forEach(function (id) {
                        renderList(id);
                    });
                    if (changedLists.size) {
                        updateTicketCounts();
                    }
                })
                .catch(function () {})
                .finally(function () {
                    setTimeout(pollTicketState, 20000);
                });
        }
        pollTicketState();

        function isListComplete(entries) {
            if (!entries || !entries.length) {
                return false;
            }
            if (entries.every(function (entry) { return !!entry.projectId; })) {
                return false;
            }
            return entries.every(function (entry) {
                return entry.worked || entry.skipped;
            });
        }

        function updateListCompleteStatus() {
            listIds.forEach(function (id) {
                setListComplete(id, isListComplete(listState[id] || []));
            });
            setListComplete("discarded_tickets", false);
        }

        function setListComplete(id, complete) {
            const listEl = document.getElementById(id);
            const sectionEl = listEl && listEl.closest(".list-section");
            if (sectionEl) {
                sectionEl.classList.toggle("is-complete", complete);
            }
            listCompleteState[id] = !!complete;
        }

        function listCountText(entries) {
            if (!entries) {
                return "(0)";
            }
            // Projects list has no worked/skipped checkboxes.
            if (entries.length && entries.every(function (entry) { return !!entry.projectId; })) {
                return "(" + entries.length + ")";
            }
            const workedCount = entries.filter(function (entry) { return entry.worked; }).length;
            const skippedCount = entries.filter(function (entry) { return entry.skipped; }).length;
            const summary = "(" + workedCount + " worked, " + skippedCount + " skipped of " + entries.length + ")";
            return isListComplete(entries) ? summary + " Complete" : summary;
        }

        function entryStateKey(entry) {
            return [
                entry.projectId || entry.issueId || entry.ticketSubject || entry.unit,
                entry.unit,
                entry.cameraTarget,
            ].join("::");
        }

        function restoreEntryState(entry, options) {
            const saved = localTicketState[entryStateKey(entry)];
            if (saved) {
                entry.resolved = !!saved.resolved;
                entry.worked = !!saved.worked;
                entry.skipped = !!saved.skipped;
                if (saved.newAcknowledged) {
                    entry.isNew = false;
                }
                if (!(options && options.resetLeds) && saved.validationRunId === validationRunId) {
                    applyLedFields(entry, saved);
                }
            }
            // Worked/Skipped are shared, so whatever the server has for this
            // issue wins over the per-browser cache above — a teammate's click
            // should show up even on a browser that never touched this ticket.
            if (entry.issueId && serverTicketState[entry.issueId]) {
                const shared = serverTicketState[entry.issueId];
                entry.worked = !!shared.worked;
                entry.skipped = !!shared.skipped;
            }
            return entry;
        }

        function applyLedFields(entry, source) {
            if (!entry || !source) {
                return entry;
            }
            if (source.speakerUp === true || source.speakerUp === false) {
                entry.speakerUp = source.speakerUp;
            }
            if (source.cameraUp === true || source.cameraUp === false) {
                entry.cameraUp = source.cameraUp;
            }
            if (source.panelFisheyeUp === true || source.panelFisheyeUp === false) {
                entry.panelFisheyeUp = source.panelFisheyeUp;
            }
            if (source.cameraViewStatus) {
                entry.cameraViewStatus = source.cameraViewStatus;
            }
            if (source.ledStatus) {
                entry.ledStatus = source.ledStatus;
            }
            if (source.fullValidatePriority != null) {
                entry.fullValidatePriority = source.fullValidatePriority;
            }
            return entry;
        }

        function normalizeUnitKey(unit) {
            return String(unit || "").trim().toUpperCase();
        }

        function eachMatchingUnitEntry(unit, fn) {
            const key = normalizeUnitKey(unit);
            const affected = [];
            if (!key) {
                return affected;
            }
            listIds.forEach(function (listId) {
                (listState[listId] || []).forEach(function (entry) {
                    if (normalizeUnitKey(entry.unit) !== key) {
                        return;
                    }
                    fn(entry, listId);
                    if (affected.indexOf(listId) === -1) {
                        affected.push(listId);
                    }
                });
            });
            return affected;
        }

        // Same unit can appear on multiple tickets/lists; keep compute LED (and
        // other unit-level lights) in sync when one occurrence is validated.
        function propagateUnitLedFields(unit, fields, options) {
            const patch = fields || {};
            const skipRender = !!(options && options.skipRender);
            const affected = eachMatchingUnitEntry(unit, function (entry) {
                if (patch.ledStatus) {
                    entry.ledStatus = patch.ledStatus;
                }
                if (patch.computeLabel) {
                    entry.computeLabel = patch.computeLabel;
                }
                if (patch.speakerUp === true || patch.speakerUp === false) {
                    entry.speakerUp = patch.speakerUp;
                }
                if (patch.panelFisheyeUp === true || patch.panelFisheyeUp === false) {
                    entry.panelFisheyeUp = patch.panelFisheyeUp;
                }
                if (patch.cameraViewStatus) {
                    entry.cameraViewStatus = patch.cameraViewStatus;
                }
                if (patch.connectivityKind) {
                    entry.connectivityKind = patch.connectivityKind;
                }
                if (patch.fullValidatePriority != null) {
                    entry.fullValidatePriority = patch.fullValidatePriority;
                }
                saveEntryState(entry);
            });
            if (!skipRender) {
                affected.forEach(function (listId) {
                    renderList(listId);
                });
            }
            return affected;
        }

        function propagateLedFromEntry(entry, options) {
            if (!entry || !entry.unit) {
                return [];
            }
            return propagateUnitLedFields(entry.unit, {
                ledStatus: entry.ledStatus,
                computeLabel: entry.computeLabel,
                speakerUp: entry.speakerUp,
                panelFisheyeUp: entry.panelFisheyeUp,
                cameraViewStatus: entry.cameraViewStatus,
                connectivityKind: entry.connectivityKind,
                fullValidatePriority: entry.fullValidatePriority,
            }, options);
        }

        function collectLiveLedState() {
            const live = {};
            listIds.forEach(function (id) {
                (listState[id] || []).forEach(function (entry) {
                    live[entryStateKey(entry)] = {
                        speakerUp: entry.speakerUp,
                        cameraUp: entry.cameraUp,
                        panelFisheyeUp: entry.panelFisheyeUp,
                        cameraViewStatus: entry.cameraViewStatus,
                        ledStatus: entry.ledStatus,
                        worked: !!entry.worked,
                        skipped: !!entry.skipped,
                        // No server-side field backs this at all (unlike
                        // computeLabel/connectivityKind) — a freshly rebuilt
                        // entry has nothing to read it from, so it MUST come
                        // through this collect/reapply cycle or it silently
                        // resets to the neutral default on every rebuild.
                        fullValidatePriority: entry.fullValidatePriority,
                    };
                });
            });
            return live;
        }

        function dropStaleLedState(runId) {
            Object.keys(localTicketState).forEach(function (key) {
                const saved = localTicketState[key];
                if (!saved || saved.validationRunId === runId) {
                    return;
                }
                delete saved.speakerUp;
                delete saved.cameraUp;
                delete saved.panelFisheyeUp;
                delete saved.cameraViewStatus;
                delete saved.ledStatus;
                delete saved.validationRunId;
            });
            try {
                window.localStorage.setItem(
                    ticketStateStorageKey,
                    JSON.stringify(localTicketState)
                );
            } catch (ignore) {
                // LED state remains in this tab if browser storage is unavailable.
            }
        }

        function saveEntryState(entry) {
            const key = entryStateKey(entry);
            const previous = localTicketState[key] || {};
            localTicketState[key] = {
                resolved: !!entry.resolved,
                worked: !!entry.worked,
                skipped: !!entry.skipped,
                newAcknowledged: !!previous.newAcknowledged || !entry.isNew,
                validationRunId: validationRunId,
                speakerUp: entry.speakerUp,
                cameraUp: entry.cameraUp,
                panelFisheyeUp: entry.panelFisheyeUp,
                cameraViewStatus: entry.cameraViewStatus || null,
                ledStatus: entry.ledStatus || null,
            };
            try {
                window.localStorage.setItem(
                    ticketStateStorageKey,
                    JSON.stringify(localTicketState)
                );
            } catch (ignore) {
                // Checkbox and LED state remain in this tab if browser storage is unavailable.
            }
        }

        // Pushes Worked/Skipped to the server so every other browser looking
        // at this ticket sees the same triage state. Best-effort: a failed
        // push just means this browser's click hasn't reached anyone else yet
        // (it's still applied locally via saveEntryState above), so this
        // stays quiet rather than toasting an error for a background sync.
        function pushTicketState(entry) {
            if (!entry || !entry.issueId) {
                return;
            }
            serverTicketState[entry.issueId] = {
                worked: !!entry.worked,
                skipped: !!entry.skipped,
            };
            fetch("/issues/ticket-state", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    issue_id: entry.issueId,
                    worked: !!entry.worked,
                    skipped: !!entry.skipped,
                    tech: getTechName(),
                    unit: entry.unit || "",
                }),
            }).catch(function () {
                // Offline/unreachable — next pollTicketState() reconciles.
            });
        }

        function makeListEntry(item, options) {
            const isObject = typeof item === "object" && item !== null;
            const entry = {
                unit: isObject ? (item.unit || "") : item,
                issueId: isObject ? (item.issue_id || "") : "",
                projectId: isObject ? (item.project_id || "") : "",
                url: isObject ? (item.url || "") : "",
                outageType: isObject ? (item.outage_type || "") : "",
                issueSubtype: isObject ? (item.issue_subtype || "") : "",
                ticketSubject: isObject ? (item.subject || "") : "",
                siteId: isObject ? (item.site || item.site_id || "") : "",
                undiagnosed: isObject ? !!item.undiagnosed : false,
                switchUrl: isObject ? (item.switch_url || "") : "",
                fisheyeIp: isObject ? (item.fisheye_ip || "") : "",
                pveIp: isObject ? (item.pve_ip || "") : "",
                hasPve: isObject ? !!item.has_pve : false,
                hasRelay: isObject ? !!item.has_relay : false,
                hasPlatform: isObject ? !!item.has_platform : false,
                platformUrl: isObject ? (item.platform_url || "") : "",
                hasScrypted: isObject ? !!item.has_scrypted : false,
                scryptedUrl: isObject ? (item.scrypted_url || "") : "",
                scryptedNvrUrl: isObject ? (item.scrypted_nvr_url || "") : "",
                computeLabel: isObject ? (item.compute_label || "NUC") : "NUC",
                isSpeaker: isObject ? !!item.is_speaker : false,
                isNucDown: isObject
                    ? (!!item.is_nuc_down
                        || item.issue_subtype === "Nuc Down"
                        || /\bS?NUC\s+Down\b/i.test(String(item.subject || "")))
                    : false,
                speakerUp: isObject && item.speaker_up === true
                    ? true
                    : (isObject && item.speaker_up === false ? false : null),
                isCamera: isObject ? !!item.is_camera : false,
                cameraTarget: isObject ? (item.camera_target || "") : "",
                cameraLabel: isObject ? (item.camera_label || "") : "",
                cameraUp: isObject && item.camera_up === true
                    ? true
                    : (isObject && item.camera_up === false ? false : null),
                isPanelIssue: isObject ? !!item.is_panel_issue : false,
                panelFisheyeUp: isObject && item.panel_fisheye_up === true
                    ? true
                    : (isObject && item.panel_fisheye_up === false ? false : null),
                cameraViewStatus: isObject ? (item.camera_view_status || "red") : "red",
                ledStatus: isObject ? (item.led_status || null) : null,
                connectivityKind: isObject ? (item.connectivity_kind || "") : "",
                erpStatus: isObject ? (item.erp_status || "") : "",
                percentComplete: isObject && item.percent_complete != null && item.percent_complete !== ""
                    ? item.percent_complete
                    : null,
                percentCompleteLabel: isObject ? (item.percent_complete_label || "") : "",
                modified: isObject ? (item.modified || "") : "",
                vrmMu: isObject ? (item.vrm_mu || "") : "",
                vrmUrl: isObject ? (item.vrm_url || "") : "",
                holdKind: isObject ? (item.hold_kind || "") : "",
                isNew: isObject ? !!item.is_new : false,
                resolved: false,
                worked: false,
                skipped: false,
            };
            return restoreEntryState(entry, options);
        }

        function sortListEntries(entries, listId) {
            if (!entries) {
                return;
            }
            if (listId && isProjectsList(listId)) {
                entries.sort(function (a, b) {
                    const modifiedCmp = (b.modified || "").localeCompare(a.modified || "");
                    if (modifiedCmp) {
                        return modifiedCmp;
                    }
                    return (a.projectId || "").localeCompare(b.projectId || "");
                });
                return;
            }
            entries.sort(function (a, b) {
                const aPri = (a.fullValidatePriority == null) ? 50 : a.fullValidatePriority;
                const bPri = (b.fullValidatePriority == null) ? 50 : b.fullValidatePriority;
                if (aPri !== bPri) {
                    return aPri - bPri;
                }
                if (a.undiagnosed !== b.undiagnosed) {
                    return a.undiagnosed ? -1 : 1;
                }
                return (a.unit || "").localeCompare(b.unit || "");
            });
        }

        function applyResolvedStats(stats) {
            if (!stats) {
                return;
            }
            teamResolvedIds = new Set(stats.issue_ids || []);
            resolvedTodayCount = stats.count || teamResolvedIds.size || 0;
            updateTicketCounts();
        }

        function isHiddenResolved(entry) {
            const issueId = entry.issueId || entry.issue_id || "";
            return !!(issueId && teamResolvedIds.has(issueId));
        }

        function pruneResolvedEntries() {
            let changed = false;
            listIds.forEach(function (id) {
                const before = listState[id].length;
                listState[id] = listState[id].filter(function (entry) {
                    return !isHiddenResolved(entry);
                });
                if (listState[id].length !== before) {
                    changed = true;
                    renderList(id);
                }
            });
            const discardedBefore = discardedState.length;
            discardedState = discardedState.filter(function (entry) {
                const issueId = entry.issue_id || "";
                return !(issueId && teamResolvedIds.has(issueId));
            });
            if (discardedState.length !== discardedBefore) {
                changed = true;
                renderDiscardedList();
            }
            if (changed) {
                updateTicketCounts();
            }
        }

        function removeIssueFromLists(issueId, entry) {
            if (issueId) {
                teamResolvedIds.add(issueId);
            }
            listIds.forEach(function (id) {
                const before = listState[id].length;
                listState[id] = listState[id].filter(function (item) {
                    if (issueId && item.issueId === issueId) {
                        return false;
                    }
                    return item !== entry;
                });
                if (listState[id].length !== before) {
                    renderList(id);
                }
            });
            discardedState = discardedState.filter(function (item) {
                return !issueId || item.issue_id !== issueId;
            });
            renderDiscardedList();
            updateTicketCounts();
        }

        function markIssueResolved(entry) {
            const issueId = entry.issueId || "";
            entry.resolved = true;
            entry.worked = false;
            entry.skipped = false;
            entry.isNew = false;
            saveEntryState(entry);
            removeIssueFromLists(issueId, entry);
            if (!issueId) {
                return;
            }
            fetch("/issues/resolved", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    issue_id: issueId,
                    tech: getTechName(),
                    unit: entry.unit || "",
                }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    applyResolvedStats(data);
                    pruneResolvedEntries();
                })
                .catch(function (error) {
                    consoleLines.push("Failed to record resolved ticket: " + (error.message || error));
                    renderConsole(true);
                });
        }

        function fillList(id, items, options) {
            const resetLeds = !!(options && options.resetLeds);
            const liveLed = resetLeds ? {} : ((options && options.liveLed) || {});
            listState[id] = (items || []).map(function (item) {
                const entry = makeListEntry(item, { resetLeds: resetLeds });
                const live = liveLed[entryStateKey(entry)];
                if (!resetLeds) {
                    applyLedFields(entry, live);
                }
                if (live) {
                    entry.worked = !!live.worked;
                    entry.skipped = !!live.skipped;
                }
                return entry;
            }).filter(function (entry) {
                return !isHiddenResolved(entry);
            });
            sortListEntries(listState[id], id);
            renderList(id);
            updateTicketCounts();
        }

        function ticketEntryKey(entry) {
            return [
                entry.issueId || "",
                entry.projectId || "",
                entry.unit || "",
                entry.cameraTarget || "",
            ].join("::");
        }

        function applyTicketClassFields(entry, item) {
            if (!entry || !item) {
                return false;
            }
            const nextType = item.outage_type || "";
            const nextSubtype = item.issue_subtype || "";
            const nextUndiagnosed = !!item.undiagnosed;
            const nextSubject = item.subject || entry.ticketSubject || "";
            const nextSite = item.site || item.site_id || entry.siteId || "";
            const changed = (
                entry.outageType !== nextType
                || entry.issueSubtype !== nextSubtype
                || !!entry.undiagnosed !== nextUndiagnosed
                || (item.subject && entry.ticketSubject !== nextSubject)
                || (nextSite && entry.siteId !== nextSite)
            );
            entry.outageType = nextType;
            entry.issueSubtype = nextSubtype;
            entry.undiagnosed = nextUndiagnosed;
            if (item.subject) {
                entry.ticketSubject = item.subject;
            }
            if (nextSite) {
                entry.siteId = nextSite;
            }
            entry.isNucDown = (
                !!item.is_nuc_down
                || nextSubtype === "Nuc Down"
                || /\bS?NUC\s+Down\b/i.test(nextSubject)
            );
            return changed;
        }

        function appendListItems(id, items) {
            const byKey = {};
            listState[id].forEach(function (entry) {
                byKey[ticketEntryKey(entry)] = entry;
            });
            let changed = false;
            (items || []).forEach(function (item) {
                const incoming = makeListEntry(item);
                const key = ticketEntryKey(incoming);
                const existing = byKey[key];
                if (existing) {
                    if (applyTicketClassFields(existing, item)) {
                        changed = true;
                    }
                } else if (!isHiddenResolved(incoming)) {
                    listState[id].push(incoming);
                    byKey[key] = incoming;
                    changed = true;
                }
            });
            if (!changed) {
                return;
            }
            sortListEntries(listState[id], id);
            renderList(id);
            updateTicketCounts();
        }

        function moveEntryToList(entry, fromId, toId) {
            if (toId === "stale_vpn") {
                toId = "truly_down";
            }
            if (!listState[toId]) {
                throw new Error("Unknown validation category: " + toId);
            }
            const moveLed = {
                false_positives: "green",
                nuc_down: "yellow",
                scrypted_outage: "yellow",
                truly_down: "red",
            };
            if (moveLed[toId]) {
                entry.ledStatus = moveLed[toId];
            }
            if (entry.ledStatus) {
                propagateLedFromEntry(entry, { skipRender: true });
            } else {
                saveEntryState(entry);
            }
            if (fromId !== toId) {
                const sourceIndex = listState[fromId].indexOf(entry);
                if (sourceIndex !== -1) {
                    listState[fromId].splice(sourceIndex, 1);
                }
                listState[toId].push(entry);
                sortListEntries(listState[toId], toId);
            }
            const affectedLists = {};
            affectedLists[fromId] = true;
            affectedLists[toId] = true;
            eachMatchingUnitEntry(entry.unit, function (_other, listId) {
                affectedLists[listId] = true;
            });
            Object.keys(affectedLists).forEach(function (listId) {
                renderList(listId);
            });
            updateTicketCounts();
        }

        function applyRevalidateFields(entry, fields) {
            if (!entry || !fields) {
                return;
            }
            if (Object.prototype.hasOwnProperty.call(fields, "speaker_up")) {
                entry.speakerUp = fields.speaker_up === true;
            }
            if (Object.prototype.hasOwnProperty.call(fields, "camera_up")) {
                entry.cameraUp = fields.camera_up === true;
            }
            if (Object.prototype.hasOwnProperty.call(fields, "panel_fisheye_up")) {
                entry.panelFisheyeUp = fields.panel_fisheye_up === true;
            }
            if (fields.camera_view_status) {
                entry.cameraViewStatus = fields.camera_view_status;
            }
            if (fields.led_status) {
                entry.ledStatus = fields.led_status;
            }
            if (fields.hold_kind) {
                entry.holdKind = fields.hold_kind;
            }
            if (fields.compute_label) {
                entry.computeLabel = fields.compute_label;
            }
            propagateLedFromEntry(entry, { skipRender: true });
        }

        function findListEntry(listId, move) {
            return (listState[listId] || []).find(function (entry) {
                return (entry.issueId || "") === (move.issue_id || "")
                    && (entry.unit || "") === (move.unit || "")
                    && (entry.cameraTarget || "") === (move.camera_target || "");
            });
        }

        function applyRevalidationMoves(fromId, moves) {
            const affected = new Set([fromId]);
            (moves || []).forEach(function (move) {
                const entry = findListEntry(fromId, move);
                if (!entry) {
                    return;
                }
                applyRevalidateFields(entry, move.fields);
                if (move.to === "false_positives") {
                    entry.ledStatus = "green";
                    propagateLedFromEntry(entry, { skipRender: true });
                }
                if (move.to && move.to !== fromId && listState[move.to]) {
                    const sourceIndex = listState[fromId].indexOf(entry);
                    if (sourceIndex !== -1) {
                        listState[fromId].splice(sourceIndex, 1);
                    }
                    listState[move.to].push(entry);
                    affected.add(move.to);
                }
                eachMatchingUnitEntry(entry.unit, function (_other, listId) {
                    affected.add(listId);
                });
            });
            affected.forEach(function (id) {
                sortListEntries(listState[id], id);
                renderList(id);
            });
            updateTicketCounts();
        }

        let listRevalidateInFlight = false;

        function revalidateList(listId, btn) {
            if (listRevalidateInFlight) {
                statusEl.textContent = "A list revalidation is already running.";
                return;
            }
            if (!(listState[listId] || []).length) {
                statusEl.textContent = "Nothing to revalidate in "
                    + (listHeadingLabels[listId] || listId) + ".";
                return;
            }
            listRevalidateInFlight = true;
            const label = listHeadingLabels[listId] || listId;
            btn.disabled = true;
            btn.textContent = "Revalidating...";
            statusEl.textContent = "Revalidating " + label + "...";
            fetch("/issues/revalidate-list/" + encodeURIComponent(listId), {
                method: "POST",
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    appendPollLogs(data.logs || []);
                    applyRevalidationMoves(listId, data.moves || []);
                    const moved = data.moved || 0;
                    statusEl.textContent = moved
                        ? "Revalidated " + label + " — " + moved
                            + " ticket" + (moved === 1 ? "" : "s") + " moved."
                        : "Revalidated " + label + " — no list changes.";
                })
                .catch(function (error) {
                    const message = "List revalidation failed: " + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message;
                })
                .finally(function () {
                    listRevalidateInFlight = false;
                    btn.disabled = false;
                    btn.textContent = "Revalidate";
                });
        }

        // A "Camera Outage" ticket whose subject doesn't name a specific
        // camera fans out server-side into one entry per camera on the unit
        // (see work_tool._core's generic camera-outage handling) — same
        // issue_id+unit, different cameraTarget/cameraLabel/cameraUp. Group
        // those back into one row here so one real ticket reads as one row,
        // with a per-camera status strip instead of duplicate rows. The
        // first entry per group (by a stable camera order) becomes the
        // group's representative and carries the rest as cameraGroupMembers.
        const CAMERA_GROUP_ORDER = ["fisheye", "camera1", "camera2", "camera3", "camera4"];
        function groupCameraOutageEntries(entries) {
            const groups = [];
            const byKey = new Map();
            entries.forEach(function (entry) {
                const key = (entry.issueId || entry.ticketSubject || "") + "::" + (entry.unit || "");
                let group = byKey.get(key);
                if (!group) {
                    group = [];
                    byKey.set(key, group);
                    groups.push(group);
                }
                group.push(entry);
            });
            return groups.map(function (group) {
                group.sort(function (a, b) {
                    return CAMERA_GROUP_ORDER.indexOf(a.cameraTarget) - CAMERA_GROUP_ORDER.indexOf(b.cameraTarget);
                });
                const primary = group[0];
                primary.cameraGroupMembers = group;
                return primary;
            });
        }

        // Set Fields (ERP field presets) — hoisted out of renderList so the
        // Power vs Cell Graphs modal's rail can build the same submenu for the
        // ticket it was opened from (renderGraphsDeviceMenu). `id` is the
        // ticket's list id, which picks the presets and the list a preset may
        // move the ticket to. ERP writes: disabled while DISABLE_ERP_WRITES is
        // on (disableErpWriteControl), same as before.
        function appendSetFieldsButton(commandItems, entry, preset, id) {
            const label = preset.label;
            const setFieldsBtn = document.createElement("button");
            setFieldsBtn.type = "button";
            setFieldsBtn.className = "action-btn";
            setFieldsBtn.textContent = label;
            if (!entry.issueId) {
                setFieldsBtn.disabled = true;
                setFieldsBtn.title = "No ERP issue id";
            }
            setFieldsBtn.addEventListener("click", function () {
                if (!entry.issueId || erpWritesDisabled) {
                    return;
                }
                setFieldsBtn.disabled = true;
                setFieldsBtn.textContent = "Setting...";
                fetch(
                    "/issues/set-fields/"
                        + encodeURIComponent(preset.presetId)
                        + "/"
                        + encodeURIComponent(entry.issueId),
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            unit: entry.unit,
                            subject: entry.ticketSubject || "",
                            source_list_id: id,
                        }),
                    }
                )
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || ("HTTP " + response.status));
                            }
                            return data;
                        });
                    })
                    .then(function (data) {
                        const fieldLabels = {
                            issue_type: "Issue Type",
                            issue_subtype: "Issue Subtype",
                            incident_date: "Incident Date",
                            next_followup: "Next Follow-up",
                            working_team: "Working Team",
                            who_is_working: "Who is Working",
                            owner_team: "Owner Team",
                            component: "Component",
                            site: "Site",
                            progress: "Progress",
                            assigned_user_group: "Assigned To User Group",
                        };
                        const setNames = (data.set_fields || []).map(function (name) {
                            return fieldLabels[name] || name;
                        });
                        const skippedNames = (data.skipped || []).map(function (item) {
                            const name = fieldLabels[item.field] || item.field;
                            return name + " (" + (item.reason || "skipped") + ")";
                        });
                        if (Object.prototype.hasOwnProperty.call(data, "outage_type")) {
                            entry.outageType = data.outage_type || "";
                        }
                        if (Object.prototype.hasOwnProperty.call(data, "issue_subtype")) {
                            entry.issueSubtype = data.issue_subtype || "";
                        }
                        if (Object.prototype.hasOwnProperty.call(data, "undiagnosed")) {
                            entry.undiagnosed = !!data.undiagnosed;
                        }
                        const moveTarget = data.move_to_list || preset.moveToList || "";
                        if (moveTarget && moveTarget !== id) {
                            if (moveTarget === "nuc_down") {
                                entry.isNucDown = true;
                                entry.ledStatus = "yellow";
                            } else {
                            entry.cameraViewStatus =
                                entry.cameraViewStatus || entry.ledStatus || "green";
                            entry.ledStatus = entry.cameraViewStatus;
                            }
                            saveEntryState(entry);
                            moveEntryToList(entry, id, moveTarget);
                            consoleLines.push(
                                label + " — moved to "
                                    + (listHeadingLabels[moveTarget] || moveTarget)
                            );
                        } else if (!moveTarget) {
                            renderList(preset.listId || id);
                        }
                        consoleLines.push(
                            label + " " + entry.issueId
                                + (setNames.length ? (" — set " + setNames.join(", ")) : " — nothing new to set")
                        );
                        if (skippedNames.length) {
                            consoleLines.push("Skipped: " + skippedNames.join("; "));
                        }
                        (data.errors || []).forEach(function (line) {
                            if (line) {
                                consoleLines.push(label + " warning: " + line);
                            }
                        });
                        renderConsole(true);
                    })
                    .catch(function (error) {
                        notifyError(label + " failed: " + (error.message || error));
                    })
                    .finally(function () {
                        setFieldsBtn.textContent = label;
                        if (erpWritesDisabled) {
                            disableErpWriteControl(setFieldsBtn);
                        } else {
                            setFieldsBtn.disabled = !entry.issueId;
                            if (!entry.issueId) {
                                setFieldsBtn.title = "No ERP issue id";
                            } else {
                                setFieldsBtn.removeAttribute("title");
                            }
                        }
                    });
            });
            disableErpWriteControl(setFieldsBtn);
            commandItems.appendChild(setFieldsBtn);
        }

        function appendSetFieldsCommandMenu(commandItems, entry, id) {
            const actionListId = (id === "on_hold" && entry.holdKind)
                ? entry.holdKind
                : id;
            const setFieldPresets = [];
            if (!isProjectsList(id) && actionListId === "panel_issues") {
                setFieldPresets.push(
                    {
                        presetId: "dirty_panels",
                        label: "Dirty Panels",
                        listId: "panel_issues",
                    },
                    {
                        presetId: "panels_closed",
                        label: "Panels closed",
                        listId: "panel_issues",
                    }
                );
            }
            if (!isProjectsList(id) && actionListId === "camera_view") {
                setFieldPresets.push(
                    {
                        presetId: "camera_adjustment",
                        label: "Camera Adjustment",
                        listId: "camera_view",
                    },
                    {
                        presetId: "dark_views",
                        label: "Dark Views",
                        listId: "camera_view",
                    },
                    {
                        presetId: "blurry_cameras",
                        label: "Blurry cameras",
                        listId: "camera_view",
                    },
                    {
                        presetId: "dirty_cameras",
                        label: "Dirty Cameras",
                        listId: "camera_view",
                    }
                );
            }
            if (
                !isProjectsList(id)
                && (id === "false_positives" || id === "truly_down")
            ) {
                setFieldPresets.push(
                    {
                        presetId: "weather",
                        label: "Weather",
                        listId: id,
                    },
                    {
                        presetId: "unit_unplugged",
                        label: "Unit Unplugged",
                        listId: id,
                    },
                    {
                        presetId: "recording_drive_error",
                        label: "Recording Drive Error",
                        listId: id,
                    },
                    {
                        presetId: "camera_adjustment",
                        label: "Camera Adjustment",
                        listId: id,
                        moveToList: "camera_view",
                    },
                    {
                        presetId: "dark_views",
                        label: "Dark Views",
                        listId: id,
                        moveToList: "camera_view",
                    },
                    {
                        presetId: "blurry_cameras",
                        label: "Blurry cameras",
                        listId: id,
                        moveToList: "camera_view",
                    },
                    {
                        presetId: "dirty_cameras",
                        label: "Dirty Cameras",
                        listId: id,
                        moveToList: "camera_view",
                    },
                    {
                        presetId: "nuc_down",
                        label: "NUC Down",
                        listId: id,
                        moveToList: "nuc_down",
                    }
                );
            }
            if (
                !isProjectsList(id)
                && id === "nuc_down"
            ) {
                setFieldPresets.push(
                    {
                        presetId: "nuc_down",
                        label: "NUC Down",
                        listId: "nuc_down",
                    },
                    {
                        presetId: "recording_drive_error",
                        label: "Recording Drive Error",
                        listId: id,
                    }
                );
            }
            if (
                !isProjectsList(id)
                && id === "scrypted_outage"
            ) {
                setFieldPresets.push({
                    presetId: "recording_drive_error",
                    label: "Recording Drive Error",
                    listId: id,
                });
            }
            if (setFieldPresets.length) {
                const setFieldsMenu = appendCommandSubmenu(commandItems, "Set Fields");
                setFieldPresets.forEach(function (preset) {
                    appendSetFieldsButton(setFieldsMenu, entry, {
                        presetId: preset.presetId,
                        label: "Set Fields (" + preset.label + ")",
                        listId: preset.listId,
                        moveToList: preset.moveToList || "",
                    }, id);
                });
            }
        }

        function renderList(id) {
            const el = document.getElementById(id);
            const countEl = document.getElementById(id + "_count");
            const entries = listState[id];
            const groupedEntries = id === "camera_outage" ? groupCameraOutageEntries(entries) : entries;
            // New tickets (entry.isNew, set server-side the moment a poll
            // first discovers them) get appended wherever the poll happens
            // to land them — often mid-list, scattered among whatever was
            // already there — not sorted to any particular spot. Stable-
            // sort a render-only copy so new tickets surface at the top
            // (a tech scanning top-down sees what's new first) without
            // disturbing listState's own order, which other code (counts,
            // search, camera grouping) still reads unchanged. Andrew's own
            // report, 2026-10-01.
            const renderEntries = groupedEntries.slice().sort(function (a, b) {
                return (b.isNew ? 1 : 0) - (a.isNew ? 1 : 0);
            });

            countEl.textContent = entries.length ? listCountText(groupedEntries) : "";

            el.innerHTML = "";
            if (!isProjectsList(id)) {
                const legend = document.createElement("li");
                legend.className = "checkbox-legend";
                const legendRws = document.createElement("div");
                legendRws.className = "checkbox-legend-rws";
                [["R", "legend-r"], ["W", "legend-w"], ["S", "legend-s"]].forEach(function (pair) {
                    const mark = document.createElement("span");
                    mark.className = "legend-mark " + pair[1];
                    mark.textContent = pair[0];
                    legendRws.appendChild(mark);
                });
                legend.appendChild(legendRws);
                el.appendChild(legend);
            }

            if (entries.length === 0) {
                const li = document.createElement("li");
                li.className = "empty";
                li.textContent = "None";
                el.appendChild(li);
                applyListFilters();
                setListComplete(id, false);
                return;
            }

            renderEntries.forEach(function (entry) {
                const li = document.createElement("li");
                const classes = ["ticket-row"];
                if (entry.undiagnosed) {
                    classes.push("undiagnosed-row");
                }
                if (entry.resolved) {
                    classes.push("resolved-row");
                }
                if (entry.worked) {
                    classes.push("worked-row");
                }
                if (entry.skipped) {
                    classes.push("skipped-row");
                }
                if (isProjectsList(id)) {
                    classes.push("ticket-row-no-rws");
                }
                li.className = classes.join(" ");
                li.dataset.searchText = [
                    entry.unit,
                    entry.issueId,
                    entry.projectId,
                    entry.erpStatus,
                    entry.percentCompleteLabel,
                    entry.outageType,
                    entry.issueSubtype,
                    entry.ticketSubject,
                ].join(" ").toLowerCase();

                const rowBody = document.createElement("div");
                rowBody.className = "ticket-row-body";
                const rowRws = document.createElement("div");
                rowRws.className = "ticket-row-rws";

                let newBadge = null;
                function refreshRow() {
                    li.classList.toggle("resolved-row", entry.resolved);
                    li.classList.toggle("worked-row", entry.worked);
                    li.classList.toggle("skipped-row", entry.skipped);
                    if (newBadge) {
                        newBadge.hidden = !entry.isNew;
                    }
                    // Camera-outage rows fan out into several entries sharing
                    // one ticket (see groupCameraOutageEntries) — Resolve/
                    // Worked/Skipped apply to the whole ticket, so every
                    // member needs the same state saved, not just the one
                    // this row's checkboxes are bound to.
                    (entry.cameraGroupMembers || [entry]).forEach(function (member) {
                        if (member !== entry) {
                            member.resolved = entry.resolved;
                            member.worked = entry.worked;
                            member.skipped = entry.skipped;
                            member.isNew = entry.isNew;
                        }
                        saveEntryState(member);
                    });
                    countEl.textContent = listCountText(groupedEntries);
                    updateTicketCounts();
                }

                if (!isProjectsList(id)) {
                    const resolveBox = document.createElement("input");
                    resolveBox.type = "checkbox";
                    resolveBox.className = "resolve-box";
                    resolveBox.title = "Mark ticket as resolved (stays in list until Resolve Selected is clicked)";
                    resolveBox.checked = !!entry.resolved;
                    resolveBox.addEventListener("change", function () {
                        entry.resolved = resolveBox.checked;
                        if (entry.resolved) {
                            entry.worked = false;
                            entry.skipped = false;
                            entry.isNew = false;
                            workedBox.checked = false;
                            skipBox.checked = false;
                        }
                        refreshRow();
                        updateResolveSelectedButton();
                    });
                    rowRws.appendChild(resolveBox);

                    const workedBox = document.createElement("input");
                    workedBox.type = "checkbox";
                    workedBox.className = "worked-box";
                    workedBox.title = "Mark ticket as worked";
                    workedBox.checked = !!entry.worked;
                    workedBox.addEventListener("change", function () {
                        entry.worked = workedBox.checked;
                        if (entry.worked) {
                            entry.resolved = false;
                            entry.skipped = false;
                            entry.isNew = false;
                            resolveBox.checked = false;
                            skipBox.checked = false;
                        }
                        refreshRow();
                        updateResolveSelectedButton();
                        pushTicketState(entry);
                    });
                    rowRws.appendChild(workedBox);

                    const skipBox = document.createElement("input");
                    skipBox.type = "checkbox";
                    skipBox.className = "skip-box";
                    skipBox.title = "Mark ticket as skipped";
                    skipBox.checked = !!entry.skipped;
                    skipBox.addEventListener("change", function () {
                        entry.skipped = skipBox.checked;
                        if (entry.skipped) {
                            entry.resolved = false;
                            entry.worked = false;
                            entry.isNew = false;
                            resolveBox.checked = false;
                            workedBox.checked = false;
                        }
                        refreshRow();
                        updateResolveSelectedButton();
                        pushTicketState(entry);
                    });
                    rowRws.appendChild(skipBox);
                }

                let computeLed = null;
                const ledListId = (id === "on_hold" && entry.holdKind) ? entry.holdKind : id;
                if (
                    ledListId === "false_positives"
                    || ledListId === "truly_down"
                    || ledListId === "nuc_down"
                    || ledListId === "scrypted_outage"
                    || ledListId === "camera_view"
                    || isNocProjectsList(ledListId)
                    || (id === "on_hold" && entry.ledStatus)
                ) {
                    computeLed = document.createElement("span");
                    computeLed.className = "speaker-led";
                    if (ledListId === "false_positives") {
                        entry.ledStatus = "green";
                        computeLed.classList.add("is-up");
                        computeLed.title = "Unit is up steady";
                    } else if (entry.ledStatus) {
                        computeLed.classList.toggle("is-up", entry.ledStatus === "green");
                        computeLed.classList.toggle("is-warning", entry.ledStatus === "yellow");
                        computeLed.classList.toggle("is-multi", entry.ledStatus === "orange");
                        computeLed.classList.toggle("is-down", entry.ledStatus === "red");
                        computeLed.title = entry.ledStatus === "green"
                            ? (ledListId === "scrypted_outage"
                                ? "Scrypted is up"
                                : (isNocProjectsList(ledListId)
                                    ? "Project unit is up"
                                    : entry.computeLabel + " is up"))
                            : (entry.ledStatus === "yellow"
                                ? (ledListId === "scrypted_outage"
                                    ? "Scrypted is still unreachable"
                                    : (isNocProjectsList(ledListId)
                                        ? "Project unit has offline compute / Scrypted"
                                        : entry.computeLabel + " is still unreachable"))
                                : (entry.ledStatus === "orange"
                                    ? "Multiple endpoints down"
                                    : (isNocProjectsList(ledListId)
                                        ? "Project unit is down"
                                        : "Unit is down")));
                    } else if (ledListId === "camera_view") {
                        computeLed.classList.toggle("is-up", entry.cameraViewStatus === "green");
                        computeLed.classList.toggle("is-warning", entry.cameraViewStatus === "yellow");
                        computeLed.classList.toggle("is-down", entry.cameraViewStatus === "red");
                        computeLed.title = entry.cameraViewStatus === "green"
                            ? "Router and " + entry.computeLabel + " are reachable"
                            : (entry.cameraViewStatus === "yellow"
                                ? "Router is up and " + entry.computeLabel + " is down"
                                : "Unit is down");
                    } else if (ledListId === "truly_down") {
                        computeLed.classList.add("is-down");
                        computeLed.title = "Unit is fully down";
                    } else if (isNocProjectsList(ledListId)) {
                        computeLed.classList.add("is-warning");
                        computeLed.title = "Project connectivity unknown";
                    } else {
                        computeLed.classList.add("is-warning");
                        computeLed.title = ledListId === "scrypted_outage"
                            ? "Scrypted is offline or needs verification"
                            : entry.computeLabel + " is offline or needs verification";
                    }
                    // Appended to the row itself here; the "rowLed" block
                    // further down also drops a CLONE of whichever LED
                    // applies into the expanded command menu's status row,
                    // so the same status is visible both at a glance on
                    // the row and inside the menu alongside the alarm/
                    // power/shading/dead-panel glyphs.
                    rowBody.appendChild(computeLed);
                }

                let speakerLed = null;
                if (entry.isSpeaker) {
                    speakerLed = document.createElement("span");
                    speakerLed.className = "speaker-led";
                    speakerLed.title = "Speaker status unknown";
                    function updateSpeakerLed() {
                        speakerLed.classList.toggle("is-up", entry.speakerUp === true);
                        speakerLed.classList.toggle("is-down", entry.speakerUp === false);
                        speakerLed.title = entry.speakerUp === true
                            ? "Speaker is up"
                            : (entry.speakerUp === false ? "Speaker is down" : "Speaker status unknown");
                    }
                    updateSpeakerLed();
                    rowBody.appendChild(speakerLed);
                }

                let cameraLed = null;
                const cameraLedByTarget = {};
                if (entry.isCamera) {
                    const cameraMembers = entry.cameraGroupMembers || [entry];
                    cameraMembers.forEach(function (member) {
                        const led = document.createElement("span");
                        led.className = "speaker-led";
                        led.classList.toggle("is-up", member.cameraUp === true);
                        led.classList.toggle("is-down", member.cameraUp === false);
                        led.title = member.cameraUp === true
                            ? member.cameraLabel + " is up"
                            : (member.cameraUp === false
                                ? member.cameraLabel + " is down"
                                : member.cameraLabel + " status unknown");
                        cameraLedByTarget[member.cameraTarget] = led;
                        if (member === entry) {
                            cameraLed = led;
                        }
                        if (cameraMembers.length > 1) {
                            const wrap = document.createElement("span");
                            wrap.className = "camera-strip-item";
                            wrap.title = led.title;
                            wrap.appendChild(led);
                            const ledLabel = document.createElement("span");
                            ledLabel.className = "camera-strip-led-label";
                            ledLabel.textContent = (member.cameraLabel || "").replace("Camera ", "C");
                            wrap.appendChild(ledLabel);
                            rowBody.appendChild(wrap);
                        } else {
                            rowBody.appendChild(led);
                        }
                    });
                }

                let panelLed = null;
                if (entry.isPanelIssue) {
                    panelLed = document.createElement("span");
                    panelLed.className = "speaker-led";
                    panelLed.classList.toggle("is-up", entry.panelFisheyeUp === true);
                    panelLed.classList.toggle("is-down", entry.panelFisheyeUp === false);
                    panelLed.title = entry.panelFisheyeUp === true
                        ? "Fisheye is up"
                        : (entry.panelFisheyeUp === false
                            ? "Fisheye is down"
                            : "Fisheye status unknown");
                    rowBody.appendChild(panelLed);
                }

                appendWeatherIcon(rowBody, entry);

                const label = document.createElement("span");
                label.className = "ticket-label";
                const displayText = entry.ticketSubject || entry.unit || entry.issueId || entry.projectId || "(No subject)";
                if (entry.url) {
                    const link = document.createElement("a");
                    link.href = entry.url;
                    link.target = "_blank";
                    link.rel = "noopener noreferrer";
                    link.textContent = displayText;
                    const titleBits = [entry.unit, entry.issueId || entry.projectId].filter(Boolean);
                    if (titleBits.length) {
                        link.title = titleBits.join(" · ");
                    }
                    label.appendChild(link);
                } else {
                    label.appendChild(document.createTextNode(displayText));
                }
                newBadge = document.createElement("span");
                newBadge.className = "new-ticket-badge";
                newBadge.textContent = " (New!)";
                newBadge.hidden = !entry.isNew;
                label.appendChild(newBadge);

                // Power vs Cell Outage row badge — on every ticket list with
                // a unit, not just the four the fleet sweep covers: it's
                // the way into the graphs modal, and the modal runs the
                // check itself when the sweep has nothing for this unit.
                // One badge per unit the subject names (a multi-unit ticket
                // gets one each, in subject order, each coloured by its own
                // verdict); falls back to entry.unit when the subject doesn't
                // parse.
                //
                // The badge now lives INSIDE the unit button on the left
                // (Andrew's request, 2026-10-03): clicking the unit opens the
                // Power vs Cell modal, where a ticket gets worked; the small
                // ▾ next to it (the command menu, below) is for a quick
                // one-off action. One control per unit instead of a unit pill
                // plus a separate badge in the subject.
                const unitOpenBtns = [];
                if (!isProjectsList(id) && entry.unit) {
                    ticketPowerVsCellUnits(entry).forEach(function (badgeUnit) {
                        const openBtn = document.createElement("button");
                        openBtn.type = "button";
                        openBtn.className = "unit-open-btn";
                        openBtn.dataset.unit = badgeUnit;
                        const powerVsCellBadge = document.createElement("span");
                        powerVsCellBadge.className = "power-vs-cell-row-badge";
                        powerVsCellBadge.dataset.unit = badgeUnit;
                        powerVsCellBadge.hidden = true;
                        const unitText = document.createElement("span");
                        unitText.className = "unit-open-label";
                        unitText.textContent = badgeUnit;
                        // Outage/recovery email still to send — see
                        // applyRowEmailGlyph. Its click opens the ERP
                        // ticket instead of the modal, when there is one.
                        const emailGlyph = document.createElement("span");
                        emailGlyph.className = "unit-email-glyph";
                        emailGlyph.dataset.unit = badgeUnit;
                        emailGlyph.hidden = true;
                        emailGlyph.addEventListener("click", function (event) {
                            const url = emailGlyph.dataset.url;
                            if (!url) {
                                return; // falls through to the button: opens the modal
                            }
                            event.stopPropagation();
                            if (!openBlankTab(url)) {
                                notifyError("Pop-up blocked. Allow pop-ups for this site to open the ticket.");
                            }
                        });
                        applyRowEmailGlyph(emailGlyph);
                        openBtn.appendChild(powerVsCellBadge);
                        openBtn.appendChild(emailGlyph);
                        openBtn.appendChild(unitText);
                        openBtn.addEventListener("click", function (event) {
                            event.stopPropagation();
                            openPowerVsCellRowDetail(
                                badgeUnit, entry.ticketSubject || entry.subject || "", entry.url || "",
                                entry, id
                            );
                        });
                        applyPowerVsCellRowBadge(powerVsCellBadge); // also sets openBtn.title
                        unitOpenBtns.push(openBtn);
                    });
                }

                const metaBits = [];
                if (isProjectsList(id)) {
                    if (isPrepProjectsList(id)) {
                        if (entry.erpStatus) {
                            metaBits.push(entry.erpStatus);
                        }
                    } else if (id === "projects_in_progress") {
                        if (entry.percentCompleteLabel) {
                            metaBits.push(entry.percentCompleteLabel);
                        } else if (entry.erpStatus) {
                            metaBits.push(entry.erpStatus);
                        }
                    } else if (entry.erpStatus) {
                        metaBits.push(entry.erpStatus);
                    }
                }
                if (entry.cameraLabel && (entry.cameraGroupMembers || [entry]).length === 1) {
                    metaBits.push(entry.cameraLabel);
                }
                if (entry.outageType) {
                    metaBits.push(entry.outageType);
                }
                if (entry.undiagnosed) {
                    metaBits.push("UNDIAGNOSED");
                } else if (entry.issueSubtype) {
                    metaBits.push(entry.issueSubtype);
                }
                if (metaBits.length) {
                    label.appendChild(document.createTextNode(" "));
                    const meta = document.createElement("span");
                    meta.className = entry.undiagnosed ? "undiagnosed-badge" : "meta";
                    meta.textContent = "(" + metaBits.join(" · ") + ")";
                    label.appendChild(meta);
                }

                rowBody.appendChild(label);
                appendUnitBusyFlag(rowBody, entry);
                appendQuickActions(rowBody, entry, id);

                const menuParts = createCommandMenuElement(entry, li);
                const commandItems = menuParts.commandItems;
                // Whichever connectivity LED this row built above (at most
                // one applies per row — list type and entry flags are
                // mutually exclusive in practice) already sits on the row
                // itself; a CLONE of it also goes into the expanded menu's
                // status row, alongside the alarm/power/shading/dead-panel
                // glyphs, so the same status is visible both places. A
                // clone is safe here — none of these LEDs carry a click
                // listener, just classes and a title.
                const rowLed = computeLed || speakerLed || cameraLed || panelLed;
                if (rowLed) {
                    const statusRow = commandItems.querySelector(".command-menu-status");
                    if (statusRow) {
                        statusRow.insertBefore(rowLed.cloneNode(true), statusRow.firstChild);
                        statusRow.hidden = false;
                    }
                }
                const actions = document.createElement("div");
                actions.className = "ticket-row-actions";
                if (unitOpenBtns.length) {
                    // Unit button(s) open the modal; the menu shrinks to a ▾
                    // caret (its multi-unit chooser still covers every unit).
                    const split = document.createElement("div");
                    split.className = "unit-split";
                    unitOpenBtns.forEach(function (btn) { split.appendChild(btn); });
                    const caret = menuParts.commandMenu.querySelector("summary");
                    menuParts.commandMenu.classList.add("is-caret");
                    caret.textContent = "";
                    caret.setAttribute("aria-label", "Quick commands for " + (entry.unit || ""));
                    caret.title = "Quick command menu (everything is also in the modal)";
                    split.appendChild(menuParts.commandMenu);
                    actions.appendChild(split);
                } else {
                    actions.appendChild(menuParts.commandMenu);
                }
                li.appendChild(actions);
                li.appendChild(rowBody);
                if (rowRws.childElementCount) {
                    li.appendChild(rowRws);
                }

                const actionListId = (id === "on_hold" && entry.holdKind)
                    ? entry.holdKind
                    : id;

                function appendCommandSubmenu(parent, label) {
                    const submenu = document.createElement("details");
                    submenu.className = "command-submenu";
                    const summary = document.createElement("summary");
                    summary.textContent = label;
                    submenu.appendChild(summary);
                    const items = document.createElement("div");
                    items.className = "command-submenu-items";
                    submenu.appendChild(items);
                    parent.appendChild(submenu);
                    return items;
                }

                if (isPrepProjectsList(id)) {
                    const createBtn = document.createElement("button");
                    createBtn.type = "button";
                    createBtn.className = "action-btn";
                    createBtn.textContent = "Create Deployment Project";
                    if (!entry.projectId) {
                        createBtn.disabled = true;
                        createBtn.title = "No project id";
                    } else {
                        createBtn.addEventListener("click", function () {
                            openCreateDeploymentModal(
                                entry.projectId,
                                entry.ticketSubject || "",
                                createBtn
                            );
                        });
                    }
                    disableErpWriteControl(createBtn);
                    commandItems.appendChild(createBtn);
                    appendCamerasCommandMenu(commandItems, entry);
                    appendDiagnosticsCommandMenu(commandItems, entry);
                    const openMenu = appendCommandSubmenu(commandItems, "Open");
                    appendShieldMenu(openMenu, entry);
                    appendErpMenu(openMenu, entry);
                    appendArtMenu(commandItems, entry);
                    if (entry.unit) {
                        const raindanceBtn = document.createElement("a");
                        raindanceBtn.className = "action-btn";
                        raindanceBtn.href = raindanceBaseUrl
                            + encodeURIComponent(entry.unit);
                        raindanceBtn.target = "_blank";
                        raindanceBtn.rel = "noopener noreferrer";
                        raindanceBtn.textContent = "Open Raindance";
                        openMenu.appendChild(raindanceBtn);

                        const meshBtn = document.createElement("a");
                        meshBtn.className = "action-btn";
                        meshBtn.href = meshBaseUrl
                            + encodeURIComponent(entry.unit);
                        meshBtn.target = "_blank";
                        meshBtn.rel = "noopener noreferrer";
                        meshBtn.textContent = "Open Mesh";
                        openMenu.appendChild(meshBtn);
                    } else {
                        const raindanceBtn = document.createElement("button");
                        raindanceBtn.type = "button";
                        raindanceBtn.className = "action-btn";
                        raindanceBtn.textContent = "Open Raindance";
                        raindanceBtn.disabled = true;
                        raindanceBtn.title = "No unit on this project";
                        openMenu.appendChild(raindanceBtn);

                        const meshBtn = document.createElement("button");
                        meshBtn.type = "button";
                        meshBtn.className = "action-btn";
                        meshBtn.textContent = "Open Mesh";
                        meshBtn.disabled = true;
                        meshBtn.title = "No unit on this project";
                        openMenu.appendChild(meshBtn);
                    }
                    appendOpenScryptedButton(openMenu, entry);
                    appendOpenVrmButton(openMenu, entry);
                } else {
                if (id === "termination") {
                    const createTermBtn = document.createElement("button");
                    createTermBtn.type = "button";
                    createTermBtn.className = "action-btn";
                    createTermBtn.textContent = "Create Termination Project";
                    if (!entry.issueId) {
                        createTermBtn.disabled = true;
                        createTermBtn.title = "No ERP issue id";
                    } else {
                        createTermBtn.addEventListener("click", function () {
                            openCreateTerminationModal(
                                entry.issueId,
                                entry.ticketSubject || "",
                                createTermBtn
                            );
                        });
                    }
                    disableErpWriteControl(createTermBtn);
                    commandItems.appendChild(createTermBtn);
                }
                if (id === "relocation") {
                    const createRelocBtn = document.createElement("button");
                    createRelocBtn.type = "button";
                    createRelocBtn.className = "action-btn";
                    createRelocBtn.textContent = "Create Relocation Project";
                    if (!entry.issueId) {
                        createRelocBtn.disabled = true;
                        createRelocBtn.title = "No ERP issue id";
                    } else {
                        createRelocBtn.addEventListener("click", function () {
                            openCreateRelocationModal(
                                entry.issueId,
                                entry.ticketSubject || "",
                                createRelocBtn
                            );
                        });
                    }
                    disableErpWriteControl(createRelocBtn);
                    commandItems.appendChild(createRelocBtn);
                }
                const cliActionId = isNocProjectsList(id)
                    ? (entry.connectivityKind || "truly_down")
                    : actionListId;
                const cliMenu = appendCommandSubmenu(commandItems, "Validate");

                if (
                    cliActionId === "false_positives"
                    || cliActionId === "truly_down"
                    || cliActionId === "nuc_down"
                    || isNocProjectsList(id)
                ) {
                    function appendValidateButton(label, endpoint, isFull) {
                        const validateBtn = document.createElement("button");
                        validateBtn.type = "button";
                        validateBtn.className = "action-btn";
                        validateBtn.textContent = label;
                        if (!entry.unit) {
                            validateBtn.disabled = true;
                            validateBtn.title = "No unit on this project";
                        }
                        validateBtn.addEventListener("click", function () {
                            if (!entry.unit) {
                                return;
                            }
                            validateBtn.disabled = true;
                            validateBtn.textContent = "Validating...";
                            const quickNucDown = (
                                !isFull
                                && cliActionId === "nuc_down"
                                && entry.isNucDown
                            );
                            const requestUrl = quickNucDown
                                ? ("/issues/ping-compute/"
                                    + encodeURIComponent(entry.unit))
                                : (endpoint + encodeURIComponent(entry.unit));
                            // issue_id/source_list_id let the backend keep
                            // the SHARED job's own copy of this ticket in
                            // sync with whatever Validate just found —
                            // without them, this result only ever updates
                            // this browser's view, and the next shared-state
                            // poll (every ~1s, whenever results change)
                            // silently reverts it back to server truth (see
                            // _sync_shared_validate_result).
                            fetch(requestUrl, {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({
                                    issue_id: entry.issueId || "",
                                    source_list_id: id,
                                }),
                            })
                                .then(function (response) {
                                    return response.json().then(function (data) {
                                        if (!response.ok || !data.ok) {
                                            throw new Error(
                                                data.error || ("HTTP " + response.status)
                                            );
                                        }
                                        return data;
                                    });
                                })
                                .then(function (data) {
                                    if (quickNucDown) {
                                        entry.computeLabel =
                                            data.label || entry.computeLabel;
                                        entry.ledStatus =
                                            data.compute_up === true ? "green" : "yellow";
                                        consoleLines.push(
                                            "Validate (Quick) "
                                                + entry.unit
                                                + " — ping "
                                                + entry.computeLabel
                                                + " only"
                                        );
                                        if (data.output) {
                                            data.output.split(/\r?\n/).forEach(
                                                function (line) {
                                                    if (line) {
                                                        consoleLines.push(line);
                                                    }
                                                }
                                            );
                                        }
                                        consoleLines.push(
                                            entry.computeLabel
                                                + " is "
                                                + (data.compute_up === true
                                                    ? "up"
                                                    : "down")
                                                + ": "
                                                + entry.unit
                                        );
                                        renderConsole(true);
                                        propagateLedFromEntry(entry);
                                        return;
                                    }
                                    if (data.output) {
                                        data.output.split(/\r?\n/).forEach(function (line) {
                                            if (line) {
                                                consoleLines.push(line);
                                            }
                                        });
                                    }
                                    if (isFull) {
                                        entry.ledStatus = data.led_status || entry.ledStatus;
                                        if (
                                            id === "false_positives"
                                            && !(data.move_to)
                                        ) {
                                            entry.ledStatus = "green";
                                        }
                                        entry.computeLabel =
                                            data.compute_label || entry.computeLabel;
                                        entry.fullValidatePriority =
                                            data.sort_priority == null
                                                ? entry.fullValidatePriority
                                                : data.sort_priority;
                                        if (data.speaker_up === true || data.speaker_up === false) {
                                            entry.speakerUp = data.speaker_up;
                                        }
                                        if (data.is_speaker) {
                                            entry.isSpeaker = true;
                                        }
                                        if (data.is_camera) {
                                            entry.isCamera = true;
                                            entry.cameraTarget = data.camera_target || "";
                                            entry.cameraLabel = data.camera_label || "";
                                            entry.cameraUp = data.camera_up === true;
                                        }
                                        if (isNocProjectsList(id)) {
                                            entry.connectivityKind = data.category || "";
                                            consoleLines.push(
                                                "Full validate project "
                                                    + entry.unit
                                                    + " — "
                                                    + (data.led_status || "unknown")
                                                    + (data.multi_down ? " (multi-down)" : "")
                                            );
                                            renderConsole(true);
                                            propagateLedFromEntry(entry);
                                            return;
                                        }
                                        if (entry.isNucDown && (
                                            id === "nuc_down"
                                            || (id === "on_hold" && entry.holdKind === "nuc_down")
                                        )) {
                                            consoleLines.push(
                                                "Full validate "
                                                    + entry.unit
                                                    + " — "
                                                    + (data.led_status || "unknown")
                                                    + " (Nuc Down — staying in offline compute)"
                                            );
                                            renderConsole(true);
                                            propagateLedFromEntry(entry);
                                            return;
                                        }
                                        const moveTo = data.move_to
                                            || (
                                                data.category === "false_positives"
                                                    ? "false_positives"
                                                    : ""
                                            );
                                        if (moveTo && moveTo !== id && listState[moveTo]) {
                                            consoleLines.push(
                                                "Full validate "
                                                    + entry.unit
                                                    + " — moved to "
                                                    + (listHeadingLabels[moveTo] || moveTo)
                                            );
                                            renderConsole(true);
                                            moveEntryToList(entry, id, moveTo);
                                            return;
                                        }
                                        consoleLines.push(
                                            "Full validate "
                                                + entry.unit
                                                + " — "
                                                + (data.led_status || "unknown")
                                                + (data.multi_down ? " (multi-down)" : "")
                                                + " (staying in list)"
                                        );
                                        renderConsole(true);
                                        propagateLedFromEntry(entry);
                                        return;
                                    }

                                    const category = data.category === "stale_vpn"
                                        ? "truly_down"
                                        : (data.category || "false_positives");
                                    const connectivityLed = {
                                        false_positives: "green",
                                        nuc_down: "yellow",
                                        scrypted_outage: "yellow",
                                        truly_down: "red",
                                    };
                                    if (isNocProjectsList(id)) {
                                        entry.connectivityKind = category;
                                        if (connectivityLed[category]) {
                                            entry.ledStatus = connectivityLed[category];
                                        }
                                        consoleLines.push(
                                            "Revalidated project "
                                                + entry.unit
                                                + " — "
                                                + category.replace(/_/g, " ")
                                        );
                                        renderConsole(true);
                                        propagateLedFromEntry(entry);
                                        return;
                                    }
                                    if (id === "on_hold") {
                                        entry.holdKind = category;
                                        if (connectivityLed[category]) {
                                            entry.ledStatus = connectivityLed[category];
                                        }
                                        consoleLines.push(
                                            "Revalidated On Hold "
                                                + entry.unit
                                                + " — "
                                                + category.replace(/_/g, " ")
                                        );
                                        renderConsole(true);
                                        propagateLedFromEntry(entry);
                                        return;
                                    }
                                    if (connectivityLed[category]) {
                                        entry.ledStatus = connectivityLed[category];
                                    }
                                    consoleLines.push(
                                        "Revalidated "
                                            + entry.unit
                                            + " — moved to "
                                            + category.replace(/_/g, " ")
                                    );
                                    renderConsole(true);
                                    moveEntryToList(entry, id, category);
                                })
                                .catch(function (error) {
                                    notifyError(
                                        label + " failed: " + (error.message || error)
                                    );
                                })
                                .finally(function () {
                                    validateBtn.disabled = false;
                                    validateBtn.textContent = label;
                                });
                        });
                        cliMenu.appendChild(validateBtn);
                    }

                    appendValidateButton(
                        "Validate (Quick)",
                        "/issues/validate-unit/",
                        false
                    );
                    appendValidateButton(
                        "Validate (Full)",
                        "/issues/validate-unit-full/",
                        true
                    );
                }

                appendWeatherCommandMenu(commandItems, entry);
                appendRouterCommandMenu(commandItems, entry);
                appendCamerasCommandMenu(commandItems, entry);
                    appendDiagnosticsCommandMenu(commandItems, entry);

                const openMenu = appendCommandSubmenu(commandItems, "Open");
                appendShieldMenu(openMenu, entry);
                appendErpMenu(openMenu, entry);
                appendArtMenu(commandItems, entry);

                if (entry.unit) {
                    const meshBtn = document.createElement("a");
                    meshBtn.className = "action-btn";
                    meshBtn.href = meshBaseUrl
                        + encodeURIComponent(entry.unit);
                    meshBtn.target = "_blank";
                    meshBtn.rel = "noopener noreferrer";
                    meshBtn.textContent = "Open Mesh";
                    openMenu.appendChild(meshBtn);
                } else {
                    const meshBtn = document.createElement("button");
                    meshBtn.type = "button";
                    meshBtn.className = "action-btn";
                    meshBtn.textContent = "Open Mesh";
                    meshBtn.disabled = true;
                    meshBtn.title = "No unit on this ticket";
                    openMenu.appendChild(meshBtn);
                }

                if (isNocProjectsList(id)) {
                    if (entry.unit) {
                        const raindanceBtn = document.createElement("a");
                        raindanceBtn.className = "action-btn";
                        raindanceBtn.href = raindanceBaseUrl
                            + encodeURIComponent(entry.unit);
                        raindanceBtn.target = "_blank";
                        raindanceBtn.rel = "noopener noreferrer";
                        raindanceBtn.textContent = "Open Raindance";
                        openMenu.appendChild(raindanceBtn);
                    } else {
                        const raindanceBtn = document.createElement("button");
                        raindanceBtn.type = "button";
                        raindanceBtn.className = "action-btn";
                        raindanceBtn.textContent = "Open Raindance";
                        raindanceBtn.disabled = true;
                        raindanceBtn.title = "No unit on this project";
                        openMenu.appendChild(raindanceBtn);
                    }

                    const showTerminate = isTerminationProjectSubject(entry.ticketSubject);
                    const showActivate = isDeploymentProjectSubject(entry.ticketSubject);
                    if (showTerminate || showActivate) {
                        const taskMenu = appendCommandSubmenu(commandItems, "Task Controls");
                        if (showTerminate) {
                            const terminateBtn = document.createElement("button");
                            terminateBtn.type = "button";
                            terminateBtn.className = "action-btn";
                            terminateBtn.textContent = "Terminate Site";
                            terminateBtn.addEventListener("click", function () {
                                beginSiteAction(
                                    "terminate",
                                    entry.ticketSubject || "",
                                    terminateBtn
                                );
                            });
                            disableErpWriteControl(terminateBtn);
                            taskMenu.appendChild(terminateBtn);

                            const clearMuBtn = document.createElement("button");
                            clearMuBtn.type = "button";
                            clearMuBtn.className = "action-btn";
                            clearMuBtn.textContent = "Clear MU Coordinates";
                            const trailerMu = muTrailerFromSubject(
                                entry.ticketSubject || "",
                                entry.unit || ""
                            );
                            if (!trailerMu) {
                                clearMuBtn.disabled = true;
                                clearMuBtn.title = "No MU trailer found in project subject";
                            } else {
                                clearMuBtn.title = "Clear coordinates on SC-" + trailerMu;
                                clearMuBtn.addEventListener("click", function () {
                                    openClearMuCoordinatesModal(
                                        entry.ticketSubject || "",
                                        entry.unit || "",
                                        clearMuBtn
                                    );
                                });
                            }
                            disableErpWriteControl(clearMuBtn);
                            taskMenu.appendChild(clearMuBtn);

                            const clearMuSiteBtn = document.createElement("button");
                            clearMuSiteBtn.type = "button";
                            clearMuSiteBtn.className = "action-btn";
                            clearMuSiteBtn.textContent = "Clear MU Site";
                            const trailerMuForSite = muTrailerFromSubject(
                                entry.ticketSubject || "",
                                entry.unit || ""
                            );
                            if (!trailerMuForSite) {
                                clearMuSiteBtn.disabled = true;
                                clearMuSiteBtn.title = "No MU trailer found in project subject";
                            } else {
                                clearMuSiteBtn.title = "Clear Site link on SC-" + trailerMuForSite;
                                clearMuSiteBtn.addEventListener("click", function () {
                                    openClearMuSiteModal(
                                        entry.ticketSubject || "",
                                        entry.unit || "",
                                        clearMuSiteBtn
                                    );
                                });
                            }
                            disableErpWriteControl(clearMuSiteBtn);
                            taskMenu.appendChild(clearMuSiteBtn);

                            const refurbBtn = document.createElement("button");
                            refurbBtn.type = "button";
                            refurbBtn.className = "action-btn";
                            refurbBtn.textContent = "Create Refurbish Projects";
                            refurbBtn.addEventListener("click", function () {
                                beginCreateRefurbishProjects(
                                    entry.ticketSubject || "",
                                    entry.unit || "",
                                    refurbBtn
                                );
                            });
                            disableErpWriteControl(refurbBtn);
                            taskMenu.appendChild(refurbBtn);
                        }
                        if (showActivate) {
                            const activateBtn = document.createElement("button");
                            activateBtn.type = "button";
                            activateBtn.className = "action-btn";
                            activateBtn.textContent = "Activate Site";
                            activateBtn.addEventListener("click", function () {
                                beginSiteAction(
                                    "activate",
                                    entry.ticketSubject || "",
                                    activateBtn
                                );
                            });
                            disableErpWriteControl(activateBtn);
                            taskMenu.appendChild(activateBtn);

                            const techChecksBtn = document.createElement("button");
                            techChecksBtn.type = "button";
                            techChecksBtn.className = "action-btn";
                            techChecksBtn.textContent = "Tech Checks (180 Unit)";
                            techChecksBtn.addEventListener("click", function () {
                                beginTechChecks(
                                    entry.projectId || "",
                                    entry.ticketSubject || "",
                                    techChecksBtn
                                );
                            });
                            disableErpWriteControl(techChecksBtn);
                            taskMenu.appendChild(techChecksBtn);
                        }
                    }
                }

                if (entry.switchUrl) {
                    const switchBtn = document.createElement("a");
                    switchBtn.className = "action-btn";
                    switchBtn.href = "/issues/switch/" + encodeURIComponent(entry.unit);
                    switchBtn.target = "_blank";
                    switchBtn.rel = "noopener noreferrer";
                    switchBtn.textContent = "Open Switch";
                    openMenu.appendChild(switchBtn);
                } else {
                    const switchBtn = document.createElement("button");
                    switchBtn.type = "button";
                    switchBtn.className = "action-btn";
                    switchBtn.textContent = "Open Switch";
                    switchBtn.disabled = true;
                    switchBtn.title = "No switch IP in net sheet";
                    openMenu.appendChild(switchBtn);
                }

                if (entry.unit) {
                    const routerBtn = document.createElement("a");
                    routerBtn.className = "action-btn";
                    routerBtn.href = "/issues/router/" + encodeURIComponent(entry.unit);
                    routerBtn.target = "_blank";
                    routerBtn.rel = "noopener noreferrer";
                    routerBtn.textContent = "Open Router";
                    openMenu.appendChild(routerBtn);
                }

                if (entry.hasPve) {
                    const pveBtn = document.createElement("a");
                    pveBtn.className = "action-btn";
                    pveBtn.href = "/issues/pve/" + encodeURIComponent(entry.unit);
                    pveBtn.target = "_blank";
                    pveBtn.rel = "noopener noreferrer";
                    pveBtn.textContent = "Open PVE";
                    openMenu.appendChild(pveBtn);
                }

                if (entry.hasPlatform) {
                    if (entry.platformUrl) {
                        const platformBtn = document.createElement("a");
                        platformBtn.className = "action-btn";
                        platformBtn.href = entry.platformUrl;
                        platformBtn.target = "_blank";
                        platformBtn.rel = "noopener noreferrer";
                        platformBtn.textContent = "Open Platform";
                        openMenu.appendChild(platformBtn);
                    } else {
                        const platformBtn = document.createElement("button");
                        platformBtn.type = "button";
                        platformBtn.className = "action-btn";
                        platformBtn.textContent = "Open Platform";
                        platformBtn.disabled = true;
                        platformBtn.title = "No Scrypted IP in net sheet";
                        openMenu.appendChild(platformBtn);
                    }
                }

                if (entry.hasRelay) {
                    const relayBtn = document.createElement("a");
                    relayBtn.className = "action-btn";
                    relayBtn.href = "/issues/relay/" + encodeURIComponent(entry.unit);
                    relayBtn.target = "_blank";
                    relayBtn.rel = "noopener noreferrer";
                    relayBtn.textContent = "Open Relay";
                    openMenu.appendChild(relayBtn);
                }

                appendOpenScryptedButton(openMenu, entry);
                appendOpenVrmButton(openMenu, entry);

                function appendBounceButton(label, endpoint, parentMenu, confirmMessage) {
                    const bounceBtn = document.createElement("button");
                    bounceBtn.type = "button";
                    bounceBtn.className = "action-btn";
                    bounceBtn.textContent = label;
                    bounceBtn.addEventListener("click", function () {
                        if (confirmMessage) {
                            openGenericConfirmModal(label + "?", confirmMessage, label, function () {
                                executeBounceAction(entry.unit, label, endpoint, bounceBtn);
                            });
                            return;
                        }
                        executeBounceAction(entry.unit, label, endpoint, bounceBtn);
                    });
                    (parentMenu || cliMenu).appendChild(bounceBtn);
                }

                if (bounceSwitchListIds.has(id)) {
                    const switchMenu = appendCommandSubmenu(commandItems, "Switch");
                    appendBounceButton(
                        "Bounce (Relay)",
                        "/issues/bounce-switch/",
                        switchMenu,
                        "This will bounce the relay/switch for " + entry.unit + ". Continue?"
                    );

                    const uptimeBtn = document.createElement("button");
                    uptimeBtn.type = "button";
                    uptimeBtn.className = "action-btn";
                    uptimeBtn.textContent = "Switch Uptime";
                    if (!entry.unit) {
                        uptimeBtn.disabled = true;
                        uptimeBtn.title = "No unit on this ticket";
                    }
                    uptimeBtn.addEventListener("click", function () {
                        if (!entry.unit) {
                            return;
                        }
                        uptimeBtn.disabled = true;
                        uptimeBtn.textContent = "Checking...";
                        statusEl.textContent =
                            "Checking switch uptime for " + entry.unit + "...";
                        fetch(
                            "/issues/robofiber-uptime/"
                                + encodeURIComponent(entry.unit),
                            { method: "POST" }
                        )
                            .then(function (response) {
                                return response.json().then(function (data) {
                                    if (!response.ok || !data.ok) {
                                        throw new Error(
                                            data.error || ("HTTP " + response.status)
                                        );
                                    }
                                    return data;
                                });
                            })
                            .then(function (data) {
                                const header =
                                    "Switch uptime "
                                    + (data.unit || entry.unit)
                                    + (data.ip ? (" (" + data.ip + ")") : "");
                                consoleLines.push(header);
                                (data.lines || []).forEach(function (line) {
                                    if (line) {
                                        consoleLines.push(line);
                                    }
                                });
                                if (!(data.lines || []).length && data.output) {
                                    consoleLines.push(data.output);
                                }
                                renderConsole(true);
                                statusEl.textContent =
                                    data.uptime || data.output || header;
                                applyFreshSwitchUptime(entry.unit, data, commandItems.closest(".command-menu"));
                            })
                            .catch(function (error) {
                                const message =
                                    "Switch Uptime failed: "
                                    + (error.message || error);
                                consoleLines.push(message);
                                renderConsole(true);
                                statusEl.textContent = message;
                                notifyError(message);
                            })
                            .finally(function () {
                                uptimeBtn.disabled = false;
                                uptimeBtn.textContent = "Switch Uptime";
                            });
                    });
                    switchMenu.appendChild(uptimeBtn);

                    function appendRobofiberLogButton(label, endpoint, statusPrefix) {
                        const logBtn = document.createElement("button");
                        logBtn.type = "button";
                        logBtn.className = "action-btn";
                        logBtn.textContent = label;
                        if (!entry.unit) {
                            logBtn.disabled = true;
                            logBtn.title = "No unit on this ticket";
                        }
                        logBtn.addEventListener("click", function () {
                            if (!entry.unit) {
                                return;
                            }
                            logBtn.disabled = true;
                            logBtn.textContent = "Loading...";
                            statusEl.textContent =
                                statusPrefix + " for " + entry.unit + "...";
                            fetch(endpoint + encodeURIComponent(entry.unit), {
                                method: "POST",
                            })
                                .then(function (response) {
                                    return response.json().then(function (data) {
                                        if (!response.ok || !data.ok) {
                                            throw new Error(
                                                data.error || ("HTTP " + response.status)
                                            );
                                        }
                                        return data;
                                    });
                                })
                                .then(function (data) {
                                    const header =
                                        label
                                        + " — "
                                        + (data.unit || entry.unit)
                                        + (data.ip ? (" (" + data.ip + ")") : "")
                                        + (data.count != null
                                            ? (" — " + data.count + " line(s)")
                                            : "");
                                    consoleLines.push(header);
                                    (data.lines || []).forEach(function (line) {
                                        if (line) {
                                            consoleLines.push(line);
                                        }
                                    });
                                    if (!(data.lines || []).length && data.output) {
                                        consoleLines.push(data.output);
                                    }
                                    renderConsole(true);
                                    statusEl.textContent = header;
                                })
                                .catch(function (error) {
                                    const message =
                                        label + " failed: "
                                        + (error.message || error);
                                    consoleLines.push(message);
                                    renderConsole(true);
                                    statusEl.textContent = message;
                                    notifyError(message);
                                })
                                .finally(function () {
                                    logBtn.disabled = false;
                                    logBtn.textContent = label;
                                });
                        });
                        switchMenu.appendChild(logBtn);
                    }

                    appendRobofiberLogButton(
                        "Link Up/Down Events",
                        "/issues/robofiber-logs-link/",
                        "Fetching switch link events"
                    );
                    appendRobofiberLogButton(
                        "Syslog",
                        "/issues/robofiber-logs-month/",
                        "Fetching switch syslog"
                    );
                }

                if (cliActionId === "speaker_outage") {
                    appendBounceButton(
                        "Bounce Speaker",
                        "/issues/bounce-speaker/",
                        undefined,
                        "This will power-cycle the speaker on " + entry.unit + ", interrupting audio briefly. Continue?"
                    );
                }


                appendSetFieldsCommandMenu(commandItems, entry, id);

                if (
                    id !== "discarded_tickets"
                    && entry.unit
                    && (unitSupportsLinux(entry) || unitSupportsNucReboot(entry))
                    && (
                        !isProjectsList(id)
                        || (
                            isNocProjectsList(id)
                            && (
                                isDeploymentProjectSubject(entry.ticketSubject)
                                || isRelocationProjectSubject(entry.ticketSubject)
                            )
                        )
                    )
                ) {
                    appendLinuxCommandMenus(commandItems, entry);
                }

                if (cliActionId === "nuc_down") {
                    const pingComputeBtn = document.createElement("button");
                    pingComputeBtn.type = "button";
                    pingComputeBtn.className = "action-btn";
                    pingComputeBtn.textContent = "Ping " + entry.computeLabel;
                    pingComputeBtn.addEventListener("click", function () {
                        pingComputeBtn.disabled = true;
                        pingComputeBtn.textContent = "Pinging...";
                        fetch("/issues/ping-compute/" + encodeURIComponent(entry.unit), {
                            method: "POST",
                        })
                            .then(function (response) {
                                return response.json().then(function (data) {
                                    if (!response.ok || !data.ok) {
                                        throw new Error(data.error || ("HTTP " + response.status));
                                    }
                                    return data;
                                });
                            })
                            .then(function (data) {
                                entry.computeLabel = data.label || entry.computeLabel;
                                entry.ledStatus = data.compute_up === true ? "green" : "yellow";
                                pingComputeBtn.textContent = "Ping " + entry.computeLabel;
                                if (computeLed) {
                                    computeLed.classList.toggle("is-up", data.compute_up === true);
                                    computeLed.classList.toggle("is-warning", data.compute_up !== true);
                                    computeLed.title = data.compute_up === true
                                        ? entry.computeLabel + " is up"
                                        : entry.computeLabel + " is still unreachable";
                                }
                                saveEntryState(entry);
                                consoleLines.push(
                                    "Checking " + entry.unit + "'s " + entry.computeLabel + "..."
                                );
                                if (data.output) {
                                    data.output.split(/\r?\n/).forEach(function (line) {
                                        if (line) {
                                            consoleLines.push(line);
                                        }
                                    });
                                }
                                consoleLines.push(
                                    entry.computeLabel
                                        + " is "
                                        + (data.compute_up === true ? "up" : "down")
                                        + ": "
                                        + entry.unit
                                );
                                renderConsole(true);
                            })
                            .catch(function (error) {
                                notifyError("Compute ping failed: " + (error.message || error));
                            })
                            .finally(function () {
                                pingComputeBtn.disabled = false;
                                if (pingComputeBtn.textContent === "Pinging...") {
                                    pingComputeBtn.textContent = "Ping " + entry.computeLabel;
                                }
                            });
                    });
                    cliMenu.appendChild(pingComputeBtn);
                }

                if (cliActionId === "scrypted_outage") {
                    const pingScryptedBtn = document.createElement("button");
                    pingScryptedBtn.type = "button";
                    pingScryptedBtn.className = "action-btn";
                    pingScryptedBtn.textContent = "Ping Scrypted";
                    pingScryptedBtn.addEventListener("click", function () {
                        pingScryptedBtn.disabled = true;
                        pingScryptedBtn.textContent = "Pinging...";
                        fetch("/issues/ping-scrypted/" + encodeURIComponent(entry.unit), {
                            method: "POST",
                        })
                            .then(function (response) {
                                return response.json().then(function (data) {
                                    if (!response.ok || !data.ok) {
                                        throw new Error(data.error || ("HTTP " + response.status));
                                    }
                                    return data;
                                });
                            })
                            .then(function (data) {
                                entry.ledStatus = data.scrypted_up === true ? "green" : "yellow";
                                if (computeLed) {
                                    computeLed.classList.toggle("is-up", data.scrypted_up === true);
                                    computeLed.classList.toggle("is-warning", data.scrypted_up !== true);
                                    computeLed.title = data.scrypted_up === true
                                        ? "Scrypted is up"
                                        : "Scrypted is still unreachable";
                                }
                                saveEntryState(entry);
                                consoleLines.push("Checking " + entry.unit + "'s Scrypted...");
                                if (data.output) {
                                    data.output.split(/\r?\n/).forEach(function (line) {
                                        if (line) {
                                            consoleLines.push(line);
                                        }
                                    });
                                }
                                consoleLines.push(
                                    "Scrypted is "
                                        + (data.scrypted_up === true ? "up" : "down")
                                        + ": "
                                        + entry.unit
                                );
                                renderConsole(true);
                            })
                            .catch(function (error) {
                                notifyError("Scrypted ping failed: " + (error.message || error));
                            })
                            .finally(function () {
                                pingScryptedBtn.disabled = false;
                                pingScryptedBtn.textContent = "Ping Scrypted";
                            });
                    });
                    cliMenu.appendChild(pingScryptedBtn);

                    if (entry.pveIp) {
                        const pingPveBtn = document.createElement("button");
                        pingPveBtn.type = "button";
                        pingPveBtn.className = "action-btn";
                        pingPveBtn.textContent = "Ping PVE";
                        pingPveBtn.addEventListener("click", function () {
                            pingPveBtn.disabled = true;
                            pingPveBtn.textContent = "Pinging...";
                            fetch("/issues/ping-pve/" + encodeURIComponent(entry.unit), {
                                method: "POST",
                            })
                                .then(function (response) {
                                    return response.json().then(function (data) {
                                        if (!response.ok || !data.ok) {
                                            throw new Error(data.error || ("HTTP " + response.status));
                                        }
                                        return data;
                                    });
                                })
                                .then(function (data) {
                                    consoleLines.push("Checking " + entry.unit + "'s PVE...");
                                    if (data.output) {
                                        data.output.split(/\r?\n/).forEach(function (line) {
                                            if (line) {
                                                consoleLines.push(line);
                                            }
                                        });
                                    }
                                    consoleLines.push(
                                        "PVE is "
                                            + (data.pve_up === true ? "up" : "down")
                                            + ": "
                                            + entry.unit
                                    );
                                    renderConsole(true);
                                })
                                .catch(function (error) {
                                    notifyError("PVE ping failed: " + (error.message || error));
                                })
                                .finally(function () {
                                    pingPveBtn.disabled = false;
                                    pingPveBtn.textContent = "Ping PVE";
                                });
                        });
                        cliMenu.appendChild(pingPveBtn);
                    } else {
                        const pingPveBtn = document.createElement("button");
                        pingPveBtn.type = "button";
                        pingPveBtn.className = "action-btn";
                        pingPveBtn.textContent = "Ping PVE";
                        pingPveBtn.disabled = true;
                        pingPveBtn.title = "No PVE IP in net sheet";
                        cliMenu.appendChild(pingPveBtn);
                    }
                }

                if (cliActionId === "camera_view") {
                    const validateCameraViewBtn = document.createElement("button");
                    validateCameraViewBtn.type = "button";
                    validateCameraViewBtn.className = "action-btn";
                    validateCameraViewBtn.textContent = "Validate";
                    validateCameraViewBtn.addEventListener("click", function () {
                        validateCameraViewBtn.disabled = true;
                        validateCameraViewBtn.textContent = "Validating...";
                        fetch("/issues/validate-camera-view/" + encodeURIComponent(entry.unit), {
                            method: "POST",
                        })
                            .then(function (response) {
                                return response.json().then(function (data) {
                                    if (!response.ok || !data.ok) {
                                        throw new Error(data.error || ("HTTP " + response.status));
                                    }
                                    return data;
                                });
                            })
                            .then(function (data) {
                                entry.cameraViewStatus = data.status;
                                entry.computeLabel = data.compute_label || entry.computeLabel;
                                entry.ledStatus = data.status;
                                consoleLines.push("Checking " + entry.unit + "'s router...");
                                if (data.router_output) {
                                    data.router_output.split(/\r?\n/).forEach(function (line) {
                                        if (line) {
                                            consoleLines.push(line);
                                        }
                                    });
                                }
                                consoleLines.push(
                                    "Checking " + entry.unit + "'s " + data.compute_label + "..."
                                );
                                if (data.compute_output) {
                                    data.compute_output.split(/\r?\n/).forEach(function (line) {
                                        if (line) {
                                            consoleLines.push(line);
                                        }
                                    });
                                }
                                consoleLines.push(
                                    "Camera View validation: "
                                        + entry.unit
                                        + " — "
                                        + data.status
                                );
                                renderConsole(true);
                                propagateLedFromEntry(entry);
                            })
                            .catch(function (error) {
                                notifyError("Camera View validation failed: " + (error.message || error));
                            })
                            .finally(function () {
                                validateCameraViewBtn.disabled = false;
                                validateCameraViewBtn.textContent = "Validate";
                            });
                    });
                    cliMenu.appendChild(validateCameraViewBtn);
                }

                if (entry.isSpeaker) {
                    const pingSpeakerBtn = document.createElement("button");
                    pingSpeakerBtn.type = "button";
                    pingSpeakerBtn.className = "action-btn";
                    pingSpeakerBtn.textContent = "Ping Speaker";
                    pingSpeakerBtn.addEventListener("click", function () {
                        pingSpeakerBtn.disabled = true;
                        pingSpeakerBtn.textContent = "Pinging...";
                        fetch("/issues/ping-speaker/" + encodeURIComponent(entry.unit), {
                            method: "POST",
                        })
                            .then(function (response) {
                                return response.json().then(function (data) {
                                    if (!response.ok || !data.ok) {
                                        throw new Error(data.error || ("HTTP " + response.status));
                                    }
                                    return data;
                                });
                            })
                            .then(function (data) {
                                entry.speakerUp = data.speaker_up === true;
                                if (speakerLed) {
                                    speakerLed.classList.toggle("is-up", entry.speakerUp === true);
                                    speakerLed.classList.toggle("is-down", entry.speakerUp === false);
                                    speakerLed.title = entry.speakerUp ? "Speaker is up" : "Speaker is down";
                                }
                                saveEntryState(entry);
                                consoleLines.push("Checking " + entry.unit + "'s speaker...");
                                if (data.output) {
                                    data.output.split(/\r?\n/).forEach(function (line) {
                                        if (line) {
                                            consoleLines.push(line);
                                        }
                                    });
                                }
                                consoleLines.push(
                                    "Speaker is " + (entry.speakerUp ? "up" : "down") + ": " + entry.unit
                                );
                                renderConsole(true);
                            })
                            .catch(function (error) {
                                notifyError("Speaker ping failed: " + (error.message || error));
                            })
                            .finally(function () {
                                pingSpeakerBtn.disabled = false;
                                pingSpeakerBtn.textContent = "Ping Speaker";
                            });
                    });
                    cliMenu.appendChild(pingSpeakerBtn);
                }

                if (entry.isCamera) {
                    // Grouped camera-outage rows (see groupCameraOutageEntries)
                    // need one Ping button per camera in the group, each
                    // updating that camera's own LED in the strip above.
                    const cameraMembersForPing = entry.cameraGroupMembers || [entry];
                    const pingCameraButtons = [];
                    cameraMembersForPing.forEach(function (member) {
                        const pingCameraBtn = document.createElement("button");
                        pingCameraBtn.type = "button";
                        pingCameraBtn.className = "action-btn";
                        const idleLabel = entry.cameraGroupMembers && entry.cameraGroupMembers.length > 1
                            ? "Ping " + member.cameraLabel
                            : "Ping Camera";
                        pingCameraBtn.textContent = idleLabel;
                        pingCameraBtn.addEventListener("click", function () {
                            pingCameraBtn.disabled = true;
                            pingCameraBtn.textContent = "Pinging...";
                            fetch(
                                "/issues/ping-camera/"
                                    + encodeURIComponent(member.unit)
                                    + "/"
                                    + encodeURIComponent(member.cameraTarget),
                                { method: "POST" }
                            )
                                .then(function (response) {
                                    return response.json().then(function (data) {
                                        if (!response.ok || !data.ok) {
                                            throw new Error(data.error || ("HTTP " + response.status));
                                        }
                                        return data;
                                    });
                                })
                                .then(function (data) {
                                    member.cameraUp = data.camera_up === true;
                                    const led = cameraLedByTarget[member.cameraTarget];
                                    if (led) {
                                        led.classList.toggle("is-up", member.cameraUp === true);
                                        led.classList.toggle("is-down", member.cameraUp === false);
                                        led.title = member.cameraLabel
                                            + (member.cameraUp ? " is up" : " is down");
                                    }
                                    saveEntryState(member);
                                    consoleLines.push(
                                        "Checking " + member.unit + "'s " + member.cameraLabel + "..."
                                    );
                                    if (data.output) {
                                        data.output.split(/\r?\n/).forEach(function (line) {
                                            if (line) {
                                                consoleLines.push(line);
                                            }
                                        });
                                    }
                                    consoleLines.push(
                                        member.cameraLabel
                                            + " is "
                                            + (member.cameraUp ? "up" : "down")
                                            + ": "
                                            + member.unit
                                    );
                                    renderConsole(true);
                                })
                                .catch(function (error) {
                                    notifyError("Camera ping failed: " + (error.message || error));
                                })
                                .finally(function () {
                                    pingCameraBtn.disabled = false;
                                    pingCameraBtn.textContent = idleLabel;
                                });
                        });
                        cliMenu.appendChild(pingCameraBtn);
                        pingCameraButtons.push(pingCameraBtn);
                    });
                    if (pingCameraButtons.length > 1) {
                        const pingAllBtn = document.createElement("button");
                        pingAllBtn.type = "button";
                        pingAllBtn.className = "action-btn";
                        pingAllBtn.textContent = "Ping All Cameras";
                        pingAllBtn.title = "Ping every camera on this ticket";
                        pingAllBtn.addEventListener("click", function () {
                            // Reuses each button's own click handler (fetch,
                            // LED update, console lines, busy state) rather
                            // than duplicating it — this just fires all of
                            // them, skipping any already mid-ping.
                            pingCameraButtons.forEach(function (btn) {
                                if (!btn.disabled) {
                                    btn.click();
                                }
                            });
                        });
                        cliMenu.insertBefore(pingAllBtn, pingCameraButtons[0]);
                    }
                }

                if (cliMenu && !cliMenu.children.length && cliMenu.parentElement) {
                    cliMenu.parentElement.remove();
                }

                }

                el.appendChild(li);
            });
            applyListFilters();
            setListComplete(id, isListComplete(entries));
            scheduleTicketWeatherRefresh();
            if (!isProjectsList(id)) {
                updateResolveSelectedButton();
            }
        }

        function renderDiscardedList() {
            const entries = discardedState;
            const el = document.getElementById("discarded_tickets");
            const countEl = document.getElementById("discarded_tickets_count");
            countEl.textContent = "(" + entries.length + ")";
            el.innerHTML = "";
            if (entries.length === 0) {
                const li = document.createElement("li");
                li.className = "empty";
                li.textContent = "None";
                el.appendChild(li);
                applyListFilters();
                return;
            }
            entries.forEach(function (entry) {
                const li = document.createElement("li");
                li.dataset.searchText = [
                    entry.unit || "",
                    entry.issue_id || "",
                    entry.subject || "",
                    entry.reason || "",
                ].join(" ").toLowerCase();
                // Commands button per unit the subject names — the same
                // lazy-loading menu the fleet report rows use, since these
                // entries carry no unit context of their own. Tickets that
                // name no unit ("Test - Ignore") get none.
                const subjectUnits = unitsFromTicketSubject(entry.subject || "");
                if (subjectUnits.length) {
                    li.classList.add("has-commands");
                    const actions = document.createElement("span");
                    actions.className = "discarded-commands";
                    subjectUnits.forEach(function (token) {
                        attachFleetRowCommandMenu(actions, li, token.unit, token.unit, token.unit, entry.subject || "");
                    });
                    li.appendChild(actions);
                }
                if (entry.url) {
                    const link = document.createElement("a");
                    link.href = entry.url;
                    link.target = "_blank";
                    link.rel = "noopener noreferrer";
                    link.textContent = entry.subject || entry.issue_id || "(No subject)";
                    if (entry.issue_id) {
                        link.title = entry.issue_id;
                    }
                    li.appendChild(link);
                    if (entry.is_new) {
                        const newBadge = document.createElement("span");
                        newBadge.className = "new-ticket-badge";
                        newBadge.textContent = " (New!)";
                        li.appendChild(newBadge);
                    }
                } else {
                    li.appendChild(document.createTextNode(entry.subject || "(No subject)"));
                }
                if (entry.reason) {
                    const reason = document.createElement("div");
                    reason.className = "discarded-reason";
                    reason.textContent = entry.reason;
                    li.appendChild(reason);
                }
                el.appendChild(li);
            });
            applyListFilters();
        }

        function fillDiscardedList(items) {
            discardedState = (items || []).filter(function (entry) {
                const issueId = entry.issue_id || "";
                return !(issueId && teamResolvedIds.has(issueId));
            });
            renderDiscardedList();
        }

        function appendDiscardedItems(items) {
            const existingIds = new Set(discardedState.map(function (entry) {
                return entry.issue_id;
            }));
            (items || []).forEach(function (entry) {
                const issueId = entry.issue_id || "";
                if (!existingIds.has(issueId) && !(issueId && teamResolvedIds.has(issueId))) {
                    discardedState.push(entry);
                    existingIds.add(issueId);
                }
            });
            renderDiscardedList();
        }

        function setProgress(current, total, unit) {
            const safeTotal = total || 0;
            const pct = safeTotal > 0 ? Math.min(100, Math.round((current / safeTotal) * 100)) : 0;
            progressFillEl.style.width = pct + "%";
            if (safeTotal === 0) {
                progressLabelEl.textContent = "No units to validate";
                progressFillEl.classList.add("is-complete");
                return;
            }
            if (unit && unit !== "complete" && unit !== "starting") {
                progressLabelEl.textContent = "Validating " + current + " / " + safeTotal + " — " + unit;
            } else if (current >= safeTotal) {
                progressLabelEl.textContent = "Validation complete — " + safeTotal + " / " + safeTotal;
                progressFillEl.classList.add("is-complete");
            } else {
                progressLabelEl.textContent = "Validating " + current + " / " + safeTotal;
            }
            if (current >= safeTotal && safeTotal > 0) {
                progressFillEl.classList.add("is-complete");
            }
        }

        function appendPollLogs(logs) {
            (logs || []).forEach(function (line) {
                const progressMatch = /^__PROGRESS__\s+(\d+)\s+(\d+)\s+(.+)$/.exec(line);
                if (progressMatch) {
                    setProgress(
                        parseInt(progressMatch[1], 10),
                        parseInt(progressMatch[2], 10),
                        progressMatch[3]
                    );
                } else if (line) {
                    consoleLines.push(line);
                }
            });
            renderConsole(true);
        }

        function pullButtonIdleLabel() {
            return currentPanelMode() === "projects" ? "Pull Projects" : "Pull Issues";
        }

        function pullButtonBusyLabel() {
            return currentPanelMode() === "projects" ? "Pulling Projects..." : "Pulling Issues...";
        }

        function setPullErpBusy(busy) {
            if (!pullErpBtn) {
                return;
            }
            pullErpBtn.disabled = !!busy || !initialValidationComplete;
            pullErpBtn.textContent = busy ? pullButtonBusyLabel() : pullButtonIdleLabel();
            if (!busy && initialValidationComplete) {
                pullErpBtn.title = currentPanelMode() === "projects"
                    ? "Refresh Open/In Progress NOC projects from ERP now"
                    : "Refresh Open/Monitoring/On Hold tickets from ERP now";
            }
        }

        function pollForNewIssues(options) {
            const force = !!(options && options.force);
            const manual = !!(options && options.manual);
            const scope = currentPanelMode();
            if (issuePollInFlight) {
                if (manual) {
                    statusEl.textContent = "ERP refresh already in progress.";
                }
                return;
            }
            issuePollInFlight = true;
            if (manual) {
                setPullErpBusy(true);
            }
            statusEl.textContent = scope === "projects"
                ? "Refreshing Open/In Progress NOC projects from ERP..."
                : "Refreshing Open/Monitoring/On Hold issues from ERP...";
            fetch("/issues/poll/" + encodeURIComponent(jobId), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ force: force, manual: manual, scope: scope }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    applyResolvedStats(data.resolved_today);
                    if (data.busy) {
                        statusEl.textContent = "ERP refresh already in progress.";
                        return;
                    }
                    if (data.skipped) {
                        if (data.paused) {
                            statusEl.textContent =
                                "ERP refresh skipped — automated tasks are paused (PAUSE_AUTOMATED_TASKS).";
                        return;
                        }
                        if (!force) {
                            return;
                        }
                    }
                    if (Array.isArray(data.logs) && data.logs.length) {
                        data.logs.forEach(function (line) {
                            if (line) {
                                consoleLines.push(line);
                            }
                        });
                        renderConsole(true);
                    }
                    const r = foldStaleVpnIntoTrulyDown(data.results || {});
                    const resultScope = data.scope || scope;
                    if (data.snapshot) {
                        applyResultsSnapshot(data.snapshot, {
                            liveLed: collectLiveLedState(),
                            scope: resultScope,
                        });
                    } else if (resultScope === "projects") {
                        projectListIds.forEach(function (id) {
                            fillList(id, r[id] || []);
                        });
                    } else {
                        issueListIds.forEach(function (id) {
                            appendListItems(id, r[id] || []);
                        });
                        appendDiscardedItems(r.discarded_tickets || []);
                    }
                    pruneResolvedEntries();
                    if (resultScope === "projects") {
                        const count = data.project_count != null
                            ? data.project_count
                            : projectListIds.reduce(function (sum, id) {
                                return sum + ((r[id] || []).length);
                            }, 0);
                        statusEl.textContent = "ERP project refresh complete — "
                            + count + " project" + (count === 1 ? "" : "s") + ".";
                        return;
                    }
                    const parts = [];
                    if (data.new_count) {
                        parts.push(data.new_count + " new ticket" + (data.new_count === 1 ? "" : "s"));
                    }
                    if (data.removed_count) {
                        parts.push(data.removed_count + " no longer Open/Monitoring/On Hold");
                    }
                    if (data.restored_count) {
                        parts.push(data.restored_count + " re-added from ERP");
                    }
                    if (data.updated_count) {
                        // Covers a changed Issue Type/Subtype AND a changed
                        // Subject — both are treated as "drop and
                        // revalidate fresh" server-side (see
                        // _issue_class_key), since a subject edit can move
                        // a ticket to a different unit/region/list, not
                        // just relabel it.
                        parts.push(
                            data.updated_count + " updated (type/subtype or subject)"
                        );
                    }
                    const fetchedSuffix = data.fetched_count != null
                        ? " (fetched " + data.fetched_count + " from ERP)"
                        : "";
                    statusEl.textContent = parts.length
                        ? "ERP refresh complete — " + parts.join(", ") + fetchedSuffix + "."
                        : "ERP refresh complete — no new tickets" + fetchedSuffix + ".";
                })
                .catch(function (error) {
                    const message = "ERP refresh failed: " + (error.message || error);
                    consoleLines.push(message);
                    renderConsole(true);
                    statusEl.textContent = message + " Retrying in 30 minutes.";
                })
                .finally(function () {
                    issuePollInFlight = false;
                    setPullErpBusy(false);
                });
        }

        function startIssuePolling() {
            // ERP ticket/project pull is a named exception to
            // automationPaused now (2026-09-15) — the server itself
            // already polls every 30 min regardless of an open tab (see
            // _erp_ticket_project_poll_loop), and this client-side timer
            // stays enabled too so a tab left open re-renders on the same
            // cadence rather than only picking up the server's refresh on
            // next reload.
            if (issuePollTimer === null) {
                issuePollTimer = window.setInterval(pollForNewIssues, 30 * 60 * 1000);
            }
        }

        function foldStaleVpnIntoTrulyDown(results) {
            const r = results || {};
            const stale = Array.isArray(r.stale_vpn) ? r.stale_vpn : [];
            if (stale.length) {
                r.truly_down = (r.truly_down || []).concat(stale);
            }
            r.stale_vpn = [];
            return r;
        }

        function applyResultsSnapshot(results, options) {
            const r = foldStaleVpnIntoTrulyDown(results || {});
            const scope = options && options.scope;
            if (!scope || scope === "issues") {
                issueListIds.forEach(function (id) {
                    fillList(id, r[id] || [], options);
                });
                fillDiscardedList(r.discarded_tickets || []);
            }
            if (!scope || scope === "projects") {
                projectListIds.forEach(function (id) {
                    fillList(id, r[id] || [], options);
                });
            } else if (
                Object.prototype.hasOwnProperty.call(r, "projects_open")
                || Object.prototype.hasOwnProperty.call(r, "projects_in_progress")
                || Object.prototype.hasOwnProperty.call(r, "projects_prep")
            ) {
                projectListIds.forEach(function (id) {
                    fillList(id, r[id] || [], options);
                });
            }
            applyPanelMode();
        }

        function handleSharedEvents(events) {
            let latestProgress = null;
            let consoleChanged = false;
            (events || []).forEach(function (event) {
                if (event.type === "progress") {
                    latestProgress = event;
                } else if (event.type === "log") {
                    consoleEchoMuted = true; // server/background lines skip the Graphs Output pane
                    consoleLines.push(event.line);
                    consoleEchoMuted = false;
                    consoleChanged = true;
                    // _run_issues_validation publishes exactly this prefix
                    // when the whole validation run failed (ERP fetch, or
                    // the classification loop itself) and falls back to
                    // empty results — previously that read as a genuinely
                    // clean, empty fleet with nothing but a scrolling
                    // console line to say otherwise. Caught in this
                    // session's own audit, fixing proactively.
                    if (String(event.line || "").indexOf("ERROR:") === 0) {
                        notifyError(event.line);
                    }
                }
            });
            if (latestProgress) {
                setProgress(
                    latestProgress.current || 0,
                    latestProgress.total || 0,
                    latestProgress.unit || ""
                );
            }
            if (consoleChanged) {
                renderConsole(true);
            }
        }

        function pollSharedReportState() {
            if (statePollInFlight) {
                window.setTimeout(pollSharedReportState, 1000);
                return;
            }
            statePollInFlight = true;
            const stateUrl = "/issues/state/" + encodeURIComponent(jobId)
                + "?cursor=" + encodeURIComponent(serverEventCursor)
                + "&version=" + encodeURIComponent(serverVersion);
            fetch(stateUrl)
                .then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok || !data.ok) {
                            throw new Error(data.error || ("HTTP " + response.status));
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    handleSharedEvents(data.events);
                    serverEventCursor = data.cursor || serverEventCursor;
                    applyResolvedStats(data.resolved_today);
                    if (data.results) {
                        const nextRunId = data.validation_run_id || "";
                        const runChanged = !!(
                            validationRunId
                            && nextRunId
                            && nextRunId !== validationRunId
                        );
                        if (nextRunId) {
                            validationRunId = nextRunId;
                        }
                        if (runChanged) {
                            dropStaleLedState(validationRunId);
                        }
                        applyResultsSnapshot(data.results, {
                            resetLeds: runChanged,
                            liveLed: runChanged ? {} : collectLiveLedState(),
                        });
                        if (runChanged && initialValidationComplete) {
                            statusEl.textContent = "Scheduled full validation complete. Status lights refreshed.";
                        }
                    }
                    pruneResolvedEntries();
                    serverVersion = data.version || serverVersion;
                    if (data.done && !initialValidationComplete) {
                        initialValidationComplete = true;
                        pullErpBtn.disabled = false;
                        pullErpBtn.textContent = pullButtonIdleLabel();
                        pullErpBtn.title = currentPanelMode() === "projects"
                            ? "Refresh Open/In Progress NOC projects from ERP now"
                            : "Refresh Open/Monitoring/On Hold tickets from ERP now";
                        statusEl.textContent = "Validation complete. ERP refreshes every 30 minutes.";
                        if (progressFillEl.style.width !== "100%") {
                            setProgress(1, 1, "complete");
                        }
                        startIssuePolling();
                    }
                })
                .catch(function (error) {
                    statusEl.textContent = "Shared report connection failed: "
                        + (error.message || error)
                        + ". Retrying...";
                })
                .finally(function () {
                    statePollInFlight = false;
                    window.setTimeout(pollSharedReportState, 1000);
                });
        }

        // ---- Guided tour --------------------------------------------------
        // Every step is purely visual — no step here clicks a real action
        // button, submits anything, or calls the server (steps that touch
        // the live command-menu structure only ever read/open it, and
        // "opening" a <details> triggers no network call on its own).
        // Steps that need something on screen that's normally hidden
        // (Reports mode, an open command menu, a collapsed section) change
        // exactly that and endTour() restores it — so leaving the tour, at
        // any step, any way (Finish, Skip, Esc, clicking the backdrop),
        // always puts the page back exactly how it was found.
        const TOUR_STEPS = [
            {
                title: "Welcome to the NOC Dashboard",
                body: "A quick tour of what's here. It's look-only — no step runs a check, saves a note, or talks to ERP/VRM/Zabbix. Back/Next or the arrow keys move around; Skip tour or Esc leaves anytime, and nothing you saw stays changed.",
            },
            {
                selector: "#panel_mode",
                title: "Issues / Projects / Reports",
                body: "Three pages, one control. Issues is the live ERP ticket queue, split into categories (False Positives, NUC Down, Truly Down, Camera Outage, ...). Projects is NOC projects (Open / In Progress / Prep). Reports is fleet-wide checks that don't belong to any single ticket — covered near the end of this tour.",
                before: function () { tourSetPanelMode("issues"); },
            },
            {
                selector: "#list_search",
                title: "Search",
                body: "Filters whatever's currently on screen — unit, ticket ID, subject, outage type. Nuance: type a unit that ISN'T in any visible list and Unit Tools (bottom of the page) opens on its own with that unit's full command menu — the fast path to a unit with no open ticket at all.",
            },
            {
                selector: "#list_view_toggle",
                title: "All lists / One list",
                body: "All lists shows every category at once. One list narrows to just the categories ticked in the Select Lists dropdown that appears next to it — for working one category (say, Truly Down) without the rest crowding the page. Nuance: this same toggle works on the Reports page too, narrowing to just the fleet-wide checks worth looking at right now.",
            },
            {
                selector: ".ticket-row-rws",
                title: "Resolved / Worked / Skipped",
                body: "Per-ticket checkboxes on issue rows (projects don't have these). Resolved queues a ticket for removal — nothing happens until Resolve Selected is clicked, so checking it is safe to undo. Worked/Skipped just track what you've triaged this session; they're per-browser, not saved to ERP.",
                before: function () { tourSetPanelMode("issues"); },
            },
            {
                selector: "li.ticket-row .unit-open-btn",
                title: "Open a unit",
                body: "Click a unit's button to open its graphs modal — where you work a ticket: the Power vs Cell verdict, switch uptime, status chips, email status, notes, every command, and the output of what you run. The glyph on the button is that verdict: ⚡ power outage, 📶 cell outage, grey ∿ not determined yet (opening it runs the check). A ticket naming several units gets one button per unit.",
                before: function () { tourSetPanelMode("issues"); },
            },
            {
                selector: "li.ticket-row .command-menu.is-caret summary",
                title: "Quick commands",
                body: "The small ▾ next to it drops the quick command menu right here in the list, for a one-off action without opening the modal. The moment it opens, a status row appears at the top if there's anything worth flagging.",
                before: function () { tourSetPanelMode("issues"); },
            },
            {
                selector: ".command-menu[open] .command-menu-status",
                title: "Status row",
                body: "Up to eight glyphs can appear here, left to right. Alert-only — appear ONLY when there's something to flag, nothing on a clean unit: ⚠ Power & Infra (Zabbix + VRM both flagging this unit — click for detail), 🌳 possible shading, 🔧 possible dead/underperforming panel, 📡 VRM gone stale or disconnected, ⚡/📶 Power vs Cell Outage's own verdict (⚡ power, 📶 cell) for Up Steady units. Shown whenever a reading resolved either way, clean or not: 🔌 AC/shore power status, the colored pill is battery SOC%, ☁ is the 5-day cloud forecast Battery Outlook reads against. The connectivity LED (same one as the row itself) rounds it out. Nuance: most fetch lazily the moment the menu opens and cache 5 minutes; ⚠ and ⚡/📶 instead poll a shared background sweep, so those two can already be lit before you've opened anything.",
                before: function () { tourSetPanelMode("issues"); tourOpenFirstRowMenu(); },
            },
            {
                selector: "#false_positives",
                title: "Up Steady",
                body: "Nuance: a unit's button here shows ⚡ (power) or 📶 (cell) when the background sweep over this list found a verdict — the same Power vs Cell Outage check as the Diagnostics submenu's own, surfaced without opening anything. Click the unit to open the graph the verdict was based on, plus the switch's uptime at the time it was checked. \"Diagnose Up Steady (Cell/Power)\" above the list forces a fresh sweep on demand instead of waiting for the next scheduled one.",
                before: function () { tourSetPanelMode("issues"); },
            },
            {
                submenuLabel: "Validate",
                title: "Validate",
                body: "Quick vs Full — both re-check the unit and, quietly, feed the Flap Report (Reports page): every validation counts toward catching a unit that keeps bouncing between healthy and unhealthy, not just a dedicated flap check.",
                before: function () { tourSetPanelMode("issues"); tourOpenFirstRowMenu(); },
            },
            {
                submenuLabel: "Weather",
                title: "Weather",
                body: "Current conditions and historic weather for the unit's region, plus Battery Outlook — experimental: correlates VRM battery SOC against the multi-day cloud forecast (45% heading into three sunny days reads differently than 45% heading into three cloudy ones).",
                before: function () { tourSetPanelMode("issues"); tourOpenFirstRowMenu(); },
            },
            {
                submenuLabel: "Router",
                title: "Router",
                body: "Carrier lookup (from the SIM ICCID) and ping tools — Quick Validate stops at the first reply, Ping Router always pings 4 times, Long Ping Router runs continuously for up to 30 minutes for watching a flaky link live.",
                before: function () { tourSetPanelMode("issues"); tourOpenFirstRowMenu(); },
            },
            {
                submenuLabel: "Cameras",
                title: "Cameras",
                body: "A fisheye snapshot, or open every configured camera at once — proxied through this dashboard, so there's no separate login per camera, Dahua or Hikvision.",
                before: function () { tourSetPanelMode("issues"); tourOpenFirstRowMenu(); },
            },
            {
                submenuLabel: "Diagnostics",
                title: "Diagnostics",
                body: "Read-only checks, several marked Experimental: Power Status, Shading Status, and a dead-panel check each return a confidence percentage, not a certainty — a lead worth a look, not a verdict. Shading Status can also Schedule a Shading Snapshot: a camera photo timed for the FOLLOWING day's peak hour, only fired after re-confirming the dip is actually happening again. Graphs (nested in here) plots the same solar-power data those checks read.",
                before: function () { tourSetPanelMode("issues"); tourOpenFirstRowMenu(); },
            },
            {
                submenuLabel: "Open",
                title: "Open",
                body: "Direct links out — the ERP/Shield ticket, the unit's ERP site page, and Mesh VPN — always a new tab, never navigating away from the dashboard.",
                before: function () { tourSetPanelMode("issues"); tourOpenFirstRowMenu(); },
            },
            {
                selector: ".command-menu[open] .unit-notes-box",
                title: "Notes & lock",
                body: "Notes here are shared — visible to everyone who opens this unit's menu, not just you. If someone else has a job running on this unit (like the Security Update wizard), a busy banner appears above the notes with who/what and a Force Clear option if it's stuck.",
                before: function () { tourSetPanelMode("issues"); tourOpenFirstRowMenu(); },
            },
            {
                selector: ".quick-actions",
                title: "Quick actions",
                body: "The handful of actions promoted onto the row itself, outside the menu — set once, shown on every ticket, so the single most common action for a row doesn't cost two clicks.",
                before: function () { tourSetPanelMode("issues"); },
            },
            {
                title: "Recent commands",
                body: "Once a few commands have been used, the expanded menu grows a short \"Recent\" strip at the top — a shortcut back to whatever you actually use. It's per-browser, not shared with teammates, and won't show anything on a first visit.",
            },
            {
                selector: "#pull_erp",
                title: "Pull, checkboxes, weather",
                body: "Pull Issues (or Pull Projects, depending on the page) refreshes straight from ERP on demand. Clear checkboxes resets every Resolved/Worked/Skipped box at once. Update Weather refreshes the weather icon on every visible ticket. Resolve Selected finalizes every Resolved-checked ticket in one batch.",
                before: function () { tourSetPanelMode("issues"); },
            },
            {
                selector: "#stats_strip",
                title: "Stats strip",
                body: "A live summary — click a chip to jump straight to that category (it drives the same Select Lists filter as the dropdown, so ticking a box lights the matching chip and vice versa). \"mid-maintenance\" is a plain count, not a filter — it stays inert.",
            },
            {
                selector: "#console",
                title: "Console",
                body: "Shared scrollback for everything run this session — every command's output lands here, capped at 5,000 lines (trimmed in chunks so it doesn't grow forever).",
            },
            {
                selector: "#console_search",
                title: "Console search",
                body: "Filters the console pane itself, separately from the ticket-list search above it — for finding one unit's output in a long session.",
            },
            {
                selector: "#flap_report_section",
                title: "Reports — Flap Report",
                body: "Switching to Reports mode (top-left) brings up seven fleet-wide checks as their own page. Flap Report counts healthy ↔ unhealthy TRANSITIONS, not just failures — what separates a unit that's simply down from one that keeps bouncing.",
                before: function () { tourSetPanelMode("reports"); },
            },
            {
                selector: "#units_unplugged_section",
                title: "Units Unplugged",
                body: "Every VRM installation fleet-wide, checked for AC/shore power — not just units with an open \"unplugged\" ticket. Cached and refreshed on a schedule; \"Check whole fleet now\" forces a fresh pass (a real check per site, so it takes about a minute).",
                before: function () { tourSetPanelMode("reports"); },
            },
            {
                selector: "#shaded_units_section",
                title: "Shaded Units",
                body: "Nuance: only lists units the check actually confirmed shaded — not healthy units, not ones it couldn't reach a verdict on. Each row links straight to the solar-power graph the verdict came from, and can schedule a snapshot individually or for every shaded unit at once.",
                before: function () { tourSetPanelMode("reports"); },
            },
            {
                selector: "#dead_panel_section",
                title: "Dead Panels",
                body: "Same idea as Shaded Units, a different signature: output down roughly EQUALLY across every hour of the day (consistent with hardware) rather than just certain hours (consistent with shading) — the two checks cross-reference that distinction before confirming either verdict.",
                before: function () { tourSetPanelMode("reports"); },
            },
            {
                selector: "#vrm_freshness_section",
                title: "VRM Disconnected",
                body: "How recently every installation last reported to VRM at all — the cheapest of the fleet-wide checks (no per-site call needed). Nuance: a unit here that ALSO has an open issue ticket is pushed to the very top with a \"possibly related ticket\" badge — likely means someone's already on it, or it explains the silence.",
                before: function () { tourSetPanelMode("reports"); },
            },
            {
                selector: "#power_infra_section",
                title: "Power & Infra Alerts",
                body: "Experimental: merges Zabbix's currently-open problems with VRM's own battery alarms, by unit. \"Corroborated\" means both systems agree something's wrong on that unit right now — a stronger signal than either alone.",
                before: function () { tourSetPanelMode("reports"); },
            },
            {
                selector: "#alarm_frequency_section",
                title: "Alarm Frequency",
                body: "Repeat offenders — units whose alarms keep clearing and coming back, not just what's active right now. A unit that flaps 15 times a day is a different problem than one that's been steadily down since this morning, even if neither looks \"currently alarmed\" at any single instant.",
                before: function () { tourSetPanelMode("reports"); },
            },
            {
                selector: "#unit_tools_section",
                title: "Unit Tools",
                body: "The same full command menu as a ticket row, for any unit — no open ticket required. Search a unit above and, if it isn't already visible in a list, this section opens with its menu ready to go.",
                before: function () {
                    tourSetPanelMode("issues");
                    tourShow(document.getElementById("unit_tools_section"));
                },
            },
            {
                title: "That's the tour",
                body: "Everything shown was look-only — nothing was run, saved, or sent anywhere. Click Take a Tour again anytime to replay it, or jump straight in.",
            },
        ];

        let tourActive = false;
        let tourIndex = 0;
        let tourSavedPanelMode = null;
        let tourSavedFiltering = false;
        let tourOpenedMenu = null;
        let tourForcedVisible = [];
        const tourBackdropEl = document.createElement("div");
        tourBackdropEl.className = "tour-backdrop";
        const tourHighlightEl = document.createElement("div");
        tourHighlightEl.className = "tour-highlight is-hidden";
        const tourCalloutEl = document.createElement("div");
        tourCalloutEl.className = "tour-callout";
        tourCalloutEl.setAttribute("role", "dialog");
        tourCalloutEl.setAttribute("aria-label", "Guided tour");

        function tourSetPanelMode(mode) {
            if (!panelModeEl || panelModeEl.value === mode) {
                return;
            }
            panelModeEl.value = mode;
            applyPanelMode();
        }

        function tourShow(el) {
            if (!el) {
                return;
            }
            if (!tourForcedVisible.some(function (item) { return item.el === el; })) {
                tourForcedVisible.push({ el: el, wasHidden: el.hidden });
            }
            el.hidden = false;
        }

        function tourQueryVisible(selector) {
            const matches = document.querySelectorAll(selector);
            for (let i = 0; i < matches.length; i++) {
                if (matches[i].offsetParent !== null) {
                    return matches[i];
                }
            }
            return null;
        }

        function tourOpenFirstRowMenu() {
            const summary = tourQueryVisible("li.ticket-row .command-menu summary");
            if (!summary) {
                return null;
            }
            const menu = summary.closest("details.command-menu");
            if (!menu) {
                return null;
            }
            if (tourOpenedMenu && tourOpenedMenu !== menu) {
                tourOpenedMenu.open = false;
            }
            if (!menu.open) {
                menu.open = true;
                // Setting .open directly doesn't reliably fire the native
                // "toggle" event synchronously — placeCommandMenu is what
                // actually calls updateCommandMenuContext, which is what
                // lazily builds the notes box and a few other status
                // pieces. Without this, a menu opened this way stays
                // structurally empty even though .open is true.
                placeCommandMenu(menu);
            }
            tourOpenedMenu = menu;
            return menu;
        }

        function tourFindSubmenuSummary(label) {
            const summaries = document.querySelectorAll(".command-menu[open] .command-submenu > summary");
            for (let i = 0; i < summaries.length; i++) {
                if (summaries[i].textContent.trim() === label) {
                    return summaries[i];
                }
            }
            return null;
        }

        // undefined = no target at all (a centered, informational step —
        // always shown). null = a real target that isn't there RIGHT NOW
        // (e.g. no ticket rows loaded yet) — the caller skips this step.
        function tourResolveTarget(step) {
            if (step.submenuLabel) {
                return tourFindSubmenuSummary(step.submenuLabel);
            }
            if (step.selector) {
                return tourQueryVisible(step.selector);
            }
            return undefined;
        }

        function tourPositionFor(target) {
            const rect = target.getBoundingClientRect();
            tourHighlightEl.style.top = (rect.top - 4) + "px";
            tourHighlightEl.style.left = (rect.left - 4) + "px";
            tourHighlightEl.style.width = (rect.width + 8) + "px";
            tourHighlightEl.style.height = (rect.height + 8) + "px";
            tourHighlightEl.classList.remove("is-hidden");

            const calloutRect = tourCalloutEl.getBoundingClientRect();
            const margin = 12;
            let top = rect.bottom + margin;
            const left = Math.min(
                Math.max(rect.left, margin),
                Math.max(margin, window.innerWidth - calloutRect.width - margin)
            );
            if (top + calloutRect.height > window.innerHeight - margin) {
                top = Math.max(margin, rect.top - calloutRect.height - margin);
            }
            tourCalloutEl.style.top = top + "px";
            tourCalloutEl.style.left = left + "px";
        }

        function tourPositionCentered() {
            tourHighlightEl.classList.add("is-hidden");
            const calloutRect = tourCalloutEl.getBoundingClientRect();
            tourCalloutEl.style.top = Math.max(12, (window.innerHeight - calloutRect.height) / 2) + "px";
            tourCalloutEl.style.left = Math.max(12, (window.innerWidth - calloutRect.width) / 2) + "px";
        }

        function tourRenderCallout(step, index) {
            tourCalloutEl.innerHTML = "";
            const eyebrow = document.createElement("p");
            eyebrow.className = "tour-callout-eyebrow";
            eyebrow.textContent = "Guided tour — look only";
            tourCalloutEl.appendChild(eyebrow);
            const h3 = document.createElement("h3");
            h3.textContent = step.title;
            tourCalloutEl.appendChild(h3);
            const p = document.createElement("p");
            p.textContent = step.body;
            tourCalloutEl.appendChild(p);

            const actions = document.createElement("div");
            actions.className = "tour-callout-actions";

            const skipBtn = document.createElement("button");
            skipBtn.type = "button";
            skipBtn.className = "tour-skip";
            skipBtn.textContent = "Skip tour";
            skipBtn.addEventListener("click", endTour);
            actions.appendChild(skipBtn);

            const spacer = document.createElement("div");
            spacer.className = "tour-callout-spacer";
            actions.appendChild(spacer);

            const stepLabel = document.createElement("span");
            stepLabel.className = "tour-callout-step";
            stepLabel.textContent = (index + 1) + " / " + TOUR_STEPS.length;
            actions.appendChild(stepLabel);

            if (index > 0) {
                const backBtn = document.createElement("button");
                backBtn.type = "button";
                backBtn.className = "toolbar-btn";
                backBtn.textContent = "Back";
                backBtn.addEventListener("click", function () { tourGoTo(index - 1, -1); });
                actions.appendChild(backBtn);
            }

            const nextBtn = document.createElement("button");
            nextBtn.type = "button";
            nextBtn.className = "toolbar-btn";
            nextBtn.textContent = index === TOUR_STEPS.length - 1 ? "Finish" : "Next";
            nextBtn.addEventListener("click", function () {
                if (index === TOUR_STEPS.length - 1) {
                    endTour();
                } else {
                    tourGoTo(index + 1, 1);
                }
            });
            actions.appendChild(nextBtn);

            tourCalloutEl.appendChild(actions);
        }

        function tourGoTo(index, direction, attempts) {
            attempts = attempts || 0;
            if (index < 0 || index >= TOUR_STEPS.length) {
                return;
            }
            if (attempts > TOUR_STEPS.length) {
                // Every remaining step in this direction failed to resolve
                // (e.g. no ticket rows loaded at all yet) — stop rather
                // than spin forever; Back/Skip still work from here.
                return;
            }
            const step = TOUR_STEPS[index];
            if (step.before) {
                try {
                    step.before();
                } catch (ignore) {
                    // Fall through to the skip path below rather than break
                    // the tour over one step's setup failing.
                }
            }
            const target = tourResolveTarget(step);
            if (target === null) {
                tourGoTo(index + direction, direction, attempts + 1);
                return;
            }
            tourIndex = index;
            tourRenderCallout(step, index);
            if (target === undefined) {
                tourPositionCentered();
            } else {
                target.scrollIntoView({ block: "center", inline: "nearest" });
                tourPositionFor(target);
            }
            const focusable = tourCalloutEl.querySelector("button");
            if (focusable) {
                focusable.focus({ preventScroll: true });
            }
        }

        function tourReposition() {
            if (!tourActive) {
                return;
            }
            const target = tourResolveTarget(TOUR_STEPS[tourIndex]);
            if (target) {
                tourPositionFor(target);
            } else {
                tourPositionCentered();
            }
        }

        function tourBackdropClick(event) {
            if (event.target === tourBackdropEl) {
                endTour();
            }
        }

        function tourKeydown(event) {
            if (event.key === "Escape") {
                endTour();
            } else if (event.key === "ArrowRight" && tourIndex < TOUR_STEPS.length - 1) {
                tourGoTo(tourIndex + 1, 1);
            } else if (event.key === "ArrowLeft" && tourIndex > 0) {
                tourGoTo(tourIndex - 1, -1);
            }
        }

        function startTour() {
            if (tourActive) {
                return;
            }
            tourActive = true;
            tourSavedPanelMode = panelModeEl ? panelModeEl.value : "issues";
            tourForcedVisible = [];
            // One-list filtering (shared across Issues/Projects/Reports)
            // could otherwise hide the very sections/lists a step wants to
            // point at — force All lists for the tour, restored at endTour().
            tourSavedFiltering = filteringEnabled();
            if (tourSavedFiltering) {
                setListView(false);
            }
            // Start from a clean slate — any menu already open (from before
            // the tour started) closes now and isn't reopened at endTour();
            // a minor, acceptable side effect of taking the tour.
            document.querySelectorAll("details.command-menu[open]").forEach(function (menu) {
                menu.open = false;
            });
            tourOpenedMenu = null;
            document.body.appendChild(tourBackdropEl);
            document.body.appendChild(tourHighlightEl);
            document.body.appendChild(tourCalloutEl);
            tourBackdropEl.addEventListener("click", tourBackdropClick);
            document.addEventListener("keydown", tourKeydown);
            window.addEventListener("resize", tourReposition);
            tourGoTo(0, 1);
        }

        function endTour() {
            if (!tourActive) {
                return;
            }
            tourActive = false;
            if (tourOpenedMenu) {
                tourOpenedMenu.open = false;
                tourOpenedMenu = null;
            }
            tourForcedVisible.forEach(function (item) {
                item.el.hidden = item.wasHidden;
            });
            tourForcedVisible = [];
            if (panelModeEl && tourSavedPanelMode !== null && panelModeEl.value !== tourSavedPanelMode) {
                panelModeEl.value = tourSavedPanelMode;
                applyPanelMode();
            }
            tourSavedPanelMode = null;
            // Restored after panel mode, since setListView(true) reads the
            // (now-restored) mode's own selection Set.
            if (tourSavedFiltering && !filteringEnabled()) {
                setListView(true);
            }
            tourSavedFiltering = false;
            tourBackdropEl.removeEventListener("click", tourBackdropClick);
            document.removeEventListener("keydown", tourKeydown);
            window.removeEventListener("resize", tourReposition);
            [tourBackdropEl, tourHighlightEl, tourCalloutEl].forEach(function (el) {
                if (el.parentNode) {
                    el.parentNode.removeChild(el);
                }
            });
        }

        const takeTourBtn = document.getElementById("take_tour_btn");
        if (takeTourBtn) {
            takeTourBtn.addEventListener("click", startTour);
        }

        applyPanelMode();
        pollSharedReportState();
