'use client'

import React, { useState, useCallback, useEffect, useRef } from 'react'
import { Eye, Edit3, Save, ArrowRight, ArrowLeft, RefreshCw, Loader2, Send, Check } from 'lucide-react'
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
    refinementMessages,
    consoleOutput,
    isExecuting,
    executeStage,
    fetchStageContent,
    saveStageContent,
    refineContent,
  } = hook

  const [mode, setMode] = useState<'edit' | 'preview'>('edit')
  const [saveIndicator, setSaveIndicator] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [contentLoaded, setContentLoaded] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [isSendingChat, setIsSendingChat] = useState(false)
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const chatScrollRef = useRef<HTMLDivElement>(null)

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

  // Auto-scroll chat
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight
    }
  }, [refinementMessages])

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

  // Chat (AI refine)
  const handleSendChat = useCallback(async () => {
    if (!chatInput.trim() || isSendingChat) return
    const msg = chatInput.trim()
    setChatInput('')
    setIsSendingChat(true)

    const result = await refineContent(stageNum, msg, editableContent)
    if (result) {
      setEditableContent(result)
      await saveStageContent(stageNum, result, sharedKey)
    }
    setIsSendingChat(false)
  }, [chatInput, isSendingChat, refineContent, stageNum, editableContent, setEditableContent, saveStageContent, sharedKey])

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
    <div className="max-w-6xl mx-auto">
      <div className="flex gap-6" style={{ minHeight: '500px' }}>
        {/* Main editor/preview */}
        <div className="flex-1 flex flex-col">
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

        {/* Refinement chat sidebar */}
        <div
          className="w-80 flex flex-col rounded-mars-md border"
          style={{
            borderColor: 'var(--mars-color-border)',
            backgroundColor: 'var(--mars-color-surface)',
          }}
        >
          <div
            className="px-4 py-3 border-b flex-shrink-0"
            style={{ borderColor: 'var(--mars-color-border)' }}
          >
            <p className="text-sm font-medium" style={{ color: 'var(--mars-color-text)' }}>
              AI Refinement
            </p>
            <p className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
              Ask the AI to refine the report
            </p>
          </div>

          {/* Messages */}
          <div ref={chatScrollRef} className="flex-1 overflow-y-auto p-3 space-y-3">
            {refinementMessages.length === 0 && (
              <p className="text-xs text-center py-6" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                Ask the AI to add topics, remove companies, expand sections, or adjust the analysis...
              </p>
            )}
            {refinementMessages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className="max-w-[90%] px-3 py-2 rounded-mars-md text-xs"
                  style={{
                    backgroundColor: msg.role === 'user'
                      ? 'var(--mars-color-primary)'
                      : 'var(--mars-color-surface-overlay)',
                    color: msg.role === 'user'
                      ? 'white'
                      : 'var(--mars-color-text)',
                  }}
                >
                  {msg.role === 'assistant' ? (
                    <div>
                      <p className="mb-1.5 whitespace-pre-wrap">{msg.content.slice(0, 200)}...</p>
                      <button
                        onClick={() => {
                          setEditableContent(msg.content)
                          saveStageContent(stageNum, msg.content, sharedKey)
                        }}
                        className="text-xs font-medium underline"
                        style={{ color: 'var(--mars-color-primary)' }}
                      >
                        Apply to editor
                      </button>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  )}
                </div>
              </div>
            ))}
            {isSendingChat && (
              <div className="flex justify-start">
                <div className="px-3 py-2 rounded-mars-md" style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}>
                  <Loader2 className="w-4 h-4 animate-spin" style={{ color: 'var(--mars-color-primary)' }} />
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="p-3 border-t" style={{ borderColor: 'var(--mars-color-border)' }}>
            <div className="flex gap-2">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendChat() } }}
                placeholder="Add more depth on AI regulation..."
                className="flex-1 px-3 py-2 text-xs rounded-mars-md border outline-none"
                style={{
                  backgroundColor: 'var(--mars-color-surface)',
                  borderColor: 'var(--mars-color-border)',
                  color: 'var(--mars-color-text)',
                }}
                disabled={isSendingChat}
              />
              <Button
                onClick={handleSendChat}
                disabled={!chatInput.trim() || isSendingChat}
                variant="primary"
                size="sm"
              >
                <Send className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
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
