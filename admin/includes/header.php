<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= $page_title ?? 'JAMB Blogger Agent' ?> — Admin</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>

<nav class="navbar navbar-expand-lg navbar-dark bg-dark border-bottom border-secondary sticky-top">
  <div class="container-fluid">
    <a class="navbar-brand fw-bold text-warning" href="/">
      <i class="bi bi-robot me-2"></i>JAMB Blogger
    </a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMenu">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navMenu">
      <ul class="navbar-nav me-auto">
        <li class="nav-item">
          <a class="nav-link <?= ($active_page??'')==='dashboard'?'active':'' ?>" href="/">
            <i class="bi bi-speedometer2"></i> Dashboard
          </a>
        </li>
        <li class="nav-item">
          <a class="nav-link <?= ($active_page??'')==='headlines'?'active':'' ?>" href="/headlines.php">
            <i class="bi bi-newspaper"></i> Headlines
          </a>
        </li>
        <li class="nav-item">
          <a class="nav-link <?= ($active_page??'')==='posts'?'active':'' ?>" href="/posts.php">
            <i class="bi bi-file-earmark-richtext"></i> Posts
          </a>
        </li>
        <li class="nav-item">
          <a class="nav-link <?= ($active_page??'')==='sources'?'active':'' ?>" href="/sources.php">
            <i class="bi bi-rss"></i> Sources
          </a>
        </li>
        <li class="nav-item">
          <a class="nav-link <?= ($active_page??'')==='logs'?'active':'' ?>" href="/logs.php">
            <i class="bi bi-journal-text"></i> Logs
          </a>
        </li>
      </ul>
      <div class="d-flex gap-2 align-items-center">
        <span class="badge bg-success" id="agent-status">
          <i class="bi bi-circle-fill me-1" style="font-size:.5rem"></i>Online
        </span>
        <button class="btn btn-sm btn-warning fw-bold" id="run-agent-btn">
          <i class="bi bi-play-fill"></i> Run Agent Now
        </button>
      </div>
    </div>
  </div>
</nav>

<div class="container-fluid py-4 px-4">
