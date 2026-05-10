import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 15000,
})

export const fetchPrices = () => api.get('/market/prices')
export const fetchSentiment = () => api.get('/market/sentiment')
export const fetchPortfolio    = () => api.get('/portfolio/balance')
export const fetchPortfolioHistory = () => api.get('/portfolio/history')
export const fetchTrades       = (params) => api.get('/trades/history', { params })
export const fetchOpenPositions = () => api.get('/trades/open')
export const fetchPerformance  = () => api.get('/performance/metrics')
export const fetchCriteria     = () => api.get('/performance/criteria')
export const fetchCoinPerf     = () => api.get('/performance/coins')
export const fetchAgentStatus  = () => api.get('/agent/status')
export const fetchLastAnalysis = () => api.get('/agent/last-analysis')
export const triggerCycle      = () => api.post('/agent/run-now')
export const startAgent        = () => api.post('/agent/start')
export const stopAgent         = () => api.post('/agent/stop')
export const fetchHealth       = () => api.get('/health')
export const fetchCoins        = () => api.get('/coins')
export const addCoin           = (symbol) => api.post('/coins', { symbol })
export const updateCoin        = (symbol, payload) => api.patch(`/coins/${symbol}`, payload)
export const removeCoin        = (symbol) => api.delete(`/coins/${symbol}`)

export default api
