export default function ScanShortlistCard({ shortlist }) {
  const selected = shortlist?.selected_pairs || []
  const ranked = shortlist?.ranked_pairs || []
  const updatedAt = shortlist?.updated_at
    ? new Date(shortlist.updated_at).toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
      })
    : null

  return (
    <div className="rounded-xl border border-slate-700/50 bg-slate-800/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">Scanned This Cycle</h3>
          <p className="mt-1 text-xs text-slate-500">
            Tradable coins selected by the ranked scanner before analysis.
          </p>
        </div>
        {updatedAt && <span className="text-xs text-slate-500">Updated {updatedAt}</span>}
      </div>

      {selected.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-700 px-4 py-6 text-center text-sm text-slate-500">
          No scan shortlist yet. Trigger a cycle or wait for the next scheduled scan.
        </div>
      ) : (
        <>
          <div className="mb-3 flex flex-wrap gap-2">
            {selected.map((pair) => (
              <span
                key={pair}
                className="rounded-full bg-indigo-500/15 px-2.5 py-1 text-xs font-semibold text-indigo-300"
              >
                {pair.replace('INR', '')}/INR
              </span>
            ))}
          </div>

          <div className="space-y-2">
            {ranked.map((item, index) => (
              <div
                key={item.pair}
                className="flex items-center justify-between rounded-lg border border-slate-700/40 bg-slate-900/50 px-3 py-2"
              >
                <div>
                  <div className="text-sm font-semibold text-slate-200">
                    {index + 1}. {item.pair.replace('INR', '')}/INR
                  </div>
                  <div className="mt-0.5 text-xs text-slate-500">
                    Vol INR {Number(item.vol_inr || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })} ·
                    Spread {item.spread_pct}% 
                  </div>
                </div>

                <div className="text-right">
                  <div
                    className={`text-sm font-semibold ${
                      Number(item.change_24h) >= 0 ? 'text-emerald-400' : 'text-red-400'
                    }`}
                  >
                    {Number(item.change_24h) >= 0 ? '+' : ''}
                    {Number(item.change_24h || 0).toFixed(2)}%
                  </div>
                  <div className="text-xs text-slate-500">Score {Number(item.score || 0).toFixed(0)}</div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
