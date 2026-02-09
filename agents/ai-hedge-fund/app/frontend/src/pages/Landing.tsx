import { ArrowRight, Bot, Brain, Shield, TrendingUp } from "lucide-react";
import { Link } from "react-router-dom";

const features = [
  {
    icon: Bot,
    title: "20+ AI Agents",
    description:
      "Modeled after legendary investors — Buffett, Munger, Burry, Damodaran — each with a distinct thesis and style.",
  },
  {
    icon: Brain,
    title: "Devil's Advocate Synthesis",
    description:
      "A contrarian agent challenges the majority view before every trade, pressure-testing conviction.",
  },
  {
    icon: Shield,
    title: "Autonomous Risk Management",
    description:
      "Position sizing, exposure limits, and drawdown controls enforced automatically before execution.",
  },
  {
    icon: TrendingUp,
    title: "Real-Time Signal Pipeline",
    description:
      "Analysts run in parallel, streaming signals through SSE so you see the debate unfold live.",
  },
];

export default function Landing() {
  return (
    <div className="flex flex-col items-center">
      {/* Hero */}
      <section className="max-w-3xl mx-auto px-6 pt-24 pb-16 text-center">
        <p className="text-sm font-medium text-blue-400 tracking-wide uppercase mb-4">
          Multi-Agent AI Hedge Fund
        </p>
        <h1 className="text-5xl sm:text-6xl font-bold leading-tight tracking-tight mb-6">
          Let the best minds in investing
          <br />
          <span className="text-blue-400">argue for your portfolio.</span>
        </h1>
        <p className="text-lg text-gray-400 max-w-xl mx-auto mb-10">
          SynQubi orchestrates 20+ AI analyst agents — each modeled after a
          legendary investor — to research, debate, and converge on trades in
          real time.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link
            to="/app"
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-semibold transition-colors"
          >
            Launch App <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-2 px-6 py-3 border border-gray-700 hover:border-gray-500 rounded-lg text-sm font-semibold text-gray-300 transition-colors"
          >
            View Product
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-5xl mx-auto px-6 py-20 border-t border-gray-800">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-10">
          {features.map((f) => (
            <div key={f.title} className="flex gap-4">
              <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center">
                <f.icon className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <h3 className="font-semibold mb-1">{f.title}</h3>
                <p className="text-sm text-gray-400 leading-relaxed">
                  {f.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline diagram */}
      <section className="max-w-3xl mx-auto px-6 py-16 border-t border-gray-800 text-center">
        <h2 className="text-2xl font-bold mb-3">How It Works</h2>
        <p className="text-gray-400 text-sm mb-10">
          Every backtest follows the same autonomous pipeline.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3 text-sm font-mono">
          {[
            "Market Data",
            "Analyst Agents",
            "Devil's Advocate",
            "Risk Manager",
            "Portfolio Manager",
          ].map((step, i, arr) => (
            <span key={step} className="flex items-center gap-3">
              <span className="px-3 py-2 rounded bg-gray-800 border border-gray-700 text-gray-300">
                {step}
              </span>
              {i < arr.length - 1 && (
                <ArrowRight className="w-4 h-4 text-gray-600" />
              )}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
