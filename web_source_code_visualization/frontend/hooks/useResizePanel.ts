"use client";

import { useState, useCallback, useEffect } from 'react';

interface UseResizePanelOptions {
    initialWidth?: number;
    minWidth?: number;
    maxWidthOffset?: number;
}

interface UseResizePanelReturn {
    panelWidth: number;
    isResizing: boolean;
    startResizing: (e: React.MouseEvent) => void;
}

/**
 * Custom hook for handling resizable panel logic
 */
export function useResizePanel(options: UseResizePanelOptions = {}): UseResizePanelReturn {
    const {
        initialWidth = 800,
        minWidth = 400,
        maxWidthOffset = 100
    } = options;

    const [panelWidth, setPanelWidth] = useState(initialWidth);
    const [isResizing, setIsResizing] = useState(false);

    const startResizing = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        setIsResizing(true);
    }, []);

    const stopResizing = useCallback(() => {
        setIsResizing(false);
    }, []);

    const resize = useCallback(
        (mouseMoveEvent: MouseEvent) => {
            if (isResizing) {
                const newWidth = window.innerWidth - mouseMoveEvent.clientX;
                if (newWidth > minWidth && newWidth < window.innerWidth - maxWidthOffset) {
                    setPanelWidth(newWidth);
                }
            }
        },
        [isResizing, minWidth, maxWidthOffset]
    );

    useEffect(() => {
        window.addEventListener("mousemove", resize);
        window.addEventListener("mouseup", stopResizing);
        return () => {
            window.removeEventListener("mousemove", resize);
            window.removeEventListener("mouseup", stopResizing);
        };
    }, [resize, stopResizing]);

    return {
        panelWidth,
        isResizing,
        startResizing
    };
}
