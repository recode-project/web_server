const socket = io();
        let terminals = {};
        let activeTab = null;
        let tabCounter = 0;
        let isReadOnly = false;

        // ============================================================
        // DETEKSI PERANGKAT SENTUH
        // xterm.js memposisikan textarea helper-nya di luar viewport,
        // sehingga tap pada kanvas terminal tidak memicu keyboard virtual
        // di Android Chrome / iOS Safari. Karena itu di perangkat sentuh
        // kita pakai input bar sendiri.
        // ============================================================
        const IS_TOUCH = ('ontouchstart' in window) ||
            (navigator.maxTouchPoints > 0) ||
            window.matchMedia('(pointer: coarse)').matches;

        // Font 11px di perangkat sentuh agar kapasitas baris naik menjadi 60-65 kolom
        let currentFontSize = IS_TOUCH ? 11 : 14;

        // Status modifier untuk toolbar mobile (sekali pakai / one-shot)
        let modCtrl = false;
        let modAlt = false;

        // Riwayat perintah dari input bar mobile (panah atas/bawah lokal)
        let mobileHistory = [];
        let mobileHistoryIdx = -1;

        // URL params
        const urlParams = new URLSearchParams(window.location.search);
        const startPath = urlParams.get('path') || '/home/ekaharefa';
        const startCmd = urlParams.get('cmd') || '';
        const lxdTarget = urlParams.get('lxd') || null;

        // Load custom commands from localStorage
        let customCommands = JSON.parse(localStorage.getItem('customCommands') || '[]');

        document.addEventListener('DOMContentLoaded', () => {
            const fontSelect = document.getElementById('font-size');
            if (fontSelect) {
                fontSelect.value = String(currentFontSize);
            }
            addTab(startPath, startCmd ? 'Command' : 'Terminal 1');
            renderCustomCommands();
            initMobileInput();

            if (startCmd) {
                setTimeout(() => quickCmd(startCmd), 500);
            }
        });

        function addTab(path = '/root', name = null) {
            tabCounter++;
            const sessionId = 'term_' + tabCounter;
            const tabName = name || `Terminal ${tabCounter}`;

            // Create tab button
            const tabBtn = document.createElement('div');
            tabBtn.className = 'tab';
            tabBtn.id = 'tab-btn-' + sessionId;
            tabBtn.innerHTML = `
                <i class="fa-solid fa-terminal" style="font-size:0.7rem; opacity:0.7"></i>
                <span class="tab-name" contenteditable="true" spellcheck="false" 
                    onblur="saveTabName('${sessionId}', this.textContent)"
                    onkeydown="if(event.key==='Enter'){event.preventDefault();this.blur()}">${tabName}</span>
                <span class="close-tab" onclick="closeTab('${sessionId}', event)"><i class="fa-solid fa-xmark"></i></span>
            `;
            tabBtn.onclick = (e) => {
                if (!e.target.classList.contains('close-tab') && !e.target.closest('.close-tab') && !e.target.classList.contains('tab-name')) {
                    switchTab(sessionId);
                }
            };
            document.getElementById('tabs').appendChild(tabBtn);

            // Matikan tab & wrap aktif sebelumnya
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.terminal-wrap').forEach(t => t.classList.remove('active'));

            tabBtn.classList.add('active');

            // Create terminal wrap - aktifkan langsung di DOM agar bounding box memiliki dimensi valid
            const termWrap = document.createElement('div');
            termWrap.className = 'terminal-wrap active';
            termWrap.id = 'term-wrap-' + sessionId;
            document.getElementById('terminal-container').appendChild(termWrap);

            // Create xterm instance with custom theme
            const term = new Terminal({
                cursorBlink: true,
                fontSize: currentFontSize,
                fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                theme: {
                    background: '#15151e',
                    foreground: '#d0d0d0',
                    cursor: '#55efc4',
                    cursorAccent: '#15151e',
                    selection: 'rgba(85,239,196,0.3)',
                    // Custom colors for better visibility
                    black: '#1e1e28',
                    red: '#ff7675',
                    green: '#55efc4',
                    yellow: '#ffeaa7',
                    blue: '#74b9ff',
                    magenta: '#a29bfe',
                    cyan: '#81ecec',
                    white: '#dfe6e9',
                    brightBlack: '#636e72',
                    brightRed: '#ff7675',
                    brightGreen: '#55efc4',
                    brightYellow: '#ffeaa7',
                    brightBlue: '#74b9ff',
                    brightMagenta: '#a29bfe',
                    brightCyan: '#81ecec',
                    brightWhite: '#ffffff'
                }
            });

            const fitAddon = new FitAddon.FitAddon();
            term.loadAddon(fitAddon);
            term.open(termWrap);
            try { fitAddon.fit(); } catch(e) {}
            requestAnimationFrame(() => {
                try {
                    fitAddon.fit();
                    term.refresh(0, term.rows - 1);
                } catch(e) {}
            });
            setTimeout(() => {
                try {
                    fitAddon.fit();
                    term.refresh(0, term.rows - 1);
                } catch(e) {}
            }, 80);

            // Di perangkat sentuh, tarik textarea helper xterm ke dalam
            // viewport dan bentangkan transparan di atas kanvas. Dengan begitu
            // tap di mana pun pada terminal = fokus = keyboard virtual muncul,
            // dan ketikan mengalir lewat term.onData seperti di desktop.
            if (IS_TOUCH) {
                const helper = termWrap.querySelector('.xterm-helper-textarea');
                if (helper) {
                    helper.classList.add('mobile-typing');
                    helper.setAttribute('autocapitalize', 'off');
                    helper.setAttribute('autocorrect', 'off');
                    helper.setAttribute('autocomplete', 'off');
                    helper.setAttribute('spellcheck', 'false');
                }
            }

            // Handle resize
            const resizeObserver = new ResizeObserver(() => {
                fitAddon.fit();
                if (terminals[sessionId]) {
                    socket.emit('terminal_resize', {
                        session_id: sessionId,
                        rows: term.rows,
                        cols: term.cols
                    });
                }
            });
            resizeObserver.observe(termWrap);

            // Handle input
            term.onData(data => {
                if (!isReadOnly) {
                    socket.emit('terminal_input', {
                        session_id: sessionId,
                        input: data
                    });
                }
            });

            // Store
            terminals[sessionId] = { term, fitAddon, path, name: tabName };

            // Start terminal on server
            socket.emit('start_terminal', {
                session_id: sessionId,
                path: path,
                lxd_target: lxdTarget
            });

            switchTab(sessionId);
        }

        function saveTabName(sessionId, name) {
            if (terminals[sessionId]) {
                terminals[sessionId].name = name.trim() || 'Terminal';
            }
        }

        function switchTab(sessionId) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.terminal-wrap').forEach(t => t.classList.remove('active'));

            document.getElementById('tab-btn-' + sessionId)?.classList.add('active');
            const wrap = document.getElementById('term-wrap-' + sessionId);
            if (wrap) {
                wrap.classList.add('active');
            }

            activeTab = sessionId;

            if (terminals[sessionId]) {
                const t = terminals[sessionId];
                if (!IS_TOUCH || !isFallbackMode()) {
                    t.term.focus();
                }
                requestAnimationFrame(() => {
                    try {
                        t.fitAddon.fit();
                        t.term.refresh(0, t.term.rows - 1);
                    } catch(e) {}
                });
                setTimeout(() => {
                    try {
                        t.fitAddon.fit();
                        t.term.refresh(0, t.term.rows - 1);
                    } catch(e) {}
                }, 80);
            }
        }

        function closeTab(sessionId, event) {
            event.stopPropagation();

            socket.emit('stop_terminal', { session_id: sessionId });

            document.getElementById('tab-btn-' + sessionId)?.remove();
            document.getElementById('term-wrap-' + sessionId)?.remove();

            if (terminals[sessionId]) {
                terminals[sessionId].term.dispose();
                delete terminals[sessionId];
            }

            if (activeTab === sessionId) {
                const remaining = Object.keys(terminals);
                if (remaining.length > 0) {
                    switchTab(remaining[0]);
                } else {
                    activeTab = null;
                }
            }
        }

        function quickCmd(cmd) {
            if (activeTab && terminals[activeTab] && !isReadOnly) {
                socket.emit('terminal_input', {
                    session_id: activeTab,
                    input: cmd + '\n'
                });
            }
        }

        // ============================================================
        // MOBILE INPUT
        // ============================================================

        /**
         * Mode input mobile:
         *   'direct'   -> ketik langsung di dalam terminal (default)
         *   'fallback' -> pakai input bar terpisah di bawah terminal
         * Disimpan di localStorage agar pilihan Tuan Eka bertahan.
         */
        let mobileMode = localStorage.getItem('termMobileMode') || 'direct';

        function isFallbackMode() {
            return mobileMode === 'fallback';
        }

        /** Fokuskan textarea helper xterm milik tab aktif (memicu keyboard). */
        function focusTerminalInput() {
            if (!activeTab || !terminals[activeTab]) return;
            const wrap = document.getElementById('term-wrap-' + activeTab);
            const helper = wrap && wrap.querySelector('.xterm-helper-textarea');
            if (helper) {
                helper.focus({ preventScroll: true });
            } else {
                terminals[activeTab].term.focus();
            }
        }

        /** Arahkan fokus ke target yang sesuai dengan mode aktif. */
        function focusMobileTarget() {
            if (isFallbackMode()) {
                document.getElementById('mobile-input').focus();
            } else {
                focusTerminalInput();
            }
        }

        function setMobileMode(mode) {
            mobileMode = mode;
            localStorage.setItem('termMobileMode', mode);

            const bar = document.getElementById('mobile-bar');
            bar.classList.toggle('fallback', isFallbackMode());

            const btn = document.getElementById('key-mode');
            if (btn) {
                btn.classList.toggle('armed', isFallbackMode());
                btn.title = isFallbackMode()
                    ? 'Mode input bar aktif — ketuk untuk ketik langsung di terminal'
                    : 'Ketik langsung di terminal — ketuk untuk pakai input bar';
            }

            clearMods();
            refitActive();
            focusMobileTarget();
        }

        function toggleMobileMode() {
            setMobileMode(isFallbackMode() ? 'direct' : 'fallback');
        }

        /**
         * Kirim data mentah ke PTY sesi aktif.
         * Jalur yang sama dipakai term.onData, jadi server tidak perlu diubah.
         */
        function sendRaw(data) {
            if (!activeTab || !terminals[activeTab] || isReadOnly) return;
            socket.emit('terminal_input', {
                session_id: activeTab,
                input: data
            });
        }

        /** Decode escape literal dari atribut data-seq menjadi byte asli. */
        function decodeSeq(s) {
            return s
                .replace(/\\x([0-9a-fA-F]{2})/g, (_, h) => String.fromCharCode(parseInt(h, 16)))
                .replace(/\\t/g, '\t')
                .replace(/\\r/g, '\r')
                .replace(/\\n/g, '\n')
                .replace(/\\e/g, '\x1b');
        }

        /**
         * Ubah karakter menjadi control code (Ctrl+A = 0x01, dst).
         * Mengembalikan null jika karakter di luar rentang yang didukung.
         */
        function toCtrlChar(ch) {
            if (!ch) return null;
            const c = ch.toLowerCase();
            const code = c.charCodeAt(0);
            if (code >= 97 && code <= 122) {          // a-z
                return String.fromCharCode(code - 96);
            }
            const map = {
                '@': '\x00', '[': '\x1b', '\\': '\x1c',
                ']': '\x1d', '^': '\x1e', '_': '\x1f', ' ': '\x00'
            };
            return map[c] || null;
        }

        function setMod(which, value) {
            if (which === 'ctrl') {
                modCtrl = value;
                document.getElementById('key-ctrl').classList.toggle('armed', value);
            } else {
                modAlt = value;
                document.getElementById('key-alt').classList.toggle('armed', value);
            }
        }

        function clearMods() {
            setMod('ctrl', false);
            setMod('alt', false);
        }

        /**
         * Terjemahkan satu karakter dengan mempertimbangkan modifier armed.
         * Modifier bersifat one-shot: otomatis lepas setelah satu karakter.
         */
        function applyMods(ch) {
            let out = ch;
            if (modCtrl) {
                const ctrl = toCtrlChar(ch);
                if (ctrl !== null) out = ctrl;
            }
            if (modAlt) {
                out = '\x1b' + out;   // Alt dikirim sebagai ESC prefix
            }
            if (modCtrl || modAlt) clearMods();
            return out;
        }

        /** Kirim isi input bar sebagai satu baris perintah + Enter. */
        function sendMobileInput() {
            const input = document.getElementById('mobile-input');
            const value = input.value;

            // Kirim walau kosong: Enter kosong valid di prompt interaktif
            sendRaw(value + '\r');

            if (value.trim()) {
                mobileHistory.push(value);
                if (mobileHistory.length > 100) mobileHistory.shift();
            }
            mobileHistoryIdx = mobileHistory.length;

            input.value = '';
            // Jaga fokus agar keyboard virtual tidak menutup antar perintah
            input.focus();
        }

        function refitActive() {
            // Tunggu layout selesai sebelum fit, agar cols/rows akurat
            requestAnimationFrame(() => {
                if (activeTab && terminals[activeTab]) {
                    terminals[activeTab].fitAddon.fit();
                    socket.emit('terminal_resize', {
                        session_id: activeTab,
                        rows: terminals[activeTab].term.rows,
                        cols: terminals[activeTab].term.cols
                    });
                }
            });
        }

        function toggleMobileBar() {
            const bar = document.getElementById('mobile-bar');
            const shown = bar.classList.toggle('visible');
            document.getElementById('kbd-toggle').classList.toggle('active', shown);

            if (shown) {
                focusMobileTarget();
            } else {
                document.getElementById('mobile-input').blur();
                clearMods();
            }
            refitActive();
        }

        function initMobileInput() {
            const bar = document.getElementById('mobile-bar');
            const input = document.getElementById('mobile-input');

            // Toolbar tampil otomatis di perangkat sentuh
            if (IS_TOUCH) {
                bar.classList.add('visible');
                document.getElementById('kbd-toggle').classList.add('active');
            }

            // Terapkan mode tersimpan (default: ketik langsung di terminal)
            bar.classList.toggle('fallback', isFallbackMode());
            const modeBtn = document.getElementById('key-mode');
            if (modeBtn) {
                modeBtn.classList.toggle('armed', isFallbackMode());
            }

            // Toolbar tombol khusus (delegasi event supaya hemat listener)
            document.getElementById('mobile-keys').addEventListener('click', (e) => {
                const btn = e.target.closest('.key-btn');
                if (!btn) return;

                // Tombol pengalih mode input
                if (btn.dataset.action === 'mode') {
                    toggleMobileMode();
                    return;
                }

                const mod = btn.dataset.mod;
                if (mod) {
                    // Toggle modifier saja, tidak mengirim apa pun
                    setMod(mod, mod === 'ctrl' ? !modCtrl : !modAlt);
                    focusMobileTarget();
                    return;
                }

                const seq = btn.dataset.seq;
                if (seq !== undefined) {
                    sendRaw(decodeSeq(seq));
                    clearMods();
                    focusMobileTarget();
                }
            });

            // mousedown di-cegah agar tap tombol tidak mencuri fokus dari
            // textarea/input — kalau fokus lepas, keyboard virtual tertutup.
            // Hanya mousedown: preventDefault pada touchstart akan ikut
            // membatalkan event click sehingga tombol tidak berfungsi.
            document.getElementById('mobile-keys').addEventListener('mousedown', (e) => {
                if (e.target.closest('.key-btn')) e.preventDefault();
            });

            // Enter mengirim baris; panah atas/bawah menelusuri riwayat lokal
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    sendMobileInput();
                    return;
                }
                if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    if (mobileHistoryIdx > 0) {
                        mobileHistoryIdx--;
                        input.value = mobileHistory[mobileHistoryIdx];
                    }
                    return;
                }
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    if (mobileHistoryIdx < mobileHistory.length - 1) {
                        mobileHistoryIdx++;
                        input.value = mobileHistory[mobileHistoryIdx];
                    } else {
                        mobileHistoryIdx = mobileHistory.length;
                        input.value = '';
                    }
                    return;
                }
                if (e.key === 'Tab') {
                    // Tab = autocomplete shell: kirim buffer + TAB
                    e.preventDefault();
                    sendRaw(input.value + '\t');
                    input.value = '';
                    return;
                }

                // Modifier armed: kirim langsung sebagai control code supaya
                // Ctrl+C instan, tidak menumpuk di input bar.
                if ((modCtrl || modAlt) && e.key.length === 1) {
                    e.preventDefault();
                    sendRaw(applyMods(e.key));
                }
            });

            // Tap pada area terminal memunculkan keyboard virtual.
            // Mode direct: fokus ke textarea xterm yang sudah dibentangkan.
            // Mode fallback: fokus ke input bar.
            document.getElementById('terminal-container').addEventListener('click', () => {
                if (IS_TOUCH) {
                    focusMobileTarget();
                }
            });

            // Keyboard virtual mengubah tinggi viewport: refit agar baris
            // terakhir tidak tertutup keyboard.
            if (window.visualViewport) {
                let vvTimer = null;
                window.visualViewport.addEventListener('resize', () => {
                    clearTimeout(vvTimer);
                    vvTimer = setTimeout(refitActive, 120);
                });
            }
        }

        function changeFontSize(size) {
            currentFontSize = parseInt(size);
            Object.values(terminals).forEach(t => {
                t.term.options.fontSize = currentFontSize;
                t.fitAddon.fit();
            });
        }

        function toggleReadOnly(checked) {
            isReadOnly = checked;
            document.getElementById('readonly-badge').style.display = checked ? 'inline-block' : 'none';
        }

        // Custom Commands
        function renderCustomCommands() {
            const container = document.getElementById('custom-commands');
            if (customCommands.length === 0) {
                container.innerHTML = '';
                return;
            }

            container.innerHTML = `
                <span class="cmd-category-label" style="background:rgba(255,255,255,0.1); color:#888">
                    <i class="fa-solid fa-star"></i> Custom
                </span>
                ${customCommands.map(c => `
                    <button class="quick-btn" onclick="quickCmd('${c.cmd.replace(/'/g, "\\'")}')" title="${c.cmd}">
                        <i class="fa-solid fa-bolt"></i> ${c.name}
                    </button>
                `).join('')}
            `;
        }

        function showCustomCmdModal() {
            const modal = document.getElementById('custom-cmd-modal');
            modal.classList.remove('hidden');
            modal.classList.add('active');
            document.getElementById('custom-cmd-input').value = customCommands.map(c => `${c.name}=${c.cmd}`).join('\n');
        }

        function hideCustomCmdModal() {
            const modal = document.getElementById('custom-cmd-modal');
            modal.classList.remove('active');
            setTimeout(() => modal.classList.add('hidden'), 300); // Wait for transition
        }

        function saveCustomCommands() {
            const input = document.getElementById('custom-cmd-input').value;
            customCommands = input.split('\n')
                .map(line => line.trim())
                .filter(line => line && line.includes('='))
                .map(line => {
                    const idx = line.indexOf('=');
                    return {
                        name: line.substring(0, idx).trim(),
                        cmd: line.substring(idx + 1).trim()
                    };
                });

            localStorage.setItem('customCommands', JSON.stringify(customCommands));
            renderCustomCommands();
            hideCustomCmdModal();
        }

        // Socket handlers
        socket.on('terminal_output', data => {
            const sessionId = data.session_id;
            if (terminals[sessionId]) {
                terminals[sessionId].term.write(data.data);
            }
        });

        socket.on('terminal_started', data => {
            console.log('Terminal started:', data.session_id);
            if (terminals[data.session_id]) {
                const t = terminals[data.session_id];
                try {
                    t.fitAddon.fit();
                    t.term.refresh(0, t.term.rows - 1);
                } catch(e) {}
                socket.emit('terminal_resize', {
                    session_id: data.session_id,
                    rows: t.term.rows,
                    cols: t.term.cols
                });
            }
        });

        socket.on('terminal_error', data => {
            console.error('Terminal error:', data);
            const msg = (data && data.error) ? data.error : 'Unknown error';
            if (activeTab && terminals[activeTab]) {
                terminals[activeTab].term.write('\r\n\x1b[1;31m[TERMINAL ERROR: ' + msg + ']\x1b[0m\r\n');
            }
        });
        socket.on('connect_error', err => {
            console.error('Socket connect error:', err);
        });
