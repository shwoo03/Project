"""
Scanner Service - Business logic for Vulnerability Scanning
"""
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid
from services.base import BaseService


class ScanType(str, Enum):
    ACTIVE = "active"
    PASSIVE = "passive"


class ScanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ERROR = "error"


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ScanIssue:
    """Vulnerability issue"""
    id: str
    name: str
    severity: Severity
    confidence: str
    url: str
    description: str
    remediation: Optional[str] = None
    evidence: Optional[str] = None


@dataclass
class Scan:
    """Scan state"""
    id: str
    url: str
    scan_type: ScanType
    status: ScanStatus = ScanStatus.PENDING
    progress: float = 0.0
    issues_found: int = 0
    error: Optional[str] = None


@dataclass
class ScannerStats:
    """Scanner statistics"""
    total_issues: int
    by_severity: Dict[str, int]
    active_scans: int


class ScannerService(BaseService):
    """Service for Scanner-related operations"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._scans: Dict[str, Scan] = {}
    
    # Scan Management
    def list_scans(self) -> List[Scan]:
        """Get all scans"""
        return list(self._scans.values())
    
    def get_scan(self, scan_id: str) -> Optional[Scan]:
        """Get a specific scan"""
        return self._scans.get(scan_id)
    
    def scan_exists(self, scan_id: str) -> bool:
        """Check if a scan exists"""
        return scan_id in self._scans
    
    async def start_scan(self, url: str, scan_type: ScanType = ScanType.ACTIVE) -> Scan:
        """
        Start a new vulnerability scan
        
        Args:
            url: Target URL to scan
            scan_type: Type of scan (active/passive)
            
        Returns:
            Created Scan object
        """
        scan_id = str(uuid.uuid4())
        
        scan = Scan(
            id=scan_id,
            url=url,
            scan_type=scan_type,
            status=ScanStatus.RUNNING
        )
        
        self._scans[scan_id] = scan
        
        # Start scan via MCP
        await self.mcp.start_active_scan(url)
        
        return scan
    
    def stop_scan(self, scan_id: str) -> bool:
        """Stop a running scan"""
        scan = self.get_scan(scan_id)
        if not scan:
            return False
        scan.status = ScanStatus.STOPPED
        self._scans[scan_id] = scan
        return True
    
    # Issue Management
    async def get_all_issues(self) -> List[ScanIssue]:
        """Get all scanner issues"""
        raw_issues = await self.mcp.get_scan_issues()
        return [self._parse_issue(issue) for issue in raw_issues]
    
    async def get_filtered_issues(
        self,
        severity: Optional[Severity] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get filtered issues with pagination
        
        Args:
            severity: Filter by severity
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            Dictionary with issues and pagination info
        """
        issues = await self.get_all_issues()
        
        if severity:
            issues = [i for i in issues if i.severity == severity]
        
        total = len(issues)
        paginated = issues[offset:offset + limit]
        
        return {
            "total": total,
            "issues": paginated,
            "limit": limit,
            "offset": offset
        }
    
    async def get_issue_by_id(self, issue_id: str) -> Optional[ScanIssue]:
        """Get a specific issue by ID"""
        issues = await self.get_all_issues()
        for issue in issues:
            if issue.id == issue_id:
                return issue
        return None
    
    def _parse_issue(self, raw: Dict) -> ScanIssue:
        """Parse raw issue data into ScanIssue"""
        severity_str = raw.get("severity", "info").lower()
        severity = Severity(severity_str) if severity_str in [s.value for s in Severity] else Severity.INFO
        
        return ScanIssue(
            id=raw.get("id", ""),
            name=raw.get("name", "Unknown Issue"),
            severity=severity,
            confidence=raw.get("confidence", "Tentative"),
            url=raw.get("url", ""),
            description=raw.get("description", ""),
            remediation=raw.get("remediation"),
            evidence=raw.get("evidence")
        )
    
    # Statistics
    async def get_stats(self) -> ScannerStats:
        """Calculate scanner statistics"""
        issues = await self.get_all_issues()
        
        by_severity = {s.value: 0 for s in Severity}
        for issue in issues:
            by_severity[issue.severity.value] += 1
        
        active_scans = len([s for s in self._scans.values() if s.status == ScanStatus.RUNNING])
        
        return ScannerStats(
            total_issues=len(issues),
            by_severity=by_severity,
            active_scans=active_scans
        )


# Singleton instance
scanner_service = ScannerService()
