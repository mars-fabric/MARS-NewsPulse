'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { Eye, Edit3, ArrowRight, ArrowLeft, RefreshCw, Loader2, Check } from 'lucide-react'
import { Button } from '@/components/core'
import ExecutionProgress from '@/components/deepresearch/ExecutionProgress'
import MarkdownRenderer from '@/components/files/MarkdownRenderer'
import type { useNewsPulseTask } from '@/hooks/useNewsPulseTask'

interface NpReviewPanelProps {
  hook: ReturnType<typeof useNewsPulseTask>
  stageNum: number
  stageName: string
  sharedKey: string
  onNext: () => void
  onBack: () => void
  allowRerun?: boolean
  nextLabel?: string
}

export default function NpReviewPanel({
  hook,
  stageNum,
  stageName,
  sharedKey,
  onNext,
  onBack,
  allowRerun = false,
  nextLabel = 'Continue',
}: NpReviewPanelProps) {
  const {
    taskState,
    editableContent,
    setEditableContent,
    consoleOutput,
    isExecuting,
    executeStage,
    fetchStageContent,
    saveStageContent,
  } = hook

  const [mode, setMode] = useState<'edit' | 'preview'>('edit')
  const [saveIndicator, setSaveIndicator] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [contentLoaded, setContentLoaded] = useState(false)
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const stage = taskState?.stages.find(s => s.stage_number === stageNum)
  const isStageCompleted = stage?.status === 'completed'
  const isStageRunning = stage?.status === 'running' || isExecuting
  const isStageNotStarted = stage?.status === 'pending'
  const isStageFailed = stage?.status === 'failed'

  // Load content when stage completes
  useEffect(() => {
    if ((isStageCompleted || isStageFailed) && !contentLoaded) {
      fetchStageContent(stageNum).then(() => setContentLoaded(true))
    }
  }, [isStageCompleted, isStageFailed, contentLoaded, fetchStageContent, stageNum])

  const canEdit = isStageCompleted || (isStageFailed && !!editableContent)

  // Auto-save with debounce
  const handleContentChange = useCallback((value: string) => {
    setEditableContent(value)
    setSaveIndicator('idle')
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    saveTimeoutRef.current = setTimeout(async () => {
      if (canEdit) {
        setSaveIndicator('saving')
        await saveStageContent(stageNum, value, sharedKey)
        setSaveIndicator('saved')
        setTimeout(() => setSaveIndicator('idle'), 2000)
      }
    }, 1000)
  }, [canEdit, saveStageContent, setEditableContent, stageNum, sharedKey])

  // If stage is running, show execution progress
  if (isStageRunning) {
    return (
      <div className="max-w-4xl mx-auto">
        <ExecutionProgress
          consoleOutput={consoleOutput}
          isExecuting={isExecuting}
          stageName={stageName}
        />
      </div>
    )
  }

  // If stage hasn't started, show placeholder
  if (isStageNotStarted && !isExecuting) {
    return (
      <div className="max-w-3xl mx-auto text-center py-12">
        <p style={{ color: 'var(--mars-color-text-secondary)' }}>
          {stageName} has not started yet.
        </p>
        <div className="flex items-center justify-center gap-3 mt-4">
          <Button onClick={onBack} variant="secondary" size="sm">
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back
          </Button>
        </div>
      </div>
    )
  }

  // Stage completed (or failed with content) — show review UI
  return (
    <div className="max-w-4xl mx-auto">
      {/* Main editor/preview */}
      <div className="flex flex-col" style={{ minHeight: '500px' }}>
        {/* Toolbar */}
          <div
            className="flex items-center justify-between px-4 py-2 rounded-t-mars-md border border-b-0"
            style={{
              backgroundColor: 'var(--mars-color-surface-overlay)',
              borderColor: 'var(--mars-color-border)',
            }}
          >
            <div className="flex items-center gap-1">
              <button
                onClick={() => setMode('edit')}
                className={`px-3 py-1.5 text-xs font-medium rounded-mars-sm transition-colors ${mode === 'edit' ? '' : 'opacity-60'}`}
                style={{
                  backgroundColor: mode === 'edit' ? 'var(--mars-color-surface)' : 'transparent',
                  color: 'var(--mars-color-text)',
                }}
              >
                <Edit3 className="w-3 h-3 inline mr-1" /> Edit
              </button>
              <button
                onClick={() => setMode('preview')}
                className={`px-3 py-1.5 text-xs font-medium rounded-mars-sm transition-colors ${mode === 'preview' ? '' : 'opacity-60'}`}
                style={{
                  backgroundColor: mode === 'preview' ? 'var(--mars-color-surface)' : 'transparent',
                  color: 'var(--mars-color-text)',
                }}
              >
                <Eye className="w-3 h-3 inline mr-1" /> Preview
              </button>
            </div>

            <div className="flex items-center gap-2">
              {saveIndicator === 'saving' && (
                <span className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                  <Loader2 className="w-3 h-3 inline animate-spin mr-1" /> Saving...
                </span>
              )}
              {saveIndicator === 'saved' && (
                <span className="text-xs" style={{ color: 'var(--mars-color-success)' }}>
                  <Check className="w-3 h-3 inline mr-1" /> Saved
                </span>
              )}

              {allowRerun && (
                <Button
                  onClick={() => executeStage(stageNum)}
                  variant="secondary"
                  size="sm"
                  disabled={isExecuting}
                >
                  <RefreshCw className="w-3 h-3 mr-1" /> Re-run
                </Button>
              )}
            </div>
          </div>

          {/* Content area */}
          <div
            className="flex-1 border rounded-b-mars-md overflow-auto"
            style={{
              borderColor: 'var(--mars-color-border)',
              backgroundColor: 'var(--mars-color-surface)',
            }}
          >
            {mode === 'edit' ? (
              <textarea
                value={editableContent}
                onChange={(e) => handleContentChange(e.target.value)}
                className="w-full h-full p-4 text-sm font-mono resize-none outline-none"
                style={{
                  backgroundColor: 'transparent',
                  color: 'var(--mars-color-text)',
                  minHeight: '400px',
                }}
              />
            ) : (
              <div className="p-4 prose prose-sm max-w-none" style={{ color: 'var(--mars-color-text)' }}>
                <MarkdownRenderer content={editableContent} />
              </div>
            )}
          </div>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between mt-6">
        <Button onClick={onBack} variant="secondary" size="sm">
          <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back
        </Button>
        <Button onClick={onNext} variant="primary" size="sm" disabled={!canEdit}>
          {nextLabel} <ArrowRight className="w-3.5 h-3.5 ml-1" />
        </Button>
      </div>
    </div>
  )
}
