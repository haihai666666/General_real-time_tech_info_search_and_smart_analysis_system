import axios from 'axios'

const platformBaseUrl = import.meta.env.VITE_PLATFORM_URL || 'http://localhost:8000'

const platformApi = axios.create({
  baseURL: platformBaseUrl,
  headers: { 'Content-Type': 'application/json' },
})

// ============ Types ============

export type SpiderInfo = {
  name: string
  description: string
  category: string
  is_running: boolean
}

export type CrawlStatusResponse = {
  spider: string
  status: string
  started_at?: string
  finished_at?: string
  items_count: number
  error?: string
}

export type CrawlLogEntry = {
  spider: string
  status: string
  total_items: number
  new_items: number
  finished_at: string
}

export type ArticleResponse = {
  id: string
  title: string
  source: string
  url: string
  published_at: string
  crawled_at: string
  category: string
  status: string
  summary?: string
  tags: string[]
  authors: string[]
}

export type ArticlesPageResponse = {
  articles: ArticleResponse[]
  total: number
  page: number
  page_size: number
}

export type CrawlStats = {
  total_articles: number
  by_source: Record<string, number>
  by_status: Record<string, number>
  by_category: Record<string, number>
}

export type AnalysisMessage = {
  role: string
  content: string
}

export type TrendAnalysisResponse = {
  analysis: string
  article_count: number
}

export type QAResponse = {
  question: string
  answer: string
  sources_count: number
}

export type SummarizeResponse = {
  article_id: string
  title: string
  summary: string
}

// ============ Crawler API ============

export const getSpiders = async (): Promise<SpiderInfo[]> => {
  const res = await platformApi.get('/api/crawler/spiders')
  return res.data
}

export const triggerCrawl = async (spider: string, maxResults: number = 20): Promise<CrawlStatusResponse> => {
  const res = await platformApi.post('/api/crawler/crawl', { spider, max_results: maxResults })
  return res.data
}

export const getCrawlStatus = async (): Promise<{ tasks: Record<string, CrawlStatusResponse> }> => {
  const res = await platformApi.get('/api/crawler/status')
  return res.data
}

export const getCrawlLogs = async (limit: number = 20): Promise<CrawlLogEntry[]> => {
  const res = await platformApi.get(`/api/crawler/logs?limit=${limit}`)
  return res.data
}

export const getArticles = async (params: {
  page?: number
  page_size?: number
  source?: string
  category?: string
  status?: string
  search?: string
}): Promise<ArticlesPageResponse> => {
  const query = new URLSearchParams()
  if (params.page) query.set('page', String(params.page))
  if (params.page_size) query.set('page_size', String(params.page_size))
  if (params.source) query.set('source', params.source)
  if (params.category) query.set('category', params.category)
  if (params.status) query.set('status', params.status)
  if (params.search) query.set('search', params.search)
  const res = await platformApi.get(`/api/crawler/articles?${query.toString()}`)
  return res.data
}

export const getArticleDetail = async (articleId: string): Promise<Record<string, any>> => {
  const res = await platformApi.get(`/api/crawler/articles/${articleId}`)
  return res.data
}

export const getCrawlStats = async (): Promise<CrawlStats> => {
  const res = await platformApi.get('/api/crawler/stats')
  return res.data
}

// ============ Import API ============

export const importSingleArticle = async (articleId: string): Promise<{
  status: string
  message: string
  article_id: string
  title?: string
}> => {
  const res = await platformApi.post(`/api/crawler/import/${articleId}`)
  return res.data
}

export const importBatchArticles = async (articleIds: string[]): Promise<{
  status: string
  total: number
  success: number
  failed: number
  skipped: number
  results: any[]
}> => {
  const res = await platformApi.post('/api/crawler/import/batch', articleIds)
  return res.data
}

// ============ Analysis API ============

export const summarizeArticle = async (articleId: string): Promise<SummarizeResponse> => {
  const res = await platformApi.post('/api/analysis/summarize', { article_id: articleId })
  return res.data
}

export const analyzeTrends = async (source?: string, limit: number = 20): Promise<TrendAnalysisResponse> => {
  const res = await platformApi.post('/api/analysis/trends', { source, limit })
  return res.data
}

export const askQuestion = async (
  question: string,
  source?: string,
  history: AnalysisMessage[] = []
): Promise<QAResponse> => {
  const res = await platformApi.post('/api/analysis/qa', { question, source, stream: false, history })
  return res.data
}

export const askQuestionStream = async (
  question: string,
  onChunk: (chunk: string) => void,
  source?: string,
  history: AnalysisMessage[] = []
): Promise<void> => {
  const response = await fetch(`${platformBaseUrl}/api/analysis/qa`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, source, stream: true, history }),
  })

  if (!response.ok) {
    throw new Error(`HTTP error: ${response.status}`)
  }

  if (!response.body) {
    throw new Error('Response body is null')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.trim()) {
        try {
          const parsed = JSON.parse(line)
          if (parsed.response) {
            onChunk(parsed.response)
          }
        } catch {
          // skip malformed lines
        }
      }
    }
  }

  if (buffer.trim()) {
    try {
      const parsed = JSON.parse(buffer)
      if (parsed.response) {
        onChunk(parsed.response)
      }
    } catch {
      // skip
    }
  }
}
