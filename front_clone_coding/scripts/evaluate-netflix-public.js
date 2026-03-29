#!/usr/bin/env node

import path from 'path';

import {
  NETFLIX_PUBLIC_EVAL_OPTIONS,
  runNetflixPublicSiteEvaluation,
} from '../src/evaluation/netflix-public-site-evaluator.js';

async function main() {
  const result = await runNetflixPublicSiteEvaluation({
    skipClone: process.env.FRONT_CLONE_SKIP_CLONE === '1',
  });

  console.log('');
  console.log('Netflix public replay evaluation complete.');
  console.log(`Start URL: ${result.startUrl}`);
  console.log(`Output directory: ${path.resolve(result.outputDir)}`);
  console.log(`Captured pages: ${result.captureSummary.capturedPages}`);
  console.log(`Representative pages: ${result.captureSummary.representativePages}`);
  console.log(`Critical assets saved: ${result.assetParity.criticalAssetSavedCount}/${result.assetParity.criticalAssetCount}`);
  console.log(`Replay external requests: ${result.captureSummary.replayExternalRequests.length}`);
  console.log(`Local guard-blocked requests: ${result.behaviorParity.localExternalRequests.length}`);
  console.log(`Marker overlap ratio: ${result.visualParity.overlapRatio}`);
  console.log(`Navigation successes: ${result.behaviorParity.localNavigation.successCount}/${result.behaviorParity.localNavigation.attemptedCount}`);
  console.log(`Markdown report: ${path.join(result.outputDir, result.artifacts.markdown)}`);
  console.log(`JSON report: ${path.join(result.outputDir, result.artifacts.json)}`);
  console.log('');
  console.log(`Execution profile: ${JSON.stringify(NETFLIX_PUBLIC_EVAL_OPTIONS)}`);
}

main().catch((error) => {
  console.error('Netflix public replay evaluation failed.');
  console.error(error.stack || error.message);
  process.exit(1);
});
