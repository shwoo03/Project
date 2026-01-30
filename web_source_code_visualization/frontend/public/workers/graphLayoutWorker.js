/**
 * Web Worker: 그래프 레이아웃 계산
 * 
 * Dagre 레이아웃 알고리즘을 백그라운드 스레드에서 실행하여
 * 메인 스레드 블로킹을 방지합니다.
 * 
 * @file graphLayoutWorker.js
 */

// Dagre 레이아웃 알고리즘 (간단한 구현)
// 실제 프로덕션에서는 dagre 라이브러리를 번들링하여 사용

/**
 * 토폴로지 정렬을 통한 계층 할당
 */
function assignLayers(nodes, edges) {
    const nodeMap = new Map();
    const inDegree = new Map();
    const outEdges = new Map();
    
    nodes.forEach(node => {
        nodeMap.set(node.id, node);
        inDegree.set(node.id, 0);
        outEdges.set(node.id, []);
    });
    
    edges.forEach(edge => {
        const target = edge.target;
        inDegree.set(target, (inDegree.get(target) || 0) + 1);
        
        const sourceEdges = outEdges.get(edge.source) || [];
        sourceEdges.push(edge.target);
        outEdges.set(edge.source, sourceEdges);
    });
    
    // BFS로 레이어 할당
    const layers = new Map();
    const queue = [];
    
    nodes.forEach(node => {
        if (inDegree.get(node.id) === 0) {
            queue.push(node.id);
            layers.set(node.id, 0);
        }
    });
    
    while (queue.length > 0) {
        const current = queue.shift();
        const currentLayer = layers.get(current) || 0;
        
        const successors = outEdges.get(current) || [];
        successors.forEach(successor => {
            const newLayer = currentLayer + 1;
            const existingLayer = layers.get(successor) || 0;
            
            if (newLayer > existingLayer) {
                layers.set(successor, newLayer);
            }
            
            const deg = inDegree.get(successor) - 1;
            inDegree.set(successor, deg);
            
            if (deg === 0) {
                queue.push(successor);
            }
        });
    }
    
    // 레이어가 없는 노드(고립 노드)는 레이어 0에 할당
    nodes.forEach(node => {
        if (!layers.has(node.id)) {
            layers.set(node.id, 0);
        }
    });
    
    return layers;
}

/**
 * 레이어 내 노드 정렬 (교차 최소화)
 */
function orderNodesInLayers(nodes, edges, layers) {
    const layerNodes = new Map();
    
    nodes.forEach(node => {
        const layer = layers.get(node.id) || 0;
        if (!layerNodes.has(layer)) {
            layerNodes.set(layer, []);
        }
        layerNodes.get(layer).push(node);
    });
    
    // 각 레이어 내에서 노드 순서 결정 (베리센터 휴리스틱)
    const order = new Map();
    const sortedLayers = Array.from(layerNodes.keys()).sort((a, b) => a - b);
    
    // 첫 번째 레이어는 임의 순서
    if (sortedLayers.length > 0) {
        const firstLayer = layerNodes.get(sortedLayers[0]) || [];
        firstLayer.forEach((node, idx) => {
            order.set(node.id, idx);
        });
    }
    
    // 이후 레이어는 상위 레이어 기준으로 정렬
    const predecessors = new Map();
    edges.forEach(edge => {
        if (!predecessors.has(edge.target)) {
            predecessors.set(edge.target, []);
        }
        predecessors.get(edge.target).push(edge.source);
    });
    
    for (let i = 1; i < sortedLayers.length; i++) {
        const currentLayerNodes = layerNodes.get(sortedLayers[i]) || [];
        
        // 베리센터 계산
        const barycenters = currentLayerNodes.map(node => {
            const preds = predecessors.get(node.id) || [];
            if (preds.length === 0) return { node, barycenter: 0 };
            
            const sum = preds.reduce((acc, pred) => {
                return acc + (order.get(pred) || 0);
            }, 0);
            
            return { node, barycenter: sum / preds.length };
        });
        
        // 베리센터 기준 정렬
        barycenters.sort((a, b) => a.barycenter - b.barycenter);
        barycenters.forEach(({ node }, idx) => {
            order.set(node.id, idx);
        });
    }
    
    return { order, layerNodes, sortedLayers };
}

/**
 * 최종 좌표 할당
 */
function assignCoordinates(nodes, layers, order, layerNodes, sortedLayers, options) {
    const {
        nodeWidth = 180,
        nodeHeight = 50,
        rankSep = 80,
        nodeSep = 40,
        direction = 'TB' // TB, BT, LR, RL
    } = options;
    
    const positions = new Map();
    const isHorizontal = direction === 'LR' || direction === 'RL';
    
    sortedLayers.forEach((layer, layerIndex) => {
        const nodesInLayer = layerNodes.get(layer) || [];
        
        // 레이어 내 노드 정렬
        nodesInLayer.sort((a, b) => {
            return (order.get(a.id) || 0) - (order.get(b.id) || 0);
        });
        
        const layerWidth = nodesInLayer.length * (isHorizontal ? nodeHeight : nodeWidth) 
                         + (nodesInLayer.length - 1) * nodeSep;
        const startOffset = -layerWidth / 2;
        
        nodesInLayer.forEach((node, idx) => {
            const offset = startOffset + idx * ((isHorizontal ? nodeHeight : nodeWidth) + nodeSep);
            
            let x, y;
            
            if (isHorizontal) {
                x = layerIndex * (nodeWidth + rankSep);
                y = offset;
                
                if (direction === 'RL') {
                    x = -x;
                }
            } else {
                x = offset;
                y = layerIndex * (nodeHeight + rankSep);
                
                if (direction === 'BT') {
                    y = -y;
                }
            }
            
            positions.set(node.id, { x, y });
        });
    });
    
    return positions;
}

/**
 * 메인 레이아웃 함수
 */
function calculateLayout(nodes, edges, options = {}) {
    if (!nodes || nodes.length === 0) {
        return { nodes: [], edges: [] };
    }
    
    const startTime = performance.now();
    
    // 1. 레이어 할당
    const layers = assignLayers(nodes, edges);
    
    // 2. 레이어 내 순서 결정
    const { order, layerNodes, sortedLayers } = orderNodesInLayers(nodes, edges, layers);
    
    // 3. 좌표 할당
    const positions = assignCoordinates(nodes, layers, order, layerNodes, sortedLayers, options);
    
    // 4. 결과 노드 생성
    const layoutNodes = nodes.map(node => {
        const pos = positions.get(node.id) || { x: 0, y: 0 };
        return {
            ...node,
            position: pos,
        };
    });
    
    const layoutTime = performance.now() - startTime;
    
    return {
        nodes: layoutNodes,
        edges: edges,
        layoutTime,
        stats: {
            nodeCount: nodes.length,
            edgeCount: edges.length,
            layerCount: sortedLayers.length,
        },
    };
}

/**
 * 청크 기반 점진적 레이아웃 (대규모 그래프용)
 */
function calculateLayoutProgressive(nodes, edges, options = {}) {
    const { chunkSize = 100, onProgress } = options;
    const totalNodes = nodes.length;
    const chunks = Math.ceil(totalNodes / chunkSize);
    
    let processedNodes = [];
    let result = null;
    
    for (let i = 0; i < chunks; i++) {
        const start = i * chunkSize;
        const end = Math.min(start + chunkSize, totalNodes);
        const chunkNodes = nodes.slice(start, end);
        
        processedNodes = processedNodes.concat(chunkNodes);
        
        // 현재까지의 노드로 레이아웃 계산
        const relevantEdges = edges.filter(edge => {
            const nodeIds = new Set(processedNodes.map(n => n.id));
            return nodeIds.has(edge.source) && nodeIds.has(edge.target);
        });
        
        result = calculateLayout(processedNodes, relevantEdges, options);
        
        // 진행 상황 보고
        if (onProgress) {
            onProgress({
                progress: (i + 1) / chunks,
                processedNodes: processedNodes.length,
                totalNodes,
            });
        }
    }
    
    return result;
}

// 메시지 핸들러
self.onmessage = function(event) {
    const { type, id, payload } = event.data;
    
    try {
        switch (type) {
            case 'CALCULATE_LAYOUT': {
                const { nodes, edges, options } = payload;
                const result = calculateLayout(nodes, edges, options);
                
                self.postMessage({
                    type: 'LAYOUT_COMPLETE',
                    id,
                    payload: result,
                });
                break;
            }
            
            case 'CALCULATE_LAYOUT_PROGRESSIVE': {
                const { nodes, edges, options } = payload;
                
                const progressOptions = {
                    ...options,
                    onProgress: (progress) => {
                        self.postMessage({
                            type: 'LAYOUT_PROGRESS',
                            id,
                            payload: progress,
                        });
                    },
                };
                
                const result = calculateLayoutProgressive(nodes, edges, progressOptions);
                
                self.postMessage({
                    type: 'LAYOUT_COMPLETE',
                    id,
                    payload: result,
                });
                break;
            }
            
            case 'PING': {
                self.postMessage({
                    type: 'PONG',
                    id,
                    payload: { timestamp: Date.now() },
                });
                break;
            }
            
            default:
                console.warn('Unknown message type:', type);
        }
    } catch (error) {
        self.postMessage({
            type: 'ERROR',
            id,
            payload: {
                message: error.message,
                stack: error.stack,
            },
        });
    }
};

// Worker 준비 완료 알림
self.postMessage({ type: 'READY' });
