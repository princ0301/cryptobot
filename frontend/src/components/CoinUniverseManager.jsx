import { Plus, RefreshCw, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { addCoin, fetchCoins, removeCoin } from '../utils/api'

export default function CoinUniverseManager({ onChanged }) {
  const [pairs, setPairs] = useState([])
  const [symbol, setSymbol] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const loadPairs = async () => {
    try {
      setLoading(true)
      const response = await fetchCoins()
      setPairs(response.data?.pairs || [])
      setError('')
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load coins.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadPairs()
  }, [])

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
      await loadPairs()
      onChanged?.()
    } catch (err) {
      const detail = err.response?.data?.detail
      const normalizedDetail = Array.isArray(detail)
        ? detail.map((item) => item?.msg || item?.message || JSON.stringify(item)).join(', ')
        : detail
      setError(normalizedDetail || err.message || `Failed to add ${normalized}.`)
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
      const detail = err.response?.data?.detail
      const normalizedDetail = Array.isArray(detail)
        ? detail.map((item) => item?.msg || item?.message || JSON.stringify(item)).join(', ')
        : detail
      setError(normalizedDetail || err.message || `Failed to remove ${target}.`)
    } finally {
      setSaving(false)
    }
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
        <input
          type="text"
          value={symbol}
          onChange={(event) => setSymbol(event.target.value.toUpperCase())}
          placeholder="Add coin, e.g. VELO or VELOINR"
          className="flex-1 rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-slate-200 outline-none placeholder:text-slate-500 focus:border-indigo-500"
        />
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
        <span>Backend-managed</span>
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
              </div>

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
          ))}
        </div>
      )}
    </div>
  )
}
