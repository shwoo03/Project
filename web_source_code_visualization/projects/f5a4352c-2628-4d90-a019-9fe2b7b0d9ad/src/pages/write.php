<?php

$title = (string)($_POST['title'] ?? '');
$body  = (string)($_POST['body'] ?? '');
$error = isset($_GET['save_failed']) ? 'SAVE_FAILED' : '';
?>
<section class="hero">
  <h1>Write</h1>
  <p>Publish a post.</p>
</section>

<div class="grid">
  <div class="card">
    <form method="post" action="/?p=write" autocomplete="off">
      <label>Title</label>
      <input type="text" name="title" value="<?= escape($title) ?>"/>

      <div style="height:12px"></div>

      <label>Body</label>
      <textarea name="body"><?= escape($body) ?></textarea>

      <div style="margin-top:10px;display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        <button class="primary" type="submit"><span class="dot"></span>Publish</button>
        <a class="btn" href="/?p=home"><span class="dot"></span>Back</a>
        <?php if ($error): ?><span class="pill bad"><?= escape($error) ?></span><?php endif; ?>
      </div>
    </form>
  </div>

  <div class="card">
    <span class="pill hot">Shortcode Example</span>
    <div class="hr"></div>
    <pre><?= "{{include: https://example.com/a.txt}}

{{include: example.com/a.txt}}" ?></pre>
  </div>
</div>
