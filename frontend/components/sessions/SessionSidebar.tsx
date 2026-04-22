'use client'

import { useState, useMemo } from 'react'
import { Search, FileText, Play, CheckCircle2, XCircle, Clock, ChevronRight, Trash2 } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { parseBackendDate } from '@/lib/dateUtils'

export interface SessionItem {
  task_id: string
  task: string
  status: string
  created_at: string | null
  current_stage: number | null
  progress_percent: number
}

const STAGE_NAMES: Record<number, string> = {
  1: 'Setup',
  2: 'News Discovery',
  3: 'Deep Analysis',
  4: 'Final Report',
}

function getStatusConfig(status: string, progress: number) {
  if (status === 'executing' || status === 'running') {
    return {
      icon: Play,
      label: 'Running',
      color: 'var(--mars-color-warning)',
      bgColor: 'rgba(234, 179, 8, 0.1)',
      borderColor: 'rgba(234, 179, 8, 0.3)',
      pulse: true,
    }
  }
  if (status === 'completed' || progress >= 100) {
    return {
      icon: CheckCircle2,
      label: 'Completed',
      color: 'var(--mars-color-success)',
      bgColor: 'rgba(34, 197, 94, 0.1)',
      borderColor: 'rgba(34, 197, 94, 0.3)',
      pulse: false,
    }
  }
  if (status === 'failed') {
    return {
      icon: XCircle,
      label: 'Failed',
      color: 'var(--mars-color-danger)',
      bgColor: 'rgba(239, 68, 68, 0.1)',
      borderColor: 'rgba(239, 68, 68, 0.3)',
      pulse: false,
    }
  }
  return {
    icon: Clock,
    label: 'In Progress',
    color: 'var(--mars-color-primary)',
    bgColor: 'rgba(59, 130, 246, 0.1)',
    borderColor: 'rgba(59, 130, 246, 0.3)',
    pulse: false,
  }
}

interface SessionSidebarProps {
  sessions: SessionItem[]
  activeSessionId: string | null
  onSelectSession: (taskId: string) => void
  onDeleteSession: (taskId: string) => void
  collapsed?: boolean
}

export default function SessionSidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onDeleteSession,
  collapsed = false,
}: SessionSidebarProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [filterStatus, setFilterStatus] = useState<'all' | 'running' | 'completed' | 'failed'>('all')

  const filteredSessions = useMemo(() => {
    return sessions.filter((s) => {
      const matchesSearch = !searchQuery ||
        (s.task || '').toLowerCase().includes(searchQuery.toLowerCase())
      const matchesFilter =
        filterStatus === 'all' ||
        (filterStatus === 'running' && (s.status === 'executing' || s.status === 'running' || s.status === 'draft' || s.status === 'planning')) ||
        (filterStatus === 'completed' && (s.status === 'completed' || s.progress_percent >= 100)) ||
        (filterStatus === 'failed' && s.status === 'failed')
      return matchesSearch && matchesFilter
    })
  }, [sessions, searchQuery, filterStatus])

  const statusCounts = useMemo(() => {
    const running = sessions.filter(s => s.status === 'executing' || s.status === 'running' || s.status === 'draft' || s.status === 'planning').length
    const completed = sessions.filter(s => s.status === 'completed' || s.progress_percent >= 100).length
    const failed = sessions.filter(s => s.status === 'failed').length
    return { all: sessions.length, running, completed, failed }
  }, [sessions])

  if (collapsed) return null

  return (
    <div
      className="h-full flex flex-col border-l"
      style={{
        width: '280px',
        minWidth: '280px',
        backgroundColor: 'var(--mars-color-surface)',
        borderColor: 'var(--mars-color-border)',
      }}
    >
      {/* Header */}
      <div
        className="flex-shrink-0 px-4 py-3 border-b"
        style={{ borderColor: 'var(--mars-color-border)' }}
      >
        <h3
          className="text-xs font-semibold uppercase tracking-wider mb-2.5"
          style={{ color: 'var(--mars-color-text-tertiary)' }}
        >
          Sessions
        </h3>

        {/* Search */}
        <div
          className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs"
          style={{
            backgroundColor: 'var(--mars-color-surface-sunken)',
            border: '1px solid var(--mars-color-border)',
          }}
        >
          <Search className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--mars-color-text-tertiary)' }} />
          <input
            type="text"
            placeholder="Search sessions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 bg-transparent outline-none text-xs"
            style={{ color: 'var(--mars-color-text)' }}
          />
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-1 mt-2.5">
          {(['all', 'running', 'completed', 'failed'] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => setFilterStatus(filter)}
              className="px-2 py-1 rounded text-[10px] font-medium capitalize transition-colors"
              style={{
                backgroundColor: filterStatus === filter
                  ? 'var(--mars-color-primary-subtle)'
                  : 'transparent',
                color: filterStatus === filter
                  ? 'var(--mars-color-primary)'
                  : 'var(--mars-color-text-tertiary)',
              }}
            >
              {filter} {statusCounts[filter] > 0 && `(${statusCounts[filter]})`}
            </button>
          ))}
        </div>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-y-auto py-1.5">
        {filteredSessions.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <FileText className="w-8 h-8 mx-auto mb-2" style={{ color: 'var(--mars-color-text-disabled)' }} />
            <p className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
              {searchQuery ? 'No matching sessions' : 'No sessions yet'}
            </p>
          </div>
        ) : (
          filteredSessions.map((session) => {
            const statusCfg = getStatusConfig(session.status, session.progress_percent)
            const StatusIcon = statusCfg.icon
            const isActive = session.task_id === activeSessionId

            return (
              <div
                key={session.task_id}
                role="button"
                tabIndex={0}
                onClick={() => onSelectSession(session.task_id)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelectSession(session.task_id); } }}
                className="w-full text-left px-3 py-2.5 mx-1.5 mb-0.5 rounded-lg transition-all duration-150 group cursor-pointer"
                style={{
                  width: 'calc(100% - 12px)',
                  backgroundColor: isActive
                    ? 'var(--mars-color-primary-subtle)'
                    : 'transparent',
                  borderLeft: isActive ? '3px solid var(--mars-color-primary)' : '3px solid transparent',
                }}
              >
                <div className="flex items-start gap-2.5">
                  <div
                    className={`flex-shrink-0 w-6 h-6 rounded-md flex items-center justify-center mt-0.5 ${statusCfg.pulse ? 'animate-pulse' : ''}`}
                    style={{ backgroundColor: statusCfg.bgColor }}
                  >
                    <StatusIcon className="w-3.5 h-3.5" style={{ color: statusCfg.color }} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <p
                      className="text-xs font-medium truncate leading-tight"
                      style={{ color: isActive ? 'var(--mars-color-primary)' : 'var(--mars-color-text)' }}
                    >
                      {session.task || 'Untitled Analysis'}
                    </p>
                    <p
                      className="text-[10px] mt-0.5 truncate"
                      style={{ color: 'var(--mars-color-text-tertiary)' }}
                    >
                      {session.current_stage
                        ? `Stage ${session.current_stage}: ${STAGE_NAMES[session.current_stage] || ''}`
                        : 'Setup'}
                    </p>
                    <div className="flex items-center gap-2 mt-1.5">
                      <div
                        className="flex-1 h-1 rounded-full overflow-hidden"
                        style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
                      >
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${Math.max(3, session.progress_percent)}%`,
                            background: statusCfg.color,
                            opacity: 0.8,
                          }}
                        />
                      </div>
                      <span
                        className="text-[9px] flex-shrink-0 tabular-nums"
                        style={{ color: 'var(--mars-color-text-tertiary)' }}
                      >
                        {Math.round(session.progress_percent)}%
                      </span>
                    </div>
                    {(() => {
                      const d = parseBackendDate(session.created_at)
                      return d ? (
                        <p
                          className="text-[9px] mt-1"
                          style={{ color: 'var(--mars-color-text-disabled)' }}
                        >
                          {formatDistanceToNow(d, { addSuffix: true })}
                        </p>
                      ) : null
                    })()}
                  </div>

                  <div className="flex-shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <ChevronRight className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-text-tertiary)' }} />
                  </div>
                </div>

                <div className="flex justify-end mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onDeleteSession(session.task_id)
                    }}
                    className="p-1 rounded transition-colors hover:bg-[rgba(239,68,68,0.15)]"
                    title="Delete session"
                  >
                    <Trash2 className="w-3 h-3" style={{ color: 'var(--mars-color-text-tertiary)' }} />
                  </button>
                </div>
              </div>
            )
          })
        )}
      </div>

      <div
        className="flex-shrink-0 px-4 py-2.5 border-t text-center"
        style={{ borderColor: 'var(--mars-color-border)' }}
      >
        <p className="text-[10px]" style={{ color: 'var(--mars-color-text-disabled)' }}>
          {sessions.length} session{sessions.length !== 1 ? 's' : ''} total
        </p>
      </div>
    </div>
  )
}
