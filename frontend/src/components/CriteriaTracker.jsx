import { CheckCircle, Lock, Unlock, XCircle } from 'lucide-react'

function CriteriaBar({ item }) {
  const pass = item.pass
  const pct = Math.min(item.progress, 100)

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5">
          {pass ? (
            <CheckCircle size={13} className="text-emerald-400" />
          ) : (
            <XCircle size={13} className="text-slate-500" />
          )}
          <span className={pass ? 'text-slate-300' : 'text-slate-400'}>{item.name}</span>
        </div>
        <span className={`font-mono font-semibold ${pass ? 'text-emerald-400' : 'text-slate-400'}`}>
          {item.current?.toFixed(item.unit === '%' ? 1 : 2)}
          {item.unit}
          <span className="font-normal text-slate-600">
            {' '}
            / {item.required}
            {item.unit}
          </span>
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-700/60">
        <div
          className={`h-full rounded-full transition-all duration-700 ${pass ? 'bg-emerald-500' : 'bg-slate-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export default function CriteriaTracker({ criteria }) {
  if (!criteria) {
    return <div className="h-48 rounded-xl border border-slate-700/50 bg-slate-800/60 p-5 animate-pulse" />
  }

  const allMet = criteria.all_criteria_met
  const tradeDone = criteria.trades_completed || 0
  const tradeReq = criteria.trades_required || 30
  const tradePct = Math.min((tradeDone / tradeReq) * 100, 100)

  return (
    <div
      className={`rounded-xl border p-5 ${
        allMet ? 'border-emerald-500/30 bg-emerald-950/30' : 'border-slate-700/50 bg-slate-800/60'
      }`}
    >
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {allMet ? (
            <Unlock size={16} className="text-emerald-400" />
          ) : (
            <Lock size={16} className="text-slate-400" />
          )}
          <span className="text-sm font-semibold text-slate-200">
            {allMet ? 'Live Mode Unlocked' : 'Live Mode Criteria'}
          </span>
        </div>
        <span className="font-mono text-xs text-slate-500">
          {tradeDone}/{tradeReq} trades
        </span>
      </div>

      <div className="mb-4 space-y-1.5">
        <div className="flex justify-between text-xs text-slate-400">
          <span>Trade count</span>
          <span className="font-mono">
            {tradeDone} / {tradeReq} minimum
          </span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-slate-700/60">
          <div
            className="h-full rounded-full bg-indigo-500 transition-all duration-700"
            style={{ width: `${tradePct}%` }}
          />
        </div>
      </div>

      <div className="space-y-3">
        {criteria.criteria?.map((item) => (
          <CriteriaBar key={item.name} item={item} />
        ))}
      </div>

      {allMet && (
        <div className="mt-4 rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-center text-xs text-emerald-300">
          Agent has proven itself. Go to the Live Mode tab to activate real trading.
        </div>
      )}
    </div>
  )
}
