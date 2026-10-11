// CLASH LIVE PROXY STUDIO - OBSIDIAN VICE APPLICATION LOGIC

document.addEventListener('DOMContentLoaded', () => {
  // Global App State
  const state = {
    configs: [],
    activePath: '',
    proxies: [],
    proxyGroups: [],
    testResults: {}, // name -> { alive, delay, error, tested_at }
    filter: 'all',
    search: '',
    sortBy: 'original',
    isTestingAll: false,
  };

  // DOM Elements
  const configSelect = document.getElementById('configSelect');
  const btnReloadConfig = document.getElementById('btnReloadConfig');
  const coreDot = document.getElementById('coreDot');
  const coreText = document.getElementById('coreText');
  const btnRestartCore = document.getElementById('btnRestartCore');

  const btnTestAll = document.getElementById('btnTestAll');
  const btnAddProxy = document.getElementById('btnAddProxy');
  const btnBulkReplace = document.getElementById('btnBulkReplace');
  const btnPurgeDead = document.getElementById('btnPurgeDead');
  const testTargetUrl = document.getElementById('testTargetUrl');
  const btnRawYaml = document.getElementById('btnRawYaml');
  const btnDownloadYaml = document.getElementById('btnDownloadYaml');

  const hudTotal = document.getElementById('hudTotal');
  const hudAlive = document.getElementById('hudAlive');
  const hudDead = document.getElementById('hudDead');
  const hudAvgPing = document.getElementById('hudAvgPing');
  const hudBestPing = document.getElementById('hudBestPing');
  const hudBestName = document.getElementById('hudBestName');
  const hudFileName = document.getElementById('hudFileName');
  const hudAlivePercent = document.getElementById('hudAlivePercent');
  const hudDeadPercent = document.getElementById('hudDeadPercent');

  const countTabAll = document.getElementById('countTabAll');
  const countTabAlive = document.getElementById('countTabAlive');
  const countTabDead = document.getElementById('countTabDead');
  const countTabUntested = document.getElementById('countTabUntested');

  const progressBarContainer = document.getElementById('testProgressBarContainer');
  const progressBarFill = document.getElementById('progressBarFill');
  const progressStatusText = document.getElementById('progressStatusText');
  const progressCountText = document.getElementById('progressCountText');

  const searchInput = document.getElementById('searchInput');
  const sortSelect = document.getElementById('sortSelect');
  const proxyGrid = document.getElementById('proxyGrid');

  // Modals
  const proxyModal = document.getElementById('proxyModal');
  const modalTitle = document.getElementById('modalTitle');
  const btnCloseProxyModal = document.getElementById('btnCloseProxyModal');
  const btnCancelProxyModal = document.getElementById('btnCancelProxyModal');
  const btnSaveProxy = document.getElementById('btnSaveProxy');
  const editOriginalName = document.getElementById('editOriginalName');

  const bulkModal = document.getElementById('bulkModal');
  const btnCloseBulkModal = document.getElementById('btnCloseBulkModal');
  const btnCancelBulkModal = document.getElementById('btnCancelBulkModal');
  const btnApplyBulk = document.getElementById('btnApplyBulk');
  const bulkScope = document.getElementById('bulkScope');
  const bulkOldVal = document.getElementById('bulkOldVal');
  const bulkNewVal = document.getElementById('bulkNewVal');

  const rawModal = document.getElementById('rawModal');
  const btnCloseRawModal = document.getElementById('btnCloseRawModal');
  const btnCancelRawModal = document.getElementById('btnCancelRawModal');
  const btnSaveRaw = document.getElementById('btnSaveRaw');
  const rawYamlEditor = document.getElementById('rawYamlEditor');
  const rawYamlStatus = document.getElementById('rawYamlStatus');

  const toastContainer = document.getElementById('toastContainer');

  // Initialize
  init();

  async function init() {
    await fetchConfigs();
    await loadCurrentConfig();
    await checkSystemStatus();

    setupEventListeners();
  }

  function setupEventListeners() {
    // Config selector
    configSelect.addEventListener('change', async (e) => {
      const selectedPath = e.target.value;
      if (selectedPath && selectedPath !== state.activePath) {
        await switchConfig(selectedPath);
      }
    });

    btnReloadConfig.addEventListener('click', async () => {
      await fetchConfigs();
      showToast('Config list refreshed', 'info');
    });

    btnRestartCore.addEventListener('click', async () => {
      btnRestartCore.disabled = true;
      btnRestartCore.textContent = 'Restarting...';
      try {
        const resp = await fetch('/api/system/restart-core', { method: 'POST' });
        const data = await resp.json();
        if (data.active) {
          showToast('Mihomo Core restarted successfully', 'success');
        } else {
          showToast('Failed to start core', 'error');
        }
      } catch (err) {
        showToast('Error restarting core: ' + err.message, 'error');
      } finally {
        btnRestartCore.disabled = false;
        btnRestartCore.textContent = 'Restart Core';
        await checkSystemStatus();
      }
    });

    // Ribbon Actions
    btnTestAll.addEventListener('click', () => {
      if (!state.isTestingAll) {
        testAllNodes();
      }
    });

    btnAddProxy.addEventListener('click', () => {
      openProxyModal(null);
    });

    btnBulkReplace.addEventListener('click', () => {
      bulkModal.classList.remove('hidden');
    });

    btnPurgeDead.addEventListener('click', () => {
      purgeDeadNodes();
    });

    btnRawYaml.addEventListener('click', async () => {
      await openRawModal();
    });

    // Search and Sort
    searchInput.addEventListener('input', (e) => {
      state.search = e.target.value.toLowerCase().trim();
      renderProxies();
    });

    sortSelect.addEventListener('change', (e) => {
      state.sortBy = e.target.value;
      renderProxies();
    });

    // Filter tabs
    document.querySelectorAll('.filter-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        state.filter = tab.getAttribute('data-filter');
        renderProxies();
      });
    });

    // Modal Close handlers
    btnCloseProxyModal.addEventListener('click', () => proxyModal.classList.add('hidden'));
    btnCancelProxyModal.addEventListener('click', () => proxyModal.classList.add('hidden'));
    btnSaveProxy.addEventListener('click', saveProxyForm);

    btnCloseBulkModal.addEventListener('click', () => bulkModal.classList.remove('hidden') || bulkModal.classList.add('hidden'));
    btnCancelBulkModal.addEventListener('click', () => bulkModal.classList.add('hidden'));
    btnApplyBulk.addEventListener('click', applyBulkReplacement);

    btnCloseRawModal.addEventListener('click', () => rawModal.classList.add('hidden'));
    btnCancelRawModal.addEventListener('click', () => rawModal.classList.add('hidden'));
    btnSaveRaw.addEventListener('click', saveRawYamlConfig);
  }

  // --- API CALLS ---

  async function fetchConfigs() {
    try {
      const resp = await fetch('/api/configs/list');
      const data = await resp.json();
      state.configs = data.configs || [];
      state.activePath = data.active_path || '';

      configSelect.innerHTML = '';
      state.configs.forEach(cfg => {
        const opt = document.createElement('option');
        opt.value = cfg.path;
        opt.textContent = `${cfg.name} (${cfg.proxy_count} proxies, ${cfg.size_kb} KB)`;
        if (cfg.is_active) opt.selected = true;
        configSelect.appendChild(opt);
      });
    } catch (err) {
      showToast('Error loading configs: ' + err.message, 'error');
    }
  }

  async function switchConfig(path) {
    try {
      showToast('Loading config: ' + path.split('\\').pop(), 'info');
      const resp = await fetch('/api/configs/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      });
      const data = await resp.json();
      state.activePath = data.active_path;
      state.testResults = {}; // reset tests
      await loadCurrentConfig();
      await checkSystemStatus();
      showToast('Switched config successfully', 'success');
    } catch (err) {
      showToast('Failed to switch config: ' + err.message, 'error');
    }
  }

  async function loadCurrentConfig() {
    try {
      const resp = await fetch('/api/configs/current');
      if (!resp.ok) throw new Error('Cannot load current config');
      const data = await resp.json();
      state.proxies = data.proxies || [];
      state.proxyGroups = data.proxy_groups || [];
      state.activePath = data.path;

      hudFileName.textContent = data.filename || 'Config Loaded';
      renderProxies();
      updateHUD();
    } catch (err) {
      showToast(err.message, 'error');
      proxyGrid.innerHTML = `
        <div class="empty-state">
          <p>Gagal memuat file konfigurasi.</p>
        </div>
      `;
    }
  }

  async function checkSystemStatus() {
    try {
      const resp = await fetch('/api/system/status');
      const data = await resp.json();
      if (data.active) {
        coreDot.className = 'status-dot green pulse';
        coreText.textContent = `CORE ACTIVE :${data.controller_port}`;
      } else {
        coreDot.className = 'status-dot red';
        coreText.textContent = 'CORE OFFLINE';
      }
    } catch (err) {
      coreDot.className = 'status-dot red';
      coreText.textContent = 'CORE OFFLINE';
    }
  }

  // --- TESTING LOGIC ---

  async function testSingleProxy(name) {
    state.testResults[name] = { alive: false, delay: null, testing: true };
    renderProxies();

    try {
      const targetUrl = testTargetUrl.value;
      const resp = await fetch('/api/test/proxy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          test_url: targetUrl,
          timeout_ms: 4500,
        }),
      });
      const result = await resp.json();
      state.testResults[name] = result;
    } catch (err) {
      state.testResults[name] = { alive: false, delay: null, error: err.message };
    } finally {
      renderProxies();
      updateHUD();
    }
  }

  async function testAllNodes() {
    if (state.proxies.length === 0) return;
    state.isTestingAll = true;
    btnTestAll.disabled = true;
    btnTestAll.innerHTML = '<span class="spinner-sm"></span> TESTING...';

    progressBarContainer.classList.remove('hidden');
    progressBarFill.style.width = '0%';
    progressStatusText.textContent = 'Testing proxies live via isolated Mihomo core...';

    const total = state.proxies.length;
    let completed = 0;
    const targetUrl = testTargetUrl.value;

    // Use SSE Streaming for real-time live updates
    const eventSource = new EventSource(`/api/test/stream?test_url=${encodeURIComponent(targetUrl)}&timeout_ms=4500`);

    eventSource.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'init') {
          progressCountText.textContent = `0 / ${msg.total}`;
        } else if (msg.type === 'result') {
          completed++;
          const res = msg.data;
          state.testResults[res.name] = res;
          const pct = Math.round((completed / total) * 100);
          progressBarFill.style.width = `${pct}%`;
          progressCountText.textContent = `${completed} / ${total}`;

          // Quick update of card in real time
          renderProxies();
          updateHUD();
        } else if (msg.type === 'done') {
          eventSource.close();
          finishTestAll();
        }
      } catch (e) {
        console.error('SSE Error:', e);
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      finishTestAll();
    };

    function finishTestAll() {
      state.isTestingAll = false;
      btnTestAll.disabled = false;
      btnTestAll.innerHTML = '<span class="btn-icon-symbol">⚡</span> TEST ALL NODES';
      progressStatusText.textContent = 'Audit completed!';
      setTimeout(() => {
        progressBarContainer.classList.add('hidden');
      }, 2500);
      showToast('Selesai menguji seluruh node proxy!', 'success');
      updateHUD();
    }
  }

  // --- RENDER FUNCTIONS ---

  function renderProxies() {
    const list = getFilteredAndSortedProxies();

    if (list.length === 0) {
      proxyGrid.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 48px; color: var(--text-dim);">
          <h3>Tidak ada proxy yang sesuai kriteria</h3>
          <p style="font-size: 13px; margin-top: 6px;">Coba ubah kata kunci pencarian atau tab filter.</p>
        </div>
      `;
      return;
    }

    proxyGrid.innerHTML = list.map(p => {
      const name = p.name;
      const test = state.testResults[name];
      const type = (p.type || 'trojan').toLowerCase();
      const server = p.server || '-';
      const port = p.port || 443;
      const sni = p.sni || '-';
      const wsOpts = p['ws-opts'] || {};
      const wsPath = wsOpts.path || '-';
      const hostHeader = (wsOpts.headers && wsOpts.headers.Host) || '-';

      let statusClass = 'status-untested';
      let latencyHtml = '<span class="latency-badge untested">⏳ UNTESTED</span>';

      if (test) {
        if (test.testing) {
          statusClass = 'status-testing';
          latencyHtml = '<span class="latency-badge testing">⚡ PINGING...</span>';
        } else if (test.alive) {
          statusClass = 'status-alive';
          latencyHtml = `<span class="latency-badge alive">⚡ ${test.delay} ms</span>`;
        } else {
          statusClass = 'status-dead';
          const errShort = test.error ? (test.error.includes('503') ? 'DEAD / 503' : 'TIMEOUT') : 'DEAD';
          latencyHtml = `<span class="latency-badge dead" title="${test.error || 'Connection failed'}">🔴 ${errShort}</span>`;
        }
      }

      return `
        <div class="proxy-card ${statusClass}" data-name="${escapeHtml(name)}">
          <div class="card-header">
            <div class="node-title-box">
              <span class="badge-protocol">${type}</span>
              <div class="node-name" title="${escapeHtml(name)}">${escapeHtml(name)}</div>
            </div>
            ${latencyHtml}
          </div>

          <div class="card-specs">
            <div class="spec-item">
              <span class="spec-label">BUG / SERVER:</span>
              <span class="spec-val">${escapeHtml(server)}:${port}</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">SNI:</span>
              <span class="spec-val">${escapeHtml(sni)}</span>
            </div>
            <div class="spec-item">
              <span class="spec-label">WS PATH / HOST:</span>
              <span class="spec-val">${escapeHtml(wsPath)} | ${escapeHtml(hostHeader)}</span>
            </div>
          </div>

          <div class="card-actions">
            <button class="btn-card-test btn-action-test" data-name="${escapeHtml(name)}">
              ⚡ Test Ping
            </button>
            <div class="card-icon-actions">
              <button class="btn-icon btn-action-edit" data-name="${escapeHtml(name)}" title="Edit Node">✏️</button>
              <button class="btn-icon btn-action-dup" data-name="${escapeHtml(name)}" title="Duplicate Node">📑</button>
              <button class="btn-icon btn-action-del" data-name="${escapeHtml(name)}" title="Delete Node">🗑️</button>
            </div>
          </div>
        </div>
      `;
    }).join('');

    // Attach card event listeners
    proxyGrid.querySelectorAll('.btn-action-test').forEach(btn => {
      btn.addEventListener('click', () => testSingleProxy(btn.getAttribute('data-name')));
    });

    proxyGrid.querySelectorAll('.btn-action-edit').forEach(btn => {
      btn.addEventListener('click', () => {
        const name = btn.getAttribute('data-name');
        const target = state.proxies.find(p => p.name === name);
        if (target) openProxyModal(target);
      });
    });

    proxyGrid.querySelectorAll('.btn-action-dup').forEach(btn => {
      btn.addEventListener('click', () => duplicateProxy(btn.getAttribute('data-name')));
    });

    proxyGrid.querySelectorAll('.btn-action-del').forEach(btn => {
      btn.addEventListener('click', () => deleteProxy(btn.getAttribute('data-name')));
    });
  }

  function getFilteredAndSortedProxies() {
    let list = [...state.proxies];

    // Search filter
    if (state.search) {
      list = list.filter(p => {
        const text = `${p.name} ${p.server} ${p.sni || ''} ${p.type || ''}`.toLowerCase();
        return text.includes(state.search);
      });
    }

    // Status filter
    if (state.filter === 'alive') {
      list = list.filter(p => state.testResults[p.name] && state.testResults[p.name].alive);
    } else if (state.filter === 'dead') {
      list = list.filter(p => state.testResults[p.name] && !state.testResults[p.name].alive && !state.testResults[p.name].testing);
    } else if (state.filter === 'untested') {
      list = list.filter(p => !state.testResults[p.name]);
    }

    // Sort
    if (state.sortBy === 'ping-asc') {
      list.sort((a, b) => {
        const da = (state.testResults[a.name] && state.testResults[a.name].delay) || 99999;
        const db = (state.testResults[b.name] && state.testResults[b.name].delay) || 99999;
        return da - db;
      });
    } else if (state.sortBy === 'ping-desc') {
      list.sort((a, b) => {
        const da = (state.testResults[a.name] && state.testResults[a.name].delay) || -1;
        const db = (state.testResults[b.name] && state.testResults[b.name].delay) || -1;
        return db - da;
      });
    } else if (state.sortBy === 'name-asc') {
      list.sort((a, b) => a.name.localeCompare(b.name));
    }

    return list;
  }

  function updateHUD() {
    const total = state.proxies.length;
    let aliveCount = 0;
    let deadCount = 0;
    let untestedCount = 0;
    let totalDelay = 0;
    let bestDelay = Infinity;
    let bestName = 'None';

    state.proxies.forEach(p => {
      const res = state.testResults[p.name];
      if (!res) {
        untestedCount++;
      } else if (res.alive) {
        aliveCount++;
        totalDelay += res.delay || 0;
        if (res.delay && res.delay < bestDelay) {
          bestDelay = res.delay;
          bestName = p.name;
        }
      } else {
        deadCount++;
      }
    });

    hudTotal.textContent = total;
    hudAlive.textContent = aliveCount;
    hudDead.textContent = deadCount;

    const alivePct = total > 0 ? Math.round((aliveCount / total) * 100) : 0;
    const deadPct = total > 0 ? Math.round((deadCount / total) * 100) : 0;
    hudAlivePercent.textContent = `${alivePct}% active`;
    hudDeadPercent.textContent = `${deadPct}% fail`;

    if (aliveCount > 0) {
      hudAvgPing.textContent = `${Math.round(totalDelay / aliveCount)} ms`;
      hudBestPing.textContent = `${bestDelay} ms`;
      hudBestName.textContent = bestName;
    } else {
      hudAvgPing.textContent = '-- ms';
      hudBestPing.textContent = '-- ms';
      hudBestName.textContent = 'None';
    }

    countTabAll.textContent = total;
    countTabAlive.textContent = aliveCount;
    countTabDead.textContent = deadCount;
    countTabUntested.textContent = untestedCount;

    // Enable/disable purge dead button
    btnPurgeDead.disabled = deadCount === 0;
  }

  // --- PROXY CRUD ---

  function openProxyModal(proxy) {
    const isEdit = !!proxy;
    modalTitle.textContent = isEdit ? 'Edit Proxy Node' : 'Add New Proxy Node';
    editOriginalName.value = isEdit ? proxy.name : '';

    document.getElementById('formName').value = isEdit ? proxy.name : '';
    document.getElementById('formType').value = isEdit ? (proxy.type || 'trojan') : 'trojan';
    document.getElementById('formServer').value = isEdit ? (proxy.server || '') : 'support.zoom.us';
    document.getElementById('formPort').value = isEdit ? (proxy.port || 443) : 443;
    document.getElementById('formPassword').value = isEdit ? (proxy.password || proxy.uuid || '') : '';
    document.getElementById('formSni').value = isEdit ? (proxy.sni || '') : '';
    document.getElementById('formNetwork').value = isEdit ? (proxy.network || 'ws') : 'ws';

    const wsOpts = (isEdit && proxy['ws-opts']) || {};
    document.getElementById('formWsPath').value = wsOpts.path || '/trojan';
    document.getElementById('formWsHost').value = (wsOpts.headers && wsOpts.headers.Host) || '';

    document.getElementById('formSkipCert').checked = isEdit ? (proxy['skip-cert-verify'] !== false) : true;
    document.getElementById('formUdp').checked = isEdit ? (proxy.udp !== false) : true;

    proxyModal.classList.remove('hidden');
  }

  async function saveProxyForm() {
    const name = document.getElementById('formName').value.trim();
    const type = document.getElementById('formType').value;
    const server = document.getElementById('formServer').value.trim();
    const port = parseInt(document.getElementById('formPort').value, 10);
    const password = document.getElementById('formPassword').value.trim();
    const sni = document.getElementById('formSni').value.trim();
    const network = document.getElementById('formNetwork').value;
    const wsPath = document.getElementById('formWsPath').value.trim();
    const wsHost = document.getElementById('formWsHost').value.trim();
    const skipCert = document.getElementById('formSkipCert').checked;
    const udp = document.getElementById('formUdp').checked;

    if (!name || !server || !password) {
      showToast('Mohon isi field Name, Server, dan Password/UUID!', 'error');
      return;
    }

    const proxyData = {
      name,
      server,
      port,
      type,
      password,
      'skip-cert-verify': skipCert,
      network,
      udp,
    };

    if (type === 'vmess' || type === 'vless') {
      proxyData.uuid = password;
      delete proxyData.password;
    }

    if (sni) proxyData.sni = sni;

    if (network === 'ws') {
      proxyData['ws-opts'] = {
        path: wsPath || '/trojan',
        headers: {
          Host: wsHost || sni || server,
        },
      };
    }

    const origName = editOriginalName.value;
    const isEdit = !!origName;

    try {
      if (isEdit) {
        const resp = await fetch('/api/proxies/update', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ original_name: origName, proxy: proxyData }),
        });
        if (!resp.ok) {
          const err = await resp.json();
          throw new Error(err.detail || 'Gagal mengupdate proxy');
        }
        showToast(`Proxy '${name}' berhasil diperbarui`, 'success');
      } else {
        const resp = await fetch('/api/proxies/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ proxy: proxyData }),
        });
        if (!resp.ok) {
          const err = await resp.json();
          throw new Error(err.detail || 'Gagal menambah proxy');
        }
        showToast(`Proxy '${name}' berhasil ditambahkan`, 'success');
      }

      proxyModal.classList.add('hidden');
      await loadCurrentConfig();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function duplicateProxy(name) {
    try {
      const resp = await fetch(`/api/proxies/duplicate/${encodeURIComponent(name)}`, { method: 'POST' });
      if (!resp.ok) throw new Error('Gagal duplikasi node');
      const data = await resp.json();
      showToast(`Duplikasi berhasil: ${data.new_name}`, 'success');
      await loadCurrentConfig();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function deleteProxy(name) {
    if (!confirm(`Hapus node proxy '${name}' dari konfigurasi?`)) return;

    try {
      const resp = await fetch(`/api/proxies/${encodeURIComponent(name)}`, { method: 'DELETE' });
      if (!resp.ok) throw new Error('Gagal menghapus node');
      showToast(`Node '${name}' berhasil dihapus`, 'success');
      delete state.testResults[name];
      await loadCurrentConfig();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function applyBulkReplacement() {
    const scope = bulkScope.value;
    const oldVal = bulkOldVal.value.trim();
    const newVal = bulkNewVal.value.trim();

    if (!oldVal || !newVal) {
      showToast('Isi nilai Old Value dan New Value!', 'error');
      return;
    }

    try {
      const resp = await fetch('/api/proxies/bulk-replace-bug', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scope, old_val: oldVal, new_val: newVal }),
      });
      const data = await resp.json();
      showToast(`Berhasil mengganti bug pada ${data.replaced_count} proxy!`, 'success');
      bulkModal.classList.add('hidden');
      await loadCurrentConfig();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function purgeDeadNodes() {
    const deadNames = Object.keys(state.testResults).filter(
      name => !state.testResults[name].alive && !state.testResults[name].testing
    );

    if (deadNames.length === 0) {
      showToast('Tidak ada node dead yang terdeteksi.', 'info');
      return;
    }

    if (!confirm(`Bersihkan ${deadNames.length} node DEAD dari file konfigurasi? Tindakan ini tidak dapat dibatalkan (backup otomatis dibuat).`)) {
      return;
    }

    try {
      const resp = await fetch('/api/proxies/purge-dead', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dead_names: deadNames }),
      });
      const data = await resp.json();
      showToast(`${data.purged_count} node dead berhasil dibersihkan!`, 'success');
      state.testResults = {};
      await loadCurrentConfig();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function openRawModal() {
    try {
      rawYamlStatus.textContent = 'Loading YAML...';
      const resp = await fetch('/api/configs/raw');
      const data = await resp.json();
      rawYamlEditor.value = data.content || '';
      rawYamlStatus.textContent = `Lines: ${data.content.split('\n').length}`;
      rawModal.classList.remove('hidden');
    } catch (err) {
      showToast('Gagal memuat raw YAML: ' + err.message, 'error');
    }
  }

  async function saveRawYamlConfig() {
    const content = rawYamlEditor.value;
    rawYamlStatus.textContent = 'Saving & Validating...';
    try {
      const resp = await fetch('/api/configs/raw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'Gagal menyimpan YAML');
      showToast('YAML berhasil disimpan dan divalidasi!', 'success');
      rawModal.classList.add('hidden');
      await loadCurrentConfig();
    } catch (err) {
      rawYamlStatus.textContent = 'Error: ' + err.message;
      showToast(err.message, 'error');
    }
  }

  // --- TOAST NOTIFICATIONS (Safe DOM construction anti-XSS) ---
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const iconSpan = document.createElement('span');
    iconSpan.textContent = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
    const textSpan = document.createElement('span');
    textSpan.textContent = message;
    toast.appendChild(iconSpan);
    toast.appendChild(textSpan);
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
});
