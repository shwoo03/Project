#!/usr/bin/env node

import { Command } from 'commander';
import chalk from 'chalk';
import { cloneFrontend } from '../src/index.js';
import { validateUrlSafety } from '../src/utils/url-utils.js';

const program = new Command();

program
  .name('front-clone')
  .description('Clone a commercial site frontend into a backend-ready project')
  .version('3.0.0')
  .argument('<url>', 'Target page URL')
  .option('-o, --output <dir>', 'Output parent directory (final path: <dir>/<domain>)', './output')
  .option('-w, --wait <ms>', 'Extra wait time after page load (ms)', '3000')
  .option('-v, --viewport <size>', 'Viewport size (widthxheight)', '1920x1080')
  .option('-s, --screenshot', 'Save screenshots during crawl', false)
  .option('--storage-state <path>', 'Playwright storage state JSON path', '')
  .option('--cookie-file <path>', 'Cookie JSON file path', '')
  .option('--follow-login-gated', 'Allow crawling links from login-gated pages', false)
  .option('--headful', 'Run browser in headed mode', false)
  .option('--scroll-count <n>', 'Auto-scroll repeat count', '5')
  .option('-r, --recursive', 'Enable recursive multi-page crawl on the same domain scope', false)
  .option('--max-pages <n>', 'Maximum number of pages to crawl', '20')
  .option('--max-depth <n>', 'Maximum crawl depth', '3')
  .option('-c, --concurrency <n>', 'Number of concurrent pages to crawl', '3')
  .option('--domain-scope <mode>', 'Domain scope: registrable-domain or hostname', 'registrable-domain')
  .option('--resume-manifest <path>', 'Existing crawl manifest path for future update workflows', '')
  .option('--update-existing', 'Keep the existing output directory instead of wiping it first', false)
  .option('--visual-analysis <mode>', 'Visual analysis mode: docs or off', 'docs')
  .option('--no-scaffold', 'Skip backend scaffold generation')
  .action(async (url, options) => {
    if (url.toLowerCase() === 'ui') {
      try {
        const module = await import('../web/server.js');
        module.startUIServer();
      } catch (err) {
        console.error(chalk.red('Failed to load Web UI server:'), err);
        process.exit(1);
      }
      return;
    }

    console.log('');
    console.log(chalk.cyan.bold('  Front Clone Coding v3.0.0'));
    console.log(chalk.gray('  Browser-driven mirror + backend handoff docs'));
    console.log('');

    const urlCheck = validateUrlSafety(url);
    if (!urlCheck.safe) {
      console.error(chalk.red('URL rejected:', urlCheck.reason));
      console.error(chalk.gray('  Only http/https URLs to public hosts are allowed.'));
      process.exit(1);
    }

    try {
      await cloneFrontend({
        url,
        output: options.output || './output',
        waitTime: parseInt(options.wait, 10),
        viewport: options.viewport,
        screenshot: options.screenshot,
        scrollCount: parseInt(options.scrollCount, 10),
        recursive: options.recursive,
        maxPages: parseInt(options.maxPages, 10),
        maxDepth: parseInt(options.maxDepth, 10),
        concurrency: parseInt(options.concurrency, 10),
        storageState: options.storageState || null,
        cookieFile: options.cookieFile || null,
        followLoginGated: options.followLoginGated || false,
        headful: options.headful || false,
        scaffold: options.scaffold !== false,
        domainScope: options.domainScope || 'registrable-domain',
        resumeManifest: options.resumeManifest || null,
        updateExisting: options.updateExisting || false,
        visualAnalysis: options.visualAnalysis || 'docs',
      });
    } catch (err) {
      console.error(chalk.red('\nClone failed:'), err.message);
      process.exit(1);
    }
  });

program.parse();
