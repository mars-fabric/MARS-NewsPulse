'use client'

import { useState, useCallback, useEffect } from 'react'
import { TrendingUp, ArrowRight, X } from 'lucide-react'
import NewsPulseTask from '@/components/tasks/NewsPulseTask'
import { getApiUrl } from '@/lib/config'

interface RecentTask {
  task_id: string
  task: string
  status: string
  created_at: string | null
  current_stage: number | null
  progress_percent: number
}

const STAGE_NAMES: Record<number, string> = {
  1: 'Setup',
  2: 'Initial Research',
  3: 'Review & Refine',
  4: 'Final Report',
}

export default function Home() {
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [showTask, setShowTask] = useState(false)
  const [recentTasks, setRecentTasks] = useState<RecentTask[]>([])

  const fetchRecentTasks = useCallback(async () => {
    try {
      const resp = await fetch(getApiUrl('/api/newspulse/recent'))
      if (resp.ok) {
        const data: RecentTask[] = await resp.json()
        setRecentTasks(data)
      }
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    if (!showTask) {
      fetchRecentTasks()
    }
  }, [showTask, fetchRecentTasks])

  const handleResume = useCallback((taskId: string) => {
    setActiveTaskId(taskId)
    setShowTask(true)
  }, [])

  const handleNew = useCallback(() => {
    setActiveTaskId(null)
    setShowTask(true)
  }, [])

  const handleBack = useCallback(() => {
    setShowTask(false)
    setActiveTaskId(null)
  }, [])

  const handleDelete = useCallback(async (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this task? This will remove all data and files.')) return
    try {
      await fetch(getApiUrl(`/api/newspulse/${taskId}`), { method: 'DELETE' })
      setRecentTasks(prev => prev.filter(t => t.task_id !== taskId))
    } catch {
      // ignore
    }
  }, [])

  if (showTask) {
    return (
      <NewsPulseTask
        onBack={handleBack}
        resumeTaskId={activeTaskId}
      />
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-8">
        <h2
          className="text-2xl font-semibold"
          style={{ color: 'var(--mars-color-text)' }}
        >
          NewsPulse
        </h2>
        <p
          className="text-sm mt-1"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          Industry News & Sentiment Analysis
        </p>
      </div>

      {/* New Task Button */}
      <button
        onClick={handleNew}
        className="w-full mb-6 flex items-center gap-4 p-4 rounded-lg border-2 border-dashed transition-colors hover:border-[var(--mars-color-primary)]"
        style={{
          borderColor: 'var(--mars-color-border)',
          backgroundColor: 'var(--mars-color-surface)',
        }}
      >
        <div
          className="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center"
          style={{ background: 'linear-gradient(135deg, #10b981, #14b8a6)' }}
        >
          <TrendingUp className="w-5 h-5 text-white" />
        </div>
        <div className="text-left">
          <p
            className="text-sm font-medium"
            style={{ color: 'var(--mars-color-text)' }}
          >
            New Analysis
          </p>
          <p
            className="text-xs"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          >
            Start a new industry news research and sentiment analysis
          </p>
        </div>
      </button>

      {/* Recent Tasks */}
      {recentTasks.length > 0 && (
        <div className="space-y-2">
          <h3
            className="text-xs font-medium uppercase tracking-wider mb-3"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          >
            Recent Tasks
          </h3>
          {recentTasks.map((task) => (
            <button
              key={task.task_id}
              onClick={() => handleResume(task.task_id)}
              className="w-full flex items-center gap-3 p-3 rounded-lg border transition-colors hover:border-[var(--mars-color-primary)]"
              style={{
                borderColor: 'var(--mars-color-border)',
                backgroundColor: 'var(--mars-color-surface)',
              }}
            >
              <div
                className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center"
                style={{ background: 'linear-gradient(135deg, #10b981, #14b8a6)' }}
              >
                <TrendingUp className="w-4 h-4 text-white" />
              </div>
              <div className="flex-1 text-left min-w-0">
                <p
                  className="text-sm font-medium truncate"
                  style={{ color: 'var(--mars-color-text)' }}
                >
                  {task.task || 'Untitled Analysis'}
                </p>
                <p
                  className="text-xs"
                  style={{ color: 'var(--mars-color-text-tertiary)' }}
                >
                  {task.current_stage
                    ? `Stage ${task.current_stage}: ${STAGE_NAMES[task.current_stage] || ''}`
                    : 'Starting...'}
                  {' '}&middot;{' '}
                  {Math.round(task.progress_percent)}% complete
                </p>
              </div>
              <div
                className="flex-shrink-0 w-20 h-1.5 rounded-full overflow-hidden"
                style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
              >
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.max(5, task.progress_percent)}%`,
                    background: 'linear-gradient(90deg, #10b981, #14b8a6)',
                  }}
                />
              </div>
              <ArrowRight
                className="w-4 h-4 flex-shrink-0"
                style={{ color: 'var(--mars-color-text-tertiary)' }}
              />
              <div
                role="button"
                tabIndex={0}
                onClick={(e) => handleDelete(task.task_id, e)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleDelete(task.task_id, e as unknown as React.MouseEvent) }}
                className="flex-shrink-0 p-1 rounded transition-colors hover:bg-[var(--mars-color-danger-subtle,rgba(239,68,68,0.1))]"
                title="Delete task"
              >
                <X
                  className="w-3.5 h-3.5"
                  style={{ color: 'var(--mars-color-text-tertiary)' }}
                />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
