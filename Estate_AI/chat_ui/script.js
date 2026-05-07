// ═══════════════════════════════════════════
//  ESTATE AI — Agent Dashboard
// ═══════════════════════════════════════════

// ─── State ─────────────────────────────
let currentLang   = 'en';
let selectedFiles = [];
let selectedTone  = 'professional';
let lastResult    = null;
let currentUser   = null;
let editMode      = false;

// ═══════ AUTH BOOTSTRAP ═══════
async function checkAuth() {
  try {
    const res = await fetch('/api/auth/me', { credentials: 'include' });
    const data = await res.json();
    if (!data.authenticated) {
      window.location.href = '/login';
      return false;
    }
    if (data.user.role === 'admin') {
      window.location.href = '/admin/';
      return false;
    }
    currentUser = data.user;
    document.getElementById('userName').textContent = data.user.full_name || data.user.username;
    document.getElementById('userRole').textContent = data.user.agency || 'Real estate agent';
    document.getElementById('userAvatar').textContent =
      (data.user.full_name || data.user.username).charAt(0).toUpperCase();
    return true;
  } catch {
    window.location.href = '/login';
    return false;
  }
}

async function logout() {
  if (!confirm('Sign out of Estate AI?')) return;
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
  window.location.href = '/login';
}

// ═══════ i18n ═══════
function t(key) {
  return (TRANSLATIONS[currentLang] || TRANSLATIONS.en)[key] || key;
}

function tv(label) {
  // Translate a value if a translation exists, else return as-is
  if (!label) return label;
  const k = String(label).toLowerCase().replace(/\s+/g, '_');
  const v = (TRANSLATIONS[currentLang] || TRANSLATIONS.en)[k];
  return v || label;
}

function applyTranslations() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const val = t(key);
    if (el.hasAttribute('placeholder')) {
      el.placeholder = val;
    } else {
      el.textContent = val;
    }
  });
  document.querySelectorAll('[data-i18n-html]').forEach(el => {
    el.innerHTML = t(el.dataset.i18nHtml);
  });
}

function setLanguage(lang) {
  currentLang = lang;
  const meta = { en: ['🇬🇧', 'EN'], hi: ['🇮🇳', 'HI'], zh: ['🇨🇳', 'ZH'], ja: ['🇯🇵', 'JA'] };
  document.getElementById('langFlag').textContent = meta[lang][0];
  document.getElementById('langLabel').textContent = meta[lang][1];
  closeLangMenu();
  applyTranslations();
  if (lastResult) renderResults(lastResult);
}

function toggleLangMenu() {
  document.getElementById('langMenu').classList.toggle('open');
}
function closeLangMenu() {
  document.getElementById('langMenu').classList.remove('open');
}
document.addEventListener('click', e => {
  const sel = document.getElementById('langSelector');
  if (sel && !sel.contains(e.target)) closeLangMenu();
});

// ═══════ NAV / PAGE ROUTING ═══════
function goPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById(`page-${name}`).classList.add('active');
  document.querySelector(`.nav-item[data-page="${name}"]`).classList.add('active');

  const titles = {
    dashboard: { title: 'Dashboard',  crumb: 'Welcome back' },
    generator: { title: 'Generator',  crumb: 'Create a new listing' },
    history:   { title: 'History',    crumb: 'Your past generations' },
  };
  document.getElementById('pageTitle').textContent = titles[name].title;
  document.getElementById('pageCrumb').textContent = titles[name].crumb;

  if (name === 'dashboard') loadDashboard();
  if (name === 'history')   loadHistory();

  // Close mobile sidebar
  document.getElementById('sidebar').classList.remove('open');
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}

// ── Collapsible sidebar (desktop) ──
function collapseSidebar() {
  const sidebar = document.getElementById('sidebar');
  const layout  = document.querySelector('.app-layout');
  const isNowCollapsed = sidebar.classList.toggle('collapsed');
  layout.classList.toggle('sidebar-collapsed', isNowCollapsed);
  localStorage.setItem('sidebarCollapsed', isNowCollapsed ? '1' : '0');
}

function restoreSidebarState() {
  if (localStorage.getItem('sidebarCollapsed') === '1') {
    document.getElementById('sidebar').classList.add('collapsed');
    document.querySelector('.app-layout').classList.add('sidebar-collapsed');
  }
}

// ═══════ DASHBOARD ═══════
async function loadDashboard() {
  try {
    const res = await fetch('/api/my-generations', { credentials: 'include' });
    const data = await res.json();
    const gens = data.generations || [];

    document.getElementById('statTotal').textContent = gens.length;

    // This week
    const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString();
    document.getElementById('statWeek').textContent = gens.filter(g => g.created_at > weekAgo).length;

    // Most used tone
    const toneCounts = {};
    gens.forEach(g => { if (g.tone) toneCounts[g.tone] = (toneCounts[g.tone] || 0) + 1; });
    const topTone = Object.entries(toneCounts).sort((a, b) => b[1] - a[1])[0];
    document.getElementById('statTone').textContent = topTone ? topTone[0] : '—';

    // Last activity
    document.getElementById('statLast').textContent = gens.length
      ? formatRelative(gens[0].created_at) : 'Never';

    // Recent
    const recentEl = document.getElementById('recentList');
    if (gens.length === 0) {
      recentEl.innerHTML = '<div style="text-align:center;padding:24px;color:var(--muted);font-size:0.85rem;">No generations yet</div>';
    } else {
      recentEl.innerHTML = gens.slice(0, 5).map(g => `
        <div onclick="viewGeneration(${g.id})" style="cursor:pointer;padding:10px 12px;border:1px solid var(--border);border-radius:8px;display:flex;justify-content:space-between;align-items:center;transition:all .15s;"
             onmouseover="this.style.borderColor='var(--green)';this.style.background='var(--green-lt)'"
             onmouseout="this.style.borderColor='var(--border)';this.style.background='transparent'">
          <div>
            <div style="font-weight:600;font-size:0.86rem;">${escapeHtml(g.suburb || 'Property')}</div>
            <div style="color:var(--muted);font-size:0.74rem;">${escapeHtml(g.tone || '')} · ${formatRelative(g.created_at)}</div>
          </div>
          <i class="bi bi-chevron-right" style="color:var(--muted-lt);"></i>
        </div>
      `).join('');
    }
  } catch (e) {
    console.error(e);
  }
}

// ═══════ HISTORY ═══════
async function loadHistory() {
  const container = document.getElementById('historyContainer');
  try {
    const res = await fetch('/api/my-generations', { credentials: 'include' });
    const data = await res.json();
    const gens = data.generations || [];

    if (gens.length === 0) {
      container.innerHTML = `
        <div class="empty-history">
          <i class="bi bi-clock-history"></i>
          <h3 style="font-family:'Playfair Display',serif;font-size:1.4rem;color:var(--ink);margin-bottom:6px;">No history yet</h3>
          <p>Your past generations will appear here.</p>
          <button class="btn-sm primary" onclick="goPage('generator')" style="margin-top:14px;">
            <i class="bi bi-stars"></i> Create your first listing
          </button>
        </div>`;
      return;
    }

    // Header row with count + delete-all
    const header = `
      <div class="history-header">
        <div class="history-count">
          <i class="bi bi-collection"></i>
          <span>${gens.length} generation${gens.length === 1 ? '' : 's'}</span>
        </div>
        <button class="btn-sm danger" onclick="confirmDeleteAllGenerations(${gens.length})">
          <i class="bi bi-trash3-fill"></i> Delete all
        </button>
      </div>
    `;

    const list = `<div class="history-list">${gens.map(g => {
      // Use the first image path for a thumbnail if available
      let firstThumb = '';
      try {
        const paths = JSON.parse(g.image_paths || '[]');
        if (paths.length) firstThumb = '/' + paths[0];
      } catch {}
      return `
      <div class="history-card">
        ${firstThumb
          ? `<img class="history-thumb" src="${firstThumb}" alt="" onerror="this.style.display='none'"/>`
          : `<div class="history-thumb history-thumb-empty"><i class="bi bi-image"></i></div>`}
        <div class="history-card-main">
          <div class="history-card-title">
            <i class="bi bi-house-fill" style="color:var(--green-d);"></i>
            ${escapeHtml(g.suburb || 'Property')}
            ${g.tone ? `<span class="badge badge-secondary">${escapeHtml(g.tone)}</span>` : ''}
          </div>
          <div class="history-meta">
            <span><i class="bi bi-calendar3"></i> ${formatDate(g.created_at)}</span>
            ${g.beds ? `<span><i class="bi bi-door-open"></i> ${escapeHtml(g.beds)} bed</span>` : ''}
            ${g.baths ? `<span><i class="bi bi-droplet"></i> ${escapeHtml(g.baths)} bath</span>` : ''}
            ${g.price ? `<span><i class="bi bi-tag"></i> ${escapeHtml(g.price)}</span>` : ''}
          </div>
        </div>
        <div class="history-card-actions">
          <button class="btn-sm" onclick="viewGeneration(${g.id})">
            <i class="bi bi-eye"></i> <span data-i18n="btn_view">View</span>
          </button>
          <button class="btn-sm danger" onclick="deleteGeneration(${g.id})">
            <i class="bi bi-trash3"></i>
          </button>
        </div>
      </div>
    `;}).join('')}</div>`;

    container.innerHTML = header + list;
    applyTranslations();
  } catch (e) {
    container.innerHTML = `<div class="empty-history"><i class="bi bi-exclamation-triangle"></i><p>Could not load history.</p></div>`;
  }
}

async function viewGeneration(id) {
  try {
    const res = await fetch(`/api/generations/${id}`, { credentials: 'include' });
    const data = await res.json();
    if (!data.generation) return;
    const g = data.generation;
    let ads = [];
    try { ads = JSON.parse(g.ads || '[]'); } catch {}

    // Parse image paths for display
    let imagePaths = [];
    try { imagePaths = JSON.parse(g.image_paths || '[]'); } catch {}

    document.getElementById('modalTitle').textContent =
      `${g.suburb || 'Property'} · ${formatDate(g.created_at)}`;

    const imagesHtml = imagePaths.length ? `
      <h4 class="hist-section-label">Photos (${imagePaths.length})</h4>
      <div class="hist-image-grid">
        ${imagePaths.map(p => `
          <a href="/${p}" target="_blank" class="hist-image-cell" title="Open full size">
            <img src="/${p}" alt="" loading="lazy"
                 onerror="this.parentElement.classList.add('missing'); this.remove();"/>
            <div class="hist-image-missing">
              <i class="bi bi-image-alt"></i>
              <span>Missing</span>
            </div>
          </a>
        `).join('')}
      </div>
    ` : '';

    const adsHtml = ads.length ? `
      <h4 class="hist-section-label">Ads</h4>
      ${ads.map((ad, i) => `
        <div class="hist-content-block">
          <div class="hist-content-eyebrow">Variation ${i+1}</div>
          ${escapeHtml(ad)}
        </div>
      `).join('')}
    ` : '';

    document.getElementById('modalBody').innerHTML = `
      <div style="margin-bottom:14px;">
        <span class="badge badge-info">${escapeHtml(g.tone || '—')}</span>
        ${g.beds ? `<span class="badge badge-secondary">${escapeHtml(g.beds)} bed</span>` : ''}
        ${g.baths ? `<span class="badge badge-secondary">${escapeHtml(g.baths)} bath</span>` : ''}
        ${g.price ? `<span class="badge badge-secondary">${escapeHtml(g.price)}</span>` : ''}
      </div>
      ${imagesHtml}
      <h4 class="hist-section-label">Listing</h4>
      <div class="hist-content-block hist-content-block-listing">${escapeHtml(g.listing || '')}</div>
      ${adsHtml}
    `;
    document.getElementById('modalOverlay').classList.add('open');
  } catch (e) {
    showToast('Could not load generation', 'error');
  }
}

async function deleteGeneration(id) {
  if (!confirm('Delete this generation? This cannot be undone.')) return;
  try {
    const res = await fetch(`/api/generations/${id}`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (!res.ok) {
      showToast('Could not delete', 'error');
      return;
    }
    showToast('Deleted', 'success');
    loadHistory();
  } catch {
    showToast('Could not delete', 'error');
  }
}

// ── Delete-all with typed confirmation ──
function confirmDeleteAllGenerations(count) {
  // Build the modal inline; simpler than adding markup to index.html.
  // User must literally type DELETE before the button activates.
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.id = 'deleteAllOverlay';
  overlay.innerHTML = `
    <div class="modal" style="max-width:480px;">
      <div class="modal-head" style="background:#fef2f2;border-bottom-color:#fecaca;">
        <h3 style="color:#991b1b;display:flex;align-items:center;gap:8px;">
          <i class="bi bi-exclamation-triangle-fill"></i> Delete all generations
        </h3>
        <button class="modal-close" onclick="closeDeleteAllModal()">
          <i class="bi bi-x-lg"></i>
        </button>
      </div>
      <div class="modal-body">
        <p style="color:var(--ink);font-size:0.95rem;line-height:1.5;margin-bottom:14px;">
          You are about to permanently delete
          <strong>${count} generation${count === 1 ? '' : 's'}</strong>
          and all their uploaded photos. This action cannot be undone.
        </p>
        <p style="color:var(--muted);font-size:0.85rem;margin-bottom:8px;">
          Type <code style="background:#f1f5f9;padding:2px 6px;border-radius:4px;font-weight:600;">DELETE</code>
          below to confirm:
        </p>
        <input type="text" id="deleteAllConfirmInput" autocomplete="off"
               style="width:100%;padding:10px 12px;border:2px solid #fecaca;
                      border-radius:8px;font-size:0.95rem;font-family:monospace;
                      letter-spacing:0.05em;outline:none;"
               oninput="onDeleteAllConfirmInput(this)"
               onkeydown="if(event.key==='Enter' && !document.getElementById('deleteAllBtn').disabled) executeDeleteAllGenerations()"/>
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;">
          <button class="btn-sm" onclick="closeDeleteAllModal()">Cancel</button>
          <button id="deleteAllBtn" class="btn-sm danger" disabled
                  onclick="executeDeleteAllGenerations()"
                  style="opacity:0.5;cursor:not-allowed;">
            <i class="bi bi-trash3-fill"></i> Delete everything
          </button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  setTimeout(() => document.getElementById('deleteAllConfirmInput')?.focus(), 50);
}

function onDeleteAllConfirmInput(input) {
  const btn = document.getElementById('deleteAllBtn');
  if (!btn) return;
  if (input.value.trim().toUpperCase() === 'DELETE') {
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.style.cursor = 'pointer';
  } else {
    btn.disabled = true;
    btn.style.opacity = '0.5';
    btn.style.cursor = 'not-allowed';
  }
}

function closeDeleteAllModal() {
  document.getElementById('deleteAllOverlay')?.remove();
}

async function executeDeleteAllGenerations() {
  const input = document.getElementById('deleteAllConfirmInput');
  const btn   = document.getElementById('deleteAllBtn');
  if (!input || input.value.trim().toUpperCase() !== 'DELETE') return;
  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Deleting...';
  try {
    const res = await fetch('/api/generations', {
      method: 'DELETE',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirm: 'DELETE' }),
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || 'Could not delete', 'error');
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-trash3-fill"></i> Delete everything';
      return;
    }
    showToast(`Deleted ${data.deleted} generation${data.deleted === 1 ? '' : 's'} ✓`, 'success');
    closeDeleteAllModal();
    loadHistory();
  } catch (e) {
    showToast('Could not delete', 'error');
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-trash3-fill"></i> Delete everything';
  }
}

function closeModal() {
  document.getElementById('modalOverlay').classList.remove('open');
}

// ═══════ FILE HANDLING ═══════
function setupDragDrop() {
  const zone = document.getElementById('uploadZone');
  if (!zone) return;
  zone.addEventListener('dragover', e => {
    e.preventDefault();
    zone.classList.add('dragging');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragging'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('dragging');
    handleFiles(e.dataTransfer.files);
  });
}

function handleFiles(newFiles) {
  const allFiles = Array.from(newFiles);

  // Auto-fill property details if metadata.json is included
  const metaFile = allFiles.find(f => f.name === 'metadata.json');
  if (metaFile) {
    const reader = new FileReader();
    reader.onload = e => {
      try {
        const meta = JSON.parse(e.target.result);
        if (meta.suburb)    document.getElementById('suburb').value    = meta.suburb;
        if (meta.beds)      document.getElementById('beds').value      = meta.beds;
        if (meta.baths)     document.getElementById('baths').value     = meta.baths;
        if (meta.parking)   document.getElementById('parking').value   = meta.parking;
        if (meta.price)     document.getElementById('price').value     = meta.price;
        if (meta.land_size) document.getElementById('land_size').value = meta.land_size;
        showToast(`Details loaded: ${meta.address}, ${meta.suburb}`, 'success');
      } catch (err) {
        console.warn('metadata.json parse error:', err);
      }
    };
    reader.readAsText(metaFile);
  }

  // Add only image files to the selection (ignore metadata.json)
  allFiles
    .filter(f => f.type.startsWith('image/'))
    .slice(0, 10 - selectedFiles.length)
    .forEach(f => selectedFiles.push(f));
  renderPreviews();
}

function renderPreviews() {
  const grid = document.getElementById('previewGrid');
  const ph   = document.getElementById('uploadPlaceholder');
  const cnt  = document.getElementById('imgCount');
  const clr  = document.getElementById('clearBtn');

  grid.innerHTML = '';

  if (!selectedFiles.length) {
    ph.style.display = '';
    cnt.classList.add('hidden');
    cnt.textContent = '';
    clr.classList.add('hidden');
    return;
  }

  ph.style.display = 'none';
  clr.classList.remove('hidden');
  cnt.classList.remove('hidden');
  const n = selectedFiles.length;
  cnt.innerHTML = `<i class="bi bi-images"></i> ${n} ${t(n > 1 ? 'label_images_selected' : 'label_image_selected')}`;

  selectedFiles.slice(0, 9).forEach((f, i) => {
    const d = document.createElement('div');
    d.className = 'prev-item';
    d.innerHTML = `<img src="${URL.createObjectURL(f)}"/><button class="rx" onclick="event.stopPropagation();removeFile(${i})">✕</button>`;
    grid.appendChild(d);
  });

  if (selectedFiles.length > 9) {
    const m = document.createElement('div');
    m.className = 'prev-item more-count';
    m.textContent = `+${selectedFiles.length - 9}`;
    grid.appendChild(m);
  }
}

function removeFile(i) { selectedFiles.splice(i, 1); renderPreviews(); }
function clearAll() {
  selectedFiles = [];
  document.getElementById('fileInput').value = '';
  renderPreviews();
}

// ═══════ TONE ═══════
function setTone(btn) {
  document.querySelectorAll('.tone-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  selectedTone = btn.dataset.tone;
}

// ═══════ PANEL STATE ═══════
function showPanel(state) {
  document.getElementById('emptyState').classList.toggle('hidden',   state !== 'empty');
  document.getElementById('loadingState').classList.toggle('hidden', state !== 'loading');
  document.getElementById('outputArea').classList.toggle('hidden',   state !== 'output');
}

// ═══════ TABS ═══════
function switchTab(tabId, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(tabId).classList.add('active');
}

// ═══════ GENERATE ═══════
async function generate() {
  if (!selectedFiles.length) { showToast(t('err_no_images'), 'error'); return; }

  const btn = document.getElementById('genBtn');
  btn.disabled = true;
  btn.innerHTML = `<div class="spinner-lg" style="width:18px;height:18px;border-width:2px;margin:0;"></div> ${t('btn_generating')}`;
  showPanel('loading');

  const fd = new FormData();
  selectedFiles.forEach(f => fd.append('images', f));
  fd.append('beds',      document.getElementById('beds').value);
  fd.append('baths',     document.getElementById('baths').value);
  fd.append('parking',   document.getElementById('parking').value);
  fd.append('suburb',    document.getElementById('suburb').value || 'Adelaide');
  fd.append('land_size', document.getElementById('land_size').value);
  fd.append('price',     document.getElementById('price').value);
  fd.append('tone',      selectedTone);
  fd.append('lang',      currentLang);
  fd.append('prompt',    '');

  try {
    const res = await fetch('/upload', { method: 'POST', body: fd, credentials: 'include' });
    if (res.status === 401) { window.location.href = '/login'; return; }
    const data = await res.json();
    if (data.error) { showToast(t('err_generic') + data.error, 'error'); showPanel('empty'); return; }
    lastResult = data;
    renderResults(data);
    showPanel('output');
  } catch (e) {
    showToast(t('err_server') + ' ' + e.message, 'error');
    showPanel('empty');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-stars"></i> ${t('btn_generate')}`;
  }
}

// ═══════ BADGE COLOURS ═══════
function conditionBadgeClass(rating) {
  return {
    excellent: 'badge-success',
    good:      'badge-info',
    fair:      'badge-warning',
    poor:      'badge-danger',
  }[String(rating).toLowerCase()] || 'badge-secondary';
}
function confidenceBadgeClass(conf) {
  return {
    high:   'badge-success',
    medium: 'badge-warning',
    low:    'badge-secondary',
  }[String(conf).toLowerCase()] || 'badge-secondary';
}

// ═══════ ANALYSIS PANEL ═══════
function renderAnalysis(analysis) {
  const el = document.getElementById('analysisPanel');
  if (!el) return;

  if (!analysis || !Object.keys(analysis).length) {
    el.innerHTML = `<div class="analysis-header">
      <i class="bi bi-cpu" style="color:var(--green);"></i>
      <span class="analysis-header-title">${t('analysis_heading')}</span>
    </div>
    <p style="color:var(--muted);font-style:italic;font-size:0.82rem;">${t('analysis_not_available')}</p>`;
    return;
  }

  const interior_condition  = analysis.interior_condition  || {};
  const architectural_style = analysis.architectural_style || {};
  const fixtures            = analysis.fixtures || [];
  const luxury              = analysis.luxury_features || [];
  const room_types          = Array.isArray(analysis.room_types) ? analysis.room_types : [];

  const condClass = conditionBadgeClass(interior_condition.rating);
  const confClass = confidenceBadgeClass(architectural_style.confidence);

  const roomRows = room_types.map(r => `
    <tr>
      <td style="font-weight:600;">${tv(r.room || '')}</td>
      <td>${tv(r.size || t('label_unknown'))}</td>
      <td>${tv(r.flooring || t('label_unknown'))}</td>
      <td>${tv(r.ceiling || t('label_unknown'))}</td>
    </tr>
  `).join('');

  const fixturesHtml = fixtures.length
    ? `<div style="display:flex;flex-wrap:wrap;gap:4px;">${fixtures.map(f => `<span class="badge badge-secondary">${tv(f)}</span>`).join('')}</div>`
    : `<p style="color:var(--muted);font-size:0.78rem;font-style:italic;margin:0;">${t('label_none_detected')}</p>`;

  const luxuryHtml = luxury.length
    ? `<div style="display:flex;flex-wrap:wrap;gap:4px;">${luxury.map(l => `<span class="badge badge-warning">${tv(l)}</span>`).join('')}</div>`
    : `<p style="color:var(--muted);font-size:0.78rem;font-style:italic;margin:0;">${t('label_none_detected')}</p>`;

  el.innerHTML = `
    <div class="analysis-header">
      <i class="bi bi-cpu" style="color:var(--green);"></i>
      <span class="analysis-header-title">${t('analysis_heading')}</span>
      <span class="analysis-header-sub">${t('analysis_sub')}</span>
    </div>
    <div class="analysis-grid">
      <div class="analysis-section full-width">
        <div class="analysis-section-label">${t('col_room_types')}</div>
        <table class="analysis-table">
          <thead>
            <tr>
              <th>${t('col_room')}</th>
              <th>${t('col_size')}</th>
              <th>${t('col_flooring')}</th>
              <th>${t('col_ceiling')}</th>
            </tr>
          </thead>
          <tbody>${roomRows || `<tr><td colspan="4" style="color:var(--muted);">${t('label_no_rooms')}</td></tr>`}</tbody>
        </table>
      </div>
      <div class="analysis-section">
        <div class="analysis-section-label">${t('col_condition')}</div>
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
          <span class="badge ${condClass}">${tv(interior_condition.rating) || t('label_unknown')}</span>
        </div>
        <p style="color:var(--muted);font-size:0.78rem;margin:0;">${interior_condition.notes || ''}</p>
      </div>
      <div class="analysis-section">
        <div class="analysis-section-label">${t('col_style')}</div>
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
          <span style="font-weight:600;text-transform:capitalize;">${tv(architectural_style.style) || t('label_unknown')}</span>
          <span class="badge ${confClass}">${tv(architectural_style.confidence) || ''} ${t('label_confidence')}</span>
        </div>
        <p style="color:var(--muted);font-size:0.78rem;margin:0;">${architectural_style.notes || ''}</p>
      </div>
      <div class="analysis-section">
        <div class="analysis-section-label">${t('col_fixtures')}</div>
        ${fixturesHtml}
      </div>
      <div class="analysis-section">
        <div class="analysis-section-label">${t('col_luxury')}</div>
        ${luxuryHtml}
      </div>
    </div>`;
}

// ═══════ COMPLIANCE BAR ═══════
function renderCompliance(violations) {
  const el = document.getElementById('complianceBar');
  if (!violations || !violations.length) {
    el.classList.remove('hidden');
    el.classList.remove('has-error');
    el.classList.add('has-success');
    el.innerHTML = `
      <div class="compliance-title">
        <i class="bi bi-shield-check"></i> Compliance check passed
      </div>
      <div style="font-size:0.8rem;color:var(--ink-2);">No issues detected by Australian real estate guidelines.</div>`;
    return;
  }
  const hasError = violations.some(v => v.severity === 'error');
  el.classList.remove('hidden', 'has-success');
  el.classList.toggle('has-error', hasError);
  el.innerHTML = `
    <div class="compliance-title">
      <i class="bi bi-${hasError ? 'exclamation-octagon-fill' : 'exclamation-triangle-fill'}"></i>
      ${hasError ? 'Compliance issue detected' : 'Review recommended'}
    </div>
    <ul class="compliance-items">
      ${violations.map(v => `
        <li class="compliance-item sev-${v.severity}">
          <i class="bi bi-${v.severity === 'error' ? 'x-circle-fill' : 'exclamation-circle-fill'}"></i>
          <div><strong>${escapeHtml(v.rule_name)}:</strong> ${escapeHtml(v.message)}</div>
        </li>`).join('')}
    </ul>`;
}

// ═══════ RESULTS ═══════
function renderResults(data) {
  const rooms   = data.images ? data.images.map(i => ({ room_type: i.room, objects: i.objects })) : [];
  const content = data.content || null;
  const ads     = content ? content.facebook_ads : [];
  const allObjs = data.all_objects || [];
  const listing = content ? content.listing : (data.final_description || '');

  // Compliance
  renderCompliance(data.compliance || []);

  // Detected chips
  const bar = document.getElementById('detectedBar');
  bar.innerHTML = '';
  const seen = new Set();
  rooms.forEach(r => {
    const label = r.room_type || '';
    if (label && !seen.has(label) && label !== 'invalid') {
      seen.add(label);
      const icon = label === 'floor plan' ? 'bi-grid' : 'bi-house-door';
      bar.innerHTML += `<span class="det-chip det-room"><i class="bi ${icon}"></i> ${escapeHtml(tv(label))}</span>`;
    }
  });
  allObjs.slice(0, 8).forEach(o => {
    bar.innerHTML += `<span class="det-chip det-obj">${escapeHtml(o)}</span>`;
  });

  // Image descriptions
  const imageArea = document.getElementById('imageDescriptions');
  imageArea.innerHTML = '';
  if (data.images) {
    const roomItems = data.images.filter(i => !i.is_invalid && !i.is_floor_plan);
    const fpItems   = data.images.filter(i => i.is_floor_plan);

    const thumbStrip = items => items.map(item => {
      const fileObj = selectedFiles.find(f => f.name === item.filename);
      const imgSrc  = fileObj ? URL.createObjectURL(fileObj) : item.image_url;
      return `<img src="${imgSrc}"/>`;
    }).join('');

    if (roomItems.length > 0) {
      const combinedDesc = roomItems
        .map(i => (i.description || '').trim().replace(/\.+$/, ''))
        .filter(Boolean)
        .join('. ')
        .replace(/\.\s*\./g, '.') + (roomItems.some(i => i.description) ? '.' : '') || t('label_no_desc');
      const roomLabels = [...new Set(roomItems.map(r => r.room).filter(Boolean))].map(tv).join(', ');
      const objLabels  = [...new Set(roomItems.flatMap(r => r.objects || []))].slice(0, 8).join(', ');
      imageArea.innerHTML += `
        <div class="desc-card">
          <div class="thumb-strip">${thumbStrip(roomItems)}</div>
          <div class="section-label">📷 ${t('section_interior')}</div>
          <p>${escapeHtml(combinedDesc)}</p>
          <div class="desc-meta">
            ${roomLabels ? `<span class="pill">🎯 CLIP: ${escapeHtml(roomLabels)}</span>` : ''}
            ${objLabels  ? `<span class="pill">📦 YOLO: ${escapeHtml(objLabels)}</span>` : ''}
            <span class="pill">✍️ LLaVA</span>
          </div>
        </div>`;
    }

    if (fpItems.length > 0) {
      const fpDesc = data.floor_plan_description || t('label_no_desc');
      imageArea.innerHTML += `
        <div class="desc-card">
          <div class="thumb-strip">${thumbStrip(fpItems)}</div>
          <div class="section-label">📐 ${t('section_floor_plan')}</div>
          <p>${escapeHtml(fpDesc)}</p>
          <div class="desc-meta">
            <span class="pill">📐 ${fpItems.length} ${t(fpItems.length > 1 ? 'label_floor_plans' : 'label_floor_plan')}</span>
            <span class="pill">✍️ LLaVA</span>
          </div>
        </div>`;
    }
  }

  // Analysis
  const analysis = data.property_analysis || {};
  if (!Array.isArray(analysis.room_types) || !analysis.room_types.length) {
    const seen = [];
    (data.images || []).filter(i => !i.is_invalid && !i.is_floor_plan).forEach(item => {
      const r = item.room;
      if (r && !seen.includes(r) && r !== 'invalid' && r !== 'floor plan') seen.push(r);
    });
    analysis.room_types = seen.map(r => ({ room: r, size: 'unknown', flooring: 'unknown', ceiling: 'unknown' }));
  }
  renderAnalysis(analysis);

  // Listing
  document.getElementById('listingBody').textContent = listing || t('listing_fallback');

  // Ads
  const adsEl = document.getElementById('adsContainer');
  adsEl.innerHTML = '';
  if (ads && ads.length) {
    ads.forEach((ad, i) => {
      adsEl.innerHTML += `
        <div class="ad-block">
          <div class="ad-block-head">
            <span class="ad-block-label">${t('label_variation')} ${i + 1}</span>
            <div style="display:flex;gap:6px;">
              <button class="btn-sm" onclick="toggleEdit('adBody${i}', this)">
                <i class="bi bi-pencil"></i> ${t('btn_edit')}
              </button>
              <button class="btn-sm" onclick="copyEl('adBody${i}',this)">
                <i class="bi bi-clipboard"></i> ${t('label_ad_copy')}
              </button>
            </div>
          </div>
          <div class="ad-block-body" id="adBody${i}">${escapeHtml(ad)}</div>
        </div>`;
    });
  } else {
    adsEl.innerHTML = `<div class="ad-block"><div class="ad-block-body" style="color:var(--muted);font-style:italic;">${t('err_ads_backend')}</div></div>`;
  }

  // Activate listing tab
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelector('[data-tab="tabListing"]').classList.add('active');
  document.getElementById('tabListing').classList.add('active');
}

// ═══════ EDIT MODE ═══════
function toggleEdit(elId, btn) {
  const el = document.getElementById(elId);
  const isEditing = el.getAttribute('contenteditable') === 'true';
  if (isEditing) {
    el.removeAttribute('contenteditable');
    btn.innerHTML = `<i class="bi bi-pencil"></i> ${t('btn_edit')}`;
    btn.classList.remove('primary');
  } else {
    el.setAttribute('contenteditable', 'true');
    el.focus();
    btn.innerHTML = `<i class="bi bi-check-lg"></i> Done`;
    btn.classList.add('primary');
  }

  // Show save edits button if we have a generation_id and any element is editable
  const anyEditing = document.querySelectorAll('[contenteditable="true"]').length > 0;
  document.getElementById('saveEditsBtn').style.display =
    (lastResult && lastResult.generation_id && anyEditing) ? '' : 'none';
}

async function saveEdits() {
  if (!lastResult || !lastResult.generation_id) {
    showToast('No generation to save', 'error');
    return;
  }
  const listing = document.getElementById('listingBody').innerText;
  const ads = Array.from(document.querySelectorAll("[id^='adBody']")).map(el => el.innerText);
  try {
    const res = await fetch(`/api/generations/${lastResult.generation_id}`, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ listing, ads }),
    });
    if (!res.ok) throw new Error('Save failed');
    showToast(t('toast_saved'), 'success');

    // Re-check compliance on edited listing
    fetch('/api/compliance/check', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: listing }),
    }).then(r => r.json()).then(d => renderCompliance(d.violations || [])).catch(() => {});
  } catch (e) {
    showToast('Could not save edits', 'error');
  }
}

// ═══════ COPY / EXPORT ═══════
function copyEl(id, btn) {
  const text = document.getElementById(id)?.innerText;
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn.innerHTML;
    btn.innerHTML = `<i class="bi bi-check-lg"></i> ${t('label_copied')}`;
    btn.classList.add('copied');
    setTimeout(() => { btn.innerHTML = orig; btn.classList.remove('copied'); }, 2000);
  });
}

function dlTxt(id, name) {
  const text = document.getElementById(id)?.innerText || '';
  const a = Object.assign(document.createElement('a'), {
    href: URL.createObjectURL(new Blob([text], { type: 'text/plain' })),
    download: name,
  });
  a.click();
}

function exportAll() {
  if (!lastResult) return;
  const listing = document.getElementById('listingBody')?.innerText || '';
  let txt = t('export_listing_header') + '\n\n' + listing + '\n\n';
  document.querySelectorAll("[id^='adBody']").forEach((el, i) => {
    txt += `=== ${t('export_ad_header')} ${i + 1} ===\n\n${el.innerText}\n\n`;
  });
  const a = Object.assign(document.createElement('a'), {
    href: URL.createObjectURL(new Blob([txt], { type: 'text/plain' })),
    download: 'estate_ai_content.txt',
  });
  a.click();
}

function copyAll() {
  const listing = document.getElementById('listingBody')?.innerText || '';
  const ads = Array.from(document.querySelectorAll("[id^='adBody']")).map((el, i) =>
    `${t('label_copy_var')} ${i + 1}:\n${el.innerText}`).join('\n\n');
  navigator.clipboard.writeText(listing + (ads ? '\n\n' + ads : ''))
    .then(() => showToast(t('label_all_copied'), 'success'));
}

// ═══════ TOAST ═══════
let toastTimer = null;
function showToast(msg, type = '') {
  const t = document.getElementById('toast');
  t.className = 'toast ' + type;
  t.innerHTML = `<i class="bi bi-${type === 'success' ? 'check-circle-fill' : type === 'error' ? 'exclamation-circle-fill' : 'info-circle-fill'}"></i> ${escapeHtml(msg)}`;
  requestAnimationFrame(() => t.classList.add('show'));
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3500);
}

// ═══════ HELPERS ═══════
function escapeHtml(s) {
  if (s == null) return '';
  return String(s)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatDate(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch { return iso; }
}

function formatRelative(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const sec = (Date.now() - d.getTime()) / 1000;
    if (sec < 60)   return 'Just now';
    if (sec < 3600) return Math.floor(sec / 60) + 'm ago';
    if (sec < 86400) return Math.floor(sec / 3600) + 'h ago';
    if (sec < 604800) return Math.floor(sec / 86400) + 'd ago';
    return formatDate(iso);
  } catch { return iso; }
}

// ═══════ INIT ═══════
document.addEventListener('DOMContentLoaded', async () => {
  restoreSidebarState();
  const ok = await checkAuth();
  if (!ok) return;
  setLanguage(currentLang);
  setupDragDrop();
  loadDashboard();
});