import { Activity, TrendingDown, TrendingUp, Wallet } from 'lucide-react'

export default function PortfolioSummary({ portfolio, openPositions, priceData = {} }) {
  if (!portfolio) {
    return (
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[...Array(4)].map((_, index) => (
          <div
            key={index}
            className="h-24 rounded-xl border border-slate-700/50 bg-slate-800/50 p-4 animate-pulse"
          />
        ))}
      </div>
    )
  }

  const startBalance = 100000
  const openPositionList = openPositions?.positions || []
  const liveOpenPnl = openPositionList.reduce((sum, position) => {
    const currentPrice = Number(priceData?.[position.coin]?.price || position.current_price || 0)
    const entryPrice = Number(position.entry_price || 0)
    const quantity = Number(position.quantity || 0)

    if (!currentPrice || !entryPrice || !quantity) {
      return sum + Number(position.unrealized_pnl || 0)
    }

    return sum + ((currentPrice - entryPrice) * quantity)
  }, 0)

  const pnl = liveOpenPnl
  const pnlToday = portfolio.pnl_today || 0
  const isProfit = pnl >= 0
  const isTodayProfit = pnlToday >= 0
  const pnlPct = ((pnl / startBalance) * 100).toFixed(2)
  const liveTotalValue = Number(portfolio.inr_balance || 0) + openPositionList.reduce((sum, position) => {
    const currentPrice = Number(priceData?.[position.coin]?.price || position.current_price || 0)
    const quantity = Number(position.quantity || 0)
    const fallback = Number(position.position_inr || 0)
    return sum + (currentPrice > 0 && quantity > 0 ? currentPrice * quantity : fallback)
  }, 0)

  const cards = [
    {
      label: 'Available Balance',
      value: `INR ${portfolio.inr_balance?.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,
      sub: 'Paper INR',
      icon: <Wallet size={16} className="text-slate-400" />,
      color: 'text-white',
    },
    {
      label: 'Total Portfolio',
      value: `INR ${liveTotalValue.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,
      sub: 'Started INR 1,00,000',
      icon: <Activity size={16} className="text-slate-400" />,
      color: 'text-white',
    },
    {
      label: 'Total P&L',
      value: `${isProfit ? '+' : ''}INR ${Math.abs(pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,
      sub: `${isProfit ? '+' : ''}${pnlPct}% overall`,
      icon: isProfit ? <TrendingUp size={16} className="text-emerald-400" /> : <TrendingDown size={16} className="text-red-400" />,
      color: isProfit ? 'text-emerald-400' : 'text-red-400',
    },
    {
      label: "Today's P&L",
      value: `${isTodayProfit ? '+' : ''}INR ${Math.abs(pnlToday).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,
      sub: `${openPositions?.count || 0} open position${(openPositions?.count || 0) !== 1 ? 's' : ''}`,
      icon: isTodayProfit ? <TrendingUp size={16} className="text-emerald-400" /> : <TrendingDown size={16} className="text-red-400" />,
      color: isTodayProfit ? 'text-emerald-400' : 'text-red-400',
    },
  ]

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {cards.map((card) => (
        <div key={card.label} className="rounded-xl border border-slate-700/50 bg-slate-800/60 p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs text-slate-400">{card.label}</span>
            {card.icon}
          </div>
          <div className={`num-transition text-lg font-bold ${card.color}`}>{card.value}</div>
          <div className="mt-1 text-xs text-slate-500">{card.sub}</div>
        </div>
      ))}
    </div>
  )
}
