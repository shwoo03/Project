"use client";

import React, { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, AlertCircle, WifiOff, AlertTriangle } from 'lucide-react';
import { AppError, ErrorType } from '@/types/errors';

interface ErrorToastProps {
    error: AppError | null;
    onDismiss: () => void;
    autoDismissMs?: number;
}

const errorConfig: Record<ErrorType, { icon: React.ReactNode; bgClass: string; borderClass: string }> = {
    connection: {
        icon: <WifiOff size={20} />,
        bgClass: 'bg-red-900/90',
        borderClass: 'border-red-500'
    },
    api: {
        icon: <AlertCircle size={20} />,
        bgClass: 'bg-orange-900/90',
        borderClass: 'border-orange-500'
    },
    parse: {
        icon: <AlertTriangle size={20} />,
        bgClass: 'bg-yellow-900/90',
        borderClass: 'border-yellow-500'
    },
    unknown: {
        icon: <AlertCircle size={20} />,
        bgClass: 'bg-zinc-800/90',
        borderClass: 'border-zinc-500'
    }
};

/**
 * Toast component for displaying errors
 */
export function ErrorToast({ error, onDismiss, autoDismissMs = 5000 }: ErrorToastProps) {
    useEffect(() => {
        if (error && autoDismissMs > 0) {
            const timer = setTimeout(onDismiss, autoDismissMs);
            return () => clearTimeout(timer);
        }
    }, [error, autoDismissMs, onDismiss]);

    return (
        <AnimatePresence>
            {error && (
                <motion.div
                    initial={{ opacity: 0, y: -50, x: '-50%' }}
                    animate={{ opacity: 1, y: 0, x: '-50%' }}
                    exit={{ opacity: 0, y: -50, x: '-50%' }}
                    className={`fixed top-4 left-1/2 z-[100] max-w-md w-full px-4 py-3 rounded-lg border backdrop-blur-md shadow-2xl ${errorConfig[error.type].bgClass} ${errorConfig[error.type].borderClass}`}
                >
                    <div className="flex items-start gap-3">
                        <div className="text-white/80 mt-0.5">
                            {errorConfig[error.type].icon}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-white font-medium text-sm">{error.message}</p>
                            {error.details && (
                                <p className="text-white/60 text-xs mt-1 truncate">{error.details}</p>
                            )}
                        </div>
                        <button
                            onClick={onDismiss}
                            className="text-white/60 hover:text-white transition-colors"
                        >
                            <X size={18} />
                        </button>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}

export default ErrorToast;
