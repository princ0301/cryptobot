import { Clock3, Sparkles, Wallet } from 'lucide-react'

function formatCoin(coin) {
  return `${coin?.replace('INR', '') || ''}/INR`
}

export default function LatestBuyCard({ position }) {
  if (!position) {
    return (
      <div className="rounded-xl border border-slate-700/50 bg-slate-800/60 p-4">
        <div className="mb-2 flex items-center gap-2">
          <Sparkles size={15} className="text-slate-400" />
          <span className="text-sm font-semibold text-slate-200">Latest Buy</span>
        </div>
        <p className="py-4 text-center text-sm text-slate-500">No buy yet. The next agent entry will show here.</p>
      </div>
    )
  }

  const openedAt = position.opened_at
    ? new Date(position.opened_at).toLocaleString('en-IN', {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '--'

  return (
    <div className="rounded-xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 via-slate-900/40 to-slate-800/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles size={15} className="text-emerald-400" />
          <span className="text-sm font-semibold text-slate-100">Latest Buy</span>
        </div>
        <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-semibold text-emerald-400">
          {position.action}
        </span>
      </div>

      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <div className="text-lg font-bold text-white">{formatCoin(position.coin)}</div>
          <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-400">
            <Clock3 size={12} />
            <span>{openedAt}</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-500">Entry</div>
          <div className="font-mono text-sm font-semibold text-slate-200">
            INR {Number(position.entry_price).toLocaleString('en-IN')}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 rounded-lg border border-slate-700/40 bg-slate-900/40 p-3">
        <div>
          <div className="text-xs text-slate-500">Quantity</div>
          <div className="mt-1 font-mono text-sm text-slate-200">
            {Number(position.quantity).toLocaleString('en-IN', { maximumFractionDigits: 6 })}
          </div>
        </div>
        <div>
          <div className="flex items-center gap-1 text-xs text-slate-500">
            <Wallet size={12} />
            <span>Position Size</span>
          </div>
          <div className="mt-1 font-mono text-sm text-slate-200">
            INR {Number(position.position_inr).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
          </div>
        </div>
      </div>
    </div>
  )
}
