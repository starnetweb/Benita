<?php
$page_title  = 'Run History';
$active_page = 'runs';
require_once __DIR__ . '/includes/db.php';

$runs = db_query("SELECT * FROM runs ORDER BY started_at DESC LIMIT 100");

// Get schedule info
$cron  = db_one("SELECT value FROM settings WHERE key='cron_schedule'");
$cron_expr = $cron ? $cron['value'] : '0 5 * * *';
$last_run  = db_one("SELECT value FROM settings WHERE key='last_run'");

function next_run(string $expr): string {
    $parts = explode(' ', trim($expr));
    if (count($parts) !== 5) return 'Unknown';
    [$min, $hour] = $parts;
    $now   = time();
    $today = mktime((int)$hour, (int)$min, 0);
    $next  = $today > $now ? $today : $today + 86400;
    return date('D, d M Y H:i', $next) . ' UTC';
}

function fmt_duration(?int $secs): string {
    if ($secs === null) return '—';
    if ($secs < 60) return $secs . 's';
    return floor($secs / 60) . 'm ' . ($secs % 60) . 's';
}

require_once __DIR__ . '/includes/header.php';
?>

<div class="d-flex justify-content-between align-items-center mb-4">
  <div>
    <h1 class="h3 text-warning mb-0"><i class="bi bi-clock-history me-2"></i>Run History</h1>
    <p class="text-muted mt-1">All agent runs — scheduled and manual.</p>
  </div>
  <button class="btn btn-sm btn-warning fw-bold" id="run-agent-btn">
    <i class="bi bi-play-fill"></i> Run Agent Now
  </button>
</div>

<!-- ── Schedule Info ─────────────────────────────────────────────── -->
<div class="row g-3 mb-4">
  <div class="col-md-4">
    <div class="stat-card">
      <div class="stat-value" style="color:#6af;font-size:1.1rem"><?= sanitize($cron_expr) ?></div>
      <div class="stat-label">Cron Schedule (UTC)</div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="stat-card">
      <div class="stat-value" style="color:#fa6;font-size:1rem"><?= next_run($cron_expr) ?></div>
      <div class="stat-label">Next Scheduled Run</div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="stat-card">
      <div class="stat-value" style="color:#5f5;font-size:1rem">
        <?= $last_run && $last_run['value'] ? sanitize(substr($last_run['value'], 0, 16)) . ' UTC' : 'Never' ?>
      </div>
      <div class="stat-label">Last Run</div>
    </div>
  </div>
</div>

<!-- ── Runs Table ─────────────────────────────────────────────────── -->
<div class="panel-card">
  <div class="section-header mb-3">
    <h2><i class="bi bi-list-check me-2"></i>All Runs</h2>
    <span class="badge bg-secondary"><?= count($runs) ?> runs</span>
  </div>

  <?php if (empty($runs)): ?>
    <div class="text-muted text-center py-5">No runs yet. Click <strong>Run Agent Now</strong> to start.</div>
  <?php else: ?>
  <div class="table-responsive">
    <table class="table table-dark table-hover align-middle mb-0" style="font-size:.875rem">
      <thead class="table-dark border-secondary">
        <tr>
          <th>#</th>
          <th>Started</th>
          <th>Duration</th>
          <th>Trigger</th>
          <th>Status</th>
          <th>Headlines</th>
          <th>Published</th>
          <th>Errors</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody>
        <?php foreach ($runs as $r): ?>
        <?php
          $badge = match($r['status']) {
            'completed' => 'badge-published',
            'running'   => 'bg-info text-dark',
            'failed'    => 'badge-error',
            default     => 'bg-secondary',
          };
          $trigger_badge = $r['trigger'] === 'manual' ? 'bg-warning text-dark' : 'bg-secondary';
        ?>
        <tr>
          <td class="text-muted"><?= $r['id'] ?></td>
          <td>
            <span><?= sanitize(substr($r['started_at'], 0, 16)) ?></span><br>
            <small class="text-muted"><?= time_ago($r['started_at']) ?></small>
          </td>
          <td><?= fmt_duration($r['duration_secs']) ?></td>
          <td><span class="badge <?= $trigger_badge ?>"><?= sanitize($r['trigger']) ?></span></td>
          <td><span class="badge <?= $badge ?> text-uppercase"><?= sanitize($r['status']) ?></span></td>
          <td><?= (int)$r['headlines_found'] ?></td>
          <td class="text-success fw-semibold"><?= (int)$r['posts_published'] ?></td>
          <td class="<?= $r['posts_errored'] > 0 ? 'text-danger' : '' ?>"><?= (int)$r['posts_errored'] ?></td>
          <td class="text-muted" style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
            <?= sanitize($r['notes'] ?? '') ?>
          </td>
        </tr>
        <?php endforeach; ?>
      </tbody>
    </table>
  </div>
  <?php endif; ?>
</div>

<?php require_once __DIR__ . '/includes/footer.php'; ?>
