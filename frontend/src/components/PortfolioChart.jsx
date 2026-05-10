import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const val = payload[0]?.value
  const isProfit = val >= 100000
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-slate-400 mb-1">{label}</p>
      <p className={`font-bold ${isProfit ? 'text-emerald-400' : 'text-red-400'}`}>
        ₹{val?.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
      </p>
    </div>
  )
}

export default function PortfolioChart({ history }) {
  const data = history?.history || []

  // If no history yet, show placeholder
  if (data.length === 0) {
    return (
      <div className="bg-slate-800/60 rounded-xl p-5 border border-slate-700/50">
        <div className="flex items-center justify-between mb-4">
          <span className="text-sm font-semibold text-slate-200">Portfolio Value</span>
          <span className="text-xs text-slate-500">Daily</span>
        </div>
        <div className="h-40 flex items-center justify-center text-slate-500 text-sm">
          Chart will populate as agent trades
        </div>
      </div>
    )
  }

  const chartData = data.map(d => ({
    date: new Date(d.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }),
    value: d.portfolio_value,
  }))

  const min = Math.min(...chartData.map(d => d.value))
  const max = Math.max(...chartData.map(d => d.value))
  const latest = chartData[chartData.length - 1]?.value || 100000
  const isProfit = latest >= 100000

  return (
    <div className="bg-slate-800/60 rounded-xl p-5 border border-slate-700/50">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-semibold text-slate-200">Portfolio Value</span>
        <span className={`text-sm font-bold ${isProfit ? 'text-emerald-400' : 'text-red-400'}`}>
          ₹{latest?.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10, fill: '#64748b' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[Math.max(min * 0.98, 0), max * 1.02]}
            tick={{ fontSize: 10, fill: '#64748b' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={v => `₹${(v/1000).toFixed(0)}k`}
            width={45}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={100000} stroke="#475569" strokeDasharray="3 3" />
          <Line
            type="monotone"
            dataKey="value"
            stroke={isProfit ? '#10b981' : '#ef4444'}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: isProfit ? '#10b981' : '#ef4444' }}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="text-xs text-slate-600 mt-2 text-center">Dashed line = starting ₹1,00,000</p>
    </div>
  )
}