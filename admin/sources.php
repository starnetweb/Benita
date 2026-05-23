<?php
$page_title  = 'News Sources';
$active_page = 'sources';
require_once __DIR__ . '/includes/db.php';

// Handle form submissions server-side for non-JS fallback
$msg = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $act = $_POST['_action'] ?? '';
    if ($act === 'add') {
        $name   = trim($_POST['name'] ?? '');
        $type   = $_POST['type'] ?? 'rss';
        $url    = trim($_POST['url'] ?? '') ?: null;
        $handle = trim($_POST['handle'] ?? '') ?: null;
        $pri    = (int)($_POST['priority'] ?? 5);
        $notes  = trim($_POST['notes'] ?? '') ?: null;
        if ($name) {
            db_execute("INSERT INTO sources (name,type,url,handle,priority,notes) VALUES (?,?,?,?,?,?)",
                [$name, $type, $url, $handle, $pri, $notes]);
            $msg = 'Source added.';
        }
    } elseif ($act === 'delete') {
        db_execute("DELETE FROM sources WHERE id=?", [(int)$_POST['id']]);
        $msg = 'Source deleted.';
    } elseif ($act === 'toggle') {
        $s = db_one("SELECT active FROM sources WHERE id=?", [(int)$_POST['id']]);
        if ($s) db_execute("UPDATE sources SET active=? WHERE id=?", [$s['active']?0:1, (int)$_POST['id']]);
    }
    header('Location: sources.php' . ($msg ? '?msg='.urlencode($msg) : ''));
    exit;
}

$msg = $_GET['msg'] ?? '';
require_once __DIR__ . '/includes/header.php';

$sources = db_query("SELECT * FROM sources ORDER BY priority DESC, name");
?>

<?php if ($msg): ?>
<div class="alert alert-success alert-dismissible fade show" role="alert">
  <?= sanitize($msg) ?>
  <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
</div>
<?php endif; ?>

<div class="section-header">
  <h2><i class="bi bi-rss me-2"></i>News Sources</h2>
  <button class="btn btn-warning" data-bs-toggle="modal" data-bs-target="#addSourceModal">
    <i class="bi bi-plus-lg me-1"></i>Add Source
  </button>
</div>

<div class="panel-card p-0">
<div class="table-responsive">
<table class="table table-dark table-hover mb-0">
  <thead>
    <tr>
      <th>Name</th>
      <th>Type</th>
      <th>URL / Handle</th>
      <th>Priority</th>
      <th>Notes</th>
      <th>Status</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody>
  <?php foreach ($sources as $s): ?>
  <tr id="source-row-<?= $s['id'] ?>">
    <td class="fw-semibold"><?= sanitize($s['name']) ?></td>
    <td>
      <span class="badge <?= str_starts_with($s['type'],'twitter') ? 'badge-twitter' : 'badge-rss' ?>">
        <?= sanitize($s['type']) ?>
      </span>
    </td>
    <td class="truncate" style="max-width:280px;font-size:.82rem">
      <?php if ($s['url']): ?>
        <a href="<?= sanitize($s['url']) ?>" target="_blank" rel="noopener"
           class="text-info text-decoration-none"><?= sanitize($s['url']) ?></a>
      <?php elseif ($s['handle']): ?>
        <span class="text-muted">@<?= sanitize($s['handle']) ?></span>
      <?php else: ?>—<?php endif; ?>
    </td>
    <td>
      <div class="d-flex align-items-center gap-1">
        <?php for ($i=1;$i<=10;$i++): ?>
          <div style="width:6px;height:14px;border-radius:2px;
               background:<?= $i<=$s['priority']?'#f0a500':'#333' ?>"></div>
        <?php endfor; ?>
        <small class="text-muted ms-1"><?= $s['priority'] ?>/10</small>
      </div>
    </td>
    <td class="text-muted" style="font-size:.8rem"><?= sanitize($s['notes'] ?? '—') ?></td>
    <td>
      <?php if ($s['active']): ?>
        <span class="badge badge-published">Active</span>
      <?php else: ?>
        <span class="badge bg-secondary">Paused</span>
      <?php endif; ?>
    </td>
    <td class="d-flex gap-1">
      <button class="btn btn-sm <?= $s['active']?'btn-outline-warning':'btn-outline-success' ?>"
              onclick="toggleSource(<?= $s['id'] ?>)" title="<?= $s['active']?'Pause':'Activate' ?>">
        <i class="bi bi-<?= $s['active']?'pause':'play' ?>-fill"></i>
      </button>
      <button class="btn btn-sm btn-outline-info" onclick="editSource(<?= $s['id'] ?>)"
              data-id="<?= $s['id'] ?>"
              data-name="<?= sanitize($s['name']) ?>"
              data-type="<?= sanitize($s['type']) ?>"
              data-url="<?= sanitize($s['url']??'') ?>"
              data-handle="<?= sanitize($s['handle']??'') ?>"
              data-priority="<?= $s['priority'] ?>"
              data-notes="<?= sanitize($s['notes']??'') ?>">
        <i class="bi bi-pencil"></i>
      </button>
      <button class="btn btn-sm btn-outline-danger" onclick="deleteSource(<?= $s['id'] ?>)">
        <i class="bi bi-trash"></i>
      </button>
    </td>
  </tr>
  <?php endforeach; ?>
  </tbody>
</table>
</div>
</div>

<!-- ── Add Source Modal ─────────────────────────────────────── -->
<div class="modal fade" id="addSourceModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content bg-dark border-secondary">
      <div class="modal-header border-secondary">
        <h5 class="modal-title text-warning" id="source-modal-title">Add News Source</h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <form id="source-form">
          <input type="hidden" id="src-id" name="id">
          <div class="mb-3">
            <label class="form-label">Name *</label>
            <input type="text" id="src-name" name="name" class="form-control bg-dark text-light border-secondary" required placeholder="e.g. Vanguard Education RSS">
          </div>
          <div class="mb-3">
            <label class="form-label">Type *</label>
            <select id="src-type" name="type" class="form-select bg-dark text-light border-secondary" onchange="toggleUrlHandle()">
              <option value="rss">RSS Feed</option>
              <option value="website">Website (Scrape)</option>
              <option value="twitter">Twitter/X Handle</option>
              <option value="twitter_hashtag">Twitter/X Hashtag</option>
            </select>
          </div>
          <div class="mb-3" id="url-group">
            <label class="form-label">Feed URL</label>
            <input type="url" id="src-url" name="url" class="form-control bg-dark text-light border-secondary" placeholder="https://…/feed/">
          </div>
          <div class="mb-3 d-none" id="handle-group">
            <label class="form-label">Handle / Hashtag</label>
            <div class="input-group">
              <span class="input-group-text bg-dark text-muted border-secondary">@#</span>
              <input type="text" id="src-handle" name="handle" class="form-control bg-dark text-light border-secondary" placeholder="officialJAMB_NG">
            </div>
          </div>
          <div class="mb-3">
            <label class="form-label">Priority (1–10)</label>
            <input type="range" id="src-priority" name="priority" class="form-range" min="1" max="10" value="5" oninput="document.getElementById('pri-val').textContent=this.value">
            <div class="text-end text-muted"><span id="pri-val">5</span>/10</div>
          </div>
          <div class="mb-3">
            <label class="form-label">Notes</label>
            <textarea id="src-notes" name="notes" class="form-control bg-dark text-light border-secondary" rows="2" placeholder="Optional notes…"></textarea>
          </div>
        </form>
      </div>
      <div class="modal-footer border-secondary">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
        <button type="button" class="btn btn-warning" onclick="saveSource()">Save Source</button>
      </div>
    </div>
  </div>
</div>

<script>
const modal = () => bootstrap.Modal.getOrCreateInstance(document.getElementById('addSourceModal'));

function toggleUrlHandle() {
  const type = document.getElementById('src-type').value;
  const isTwitter = type.startsWith('twitter');
  document.getElementById('url-group').classList.toggle('d-none', isTwitter);
  document.getElementById('handle-group').classList.toggle('d-none', !isTwitter);
}

function editSource(id) {
  const btn = document.querySelector(`[data-id="${id}"]`);
  document.getElementById('source-modal-title').textContent = 'Edit Source';
  document.getElementById('src-id').value       = btn.dataset.id;
  document.getElementById('src-name').value     = btn.dataset.name;
  document.getElementById('src-type').value     = btn.dataset.type;
  document.getElementById('src-url').value      = btn.dataset.url;
  document.getElementById('src-handle').value   = btn.dataset.handle;
  document.getElementById('src-priority').value = btn.dataset.priority;
  document.getElementById('pri-val').textContent= btn.dataset.priority;
  document.getElementById('src-notes').value    = btn.dataset.notes;
  toggleUrlHandle();
  modal().show();
}

function saveSource() {
  const id = document.getElementById('src-id').value;
  const action = id ? 'edit_source' : 'add_source';
  const data = new FormData(document.getElementById('source-form'));
  fetch('api.php?action=' + action, { method: 'POST', body: data })
    .then(r => r.json()).then(d => {
      if (d.success) { modal().hide(); location.reload(); }
      else showToast('Error: ' + d.error, 'danger');
    });
}

function toggleSource(id) {
  fetch('api.php?action=toggle_source', {
    method: 'POST', headers: {'Content-Type':'application/x-www-form-urlencoded'}, body: 'id='+id
  }).then(r => r.json()).then(d => { if (d.success) location.reload(); });
}

function deleteSource(id) {
  if (!confirm('Delete this source? This cannot be undone.')) return;
  fetch('api.php?action=delete_source', {
    method: 'POST', headers: {'Content-Type':'application/x-www-form-urlencoded'}, body: 'id='+id
  }).then(r => r.json()).then(d => { if (d.success) location.reload(); });
}
</script>

<?php require_once __DIR__ . '/includes/footer.php'; ?>
