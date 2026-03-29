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
  .option('-w, --wait <ms>', 'Extra wait time after page load (ms)', '3000')
  .option('-v, --viewport <size>', 'Viewport size (widthxheight)', '1920x1080')
  .option('-s, --screenshot', 'Save screenshots during crawl', false)
  .option('--storage-state <path>', 'Playwright storage state JSON path', '')
  .option('--cookie-file <path>', 'Cookie JSON file path', '')
  .option('--follow-login-gated', 'Allow crawling links from login-gated pages', false)
  .option('--crawl-profile <mode>', 'Crawl profile: accurate, balanced, lightweight, authenticated', 'accurate')
  .option('--network-posture <mode>', 'Network posture: default, authenticated, sensitive-site, manual-review', 'default')
  .option('--representative-qa', 'Enable representative QA summaries for sampled pages', false)
  .option('--interaction-budget <n>', 'Safe interaction attempts per page', '')
  .option('--no-graphql-introspection', 'Disable best-effort GraphQL introspection')
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
        crawlProfile: options.crawlProfile || 'accurate',
        networkPosture: options.networkPosture || 'default',
        enableRepresentativeQA: Boolean(options.representativeQa),
        interactionBudget: options.interactionBudget ? parseInt(options.interactionBudget, 10) : undefined,
        enableGraphqlIntrospection: options.graphqlIntrospection !== false,
        headful: options.headful || false,
        scaffold: options.scaffold !== false,
        domainScope: options.domainScope || 'registrable-domain',
        resumeManifest: options.resumeManifest || null,
        updateExisting: options.updateExisting || false,
        visualAnalysis: options.visualAnalysis || 'docs',
      });
    } catch (err) {
      console.error(chalk.red('\nClone failed:'), err.message);
      if (err.hint) {
        console.error(chalk.yellow(err.hint));
      }
      process.exit(1);
    }
  });

program.parse();
