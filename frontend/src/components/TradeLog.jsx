import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

const STATUS_STYLE = {
  OPEN: 'bg-blue-500/15 text-blue-400',
  CLOSED_TP1: 'bg-emerald-500/15 text-emerald-400',
  CLOSED_TP2: 'bg-emerald-500/15 text-emerald-400',
  CLOSED_SL: 'bg-red-500/15 text-red-400',
  CLOSED_MANUAL: 'bg-slate-500/15 text-slate-400',
}

const STATUS_LABEL = {
  OPEN: 'Open',
  CLOSED_TP1: 'TP1 Hit',
  CLOSED_TP2: 'TP2 Hit',
  CLOSED_SL: 'SL Hit',
  CLOSED_MANUAL: 'Manual',
}

function formatInr(value, digits = 0) {
  return `INR ${Number(value || 0).toLocaleString('en-IN', { maximumFractionDigits: digits })}`
}

function TradeRow({ trade, priceData }) {
  const [expanded, setExpanded] = useState(false)
  const isOpen = trade.status === 'OPEN'
  const coin = `${trade.coin?.replace('INR', '') || ''}/INR`
  const time = new Date(trade.opened_at).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })

  const entryPrice = Number(trade.entry_price || 0)
  const quantity = Number(trade.quantity || 0)
  const currentPrice = Number(priceData?.[trade.coin]?.price || 0)
  const realizedPnl = Number(trade.pnl_after_tax || 0)
  const unrealizedPnl = currentPrice > 0 ? (currentPrice - entryPrice) * quantity : 0
  const pnl = isOpen ? unrealizedPnl : realizedPnl
  const isProfit = pnl >= 0
  const pnlPct = isOpen && currentPrice > 0 && entryPrice > 0
    ? ((currentPrice - entryPrice) / entryPrice) * 100
    : null

  return (
    <>
      <tr
        className="cursor-pointer border-b border-slate-700/30 transition-colors hover:bg-slate-700/20"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-4 py-3 font-mono text-xs text-slate-400">{time}</td>
        <td className="px-4 py-3">
          <span className="text-xs font-semibold text-slate-300">{coin}</span>
        </td>
        <td className="px-4 py-3">
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-bold ${
              trade.action === 'BUY'
                ? 'bg-emerald-500/15 text-emerald-400'
                : 'bg-red-500/15 text-red-400'
            }`}
          >
            {trade.action}
          </span>
        </td>
        <td className="px-4 py-3 font-mono text-xs text-slate-300">{formatInr(entryPrice, 2)}</td>
        <td className="px-4 py-3 font-mono text-xs text-slate-300">
          {quantity.toLocaleString('en-IN', { maximumFractionDigits: 8 })}
        </td>
        <td className="px-4 py-3 font-mono text-xs text-slate-300">
          {isOpen
            ? currentPrice > 0
              ? formatInr(currentPrice, 2)
              : <span className="text-slate-500">--</span>
            : <span className="text-slate-500">--</span>}
        </td>
        <td className="px-4 py-3 font-mono text-xs">
          {isOpen && currentPrice <= 0 ? (
            <span className="text-slate-500">--</span>
          ) : (
            <>
              <span className={isProfit ? 'text-emerald-400' : 'text-red-400'}>
                {isProfit ? '+' : '-'}{formatInr(Math.abs(pnl), 0)}
              </span>
              {pnlPct !== null && (
                <div className={`mt-1 text-[11px] ${isProfit ? 'text-emerald-500' : 'text-red-500'}`}>
                  {isProfit ? '+' : ''}{pnlPct.toFixed(2)}%
                </div>
              )}
            </>
          )}
        </td>
        <td className="px-4 py-3">
          <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_STYLE[trade.status] || STATUS_STYLE.OPEN}`}>
            {STATUS_LABEL[trade.status] || trade.status}
          </span>
        </td>
        <td className="px-4 py-3 font-mono text-xs text-slate-500">{trade.confidence}%</td>
        <td className="px-4 py-3 text-slate-500">
          {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </td>
      </tr>
      {expanded && (
        <tr className="bg-slate-800/30">
          <td colSpan={10} className="px-4 py-3">
            <div className="space-y-2">
              {trade.reasoning && (
                <div>
                  <span className="text-xs uppercase tracking-wider text-slate-500">AI Reasoning</span>
                  <p className="mt-1 text-xs leading-relaxed text-slate-300">{trade.reasoning}</p>
                </div>
              )}
              <div className="flex flex-wrap gap-4 font-mono text-xs text-slate-400">
                <span>SL: {formatInr(trade.stop_loss, 2)}</span>
                <span>TP1: {formatInr(trade.take_profit_1, 2)}</span>
                <span>TP2: {formatInr(trade.take_profit_2, 2)}</span>
                <span>Qty: {quantity.toLocaleString('en-IN', { maximumFractionDigits: 8 })}</span>
                <span>R:R: {trade.risk_reward}</span>
                {isOpen && currentPrice > 0 && <span>Now: {formatInr(currentPrice, 2)}</span>}
                {trade.tax_provision > 0 && <span>Tax: {formatInr(trade.tax_provision, 0)}</span>}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export default function TradeLog({ trades, priceData = {} }) {
  const [filter, setFilter] = useState('all')

  const tradeList = trades?.trades || []
  const filtered = filter === 'all'
    ? tradeList
    : tradeList.filter((trade) => {
        if (filter === 'win') return trade.pnl_after_tax > 0
        if (filter === 'loss') return trade.pnl_after_tax <= 0 && trade.status !== 'OPEN'
        if (filter === 'open') return trade.status === 'OPEN'
        return true
      })

  return (
    <div className="overflow-hidden rounded-xl border border-slate-700/50 bg-slate-800/60">
      <div className="flex items-center justify-between border-b border-slate-700/50 px-4 py-3">
        <span className="text-sm font-semibold text-slate-200">
          Trade Log <span className="ml-1 text-xs font-normal text-slate-500">({tradeList.length} trades)</span>
        </span>
        <div className="flex gap-1">
          {['all', 'open', 'win', 'loss'].map((value) => (
            <button
              key={value}
              onClick={() => setFilter(value)}
              className={`rounded-lg px-2.5 py-1 text-xs capitalize transition-all ${
                filter === value
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-400 hover:bg-slate-700/50 hover:text-slate-300'
              }`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="py-12 text-center text-sm text-slate-500">
          No trades yet. Agent is analyzing the market every hour.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-700/30 text-xs uppercase tracking-wider text-slate-500">
                <th className="px-4 py-2 text-left">Time</th>
                <th className="px-4 py-2 text-left">Pair</th>
                <th className="px-4 py-2 text-left">Action</th>
                <th className="px-4 py-2 text-left">Entry</th>
                <th className="px-4 py-2 text-left">Qty</th>
                <th className="px-4 py-2 text-left">Current</th>
                <th className="px-4 py-2 text-left">P&amp;L</th>
                <th className="px-4 py-2 text-left">Status</th>
                <th className="px-4 py-2 text-left">Conf</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((trade) => (
                <TradeRow key={trade.id} trade={trade} priceData={priceData} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
