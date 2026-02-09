import { ArrowUpRight, Bot, Cpu, Globe, Layers, Zap } from "lucide-react";

const agents = [
  { name: "Warren Buffett", style: "Deep value, wide moats" },
  { name: "Charlie Munger", style: "Multi-disciplinary mental models" },
  { name: "Michael Burry", style: "Contrarian deep-dive" },
  { name: "Cathie Wood", style: "Disruptive innovation" },
  { name: "Peter Lynch", style: "Growth at a reasonable price" },
  { name: "Ben Graham", style: "Margin of safety" },
  { name: "Aswath Damodaran", style: "DCF valuation" },
  { name: "Stanley Druckenmiller", style: "Macro + conviction" },
  { name: "Phil Fisher", style: "Scuttlebutt growth" },
  { name: "Bill Ackman", style: "Activist catalyst" },
  { name: "Rakesh Jhunjhunwala", style: "Emerging market momentum" },
  { name: "Mohnish Pabrai", style: "Cloned value bets" },
];

const systemAgents = [
  { name: "Technical Analyst", icon: Layers },
  { name: "Fundamentals Analyst", icon: Cpu },
  { name: "Sentiment Analyst", icon: Globe },
  { name: "Devil's Advocate", icon: Zap },
];

export default function Dashboard() {
  return (
    <div className="max-w-5xl mx-auto px-6 py-16">
      <div className="flex items-center justify-between mb-10">
        <div>
          <h1 className="text-3xl font-bold mb-1">Product Overview</h1>
          <p className="text-gray-400 text-sm">
            Multi-agent AI hedge fund — autonomous research, debate, and
            portfolio management.
          </p>
        </div>
        <a
          href="mailto:hello@synqubi.ai"
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-semibold transition-colors"
        >
          Request Access <ArrowUpRight className="w-4 h-4" />
        </a>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-12">
        {[
          { label: "Analyst Agents", value: "12" },
          { label: "System Agents", value: "8" },
          { label: "Signal Pipeline", value: "Real-time" },
          { label: "LLM Providers", value: "5+" },
        ].map((s) => (
          <div
            key={s.label}
            className="bg-gray-900 border border-gray-800 rounded-lg p-4"
          >
            <div className="text-2xl font-bold text-blue-400 mb-1">
              {s.value}
            </div>
            <div className="text-xs text-gray-500">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Investor agents */}
      <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <Bot className="w-5 h-5 text-blue-400" />
        Investor Agents
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 mb-12">
        {agents.map((a) => (
          <div
            key={a.name}
            className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3"
          >
            <div className="font-medium text-sm">{a.name}</div>
            <div className="text-xs text-gray-500 mt-0.5">{a.style}</div>
          </div>
        ))}
      </div>

      {/* System agents */}
      <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <Cpu className="w-5 h-5 text-blue-400" />
        System Agents
      </h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-12">
        {systemAgents.map((a) => (
          <div
            key={a.name}
            className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex items-center gap-3"
          >
            <a.icon className="w-4 h-4 text-gray-400 flex-shrink-0" />
            <span className="text-sm font-medium">{a.name}</span>
          </div>
        ))}
      </div>

      {/* Architecture */}
      <h2 className="text-xl font-semibold mb-4">Architecture</h2>
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 text-sm text-gray-400 font-mono leading-relaxed whitespace-pre">
{`  Market Data APIs
        |
  ┌─────┴─────┐
  │  start()  │   fetch prices, metrics, news
  └─────┬─────┘
        |
  ┌─────┴─────────────────────┐
  │   12 Analyst Agents       │   fan-out (parallel)
  │   + 6 Systematic Agents   │
  └─────┬─────────────────────┘
        |
  ┌─────┴──────────────┐
  │  Devil's Advocate   │   contrarian challenge
  └─────┬──────────────┘
        |
  ┌─────┴──────────────┐
  │   Risk Manager      │   position sizing + limits
  └─────┬──────────────┘
        |
  ┌─────┴──────────────┐
  │  Portfolio Manager  │   final trade decisions
  └────────────────────┘`}
      </div>
    </div>
  );
}
