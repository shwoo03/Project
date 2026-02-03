import client from './client';

export interface ProxyEntry {
    id: string;
    method: string;
    host: string;
    path: string;
    status_code: number;
    length: number;
    mime_type: string;
    timestamp?: string;
    request?: string;
    response?: string;
}

export interface ProxyFilter {
    method?: string;
    host?: string;
    status_code?: number;
    path_contains?: string;
    mime_type?: string;
}

export interface ProxyHistoryResponse {
    entries: ProxyEntry[];
    total: number;
    limit: number;
    offset: number;
}

export const proxyApi = {
    getHistory: async (limit = 100, offset = 0, filters?: ProxyFilter) => {
        const params = { limit, offset, ...filters };
        const response = await client.get<ProxyHistoryResponse>('/api/proxy/history', { params });
        return response.data;
    },

    getDetails: async (id: string) => {
        const response = await client.get<ProxyEntry>(`/api/proxy/request/${id}`);
        return response.data;
    },

    sendToRepeater: async (id: string) => {
        const response = await client.post(`/api/proxy/request/${id}/send-to-repeater`);
        return response.data;
    },

    getStats: async () => {
        const response = await client.get('/api/proxy/stats');
        return response.data;
    }
};
