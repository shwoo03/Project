import client from './client';

export interface HealthStatus {
    status: string;
    mcp_connected: boolean;
    version: string;
}

export const systemApi = {
    checkHealth: async () => {
        const response = await client.get<HealthStatus>('/api/health');
        return response.data;
    },

    listTools: async () => {
        const response = await client.get('/api/mcp/tools');
        return response.data;
    }
};
