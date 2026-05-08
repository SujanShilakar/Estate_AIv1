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
          <span class="ctrl-label">${tx(['poster_featured'], 'Featured photo')}</span>
          <select id="posterHeroSelect" class="format-btn" style="padding:8px 10px;cursor:pointer;">
            <option value="0">${tx(['poster_first_photo'], 'First uploaded photo')}</option>
          </select>
        </div>

        <div class="poster-actions">
          <button class="btn-sm" id="posterShareBtn">
            <i class="bi bi-share-fill"></i> ${tx(['poster_share'], 'Share')}
          </button>
          <button class="btn-sm primary" id="posterDlBtn">
            <i class="bi bi-download"></i> ${tx(['poster_download'], 'Download')}
          </button>
          <div class="share-menu" id="posterShareMenu"></div>
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

    document.getElementById('posterShareBtn').addEventListener('click', toggleShareMenu);
    document.getElementById('posterDlBtn').addEventListener('click', () => downloadPoster());

    // Close share menu on outside click
    document.addEventListener('click', (e) => {
      const menu = document.getElementById('posterShareMenu');
      const btn  = document.getElementById('posterShareBtn');
      if (!menu || !btn) return;
      if (menu.classList.contains('open')
          && !menu.contains(e.target)
          && !btn.contains(e.target)) {
        menu.classList.remove('open');
      }
    });
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

    // Parse the full listing text into paragraphs and highlights
    const listingText = (data.room_description && data.room_description.trim())
                      || listing
                      || '';

    let descParagraphs = [];
    let highlights = [];

    if (listingText) {
      const rawLines = listingText.split('\n');
      let currentPara = [];
      let inHighlights = false;

      for (const line of rawLines) {
        const trimmed = line.trim();
        if (/^The Highlights\s*[:\-]?\s*$/i.test(trimmed)) {
          if (currentPara.length) {
            descParagraphs.push(currentPara.join(' ').trim());
            currentPara = [];
          }
          inHighlights = true;
          continue;
        }
        if (inHighlights) {
          const m = trimmed.match(/^[-•*]\s*(.+)/);
          if (m) highlights.push(m[1].trim());
        } else if (trimmed) {
          currentPara.push(trimmed);
        } else if (currentPara.length) {
          descParagraphs.push(currentPara.join(' ').trim());
          currentPara = [];
        }
      }
      if (currentPara.length) descParagraphs.push(currentPara.join(' ').trim());
    }

    // Fallback if nothing parsed
    if (!descParagraphs.length && !highlights.length && listingText) {
      const sentences = listingText.replace(/\s+/g, ' ').trim().match(/[^.!?]+[.!?]+/g) || [listingText];
      descParagraphs = [sentences.slice(0, 4).join(' ').trim()];
    }
    if (!descParagraphs.length) {
      descParagraphs = [tx(['poster_default_blurb'],
        'A beautifully presented home in a sought-after location, ready to welcome its next chapter.')];
    }

    // Limit content for landscape (less vertical space)
    const maxParas = state.format === 'landscape' ? 2 : descParagraphs.length;

    const tone = details.tone || 'professional';

    return {
      suburb, propType, beds, baths, parking,
      price, landSize,
      descParagraphs: descParagraphs.slice(0, maxParas),
      highlights,
      images, tone,
    };
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

    // Resolve hero image sources for collage — prefer File blob URLs (no CORS)
    const filesArr = (typeof selectedFiles !== 'undefined' && selectedFiles)
                   ? selectedFiles
                   : (window.selectedFiles || []);

    // Build the photo list, starting from heroIndex (so user's chosen photo leads)
    const photoSrcs = [];
    if (c.images.length) {
      const order = [];
      const startIdx = Math.min(state.heroIndex, c.images.length - 1);
      order.push(startIdx);
      for (let i = 0; i < c.images.length; i++) {
        if (i !== startIdx) order.push(i);
      }
      for (const i of order) {
        const img = c.images[i];
        const fileObj = filesArr.find(f => f.name === img.filename);
        photoSrcs.push(fileObj ? URL.createObjectURL(fileObj) : img.image_url);
      }
    }

    // Decide collage cell count based on format
    // We always show: 1 big + up to 3 small = max 4 cells. Overflow goes on last cell as "+N".
    const maxCells = 4;
    const visibleCount = Math.min(photoSrcs.length, maxCells);
    const overflow = Math.max(0, photoSrcs.length - visibleCount);
    const countClass = visibleCount <= 1 ? 'count-1'
                     : visibleCount === 2 ? 'count-2'
                     : visibleCount === 3 ? 'count-3'
                     : 'count-4';

    const beds    = c.beds    || '—';
    const baths   = c.baths   || '—';
    const parking = c.parking || '—';
    const stageBadge = (c.tone || '').toUpperCase();

    const addressLine = c.suburb
      ? `${c.suburb}, SA`
      : tx(['poster_addr_placeholder'], 'Premium property listing');

    const descHtml = c.descParagraphs.map(p =>
      `<p class="poster-desc-para">${escapeHtml(p)}</p>`
    ).join('');

    const highlightsHtml = c.highlights.length ? `
      <div class="poster-highlights">
        <div class="poster-highlights-label">The Highlights:</div>
        ${c.highlights.map(h => `<div class="poster-highlight-item">- ${escapeHtml(h)}</div>`).join('')}
      </div>
    ` : '';

    // Build collage HTML
    let heroHtml;
    if (visibleCount === 0) {
      heroHtml = `<div class="poster-hero-empty">
                    <i class="bi bi-house"></i>
                    <span>No photos uploaded</span>
                  </div>`;
    } else {
      const cells = [];
      for (let i = 0; i < visibleCount; i++) {
        const isLast = (i === visibleCount - 1);
        const showOverlay = isLast && overflow > 0;
        cells.push(`
          <div class="col-cell">
            <img src="${photoSrcs[i]}" alt="" crossorigin="anonymous"/>
            ${showOverlay ? `<div class="col-more-overlay">+${overflow}</div>` : ''}
          </div>
        `);
      }
      heroHtml = `<div class="poster-collage ${countClass}">${cells.join('')}</div>`;
    }

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
            <div class="poster-desc">${descHtml}</div>

            ${highlightsHtml}

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

  // ─── Render poster as PNG blob (used by both download + share) ────
  async function renderPosterBlob() {
    const poster = document.getElementById('posterRoot');
    if (!poster) return null;
    if (typeof html2canvas !== 'function') return null;

    const dims = {
      square:    { w: 1080, h: 1080 },
      landscape: { w: 1200, h: 630  },
      story:     { w: 1080, h: 1920 },
    }[state.format] || { w: 1080, h: 1080 };

    const wrap = poster.parentElement;
    const savedStyle = wrap.getAttribute('style') || '';
    wrap.setAttribute('style', `transform: none; width: ${dims.w}px; height: ${dims.h}px;`);

    // Wait for ALL collage images to load
    const imgs = poster.querySelectorAll('.poster-collage img');
    await Promise.all(Array.from(imgs).map(img => {
      if (img.complete && img.naturalWidth > 0) return Promise.resolve();
      return new Promise(resolve => {
        img.onload  = resolve;
        img.onerror = resolve;
        setTimeout(resolve, 4000);
      });
    }));

    void poster.offsetHeight;

    let blob = null;
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
      blob = await new Promise(res => canvas.toBlob(res, 'image/png'));
    } catch (err) {
      console.error('Poster render failed:', err);
    }

    wrap.setAttribute('style', savedStyle);
    renderPoster();
    return blob;
  }

  // ─── Download as PNG ─────────────────────────────────────
  async function downloadPoster() {
    const btn = document.getElementById('posterDlBtn');
    const orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<i class="bi bi-hourglass-split"></i> Rendering...`;

    const blob = await renderPosterBlob();
    if (!blob) {
      btn.disabled = false;
      btn.innerHTML = orig;
      if (window.showToast) window.showToast('Could not render poster', 'error');
      return null;
    }

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const stamp = new Date().toISOString().slice(0, 10);
    a.href = url;
    a.download = `apdg-poster-${state.format}-${stamp}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);

    btn.disabled = false;
    btn.innerHTML = orig;
    if (window.showToast) window.showToast('Poster downloaded ✓', 'success');
    return blob;
  }

  // ─── Build a sharing caption from the listing data ───────
  function buildCaption() {
    const c = buildContent();
    if (!c) return '';
    const parts = [];
    const headline = c.suburb
      ? `🏡 New listing in ${c.suburb}`
      : `🏡 New property listing`;
    parts.push(headline);
    if (c.price) parts.push(`💰 ${c.price}`);
    const specs = [];
    if (c.beds)    specs.push(`${c.beds} bed`);
    if (c.baths)   specs.push(`${c.baths} bath`);
    if (c.parking) specs.push(`${c.parking} car`);
    if (specs.length) parts.push(`📐 ${specs.join(' · ')}`);
    parts.push('');
    parts.push(c.blurb);
    parts.push('');
    parts.push('#realestate #property #forsale' + (c.suburb ? ` #${c.suburb.replace(/\s+/g,'')}` : ''));
    return parts.join('\n');
  }

  // ─── Share menu ──────────────────────────────────────────
  function toggleShareMenu() {
    const menu = document.getElementById('posterShareMenu');
    if (!menu) return;
    if (menu.classList.contains('open')) {
      menu.classList.remove('open');
      return;
    }
    // Build menu fresh each time
    const hasNativeShare = typeof navigator.share === 'function';
    const supportsImageShare = hasNativeShare
      && typeof navigator.canShare === 'function';
    menu.innerHTML = `
      ${hasNativeShare ? `
        <div class="menu-label">Share with image</div>
        <button class="share-native">
          <i class="bi bi-phone"></i> Share via device…
        </button>
        <div class="menu-divider"></div>
      ` : ''}
      <div class="menu-label">Share caption only</div>
      <button class="fb share-fb">
        <i class="bi bi-facebook"></i> Facebook
      </button>
      <button class="wa share-wa">
        <i class="bi bi-whatsapp"></i> WhatsApp
      </button>
      <button class="tw share-tw">
        <i class="bi bi-twitter-x"></i> X (Twitter)
      </button>
      <button class="li share-li">
        <i class="bi bi-linkedin"></i> LinkedIn
      </button>
      <div class="menu-divider"></div>
      <button class="share-copy-cap">
        <i class="bi bi-clipboard"></i> Copy caption
      </button>
      <button class="share-copy-img">
        <i class="bi bi-images"></i> Copy image
      </button>
    `;
    menu.classList.add('open');

    // Wire menu actions
    menu.querySelector('.share-native')?.addEventListener('click', shareNative);
    menu.querySelector('.share-fb')?.addEventListener('click', shareFacebook);
    menu.querySelector('.share-wa')?.addEventListener('click', shareWhatsApp);
    menu.querySelector('.share-tw')?.addEventListener('click', shareTwitter);
    menu.querySelector('.share-li')?.addEventListener('click', shareLinkedIn);
    menu.querySelector('.share-copy-cap')?.addEventListener('click', copyCaption);
    menu.querySelector('.share-copy-img')?.addEventListener('click', copyImage);
  }

  function closeShareMenu() {
    document.getElementById('posterShareMenu')?.classList.remove('open');
  }

  // Native Web Share API — best path on mobile (IG, FB, WA, etc.)
  async function shareNative() {
    closeShareMenu();
    if (window.showToast) window.showToast('Preparing image…', 'info');
    const blob = await renderPosterBlob();
    if (!blob) return;
    const file = new File([blob], `apdg-poster-${state.format}.png`, { type: 'image/png' });
    const caption = buildCaption();
    const shareData = { files: [file], text: caption, title: 'Property Listing' };
    try {
      if (navigator.canShare && navigator.canShare(shareData)) {
        await navigator.share(shareData);
      } else if (navigator.share) {
        await navigator.share({ text: caption, title: 'Property Listing' });
      } else {
        if (window.showToast) window.showToast('Sharing not supported on this device', 'error');
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error('Share failed:', err);
        if (window.showToast) window.showToast('Share cancelled', 'info');
      }
    }
  }

  function shareFacebook() {
    closeShareMenu();
    const caption = encodeURIComponent(buildCaption());
    const url = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(window.location.origin)}&quote=${caption}`;
    window.open(url, '_blank', 'width=600,height=600');
    if (window.showToast) window.showToast('Tip: download the image too, then attach it in Facebook', 'info');
  }

  function shareWhatsApp() {
    closeShareMenu();
    const caption = encodeURIComponent(buildCaption());
    const url = `https://wa.me/?text=${caption}`;
    window.open(url, '_blank');
    if (window.showToast) window.showToast('Tip: download the image and attach it to your WhatsApp message', 'info');
  }

  function shareTwitter() {
    closeShareMenu();
    const caption = encodeURIComponent(buildCaption());
    const url = `https://twitter.com/intent/tweet?text=${caption}`;
    window.open(url, '_blank', 'width=600,height=600');
  }

  function shareLinkedIn() {
    closeShareMenu();
    const url = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(window.location.origin)}`;
    window.open(url, '_blank', 'width=600,height=600');
    if (window.showToast) window.showToast('Caption copied — paste it into LinkedIn', 'info');
    navigator.clipboard?.writeText(buildCaption()).catch(() => {});
  }

  async function copyCaption() {
    closeShareMenu();
    const caption = buildCaption();
    try {
      await navigator.clipboard.writeText(caption);
      if (window.showToast) window.showToast('Caption copied to clipboard ✓', 'success');
    } catch {
      if (window.showToast) window.showToast('Could not copy — your browser may block clipboard', 'error');
    }
  }

  async function copyImage() {
    closeShareMenu();
    if (!navigator.clipboard || !window.ClipboardItem) {
      if (window.showToast) window.showToast('Image clipboard not supported — use Download instead', 'error');
      return;
    }
    if (window.showToast) window.showToast('Preparing image…', 'info');
    const blob = await renderPosterBlob();
    if (!blob) return;
    try {
      await navigator.clipboard.write([
        new ClipboardItem({ 'image/png': blob })
      ]);
      if (window.showToast) window.showToast('Image copied — paste it anywhere ✓', 'success');
    } catch (err) {
      console.error('Image copy failed:', err);
      if (window.showToast) window.showToast('Could not copy image', 'error');
    }
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