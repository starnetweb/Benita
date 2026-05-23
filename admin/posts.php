<?php
$page_title  = 'Generated Posts';
$active_page = 'posts';
require_once __DIR__ . '/includes/db.php';
require_once __DIR__ . '/includes/header.php';

$filter = $_GET['status'] ?? '';
$page   = max(1, (int)($_GET['page'] ?? 1));
$per    = 20;
$offset = ($page - 1) * $per;

$where  = $filter ? "WHERE status=?" : "";
$params = $filter ? [$filter] : [];
$total  = db_one("SELECT COUNT(*) AS n FROM posts $where", $params)['n'];
$pages  = max(1, ceil($total / $per));
$posts  = db_query(
    "SELECT * FROM posts $where ORDER BY created_at DESC LIMIT ? OFFSET ?",
    array_merge($params, [$per, $offset])
);
?>

<div class="section-header">
  <h2><i class="bi bi-file-earmark-richtext me-2"></i>Generated Posts <span class="badge bg-secondary"><?= $total ?></span></h2>
  <div class="d-flex gap-2">
    <?php foreach ([''=>'All','published'=>'Published','draft'=>'Drafts','error'=>'Errors'] as $val=>$lbl): ?>
    <a href="?status=<?= $val ?>"
       class="btn btn-sm <?= $filter===$val?'btn-warning':'btn-outline-secondary' ?>">
       <?= $lbl ?>
    </a>
    <?php endforeach; ?>
  </div>
</div>

<div class="panel-card p-0">
<div class="table-responsive">
<table class="table table-dark table-hover mb-0">
  <thead>
    <tr>
      <th>ID</th>
      <th>Title</th>
      <th>Keyphrase</th>
      <th>Words</th>
      <th>Status</th>
      <th>WP Link</th>
      <th>Created</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody>
  <?php if (empty($posts)): ?>
    <tr><td colspan="8" class="text-center text-muted py-4">No posts found.</td></tr>
  <?php endif; ?>
  <?php foreach ($posts as $p):
    $badge = match($p['status']) {
      'published' => 'badge-published', 'draft' => 'badge-draft', default => 'badge-error'
    };
  ?>
  <tr>
    <td class="text-muted"><?= $p['id'] ?></td>
    <td class="truncate" style="max-width:300px">
      <span title="<?= sanitize($p['title']) ?>"><?= sanitize(mb_strimwidth($p['title'],0,65,'…')) ?></span>
      <?php if ($p['meta_description']): ?>
        <div class="text-muted" style="font-size:.73rem"><?= sanitize(mb_strimwidth($p['meta_description'],0,90,'…')) ?></div>
      <?php endif; ?>
    </td>
    <td><span class="badge bg-secondary"><?= sanitize($p['focus_keyphrase'] ?? '—') ?></span></td>
    <td><?= number_format((int)$p['word_count']) ?></td>
    <td><span class="badge <?= $badge ?>"><?= sanitize($p['status']) ?></span></td>
    <td>
      <?php if ($p['wp_url']): ?>
        <a href="<?= sanitize($p['wp_url']) ?>" target="_blank" rel="noopener"
           class="btn btn-sm btn-outline-info"><i class="bi bi-box-arrow-up-right"></i></a>
      <?php else: ?>
        <span class="text-muted">—</span>
      <?php endif; ?>
    </td>
    <td class="text-muted" style="font-size:.8rem;white-space:nowrap"><?= time_ago($p['created_at']) ?></td>
    <td class="d-flex gap-1">
      <?php if ($p['content']): ?>
      <button class="btn btn-sm btn-outline-info view-content-btn"
              data-title="<?= sanitize($p['title']) ?>"
              data-content="<?= sanitize($p['content']) ?>">
        <i class="bi bi-eye"></i>
      </button>
      <?php endif; ?>
      <?php if ($p['error']): ?>
      <button class="btn btn-sm btn-outline-danger view-content-btn"
              data-title="Error Details" data-content="<?= sanitize($p['error']) ?>">
        <i class="bi bi-exclamation-triangle"></i>
      </button>
      <?php endif; ?>
      <button class="btn btn-sm btn-outline-danger" onclick="deletePost(<?= $p['id'] ?>)">
        <i class="bi bi-trash"></i>
      </button>
    </td>
  </tr>
  <?php endforeach; ?>
  </tbody>
</table>
</div>
</div>

<?php if ($pages > 1): ?>
<nav class="mt-3">
  <ul class="pagination pagination-sm justify-content-center">
    <?php for ($i=1;$i<=$pages;$i++): ?>
    <li class="page-item <?= $i===$page?'active':'' ?>">
      <a class="page-link" href="?status=<?= urlencode($filter) ?>&page=<?= $i ?>"><?= $i ?></a>
    </li>
    <?php endfor; ?>
  </ul>
</nav>
<?php endif; ?>

<div class="modal fade" id="contentModal" tabindex="-1">
  <div class="modal-dialog modal-xl">
    <div class="modal-content bg-dark">
      <div class="modal-header border-secondary">
        <h5 class="modal-title text-warning" id="content-modal-title">Post Content</h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body"><div id="content-viewer" class="post-preview"></div></div>
    </div>
  </div>
</div>

<style>.post-preview h2,.post-preview h3{color:#f0a500}.post-preview{color:#ddd;line-height:1.8}</style>

<script>
function deletePost(id) {
  if (!confirm('Delete this post record?')) return;
  fetch('api.php?action=delete_post', {
    method: 'POST', headers: {'Content-Type':'application/x-www-form-urlencoded'}, body: 'id='+id
  }).then(r=>r.json()).then(d=>{ if(d.success) location.reload(); });
}
</script>

<?php require_once __DIR__ . '/includes/footer.php'; ?>
