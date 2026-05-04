import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import {
  getSpiders, triggerCrawl, getCrawlStats, getArticles, getCrawlLogs, getCrawlStatus,
  importSingleArticle, importBatchArticles,
  type SpiderInfo, type ArticleResponse, type CrawlStats, type CrawlLogEntry,
} from '@/api/platform'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Badge from '@/components/ui/Badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select'
import {
  DatabaseIcon, RefreshCwIcon, PlayIcon, SearchIcon, GlobeIcon,
  BookOpenIcon, NewspaperIcon, CpuIcon, ChevronLeftIcon, ChevronRightIcon,
  LoaderIcon, AlertCircleIcon, CheckCircleIcon, UploadIcon, PackageIcon,
} from 'lucide-react'

const sourceIcons: Record<string, React.ReactNode> = {
  arxiv: <BookOpenIcon className="size-4" />,
  github_trending: <GlobeIcon className="size-4" />,
  techcrunch: <NewspaperIcon className="size-4" />,
  mit_news: <CpuIcon className="size-4" />,
  ieee_spectrum: <GlobeIcon className="size-4" />,
}

export default function DataSourceManager() {
  const { t } = useTranslation()
  const [spiders, setSpiders] = useState<SpiderInfo[]>([])
  const [stats, setStats] = useState<CrawlStats | null>(null)
  const [articles, setArticles] = useState<ArticleResponse[]>([])
  const [logs, setLogs] = useState<CrawlLogEntry[]>([])
  const [totalArticles, setTotalArticles] = useState(0)
  const [page, setPage] = useState(1)
  const pageSize = 15
  const [sourceFilter, setSourceFilter] = useState('')
  const [searchText, setSearchText] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'raw' | 'ingested'>('all')
  const [loading, setLoading] = useState(false)
  const [crawling, setCrawling] = useState<Record<string, boolean>>({})
  const [importing, setImporting] = useState<Record<string, boolean>>({})
  const [batchImporting, setBatchImporting] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [sp, st, lg] = await Promise.all([
        getSpiders().catch(() => []),
        getCrawlStats().catch(() => null),
        getCrawlLogs(10).catch(() => []),
      ])
      setSpiders(sp); setStats(st); setLogs(lg)
    } finally { setLoading(false) }
  }, [])

  const loadArticles = useCallback(async () => {
    try {
      const res = await getArticles({
        page, page_size: pageSize,
        source: sourceFilter || undefined,
        search: searchText || undefined,
        status: statusFilter === 'all' ? undefined : statusFilter,
      })
      setArticles(res.articles)
      setTotalArticles(res.total)
    } catch (err) { console.error('Load articles failed:', err) }
  }, [page, pageSize, sourceFilter, searchText, statusFilter])

  useEffect(() => { loadData() }, [loadData])
  useEffect(() => { loadArticles() }, [loadArticles])
  useEffect(() => { return () => { if (pollRef.current) clearInterval(pollRef.current) } }, [])

  const startPolling = useCallback((spiderName: string) => {
    if (pollRef.current) clearInterval(pollRef.current)
    let ticks = 0
    pollRef.current = setInterval(async () => {
      ticks++
      try {
        const statusRes = await getCrawlStatus()
        const running = Object.values(statusRes.tasks).some((t: any) => t.spider === spiderName && t.status === 'running')
        await loadArticles(); await loadData()
        if (!running || ticks > 60) {
          if (pollRef.current) clearInterval(pollRef.current); pollRef.current = null
          setCrawling(p => ({ ...p, [spiderName]: false }))
          if (!running) toast.success(t('dataSource.crawlFinished', { spider: spiderName }))
        }
      } catch { /* keep polling */ }
    }, 3000)
  }, [loadArticles, loadData, t])

  const handleCrawl = async (name: string) => {
    setCrawling(p => ({ ...p, [name]: true }))
    try {
      await triggerCrawl(name, 20)
      toast.success(t('dataSource.crawlStarted', { spider: name }))
      startPolling(name)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err.message)
      setCrawling(p => ({ ...p, [name]: false }))
    }
  }

  const handleImport = async (articleId: string) => {
    setImporting(p => ({ ...p, [articleId]: true }))
    try {
      const res = await importSingleArticle(articleId)
      if (res.status === 'success') { toast.success(t('dataSource.importSuccess', { title: (res.title || '').substring(0, 40) })); await loadArticles(); await loadData() }
      else if (res.status === 'skipped') { toast.info(res.message) }
      else { toast.error(res.message) }
    } catch (err: any) { toast.error(err?.response?.data?.detail || err.message) }
    finally { setImporting(p => ({ ...p, [articleId]: false })) }
  }

  const handleBatchImport = async () => {
    const rawIds = articles.filter(a => a.status === 'raw').map(a => a.id)
    if (rawIds.length === 0) { toast.info(t('dataSource.noRawArticles')); return }
    setBatchImporting(true)
    try {
      const res = await importBatchArticles(rawIds)
      toast.success(t('dataSource.batchImportDone', { success: res.success, failed: res.failed, total: res.total }))
      await loadArticles(); await loadData()
    } catch (err: any) { toast.error(err?.response?.data?.detail || err.message) }
    finally { setBatchImporting(false) }
  }

  const totalPages = Math.ceil(totalArticles / pageSize)
  const rawCount = articles.filter(a => a.status === 'raw').length

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-4">
      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard icon={<DatabaseIcon className="size-5 text-cyan-400" />} value={stats?.total_articles ?? 0} label={t('dataSource.totalArticles')} />
        {stats && Object.entries(stats.by_source).map(([src, cnt]) => (
          <StatCard key={src} icon={sourceIcons[src] || <GlobeIcon className="size-5 text-slate-400" />} value={cnt} label={src} />
        ))}
      </div>

      {/* Spiders */}
      <div className="rounded-lg border border-cyan-400/20 bg-slate-900/60 p-4 backdrop-blur">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-cyan-50">{t('dataSource.spiders')}</h3>
            <p className="text-xs text-slate-400">{t('dataSource.spidersDesc')}</p>
          </div>
          <Button variant="ghost" size="icon" onClick={loadData} className="text-cyan-300 hover:bg-cyan-500/15">
            <RefreshCwIcon className={`size-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2 lg:grid-cols-3">
          {spiders.map(spider => (
            <div key={spider.name} className="flex items-center justify-between rounded-lg border border-slate-700/50 bg-slate-800/40 p-3">
              <div className="flex items-center gap-3">
                <div className="flex size-8 items-center justify-center rounded-md bg-slate-700/60">
                  {sourceIcons[spider.name] || <GlobeIcon className="size-4 text-slate-400" />}
                </div>
                <div>
                  <p className="text-sm font-medium text-cyan-50">{spider.name}</p>
                  <p className="text-xs text-slate-400">{spider.description}</p>
                </div>
              </div>
              <Button variant="ghost" size="icon" onClick={() => handleCrawl(spider.name)}
                disabled={crawling[spider.name] || spider.is_running}
                className="text-emerald-400 hover:bg-emerald-500/15 disabled:opacity-50">
                {crawling[spider.name] ? <LoaderIcon className="size-4 animate-spin" /> : <PlayIcon className="size-4" />}
              </Button>
            </div>
          ))}
        </div>
      </div>

      {/* Logs */}
      {logs.length > 0 && (
        <div className="rounded-lg border border-cyan-400/20 bg-slate-900/60 p-4 backdrop-blur">
          <h3 className="mb-2 text-base font-semibold text-cyan-50">{t('dataSource.recentLogs')}</h3>
          <div className="space-y-1.5">
            {logs.slice(0, 5).map((log, i) => (
              <div key={i} className="flex items-center justify-between rounded border border-slate-700/30 bg-slate-800/30 px-3 py-1.5 text-xs">
                <div className="flex items-center gap-2">
                  {log.status === 'success' ? <CheckCircleIcon className="size-3.5 text-emerald-400" /> : <AlertCircleIcon className="size-3.5 text-red-400" />}
                  <span className="font-medium text-cyan-100">{log.spider}</span>
                </div>
                <div className="flex items-center gap-3 text-slate-400">
                  <span>{log.new_items}/{log.total_items} {t('dataSource.newItems')}</span>
                  <span>{new Date(log.finished_at).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Articles */}
      <div className="flex-1 rounded-lg border border-cyan-400/20 bg-slate-900/60 p-4 backdrop-blur">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h3 className="text-base font-semibold text-cyan-50">{t('dataSource.articles')}</h3>
            {rawCount > 0 && statusFilter !== 'ingested' && (
              <Button onClick={handleBatchImport} disabled={batchImporting}
                className="h-7 bg-gradient-to-r from-emerald-600 to-cyan-600 px-3 text-[11px] text-white hover:from-emerald-500 hover:to-cyan-500 disabled:opacity-50">
                {batchImporting
                  ? <><LoaderIcon className="mr-1 size-3 animate-spin" />{t('dataSource.importing')}</>
                  : <><PackageIcon className="mr-1 size-3" />{t('dataSource.importAll', { count: rawCount })}</>}
              </Button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <SearchIcon className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-slate-400" />
              <Input className="h-8 w-48 border-slate-700/50 bg-slate-800/50 pl-8 text-xs text-cyan-50 placeholder:text-slate-500"
                placeholder={t('dataSource.searchPlaceholder')} value={searchText}
                onChange={e => { setSearchText(e.target.value); setPage(1) }} />
            </div>
            <Select value={sourceFilter || 'all'} onValueChange={v => { setSourceFilter(v === 'all' ? '' : v); setPage(1) }}>
              <SelectTrigger className="h-8 w-36 border-slate-700/50 bg-slate-800/50 text-xs text-cyan-50">
                <SelectValue placeholder={t('dataSource.allSources')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('dataSource.allSources')}</SelectItem>
                <SelectItem value="arxiv">ArXiv</SelectItem>
                <SelectItem value="github_trending">GitHub</SelectItem>
                <SelectItem value="techcrunch">TechCrunch</SelectItem>
                <SelectItem value="mit_news">MIT News</SelectItem>
                <SelectItem value="ieee_spectrum">IEEE</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="ghost" size="icon" onClick={loadArticles} className="text-cyan-300 hover:bg-cyan-500/15">
              <RefreshCwIcon className="size-4" />
            </Button>
          </div>
        </div>

        {/* Status Filter Tabs */}
        <div className="mb-3 flex gap-2">
          <Button variant={statusFilter === 'all' ? 'default' : 'ghost'} size="sm"
            onClick={() => { setStatusFilter('all'); setPage(1) }}
            className={`h-7 text-xs ${statusFilter === 'all' ? 'bg-cyan-600 text-white' : 'text-slate-300'}`}>
            {t('dataSource.allArticles')}
          </Button>
          <Button variant={statusFilter === 'raw' ? 'default' : 'ghost'} size="sm"
            onClick={() => { setStatusFilter('raw'); setPage(1) }}
            className={`h-7 text-xs ${statusFilter === 'raw' ? 'bg-yellow-600 text-white' : 'text-slate-300'}`}>
            {t('dataSource.pendingArticles')}
          </Button>
          <Button variant={statusFilter === 'ingested' ? 'default' : 'ghost'} size="sm"
            onClick={() => { setStatusFilter('ingested'); setPage(1) }}
            className={`h-7 text-xs ${statusFilter === 'ingested' ? 'bg-emerald-600 text-white' : 'text-slate-300'}`}>
            {t('dataSource.importedArticles')}
          </Button>
        </div>

        <div className="space-y-2">
          {articles.map(article => (
            <div key={article.id} className="rounded-lg border border-slate-700/30 bg-slate-800/30 p-3 transition-colors hover:border-cyan-400/30">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <a href={article.url} target="_blank" rel="noopener noreferrer"
                    className="text-sm font-medium text-cyan-100 hover:text-cyan-300 hover:underline">{article.title}</a>
                  {article.summary && <p className="mt-1 line-clamp-2 text-xs text-slate-400">{article.summary}</p>}
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className="border-slate-600/50 text-[10px] text-slate-300">{article.source}</Badge>
                    <Badge variant="outline" className={`text-[10px] ${article.status === 'ingested' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-400/30' : 'bg-yellow-500/20 text-yellow-300 border-yellow-400/30'}`}>
                      {article.status === 'ingested' ? 'Imported' : 'Pending'}
                    </Badge>
                    {article.tags.slice(0, 3).map(tag => (
                      <Badge key={tag} variant="outline" className="border-cyan-400/20 text-[10px] text-cyan-300/70">{tag}</Badge>
                    ))}
                    <span className="text-[10px] text-slate-500">{new Date(article.published_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="shrink-0">
                  {article.status === 'raw' ? (
                    <Button variant="ghost" size="icon" onClick={() => handleImport(article.id)}
                      disabled={importing[article.id]}
                      className="size-8 text-emerald-400 hover:bg-emerald-500/15 disabled:opacity-50"
                      tooltip={t('dataSource.importToKG')}>
                      {importing[article.id] ? <LoaderIcon className="size-3.5 animate-spin" /> : <UploadIcon className="size-3.5" />}
                    </Button>
                  ) : article.status === 'ingested' ? (
                    <div className="flex size-8 items-center justify-center"><CheckCircleIcon className="size-4 text-emerald-400" /></div>
                  ) : null}
                </div>
              </div>
            </div>
          ))}
          {articles.length === 0 && <div className="py-12 text-center text-sm text-slate-400">{t('dataSource.noArticles')}</div>}
        </div>

        {totalPages > 1 && (
          <div className="mt-4 flex items-center justify-between">
            <span className="text-xs text-slate-400">{(page - 1) * pageSize + 1}-{Math.min(page * pageSize, totalArticles)} / {totalArticles}</span>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon" disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="size-7 text-cyan-300">
                <ChevronLeftIcon className="size-4" />
              </Button>
              <span className="px-2 text-xs text-slate-300">{page} / {totalPages}</span>
              <Button variant="ghost" size="icon" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} className="size-7 text-cyan-300">
                <ChevronRightIcon className="size-4" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ icon, value, label }: { icon: React.ReactNode; value: number; label: string }) {
  return (
    <div className="rounded-lg border border-cyan-400/20 bg-slate-900/60 p-4 backdrop-blur">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-cyan-500/20">{icon}</div>
        <div>
          <p className="text-2xl font-bold text-cyan-50">{value}</p>
          <p className="text-xs capitalize text-slate-400">{label}</p>
        </div>
      </div>
    </div>
  )
}
