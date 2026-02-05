
import React from 'react';
import { Search, Filter } from 'lucide-react';

interface ProxyFiltersProps {
    filter: string;
    setFilter: (value: string) => void;
}

export const ProxyFilters: React.FC<ProxyFiltersProps> = ({ filter, setFilter }) => {
    return (
        <div className="flex gap-4 mb-6">
            <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
                <input
                    type="text"
                    placeholder="Filter by host or path..."
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg py-2 pl-10 pr-4 text-white focus:border-burp-orange focus:outline-none"
                />
            </div>
            <button className="flex items-center gap-2 bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg transition-colors">
                <Filter size={18} />
                Filters
            </button>
        </div>
    );
};
