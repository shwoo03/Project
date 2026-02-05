
import React from 'react';

interface BadgeProps {
    type: 'method' | 'status';
    value: string | number;
    className?: string; // Allow custom classes
}

export const Badge: React.FC<BadgeProps> = ({ type, value, className = '' }) => {
    let colorClass = 'bg-gray-500 text-white';

    if (type === 'method') {
        const method = String(value).toUpperCase();
        const colors: Record<string, string> = {
            GET: 'bg-green-500',
            POST: 'bg-blue-500',
            PUT: 'bg-yellow-500',
            DELETE: 'bg-red-500',
            PATCH: 'bg-purple-500'
        };
        colorClass = colors[method] || 'bg-gray-500';
        return (
            <span className={`${colorClass} px-2 py-1 rounded text-xs font-medium text-white ${className}`}>
                {value}
            </span>
        );
    } else if (type === 'status') {
        const status = Number(value);
        if (status >= 200 && status < 300) colorClass = 'text-green-400';
        else if (status >= 300 && status < 400) colorClass = 'text-blue-400';
        else if (status >= 400 && status < 500) colorClass = 'text-yellow-400';
        else if (status >= 500) colorClass = 'text-red-400';
        else colorClass = 'text-gray-400';

        return (
            <span className={`${colorClass} font-medium ${className}`}>
                {value || '-'}
            </span>
        );
    }

    return null;
};
