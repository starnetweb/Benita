<?php
$page_title  = 'Settings';
$active_page = 'settings';
require_once __DIR__ . '/includes/db.php';

$saved = false;
$error = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $fields = ['max_posts_per_run', 'news_lookback_hours', 'cron_schedule', 'rewriter_prompt', 'min_word_count'];
    foreach ($fields as $f) {
        if (isset($_POST[$f])) {
            $val = trim($_POST[$f]);
            db_execute("INSERT INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now'))
                        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                       [$f, $val]);
        }
    }
    $saved = true;
}

// Load current settings
function get_setting_val(string $key, string $default = ''): string {
    $row = db_one("SELECT value FROM settings WHERE key=?", [$key]);
    return $row ? $row['value'] : $default;
}

$max_posts        = get_setting_val('max_posts_per_run', '5');
$lookback_hours   = get_setting_val('news_lookback_hours', '48');
$cron_schedule    = get_setting_val('cron_schedule', '0 5 * * *');
$min_words        = get_setting_val('min_word_count', '320');
$rewriter_prompt  = get_setting_val('rewriter_prompt', '');

require_once __DIR__ . '/includes/header.php';
?>

<?php if ($saved): ?>
<div class="alert alert-success alert-dismissible fade show mb-4" role="alert">
  <i class="bi bi-check-circle-fill me-2"></i>Settings saved successfully.
  <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
</div>
<?php endif; ?>

<div class="mb-4">
  <h1 class="h3 text-warning mb-0"><i class="bi bi-gear-fill me-2"></i>Settings</h1>
  <p class="text-muted mt-1">Configure agent behaviour, news freshness, and the rewriter prompt.</p>
</div>

<form method="POST">
<div class="row g-4">

  <!-- ── Agent Settings ──────────────────────────────────────── -->
  <div class="col-lg-6">
    <div class="panel-card">
      <div class="section-header mb-3">
        <h2><i class="bi bi-robot me-2"></i>Agent Settings</h2>
      </div>

      <div class="mb-3">
        <label class="form-label fw-semibold">Max Posts Per Run</label>
        <input type="number" name="max_posts_per_run" class="form-control bg-dark text-light border-secondary"
               value="<?= sanitize($max_posts) ?>" min="1" max="20">
        <div class="form-text text-muted">How many blog posts to generate each run (default: 5)</div>
      </div>

      <div class="mb-3">
        <label class="form-label fw-semibold">Minimum Article Word Count</label>
        <input type="number" name="min_word_count" class="form-control bg-dark text-light border-secondary"
               value="<?= sanitize($min_words) ?>" min="100" max="2000">
        <div class="form-text text-muted">Minimum words per generated article (default: 320)</div>
      </div>

      <div class="mb-3">
        <label class="form-label fw-semibold">News Freshness (hours)</label>
        <input type="number" name="news_lookback_hours" class="form-control bg-dark text-light border-secondary"
               value="<?= sanitize($lookback_hours) ?>" min="6" max="720">
        <div class="form-text text-muted">Only fetch news published within this many hours (default: 48). Set to 168 for 7 days.</div>
      </div>

      <div class="mb-3">
        <label class="form-label fw-semibold">Cron Schedule (UTC)</label>
        <input type="text" name="cron_schedule" class="form-control bg-dark text-light border-secondary font-monospace"
               value="<?= sanitize($cron_schedule) ?>" placeholder="0 5 * * *">
        <div class="form-text text-muted">
          Cron expression for daily run. Current: <strong><?= sanitize($cron_schedule) ?></strong>
          = <?= cron_human($cron_schedule) ?>.
          <br>Change requires container restart to take effect.
        </div>
      </div>
    </div>
  </div>

  <!-- ── News Sources Quick Link ─────────────────────────────── -->
  <div class="col-lg-6">
    <div class="panel-card">
      <div class="section-header mb-3">
        <h2><i class="bi bi-rss me-2"></i>News Sources</h2>
      </div>
      <p class="text-muted">Add, remove, and toggle RSS feeds and Twitter handles used by the scraper.</p>
      <a href="/sources.php" class="btn btn-outline-warning">
        <i class="bi bi-pencil-square me-1"></i>Manage Sources
      </a>

      <hr class="border-secondary my-4">

      <div class="section-header mb-3">
        <h2><i class="bi bi-clock-history me-2"></i>Run Schedule</h2>
      </div>
      <?php
        $last_run = get_setting_val('last_run', '');
        $next_run = next_run_from_cron($cron_schedule);
      ?>
      <div class="d-flex flex-column gap-2" style="font-size:.9rem">
        <div><span class="text-muted">Last run:</span> <strong><?= $last_run ? sanitize(substr($last_run,0,16).' UTC') : 'Never' ?></strong></div>
        <div><span class="text-muted">Next run:</span> <strong class="text-warning"><?= sanitize($next_run) ?></strong></div>
        <div><span class="text-muted">Schedule:</span> <code class="text-success"><?= sanitize($cron_schedule) ?></code></div>
      </div>
    </div>
  </div>

  <!-- ── Rewriter Prompt ─────────────────────────────────────── -->
  <div class="col-12">
    <div class="panel-card">
      <div class="section-header mb-3">
        <h2><i class="bi bi-chat-text me-2"></i>Rewriter Prompt (System Prompt)</h2>
      </div>
      <p class="text-muted mb-3">
        Customise the Claude system prompt used to write blog posts.
        Leave blank to use the built-in default prompt.
      </p>

      <div class="mb-2">
        <button type="button" class="btn btn-sm btn-outline-secondary" id="show-default-btn">
          <i class="bi bi-eye me-1"></i>Show Default Prompt
        </button>
      </div>

      <div id="default-prompt-box" class="mb-3" style="display:none">
        <pre class="p-3 rounded" style="background:#1a1a2e;font-size:.78rem;max-height:300px;overflow-y:auto;color:#adb5bd"><?= sanitize(get_default_prompt()) ?></pre>
      </div>

      <textarea name="rewriter_prompt" class="form-control bg-dark text-light border-secondary font-monospace"
                rows="16" placeholder="Leave blank to use the default prompt above..."
                style="font-size:.82rem"><?= sanitize($rewriter_prompt) ?></textarea>
      <div class="form-text text-muted mt-1">
        Available variables: <code>{news_data}</code>, <code>{min_words}</code>, <code>{max_words}</code>
      </div>
    </div>
  </div>

</div>

<div class="mt-4">
  <button type="submit" class="btn btn-warning fw-bold px-4">
    <i class="bi bi-save me-1"></i>Save Settings
  </button>
</div>
</form>

<script>
document.getElementById('show-default-btn').addEventListener('click', function() {
  const box = document.getElementById('default-prompt-box');
  box.style.display = box.style.display === 'none' ? 'block' : 'none';
  this.innerHTML = box.style.display === 'none'
    ? '<i class="bi bi-eye me-1"></i>Show Default Prompt'
    : '<i class="bi bi-eye-slash me-1"></i>Hide Default Prompt';
});
</script>

<?php
function get_default_prompt(): string {
    return 'You are an expert Nigerian education blogger and SEO specialist.
You write helpful, friendly, and accurate blog posts for JAMB/SSCE/UTME candidates
and Nigerian students seeking university or polytechnic admission.

Your writing style:
- Warm, encouraging, and relatable to Nigerian students aged 16-25
- Conversational but professional
- Use simple English — not too academic
- Include practical advice, not just news
- Use Nigerian context (mention JAMB, WAEC, NECO, NUC, etc. correctly)
- Never plagiarise — always write in your own voice based on the facts

SEO/AEO requirements you MUST follow:
- Use the focus keyphrase naturally in the first paragraph, at least one H2, and the meta description
- All H2/H3 headings must be keyword-rich and describe the section
- Include a FAQ section with 2-3 questions only (boosts featured snippets / AEO)
- Write between {min_words} and {max_words} words — be concise, no padding, no repetition
- Include transition words (however, therefore, furthermore, in addition, etc.)
- Use passive and active voice mix (Yoast readability score friendly)
- External links: cite the original sources with proper anchor text
- Internal link placeholders: add [INTERNAL_LINK: topic] where relevant
- Image suggestions: add [IMAGE: description] placeholders where images would help
- Schema markup: include Article + FAQPage schema JSON-LD';
}

function cron_human(string $expr): string {
    $parts = explode(' ', trim($expr));
    if (count($parts) !== 5) return 'custom schedule';
    [$min, $hour, $dom, $mon, $dow] = $parts;
    if ($dom === '*' && $mon === '*' && $dow === '*') {
        return "daily at " . str_pad($hour, 2, '0', STR_PAD_LEFT) . ":" . str_pad($min, 2, '0', STR_PAD_LEFT) . " UTC";
    }
    return $expr;
}

function next_run_from_cron(string $expr): string {
    $parts = explode(' ', trim($expr));
    if (count($parts) !== 5) return 'Unknown';
    [$min, $hour] = $parts;
    $now = time();
    $today = mktime((int)$hour, (int)$min, 0);
    $next = $today > $now ? $today : $today + 86400;
    return date('Y-m-d H:i', $next) . ' UTC';
}

require_once __DIR__ . '/includes/footer.php';
?>
