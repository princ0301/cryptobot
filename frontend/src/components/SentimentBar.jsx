export default function SentimentBar({ sentiment }) {
  if (!sentiment) {
    return <div className="h-20 rounded-xl border border-slate-700/50 bg-slate-800/60 p-4 animate-pulse" />
  }

  const score = sentiment.fear_greed?.score ?? sentiment.score ?? 50
  const label = sentiment.fear_greed?.label || sentiment.label || sentiment.sentiment_label || 'Neutral'
  const signalText =
    sentiment.fear_greed?.trade_hint ||
    sentiment.sentiment_label ||
    sentiment.signal_text ||
    'Market sentiment indicator'

  const color =
    score <= 25 ? 'bg-red-500' :
    score <= 45 ? 'bg-orange-500' :
    score <= 55 ? 'bg-slate-400' :
    score <= 75 ? 'bg-emerald-500' :
    'bg-yellow-400'

  const textColor =
    score <= 25 ? 'text-red-400' :
    score <= 45 ? 'text-orange-400' :
    score <= 55 ? 'text-slate-400' :
    score <= 75 ? 'text-emerald-400' :
    'text-yellow-400'

  return (
    <div className="rounded-xl border border-slate-700/50 bg-slate-800/60 p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs text-slate-400">Fear & Greed Index</span>
        <span className={`text-xs font-bold ${textColor}`}>{label}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-2xl font-bold text-white">{score}</span>
        <div className="flex-1">
          <div className="h-2 overflow-hidden rounded-full bg-slate-700">
            <div
              className={`h-full rounded-full transition-all duration-700 ${color}`}
              style={{ width: `${score}%` }}
            />
          </div>
          <div className="mt-1 flex justify-between text-xs text-slate-600">
            <span>Extreme Fear</span>
            <span>Extreme Greed</span>
          </div>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-500">{signalText}</p>
    </div>
  )
}
