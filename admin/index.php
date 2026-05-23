<?php
$page_title  = 'Dashboard';
$active_page = 'dashboard';
require_once __DIR__ . '/includes/db.php';
require_once __DIR__ . '/includes/header.php';

$stats = get_stats();
$recent_posts     = db_query("SELECT * FROM posts ORDER BY created_at DESC LIMIT 5");
$recent_headlines = db_query("SELECT h.*, s.name AS source_name FROM headlines h LEFT JOIN sources s ON h.source_id=s.id ORDER BY h.fetched_at DESC LIMIT 8");
$recent_logs      = db_query("SELECT * FROM logs ORDER BY created_at DESC LIMIT 10");
?>

<!-- ── Stat Cards ────────────────────────────────────────────── -->
<div class="row g-3 mb-4">
  <?php
  $cards = [
    ['icon'=>'bi-newspaper',          'label'=>'Headlines Fetched',  'val'=>$stats['total_headlines'],  'sub'=>$stats['unused_headlines'].' unused',    'color'=>'#6af'],
    ['icon'=>'bi-file-earmark-check', 'label'=>'Posts Published',    'val'=>$stats['published_posts'],  'sub'=>'of '.$stats['total_posts'].' total',   'color'=>'#5f5'],
    ['icon'=>'bi-rss-fill',           'label'=>'Active Sources',     'val'=>$stats['active_sources'],   'sub'=>'news + social feeds',                  'color'=>'#fa6'],
    ['icon'=>'bi-clock-history',      'label'=>'Last Run',           'val'=>time_ago($stats['last_run']),'sub'=>$stats['last_run'],                    'color'=>'#c8f'],
  ];
  foreach ($cards as $c): ?>
  <div class="col-6 col-lg-3">
    <div class="stat-card d-flex justify-content-between align-items-start">
      <div>
        <div class="stat-value" style="color:<?= $c['color'] ?>"><?= sanitize($c['val']) ?></div>
        <div class="stat-label"><?= $c['label'] ?></div>
        <div class="text-muted" style="font-size:.75rem;margin-top:.3rem"><?= sanitize($c['sub']) ?></div>
      </div>
      <i class="bi <?= $c['icon'] ?> stat-icon" style="color:<?= $c['color'] ?>"></i>
    </div>
  </div>
  <?php endforeach; ?>
</div>

<div class="row g-4">

  <!-- ── Recent Posts ──────────────────────────────────────── -->
  <div class="col-lg-6">
    <div class="panel-card">
      <div class="section-header">
        <h2><i class="bi bi-file-earmark-richtext me-2"></i>Recent Posts</h2>
        <a href="/Claude_code/Blogger/admin/posts.php" class="btn btn-sm btn-outline-warning">View All</a>
      </div>
      <?php if (empty($recent_posts)): ?>
        <div class="text-muted text-center py-4">No posts yet. Run the agent to generate posts.</div>
      <?php else: ?>
      <div class="list-group list-group-flush">
        <?php foreach ($recent_posts as $p): ?>
        <div class="list-group-item bg-transparent border-secondary d-flex justify-content-between align-items-start py-2">
          <div class="me-2">
            <div class="fw-semibold" style="font-size:.9rem"><?= sanitize(mb_strimwidth($p['title'],0,70,'…')) ?></div>
            <small class="text-muted"><?= time_ago($p['created_at']) ?> · <?= $p['word_count'] ?? '?' ?> words</small>
          </div>
          <?php
          $badge = match($p['status']) {
            'published' => 'badge-published', 'draft' => 'badge-draft', default => 'badge-error'
          };
          ?>
          <span class="badge <?= $badge ?> text-uppercase"><?= sanitize($p['status']) ?></span>
        </div>
        <?php endforeach; ?>
      </div>
      <?php endif; ?>
    </div>
  </div>

  <!-- ── Recent Headlines ──────────────────────────────────── -->
  <div class="col-lg-6">
    <div class="panel-card">
      <div class="section-header">
        <h2><i class="bi bi-newspaper me-2"></i>Recent Headlines</h2>
        <a href="/Claude_code/Blogger/admin/headlines.php" class="btn btn-sm btn-outline-warning">View All</a>
      </div>
      <?php if (empty($recent_headlines)): ?>
        <div class="text-muted text-center py-4">No headlines yet.</div>
      <?php else: ?>
      <div class="list-group list-group-flush">
        <?php foreach ($recent_headlines as $h): ?>
        <div class="list-group-item bg-transparent border-secondary py-2">
          <div class="d-flex justify-content-between">
            <a href="<?= sanitize($h['url']) ?>" target="_blank" rel="noopener"
               class="text-decoration-none" style="font-size:.88rem;color:#ddd">
              <?= sanitize(mb_strimwidth($h['title'],0,80,'…')) ?>
            </a>
            <?php if ($h['used']): ?>
              <span class="badge badge-published ms-2 flex-shrink-0">Used</span>
            <?php endif; ?>
          </div>
          <small class="text-muted"><?= sanitize($h['source_name'] ?? 'Unknown') ?> · <?= time_ago($h['fetched_at']) ?></small>
        </div>
        <?php endforeach; ?>
      </div>
      <?php endif; ?>
    </div>
  </div>

  <!-- ── Activity Log ──────────────────────────────────────── -->
  <div class="col-12">
    <div class="panel-card">
      <div class="section-header">
        <h2><i class="bi bi-activity me-2"></i>Recent Activity</h2>
        <a href="/Claude_code/Blogger/admin/logs.php" class="btn btn-sm btn-outline-secondary">Full Logs</a>
      </div>
      <div style="font-family:monospace;font-size:.82rem;max-height:260px;overflow-y:auto">
        <?php foreach ($recent_logs as $log): ?>
        <div class="mb-1">
          <span class="text-muted"><?= sanitize(substr($log['created_at'],0,19)) ?></span>
          <span class="log-<?= sanitize($log['level']) ?> ms-2 fw-bold">[<?= sanitize($log['level']) ?>]</span>
          <span class="ms-2"><?= sanitize($log['message']) ?></span>
        </div>
        <?php endforeach; ?>
        <?php if (empty($recent_logs)): ?>
          <div class="text-muted">No log entries yet.</div>
        <?php endif; ?>
      </div>
    </div>
  </div>

</div>

<!-- Content Viewer Modal -->
<div class="modal fade" id="contentModal" tabindex="-1">
  <div class="modal-dialog modal-xl">
    <div class="modal-content bg-dark">
      <div class="modal-header border-secondary">
        <h5 class="modal-title text-warning" id="content-modal-title">Post Content</h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body"><div id="content-viewer"></div></div>
    </div>
  </div>
</div>

<?php require_once __DIR__ . '/includes/footer.php'; ?>
