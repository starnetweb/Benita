/* JAMB Blogger Agent — Admin Panel JS */

// ── Run Agent ─────────────────────────────────────────────
document.getElementById('run-agent-btn')?.addEventListener('click', () => {
  if (!confirm('Run the agent now? This will scrape news and post to WordPress.')) return;
  const btn = document.getElementById('run-agent-btn');
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running…';
  btn.classList.add('running');

  fetch('/Claude_code/Blogger/admin/api.php?action=run_agent', { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      btn.innerHTML = '<i class="bi bi-play-fill"></i> Run Agent Now';
      btn.classList.remove('running');
      if (data.success) {
        showToast('Agent started successfully!', 'success');
        setTimeout(() => location.reload(), 3000);
      } else {
        showToast('Error: ' + (data.error || 'Unknown error'), 'danger');
      }
    })
    .catch(err => {
      btn.innerHTML = '<i class="bi bi-play-fill"></i> Run Agent Now';
      btn.classList.remove('running');
      showToast('Request failed: ' + err, 'danger');
    });
});

// ── Toast notification ────────────────────────────────────
function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container') || (() => {
    const c = document.createElement('div');
    c.id = 'toast-container';
    c.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    c.style.zIndex = 9999;
    document.body.appendChild(c);
    return c;
  })();

  const id = 'toast-' + Date.now();
  container.insertAdjacentHTML('beforeend', `
    <div id="${id}" class="toast align-items-center text-bg-${type} border-0" role="alert">
      <div class="d-flex">
        <div class="toast-body">${msg}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    </div>
  `);
  const el = document.getElementById(id);
  new bootstrap.Toast(el, { delay: 4000 }).show();
  el.addEventListener('hidden.bs.toast', () => el.remove());
}

// ── Delete confirmation ───────────────────────────────────
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', e => {
    if (!confirm(el.dataset.confirm || 'Are you sure?')) e.preventDefault();
  });
});

// ── View content modal ────────────────────────────────────
document.querySelectorAll('.view-content-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const content = btn.dataset.content || '(no content)';
    const title   = btn.dataset.title   || 'Content';
    document.getElementById('content-modal-title').textContent = title;
    document.getElementById('content-viewer').innerHTML = content;
    new bootstrap.Modal(document.getElementById('contentModal')).show();
  });
});

// ── Auto-refresh logs page ────────────────────────────────
if (document.body.dataset.page === 'logs') {
  setInterval(() => {
    fetch(location.href + '&partial=1')
      .then(r => r.text())
      .then(html => {
        const el = document.getElementById('log-table-body');
        if (el) el.innerHTML = (new DOMParser().parseFromString(html, 'text/html'))
          .getElementById('log-table-body')?.innerHTML || el.innerHTML;
      });
  }, 30000);
}

// ── Search filter (client-side instant) ──────────────────
const searchInput = document.getElementById('table-search');
if (searchInput) {
  searchInput.addEventListener('input', () => {
    const q = searchInput.value.toLowerCase();
    document.querySelectorAll('tbody tr').forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });
}
