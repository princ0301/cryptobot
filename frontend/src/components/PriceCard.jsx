import { TrendingDown, TrendingUp } from 'lucide-react'

const COIN_CONFIG = {
  BTC: { color: 'from-orange-500/10 border-orange-500/20', dot: 'bg-orange-400' },
  ETH: { color: 'from-blue-500/10 border-blue-500/20', dot: 'bg-blue-400' },
  BNB: { color: 'from-yellow-500/10 border-yellow-500/20', dot: 'bg-yellow-400' },
}

export default function PriceCard({ coin, data }) {
  const symbol = coin.replace('INR', '')
  const config = COIN_CONFIG[symbol] || {
    color: 'from-slate-500/10 border-slate-500/20',
    dot: 'bg-slate-400',
  }

  if (!data) {
    return (
      <div className={`bg-gradient-to-br ${config.color} to-transparent rounded-xl p-4 border animate-pulse`}>
        <div className="mb-3 h-4 w-16 rounded bg-slate-700/50" />
        <div className="mb-2 h-7 w-32 rounded bg-slate-700/50" />
        <div className="h-3 w-24 rounded bg-slate-700/50" />
      </div>
    )
  }

  const isUp = data.change_24h >= 0

  return (
    <div className={`bg-gradient-to-br ${config.color} to-transparent rounded-xl p-4 border`}>
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${config.dot}`} />
          <span className="text-xs font-bold tracking-widest text-slate-300">{symbol}</span>
          <span className="text-xs text-slate-600">/ INR</span>
        </div>
        <span
          className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${
            isUp ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'
          }`}
        >
          {isUp ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
          {isUp ? '+' : ''}
          {data.change_24h?.toFixed(2)}%
        </span>
      </div>

      <div className="num-transition tabular-nums text-2xl font-bold text-white">
        INR {Number(data.price)?.toLocaleString('en-IN')}
      </div>

      <div className="mt-2 flex gap-3">
        <span className="text-xs text-slate-600">
          H <span className="text-slate-400">INR {Number(data.high_24h)?.toLocaleString('en-IN')}</span>
        </span>
        <span className="text-xs text-slate-600">
          L <span className="text-slate-400">INR {Number(data.low_24h)?.toLocaleString('en-IN')}</span>
        </span>
      </div>
    </div>
  )
}
