import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

const STATUS_STYLE = {
  OPEN:          'bg-blue-500/15 text-blue-400',
  CLOSED_TP1:    'bg-emerald-500/15 text-emerald-400',
  CLOSED_TP2:    'bg-emerald-500/15 text-emerald-400',
  CLOSED_SL:     'bg-red-500/15 text-red-400',
  CLOSED_MANUAL: 'bg-slate-500/15 text-slate-400',
}

const STATUS_LABEL = {
  OPEN:          'Open',
  CLOSED_TP1:    'TP1 ✓',
  CLOSED_TP2:    'TP2 ✓',
  CLOSED_SL:     'SL Hit',
  CLOSED_MANUAL: 'Manual',
}

function TradeRow({ trade }) {
  const [expanded, setExpanded] = useState(false)
  const pnl      = trade.pnl_after_tax || 0
  const isProfit = pnl > 0
  const isOpen   = trade.status === 'OPEN'
  const coin     = trade.coin?.replace('INR', '') + '/INR'
  const time     = new Date(trade.opened_at).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
  })

  return (
    <>
      <tr
        className="border-b border-slate-700/30 hover:bg-slate-700/20 cursor-pointer transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-4 py-3 text-xs text-slate-400 font-mono">{time}</td>
        <td className="px-4 py-3">
          <span className="text-xs font-semibold text-slate-300">{coin}</span>
        </td>
        <td className="px-4 py-3">
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
            trade.action === 'BUY' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'
          }`}>{trade.action}</span>
        </td>
        <td className="px-4 py-3 text-xs text-slate-300 font-mono">
          ₹{Number(trade.entry_price).toLocaleString('en-IN')}
        </td>
        <td className="px-4 py-3 text-xs font-mono">
          {isOpen ? (
            <span className="text-slate-500">—</span>
          ) : (
            <span className={isProfit ? 'text-emerald-400' : 'text-red-400'}>
              {isProfit ? '+' : ''}₹{Math.abs(pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
            </span>
          )}
        </td>
        <td className="px-4 py-3">
          <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_STYLE[trade.status] || STATUS_STYLE.OPEN}`}>
            {STATUS_LABEL[trade.status] || trade.status}
          </span>
        </td>
        <td className="px-4 py-3 text-xs text-slate-500 font-mono">{trade.confidence}%</td>
        <td className="px-4 py-3 text-slate-500">
          {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </td>
      </tr>
      {expanded && (
        <tr className="bg-slate-800/30">
          <td colSpan={8} className="px-4 py-3">
            <div className="space-y-2">
              {trade.reasoning && (
                <div>
                  <span className="text-xs text-slate-500 uppercase tracking-wider">AI Reasoning</span>
                  <p className="text-xs text-slate-300 mt-1 leading-relaxed">{trade.reasoning}</p>
                </div>
              )}
              <div className="flex flex-wrap gap-4 text-xs text-slate-400 font-mono">
                <span>SL: ₹{Number(trade.stop_loss).toLocaleString('en-IN')}</span>
                <span>TP1: ₹{Number(trade.take_profit_1).toLocaleString('en-IN')}</span>
                <span>TP2: ₹{Number(trade.take_profit_2).toLocaleString('en-IN')}</span>
                <span>Qty: {trade.quantity}</span>
                <span>R:R: {trade.risk_reward}</span>
                {trade.tax_provision > 0 && <span>Tax: ₹{Number(trade.tax_provision).toFixed(0)}</span>}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export default function TradeLog({ trades }) {
  const [filter, setFilter] = useState('all')

  const tradeList = trades?.trades || []
  const filtered  = filter === 'all'
    ? tradeList
    : tradeList.filter(t => {
        if (filter === 'win')  return t.pnl_after_tax > 0
        if (filter === 'loss') return t.pnl_after_tax <= 0 && t.status !== 'OPEN'
        if (filter === 'open') return t.status === 'OPEN'
        return true
      })

  return (
    <div className="bg-slate-800/60 rounded-xl border border-slate-700/50 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/50">
        <span className="text-sm font-semibold text-slate-200">
          Trade Log <span className="text-slate-500 font-normal text-xs ml-1">({tradeList.length} trades)</span>
        </span>
        <div className="flex gap-1">
          {['all', 'open', 'win', 'loss'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`text-xs px-2.5 py-1 rounded-lg capitalize transition-all ${
                filter === f
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-400 hover:text-slate-300 hover:bg-slate-700/50'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-12 text-slate-500 text-sm">
          No trades yet. Agent is analyzing the market every hour.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-slate-700/30">
                <th className="px-4 py-2 text-left">Time</th>
                <th className="px-4 py-2 text-left">Pair</th>
                <th className="px-4 py-2 text-left">Action</th>
                <th className="px-4 py-2 text-left">Entry</th>
                <th className="px-4 py-2 text-left">P&L</th>
                <th className="px-4 py-2 text-left">Status</th>
                <th className="px-4 py-2 text-left">Conf</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(trade => <TradeRow key={trade.id} trade={trade} />)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}