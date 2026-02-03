import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Radio, RefreshCw, Zap, Target, Settings } from 'lucide-react'
import { useWebSocket } from '../context/WebSocketContext'

const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/proxy', icon: Radio, label: 'Proxy' },
    { to: '/repeater', icon: RefreshCw, label: 'Repeater' },
    { to: '/intruder', icon: Zap, label: 'Intruder' },
    { to: '/scanner', icon: Target, label: 'Scanner' },
]

export default function Sidebar() {
    const { isConnected } = useWebSocket()

    return (
        <aside className="w-64 h-screen bg-burp-darker border-r border-gray-800 flex flex-col">
            {/* Logo */}
            <div className="p-6 border-b border-gray-800">
                <h1 className="text-xl font-bold flex items-center gap-2">
                    <span className="text-burp-orange">🔒</span>
                    <span>Burp Web</span>
                </h1>
                <p className="text-xs text-gray-500 mt-1">Security Testing Interface</p>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-4">
                <ul className="space-y-2">
                    {navItems.map(({ to, icon: Icon, label }) => (
                        <li key={to}>
                            <NavLink
                                to={to}
                                className={({ isActive }) =>
                                    `flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200
                  ${isActive
                                        ? 'bg-burp-orange text-white glow-orange'
                                        : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                                    }`
                                }
                            >
                                <Icon size={20} />
                                <span className={({ isActive }: any) => isActive ? 'font-semibold' : ''}>{label}</span>
                            </NavLink>
                        </li>
                    ))}
                </ul>
            </nav>

            {/* Settings */}
            <div className="p-4 border-t border-gray-800">
                <NavLink
                    to="/settings"
                    className="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-400 hover:bg-gray-800 hover:text-white transition-all"
                >
                    <Settings size={20} />
                    <span>Settings</span>
                </NavLink>

                {/* Connection Status */}
                <div className="mt-4 px-4 py-3 glass rounded-lg transition-all duration-300">
                    <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse' : 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]'} transition-colors duration-300`}></div>
                        <span className="text-xs text-gray-400">{isConnected ? 'System Online' : 'Disconnected'}</span>
                    </div>
                </div>
            </div>
        </aside>
    )
}
