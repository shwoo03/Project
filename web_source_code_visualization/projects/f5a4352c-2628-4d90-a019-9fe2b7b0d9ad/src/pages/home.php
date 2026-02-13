<?php
function load_all_post(): array {
  $postFiles = glob(posts_dir() . '/*.post') ?: [];
  rsort($postFiles);
  $posts = [];
  foreach ($postFiles as $postFile) {
    $id = basename($postFile, '.post');
    $post = load_post($id);
    if ($post) $posts[] = $post;
  }
  return $posts;
}

$posts = load_all_post();
?>
<section class="hero">
  <h1>Posts</h1>
</section>

<div class="grid">
  <div class="card">
    <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:center">
      <span class="pill hot"><?= count($posts) ?> posts</span>
      <a class="btn" href="/?p=write"><span class="dot"></span>Write</a>
    </div>
    <div class="hr"></div>

    <div class="list">
      <?php if (!$posts): ?>
        <div style="color:rgba(255,255,255,.62);font-size:13px">No posts.</div>
      <?php else: foreach ($posts as $p): ?>
        <a class="post" href="/?p=post&id=<?= escape($p['id']) ?>">
          <div class="cover"></div>
          <div class="pb">
            <div class="pt"><?= escape($p['title']) ?></div>
</div>
        </a>
      <?php endforeach; endif; ?>
    </div>
  </div>

  <div class="card">
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
      <span class="pill">Notice</span>
    </div>
    <div class="hr"></div>
  <pre style="margin:0;white-space:pre-wrap;color:rgba(255,255,255,.62);font-size:13px;line-height:1.6">PatchNote - v1 (2025/12/30)
---------------------
- 블로그 개설
- 숏코드 기능 추가
</pre>
  </div>
</div>
