import Button from '@/components/ui/Button'
import { SiteInfo, webuiPrefix } from '@/lib/constants'
import AppSettings from '@/components/AppSettings'
import { TabsList, TabsTrigger } from '@/components/ui/Tabs'
import { useSettingsStore } from '@/stores/settings'
import { useAuthStore } from '@/stores/state'
import { cn } from '@/lib/utils'
import { useTranslation } from 'react-i18next'
import { navigationService } from '@/services/navigation'
import { ZapIcon, LogOutIcon } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/Tooltip'

interface NavigationTabProps {
  value: string
  currentTab: string
  children: React.ReactNode
}

function NavigationTab({ value, currentTab, children }: NavigationTabProps) {
  return (
    <TabsTrigger
      value={value}
      className={cn(
        'cursor-pointer px-3 py-1.5 text-[12px] tracking-wide uppercase transition-all duration-300 border border-transparent data-[state=active]:shadow-[0_0_20px_rgba(0,255,255,0.35)]',
        currentTab === value
          ? '!bg-cyan-400/25 !text-cyan-100 !border-cyan-300/70'
          : 'bg-slate-900/35 text-slate-200 hover:bg-cyan-500/15 hover:text-cyan-100 hover:border-cyan-300/30'
      )}
    >
      {children}
    </TabsTrigger>
  )
}

function TabsNavigation() {
  const currentTab = useSettingsStore.use.currentTab()
  const { t } = useTranslation()

  return (
    <div className="flex h-8 self-center">
      <TabsList className="h-full gap-2 bg-slate-950/35 border border-cyan-400/25 backdrop-blur-xl shadow-[0_0_24px_rgba(0,255,255,0.18)]">
        <NavigationTab value="documents" currentTab={currentTab}>
          {t('header.documents')}
        </NavigationTab>
        <NavigationTab value="knowledge-graph" currentTab={currentTab}>
          {t('header.knowledgeGraph')}
        </NavigationTab>
        <NavigationTab value="retrieval" currentTab={currentTab}>
          {t('header.retrieval')}
        </NavigationTab>
        <NavigationTab value="data-sources" currentTab={currentTab}>
          {t('header.dataSources')}
        </NavigationTab>
        <NavigationTab value="analysis" currentTab={currentTab}>
          {t('header.analysis')}
        </NavigationTab>
      </TabsList>
    </div>
  )
}

export default function SiteHeader() {
  const { t } = useTranslation()
  const { isGuestMode, username, webuiTitle, webuiDescription } = useAuthStore()

  const handleLogout = () => {
    navigationService.navigateToLogin();
  }

  return (
    <header className="border-cyan-400/25 bg-slate-950/55 supports-[backdrop-filter]:bg-slate-950/45 sticky top-0 z-50 flex h-11 w-full border-b px-4 backdrop-blur-xl shadow-[0_8px_32px_rgba(4,10,30,0.65)]">
      <div className="min-w-[200px] w-auto flex items-center">
        <a href={webuiPrefix} className="flex items-center gap-2">
          <ZapIcon className="size-4 text-cyan-300 drop-shadow-[0_0_8px_rgba(45,212,191,0.9)]" aria-hidden="true" />
          <span className="font-bold md:inline-block text-cyan-50 tracking-wide">{SiteInfo.name}</span>
        </a>
        {webuiTitle && (
          <div className="flex items-center">
            <span className="mx-1 text-xs text-cyan-300/70 dark:text-cyan-200/70">|</span>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="font-medium text-sm cursor-default text-cyan-100">
                    {webuiTitle}
                  </span>
                </TooltipTrigger>
                {webuiDescription && (
                  <TooltipContent side="bottom">
                    {webuiDescription}
                  </TooltipContent>
                )}
              </Tooltip>
            </TooltipProvider>
          </div>
        )}
      </div>

      <div className="flex h-10 flex-1 items-center justify-center">
        <TabsNavigation />
      </div>

      <nav className="w-[200px] flex items-center justify-end">
        <div className="flex items-center gap-2">
          <AppSettings />
          {!isGuestMode && (
            <Button
              variant="ghost"
              size="icon"
              side="bottom"
              tooltip={`${t('header.logout')} (${username})`}
              onClick={handleLogout}
              className="text-cyan-100/80 hover:bg-cyan-400/15 hover:text-cyan-100"
            >
              <LogOutIcon className="size-4" aria-hidden="true" />
            </Button>
          )}
        </div>
      </nav>
    </header>
  )
}
