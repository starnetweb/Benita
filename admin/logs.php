<?php
$page_title  = 'Agent Logs';
$active_page = 'logs';
require_once __DIR__ . '/includes/db.php';
require_once __DIR__ . '/includes/header.php';

$filter = $_GET['level'] ?? '';
$where  = $filter ? "WHERE level=?" : "";
$params = $filter ? [$filter] : [];
$logs   = db_query("SELECT * FROM logs $where ORDER BY created_at DESC LIMIT 500", $params);

// Also read the flat log file
$log_file = dirname(__DIR__) . '/logs/agent.log';
$file_lines = [];
if (file_exists($log_file)) {
    $lines = file($log_file);
    $file_lines = array_reverse(array_slice($lines, -100));
}
?>

<div class="section-header">
  <h2><i class="bi bi-journal-text me-2"></i>Agent Logs</h2>
  <div class="d-flex gap-2">
    <?php foreach ([''=>'All','INFO'=>'Info','WARNING'=>'Warnings','ERROR'=>'Errors'] as $val=>$lbl): ?>
    <a href="?level=<?= $val ?>"
       class="btn btn-sm <?= $filter===$val?'btn-warning':'btn-outline-secondary' ?>">
       <?= $lbl ?>
    </a>
    <?php endforeach; ?>
    <button class="btn btn-sm btn-outline-danger" onclick="clearOldLogs()">
      <i class="bi bi-trash me-1"></i>Clear Old (>7d)
    </button>
  </div>
</div>

<div class="row g-4">
  <!-- DB Logs -->
  <div class="col-lg-6">
    <div class="panel-card">
      <h6 class="text-warning mb-3"><i class="bi bi-database me-2"></i>Database Logs (<?= count($logs) ?>)</h6>
      <div style="font-family:monospace;font-size:.78rem;max-height:500px;overflow-y:auto" id="log-table-body">
        <?php if (empty($logs)): ?>
          <div class="text-muted">No log entries found.</div>
        <?php endif; ?>
        <?php foreach ($logs as $log): ?>
        <div class="mb-1 py-1 border-bottom border-secondary" style="border-bottom-style:dashed!important">
          <span class="text-muted"><?= sanitize(substr($log['created_at'],0,19)) ?></span>
          <span class="fw-bold log-<?= sanitize($log['level']) ?> ms-2">[<?= sanitize($log['level']) ?>]</span>
          <span class="ms-2 text-light"><?= sanitize($log['message']) ?></span>
          <?php if ($log['context']): ?>
            <div class="text-muted ps-3" style="font-size:.72rem"><?= sanitize($log['context']) ?></div>
          <?php endif; ?>
        </div>
        <?php endforeach; ?>
      </div>
    </div>
  </div>

  <!-- File Logs -->
  <div class="col-lg-6">
    <div class="panel-card">
      <h6 class="text-warning mb-3"><i class="bi bi-file-text me-2"></i>Log File (last 100 lines)</h6>
      <?php if (empty($file_lines)): ?>
        <div class="text-muted">Log file not found or empty.</div>
      <?php else: ?>
      <div style="font-family:monospace;font-size:.75rem;max-height:500px;overflow-y:auto;background:#0a0a14;padding:.75rem;border-radius:6px">
        <?php foreach ($file_lines as $line):
          $level = 'INFO';
          if (str_contains($line, '[ERROR]')) $level='ERROR';
          elseif (str_contains($line, '[WARNING]')) $level='WARNING';
          elseif (str_contains($line, '[DEBUG]')) $level='DEBUG';
        ?>
        <div class="log-<?= $level ?>"><?= sanitize(rtrim($line)) ?></div>
        <?php endforeach; ?>
      </div>
      <?php endif; ?>
    </div>
  </div>
</div>

<script>
function clearOldLogs() {
  if (!confirm('Clear logs older than 7 days?')) return;
  fetch('/Claude_code/Blogger/admin/api.php?action=clear_logs', { method: 'POST' })
    .then(r => r.json()).then(d => { if (d.success) { showToast('Old logs cleared'); location.reload(); } });
}
</script>

<?php require_once __DIR__ . '/includes/footer.php'; ?>
