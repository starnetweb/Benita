<?php
/**
 * AJAX API endpoint for admin panel actions.
 */
header('Content-Type: application/json');
require_once __DIR__ . '/includes/db.php';

$action = $_GET['action'] ?? $_POST['action'] ?? '';

switch ($action) {

    // ── Run agent (background process) ───────────────────────────────────────
    case 'run_agent':
        if ($_SERVER['REQUEST_METHOD'] !== 'POST') json_response(['error' => 'POST required'], 405);

        $python     = 'C:\\Users\\Loki\\AppData\\Local\\Programs\\Python\\Python313\\python.exe';
        $agent_dir  = dirname(__DIR__) . '\\agent';
        $script     = $agent_dir . '\\agent.py';
        $log        = dirname(__DIR__) . '\\logs\\manual_run.log';

        // Verify python and script exist
        if (!file_exists($python))  json_response(['error' => 'Python not found at: ' . $python], 500);
        if (!file_exists($script))  json_response(['error' => 'agent.py not found at: ' . $script], 500);

        // Use PHP COM (always available in XAMPP) to launch a hidden, detached process
        $cmd = 'cmd /c cd /d "' . $agent_dir . '" && '
             . '"' . $python . '" "' . $script . '" '
             . '>> "' . $log . '" 2>&1';
        try {
            $shell = new COM('WScript.Shell');
            $shell->Run($cmd, 0, false); // 0 = hidden window, false = don't wait
        } catch (\Exception $e) {
            // COM not available — fallback to exec
            $env  = 'set PYTHONUTF8=1 && set PYTHONIOENCODING=utf-8 && ';
            exec('cmd /c ' . $env . $cmd . ' &');
        }

        json_response(['success' => true, 'message' => 'Agent started', 'log' => $log]);
        break;

    // ── Sources CRUD ─────────────────────────────────────────────────────────
    case 'add_source':
        $name     = trim($_POST['name'] ?? '');
        $type     = $_POST['type'] ?? 'rss';
        $url      = trim($_POST['url'] ?? '') ?: null;
        $handle   = trim($_POST['handle'] ?? '') ?: null;
        $priority = (int)($_POST['priority'] ?? 5);
        $notes    = trim($_POST['notes'] ?? '') ?: null;
        if (!$name) json_response(['error' => 'Name required'], 400);
        db_execute(
            "INSERT INTO sources (name, type, url, handle, priority, notes) VALUES (?,?,?,?,?,?)",
            [$name, $type, $url, $handle, $priority, $notes]
        );
        json_response(['success' => true]);
        break;

    case 'toggle_source':
        $id = (int)($_POST['id'] ?? 0);
        if (!$id) json_response(['error' => 'ID required'], 400);
        $src = db_one("SELECT active FROM sources WHERE id=?", [$id]);
        if (!$src) json_response(['error' => 'Not found'], 404);
        $new = $src['active'] ? 0 : 1;
        db_execute("UPDATE sources SET active=?, updated_at=datetime('now') WHERE id=?", [$new, $id]);
        json_response(['success' => true, 'active' => $new]);
        break;

    case 'delete_source':
        $id = (int)($_POST['id'] ?? 0);
        if (!$id) json_response(['error' => 'ID required'], 400);
        db_execute("DELETE FROM sources WHERE id=?", [$id]);
        json_response(['success' => true]);
        break;

    case 'edit_source':
        $id       = (int)($_POST['id'] ?? 0);
        $name     = trim($_POST['name'] ?? '');
        $type     = $_POST['type'] ?? 'rss';
        $url      = trim($_POST['url'] ?? '') ?: null;
        $handle   = trim($_POST['handle'] ?? '') ?: null;
        $priority = (int)($_POST['priority'] ?? 5);
        $notes    = trim($_POST['notes'] ?? '') ?: null;
        if (!$id || !$name) json_response(['error' => 'ID and name required'], 400);
        db_execute(
            "UPDATE sources SET name=?,type=?,url=?,handle=?,priority=?,notes=?,updated_at=datetime('now') WHERE id=?",
            [$name, $type, $url, $handle, $priority, $notes, $id]
        );
        json_response(['success' => true]);
        break;

    // ── Stats (for dashboard refresh) ────────────────────────────────────────
    case 'stats':
        json_response(get_stats());
        break;

    // ── Delete headline ───────────────────────────────────────────────────────
    case 'delete_headline':
        $id = (int)($_POST['id'] ?? 0);
        if (!$id) json_response(['error' => 'ID required'], 400);
        db_execute("DELETE FROM headlines WHERE id=?", [$id]);
        json_response(['success' => true]);
        break;

    // ── Delete post ───────────────────────────────────────────────────────────
    case 'delete_post':
        $id = (int)($_POST['id'] ?? 0);
        if (!$id) json_response(['error' => 'ID required'], 400);
        db_execute("DELETE FROM posts WHERE id=?", [$id]);
        json_response(['success' => true]);
        break;

    // ── Clear logs ────────────────────────────────────────────────────────────
    case 'clear_logs':
        db_execute("DELETE FROM logs WHERE created_at < datetime('now', '-7 days')");
        json_response(['success' => true]);
        break;

    default:
        json_response(['error' => 'Unknown action'], 400);
}
