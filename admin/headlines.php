<?php
$page_title  = 'Headlines';
$active_page = 'headlines';
require_once __DIR__ . '/includes/db.php';
require_once __DIR__ . '/includes/header.php';

$search      = trim($_GET['search'] ?? '');
$filter_used = $_GET['used'] ?? '';
$page        = max(1, (int)($_GET['page'] ?? 1));
$per_page    = 25;
$offset      = ($page - 1) * $per_page;

$where = ['1=1'];
$params = [];
if ($search) {
    $where[] = "(h.title LIKE ? OR h.summary LIKE ?)";
    $params[] = "%$search%";
    $params[] = "%$search%";
}
if ($filter_used === '0') { $where[] = "h.used=0 AND h.duplicate=0"; }
if ($filter_used === '1') { $where[] = "h.used=1"; }

$cond = implode(' AND ', $where);
$total = db_one("SELECT COUNT(*) AS n FROM headlines h WHERE $cond", $params)['n'];
$pages = max(1, ceil($total / $per_page));
$params_paged = array_merge($params, [$per_page, $offset]);
$headlines = db_query(
    "SELECT h.*, s.name AS source_name FROM headlines h LEFT JOIN sources s ON h.source_id=s.id
     WHERE $cond ORDER BY h.fetched_at DESC LIMIT ? OFFSET ?",
    $params_paged
);
?>

<div class="section-header">
  <h2><i class="bi bi-newspaper me-2"></i>Headlines <span class="badge bg-secondary"><?= $total ?></span></h2>
</div>

<!-- Filter Bar -->
<div class="filter-bar d-flex gap-2 flex-wrap mb-3">
  <input id="table-search" type="text" class="form-control form-control-sm" style="max-width:300px"
         placeholder="Search headlines…" value="<?= sanitize($search) ?>">
  <select class="form-select form-select-sm" style="max-width:160px"
          onchange="window.location='?used='+this.value+'&search=<?= urlencode($search) ?>'">
    <option value="" <?= $filter_used===''?'selected':'' ?>>All</option>
    <option value="0" <?= $filter_used==='0'?'selected':'' ?>>Unused</option>
    <option value="1" <?= $filter_used==='1'?'selected':'' ?>>Used</option>
  </select>
  <form method="get" class="d-flex gap-2">
    <input type="text" name="search" class="form-control form-control-sm" style="max-width:300px"
           placeholder="Search…" value="<?= sanitize($search) ?>">
    <button class="btn btn-sm btn-warning">Search</button>
    <?php if ($search): ?>
      <a href="?" class="btn btn-sm btn-outline-secondary">Clear</a>
    <?php endif; ?>
  </form>
</div>

<div class="panel-card p-0">
<div class="table-responsive">
<table class="table table-dark table-hover mb-0">
  <thead>
    <tr>
      <th>ID</th>
      <th>Title</th>
      <th>Source</th>
      <th>Published</th>
      <th>Fetched</th>
      <th>Status</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody id="log-table-body">
  <?php if (empty($headlines)): ?>
    <tr><td colspan="7" class="text-center text-muted py-4">No headlines found.</td></tr>
  <?php endif; ?>
  <?php foreach ($headlines as $h): ?>
  <tr>
    <td class="text-muted"><?= $h['id'] ?></td>
    <td class="truncate" style="max-width:340px">
      <?php if ($h['url']): ?>
        <a href="<?= sanitize($h['url']) ?>" target="_blank" rel="noopener"
           class="text-decoration-none text-light"><?= sanitize($h['title']) ?></a>
      <?php else: ?>
        <?= sanitize($h['title']) ?>
      <?php endif; ?>
      <?php if ($h['summary']): ?>
        <div class="text-muted" style="font-size:.75rem;margin-top:2px">
          <?= sanitize(mb_strimwidth($h['summary'],0,100,'…')) ?>
        </div>
      <?php endif; ?>
    </td>
    <td><span class="badge badge-rss"><?= sanitize($h['source_name'] ?? '—') ?></span></td>
    <td class="text-muted" style="font-size:.8rem;white-space:nowrap"><?= sanitize(substr($h['published_at']??'',0,16)) ?></td>
    <td class="text-muted" style="font-size:.8rem;white-space:nowrap"><?= time_ago($h['fetched_at']) ?></td>
    <td>
      <?php if ($h['used']): ?>
        <span class="badge badge-published">Used</span>
      <?php elseif ($h['duplicate']): ?>
        <span class="badge bg-secondary">Dup</span>
      <?php else: ?>
        <span class="badge badge-draft">New</span>
      <?php endif; ?>
    </td>
    <td>
      <?php if ($h['full_content']): ?>
      <button class="btn btn-sm btn-outline-info view-content-btn"
              data-title="<?= sanitize($h['title']) ?>"
              data-content="<?= sanitize(nl2br($h['full_content'])) ?>">
        <i class="bi bi-eye"></i>
      </button>
      <?php endif; ?>
      <button class="btn btn-sm btn-outline-danger ms-1" onclick="deleteHeadline(<?= $h['id'] ?>)">
        <i class="bi bi-trash"></i>
      </button>
    </td>
  </tr>
  <?php endforeach; ?>
  </tbody>
</table>
</div>
</div>

<!-- Pagination -->
<?php if ($pages > 1): ?>
<nav class="mt-3">
  <ul class="pagination pagination-sm justify-content-center">
    <?php for ($i = 1; $i <= $pages; $i++): ?>
    <li class="page-item <?= $i===$page?'active':'' ?>">
      <a class="page-link" href="?page=<?= $i ?>&search=<?= urlencode($search) ?>&used=<?= urlencode($filter_used) ?>"><?= $i ?></a>
    </li>
    <?php endfor; ?>
  </ul>
</nav>
<?php endif; ?>

<!-- Content Modal -->
<div class="modal fade" id="contentModal" tabindex="-1">
  <div class="modal-dialog modal-xl">
    <div class="modal-content bg-dark">
      <div class="modal-header border-secondary">
        <h5 class="modal-title text-warning" id="content-modal-title">Article Content</h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body"><div id="content-viewer"></div></div>
    </div>
  </div>
</div>

<script>
function deleteHeadline(id) {
  if (!confirm('Delete this headline?')) return;
  fetch('/Claude_code/Blogger/admin/api.php?action=delete_headline', {
    method: 'POST', headers: {'Content-Type':'application/x-www-form-urlencoded'},
    body: 'id=' + id
  }).then(r => r.json()).then(d => { if (d.success) location.reload(); });
}
</script>

<?php require_once __DIR__ . '/includes/footer.php'; ?>
