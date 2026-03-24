import path from 'path';
import crypto from 'crypto';
import { ensureDir, saveFile } from './file-utils.js';

export async function writeManifest(outputDir, manifest) {
  const manifestDir = path.join(outputDir, 'server', 'spec', 'manifest');
  const specDir = path.join(outputDir, 'server', 'spec');
  const crawlDocsDir = path.join(outputDir, 'server', 'docs', 'crawl');
  await ensureDir(manifestDir);
  await ensureDir(specDir);
  await ensureDir(crawlDocsDir);

  await saveFile(
    path.join(manifestDir, 'crawl-manifest.json'),
    JSON.stringify(manifest, null, 2),
  );

  await saveFile(
    path.join(crawlDocsDir, 'crawl-report.json'),
    JSON.stringify({
      generatedAt: manifest.generatedAt,
      startUrl: manifest.startUrl,
      domainRoot: manifest.domainRoot,
      counts: {
        pages: manifest.pages.length,
        assets: manifest.assets.length,
      },
      loginGatedPages: manifest.pages.filter((page) => page.loginGated).length,
    }, null, 2),
  );

  await saveFile(
    path.join(crawlDocsDir, 'site-map.json'),
    JSON.stringify(manifest.pages.map((page) => ({
      url: page.url,
      finalUrl: page.finalUrl,
      savedPath: page.savedPath,
      depth: page.depth,
      discoveredFrom: page.discoveredFrom,
      status: page.status,
      loginGated: page.loginGated,
      crawlState: page.crawlState || 'completed',
      skippedReason: page.skippedReason || null,
      error: page.error || null,
      title: page.title,
    })), null, 2),
  );

  await saveFile(
    path.join(specDir, 'resource-manifest.json'),
    JSON.stringify(manifest.assets, null, 2),
  );

  await saveFile(
    path.join(specDir, 'page-quality-report.json'),
    JSON.stringify(manifest.pageQualityReport || [], null, 2),
  );

  await saveFile(
    path.join(specDir, 'crawl-profile.json'),
    JSON.stringify(manifest.crawlProfile || {}, null, 2),
  );
}

export function hashContent(value) {
  return crypto.createHash('sha1').update(value).digest('hex');
}
