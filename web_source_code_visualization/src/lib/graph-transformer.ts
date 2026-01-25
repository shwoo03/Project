import { Node, Edge, Position } from 'reactflow';
import dagre from 'dagre';

export interface RouteData {
    file: string;
    line: number;
    method: string;
    path: string;
    type: string;
    framework: string;
    params?: string[];
    sinks?: {
        type: string;
        detail: string;
        flowPath?: { type: string; label: string; line: number; varName?: string }[]
    }[];
    sanitizers?: { type: string; detail: string }[];
    riskLevel?: 'critical' | 'high' | 'medium' | 'low';
}

const methodColors: Record<string, string> = {
    GET: '#3b82f6', // blue-500
    POST: '#22c55e', // green-500
    PUT: '#eab308', // yellow-500
    DELETE: '#ef4444', // red-500
    PATCH: '#a855f7', // purple-500
    USE: '#64748b', // slate-500
};

const nodeWidth = 250;
const nodeHeight = 120; // Approx height for auto layout

export function transformRoutesToGraph(routes: RouteData[]): { nodes: Node[], edges: Edge[] } {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));

    // Set direction to Top-to-Bottom
    dagreGraph.setGraph({ rankdir: 'TB', nodesep: 50, ranksep: 100 });

    const nodes: Node[] = [];
    const edges: Edge[] = [];

    // Group routes by top-level path segment (e.g., /api, /auth, /admin)
    // to create hierarchy structure: Root -> Segment -> Endpoint
    const hierarchy: Record<string, string[]> = {};

    routes.forEach((route, idx) => {
        const id = `route-${idx}`;

        // Add Node to Dagre
        dagreGraph.setNode(id, { width: nodeWidth, height: nodeHeight });

        // Determine parent segment
        const parts = route.path.split('/').filter(Boolean);
        const topLevel = parts.length > 0 ? `/${parts[0]}` : '/root';

        if (!hierarchy[topLevel]) {
            hierarchy[topLevel] = [];
            // Add segment node to Dagre
            dagreGraph.setNode(topLevel, { width: 150, height: 50 });
            // Edge Root -> Segment
            dagreGraph.setEdge('ROOT', topLevel);
        }

        // Edge Segment -> Endpoint
        dagreGraph.setEdge(topLevel, id);

        // Create ReactFlow Node Object (Metadata only, position comes later)
        nodes.push({
            id: id,
            type: 'custom', // Use our new CustomNode
            data: {
                label: route.path,
                details: route,
                isCritical: route.riskLevel === 'critical' || route.riskLevel === 'high'
            },
            position: { x: 0, y: 0 } // Placeholder
        });
    });

    // Add Root and Segment Nodes for visualization
    nodes.push({
        id: 'ROOT',
        type: 'input',
        data: { label: 'Application' },
        position: { x: 0, y: 0 },
        style: { background: '#1e293b', color: '#fff', border: '1px solid #94a3b8', width: 150, textAlign: 'center' }
    });
    dagreGraph.setNode('ROOT', { width: 150, height: 50 });

    Object.keys(hierarchy).forEach(segment => {
        nodes.push({
            id: segment,
            data: { label: segment },
            position: { x: 0, y: 0 },
            style: {
                background: '#334155',
                color: '#e2e8f0',
                borderRadius: '20px',
                border: '1px dashed #64748b',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
            }
        });

        // Create Edges for reactflow
        edges.push({
            id: `e-ROOT-${segment}`,
            source: 'ROOT',
            target: segment,
            type: 'smoothstep',
            style: { stroke: '#475569', strokeDasharray: '5,5' }
        });

        // Find children in Dagre graph to link
        const children = dagreGraph.outEdges(segment);
        children?.forEach(e => {
            const childId = e.w;

            // Check if the target child is critical
            const targetNode = nodes.find(n => n.id === childId);
            const isCriticalPath = targetNode?.data?.isCritical;

            edges.push({
                id: `e-${segment}-${childId}`,
                source: segment,
                target: childId,
                type: 'smoothstep',
                animated: isCriticalPath, // Animate if critical
                style: {
                    stroke: isCriticalPath ? '#ef4444' : '#64748b', // Red if critical
                    strokeWidth: isCriticalPath ? 2 : 1
                },
                label: isCriticalPath ? 'Attack Vector' : undefined,
                labelStyle: { fill: '#f87171', fontWeight: 700 }
            });
        });
    });

    // Calculate Layout
    dagre.layout(dagreGraph);

    // Apply positions
    return {
        nodes: nodes.map((node) => {
            const nodeWithPosition = dagreGraph.node(node.id);
            return {
                ...node,
                targetPosition: Position.Top,
                sourcePosition: Position.Bottom,
                position: {
                    x: nodeWithPosition.x - (nodeWithPosition.width / 2),
                    y: nodeWithPosition.y - (nodeWithPosition.height / 2),
                },
            };
        }),
        edges,
    };
}
