import { ArrowDownAZ, ArrowUpDown, Pin, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import PriceCard from './PriceCard'

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'gainers', label: 'Gainers' },
  { id: 'losers', label: 'Losers' },
  { id: 'open', label: 'Open Trades' },
]

const SORT_OPTIONS = [
  { id: 'change_desc', label: '% Gain', icon: <ArrowUpDown size={12} /> },
  { id: 'price_desc', label: 'Price', icon: <ArrowUpDown size={12} /> },
  { id: 'symbol_asc', label: 'A-Z', icon: <ArrowDownAZ size={12} /> },
]

const FAVORITES_KEY = 'cryptoagent.market.favorites'

export default function MarketExplorer({ coins, priceData, openCoins = [] }) {
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [sortBy, setSortBy] = useState('change_desc')
  const [favorites, setFavorites] = useState([])

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(FAVORITES_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed)) {
          setFavorites(parsed)
        }
      }
    } catch {
      setFavorites([])
    }
  }, [])

  useEffect(() => {
    window.localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites))
  }, [favorites])

  const filteredCoins = useMemo(() => {
    const normalizedQuery = query.trim().toUpperCase()
    const openCoinSet = new Set(openCoins)
    const favoriteSet = new Set(favorites)

    const visible = coins.filter((coin) => {
      const matchesQuery =
        !normalizedQuery ||
        coin.includes(normalizedQuery) ||
        coin.replace('INR', '').includes(normalizedQuery)

      if (!matchesQuery) {
        return false
      }

      const change = Number(priceData?.[coin]?.change_24h ?? 0)
      if (filter === 'gainers') {
        return change >= 0
      }
      if (filter === 'losers') {
        return change < 0
      }
      if (filter === 'open') {
        return openCoinSet.has(coin)
      }
      return true
    })

    return visible.sort((left, right) => {
      const leftPinned = favoriteSet.has(left) ? 1 : 0
      const rightPinned = favoriteSet.has(right) ? 1 : 0
      if (leftPinned !== rightPinned) {
        return rightPinned - leftPinned
      }

      if (sortBy === 'price_desc') {
        return Number(priceData?.[right]?.price ?? 0) - Number(priceData?.[left]?.price ?? 0)
      }
      if (sortBy === 'symbol_asc') {
        return left.localeCompare(right)
      }
      return Number(priceData?.[right]?.change_24h ?? 0) - Number(priceData?.[left]?.change_24h ?? 0)
    })
  }, [coins, favorites, filter, openCoins, priceData, query, sortBy])

  const handleToggleFavorite = (coin) => {
    setFavorites((current) =>
      current.includes(coin) ? current.filter((item) => item !== coin) : [...current, coin],
    )
  }

  return (
    <div className="rounded-xl border border-slate-700/50 bg-slate-800/60 p-4">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">Market Explorer</h3>
          <p className="text-xs text-slate-500">Search, sort, and pin configured pairs while keeping open trades easy to spot.</p>
        </div>

        <div className="flex flex-col gap-3 lg:items-end">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2">
              <Search size={14} className="text-slate-500" />
              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search coin"
                className="w-full bg-transparent text-sm text-slate-200 outline-none placeholder:text-slate-500 sm:w-40"
              />
            </div>

            <select
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-slate-200 outline-none focus:border-indigo-500"
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>
                  Sort: {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-wrap gap-2">
            {FILTERS.map((item) => (
              <button
                key={item.id}
                onClick={() => setFilter(item.id)}
                className={`rounded-lg px-3 py-2 text-xs transition-colors ${
                  filter === item.id
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-900/70 text-slate-400 hover:text-slate-200'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <span className="rounded-full bg-slate-900/70 px-2 py-1">{filteredCoins.length} visible</span>
        <span className="rounded-full bg-slate-900/70 px-2 py-1">{openCoins.length} open-trade coins</span>
        <span className="inline-flex items-center gap-1 rounded-full bg-slate-900/70 px-2 py-1">
          <Pin size={11} />
          {favorites.length} pinned
        </span>
      </div>

      {filteredCoins.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-700 px-4 py-8 text-center text-sm text-slate-500">
          No coins match the current filter.
        </div>
      ) : (
        <div className="max-h-[70vh] space-y-3 overflow-y-auto pr-1">
          {filteredCoins.map((coin) => (
            <PriceCard
              key={coin}
              coin={coin}
              data={priceData?.[coin]}
              isPinned={favorites.includes(coin)}
              isOpenPosition={openCoins.includes(coin)}
              onTogglePin={handleToggleFavorite}
            />
          ))}
        </div>
      )}
    </div>
  )
}
