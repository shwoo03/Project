import { useEffect, useState } from 'react'
import { Search, Filter, RefreshCw, ExternalLink } from 'lucide-react'
import { useWebSocket } from '../context/WebSocketContext'
import { proxyApi, ProxyEntry } from '../services'

export default function Proxy() {
    const [entries, setEntries] = useState<ProxyEntry[]>([])
    const [loading, setLoading] = useState(true)
    const [filter, setFilter] = useState('')
    const { lastMessage } = useWebSocket()

    const fetchHistory = async () => {
        setLoading(true)
        try {
            const data = await proxyApi.getHistory(100)
            setEntries(data.entries || [])
        } catch (e) {
            console.error('Failed to fetch proxy history:', e)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchHistory()
    }, [])

    // Listen for WebSocket messages
    useEffect(() => {
        if (lastMessage && lastMessage.type === 'PROXY_NEW_REQUEST') {
            const newEntry = lastMessage.data as ProxyEntry;
            setEntries(prev => [newEntry, ...prev]);
        }
    }, [lastMessage]);

    const filteredEntries = entries.filter(e =>
        e.host?.toLowerCase().includes(filter.toLowerCase()) ||
        e.path?.toLowerCase().includes(filter.toLowerCase())
    )

    const getMethodColor = (method: string) => {
        const colors: Record<string, string> = {
            GET: 'bg-green-500',
            POST: 'bg-blue-500',
            PUT: 'bg-yellow-500',
            DELETE: 'bg-red-500',
            PATCH: 'bg-purple-500'
        }
        return colors[method] || 'bg-gray-500'
    }

    const getStatusColor = (status: number) => {
        if (status >= 200 && status < 300) return 'text-green-400'
        if (status >= 300 && status < 400) return 'text-blue-400'
        if (status >= 400 && status < 500) return 'text-yellow-400'
        if (status >= 500) return 'text-red-400'
        return 'text-gray-400'
    }

    return (
        <div className="animate-fadeIn">
            {/* Header */}
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-3xl font-bold text-white">Proxy History</h1>
                    <p className="text-gray-400 mt-1">Intercepted HTTP traffic</p>
                </div>
                <button
                    onClick={fetchHistory}
                    className="flex items-center gap-2 bg-burp-orange hover:bg-orange-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                    <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
                    Refresh
                </button>
            </div>

            {/* Search & Filter */}
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

            {/* Table */}
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
                        ) : filteredEntries.length === 0 ? (
                            <tr>
                                <td colSpan={7} className="text-center py-8 text-gray-400">
                                    No requests captured yet. Configure your browser to use Burp Proxy.
                                </td>
                            </tr>
                        ) : (
                            filteredEntries.map((entry, index) => (
                                <tr key={entry.id} className="border-t border-gray-800 hover:bg-gray-800/50 transition-colors">
                                    <td className="py-3 px-4 text-gray-500">{index + 1}</td>
                                    <td className="py-3 px-4">
                                        <span className={`${getMethodColor(entry.method)} px-2 py-1 rounded text-xs font-medium text-white`}>
                                            {entry.method}
                                        </span>
                                    </td>
                                    <td className="py-3 px-4 text-white">{entry.host}</td>
                                    <td className="py-3 px-4 text-gray-300 max-w-xs truncate">{entry.path}</td>
                                    <td className={`py-3 px-4 font-medium ${getStatusColor(entry.status_code)}`}>
                                        {entry.status_code || '-'}
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
        </div>
    )
}
