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
    check_id: string;
    path: string;
    line: number;
    severity: 'HIGH' | 'MEDIUM' | 'LOW' | 'WARNING' | 'ERROR';
    message: string;
}

export interface Endpoint {
    id: string;
    type: 'cluster' | 'root' | 'function' | 'call' | 'child' | 'database' | 'input' | 'template';
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
}

export interface AnalysisData {
    root_path: string;
    language_stats: Record<string, number>;
    endpoints: Endpoint[];
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
    loading: boolean;
    scanning: boolean;
    showFileTree: boolean;
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
