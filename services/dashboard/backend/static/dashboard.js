// ── Sidebar filter helpers ───────────────────────────────────────────────────
function setStatus(val) {
  document.getElementById('status-hidden').value = val;
  document.getElementById('filter-form').submit();
}

// ── Card selection ───────────────────────────────────────────────────────────
function getSelected() {
  return [...document.querySelectorAll('.face-cb:checked')].map(cb => parseInt(cb.value));
}

function updateBar() {
  const n = getSelected().length;
  document.getElementById('sel-count-label').textContent = n + ' selezionati';
  document.getElementById('bulk-bar').classList.toggle('visible', n > 0);
  const btn = document.getElementById('sel-all-btn');
  const total = document.querySelectorAll('.face-cb').length;
  btn.textContent = (n === total && total > 0) ? 'Deseleziona tutto' : 'Seleziona pagina';
}

function toggleCard(card) {
  const cb = card.querySelector('.face-cb');
  cb.checked = !cb.checked;
  card.classList.toggle('selected', cb.checked);
  updateBar();
}

function syncCard(cb) {
  cb.closest('.face-card').classList.toggle('selected', cb.checked);
  updateBar();
}

function toggleAll() {
  const all = document.querySelectorAll('.face-cb');
  const anyUnchecked = [...all].some(cb => !cb.checked);
  all.forEach(cb => {
    cb.checked = anyUnchecked;
    cb.closest('.face-card').classList.toggle('selected', anyUnchecked);
  });
  updateBar();
}

function clearSelection() {
  document.querySelectorAll('.face-cb').forEach(cb => {
    cb.checked = false;
    cb.closest('.face-card').classList.remove('selected');
  });
  updateBar();
}

// ── Face grid: event delegation ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  const grid = document.getElementById('faces-grid');
  if (!grid) return;
  grid.addEventListener('click', function (e) {
    // Checkbox
    const cb = e.target.closest('.face-cb');
    if (cb) { syncCard(cb); return; }

    // Image → open lightbox
    const img = e.target.closest('.face-img');
    if (img) {
      const card = img.closest('.face-card');
      if (card) openLightFromCard(card);
      return;
    }

    // Card body → toggle selection
    const card = e.target.closest('.face-card');
    if (card) toggleCard(card);
  });
});

function openLightFromCard(card) {
  const id = card.dataset.id;
  const name = card.dataset.name || 'Sconosciuto';
  const score = parseFloat(card.dataset.score) || 0;
  const date = card.dataset.date || '';
  document.getElementById('lb-img').src = '/api/faces/' + id + '/image';
  document.getElementById('lb-name').textContent = name;
  document.getElementById('lb-score').textContent = score > 0 ? 'Score: ' + Math.round(score * 100) + '%' : '';
  document.getElementById('lb-date').textContent = date;
  bootstrap.Modal.getOrCreateInstance(document.getElementById('lightbox')).show();
}

// ── Live camera modal ────────────────────────────────────────────────────────
function openLiveModal() {
  const modalEl = document.getElementById('live-modal');
  document.getElementById('live-modal-img').src = '/api/camera/latest?t=' + Date.now();
  bootstrap.Modal.getOrCreateInstance(modalEl).show();
}

// ── Toasts ───────────────────────────────────────────────────────────────────
function toast(msg, type = 'ok') {
  const el = document.createElement('div');
  el.className = 'alert ' + (type === 'ok' ? 'alert-success' : 'alert-danger') + ' py-2 px-3 mb-1';
  el.style.cssText = 'font-size:.82rem;max-width:320px;animation:fadeIn .2s';
  el.textContent = msg;
  document.getElementById('toast-wrap').appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// ── API calls ─────────────────────────────────────────────────────────────────
async function api(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

async function bulkAssign() {
  const ids = getSelected();
  const name = document.getElementById('assign-name').value.trim();
  if (!ids.length || !name) return;
  try {
    const r = await api('/api/faces/bulk-assign', { ids, assigned_name: name });
    toast(`"${name}" assegnato a ${r.updated} volto/i`);
    document.getElementById('assign-name').value = '';
    setTimeout(() => location.reload(), 1000);
  } catch (e) { toast('Errore: ' + e.message, 'err'); }
}

async function bulkImport() {
  const ids = getSelected();
  if (!ids.length) return;
  try {
    const r = await api('/api/faces/bulk-import', { ids });
    const errs = (r.errors || []).length;
    toast(`Inviati: ${r.submitted}${errs ? ' — Errori: ' + errs : ''}`);
    setTimeout(() => location.reload(), 1000);
  } catch (e) { toast('Errore: ' + e.message, 'err'); }
}

async function bulkDiscard() {
  const ids = getSelected();
  if (!ids.length) return;
  try {
    const r = await api('/api/faces/bulk-discard', { ids });
    toast(`${r.updated} volto/i scartati`);
    setTimeout(() => location.reload(), 1000);
  } catch (e) { toast('Errore: ' + e.message, 'err'); }
}

// ── Persons / Auto-open ─────────────────────────────────────────────────────
async function loadPersons() {
  const wrap = document.getElementById('persons-list');
  if (!wrap) return;
  try {
    const r = await fetch('/api/persons');
    const data = await r.json();
    const persons = data.persons || [];
    const knownNames = data.known_names || [];

    let html = '';
    // Show all known names, with toggle
    const personMap = {};
    persons.forEach(p => personMap[p.name] = p.auto_open);

    const allNames = [...new Set([...knownNames, ...persons.map(p => p.name)])].sort();
    if (allNames.length === 0) {
      html = '<div class="text-muted" style="font-size:.75rem">Nessuna persona registrata</div>';
    } else {
      allNames.forEach(name => {
        const checked = personMap[name] ? 'checked' : '';
        html += `<div class="d-flex align-items-center gap-2">
          <div class="form-check form-switch mb-0">
            <input class="form-check-input" type="checkbox" role="switch" ${checked}
                   onchange="toggleAutoOpen('${name.replace(/'/g,"\\'")}', this.checked)"
                   style="cursor:pointer">
          </div>
          <span class="small text-truncate" style="font-size:.78rem" title="${name}">${name}</span>
        </div>`;
      });
    }
    wrap.innerHTML = html;
  } catch (e) {
    wrap.innerHTML = '<div class="text-danger small">Errore caricamento</div>';
  }
}

async function toggleAutoOpen(name, enabled) {
  try {
    await api('/api/persons/auto-open', { name, auto_open: enabled });
    toast(name + ': auto-apertura ' + (enabled ? 'ON' : 'OFF'));
  } catch (e) {
    toast('Errore: ' + e.message, 'err');
    loadPersons(); // reload to revert UI
  }
}

document.addEventListener('DOMContentLoaded', loadPersons);

// ── Live camera polling ──────────────────────────────────────────────────────
(function () {
  const thumb = document.getElementById('live-feed');
  if (!thumb) return;
  const liveModalEl = document.getElementById('live-modal');

  setInterval(() => {
    const t = Date.now();
    thumb.src = '/api/camera/latest?t=' + t;
    // aggiorna anche il modal se è aperto
    if (liveModalEl && liveModalEl.classList.contains('show')) {
      document.getElementById('live-modal-img').src = '/api/camera/latest?t=' + t;
    }
  }, 2000);
}());

