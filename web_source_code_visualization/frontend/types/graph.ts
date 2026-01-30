import { Node, Edge } from 'reactflow';

// ============================================
// API Response Types
// ============================================

export interface Parameter {
    name: string;
    type?: string;
    source?: 'path' | 'query' | 'body' | 'header' | 'cookie';
}

export interface Filter {
    name: string;
    args?: string[];
    line?: number;
}

export interface TemplateContext {
    name: string;
}

export interface TemplateUsage {
    name: string;
    line?: number;
}

export interface SecurityFinding {
    id?: string;
    check_id: string;
    rule_id?: string;
    path: string;
    line: number;
    col?: number;
    start?: { line: number; col?: number };
    severity: 'HIGH' | 'MEDIUM' | 'LOW' | 'WARNING' | 'ERROR' | 'INFO' | string;
    message: string;
    extra?: { message?: string; severity?: string };
}

export interface Endpoint {
    id: string;
    type: 'cluster' | 'root' | 'function' | 'call' | 'child' | 'database' | 'input' | 'template' | 'sink' | 'api_call' | 'event_handler';
    path: string;
    method?: string;
    file_path?: string;
    line_number?: number;
    end_line_number?: number;
    params?: Parameter[];
    filters?: Filter[];
    template_context?: TemplateContext[];
    template_usage?: TemplateUsage[];
    children?: Endpoint[];
    metadata?: Record<string, any>;
}

export interface TaintFlowEdge {
    id: string;
    source_node_id: string;
    sink_node_id: string;
    source_name: string;
    sink_name: string;
    vulnerability_type: string;
    severity: 'HIGH' | 'MEDIUM' | 'LOW';
    path: string[];
    sanitized: boolean;
    sanitizer?: string;
}

export interface AnalysisData {
    root_path: string;
    language_stats: Record<string, number>;
    endpoints: Endpoint[];
    taint_flows: TaintFlowEdge[];
    call_graph?: CallGraphData;
}

// ============================================
// Call Graph Types
// ============================================

export interface CallGraphNode {
    id: string;
    name: string;
    qualified_name: string;
    file_path: string;
    line_number: number;
    end_line: number;
    node_type: 'function' | 'method' | 'class' | 'module';
    is_entry_point: boolean;
    is_sink: boolean;
    callers: string[];
    callees: string[];
}

export interface CallGraphEdge {
    id: string;
    source_id: string;
    target_id: string;
    call_site_line: number;
    call_type: 'direct' | 'callback' | 'async' | 'decorator';
}

export interface CallGraphData {
    nodes: CallGraphNode[];
    edges: CallGraphEdge[];
    entry_points: string[];
    sinks: string[];
}

// ============================================
// Component State Types
// ============================================

export interface AIAnalysisState {
    loading: boolean;
    result: string | null;
    model?: string;
}

export interface NodeData {
    label: string;
    file_path?: string;
    line_number?: number;
    end_line_number?: number;
    params?: Parameter[];
    filters?: Filter[];
    template_context?: TemplateContext[];
    template_usage?: TemplateUsage[];
    findings?: SecurityFinding[];
    vulnerabilityCount?: number;
    initialStyle?: React.CSSProperties;
    inputs?: { name: string; source: string }[];
    [key: string]: any;
}

export type GraphNode = Node<NodeData>;
export type GraphEdge = Edge;

// ============================================
// Props Types
// ============================================

export interface ControlBarProps {
    projectPath: string;
    onProjectPathChange: (path: string) => void;
    onAnalyze: () => void;
    onScan: () => void;
    onToggleFileTree: () => void;
    onToggleSinks: () => void;
    onToggleTaintFlows: () => void;
    onToggleCallGraph: () => void;
    onToggleStreaming?: () => void;
    loading: boolean;
    scanning: boolean;
    showFileTree: boolean;
    showSinks: boolean;
    showTaintFlows: boolean;
    showCallGraph: boolean;
    useStreaming?: boolean;
    isStreaming?: boolean;
}

export interface FileTreeSidebarProps {
    files: string[];
    selectedFiles: Set<string>;
    onToggleFile: (file: string) => void;
    onSelectAll: () => void;
    onSelectNone: () => void;
}

export interface DetailPanelProps {
    node: GraphNode;
    code: string;
    aiAnalysis: AIAnalysisState;
    onClose: () => void;
    onAnalyzeAI: () => void;
    panelWidth: number;
    isResizing: boolean;
    onStartResize: (e: React.MouseEvent) => void;
}
