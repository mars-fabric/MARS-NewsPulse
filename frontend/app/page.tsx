'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { TrendingUp, Sparkles, Search, FileText, PanelRightClose, PanelRightOpen } from 'lucide-react'
import TopBar from '@/components/layout/TopBar'
import SessionSidebar from '@/components/sessions/SessionSidebar'
import type { SessionItem } from '@/components/sessions/SessionSidebar'
import NewsPulseTask from '@/components/tasks/NewsPulseTask'
import { getApiUrl } from '@/lib/config'

export default function Home() {
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [showTask, setShowTask] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Auto-collapse on small screens
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)')
    if (mq.matches) setSidebarOpen(false)
    const handler = (e: MediaQueryListEvent) => setSidebarOpen(!e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  const fetchSessions = useCallback(async () => {
    try {
      const resp = await fetch(getApiUrl('/api/newspulse/recent?include_all=true'))
      if (resp.ok) {
        const data: SessionItem[] = await resp.json()
        setSessions(data)
      }
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    fetchSessions()
    pollRef.current = setInterval(fetchSessions, 10000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [fetchSessions])

  useEffect(() => {
    if (!showTask) fetchSessions()
  }, [showTask, fetchSessions])

  const handleNewSession = useCallback(() => {
    setActiveTaskId(null)
    setShowTask(true)
  }, [])

  const handleSelectSession = useCallback((taskId: string) => {
    setActiveTaskId(taskId)
    setShowTask(true)
  }, [])

  const handleBack = useCallback(() => {
    setShowTask(false)
    setActiveTaskId(null)
  }, [])

  const handleDeleteSession = useCallback(async (taskId: string) => {
    if (!confirm('Delete this session? This will remove all data and files.')) return
    try {
      await fetch(getApiUrl(`/api/newspulse/${taskId}`), { method: 'DELETE' })
      setSessions(prev => prev.filter(s => s.task_id !== taskId))
      if (activeTaskId === taskId) {
        setShowTask(false)
        setActiveTaskId(null)
      }
    } catch {
      // ignore
    }
  }, [activeTaskId])

  return (
    <div className="flex flex-col h-full">
      <TopBar onNewSession={handleNewSession} />

      <div className="flex-1 flex min-h-0 relative">
        <div className="flex-1 min-h-0 overflow-auto relative">
          {showTask ? (
            <NewsPulseTask
              key={activeTaskId || 'new'}
              onBack={handleBack}
              resumeTaskId={activeTaskId}
            />
          ) : (
            <WelcomeView onNewSession={handleNewSession} />
          )}

          <button
            onClick={() => setSidebarOpen(prev => !prev)}
            className="absolute top-3 right-3 p-1.5 rounded-lg transition-all duration-150
              hover:bg-[var(--mars-color-surface-overlay)] z-10"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
            title={sidebarOpen ? 'Hide sessions' : 'Show sessions'}
          >
            {sidebarOpen ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
          </button>
        </div>

        <div
          className="transition-all duration-300 ease-in-out overflow-hidden"
          style={{
            width: sidebarOpen ? '280px' : '0px',
            minWidth: sidebarOpen ? '280px' : '0px',
          }}
        >
          <SessionSidebar
            sessions={sessions}
            activeSessionId={activeTaskId}
            onSelectSession={handleSelectSession}
            onDeleteSession={handleDeleteSession}
          />
        </div>
      </div>
    </div>
  )
}

interface WelcomeViewProps {
  onNewSession: () => void
}

function WelcomeView({ onNewSession }: WelcomeViewProps) {
  return (
    <div className="h-full flex items-center justify-center p-8">
      <div className="max-w-lg w-full text-center">
        {/* Hero icon */}
        <div
          className="w-20 h-20 rounded-2xl mx-auto mb-6 flex items-center justify-center"
          style={{
            background: 'linear-gradient(135deg, #10b981 0%, #14b8a6 50%, #0d9488 100%)',
            boxShadow: '0 8px 32px rgba(20, 184, 166, 0.3)',
          }}
        >
          <TrendingUp className="w-10 h-10 text-white" />
        </div>

        <h2
          className="text-2xl font-bold mb-2"
          style={{ color: 'var(--mars-color-text)' }}
        >
          NewsPulse
        </h2>
        <p
          className="text-sm mb-8"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          Generate executive industry news &amp; sentiment reports through AI-powered web search and analysis
        </p>

        <button
          onClick={onNewSession}
          className="inline-flex items-center gap-3 px-6 py-3 rounded-xl text-sm font-semibold
            text-white transition-all duration-200 hover:shadow-xl hover:scale-[1.02] active:scale-[0.98]"
          style={{
            background: 'linear-gradient(135deg, #10b981, #14b8a6)',
            boxShadow: '0 4px 16px rgba(20, 184, 166, 0.3)',
          }}
        >
          <TrendingUp className="w-5 h-5" />
          Start New Analysis
        </button>

        <div className="grid grid-cols-3 gap-4 mt-10">
          {[
            { icon: Search, label: 'Web Search', desc: 'DuckDuckGo discovery' },
            { icon: Sparkles, label: 'AI Stages', desc: '4-phase pipeline' },
            { icon: FileText, label: 'PDF Report', desc: 'Executive ready' },
          ].map((feature) => (
            <div
              key={feature.label}
              className="p-3 rounded-xl"
              style={{
                backgroundColor: 'var(--mars-color-surface)',
                border: '1px solid var(--mars-color-border)',
              }}
            >
              <feature.icon
                className="w-5 h-5 mx-auto mb-1.5"
                style={{ color: 'var(--mars-color-text-tertiary)' }}
              />
              <p className="text-xs font-medium" style={{ color: 'var(--mars-color-text)' }}>
                {feature.label}
              </p>
              <p className="text-[10px]" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                {feature.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
