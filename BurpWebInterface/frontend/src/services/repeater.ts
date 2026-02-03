import client from './client';

export interface RepeaterRequest {
    request: string;
    host: string;
    port: number;
    use_https: boolean;
}

export interface RepeaterResponse {
    response: string;
    status_code: number;
    elapsed_time: number;
}

export const repeaterApi = {
    sendRequest: async (data: RepeaterRequest): Promise<RepeaterResponse> => {
        const response = await client.post('/api/repeater/send', data);
        return response.data;
    }
};
