import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Proxy from './pages/Proxy'
import Repeater from './pages/Repeater'
import Intruder from './pages/Intruder'
import Scanner from './pages/Scanner'

function App() {
    return (
        <BrowserRouter>
            <div className="flex h-screen">
                <Sidebar />
                <main className="flex-1 overflow-auto p-6">
                    <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/proxy" element={<Proxy />} />
                        <Route path="/repeater" element={<Repeater />} />
                        <Route path="/intruder" element={<Intruder />} />
                        <Route path="/scanner" element={<Scanner />} />
                    </Routes>
                </main>
            </div>
        </BrowserRouter>
    )
}

export default App
