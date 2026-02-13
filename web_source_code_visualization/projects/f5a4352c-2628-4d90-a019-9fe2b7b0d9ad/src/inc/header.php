<?php

function current_nav(string $key, string $current): string {
  return $key === $current ? ' class="active"' : '';
}
?>
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title><?= escape($page_title) ?></title>
  <style>
    :root{--bg:#070913;--p:rgba(255,255,255,.06);--p2:rgba(255,255,255,.035);--s:rgba(255,255,255,.10);--t:rgba(255,255,255,.92);--m:rgba(255,255,255,.62);--r:20px;--a1:#7c5cff;--a2:#25c2a0;--a3:#ff5c8a;--sh:0 18px 55px rgba(0,0,0,.55)}
    *{box-sizing:border-box}html,body{height:100%}
    body{margin:0;color:var(--t);font-family:system-ui,-apple-system,"Apple SD Gothic Neo","Noto Sans KR",Segoe UI,Roboto,sans-serif;background:
      radial-gradient(1200px 620px at 12% -12%, rgba(124,92,255,.40), transparent 60%),
      radial-gradient(900px 600px at 92% 0%, rgba(37,194,160,.25), transparent 60%),
      radial-gradient(900px 620px at 55% 120%, rgba(255,92,138,.12), transparent 62%),
      linear-gradient(180deg,#050611,var(--bg));overflow-x:hidden}
    a{color:inherit;text-decoration:none}a:hover{opacity:.95}
    .wrap{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
    .top{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:14px 16px;border:1px solid var(--s);border-radius:calc(var(--r) + 10px);background:linear-gradient(180deg,rgba(255,255,255,.095),rgba(255,255,255,.03));box-shadow:var(--sh);backdrop-filter:blur(12px);position:sticky;top:14px;z-index:9}
    .brand{display:flex;gap:12px;align-items:center;min-width:0}
    .logo{width:40px;height:40px;border-radius:16px;background:linear-gradient(135deg,var(--a1),var(--a2));box-shadow:0 14px 30px rgba(124,92,255,.22)}
    .name{font-weight:900;letter-spacing:.1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .tag{font-size:13px;color:var(--m);margin-top:2px}
    .nav{display:flex;gap:10px;flex-wrap:wrap}
    .nav a{padding:9px 11px;border-radius:14px;border:1px solid transparent;color:rgba(255,255,255,.82)}
    .nav a:hover{border-color:rgba(255,255,255,.12);background:rgba(255,255,255,.05);color:rgba(255,255,255,.94)}
    .nav a.active{border-color:rgba(124,92,255,.32);background:rgba(124,92,255,.12)}
    .hero{margin-top:14px;padding:22px 18px;border-radius:calc(var(--r)+12px);border:1px solid var(--s);background:linear-gradient(180deg,rgba(255,255,255,.06),rgba(255,255,255,.02));box-shadow:var(--sh)}
    .hero h1{margin:0;font-size:28px;letter-spacing:-.3px}.hero p{margin:10px 0 0;color:var(--m)}
    .grid{margin-top:14px;display:grid;grid-template-columns:1.6fr .8fr;gap:14px}
    @media(max-width:980px){.grid{grid-template-columns:1fr}.top{position:relative;top:auto}}
    .card{padding:16px;border-radius:var(--r);border:1px solid var(--s);background:linear-gradient(180deg,var(--p),var(--p2));box-shadow:0 12px 34px rgba(0,0,0,.38)}
    .hr{height:1px;background:rgba(255,255,255,.10);margin:14px 0}
    .pill{display:inline-flex;align-items:center;gap:7px;font-size:12px;padding:7px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.05);color:rgba(255,255,255,.78);white-space:nowrap}
    .pill.hot{border-color:rgba(124,92,255,.25);background:rgba(124,92,255,.10)}.pill.bad{border-color:rgba(255,92,138,.28);background:rgba(255,92,138,.10)}.pill.ok{border-color:rgba(37,194,160,.25);background:rgba(37,194,160,.10)}
    .btn,button{appearance:none;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.05);color:rgba(255,255,255,.92);padding:10px 12px;border-radius:16px;cursor:pointer;display:inline-flex;gap:8px;align-items:center}
    .btn:hover,button:hover{background:rgba(255,255,255,.08)}button.primary{background:linear-gradient(135deg,rgba(124,92,255,.52),rgba(37,194,160,.18))}
    .dot{width:9px;height:9px;border-radius:999px;background:linear-gradient(135deg,var(--a1),var(--a2));box-shadow:0 0 0 4px rgba(124,92,255,.14)}
    label{display:block;font-size:12px;color:var(--m);margin:0 0 6px}
    input[type=text],textarea{width:100%;padding:12px 12px;border-radius:16px;border:1px solid rgba(255,255,255,.14);background:rgba(0,0,0,.18);color:rgba(255,255,255,.92);outline:none}
    textarea{min-height:300px;resize:vertical}
    input:focus,textarea:focus{border-color:rgba(124,92,255,.70);box-shadow:0 0 0 4px rgba(124,92,255,.20)}
    .list{display:grid;gap:12px}
    .post{border-radius:22px;border:1px solid rgba(255,255,255,.10);background:rgba(0,0,0,.14);overflow:hidden}
    .post:hover{background:rgba(255,255,255,.05)}
    .cover{height:92px;background:
      radial-gradient(240px 120px at 20% 40%, rgba(124,92,255,.55), transparent 65%),
      radial-gradient(240px 120px at 80% 20%, rgba(37,194,160,.40), transparent 65%),
      radial-gradient(220px 120px at 70% 110%, rgba(255,92,138,.20), transparent 65%),
      linear-gradient(135deg,rgba(255,255,255,.08),rgba(255,255,255,.02))}
    .pb{padding:14px 14px 16px}.pt{font-weight:900;letter-spacing:-.18px}
    .pm{margin-top:8px;color:var(--m);font-size:12px;display:flex;gap:8px;flex-wrap:wrap}
    .ex{margin-top:10px;color:rgba(255,255,255,.78);font-size:13px;line-height:1.6}
    .article{border-radius:22px;border:1px solid rgba(255,255,255,.10);background:rgba(0,0,0,.14);overflow:hidden}
    .ah{padding:18px 18px 0}.at{margin:0;font-size:26px;letter-spacing:-.35px}
    .am{margin-top:10px;display:flex;gap:8px;flex-wrap:wrap}
    .ac{padding:16px 18px 18px}
    pre{margin:0;padding:14px;border-radius:16px;border:1px solid rgba(255,255,255,.12);background:rgba(0,0,0,.24);overflow:auto;white-space:pre-wrap;word-break:break-word;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:13px;line-height:1.6}
    .inc{border-radius:18px;border:1px solid rgba(255,255,255,.10);background:rgba(0,0,0,.14);padding:12px;margin-bottom:12px}
    .foot{margin-top:16px;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;color:rgba(255,255,255,.55);font-size:13px}
  </style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div class="brand">
      <div class="logo"></div>
      <div style="min-width:0">
        <div class="name">MY Blog</div>
        <div class="tag">소소한 일상을 공유해요~~</div>
      </div>
    </div>
    <div class="nav">
      <a<?= current_nav('home', $active) ?> href="/?p=home">Posts</a>
      <a<?= current_nav('write', $active) ?> href="/?p=write">Write</a>
      <a<?= current_nav('about', $active) ?> href="/?p=about">About</a>
    </div>
  </div>
