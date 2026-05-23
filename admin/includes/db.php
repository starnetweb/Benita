<?php
/**
 * SQLite PDO connection helper for the admin panel.
 */

// Use DB_PATH env var (set by Docker) or fall back to relative path
define('DB_PATH', getenv('DB_PATH') ?: dirname(__DIR__, 2) . '/db/blogger.db');

function get_db(): PDO {
    static $pdo = null;
    if ($pdo === null) {
        if (!file_exists(DB_PATH)) {
            // Trigger Python init if DB doesn't exist yet
            http_response_code(503);
            die('<div class="alert alert-warning m-4">Database not found. Run the agent setup first: <code>python agent/agent.py --dry-run</code></div>');
        }
        $pdo = new PDO('sqlite:' . DB_PATH);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
        $pdo->exec('PRAGMA foreign_keys=ON;');
    }
    return $pdo;
}

function db_query(string $sql, array $params = []): array {
    $stmt = get_db()->prepare($sql);
    $stmt->execute($params);
    return $stmt->fetchAll();
}

function db_execute(string $sql, array $params = []): int {
    $stmt = get_db()->prepare($sql);
    $stmt->execute($params);
    return (int) get_db()->lastInsertId();
}

function db_one(string $sql, array $params = []): ?array {
    $rows = db_query($sql, $params);
    return $rows ? $rows[0] : null;
}

function get_stats(): array {
    $db = get_db();
    return [
        'total_headlines'   => $db->query("SELECT COUNT(*) FROM headlines")->fetchColumn(),
        'unused_headlines'  => $db->query("SELECT COUNT(*) FROM headlines WHERE used=0 AND duplicate=0")->fetchColumn(),
        'total_posts'       => $db->query("SELECT COUNT(*) FROM posts")->fetchColumn(),
        'published_posts'   => $db->query("SELECT COUNT(*) FROM posts WHERE status='published'")->fetchColumn(),
        'error_posts'       => $db->query("SELECT COUNT(*) FROM posts WHERE status='error'")->fetchColumn(),
        'active_sources'    => $db->query("SELECT COUNT(*) FROM sources WHERE active=1")->fetchColumn(),
        'last_run'          => $db->query("SELECT value FROM settings WHERE key='last_run'")->fetchColumn() ?: 'Never',
        'total_published'   => $db->query("SELECT value FROM settings WHERE key='total_posts_published'")->fetchColumn() ?: '0',
    ];
}

function time_ago(string $datetime): string {
    if (!$datetime || $datetime === 'Never') return 'Never';
    $diff = time() - strtotime($datetime);
    if ($diff < 60) return 'Just now';
    if ($diff < 3600) return floor($diff / 60) . 'm ago';
    if ($diff < 86400) return floor($diff / 3600) . 'h ago';
    return floor($diff / 86400) . 'd ago';
}

function sanitize(mixed $v): string {
    return htmlspecialchars((string)$v, ENT_QUOTES, 'UTF-8');
}

function json_response(mixed $data, int $code = 200): never {
    http_response_code($code);
    header('Content-Type: application/json');
    echo json_encode($data);
    exit;
}
