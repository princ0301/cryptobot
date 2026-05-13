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

function getStatusMeta(trade) {
  const realizedPnl = Number(trade.pnl_after_tax || 0)

  if (trade.status === 'CLOSED_SL' && realizedPnl > 0) {
    return {
      label: 'Locked Profit',
      style: 'bg-emerald-500/15 text-emerald-400',
    }
  }

  return {
    label: STATUS_LABEL[trade.status] || trade.status,
    style: STATUS_STYLE[trade.status] || STATUS_STYLE.OPEN,
  }
}

function getExitTypeLabel(trade) {
  const realizedPnl = Number(trade.pnl_after_tax || 0)

  if (trade.status === 'CLOSED_SL' && realizedPnl > 0) return 'Locked Profit'
  if (trade.status === 'CLOSED_TP1') return 'TP1 Hit'
  if (trade.status === 'CLOSED_TP2') return 'TP2 Hit'
  if (trade.status === 'CLOSED_SL') return 'Stop Loss'
  if (trade.status === 'CLOSED_MANUAL') return 'Manual Exit'
  return trade.status
}

function getStageLabel(trade) {
  if (trade.status === 'OPEN') return 'Open'
  return getExitTypeLabel(trade)
}

function getStageStyle(trade) {
  if (trade.status === 'OPEN') return 'bg-blue-500/15 text-blue-400'
  if (trade.status === 'CLOSED_SL' && Number(trade.pnl_after_tax || 0) > 0) {
    return 'bg-emerald-500/15 text-emerald-400'
  }
  if (trade.status === 'CLOSED_TP1' || trade.status === 'CLOSED_TP2') {
    return 'bg-emerald-500/15 text-emerald-400'
  }
  if (trade.status === 'CLOSED_SL') return 'bg-red-500/15 text-red-400'
  return 'bg-slate-500/15 text-slate-400'
}

function sortTradesForFilter(trades, filter) {
  const getTimestamp = (trade, preferredField) => {
    const raw = trade?.[preferredField] || trade?.opened_at || trade?.created_at
    const value = raw ? new Date(raw).getTime() : 0
    return Number.isNaN(value) ? 0 : value
  }

  const sorted = [...trades]

  if (filter === 'all') {
    sorted.sort((a, b) => {
      const aOpen = a.status === 'OPEN'
      const bOpen = b.status === 'OPEN'
      if (aOpen !== bOpen) return aOpen ? -1 : 1
      if (aOpen && bOpen) return getTimestamp(b, 'opened_at') - getTimestamp(a, 'opened_at')
      return getTimestamp(b, 'closed_at') - getTimestamp(a, 'closed_at')
    })
    return sorted
  }

  if (filter === 'open') {
    sorted.sort((a, b) => getTimestamp(b, 'opened_at') - getTimestamp(a, 'opened_at'))
    return sorted
  }

  sorted.sort((a, b) => getTimestamp(b, 'closed_at') - getTimestamp(a, 'closed_at'))
  return sorted
}

function formatInr(value, digits = 0) {
  return `INR ${Number(value || 0).toLocaleString('en-IN', { maximumFractionDigits: digits })}`
}

function formatUpdatedAt(value) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function TradeRow({ trade, priceData, showCurrentColumn, showActionColumn, showExitTypeColumn, onManualCloseTrade }) {
  const [expanded, setExpanded] = useState(false)
  const [closing, setClosing] = useState(false)
  const isOpen = trade.status === 'OPEN'
  const statusMeta = getStatusMeta(trade)
  const exitTypeLabel = getExitTypeLabel(trade)
  const stageLabel = getStageLabel(trade)
  const stageStyle = getStageStyle(trade)
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

  const handleManualClose = async (event) => {
    event.stopPropagation()
    if (!isOpen || closing || !onManualCloseTrade) return

    const confirmed = window.confirm(`Close ${coin} manually at the current market price?`)
    if (!confirmed) return

    try {
      setClosing(true)
      await onManualCloseTrade(trade.id)
    } finally {
      setClosing(false)
    }
  }

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
        {showActionColumn && (
          <td className="px-4 py-3">
            <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${stageStyle}`}>
              {stageLabel}
            </span>
          </td>
        )}
        {showExitTypeColumn && (
          <td className="px-4 py-3 text-xs text-slate-300">
            {exitTypeLabel}
          </td>
        )}
        <td className="px-4 py-3 font-mono text-xs text-slate-300">{formatInr(entryPrice, 2)}</td>
        <td className="px-4 py-3 font-mono text-xs text-slate-300">
          {quantity.toLocaleString('en-IN', { maximumFractionDigits: 8 })}
        </td>
        {showCurrentColumn && (
          <td className="px-4 py-3 font-mono text-xs text-slate-300">
            {isOpen
              ? currentPrice > 0
                ? formatInr(currentPrice, 2)
                : <span className="text-slate-500">--</span>
              : <span className="text-slate-500">--</span>}
          </td>
        )}
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
          <span className={`rounded-full px-2 py-0.5 text-xs ${statusMeta.style}`}>
            {statusMeta.label}
          </span>
        </td>
        <td className="px-4 py-3 font-mono text-xs text-slate-500">{trade.confidence}%</td>
        <td className="px-4 py-3 text-slate-500">
          {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </td>
      </tr>
      {expanded && (
        <tr className="bg-slate-800/30">
          <td colSpan={6 + (showActionColumn ? 1 : 0) + (showExitTypeColumn ? 1 : 0) + (showCurrentColumn ? 1 : 0) + 1} className="px-4 py-3">
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
              {isOpen && onManualCloseTrade && (
                <div className="pt-1">
                  <button
                    type="button"
                    onClick={handleManualClose}
                    disabled={closing}
                    className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-1.5 text-xs font-semibold text-red-300 transition-colors hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {closing ? 'Closing...' : 'Manual Exit'}
                  </button>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export default function TradeLog({ trades, priceData = {}, marketMeta = {}, onManualCloseTrade }) {
  const [filter, setFilter] = useState('all')
  const updatedAt = formatUpdatedAt(marketMeta?.served_at)
  const showCurrentColumn = filter === 'all' || filter === 'open'
  const showActionColumn = filter === 'all' || filter === 'open'
  const showExitTypeColumn = filter === 'win' || filter === 'loss'

  const tradeList = trades?.trades || []
  const filteredBase = filter === 'all'
    ? tradeList
    : tradeList.filter((trade) => {
        if (filter === 'win') return trade.pnl_after_tax > 0
        if (filter === 'loss') return trade.pnl_after_tax <= 0 && trade.status !== 'OPEN'
        if (filter === 'open') return trade.status === 'OPEN'
        return true
      })
  const filtered = sortTradesForFilter(filteredBase, filter)

  return (
    <div className="overflow-hidden rounded-xl border border-slate-700/50 bg-slate-800/60">
      <div className="flex items-center justify-between border-b border-slate-700/50 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-200">
            Trade Log <span className="ml-1 text-xs font-normal text-slate-500">({tradeList.length} trades)</span>
          </span>
          {marketMeta?.stale && (
            <span className="rounded bg-amber-500/15 px-2 py-0.5 text-xs text-amber-300">
              Cached market data
            </span>
          )}
          {updatedAt && (
            <span className="text-xs text-slate-500">
              Updated {updatedAt}
            </span>
          )}
        </div>
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
                {showActionColumn && <th className="px-4 py-2 text-left">Stage</th>}
                {showExitTypeColumn && <th className="px-4 py-2 text-left">Exit Type</th>}
                <th className="px-4 py-2 text-left">Entry</th>
                <th className="px-4 py-2 text-left">Qty</th>
                {showCurrentColumn && <th className="px-4 py-2 text-left">Current</th>}
                <th className="px-4 py-2 text-left">P&amp;L</th>
                <th className="px-4 py-2 text-left">Status</th>
                <th className="px-4 py-2 text-left">Conf</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((trade) => (
                <TradeRow
                  key={trade.id}
                  trade={trade}
                  priceData={priceData}
                  showCurrentColumn={showCurrentColumn}
                  showActionColumn={showActionColumn}
                  showExitTypeColumn={showExitTypeColumn}
                  onManualCloseTrade={onManualCloseTrade}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
