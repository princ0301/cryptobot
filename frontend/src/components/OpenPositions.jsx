import { Shield, Target } from 'lucide-react'

export default function OpenPositions({ positions, newestPositionId = null }) {
  const list = positions?.positions || []

  if (list.length === 0) {
    return (
      <div className="rounded-xl border border-slate-700/50 bg-slate-800/60 p-4">
        <div className="mb-3 flex items-center gap-2">
          <Target size={15} className="text-slate-400" />
          <span className="text-sm font-semibold text-slate-200">Open Positions</span>
        </div>
        <p className="py-4 text-center text-sm text-slate-500">No open positions</p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-700/50 bg-slate-800/60">
      <div className="flex items-center gap-2 border-b border-slate-700/50 px-4 py-3">
        <Target size={15} className="text-indigo-400" />
        <span className="text-sm font-semibold text-slate-200">Open Positions</span>
        <span className="ml-auto rounded-full bg-indigo-500/20 px-2 py-0.5 text-xs text-indigo-400">
          {list.length} active
        </span>
      </div>
      <div className="divide-y divide-slate-700/30">
        {list.map((position) => {
          const entry = Number(position.entry_price)
          const current = Number(position.current_price) || entry
          const pnl = Number(position.unrealized_pnl || 0)
          const isProfit = pnl >= 0
          const coin = `${position.coin?.replace('INR', '') || ''}/INR`
          const pct = ((current - entry) / entry * 100).toFixed(2)
          const isNewest = newestPositionId === position.id

          return (
            <div key={position.id} className="space-y-2 px-4 py-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-200">{coin}</span>
                  <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-xs text-emerald-400">
                    {position.action}
                  </span>
                  {isNewest && (
                    <span className="rounded bg-indigo-500/15 px-1.5 py-0.5 text-xs text-indigo-300">
                      New
                    </span>
                  )}
                  {position.tp1_hit && (
                    <span className="rounded bg-yellow-500/15 px-1.5 py-0.5 text-xs text-yellow-400">
                      TP1 Hit
                    </span>
                  )}
                </div>
                <span className={`text-sm font-bold ${isProfit ? 'text-emerald-400' : 'text-red-400'}`}>
                  {isProfit ? '+' : ''}INR {Math.abs(pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                </span>
              </div>

              <div className="flex gap-4 font-mono text-xs text-slate-500">
                <span>Entry INR {entry.toLocaleString('en-IN')}</span>
                <span>Now INR {current.toLocaleString('en-IN')}</span>
                <span className={isProfit ? 'text-emerald-500' : 'text-red-500'}>
                  {isProfit ? '+' : ''}
                  {pct}%
                </span>
              </div>

              <div className="flex gap-4 font-mono text-xs">
                <span className="flex items-center gap-1 text-red-400/70">
                  <Shield size={10} /> SL INR {Number(position.stop_loss).toLocaleString('en-IN')}
                </span>
                <span className="text-emerald-400/70">
                  TP1 INR {Number(position.take_profit_1).toLocaleString('en-IN')}
                </span>
                <span className="text-emerald-400/50">
                  TP2 INR {Number(position.take_profit_2).toLocaleString('en-IN')}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
