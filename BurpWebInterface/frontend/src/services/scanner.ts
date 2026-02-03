import client from './client';

export interface ScanRequest {
    url: string;
    scan_type: 'active' | 'passive';
}

export interface ScanIssue {
    id: string;
    name: string;
    severity: 'high' | 'medium' | 'low' | 'info';
    url: string;
    confidence: string;
}

export const scannerApi = {
    startScan: async (data: ScanRequest) => {
        const response = await client.post('/api/scanner/scan', data);
        return response.data;
    },

    getIssues: async () => {
        const response = await client.get<{ issues: ScanIssue[] }>('/api/scanner/issues');
        return response.data;
    },

    getStats: async () => {
        const response = await client.get('/api/scanner/stats');
        return response.data;
    }
};
