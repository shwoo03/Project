// Network interceptor limits
export const API_BODY_LIMIT = 2 * 1024 * 1024;
export const ASSET_BODY_LIMIT = 10 * 1024 * 1024;
export const MAX_RESPONSES = 5000;
export const MAX_XHR_REQUESTS = 2000;
export const MAX_WEBSOCKET_EVENTS = 1000;

// Page crawler
export const DEFAULT_WAIT_TIME = 3000;
export const PAGE_LOAD_TIMEOUT = 30000;
export const NETWORK_IDLE_TIMEOUT = 5000;
export const IMAGE_WAIT_TIMEOUT = 5000;
export const SCROLL_INTERVAL_MS = 400;
export const MAX_SCREENSHOT_HEIGHT = 8000;
export const SAFE_INTERACTION_TIMEOUT = 2500;
export const SAFE_INTERACTION_CANDIDATE_LIMIT = 24;

// Site crawler
export const WORKER_PAGE_TIMEOUT = PAGE_LOAD_TIMEOUT * 3; // 90s per page before timeout
export const VISITED_SET_SAFETY_MULTIPLIER = 100;

// Image downloader
export const IMAGE_FETCH_TIMEOUT = 5000;
export const IMAGE_DOWNLOAD_CONCURRENCY = 6;

// Web server
export const MAX_COMPLETED_JOBS = 50;
export const JOB_RETENTION_MS = 30 * 60 * 1000;
export const SSE_HEARTBEAT_INTERVAL_MS = 30000;
export const MAX_JOB_LOGS = 500;

// Content comparison thresholds (replay verifier)
export const CONTENT_GAP_CEILING = 0.35; // below this overlap → high-confidence content gap
export const PARTIAL_MATCH_CEILING = 0.6; // below this overlap → partial content match
export const BOILERPLATE_DOMINANCE_RATIO = 0.28; // nav+footer / body ratio for boilerplate detection
export const HEADING_MAIN_OVERLAP_FLOOR = 0.45; // min heading or main overlap for noise classification
export const LENGTH_DRIFT_FLOOR = 0.2; // min length drift for noise classification

// Runtime guard limits
export const MAX_GUARD_EXCEPTIONS = 100;
export const MAX_GUARD_RESOURCE_ERRORS = 200;

// Concurrency limits for parallel processing
export const ASSET_DOWNLOAD_CONCURRENCY = 10;
export const CSS_PROCESSING_CONCURRENCY = 6;
export const JS_PROCESSING_CONCURRENCY = 8;
export const PAGE_PROCESSING_CONCURRENCY = 4;

// Mock sanitizer
export const SANITIZER_MAX_DEPTH = 20;
export const SANITIZER_MAX_FIELDS = 200;

// Playwright runtime
export const PLAYWRIGHT_VERSION = '1.58.2';
export const PLAYWRIGHT_DOCKER_IMAGE = `mcr.microsoft.com/playwright:v${PLAYWRIGHT_VERSION}-noble`;
export const PLAYWRIGHT_RUNTIME_ERROR_CODE = 'PLAYWRIGHT_RUNTIME_MISMATCH';
