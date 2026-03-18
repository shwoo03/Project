import fs from 'fs/promises';
import path from 'path';
import crypto from 'crypto';
import { constants as fsConstants } from 'fs';

export async function ensureDir(dirPath) {
  await fs.mkdir(dirPath, { recursive: true });
}

export async function saveFile(filePath, content) {
  await ensureDir(path.dirname(filePath));
  await fs.writeFile(filePath, content);
}

export async function initOutputDir(outputDir) {
  await removePath(outputDir);
  await ensureDir(outputDir);
}

export async function pathExists(targetPath) {
  try {
    await fs.access(targetPath, fsConstants.F_OK);
    return true;
  } catch {
    return false;
  }
}

export async function removePath(targetPath) {
  if (!targetPath) return;
  await fs.rm(targetPath, { recursive: true, force: true });
}

export async function movePath(sourcePath, destinationPath) {
  await ensureDir(path.dirname(destinationPath));
  await fs.rename(sourcePath, destinationPath);
}

export async function copyPath(sourcePath, destinationPath) {
  await ensureDir(path.dirname(destinationPath));
  await fs.cp(sourcePath, destinationPath, {
    recursive: true,
    force: true,
  });
}

export async function replacePath(sourcePath, destinationPath) {
  await removePath(destinationPath);
  await movePath(sourcePath, destinationPath);
}

export function ensureExtension(filename, mimeType) {
  const ext = path.extname(filename);
  if (ext) return filename;

  const mimeToExt = {
    'text/css': '.css',
    'text/javascript': '.js',
    'application/javascript': '.js',
    'text/html': '.html',
    'image/png': '.png',
    'image/jpeg': '.jpg',
    'image/gif': '.gif',
    'image/svg+xml': '.svg',
    'image/webp': '.webp',
    'font/woff': '.woff',
    'font/woff2': '.woff2',
    'font/ttf': '.ttf',
    'application/json': '.json',
  };

  return filename + (mimeToExt[mimeType] || '');
}

export function deduplicateFilename(usedNames, dir, filename) {
  const key = path.posix.join(dir, filename);
  if (!usedNames.has(key)) {
    usedNames.add(key);
    return filename;
  }
  const ext = path.extname(filename);
  const base = path.basename(filename, ext);
  const uniqueName = `${base}_${crypto.randomBytes(4).toString('hex')}${ext}`;
  usedNames.add(path.posix.join(dir, uniqueName));
  return uniqueName;
}
