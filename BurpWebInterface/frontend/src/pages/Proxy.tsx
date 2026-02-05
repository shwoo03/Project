import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { useWebSocket } from '../context/WebSocketContext'
import { proxyApi, ProxyEntry } from '../services'
import { ProxyFilters } from '../components/proxy/ProxyFilters'
import { ProxyTable } from '../components/proxy/ProxyTable'

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
            <ProxyFilters filter={filter} setFilter={setFilter} />

            {/* Table */}
            <ProxyTable entries={filteredEntries} loading={loading} />
        </div>
    )
}
