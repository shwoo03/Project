import path from 'path';
import fs from 'fs/promises';
import {
  copyPath,
  ensureDir,
  movePath,
  pathExists,
  replacePath,
  removePath,
} from '../utils/file-utils.js';
import { getDomainRoot } from '../utils/url-utils.js';

const MERGED_OUTPUT_ENTRIES = [
  'public',
  'views',
  'server',
  'server.js',
  'package.json',
  'README.md',
];
const OUTPUT_FINALIZE_RETRY_DELAYS_MS = [250, 750, 1500];

export function getOutputDomainRoot(targetUrl) {
  return getDomainRoot(targetUrl, 'registrable-domain');
}

export async function resolveOutputDirForRun(outputParent, domainRoot, { updateExisting = false } = {}) {
  const baseOutputDir = path.join(outputParent, domainRoot);
  if (updateExisting) {
    return {
      outputDir: baseOutputDir,
      outputLabel: domainRoot,
      sequence: 0,
    };
  }

  if (!await pathExists(baseOutputDir)) {
    return {
      outputDir: baseOutputDir,
      outputLabel: domainRoot,
      sequence: 0,
    };
  }

  for (let sequence = 2; sequence < 10_000; sequence += 1) {
    const candidateLabel = `${domainRoot}-${sequence}`;
    const candidateDir = path.join(outputParent, candidateLabel);
    if (!await pathExists(candidateDir)) {
      return {
        outputDir: candidateDir,
        outputLabel: candidateLabel,
        sequence,
      };
    }
  }

  throw new Error(`Could not allocate a unique output directory for ${domainRoot}`);
}

export async function finalizeOutput(context) {
  if (!context.shouldUpdate) {
    await ensureDir(path.dirname(context.outputDir));
    await withFilesystemRetry(
      () => movePath(context.stagingDir, context.outputDir),
      { operation: 'move staging output into place', targetPath: context.outputDir },
    );
    return;
  }

  await ensureDir(context.outputDir);

  for (const entry of MERGED_OUTPUT_ENTRIES) {
    const sourcePath = path.join(context.stagingDir, entry);
    if (!(await pathExists(sourcePath))) continue;

    const destinationPath = path.join(context.outputDir, entry);
    await withFilesystemRetry(
      () => replacePath(sourcePath, destinationPath),
      { operation: `replace output entry ${entry}`, targetPath: destinationPath },
    );
  }

  const remainingEntries = await listRemainingEntries(context.stagingDir);
  for (const entry of remainingEntries) {
    const sourcePath = path.join(context.stagingDir, entry);
    const destinationPath = path.join(context.outputDir, entry);
    await withFilesystemRetry(
      () => copyPath(sourcePath, destinationPath),
      { operation: `copy output entry ${entry}`, targetPath: destinationPath },
    );
  }

  await withFilesystemRetry(
    () => removePath(context.stagingDir),
    { operation: 'remove staging directory', targetPath: context.stagingDir },
  );
}

async function listRemainingEntries(stagingDir) {
  try {
    const entries = await fs.readdir(stagingDir);
    return entries;
  } catch {
    return [];
  }
}

export function isRetriableFilesystemConflict(error) {
  const code = String(error?.code || '').toUpperCase();
  return ['EBUSY', 'EPERM', 'ENOTEMPTY', 'EACCES'].includes(code);
}

export async function withFilesystemRetry(operation, context = {}) {
  let lastError = null;

  for (let attempt = 0; attempt <= OUTPUT_FINALIZE_RETRY_DELAYS_MS.length; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
      if (!isRetriableFilesystemConflict(error) || attempt === OUTPUT_FINALIZE_RETRY_DELAYS_MS.length) {
        throw buildOutputFinalizeError(error, context);
      }
      await delay(OUTPUT_FINALIZE_RETRY_DELAYS_MS[attempt]);
    }
  }

  throw buildOutputFinalizeError(lastError, context);
}

export function buildOutputFinalizeError(error, context = {}) {
  const structured = new Error(`Output finalize failed while trying to ${context.operation || 'update generated output'}`);
  structured.code = 'OUTPUT_FINALIZE_LOCKED';
  structured.details = [
    context.targetPath ? `Path: ${context.targetPath}` : null,
    error?.code ? `Code: ${error.code}` : null,
    error?.message ? `Cause: ${error.message}` : null,
  ].filter(Boolean).join(' | ');
  structured.hint = 'Close any running replay server, file explorer window, or OneDrive sync lock using the output folder, then retry the clone.';
  structured.cause = error;
  return structured;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
