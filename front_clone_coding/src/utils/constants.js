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

// Image downloader
export const IMAGE_FETCH_TIMEOUT = 5000;
export const IMAGE_DOWNLOAD_CONCURRENCY = 6;

// Web server
export const MAX_COMPLETED_JOBS = 50;
export const JOB_RETENTION_MS = 30 * 60 * 1000;
export const SSE_HEARTBEAT_INTERVAL_MS = 30000;
export const MAX_JOB_LOGS = 500;
