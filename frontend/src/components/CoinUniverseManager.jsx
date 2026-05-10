import { Eye, EyeOff, Plus, RefreshCw, Search, ShieldCheck, ShieldOff, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { addCoin, fetchCoins, removeCoin, searchCoins, updateCoin } from '../utils/api'


function formatErrorDetail(detail) {
  if (!detail) return ''
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item?.message || JSON.stringify(item)).join(', ')
  }
  if (typeof detail === 'object') {
    const message = detail.message || 'Validation failed.'
    const reasons = Array.isArray(detail.reasons) ? detail.reasons.join(' ') : ''
    return [message, reasons].filter(Boolean).join(' ')
  }
  return detail
}

export default function CoinUniverseManager({ onChanged }) {
  const [pairs, setPairs] = useState([])
  const [symbol, setSymbol] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [searching, setSearching] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const searchTimeoutRef = useRef(null)

  const loadPairs = async () => {
    try {
      setLoading(true)
      const response = await fetchCoins()
      setPairs(response.data?.pairs || [])
      setError('')
    } catch (err) {
      setError(formatErrorDetail(err.response?.data?.detail) || err.message || 'Failed to load coins.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadPairs()
  }, [])

  useEffect(() => {
    const query = symbol.trim()
    if (searchTimeoutRef.current) {
      window.clearTimeout(searchTimeoutRef.current)
    }

    if (!query) {
      setSuggestions([])
      setSearching(false)
      return
    }

    searchTimeoutRef.current = window.setTimeout(async () => {
      setSearching(true)
      try {
        const response = await searchCoins(query)
        setSuggestions(response.data?.suggestions || [])
        setShowSuggestions(true)
      } catch {
        setSuggestions([])
      } finally {
        setSearching(false)
      }
    }, 200)

    return () => {
      if (searchTimeoutRef.current) {
        window.clearTimeout(searchTimeoutRef.current)
      }
    }
  }, [symbol])

  const handleAdd = async (event) => {
    event.preventDefault()
    const normalized = symbol.trim().toUpperCase()
    if (!normalized) {
      return
    }

    setSaving(true)
    setError('')
    setMessage('')
    try {
      const response = await addCoin(normalized)
      setMessage(response.data?.message || `${normalized} added.`)
      setSymbol('')
      setSuggestions([])
      setShowSuggestions(false)
      await loadPairs()
      onChanged?.()
    } catch (err) {
      setError(formatErrorDetail(err.response?.data?.detail) || err.message || `Failed to add ${normalized}.`)
    } finally {
      setSaving(false)
    }
  }

  const handleRemove = async (target) => {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const response = await removeCoin(target)
      setMessage(response.data?.message || `${target} removed.`)
      await loadPairs()
      onChanged?.()
    } catch (err) {
      setError(formatErrorDetail(err.response?.data?.detail) || err.message || `Failed to remove ${target}.`)
    } finally {
      setSaving(false)
    }
  }

  const handleUpdate = async (target, payload) => {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const response = await updateCoin(target, payload)
      setMessage(response.data?.message || `${target} updated.`)
      await loadPairs()
      onChanged?.()
    } catch (err) {
      setError(formatErrorDetail(err.response?.data?.detail) || err.message || `Failed to update ${target}.`)
    } finally {
      setSaving(false)
    }
  }

  const handleSelectSuggestion = (suggestion) => {
    setSymbol(suggestion.symbol)
    setShowSuggestions(false)
  }

  return (
    <div className="rounded-xl border border-slate-700/50 bg-slate-800/60 p-4">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">Trading Universe</h3>
          <p className="mt-1 text-xs text-slate-500">
            Frontend requests changes, but the backend validates CoinDCX support before saving.
          </p>
        </div>
        <button
          type="button"
          onClick={loadPairs}
          disabled={loading || saving}
          className="rounded-lg bg-slate-900/70 p-2 text-slate-400 transition-colors hover:text-slate-200 disabled:opacity-50"
          title="Refresh coin list"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      <form onSubmit={handleAdd} className="mb-4 flex gap-2">
        <div className="relative flex-1">
          <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 focus-within:border-indigo-500">
            <Search size={14} className="text-slate-500" />
            <input
              type="text"
              value={symbol}
              onChange={(event) => setSymbol(event.target.value.toUpperCase())}
              onFocus={() => setShowSuggestions(true)}
              placeholder="Search coin, e.g. VELO, APT, OSMO"
              className="w-full bg-transparent text-sm text-slate-200 outline-none placeholder:text-slate-500"
            />
          </div>

          {showSuggestions && (symbol.trim() || suggestions.length > 0) && (
            <div className="absolute z-20 mt-2 max-h-56 w-full overflow-y-auto rounded-lg border border-slate-700 bg-slate-950/98 shadow-2xl">
              {searching ? (
                <div className="px-3 py-2 text-xs text-slate-500">Searching CoinDCX markets...</div>
              ) : suggestions.length === 0 ? (
                <div className="px-3 py-2 text-xs text-slate-500">No active INR matches found.</div>
              ) : (
                suggestions.map((suggestion) => (
                  <button
                    key={suggestion.symbol}
                    type="button"
                    onClick={() => handleSelectSuggestion(suggestion)}
                    className="flex w-full items-center justify-between px-3 py-2 text-left transition-colors hover:bg-slate-800/80"
                  >
                    <div>
                      <div className="font-mono text-sm text-slate-200">{suggestion.symbol}</div>
                      <div className="text-xs text-slate-500">{suggestion.display}</div>
                    </div>
                    <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
                      {suggestion.asset}
                    </span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
        <button
          type="submit"
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-500 disabled:opacity-50"
        >
          <Plus size={14} />
          Add
        </button>
      </form>

      {message && (
        <div className="mb-3 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">
          {message}
        </div>
      )}

      {error && (
        <div className="mb-3 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      <div className="mb-3 flex items-center justify-between text-xs text-slate-500">
        <span>{pairs.length} approved pairs</span>
        <span>
          {pairs.filter((pair) => pair.watched).length} watched / {pairs.filter((pair) => pair.tradable).length} tradable
        </span>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[...Array(6)].map((_, index) => (
            <div key={index} className="h-10 animate-pulse rounded-lg bg-slate-900/70" />
          ))}
        </div>
      ) : (
        <div className="max-h-[60vh] space-y-2 overflow-y-auto pr-1">
          {pairs.map((pair) => (
            <div
              key={pair.symbol}
              className="flex items-center justify-between rounded-lg border border-slate-700/50 bg-slate-900/60 px-3 py-2"
            >
              <div>
                <div className="font-mono text-sm text-slate-200">{pair.symbol}</div>
                <div className="text-xs text-slate-500">{pair.display}</div>
                <div className="mt-1 flex flex-wrap gap-2">
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                      pair.watched ? 'bg-blue-500/15 text-blue-300' : 'bg-slate-700/60 text-slate-400'
                    }`}
                  >
                    {pair.watched ? 'Watched' : 'Hidden'}
                  </span>
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                      pair.tradable ? 'bg-emerald-500/15 text-emerald-300' : 'bg-yellow-500/15 text-yellow-300'
                    }`}
                  >
                    {pair.tradable ? 'Tradable' : 'Watch Only'}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => handleUpdate(pair.symbol, { watched: !pair.watched })}
                  disabled={saving}
                  className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-blue-500/10 hover:text-blue-300 disabled:opacity-50"
                  title={pair.watched ? `Hide ${pair.symbol} from watchlist` : `Add ${pair.symbol} to watchlist`}
                >
                  {pair.watched ? <Eye size={14} /> : <EyeOff size={14} />}
                </button>

                <button
                  type="button"
                  onClick={() => handleUpdate(pair.symbol, { tradable: !pair.tradable, watched: true })}
                  disabled={saving}
                  className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-emerald-500/10 hover:text-emerald-300 disabled:opacity-50"
                  title={pair.tradable ? `Set ${pair.symbol} to watch only` : `Enable trading for ${pair.symbol}`}
                >
                  {pair.tradable ? <ShieldCheck size={14} /> : <ShieldOff size={14} />}
                </button>

                <button
                  type="button"
                  onClick={() => handleRemove(pair.symbol)}
                  disabled={saving}
                  className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-red-500/10 hover:text-red-300 disabled:opacity-50"
                  title={`Remove ${pair.symbol}`}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
