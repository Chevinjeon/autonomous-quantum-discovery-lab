import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Toaster } from "./components/ui/sonner";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `text-sm font-medium transition-colors ${
    isActive ? "text-white" : "text-gray-400 hover:text-gray-200"
  }`;

function MarketingLayout() {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 bg-gray-950/70 backdrop-blur">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold text-lg">
            <span className="w-2 h-2 rounded-full bg-blue-400" />
            SynQubi
          </div>
          <nav className="flex items-center gap-6">
            <NavLink to="/" className={navLinkClass} end>
              Home
            </NavLink>
            <NavLink to="/dashboard" className={navLinkClass}>
              Product
            </NavLink>
            <NavLink
              to="/app"
              className="px-4 py-2 bg-blue-600 rounded text-sm font-semibold hover:bg-blue-500"
            >
              Launch App
            </NavLink>
          </nav>
        </div>
      </header>
      <main>
        <Routes>
          <Route index element={<Landing />} />
          <Route path="dashboard" element={<Dashboard />} />
        </Routes>
      </main>
      <footer className="border-t border-gray-800">
        <div className="max-w-6xl mx-auto px-6 py-6 text-xs text-gray-500 flex justify-between">
          <span>&copy; 2026 SynQubi. All rights reserved.</span>
          <span>Quantum-ready risk &amp; optimization stack.</span>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/app" element={<><Layout>{null}</Layout><Toaster /></>} />
        <Route path="/*" element={<MarketingLayout />} />
      </Routes>
    </BrowserRouter>
  );
}
