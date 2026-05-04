import { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  analyzeTrends, askQuestion, askQuestionStream,
  type AnalysisMessage, type TrendAnalysisResponse,
} from '@/api/platform'
import Button from '@/components/ui/Button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select'
import {
  TrendingUpIcon, MessageSquareIcon, SendIcon, LoaderIcon, SparklesIcon,
  TrashIcon, BotIcon, UserIcon,
} from 'lucide-react'

type ChatMsg = { role: 'user' | 'assistant'; content: string }

export default function SmartAnalysis() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<'trends' | 'qa'>('trends')

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Sub-tabs */}
      <div className="flex items-center gap-1 border-b border-slate-700/50 bg-slate-950/40 px-4 py-2">
        <SubTab active={activeTab === 'trends'} onClick={() => setActiveTab('trends')}
          icon={<TrendingUpIcon className="size-3.5" />} label={t('analysis.trends')} />
        <SubTab active={activeTab === 'qa'} onClick={() => setActiveTab('qa')}
          icon={<MessageSquareIcon className="size-3.5" />} label={t('analysis.qa')} />
      </div>

      <div className="flex-1 overflow-hidden">
        {activeTab === 'trends' ? <TrendsPanel /> : <QAPanel />}
      </div>
    </div>
  )
}

function SubTab({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button onClick={onClick} className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
      active ? 'bg-cyan-400/20 text-cyan-100 shadow-[0_0_12px_rgba(0,255,255,0.2)]' : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
    }`}>
      {icon}{label}
    </button>
  )
}

function TrendsPanel() {
  const { t } = useTranslation()
  const [source, setSource] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<TrendAnalysisResponse | null>(null)

  const handleAnalyze = async () => {
    setLoading(true)
    try {
      const res = await analyzeTrends(source || undefined, 20)
      setResult(res)
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err.message
      toast.error(msg)
    } finally { setLoading(false) }
  }

  return (
    <div className="flex h-full flex-col overflow-auto p-4">
      <div className="mb-4 flex items-center gap-3">
        <Select value={source || 'all'} onValueChange={v => setSource(v === 'all' ? '' : v)}>
          <SelectTrigger className="h-9 w-40 border-slate-700/50 bg-slate-800/50 text-xs text-cyan-50">
            <SelectValue placeholder={t('analysis.allSources')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('analysis.allSources')}</SelectItem>
            <SelectItem value="arxiv">ArXiv</SelectItem>
            <SelectItem value="github_trending">GitHub</SelectItem>
            <SelectItem value="techcrunch">TechCrunch</SelectItem>
            <SelectItem value="mit_news">MIT News</SelectItem>
          </SelectContent>
        </Select>
        <Button onClick={handleAnalyze} disabled={loading}
          className="h-9 bg-gradient-to-r from-cyan-600 to-blue-600 px-4 text-xs text-white hover:from-cyan-500 hover:to-blue-500">
          {loading ? <LoaderIcon className="mr-1.5 size-3.5 animate-spin" /> : <SparklesIcon className="mr-1.5 size-3.5" />}
          {t('analysis.analyze')}
        </Button>
      </div>

      {result && (
        <div className="rounded-lg border border-cyan-400/20 bg-slate-900/60 p-5 backdrop-blur">
          <div className="mb-3 flex items-center gap-2">
            <TrendingUpIcon className="size-4 text-cyan-400" />
            <span className="text-sm font-medium text-cyan-50">{t('analysis.trendResult')}</span>
            <span className="text-xs text-slate-400">({result.article_count} {t('analysis.articlesAnalyzed')})</span>
          </div>
          <div className="prose prose-sm prose-invert max-w-none text-slate-200 prose-headings:text-cyan-100 prose-strong:text-cyan-200 prose-li:text-slate-300">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.analysis}</ReactMarkdown>
          </div>
        </div>
      )}

      {!result && !loading && (
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center">
            <SparklesIcon className="mx-auto size-12 text-slate-600" />
            <p className="mt-3 text-sm text-slate-400">{t('analysis.trendHint')}</p>
          </div>
        </div>
      )}
    </div>
  )
}

function QAPanel() {
  const { t } = useTranslation()
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [source, setSource] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setLoading(true)

    const history: AnalysisMessage[] = messages.map(m => ({ role: m.role, content: m.content }))
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])

    try {
      await askQuestionStream(q, (chunk) => {
        setMessages(prev => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last.role === 'assistant') {
            updated[updated.length - 1] = { ...last, content: last.content + chunk }
          }
          return updated
        })
      }, source || undefined, history)
    } catch (err: any) {
      try {
        const res = await askQuestion(q, source || undefined, history)
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'assistant', content: res.answer }
          return updated
        })
      } catch (fallbackErr: any) {
        const msg = fallbackErr?.response?.data?.detail || fallbackErr.message
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'assistant', content: `Error: ${msg}` }
          return updated
        })
      }
    } finally { setLoading(false) }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Filter */}
      <div className="flex items-center gap-2 border-b border-slate-700/30 px-4 py-2">
        <Select value={source || 'all'} onValueChange={v => setSource(v === 'all' ? '' : v)}>
          <SelectTrigger className="h-7 w-32 border-slate-700/50 bg-slate-800/50 text-[11px] text-cyan-50">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('analysis.allSources')}</SelectItem>
            <SelectItem value="arxiv">ArXiv</SelectItem>
            <SelectItem value="github_trending">GitHub</SelectItem>
            <SelectItem value="techcrunch">TechCrunch</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="ghost" size="icon" onClick={() => setMessages([])} className="size-7 text-slate-400 hover:text-red-400">
          <TrashIcon className="size-3.5" />
        </Button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-auto p-4">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <BotIcon className="mx-auto size-12 text-slate-600" />
              <p className="mt-3 text-sm text-slate-400">{t('analysis.qaHint')}</p>
            </div>
          </div>
        )}
        <div className="space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
              {msg.role === 'assistant' && (
                <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-cyan-500/20">
                  <BotIcon className="size-4 text-cyan-400" />
                </div>
              )}
              <div className={`max-w-[80%] rounded-lg px-4 py-2.5 text-sm ${
                msg.role === 'user'
                  ? 'bg-cyan-600/30 text-cyan-50'
                  : 'border border-slate-700/30 bg-slate-800/50 text-slate-200'
              }`}>
                {msg.role === 'assistant' ? (
                  <div className="prose prose-sm prose-invert max-w-none prose-headings:text-cyan-100 prose-strong:text-cyan-200">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content || '...'}</ReactMarkdown>
                  </div>
                ) : msg.content}
              </div>
              {msg.role === 'user' && (
                <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-slate-700/50">
                  <UserIcon className="size-4 text-slate-300" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-slate-700/50 bg-slate-950/40 p-3">
        <div className="flex items-center gap-2">
          <input
            className="flex-1 rounded-lg border border-slate-700/50 bg-slate-800/50 px-3 py-2 text-sm text-cyan-50 placeholder:text-slate-500 focus:border-cyan-400/40 focus:outline-none"
            placeholder={t('analysis.qaPlaceholder')}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
            disabled={loading}
          />
          <Button onClick={handleSend} disabled={loading || !input.trim()}
            className="h-9 bg-gradient-to-r from-cyan-600 to-blue-600 px-3 text-white hover:from-cyan-500 hover:to-blue-500 disabled:opacity-50">
            {loading ? <LoaderIcon className="size-4 animate-spin" /> : <SendIcon className="size-4" />}
          </Button>
        </div>
      </div>
    </div>
  )
}
