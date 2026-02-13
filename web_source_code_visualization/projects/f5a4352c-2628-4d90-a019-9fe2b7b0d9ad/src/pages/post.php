<?php
$id = (string)($_GET['id'] ?? '');
$post = load_post($id);
if (!$post) { http_response_code(404); echo 'NOT_FOUND'; return; }

$incs = [];
$body_rendered = shortcode($post['body'], $incs);
?>
<section class="hero">
  <h1><?= escape($post['title']) ?></h1>
  <p>Saved post</p>
</section>

<div class="grid">
  <div>
    <div class="article">
      <div class="ah">
        <h2 class="at"><?= escape($post['title']) ?></h2>
        <div class="am"><span class="pill hot">post</span></div>
      </div>
      <div class="ac">
        <pre><?= escape($body_rendered) ?></pre>
      </div>
    </div>

    <div style="height:14px"></div>

    <div class="card">
      <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:center">
        <span class="pill hot">Includes <?= count($incs) ?></span>
        <a class="btn" href="/?p=write"><span class="dot"></span>Write</a>
      </div>
      <div class="hr"></div>

      <?php if (!$incs): ?>
        <div style="color:rgba(255,255,255,.62);font-size:13px">No includes.</div>
      <?php else: foreach ($incs as $inc): ?>
        <div class="inc">
          <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:center">
            <span class="pill hot"><?= escape($inc['target']) ?></span>
            <span class="pill <?= $inc['ok'] ? 'ok' : 'bad' ?>"><?= $inc['status'] ?></span>
          </div>
          <div style="height:10px"></div>
          <pre><?= $inc['content'] ?></pre>
        </div>
      <?php endforeach; endif; ?>
    </div>
  </div>

  <div class="card">
    <span class="pill">id</span>
    <div class="hr"></div>
    <span class="pill hot"><?= $post['id'] ?></span>
    <div class="hr"></div>
    <a class="btn" href="/?p=home"><span class="dot"></span>All posts</a>
  </div>
</div>
