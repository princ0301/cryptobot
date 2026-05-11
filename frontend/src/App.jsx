import { useCallback, useMemo, useState } from 'react'
import { Activity, BarChart2, Bot, List, Lock } from 'lucide-react'

import AgentThinking from './components/AgentThinking'
import CoinUniverseManager from './components/CoinUniverseManager'
import CriteriaTracker from './components/CriteriaTracker'
import LatestBuyCard from './components/LatestBuyCard'
import MarketExplorer from './components/MarketExplorer'
import OpenPositions from './components/OpenPositions'
import PortfolioChart from './components/PortfolioChart'
import PortfolioSummary from './components/PortfolioSummary'
import PriceCard from './components/PriceCard'
import ScanShortlistCard from './components/ScanShortlistCard'
import SentimentBar from './components/SentimentBar'
import TradeLog from './components/TradeLog'
import { usePolling } from './hooks/usePolling'
import {
  fetchAgentStatus,
  fetchCriteria,
  fetchHealth,
  fetchLastAnalysis,
  fetchOpenPositions,
  fetchPortfolio,
  fetchPortfolioHistory,
  fetchPrices,
  fetchScanShortlist,
  fetchSentiment,
  fetchTrades,
} from './utils/api'

const TABS = [
  { id: 'dashboard', label: 'Dashboard', icon: <Activity size={14} /> },
  { id: 'trades', label: 'Trades', icon: <List size={14} /> },
  { id: 'portfolio', label: 'Portfolio', icon: <BarChart2 size={14} /> },
  { id: 'market', label: 'Market', icon: <Activity size={14} /> },
  { id: 'live', label: 'Live Mode', icon: <Lock size={14} /> },
]

const DEFAULT_CARD_COUNT = 3

export default function App() {
  const [tab, setTab] = useState('dashboard')

  const { data: prices, refetch: refetchPrices } = usePolling(useCallback(() => fetchPrices(), []), 15000)
  const { data: sentiment } = usePolling(useCallback(() => fetchSentiment(), []), 60000)
  const { data: portfolio } = usePolling(useCallback(() => fetchPortfolio(), []), 20000)
  const { data: history } = usePolling(useCallback(() => fetchPortfolioHistory(), []), 120000)
  const { data: trades } = usePolling(useCallback(() => fetchTrades({ mode: 'paper', limit: 50 }), []), 30000)
  const { data: positions } = usePolling(useCallback(() => fetchOpenPositions(), []), 15000)
  const { data: criteria } = usePolling(useCallback(() => fetchCriteria(), []), 60000)
  const { data: status } = usePolling(useCallback(() => fetchAgentStatus(), []), 30000)
  const { data: health, refetch: refetchHealth } = usePolling(useCallback(() => fetchHealth(), []), 60000)
  const { data: scanShortlist, refetch: refetchScanShortlist } = usePolling(
    useCallback(() => fetchScanShortlist(), []),
    30000,
  )
  const { data: analyses, refetch: refetchAnalyses } = usePolling(
    useCallback(() => fetchLastAnalysis(), []),
    30000,
  )

  const priceData = prices?.prices || {}
  const marketMeta = prices?.meta || {}
  const liveModeUnlocked = criteria?.live_mode_unlocked || false
  const openPositionsList = positions?.positions || []
  const latestPosition = openPositionsList[0] || null
  const openCoins = useMemo(
    () => [...new Set(openPositionsList.map((position) => position.coin).filter(Boolean))],
    [openPositionsList],
  )
  const availableCoins = health?.coins?.length
    ? health.coins
    : Object.values(priceData)
        .map((item) => item?.market)
        .filter(Boolean)
  const visibleCoins = useMemo(
    () => availableCoins.slice(0, Math.min(DEFAULT_CARD_COUNT, availableCoins.length)),
    [availableCoins],
  )
  const handleCoinsChanged = useCallback(() => {
    refetchHealth()
    refetchPrices()
    refetchScanShortlist()
  }, [refetchHealth, refetchPrices, refetchScanShortlist])

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="sticky top-0 z-40 border-b border-slate-800 bg-slate-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600">
              <Bot size={18} className="text-white" />
            </div>
            <div>
              <span className="text-sm font-bold text-white">CryptoAgent</span>
              <span className="ml-2 text-xs text-slate-500">INR Paper Mode</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="live-pulse h-2 w-2 rounded-full bg-emerald-400" />
              <span className="text-xs text-slate-400">{status?.is_running ? 'Running' : 'Active'}</span>
            </div>

            <div className="hidden items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-1.5 sm:flex">
              <span className="text-xs text-slate-500">Interval</span>
              <span className="text-xs font-mono text-slate-300">60 min</span>
            </div>
          </div>
        </div>

        <div className="mx-auto flex max-w-7xl gap-1 px-4 pb-0">
          {TABS.map((item) => (
            <button
              key={item.id}
              onClick={() => setTab(item.id)}
              className={`flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-xs font-medium transition-all ${
                tab === item.id
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-500 hover:text-slate-300'
              }`}
            >
              {item.icon}
              {item.label}
              {item.id === 'live' && liveModeUnlocked && (
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              )}
            </button>
          ))}
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-5">
        {tab === 'dashboard' && (
          <>
            <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
              {visibleCoins.map((coin) => (
                <PriceCard key={coin} coin={coin} data={priceData[coin]} marketMeta={marketMeta} />
              ))}
            </div>

            <PortfolioSummary portfolio={portfolio} openPositions={positions} priceData={priceData} />

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <div className="space-y-4">
                <LatestBuyCard position={latestPosition} />
                <CriteriaTracker criteria={criteria} />
                <SentimentBar sentiment={sentiment} />
              </div>

              <div className="space-y-4 lg:col-span-2">
                <AgentThinking analyses={analyses} onRefresh={refetchAnalyses} />
                <OpenPositions positions={positions} newestPositionId={latestPosition?.id ?? null} />
              </div>
            </div>
          </>
        )}

        {tab === 'trades' && <TradeLog trades={trades} priceData={priceData} marketMeta={marketMeta} />}

        {tab === 'portfolio' && (
          <div className="space-y-4">
            <PortfolioSummary portfolio={portfolio} openPositions={positions} priceData={priceData} />
            <PortfolioChart history={history} />
            <OpenPositions positions={positions} newestPositionId={latestPosition?.id ?? null} />

            <div className="rounded-xl border border-slate-700/50 bg-slate-800/60 p-5">
              <h3 className="mb-4 text-sm font-semibold text-slate-200">Performance Metrics</h3>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                {[
                  { label: 'Win Rate', value: `${criteria?.criteria?.[0]?.current?.toFixed(1) || 0}%`, target: '>=60%' },
                  { label: 'Max Drawdown', value: `${criteria?.criteria?.[1]?.current?.toFixed(1) || 0}%`, target: '<15%' },
                  { label: 'Profit Factor', value: `${criteria?.criteria?.[2]?.current?.toFixed(2) || 0}x`, target: '>=1.5x' },
                  { label: 'Total Trades', value: criteria?.trades_completed || 0, target: `min ${criteria?.trades_required || 30}` },
                ].map((metric) => (
                  <div key={metric.label} className="rounded-lg bg-slate-900/50 p-3">
                    <div className="mb-1 text-xs text-slate-500">{metric.label}</div>
                    <div className="text-lg font-bold text-slate-200">{metric.value}</div>
                    <div className="mt-0.5 text-xs text-slate-600">Target: {metric.target}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === 'market' && (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <div className="xl:col-span-2">
              <div className="space-y-4">
                <ScanShortlistCard shortlist={scanShortlist} />
                <MarketExplorer coins={availableCoins} priceData={priceData} openCoins={openCoins} />
              </div>
            </div>
            <div>
              <CoinUniverseManager onChanged={handleCoinsChanged} />
            </div>
          </div>
        )}

        {tab === 'live' && (
          <div className="mx-auto max-w-lg space-y-4 pt-4">
            {liveModeUnlocked ? (
              <div className="space-y-4 rounded-xl border border-emerald-500/30 bg-emerald-950/30 p-6 text-center">
                <h2 className="text-lg font-bold text-emerald-400">Agent Approved for Live Trading!</h2>
                <p className="text-sm text-slate-400">All 3 promotion criteria passed. Agent has proven its strategy.</p>
                <div className="space-y-2 rounded-lg border border-red-500/30 bg-red-950/40 p-4 text-left">
                  <p className="text-xs font-bold text-red-400">Real Money Warning</p>
                  <p className="text-xs text-slate-400">
                    Live mode places real INR trades on your CoinDCX account. Losses are real. Only proceed if you understand the risks.
                  </p>
                </div>
                <div className="space-y-3 text-left">
                  <div>
                    <label className="mb-1 block text-xs text-slate-400">CoinDCX API Key</label>
                    <input
                      type="password"
                      placeholder="Your API key"
                      className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-slate-400">CoinDCX API Secret</label>
                    <input
                      type="password"
                      placeholder="Your API secret"
                      className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-slate-400">Type confirmation</label>
                    <input
                      type="text"
                      placeholder="I CONFIRM REAL MONEY TRADING"
                      className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 font-mono text-sm text-slate-200 focus:border-red-500 focus:outline-none"
                    />
                  </div>
                  <button className="w-full rounded-lg bg-red-600 py-2.5 text-sm font-bold text-white transition-colors hover:bg-red-700">
                    Activate Live Trading
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-4 rounded-xl border border-slate-700/50 bg-slate-800/60 p-8 text-center">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-slate-700/50">
                  <Lock size={28} className="text-slate-500" />
                </div>
                <h2 className="text-lg font-semibold text-slate-300">Live Mode Locked</h2>
                <p className="mx-auto max-w-sm text-sm text-slate-500">
                  Agent must pass all 3 promotion criteria before live trading is enabled. Keep it running in paper mode.
                </p>
                <CriteriaTracker criteria={criteria} />
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
