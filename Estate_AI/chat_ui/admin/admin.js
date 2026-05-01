// ═══════════════════════════════════════════
//  ESTATE AI — Admin Console
// ═══════════════════════════════════════════

let currentUser = null;
let cachedTemplates = [];
let cachedRules = [];

// ═══════ AUTH ═══════
async function checkAuth() {
  try {
    const res = await fetch('/api/auth/me', { credentials: 'include' });
    const data = await res.json();
    if (!data.authenticated) {
      window.location.href = '/admin-login';
      return false;
    }
    if (data.user.role !== 'admin') {
      window.location.href = '/app/';
      return false;
    }
    currentUser = data.user;
    document.getElementById('userName').textContent = data.user.full_name || data.user.username;
    document.getElementById('userAvatar').textContent =
      (data.user.full_name || data.user.username).charAt(0).toUpperCase();
    return true;
  } catch {
    window.location.href = '/admin-login';
    return false;
  }
}

async function logout() {
  if (!confirm('Sign out of admin console?')) return;
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
  window.location.href = '/admin-login';
}

// ═══════ NAV ═══════
function goPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById(`page-${name}`).classList.add('active');
  document.querySelector(`.nav-item[data-page="${name}"]`).classList.add('active');

  const titles = {
    overview:    { title: 'Overview',    crumb: 'Platform analytics' },
    users:       { title: 'Users',       crumb: 'Manage agents and admins' },
    generations: { title: 'Generations', crumb: 'All listings produced' },
    templates:   { title: 'Templates',   crumb: 'Listing template library' },
    compliance:  { title: 'Compliance',  crumb: 'Content rules and guardrails' },
  };
  document.getElementById('pageTitle').textContent = titles[name].title;
  document.getElementById('pageCrumb').textContent = titles[name].crumb;

  if (name === 'overview')    loadOverview();
  if (name === 'users')       loadUsers();
  if (name === 'generations') loadGenerations();
  if (name === 'templates')   loadTemplates();
  if (name === 'compliance')  loadCompliance();

  document.getElementById('sidebar').classList.remove('open');
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}

// ═══════ OVERVIEW ═══════
async function loadOverview() {
  try {
    const res = await fetch('/api/admin/analytics', { credentials: 'include' });
    const data = await res.json();

    document.getElementById('adminTotalAgents').textContent  = data.total_agents;
    document.getElementById('adminActiveAgents').textContent = data.active_agents;
    document.getElementById('adminTotalGens').textContent    = data.total_generations;
    document.getElementById('adminGens7d').textContent       = data.generations_7d;

    // Bar chart — last 14 days
    const chart = document.getElementById('adminBarChart');
    const days = data.per_day || [];
    if (!days.length) {
      chart.innerHTML = `<div style="margin:auto;color:var(--muted);font-size:0.85rem;">No data for this period</div>`;
    } else {
      const max = Math.max(...days.map(d => d.cnt), 1);
      // Build last 14 days
      const series = [];
      for (let i = 13; i >= 0; i--) {
        const d = new Date(Date.now() - i * 86400000);
        const k = d.toISOString().slice(0, 10);
        const found = days.find(x => x.day === k);
        series.push({ day: k, cnt: found ? found.cnt : 0 });
      }
      chart.innerHTML = series.map(s => {
        const h = (s.cnt / max) * 100;
        const dt = new Date(s.day);
        const lbl = `${dt.getDate()}/${dt.getMonth() + 1}`;
        return `<div class="bar-col">
          <div class="bar-fill" style="height:${h}%;" data-val="${s.cnt}"></div>
          <div class="bar-label">${lbl}</div>
        </div>`;
      }).join('');
    }

    // Tone distribution
    const toneEl = document.getElementById('adminToneDist');
    const tones = data.tone_distribution || [];
    if (!tones.length) {
      toneEl.innerHTML = `<div style="text-align:center;padding:24px;color:var(--muted);font-size:0.85rem;">No data</div>`;
    } else {
      const total = tones.reduce((s, t) => s + t.cnt, 0);
      toneEl.innerHTML = tones.map(t => `
        <div class="tone-bar-row">
          <span class="label">${escapeHtml(t.tone || 'unknown')}</span>
          <span class="bar"><span class="fill" style="width:${(t.cnt / total) * 100}%;"></span></span>
          <span class="count">${t.cnt}</span>
        </div>`).join('');
    }

    // Top agents
    const topAgentsEl = document.getElementById('adminTopAgents');
    const tops = data.top_agents || [];
    if (!tops.length) {
      topAgentsEl.innerHTML = `<div style="text-align:center;padding:20px;color:var(--muted);font-size:0.85rem;">No agents yet</div>`;
    } else {
      topAgentsEl.innerHTML = `<table class="data-table" style="border:none;">
        <thead><tr><th>Agent</th><th>Generations</th></tr></thead>
        <tbody>${tops.map(a => `
          <tr>
            <td>${escapeHtml(a.full_name || a.username || '—')}</td>
            <td><strong>${a.cnt}</strong></td>
          </tr>`).join('')}
        </tbody>
      </table>`;
    }

    // Top suburbs
    const subEl = document.getElementById('adminTopSuburbs');
    const subs = data.top_suburbs || [];
    if (!subs.length) {
      subEl.innerHTML = `<div style="text-align:center;padding:20px;color:var(--muted);font-size:0.85rem;">No data</div>`;
    } else {
      subEl.innerHTML = `<table class="data-table" style="border:none;">
        <thead><tr><th>Suburb</th><th>Listings</th></tr></thead>
        <tbody>${subs.map(s => `
          <tr>
            <td>${escapeHtml(s.suburb || '—')}</td>
            <td><strong>${s.cnt}</strong></td>
          </tr>`).join('')}
        </tbody>
      </table>`;
    }
  } catch (e) {
    showToast('Could not load analytics', 'error');
  }
}

// ═══════ USERS ═══════
async function loadUsers() {
  const c = document.getElementById('usersContainer');
  try {
    const res = await fetch('/api/admin/users', { credentials: 'include' });
    const data = await res.json();
    const users = data.users || [];

    if (!users.length) {
      c.innerHTML = `<div class="empty-card"><i class="bi bi-people"></i><p>No users yet</p></div>`;
      return;
    }

    c.innerHTML = `<table class="data-table">
      <thead>
        <tr>
          <th>User</th><th>Role</th><th>Email</th><th>Agency</th><th>Last login</th><th>Status</th><th></th>
        </tr>
      </thead>
      <tbody>
        ${users.map(u => `
          <tr>
            <td>
              <div style="display:flex;align-items:center;gap:10px;">
                <div style="width:32px;height:32px;border-radius:8px;background:${u.role === 'admin' ? '#fef3c7' : 'var(--green-lt)'};color:${u.role === 'admin' ? '#92400e' : 'var(--green-d)'};display:flex;align-items:center;justify-content:center;font-weight:600;font-size:0.85rem;">
                  ${escapeHtml((u.full_name || u.username).charAt(0).toUpperCase())}
                </div>
                <div>
                  <div style="font-weight:600;color:var(--ink);">${escapeHtml(u.full_name || '—')}</div>
                  <div style="font-size:0.74rem;color:var(--muted);">@${escapeHtml(u.username)}</div>
                </div>
              </div>
            </td>
            <td><span class="badge ${u.role === 'admin' ? 'badge-warning' : 'badge-info'}">${escapeHtml(u.role)}</span></td>
            <td>${escapeHtml(u.email)}</td>
            <td>${escapeHtml(u.agency || '—')}</td>
            <td>${u.last_login ? formatRelative(u.last_login) : 'Never'}</td>
            <td>
              <span class="badge ${u.is_active ? 'badge-success' : 'badge-secondary'}">
                ${u.is_active ? 'Active' : 'Disabled'}
              </span>
            </td>
            <td style="text-align:right;">
              ${u.role !== 'admin' ? `
                <button class="btn-sm" onclick="toggleUser(${u.id})">
                  <i class="bi bi-${u.is_active ? 'pause-fill' : 'play-fill'}"></i>
                  ${u.is_active ? 'Disable' : 'Enable'}
                </button>
                <button class="btn-sm danger" onclick="deleteUser(${u.id}, '${escapeHtml(u.username)}')">
                  <i class="bi bi-trash3"></i>
                </button>` : '<span style="color:var(--muted-lt);font-size:0.78rem;">protected</span>'}
            </td>
          </tr>`).join('')}
      </tbody>
    </table>`;
  } catch {
    c.innerHTML = `<div class="empty-card"><i class="bi bi-exclamation-triangle"></i><p>Could not load users</p></div>`;
  }
}

async function toggleUser(id) {
  try {
    await fetch(`/api/admin/users/${id}/toggle`, { method: 'POST', credentials: 'include' });
    showToast('User updated', 'success');
    loadUsers();
  } catch {
    showToast('Update failed', 'error');
  }
}

async function deleteUser(id, name) {
  if (!confirm(`Delete user "${name}" and all their generations? This cannot be undone.`)) return;
  try {
    const res = await fetch(`/api/admin/users/${id}`, { method: 'DELETE', credentials: 'include' });
    if (!res.ok) {
      const err = await res.json();
      showToast(err.error || 'Delete failed', 'error');
      return;
    }
    showToast('User deleted', 'success');
    loadUsers();
  } catch {
    showToast('Delete failed', 'error');
  }
}

function showAddUserModal() {
  document.getElementById('modalTitle').textContent = 'Add new user';
  document.getElementById('modalBody').innerHTML = `
    <div class="modal-row">
      <div class="modal-field">
        <label>Username *</label>
        <input class="modal-input" id="m_username" placeholder="janesmith"/>
      </div>
      <div class="modal-field">
        <label>Full name</label>
        <input class="modal-input" id="m_fullname" placeholder="Jane Smith"/>
      </div>
    </div>
    <div class="modal-field">
      <label>Email *</label>
      <input class="modal-input" id="m_email" type="email" placeholder="jane@agency.com"/>
    </div>
    <div class="modal-row">
      <div class="modal-field">
        <label>Role *</label>
        <select class="modal-input" id="m_role">
          <option value="agent">Agent</option>
          <option value="admin">Admin</option>
        </select>
      </div>
      <div class="modal-field">
        <label>Password * <span style="color:var(--muted);font-weight:400;">(min 6)</span></label>
        <input class="modal-input" id="m_password" type="password" placeholder="••••••••"/>
      </div>
    </div>
    <div class="modal-row">
      <div class="modal-field">
        <label>Agency</label>
        <input class="modal-input" id="m_agency" placeholder="Adelaide Realty"/>
      </div>
      <div class="modal-field">
        <label>Phone</label>
        <input class="modal-input" id="m_phone" placeholder="+61 400 000 000"/>
      </div>
    </div>`;
  document.getElementById('modalFoot').innerHTML = `
    <button class="btn-sm" onclick="closeModal()">Cancel</button>
    <button class="btn-sm primary" onclick="submitNewUser()"><i class="bi bi-check-lg"></i> Create user</button>`;
  openModal();
}

async function submitNewUser() {
  const body = {
    username:  document.getElementById('m_username').value.trim(),
    email:     document.getElementById('m_email').value.trim(),
    full_name: document.getElementById('m_fullname').value.trim(),
    role:      document.getElementById('m_role').value,
    password:  document.getElementById('m_password').value,
    agency:    document.getElementById('m_agency').value.trim(),
    phone:     document.getElementById('m_phone').value.trim(),
  };
  if (!body.username || !body.email || !body.password || body.password.length < 6) {
    showToast('Username, email, and a 6+ char password are required', 'error');
    return;
  }
  try {
    const res = await fetch('/api/admin/users', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) { showToast(data.error || 'Failed', 'error'); return; }
    showToast('User created', 'success');
    closeModal();
    loadUsers();
  } catch {
    showToast('Could not create user', 'error');
  }
}

// ═══════ GENERATIONS ═══════
async function loadGenerations() {
  const c = document.getElementById('genContainer');
  try {
    const res = await fetch('/api/admin/generations', { credentials: 'include' });
    const data = await res.json();
    const gens = data.generations || [];
    if (!gens.length) {
      c.innerHTML = `<div class="empty-card"><i class="bi bi-clipboard"></i><p>No generations yet</p></div>`;
      return;
    }
    c.innerHTML = `<table class="data-table">
      <thead>
        <tr><th>Date</th><th>Agent</th><th>Suburb</th><th>Tone</th><th>Beds/Baths</th><th>Price</th><th></th></tr>
      </thead>
      <tbody>
        ${gens.map(g => `
          <tr>
            <td>${formatDate(g.created_at)}</td>
            <td><strong>${escapeHtml(g.full_name || g.username || '—')}</strong></td>
            <td>${escapeHtml(g.suburb || '—')}</td>
            <td><span class="badge badge-secondary">${escapeHtml(g.tone || '—')}</span></td>
            <td>${escapeHtml(g.beds || '?')} / ${escapeHtml(g.baths || '?')}</td>
            <td>${escapeHtml(g.price || '—')}</td>
            <td style="text-align:right;">
              <button class="btn-sm" onclick="viewAdminGeneration(${g.id})"><i class="bi bi-eye"></i> View</button>
              <button class="btn-sm danger" onclick="deleteAdminGeneration(${g.id})"><i class="bi bi-trash3"></i></button>
            </td>
          </tr>`).join('')}
      </tbody>
    </table>`;
  } catch {
    c.innerHTML = `<div class="empty-card"><i class="bi bi-exclamation-triangle"></i><p>Could not load generations</p></div>`;
  }
}

async function viewAdminGeneration(id) {
  try {
    const res = await fetch(`/api/admin/generations/${id}`, { credentials: 'include' });
    const data = await res.json();
    if (!data.generation) return;
    const g = data.generation;
    let ads = []; try { ads = JSON.parse(g.ads || '[]'); } catch {}
    let imgs = []; try { imgs = JSON.parse(g.images || '[]'); } catch {}

    document.getElementById('modalTitle').textContent =
      `${g.suburb || 'Property'} · by ${g.full_name || g.username}`;
    document.getElementById('modalBody').innerHTML = `
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px;">
        <span class="badge badge-info">${escapeHtml(g.tone || '—')}</span>
        ${g.beds  ? `<span class="badge badge-secondary">${escapeHtml(g.beds)} bed</span>` : ''}
        ${g.baths ? `<span class="badge badge-secondary">${escapeHtml(g.baths)} bath</span>` : ''}
        ${g.price ? `<span class="badge badge-secondary">${escapeHtml(g.price)}</span>` : ''}
        <span class="badge badge-secondary">${formatDate(g.created_at)}</span>
      </div>
      ${imgs.length ? `<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px;">${imgs.map(i => `<img src="/uploads/${encodeURIComponent(i)}" style="width:60px;height:60px;object-fit:cover;border-radius:6px;border:1px solid var(--border);"/>`).join('')}</div>` : ''}
      <h4 style="font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:var(--muted);margin-bottom:8px;">Listing</h4>
      <div style="background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:16px;font-size:0.88rem;line-height:1.7;white-space:pre-wrap;color:var(--ink-2);">${escapeHtml(g.listing || '')}</div>
      ${ads.length ? `<h4 style="font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:var(--muted);margin-bottom:8px;">Ads</h4>` : ''}
      ${ads.map((ad, i) => `
        <div style="background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:12px;margin-bottom:8px;font-size:0.84rem;line-height:1.6;white-space:pre-wrap;color:var(--ink-2);">
          <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;color:var(--muted);margin-bottom:6px;">Variation ${i + 1}</div>
          ${escapeHtml(ad)}
        </div>`).join('')}`;
    document.getElementById('modalFoot').innerHTML = `
      <button class="btn-sm" onclick="closeModal()">Close</button>`;
    openModal();
  } catch {
    showToast('Could not load generation', 'error');
  }
}

async function deleteAdminGeneration(id) {
  if (!confirm('Delete this generation? This cannot be undone.')) return;
  try {
    await fetch(`/api/admin/generations/${id}`, { method: 'DELETE', credentials: 'include' });
    showToast('Deleted', 'success');
    loadGenerations();
  } catch {
    showToast('Delete failed', 'error');
  }
}

// ═══════ TEMPLATES ═══════
async function loadTemplates() {
  const c = document.getElementById('templatesContainer');
  try {
    const res = await fetch('/api/admin/templates', { credentials: 'include' });
    const data = await res.json();
    cachedTemplates = data.templates || [];
    if (!cachedTemplates.length) {
      c.innerHTML = `<div class="empty-card"><i class="bi bi-file-earmark-text"></i><p>No templates yet</p></div>`;
      return;
    }
    c.innerHTML = `<table class="data-table">
      <thead>
        <tr><th>Name</th><th>Tone</th><th>Description</th><th>Status</th><th></th></tr>
      </thead>
      <tbody>
        ${cachedTemplates.map(t => `
          <tr>
            <td><strong>${escapeHtml(t.name)}</strong></td>
            <td><span class="badge badge-info">${escapeHtml(t.tone)}</span></td>
            <td style="color:var(--muted);font-size:0.82rem;">${escapeHtml(t.description || '—')}</td>
            <td><span class="badge ${t.is_active ? 'badge-success' : 'badge-secondary'}">${t.is_active ? 'Active' : 'Disabled'}</span></td>
            <td style="text-align:right;">
              <button class="btn-sm" onclick="editTemplate(${t.id})"><i class="bi bi-pencil"></i> Edit</button>
              <button class="btn-sm danger" onclick="deleteTemplate(${t.id})"><i class="bi bi-trash3"></i></button>
            </td>
          </tr>`).join('')}
      </tbody>
    </table>`;
  } catch {
    c.innerHTML = `<div class="empty-card"><i class="bi bi-exclamation-triangle"></i><p>Could not load templates</p></div>`;
  }
}

function showAddTemplateModal() {
  document.getElementById('modalTitle').textContent = 'New template';
  document.getElementById('modalBody').innerHTML = templateFormHtml({});
  document.getElementById('modalFoot').innerHTML = `
    <button class="btn-sm" onclick="closeModal()">Cancel</button>
    <button class="btn-sm primary" onclick="submitTemplate(null)"><i class="bi bi-check-lg"></i> Create</button>`;
  openModal();
}

function editTemplate(id) {
  const t = cachedTemplates.find(x => x.id === id);
  if (!t) return;
  document.getElementById('modalTitle').textContent = 'Edit template';
  document.getElementById('modalBody').innerHTML = templateFormHtml(t);
  document.getElementById('modalFoot').innerHTML = `
    <button class="btn-sm" onclick="closeModal()">Cancel</button>
    <button class="btn-sm primary" onclick="submitTemplate(${id})"><i class="bi bi-check-lg"></i> Save</button>`;
  openModal();
}

function templateFormHtml(t) {
  return `
    <div class="modal-field">
      <label>Name *</label>
      <input class="modal-input" id="t_name" value="${escapeAttr(t.name || '')}" placeholder="Professional Standard"/>
    </div>
    <div class="modal-row">
      <div class="modal-field">
        <label>Tone *</label>
        <select class="modal-input" id="t_tone">
          ${['professional','luxury','family','investment','short'].map(x =>
            `<option value="${x}" ${t.tone === x ? 'selected' : ''}>${x}</option>`).join('')}
        </select>
      </div>
      <div class="modal-field">
        <label>Active</label>
        <select class="modal-input" id="t_active">
          <option value="1" ${t.is_active !== 0 ? 'selected' : ''}>Yes</option>
          <option value="0" ${t.is_active === 0 ? 'selected' : ''}>No</option>
        </select>
      </div>
    </div>
    <div class="modal-field">
      <label>Description</label>
      <input class="modal-input" id="t_desc" value="${escapeAttr(t.description || '')}" placeholder="When to use this template"/>
    </div>
    <div class="modal-field">
      <label>Content *</label>
      <textarea class="modal-input" id="t_content" rows="5" placeholder="Welcome to {suburb}. This {beds} bedroom...">${escapeHtml(t.content || '')}</textarea>
      <div class="help">You can use placeholders like <code>{suburb}</code>, <code>{beds}</code>, <code>{baths}</code>, <code>{prop_type}</code>.</div>
    </div>`;
}

async function submitTemplate(id) {
  const body = {
    name:        document.getElementById('t_name').value.trim(),
    tone:        document.getElementById('t_tone').value,
    description: document.getElementById('t_desc').value.trim(),
    content:     document.getElementById('t_content').value.trim(),
    is_active:   document.getElementById('t_active').value === '1',
  };
  if (!body.name || !body.content) {
    showToast('Name and content are required', 'error');
    return;
  }
  try {
    const url = id ? `/api/admin/templates/${id}` : '/api/admin/templates';
    const method = id ? 'PUT' : 'POST';
    const res = await fetch(url, {
      method, credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) { showToast(data.error || 'Save failed', 'error'); return; }
    showToast(id ? 'Template updated' : 'Template created', 'success');
    closeModal();
    loadTemplates();
  } catch {
    showToast('Save failed', 'error');
  }
}

async function deleteTemplate(id) {
  if (!confirm('Delete this template?')) return;
  try {
    await fetch(`/api/admin/templates/${id}`, { method: 'DELETE', credentials: 'include' });
    showToast('Template deleted', 'success');
    loadTemplates();
  } catch {
    showToast('Delete failed', 'error');
  }
}

// ═══════ COMPLIANCE ═══════
async function loadCompliance() {
  const c = document.getElementById('complianceContainer');
  try {
    const res = await fetch('/api/admin/compliance', { credentials: 'include' });
    const data = await res.json();
    cachedRules = data.rules || [];
    if (!cachedRules.length) {
      c.innerHTML = `<div class="empty-card"><i class="bi bi-shield"></i><p>No compliance rules</p></div>`;
      return;
    }
    c.innerHTML = `<table class="data-table">
      <thead>
        <tr><th>Rule</th><th>Severity</th><th>Pattern</th><th>Message</th><th>Status</th><th></th></tr>
      </thead>
      <tbody>
        ${cachedRules.map(r => `
          <tr>
            <td><strong>${escapeHtml(r.rule_name)}</strong></td>
            <td><span class="badge ${r.severity === 'error' ? 'badge-danger' : 'badge-warning'}">${escapeHtml(r.severity)}</span></td>
            <td style="font-family:ui-monospace, monospace;font-size:0.78rem;color:var(--ink-2);max-width:200px;word-break:break-all;">${escapeHtml(r.pattern)}</td>
            <td style="color:var(--muted);font-size:0.82rem;max-width:280px;">${escapeHtml(r.message)}</td>
            <td><span class="badge ${r.is_active ? 'badge-success' : 'badge-secondary'}">${r.is_active ? 'Active' : 'Disabled'}</span></td>
            <td style="text-align:right;">
              <button class="btn-sm" onclick="editRule(${r.id})"><i class="bi bi-pencil"></i></button>
              <button class="btn-sm danger" onclick="deleteRule(${r.id})"><i class="bi bi-trash3"></i></button>
            </td>
          </tr>`).join('')}
      </tbody>
    </table>`;
  } catch {
    c.innerHTML = `<div class="empty-card"><i class="bi bi-exclamation-triangle"></i><p>Could not load rules</p></div>`;
  }
}

function showAddComplianceModal() {
  document.getElementById('modalTitle').textContent = 'New compliance rule';
  document.getElementById('modalBody').innerHTML = ruleFormHtml({});
  document.getElementById('modalFoot').innerHTML = `
    <button class="btn-sm" onclick="closeModal()">Cancel</button>
    <button class="btn-sm primary" onclick="submitRule(null)"><i class="bi bi-check-lg"></i> Create</button>`;
  openModal();
}

function editRule(id) {
  const r = cachedRules.find(x => x.id === id);
  if (!r) return;
  document.getElementById('modalTitle').textContent = 'Edit compliance rule';
  document.getElementById('modalBody').innerHTML = ruleFormHtml(r);
  document.getElementById('modalFoot').innerHTML = `
    <button class="btn-sm" onclick="closeModal()">Cancel</button>
    <button class="btn-sm primary" onclick="submitRule(${id})"><i class="bi bi-check-lg"></i> Save</button>`;
  openModal();
}

function ruleFormHtml(r) {
  return `
    <div class="modal-field">
      <label>Rule name *</label>
      <input class="modal-input" id="r_name" value="${escapeAttr(r.rule_name || '')}" placeholder="No price baiting"/>
    </div>
    <div class="modal-row">
      <div class="modal-field">
        <label>Severity *</label>
        <select class="modal-input" id="r_severity">
          <option value="warning" ${r.severity === 'warning' ? 'selected' : ''}>Warning</option>
          <option value="error" ${r.severity === 'error' ? 'selected' : ''}>Error</option>
        </select>
      </div>
      <div class="modal-field">
        <label>Active</label>
        <select class="modal-input" id="r_active">
          <option value="1" ${r.is_active !== 0 ? 'selected' : ''}>Yes</option>
          <option value="0" ${r.is_active === 0 ? 'selected' : ''}>No</option>
        </select>
      </div>
    </div>
    <div class="modal-field">
      <label>Regex pattern *</label>
      <input class="modal-input" id="r_pattern" value="${escapeAttr(r.pattern || '')}" placeholder="\\b(starting from|from only)\\b" style="font-family:ui-monospace,monospace;"/>
      <div class="help">Case-insensitive regex. Use <code>\\b</code> for word boundaries.</div>
    </div>
    <div class="modal-field">
      <label>Message *</label>
      <textarea class="modal-input" id="r_message" rows="3" placeholder="Avoid 'starting from' — may breach underquoting laws.">${escapeHtml(r.message || '')}</textarea>
    </div>`;
}

async function submitRule(id) {
  const body = {
    rule_name: document.getElementById('r_name').value.trim(),
    pattern:   document.getElementById('r_pattern').value.trim(),
    severity:  document.getElementById('r_severity').value,
    message:   document.getElementById('r_message').value.trim(),
    is_active: document.getElementById('r_active').value === '1',
  };
  if (!body.rule_name || !body.pattern || !body.message) {
    showToast('All fields are required', 'error');
    return;
  }
  // Validate regex on client side
  try { new RegExp(body.pattern); }
  catch (e) { showToast('Invalid regex: ' + e.message, 'error'); return; }

  try {
    const url = id ? `/api/admin/compliance/${id}` : '/api/admin/compliance';
    const method = id ? 'PUT' : 'POST';
    const res = await fetch(url, {
      method, credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) { showToast(data.error || 'Save failed', 'error'); return; }
    showToast(id ? 'Rule updated' : 'Rule created', 'success');
    closeModal();
    loadCompliance();
  } catch {
    showToast('Save failed', 'error');
  }
}

async function deleteRule(id) {
  if (!confirm('Delete this rule?')) return;
  try {
    await fetch(`/api/admin/compliance/${id}`, { method: 'DELETE', credentials: 'include' });
    showToast('Rule deleted', 'success');
    loadCompliance();
  } catch {
    showToast('Delete failed', 'error');
  }
}

// ═══════ MODAL ═══════
function openModal() { document.getElementById('modalOverlay').classList.add('open'); }
function closeModal() { document.getElementById('modalOverlay').classList.remove('open'); }

// ═══════ TOAST ═══════
let toastTimer = null;
function showToast(msg, type = '') {
  const tEl = document.getElementById('toast');
  tEl.className = 'toast ' + type;
  tEl.innerHTML = `<i class="bi bi-${type === 'success' ? 'check-circle-fill' : type === 'error' ? 'exclamation-circle-fill' : 'info-circle-fill'}"></i> ${escapeHtml(msg)}`;
  requestAnimationFrame(() => tEl.classList.add('show'));
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => tEl.classList.remove('show'), 3500);
}

// ═══════ HELPERS ═══════
function escapeHtml(s) {
  if (s == null) return '';
  return String(s)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}
function escapeAttr(s) { return escapeHtml(s); }
function formatDate(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' }); }
  catch { return iso; }
}
function formatRelative(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const sec = (Date.now() - d.getTime()) / 1000;
    if (sec < 60) return 'Just now';
    if (sec < 3600) return Math.floor(sec / 60) + 'm ago';
    if (sec < 86400) return Math.floor(sec / 3600) + 'h ago';
    if (sec < 604800) return Math.floor(sec / 86400) + 'd ago';
    return formatDate(iso);
  } catch { return iso; }
}

// ═══════ INIT ═══════
document.addEventListener('DOMContentLoaded', async () => {
  const ok = await checkAuth();
  if (!ok) return;
  loadOverview();
});
