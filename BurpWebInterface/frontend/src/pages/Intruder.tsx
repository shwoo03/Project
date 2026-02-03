import { useState } from 'react'
import { Play, Pause, Square, Crosshair } from 'lucide-react'

export default function Intruder() {
    const [request, setRequest] = useState(`POST /login HTTP/1.1
Host: example.com
Content-Type: application/x-www-form-urlencoded

username=§admin§&password=§password123§`)
    const [payloads, setPayloads] = useState('admin\nuser\ntest')
    const [attackType, setAttackType] = useState('sniper')
    const [isRunning, setIsRunning] = useState(false)

    const startAttack = () => {
        setIsRunning(true)
        // API call to start attack
    }

    return (
        <div className="animate-fadeIn">
            {/* Header */}
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-3xl font-bold text-white">Intruder</h1>
                    <p className="text-gray-400 mt-1">Automated customized attacks</p>
                </div>
                <div className="flex gap-2">
                    {!isRunning ? (
                        <button
                            onClick={startAttack}
                            className="flex items-center gap-2 bg-burp-orange hover:bg-orange-600 text-white px-6 py-2 rounded-lg transition-colors"
                        >
                            <Play size={18} />
                            Start Attack
                        </button>
                    ) : (
                        <>
                            <button className="flex items-center gap-2 bg-yellow-600 hover:bg-yellow-500 text-white px-4 py-2 rounded-lg transition-colors">
                                <Pause size={18} />
                                Pause
                            </button>
                            <button
                                onClick={() => setIsRunning(false)}
                                className="flex items-center gap-2 bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-lg transition-colors"
                            >
                                <Square size={18} />
                                Stop
                            </button>
                        </>
                    )}
                </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
                {/* Left: Request with Positions */}
                <div className="glass rounded-xl overflow-hidden">
                    <div className="bg-gray-800/50 px-4 py-3 border-b border-gray-700 flex justify-between items-center">
                        <h3 className="font-medium text-white flex items-center gap-2">
                            <Crosshair size={18} className="text-burp-orange" />
                            Positions
                        </h3>
                        <div className="flex gap-2">
                            <button className="text-xs bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded text-gray-300">
                                Add §
                            </button>
                            <button className="text-xs bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded text-gray-300">
                                Clear §
                            </button>
                        </div>
                    </div>
                    <textarea
                        value={request}
                        onChange={(e) => setRequest(e.target.value)}
                        className="w-full h-80 bg-transparent p-4 text-green-400 font-mono text-sm resize-none focus:outline-none"
                        spellCheck={false}
                    />
                </div>

                {/* Right: Attack Config */}
                <div className="space-y-6">
                    {/* Attack Type */}
                    <div className="glass rounded-xl p-4">
                        <h3 className="font-medium text-white mb-3">Attack Type</h3>
                        <div className="grid grid-cols-2 gap-2">
                            {['sniper', 'battering_ram', 'pitchfork', 'cluster_bomb'].map(type => (
                                <button
                                    key={type}
                                    onClick={() => setAttackType(type)}
                                    className={`py-2 px-4 rounded-lg text-sm transition-colors
                    ${attackType === type
                                            ? 'bg-burp-orange text-white'
                                            : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
                                >
                                    {type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Payloads */}
                    <div className="glass rounded-xl overflow-hidden">
                        <div className="bg-gray-800/50 px-4 py-3 border-b border-gray-700">
                            <h3 className="font-medium text-white">Payloads</h3>
                        </div>
                        <textarea
                            value={payloads}
                            onChange={(e) => setPayloads(e.target.value)}
                            placeholder="Enter payloads (one per line)..."
                            className="w-full h-40 bg-transparent p-4 text-yellow-400 font-mono text-sm resize-none focus:outline-none"
                            spellCheck={false}
                        />
                    </div>
                </div>
            </div>

            {/* Results Table (placeholder) */}
            <div className="glass rounded-xl mt-6 overflow-hidden">
                <div className="bg-gray-800/50 px-4 py-3 border-b border-gray-700">
                    <h3 className="font-medium text-white">Results</h3>
                </div>
                <div className="p-8 text-center text-gray-500">
                    {isRunning
                        ? 'Attack in progress...'
                        : 'Configure positions and payloads, then start the attack.'}
                </div>
            </div>
        </div>
    )
}
