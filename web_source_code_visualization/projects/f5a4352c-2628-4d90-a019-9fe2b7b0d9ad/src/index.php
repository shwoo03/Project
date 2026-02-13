<?php
require __DIR__ . '/inc/init.php';

$p = (string)($_GET['p'] ?? 'home');


if ($p === 'write' && $_SERVER['REQUEST_METHOD'] === 'POST') {
  $title = (string)($_POST['title'] ?? '');
  $body  = (string)($_POST['body'] ?? '');

  $id = save_post($title, $body);
  if ($id !== null) {
    header('Location: /?p=post&id=' . $id);
    exit;
  }
  $_GET['save_failed'] = '1';
}

$routes = [
  'home'  => __DIR__ . '/pages/home.php',
  'write' => __DIR__ . '/pages/write.php',
  'post'  => __DIR__ . '/pages/post.php',
  'about' => __DIR__ . '/pages/about.php',
];

$active = in_array($p, ['home','write','about'], true) ? $p : 'home';
$page = $routes[$p] ?? $routes['home'];

$page_title = 'My Blog';

include __DIR__ . '/inc/header.php';
include $page;
include __DIR__ . '/inc/footer.php';
