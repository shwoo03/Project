import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';

interface WebSocketContextType {
    isConnected: boolean;
    lastMessage: any;
    sendMessage: (message: any) => void;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [isConnected, setIsConnected] = useState(false);
    const [lastMessage, setLastMessage] = useState<any>(null);
    const ws = useRef<WebSocket | null>(null);
    const reconnectTimeout = useRef<number | null>(null);

    const connect = useCallback(() => {
        // Port 10006 is backend
        const wsUrl = 'ws://localhost:10006/ws';
        const socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log('✅ WebSocket Connected');
            setIsConnected(true);
            if (reconnectTimeout.current) {
                clearTimeout(reconnectTimeout.current);
                reconnectTimeout.current = null;
            }
        };

        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                setLastMessage(data);
            } catch (e) {
                console.log('Received raw message:', event.data);
                // Handle plain text messages like "pong"
                setLastMessage({ type: 'text', payload: event.data });
            }
        };

        socket.onclose = () => {
            console.log('❌ WebSocket Disconnected');
            setIsConnected(false);
            ws.current = null;

            // Attempt reconnect after 3 seconds
            if (!reconnectTimeout.current) {
                reconnectTimeout.current = window.setTimeout(() => {
                    console.log('🔄 Attempting to reconnect...');
                    connect();
                }, 3000);
            }
        };

        socket.onerror = (error) => {
            console.error('WebSocket Error:', error);
            socket.close();
        };

        ws.current = socket;
    }, []);

    useEffect(() => {
        connect();
        return () => {
            if (ws.current) {
                ws.current.close();
            }
            if (reconnectTimeout.current) {
                clearTimeout(reconnectTimeout.current);
            }
        };
    }, [connect]);

    const sendMessage = useCallback((message: any) => {
        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            const payload = typeof message === 'string' ? message : JSON.stringify(message);
            ws.current.send(payload);
        } else {
            console.warn('WebSocket is not connected');
        }
    }, []);

    return (
        <WebSocketContext.Provider value={{ isConnected, lastMessage, sendMessage }}>
            {children}
        </WebSocketContext.Provider>
    );
};

export const useWebSocket = () => {
    const context = useContext(WebSocketContext);
    if (!context) {
        throw new Error('useWebSocket must be used within a WebSocketProvider');
    }
    return context;
};
