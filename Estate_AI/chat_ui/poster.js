/* ═══════════════════════════════════════════════════════════════
   POSTER FEATURE  ·  Estate AI / APDG
   Builds shareable social-media posters from generated listing data.
   Depends on:
     - lastResult / window.lastResult       (set by script.js after /upload)
     - selectedFiles / window.selectedFiles (uploaded File objects)
     - html2canvas                          (loaded via CDN, see index.html)
═══════════════════════════════════════════════════════════════ */

(function () {
  // ─── State ────────────────────────────────────────────────
  const state = {
    format: 'square',          // square | landscape | story
    accent: '#16a34a',         // brand accent (matches system green)
    accent2: '#15803d',        // darker shade derived
    heroIndex: 0,              // which uploaded image to feature
  };

  const PRESET_COLORS = [
    { primary: '#16a34a', dark: '#15803d', label: 'Green'   },
    { primary: '#ea580c', dark: '#c2410c', label: 'Orange'  },
    { primary: '#2563eb', dark: '#1d4ed8', label: 'Blue'    },
    { primary: '#7c3aed', dark: '#6d28d9', label: 'Purple'  },
    { primary: '#0f172a', dark: '#020617', label: 'Charcoal'},
  ];

  // Try a few candidate translation keys; fall back to default
  function tx(keys, fallback) {
    if (typeof window.t === 'function') {
      for (const k of keys) {
        const v = window.t(k);
        if (v && v !== k) return v;
      }
    }
    return fallback;
  }

  // ─── Public init: builds controls + empty preview ────────
  function initPoster() {
    const tab = document.getElementById('tabPoster');
    if (!tab) return;
    tab.innerHTML = `
      <div class="poster-controls">
        <div class="ctrl-group">
          <span class="ctrl-label">${tx(['poster_format'], 'Format')}</span>
          <div class="format-grid" id="posterFormatGrid">
            <button class="format-btn active" data-fmt="square">
              <i class="bi bi-instagram"></i>
              <span>Square <span class="fmt-dim">1:1</span></span>
            </button>
            <button class="format-btn" data-fmt="landscape">
              <i class="bi bi-facebook"></i>
              <span>Landscape <span class="fmt-dim">1.91:1</span></span>
            </button>
            <button class="format-btn" data-fmt="story">
              <i class="bi bi-phone"></i>
              <span>Story <span class="fmt-dim">9:16</span></span>
            </button>
          </div>
        </div>

        <div class="ctrl-group">
          <span class="ctrl-label">${tx(['poster_accent'], 'Accent')}</span>
          <div class="color-swatches" id="posterSwatches"></div>
        </div>

        <div class="ctrl-group">
          <span class="ctrl-label">${tx(['poster_hero'], 'Hero image')}</span>
          <select id="posterHeroSelect" class="format-btn" style="padding:8px 10px;cursor:pointer;">
            <option value="0">${tx(['poster_first_photo'], 'First uploaded photo')}</option>
          </select>
        </div>

        <div class="poster-actions">
          <button class="btn-sm" id="posterRegenBtn">
            <i class="bi bi-arrow-clockwise"></i> ${tx(['poster_refresh'], 'Refresh')}
          </button>
          <button class="btn-sm primary" id="posterDlBtn">
            <i class="bi bi-download"></i> ${tx(['poster_download'], 'Download PNG')}
          </button>
        </div>
      </div>

      <div class="poster-stage" id="posterStage">
        <div class="poster-empty-state">
          <i class="bi bi-image"></i>
          <div>${tx(['poster_empty'], 'Generate a listing first to preview your poster.')}</div>
        </div>
      </div>
    `;

    // Render swatches
    const swatchEl = document.getElementById('posterSwatches');
    swatchEl.innerHTML = PRESET_COLORS.map((c, i) => `
      <div class="swatch ${i === 0 ? 'active' : ''}"
           style="background:${c.primary}"
           data-idx="${i}"
           title="${c.label}"></div>
    `).join('');

    // Wire events
    document.getElementById('posterFormatGrid').addEventListener('click', (e) => {
      const btn = e.target.closest('.format-btn');
      if (!btn) return;
      document.querySelectorAll('#posterFormatGrid .format-btn')
        .forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.format = btn.dataset.fmt;
      renderPoster();
    });

    swatchEl.addEventListener('click', (e) => {
      const sw = e.target.closest('.swatch');
      if (!sw) return;
      const idx = parseInt(sw.dataset.idx, 10);
      document.querySelectorAll('#posterSwatches .swatch')
        .forEach(s => s.classList.remove('active'));
      sw.classList.add('active');
      state.accent  = PRESET_COLORS[idx].primary;
      state.accent2 = PRESET_COLORS[idx].dark;
      renderPoster();
    });

    document.getElementById('posterHeroSelect').addEventListener('change', (e) => {
      state.heroIndex = parseInt(e.target.value, 10) || 0;
      renderPoster();
    });

    document.getElementById('posterRegenBtn').addEventListener('click', renderPoster);
    document.getElementById('posterDlBtn').addEventListener('click', downloadPoster);
  }

  // ─── Build content from lastResult ──────────────────────
  function buildContent() {
    const data = (typeof lastResult !== 'undefined' && lastResult) ? lastResult
               : (window.lastResult || null);
    if (!data) return null;

    const details = data.details || {};
    const listing = (data.content && data.content.listing) || data.final_description || '';
    const images  = (data.images || []).filter(i => !i.is_invalid && !i.is_floor_plan);

    const suburb = details.suburb || '';
    const propType = details.prop_type || 'Property';

    const beds    = parseInt(details.beds, 10)    || 0;
    const baths   = parseInt(details.baths, 10)   || 0;
    const parking = parseInt(details.parking, 10) || 0;

    const price    = (details.price || '').trim();
    const landSize = (details.land_size || '').trim();

    // Headline description: trim to format-appropriate length
    const trimmed = listing.replace(/\s+/g, ' ').trim();
    const maxLen = state.format === 'landscape' ? 180
                 : state.format === 'story'     ? 380
                 : 280;
    let blurb = trimmed;
    if (trimmed.length > maxLen) {
      const sentences = trimmed.match(/[^.!?]+[.!?]+/g) || [trimmed];
      blurb = '';
      for (const s of sentences) {
        if ((blurb + s).length > maxLen) break;
        blurb += s;
      }
      if (!blurb) blurb = trimmed.slice(0, maxLen) + '…';
    }
    if (!blurb) {
      blurb = data.room_description || tx(['poster_default_blurb'],
        'A beautifully presented home in a sought-after location, ready to welcome its next chapter.');
    }

    // Feature bullets from detected objects + tone-based extras
    const objs = (data.all_objects || []).slice(0, 6);
    const tone = details.tone || 'professional';
    const extras = {
      professional: ['Quality finishes throughout', 'Move-in ready condition'],
      luxury:       ['Premium fittings and finishes', 'Designer-led interiors'],
      family:       ['Family-friendly layout', 'Close to schools & parks'],
      investment:   ['Strong rental potential', 'High-growth location'],
    }[tone] || [];

    const objPhrases = objs.map(o => prettyFeature(o)).filter(Boolean).slice(0, 4);
    const features = [...new Set([...objPhrases, ...extras])].slice(0, 6);

    return {
      suburb, propType, beds, baths, parking,
      price, landSize, blurb, features, images, tone,
    };
  }

  function prettyFeature(obj) {
    const map = {
      'tv':            'Entertainment-ready living',
      'couch':         'Spacious lounge area',
      'sofa':          'Spacious lounge area',
      'bed':           'Comfortable bedrooms',
      'dining table':  'Open-plan dining',
      'oven':          'Modern kitchen appliances',
      'microwave':     'Modern kitchen appliances',
      'refrigerator':  'Modern kitchen appliances',
      'sink':          'Quality kitchen fittings',
      'toilet':        'Updated bathrooms',
      'potted plant':  'Landscaped surrounds',
      'car':           'Off-street parking',
      'chair':         'Stylish furnishings',
    };
    return map[obj.toLowerCase()] || null;
  }

  // ─── Render the poster preview ───────────────────────────
  function renderPoster() {
    const stage = document.getElementById('posterStage');
    if (!stage) return;

    const c = buildContent();
    if (!c) {
      stage.innerHTML = `
        <div class="poster-empty-state">
          <i class="bi bi-image"></i>
          <div>${tx(['poster_empty'], 'Generate a listing first to preview your poster.')}</div>
        </div>`;
      return;
    }

    // Refresh hero dropdown
    const heroSel = document.getElementById('posterHeroSelect');
    if (heroSel && c.images.length) {
      heroSel.innerHTML = c.images.map((img, i) =>
        `<option value="${i}" ${i === state.heroIndex ? 'selected' : ''}>
           ${(img.room || 'Photo')} · ${img.filename}
         </option>`
      ).join('');
    }

    // Resolve hero image src — prefer File blob URL (no CORS)
    let heroSrc = '';
    if (c.images.length) {
      const idx = Math.min(state.heroIndex, c.images.length - 1);
      const img = c.images[idx];
      const filesArr = (typeof selectedFiles !== 'undefined' && selectedFiles)
                     ? selectedFiles
                     : (window.selectedFiles || []);
      const fileObj = filesArr.find(f => f.name === img.filename);
      heroSrc = fileObj ? URL.createObjectURL(fileObj) : img.image_url;
    }

    const beds    = c.beds    || '—';
    const baths   = c.baths   || '—';
    const parking = c.parking || '—';
    const stageBadge = (c.tone || '').toUpperCase();

    const addressLine = c.suburb
      ? `${c.suburb}, SA`
      : tx(['poster_addr_placeholder'], 'Premium property listing');

    const featureHtml = c.features.map(f => `
      <div class="feature-item">
        <i class="bi bi-check-circle-fill"></i>
        <span>${escapeHtml(f)}</span>
      </div>
    `).join('');

    const heroHtml = heroSrc
      ? `<img src="${heroSrc}" alt="" crossorigin="anonymous"/>`
      : `<div class="poster-hero-empty">
           <i class="bi bi-house"></i>
           <span>No photo selected</span>
         </div>`;

    const initials = (c.suburb || c.propType || 'AP').slice(0, 2).toUpperCase();

    stage.innerHTML = `
      <div class="poster-wrap">
        <div class="poster fmt-${state.format}"
             style="--accent:${state.accent};--accent-2:${state.accent2};"
             id="posterRoot">

          <div class="poster-header">
            <div class="poster-brand">
              <div class="poster-brand-logo"><i class="bi bi-houses-fill"></i></div>
              <div class="poster-brand-text">
                <div class="brand-1">APDG</div>
                <div class="brand-2">Smart Descriptions</div>
              </div>
            </div>
            <div class="poster-tagline">
              <strong>AI-Powered</strong> Listing<br/>
              Marketing-Focused · Buyer-Targeted
            </div>
          </div>

          <div class="poster-hero">
            ${heroHtml}
            <div class="poster-address-chip">
              <i class="bi bi-geo-alt-fill"></i>
              <span>${escapeHtml(addressLine)}</span>
            </div>
            ${stageBadge ? `<div class="poster-stage-badge">${escapeHtml(stageBadge)}</div>` : ''}
          </div>

          <div class="poster-body">
            <div class="poster-price-block">
              <div>
                <div class="price-eyebrow">${escapeHtml(c.propType)}</div>
                <div class="price-amount">${escapeHtml(c.price || 'Contact Agent')}</div>
                <div class="price-sub">${
                  c.landSize ? `Land ${escapeHtml(c.landSize)}` : 'Available now'
                }</div>
              </div>
              ${c.price ? `<div class="fixed-tag">For Sale</div>` : ''}
            </div>

            <div class="poster-specs">
              <div class="spec-item"><i class="bi bi-door-open"></i> ${beds} Beds</div>
              <div class="spec-item"><i class="bi bi-droplet"></i> ${baths} Baths</div>
              <div class="spec-item"><i class="bi bi-car-front"></i> ${parking} Parking</div>
            </div>

            <div class="poster-desc-label">About this property</div>
            <div class="poster-desc">${escapeHtml(c.blurb)}</div>

            ${c.features.length ? `<div class="poster-features">${featureHtml}</div>` : ''}

            <div class="poster-footer">
              <div class="footer-left">
                <div class="footer-tag">${initials}</div>
                <div class="footer-text">
                  <strong>Generated with APDG</strong>
                  AI-Based Auto Property Description Generator
                </div>
              </div>
              <div class="footer-right">
                Smarter Descriptions<br/>Better Listings
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    // Scale to fit stage width on smaller screens
    requestAnimationFrame(scaleToFit);
  }

  function scaleToFit() {
    const wrap = document.querySelector('.poster-wrap');
    const stage = document.getElementById('posterStage');
    const poster = document.getElementById('posterRoot');
    if (!wrap || !stage || !poster) return;
    const stageW = stage.clientWidth - 48; // padding
    const posterW = poster.offsetWidth;
    const scale = posterW > stageW ? stageW / posterW : 1;
    wrap.style.transform = `scale(${scale})`;
    wrap.style.height = (poster.offsetHeight * scale) + 'px';
    wrap.style.width  = posterW + 'px';
  }

  window.addEventListener('resize', scaleToFit);

  // ─── Download as PNG via html2canvas ────────────────────
  async function downloadPoster() {
    const poster = document.getElementById('posterRoot');
    if (!poster) {
      if (window.showToast) window.showToast('Generate a listing first.', 'error');
      return;
    }
    if (typeof html2canvas !== 'function') {
      alert('Image export library failed to load. Check your internet connection.');
      return;
    }

    const btn = document.getElementById('posterDlBtn');
    const orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<i class="bi bi-hourglass-split"></i> Rendering...`;

    // Format-specific true dimensions
    const dims = {
      square:    { w: 1080, h: 1080 },
      landscape: { w: 1200, h: 630  },
      story:     { w: 1080, h: 1920 },
    }[state.format] || { w: 1080, h: 1080 };

    // Save full inline style of the wrap so we can restore exactly
    const wrap = poster.parentElement;
    const savedStyle = wrap.getAttribute('style') || '';

    // Force wrap to true poster size (no scale)
    wrap.setAttribute('style', `transform: none; width: ${dims.w}px; height: ${dims.h}px;`);

    // Wait for hero image to load
    const heroImg = poster.querySelector('.poster-hero img');
    if (heroImg && !(heroImg.complete && heroImg.naturalWidth > 0)) {
      await new Promise(resolve => {
        heroImg.onload  = resolve;
        heroImg.onerror = resolve;
        setTimeout(resolve, 4000);
      });
    }

    // Force layout flush before capture
    void poster.offsetHeight;

    let success = false;
    try {
      const canvas = await html2canvas(poster, {
        backgroundColor: '#ffffff',
        scale: 2,
        useCORS: true,
        allowTaint: true,
        logging: false,
        width:  dims.w,
        height: dims.h,
        windowWidth:  dims.w,
        windowHeight: dims.h,
      });
      const url = canvas.toDataURL('image/png');
      const a = document.createElement('a');
      const stamp = new Date().toISOString().slice(0, 10);
      a.href = url;
      a.download = `apdg-poster-${state.format}-${stamp}.png`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      success = true;
    } catch (err) {
      console.error('Poster export failed:', err);
      if (window.showToast) window.showToast('Export failed: ' + err.message, 'error');
      else alert('Export failed: ' + err.message);
    }

    // Restore wrap's original inline style EXACTLY
    wrap.setAttribute('style', savedStyle);

    // Re-render the poster to guarantee a clean preview state
    renderPoster();

    btn.disabled = false;
    btn.innerHTML = orig;

    if (success && window.showToast) window.showToast('Poster downloaded ✓', 'success');
  }

  // ─── Util ───────────────────────────────────────────────
  function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // ─── Public API ─────────────────────────────────────────
  window.initPoster   = initPoster;
  window.renderPoster = renderPoster;

  // Auto-init when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPoster);
  } else {
    initPoster();
  }
})();