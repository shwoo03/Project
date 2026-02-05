
import React from 'react';
import { RefreshCw, ExternalLink } from 'lucide-react';
import { ProxyEntry } from '../../services';
import { Badge } from '../common/Badge';

interface ProxyTableProps {
    entries: ProxyEntry[];
    loading: boolean;
}

export const ProxyTable: React.FC<ProxyTableProps> = ({ entries, loading }) => {
    return (
        <div className="glass rounded-xl overflow-hidden">
            <table className="w-full">
                <thead className="bg-gray-800/50">
                    <tr>
                        <th className="text-left py-3 px-4 text-gray-400 font-medium">#</th>
                        <th className="text-left py-3 px-4 text-gray-400 font-medium">Method</th>
                        <th className="text-left py-3 px-4 text-gray-400 font-medium">Host</th>
                        <th className="text-left py-3 px-4 text-gray-400 font-medium">Path</th>
                        <th className="text-left py-3 px-4 text-gray-400 font-medium">Status</th>
                        <th className="text-left py-3 px-4 text-gray-400 font-medium">Length</th>
                        <th className="text-left py-3 px-4 text-gray-400 font-medium">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {loading ? (
                        <tr>
                            <td colSpan={7} className="text-center py-8 text-gray-400">
                                <RefreshCw className="animate-spin inline mr-2" size={20} />
                                Loading...
                            </td>
                        </tr>
                    ) : entries.length === 0 ? (
                        <tr>
                            <td colSpan={7} className="text-center py-8 text-gray-400">
                                No requests captured yet. Configure your browser to use Burp Proxy.
                            </td>
                        </tr>
                    ) : (
                        entries.map((entry, index) => (
                            <tr key={entry.id} className="border-t border-gray-800 hover:bg-gray-800/50 transition-colors">
                                <td className="py-3 px-4 text-gray-500">{index + 1}</td>
                                <td className="py-3 px-4">
                                    <Badge type="method" value={entry.method} />
                                </td>
                                <td className="py-3 px-4 text-white">{entry.host}</td>
                                <td className="py-3 px-4 text-gray-300 max-w-xs truncate">{entry.path}</td>
                                <td className="py-3 px-4">
                                    <Badge type="status" value={entry.status_code || 0} />
                                </td>
                                <td className="py-3 px-4 text-gray-400">{entry.length || '-'}</td>
                                <td className="py-3 px-4">
                                    <button className="text-burp-orange hover:text-orange-400 transition-colors">
                                        <ExternalLink size={18} />
                                    </button>
                                </td>
                            </tr>
                        ))
                    )}
                </tbody>
            </table>
        </div>
    );
};
