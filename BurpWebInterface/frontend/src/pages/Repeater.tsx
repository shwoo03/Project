import { useState } from 'react'
import { Plus, Send, Trash2 } from 'lucide-react'
import { repeaterApi } from '../services'

interface RepeaterTab {
    id: string
    name: string
    request: string
    response: string
}

export default function Repeater() {
    const [tabs, setTabs] = useState<RepeaterTab[]>([
        {
            id: '1',
            name: 'Request 1',
            request: `GET /api/users HTTP/1.1
Host: example.com
User-Agent: Mozilla/5.0
Accept: application/json

`,
            response: ''
        }
    ])
    const [activeTab, setActiveTab] = useState('1')
    const [loading, setLoading] = useState(false)

    const currentTab = tabs.find(t => t.id === activeTab)

    const addTab = () => {
        const newId = String(tabs.length + 1)
        setTabs([...tabs, {
            id: newId,
            name: `Request ${newId}`,
            request: `GET / HTTP/1.1
Host: example.com

`,
            response: ''
        }])
        setActiveTab(newId)
    }

    const updateRequest = (request: string) => {
        setTabs(tabs.map(t =>
            t.id === activeTab ? { ...t, request } : t
        ))
    }

    const sendRequest = async () => {
        if (!currentTab) return
        setLoading(true)

        try {
            // Parse host from request
            const hostMatch = currentTab.request.match(/Host:\s*([^\r\n]+)/i)
            const host = hostMatch ? hostMatch[1].trim() : 'example.com'

            const data = await repeaterApi.sendRequest({
                request: currentTab.request,
                host,
                port: 443,
                use_https: true
            })

            setTabs(tabs.map(t =>
                t.id === activeTab ? { ...t, response: data.response || 'No response received' } : t
            ))
        } catch (e: any) {
            setTabs(tabs.map(t =>
                t.id === activeTab ? { ...t, response: `Error: ${e.message || e}` } : t
            ))
        } finally {
            setLoading(false)
        }
    }

    const deleteTab = (id: string) => {
        if (tabs.length <= 1) return
        const newTabs = tabs.filter(t => t.id !== id)
        setTabs(newTabs)
        if (activeTab === id) {
            setActiveTab(newTabs[0].id)
        }
    }

    return (
        <div className="animate-fadeIn h-full flex flex-col">
            {/* Header */}
            <div className="flex justify-between items-center mb-4">
                <div>
                    <h1 className="text-3xl font-bold text-white">Repeater</h1>
                    <p className="text-gray-400 mt-1">Edit and resend HTTP requests</p>
                </div>
                <button
                    onClick={sendRequest}
                    disabled={loading}
                    className="flex items-center gap-2 bg-burp-orange hover:bg-orange-600 disabled:bg-gray-600 text-white px-6 py-2 rounded-lg transition-colors"
                >
                    <Send size={18} className={loading ? 'animate-pulse' : ''} />
                    {loading ? 'Sending...' : 'Send'}
                </button>
            </div>

            {/* Tabs */}
            <div className="flex items-center gap-1 mb-4">
                {tabs.map(tab => (
                    <div
                        key={tab.id}
                        className={`group flex items-center gap-2 px-4 py-2 rounded-t-lg cursor-pointer transition-colors
              ${activeTab === tab.id ? 'bg-gray-800 text-white' : 'bg-gray-900 text-gray-400 hover:bg-gray-800'}`}
                        onClick={() => setActiveTab(tab.id)}
                    >
                        <span>{tab.name}</span>
                        {tabs.length > 1 && (
                            <Trash2
                                size={14}
                                className="opacity-0 group-hover:opacity-100 hover:text-red-400 transition-all"
                                onClick={(e) => { e.stopPropagation(); deleteTab(tab.id); }}
                            />
                        )}
                    </div>
                ))}
                <button
                    onClick={addTab}
                    className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
                >
                    <Plus size={20} />
                </button>
            </div>

            {/* Split View */}
            <div className="flex-1 grid grid-cols-2 gap-4 min-h-0">
                {/* Request */}
                <div className="flex flex-col glass rounded-xl overflow-hidden">
                    <div className="bg-gray-800/50 px-4 py-2 border-b border-gray-700">
                        <h3 className="text-sm font-medium text-gray-300">Request</h3>
                    </div>
                    <textarea
                        value={currentTab?.request || ''}
                        onChange={(e) => updateRequest(e.target.value)}
                        className="flex-1 bg-transparent p-4 text-green-400 font-mono text-sm resize-none focus:outline-none"
                        spellCheck={false}
                    />
                </div>

                {/* Response */}
                <div className="flex flex-col glass rounded-xl overflow-hidden">
                    <div className="bg-gray-800/50 px-4 py-2 border-b border-gray-700">
                        <h3 className="text-sm font-medium text-gray-300">Response</h3>
                    </div>
                    <pre className="flex-1 bg-transparent p-4 text-blue-400 font-mono text-sm overflow-auto whitespace-pre-wrap">
                        {currentTab?.response || 'Response will appear here after sending the request.'}
                    </pre>
                </div>
            </div>
        </div>
    )
}
