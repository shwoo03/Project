"""
Analysis Cache Module.

SQLite-based caching for parsed analysis results.
Enables incremental analysis by only re-parsing changed files.
"""

import os
import json
import sqlite3
import hashlib
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from pathlib import Path


@dataclass
class CachedParseResult:
    """Cached result from parsing a file."""
    file_path: str
    file_hash: str
    language: str
    endpoints: List[Dict]  # Serialized endpoint data
    symbols: Dict[str, Dict]  # Symbol info
    parse_time_ms: float
    cached_at: float  # Unix timestamp
    

class AnalysisCache:
    """
    SQLite-based cache for analysis results.
    
    Features:
    - File hash-based change detection (SHA256)
    - Incremental analysis support
    - Cache statistics
    - Automatic cache invalidation
    """
    
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the cache.
        
        Args:
            db_path: Path to SQLite database file.
                    If None, uses a default path in the backend directory.
        """
        if db_path is None:
            # Default to .cache directory in backend
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.cache')
            os.makedirs(cache_dir, exist_ok=True)
            db_path = os.path.join(cache_dir, 'analysis_cache.db')
        
        self.db_path = db_path
        self._init_db()
        
        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "invalidations": 0,
            "saves": 0
        }
    
    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create tables
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS file_cache (
                    file_path TEXT PRIMARY KEY,
                    file_hash TEXT NOT NULL,
                    language TEXT,
                    endpoints TEXT,
                    symbols TEXT,
                    parse_time_ms REAL,
                    cached_at REAL,
                    project_path TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_project_path 
                ON file_cache(project_path)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_file_hash 
                ON file_cache(file_hash)
            ''')
            
            # Check/set schema version
            cursor.execute(
                'INSERT OR IGNORE INTO cache_meta (key, value) VALUES (?, ?)',
                ('schema_version', str(self.SCHEMA_VERSION))
            )
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with context management."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    @staticmethod
    def compute_file_hash(file_path: str) -> Optional[str]:
        """
        Compute SHA256 hash of a file's contents.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hex digest of SHA256 hash, or None if file cannot be read
        """
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return None
    
    def get_cached(self, file_path: str, current_hash: Optional[str] = None) -> Optional[CachedParseResult]:
        """
        Get cached parse result for a file if valid.
        
        Args:
            file_path: Path to the file
            current_hash: Pre-computed hash (optional, will compute if not provided)
            
        Returns:
            CachedParseResult if cache hit and valid, None otherwise
        """
        if current_hash is None:
            current_hash = self.compute_file_hash(file_path)
        
        if current_hash is None:
            self._stats["misses"] += 1
            return None
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM file_cache WHERE file_path = ?',
                (file_path,)
            )
            row = cursor.fetchone()
            
            if row is None:
                self._stats["misses"] += 1
                return None
            
            # Check if hash matches
            if row['file_hash'] != current_hash:
                self._stats["misses"] += 1
                return None
            
            # Cache hit!
            self._stats["hits"] += 1
            
            try:
                return CachedParseResult(
                    file_path=row['file_path'],
                    file_hash=row['file_hash'],
                    language=row['language'] or 'unknown',
                    endpoints=json.loads(row['endpoints'] or '[]'),
                    symbols=json.loads(row['symbols'] or '{}'),
                    parse_time_ms=row['parse_time_ms'] or 0.0,
                    cached_at=row['cached_at'] or 0.0
                )
            except (json.JSONDecodeError, KeyError):
                self._stats["misses"] += 1
                return None
    
    def save(
        self, 
        file_path: str, 
        file_hash: str, 
        language: str,
        endpoints: List[Dict],
        symbols: Dict[str, Dict],
        parse_time_ms: float,
        project_path: Optional[str] = None
    ):
        """
        Save parse result to cache.
        
        Args:
            file_path: Path to the parsed file
            file_hash: SHA256 hash of file contents
            language: Detected language
            endpoints: List of serialized endpoints
            symbols: Dictionary of symbols
            parse_time_ms: Time taken to parse
            project_path: Root path of the project (for batch invalidation)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO file_cache 
                (file_path, file_hash, language, endpoints, symbols, parse_time_ms, cached_at, project_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                file_path,
                file_hash,
                language,
                json.dumps(endpoints, ensure_ascii=False),
                json.dumps(symbols, ensure_ascii=False),
                parse_time_ms,
                time.time(),
                project_path
            ))
            conn.commit()
            self._stats["saves"] += 1
    
    def invalidate(self, file_path: str):
        """
        Invalidate cache for a specific file.
        
        Args:
            file_path: Path to the file
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM file_cache WHERE file_path = ?', (file_path,))
            if cursor.rowcount > 0:
                self._stats["invalidations"] += 1
            conn.commit()
    
    def invalidate_project(self, project_path: str):
        """
        Invalidate cache for all files in a project.
        
        Args:
            project_path: Root path of the project
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Match files that start with project_path
            cursor.execute(
                'DELETE FROM file_cache WHERE file_path LIKE ?',
                (project_path + '%',)
            )
            count = cursor.rowcount
            if count > 0:
                self._stats["invalidations"] += count
            conn.commit()
            return count
    
    def get_changed_files(self, files: List[str]) -> Tuple[List[str], List[str], Dict[str, str]]:
        """
        Identify which files have changed and need re-parsing.
        
        Args:
            files: List of file paths to check
            
        Returns:
            Tuple of (changed_files, unchanged_files, file_hashes)
        """
        changed = []
        unchanged = []
        file_hashes = {}
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            for file_path in files:
                current_hash = self.compute_file_hash(file_path)
                if current_hash is None:
                    changed.append(file_path)
                    continue
                
                file_hashes[file_path] = current_hash
                
                cursor.execute(
                    'SELECT file_hash FROM file_cache WHERE file_path = ?',
                    (file_path,)
                )
                row = cursor.fetchone()
                
                if row is None or row['file_hash'] != current_hash:
                    changed.append(file_path)
                else:
                    unchanged.append(file_path)
        
        return changed, unchanged, file_hashes
    
    def get_cached_batch(self, file_paths: List[str]) -> Dict[str, CachedParseResult]:
        """
        Get cached results for multiple files at once.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Dictionary mapping file_path to CachedParseResult
        """
        results = {}
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # SQLite has a limit on placeholders, batch if needed
            batch_size = 500
            for i in range(0, len(file_paths), batch_size):
                batch = file_paths[i:i + batch_size]
                placeholders = ','.join('?' * len(batch))
                
                cursor.execute(
                    f'SELECT * FROM file_cache WHERE file_path IN ({placeholders})',
                    batch
                )
                
                for row in cursor.fetchall():
                    try:
                        results[row['file_path']] = CachedParseResult(
                            file_path=row['file_path'],
                            file_hash=row['file_hash'],
                            language=row['language'] or 'unknown',
                            endpoints=json.loads(row['endpoints'] or '[]'),
                            symbols=json.loads(row['symbols'] or '{}'),
                            parse_time_ms=row['parse_time_ms'] or 0.0,
                            cached_at=row['cached_at'] or 0.0
                        )
                    except (json.JSONDecodeError, KeyError):
                        continue
        
        return results
    
    def clear(self):
        """Clear all cached data."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM file_cache')
            conn.commit()
        self._stats = {"hits": 0, "misses": 0, "invalidations": 0, "saves": 0}
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM file_cache')
            total_cached = cursor.fetchone()['count']
            
            cursor.execute('SELECT SUM(LENGTH(endpoints) + LENGTH(symbols)) as size FROM file_cache')
            row = cursor.fetchone()
            total_size = row['size'] if row['size'] else 0
        
        hit_rate = 0.0
        total_requests = self._stats["hits"] + self._stats["misses"]
        if total_requests > 0:
            hit_rate = self._stats["hits"] / total_requests
        
        return {
            "total_cached_files": total_cached,
            "total_size_bytes": total_size,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": hit_rate,
            "invalidations": self._stats["invalidations"],
            "saves": self._stats["saves"],
            "db_path": self.db_path
        }
    
    def get_db_size(self) -> int:
        """Get the size of the cache database file in bytes."""
        try:
            return os.path.getsize(self.db_path)
        except OSError:
            return 0


# Singleton instance
analysis_cache = AnalysisCache()
