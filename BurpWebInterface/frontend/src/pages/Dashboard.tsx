import { useEffect, useState } from 'react'
import { Radio, RefreshCw, Zap, Target, AlertTriangle } from 'lucide-react'
import { proxyApi, scannerApi, systemApi } from '../services'

interface Stats {
    proxyRequests: number
    repeaterTabs: number
    activeAttacks: number
    vulnerabilities: { high: number; medium: number; low: number }
}

export default function Dashboard() {
    const [stats, setStats] = useState<Stats>({
        proxyRequests: 0,
        repeaterTabs: 0,
        activeAttacks: 0,
        vulnerabilities: { high: 0, medium: 0, low: 0 }
    })
    const [connected, setConnected] = useState(false)

    useEffect(() => {
        const loadDashboardData = async () => {
            try {
                // Check MCP connection
                const health = await systemApi.checkHealth().catch(() => null)
                setConnected(health?.mcp_connected || false)

                // Fetch data in parallel
                const [proxyStats, scannerStats] = await Promise.all([
                    proxyApi.getStats().catch(() => ({})),
                    scannerApi.getStats().catch(() => ({}))
                ])

                setStats({
                    proxyRequests: proxyStats.total_requests || 0,
                    repeaterTabs: 0, // Placeholder
                    activeAttacks: 0, // Placeholder
                    vulnerabilities: scannerStats.by_severity || { high: 0, medium: 0, low: 0 }
                })
            } catch (e) {
                console.error('Failed to load dashboard data:', e)
            }
        }

        loadDashboardData()
    }, [])

    const statCards = [
        { icon: Radio, label: 'Proxy Requests', value: stats.proxyRequests, color: 'bg-blue-500' },
        { icon: RefreshCw, label: 'Repeater Tabs', value: stats.repeaterTabs, color: 'bg-green-500' },
        { icon: Zap, label: 'Active Attacks', value: stats.activeAttacks, color: 'bg-yellow-500' },
        { icon: Target, label: 'Total Vulns', value: stats.vulnerabilities.high + stats.vulnerabilities.medium + stats.vulnerabilities.low, color: 'bg-red-500' },
    ]

    return (
        <div className="animate-fadeIn">
            {/* Header */}
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h1 className="text-3xl font-bold text-white">Dashboard</h1>
                    <p className="text-gray-400 mt-1">Burp Suite Web Interface Overview</p>
                </div>
                <div className={`flex items-center gap-2 px-4 py-2 rounded-full ${connected ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                    <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`}></div>
                    <span className="text-sm">{connected ? 'MCP Connected' : 'MCP Disconnected'}</span>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                {statCards.map(({ icon: Icon, label, value, color }) => (
                    <div key={label} className="glass rounded-xl p-6 hover:glow-orange transition-all duration-300">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-gray-400 text-sm">{label}</p>
                                <p className="text-3xl font-bold text-white mt-2">{value}</p>
                            </div>
                            <div className={`p-3 rounded-lg ${color}`}>
                                <Icon size={24} className="text-white" />
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Vulnerability Summary */}
            <div className="glass rounded-xl p-6 mb-8">
                <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                    <AlertTriangle className="text-burp-orange" />
                    Vulnerability Summary
                </h2>
                <div className="flex gap-4">
                    <div className="flex-1 bg-red-500/20 rounded-lg p-4 text-center">
                        <p className="text-red-400 text-sm">High</p>
                        <p className="text-2xl font-bold text-red-500">{stats.vulnerabilities.high}</p>
                    </div>
                    <div className="flex-1 bg-yellow-500/20 rounded-lg p-4 text-center">
                        <p className="text-yellow-400 text-sm">Medium</p>
                        <p className="text-2xl font-bold text-yellow-500">{stats.vulnerabilities.medium}</p>
                    </div>
                    <div className="flex-1 bg-blue-500/20 rounded-lg p-4 text-center">
                        <p className="text-blue-400 text-sm">Low</p>
                        <p className="text-2xl font-bold text-blue-500">{stats.vulnerabilities.low}</p>
                    </div>
                </div>
            </div>

            {/* Quick Actions */}
            <div className="glass rounded-xl p-6">
                <h2 className="text-xl font-semibold text-white mb-4">Quick Actions</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <button className="bg-burp-orange hover:bg-orange-600 text-white py-3 px-4 rounded-lg transition-colors">
                        New Repeater Tab
                    </button>
                    <button className="bg-gray-700 hover:bg-gray-600 text-white py-3 px-4 rounded-lg transition-colors">
                        Start Active Scan
                    </button>
                    <button className="bg-gray-700 hover:bg-gray-600 text-white py-3 px-4 rounded-lg transition-colors">
                        Generate Payload
                    </button>
                    <button className="bg-gray-700 hover:bg-gray-600 text-white py-3 px-4 rounded-lg transition-colors">
                        Export Report
                    </button>
                </div>
            </div>
        </div>
    )
}
