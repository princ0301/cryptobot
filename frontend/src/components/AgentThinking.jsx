import { Brain, Minus, RefreshCw, TrendingDown, TrendingUp } from 'lucide-react'
import { useState } from 'react'

import { triggerCycle } from '../utils/api'

const ACTION_STYLES = {
  BUY: { color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20', icon: <TrendingUp size={12} /> },
  SELL: { color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20', icon: <TrendingDown size={12} /> },
  HOLD: { color: 'text-slate-400', bg: 'bg-slate-700/40 border-slate-600/30', icon: <Minus size={12} /> },
  SKIPPED: { color: 'text-slate-500', bg: 'bg-slate-800/40 border-slate-700/20', icon: <Minus size={12} /> },
}

function LogEntry({ log }) {
  const action = log.action_taken || 'HOLD'
  const style = ACTION_STYLES[action] || ACTION_STYLES.HOLD
  const time = log.cycle_time
    ? new Date(log.cycle_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
    : '--'

  const coin = `${log.coin?.replace('INR', '') || ''}/INR`
  const reasoning = log.gemini_response?.reasoning || log.skip_reason || '-'

  return (
    <div className={`space-y-1.5 rounded-lg border p-3 ${style.bg}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`flex items-center gap-1 text-xs font-bold ${style.color}`}>
            {style.icon} {action}
          </span>
          <span className="font-mono text-xs text-slate-300">{coin}</span>
        </div>
        <div className="flex items-center gap-2">
          {log.confidence > 0 && <span className="font-mono text-xs text-slate-500">{log.confidence}% conf</span>}
          <span className="text-xs text-slate-600">{time}</span>
        </div>
      </div>
      {reasoning && <p className="text-xs leading-relaxed text-slate-400">{reasoning}</p>}
      {log.indicators && (
        <div className="flex flex-wrap gap-2 pt-0.5">
          {log.indicators.rsi && <span className="font-mono text-xs text-slate-500">RSI {log.indicators.rsi?.toFixed(1)}</span>}
          {log.indicators.trend && <span className="font-mono text-xs capitalize text-slate-500">{log.indicators.trend}</span>}
          {log.indicators.macd_crossover && (
            <span className="font-mono text-xs capitalize text-slate-500">{log.indicators.macd_crossover?.replace('_', ' ')}</span>
          )}
          {log.indicators.volume_ratio && (
            <span className="font-mono text-xs text-slate-500">Vol {log.indicators.volume_ratio?.toFixed(2)}x</span>
          )}
        </div>
      )}
    </div>
  )
}

export default function AgentThinking({ analyses, onRefresh }) {
  const [triggering, setTriggering] = useState(false)

  const handleTrigger = async () => {
    setTriggering(true)
    try {
      await triggerCycle()
      setTimeout(() => {
        onRefresh?.()
        setTriggering(false)
      }, 3000)
    } catch {
      setTriggering(false)
    }
  }

  const logs = analyses?.analyses || []

  return (
    <div className="overflow-hidden rounded-xl border border-slate-700/50 bg-slate-800/60">
      <div className="flex items-center justify-between border-b border-slate-700/50 px-4 py-3">
        <div className="flex items-center gap-2">
          <Brain size={15} className="text-indigo-400" />
          <span className="text-sm font-semibold text-slate-200">Agent Thinking</span>
          <span className="text-xs text-slate-500">last 3 cycles</span>
        </div>
        <button
          onClick={handleTrigger}
          disabled={triggering}
          className="flex items-center gap-1.5 rounded-lg bg-slate-700/50 px-2.5 py-1.5 text-xs text-slate-400 transition-all hover:bg-slate-700 hover:text-slate-200 disabled:opacity-50"
        >
          <RefreshCw size={12} className={triggering ? 'animate-spin' : ''} />
          {triggering ? 'Running...' : 'Run Now'}
        </button>
      </div>
      <div className="max-h-72 space-y-2 overflow-y-auto p-3">
        {logs.length === 0 ? (
          <div className="py-8 text-center text-sm text-slate-500">No analysis yet. Hit "Run Now" to trigger a cycle.</div>
        ) : (
          logs.map((log, index) => <LogEntry key={index} log={log} />)
        )}
      </div>
    </div>
  )
}
