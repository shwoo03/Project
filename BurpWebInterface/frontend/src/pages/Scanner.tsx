import { useState } from 'react'
import { Target, Play, AlertTriangle, AlertCircle, Info } from 'lucide-react'
import { scannerApi, ScanIssue } from '../services'

export default function Scanner() {
    const [targetUrl, setTargetUrl] = useState('')
    const [scanning, setScanning] = useState(false)
    const [issues, setIssues] = useState<ScanIssue[]>([])

    const startScan = async () => {
        if (!targetUrl) return
        setScanning(true)

        try {
            await scannerApi.startScan({ url: targetUrl, scan_type: 'active' })

            // Poll for issues
            const data = await scannerApi.getIssues()
            setIssues(data.issues || [])
        } catch (e) {
            console.error('Scan error:', e)
        } finally {
            setScanning(false)
        }
    }

    const getSeverityIcon = (severity: string) => {
        switch (severity) {
            case 'high': return <AlertTriangle className="text-red-500" size={18} />
            case 'medium': return <AlertCircle className="text-yellow-500" size={18} />
            case 'low': return <AlertCircle className="text-blue-500" size={18} />
            default: return <Info className="text-gray-500" size={18} />
        }
    }

    const getSeverityClass = (severity: string) => {
        switch (severity) {
            case 'high': return 'bg-red-500/20 text-red-400 border-red-500/30'
            case 'medium': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
            case 'low': return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
            default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
        }
    }

    return (
        <div className="animate-fadeIn">
            {/* Header */}
            <div className="mb-6">
                <h1 className="text-3xl font-bold text-white">Scanner</h1>
                <p className="text-gray-400 mt-1">Automated vulnerability scanning</p>
            </div>

            {/* Scan Input */}
            <div className="glass rounded-xl p-6 mb-6">
                <div className="flex gap-4">
                    <div className="flex-1 relative">
                        <Target className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
                        <input
                            type="text"
                            placeholder="Enter target URL (e.g., https://example.com)"
                            value={targetUrl}
                            onChange={(e) => setTargetUrl(e.target.value)}
                            className="w-full bg-gray-800 border border-gray-700 rounded-lg py-3 pl-10 pr-4 text-white focus:border-burp-orange focus:outline-none"
                        />
                    </div>
                    <button
                        onClick={startScan}
                        disabled={scanning || !targetUrl}
                        className="flex items-center gap-2 bg-burp-orange hover:bg-orange-600 disabled:bg-gray-600 text-white px-8 py-3 rounded-lg transition-colors"
                    >
                        <Play size={18} className={scanning ? 'animate-pulse' : ''} />
                        {scanning ? 'Scanning...' : 'Start Scan'}
                    </button>
                </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-4 gap-4 mb-6">
                {['high', 'medium', 'low', 'info'].map(severity => {
                    const count = issues.filter(i => i.severity === severity).length
                    return (
                        <div key={severity} className={`glass rounded-xl p-4 border ${getSeverityClass(severity)}`}>
                            <div className="flex items-center justify-between">
                                <span className="capitalize">{severity}</span>
                                <span className="text-2xl font-bold">{count}</span>
                            </div>
                        </div>
                    )
                })}
            </div>

            {/* Issues List */}
            <div className="glass rounded-xl overflow-hidden">
                <div className="bg-gray-800/50 px-4 py-3 border-b border-gray-700">
                    <h3 className="font-medium text-white">Discovered Issues</h3>
                </div>

                {issues.length === 0 ? (
                    <div className="p-8 text-center text-gray-500">
                        {scanning
                            ? 'Scanning in progress...'
                            : 'No issues found yet. Enter a target URL and start scanning.'}
                    </div>
                ) : (
                    <div className="divide-y divide-gray-800">
                        {issues.map(issue => (
                            <div key={issue.id} className="p-4 hover:bg-gray-800/50 transition-colors cursor-pointer">
                                <div className="flex items-start gap-3">
                                    {getSeverityIcon(issue.severity)}
                                    <div className="flex-1">
                                        <h4 className="text-white font-medium">{issue.name}</h4>
                                        <p className="text-gray-400 text-sm mt-1">{issue.url}</p>
                                    </div>
                                    <span className={`text-xs px-2 py-1 rounded ${getSeverityClass(issue.severity)}`}>
                                        {issue.confidence}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}
