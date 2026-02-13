<?php
function escape(string $text): string {
  return htmlspecialchars($text, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function posts_dir(): string {
  $postDir = __DIR__ . '/../data/posts';
  @mkdir($postDir, 0775, true);
  return $postDir;
}

/*
 * .post 형식: title \n\n body
 * 글 번호 가져오기: data/posts/.id
 */
function save_post(string $title, string $body): ?int {
  $postDir = posts_dir();

  $idPath = $postDir . '/.id';
  $postId = ((int)@file_get_contents($idPath)) + 1;
  @file_put_contents($idPath, (string)$postId, LOCK_EX);

  $postPath = $postDir . "/$postId.post";
  $payload  = rtrim($title, "\r\n") . "\n\n" . $body;

  $ok = @file_put_contents($postPath, $payload, LOCK_EX);
  return $ok === false ? null : $postId;
}

function load_post(string $id): ?array {
  $postPath = posts_dir() . "/$id.post";
  $rawContent = @file_get_contents($postPath);
  if ($rawContent === false) return null;

  $parts = preg_split("/\R\R/", $rawContent, 2);

  return [
    'id'    => $id,
    'title' => (string)($parts[0] ?? 'Untitled'),
    'body'  => (string)($parts[1] ?? ''),
  ];
}

/* shortcode include */
function fetch(string $target): array {
  $target = trim($target);

  if (!preg_match('#^[a-z][a-z0-9+.-]*://#i', $target)) {
    $target = 'https://' . $target;
  }

  $content = @file_get_contents($target);

  return $content === false
    ? ['ok' => false, 'target' => $target, 'status' => 'FAILED', 'content' => '']
    : ['ok' => true,  'target' => $target, 'status' => 'OK',     'content' => (string)$content];
}

/* shortcode parsing*/
function shortcode(string $text, array &$includes): string
{
    $pattern = '/\{\{\s*include\s*:\s*(.*?)\s*\}\}/i';

    $result = preg_replace_callback(
        $pattern,
        function (array $match) use (&$includes): string {
            $target  = (string) $match[1];
            $include = fetch($target);
            $includes[] = $include;
            
            return $include['ok'] ? '[include:OK]' : '[include:FAILED]';
        },
        $text
    );

    if ($result !== null) {
        return $result;
    }
    return $text;
}

