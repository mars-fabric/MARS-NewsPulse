'use client'

import React, { useEffect, useCallback, useState } from 'react'
import { ArrowLeft, Download, FileText, CheckCircle, Play, Eye, Code, RefreshCw } from 'lucide-react'
import { Button } from '@/components/core'
import ExecutionProgress from '@/components/deepresearch/ExecutionProgress'
import MarkdownRenderer from '@/components/files/MarkdownRenderer'
import type { useNewsPulseTask } from '@/hooks/useNewsPulseTask'
import { getApiUrl } from '@/lib/config'

interface NpReportPanelProps {
  hook: ReturnType<typeof useNewsPulseTask>
  stageNum: number
  onBack: () => void
}

type ViewTab = 'rendered' | 'raw'

export default function NpReportPanel({ hook, stageNum, onBack }: NpReportPanelProps) {
  const {
    taskId,
    taskState,
    consoleOutput,
    isExecuting,
    executeStage,
    fetchStageContent,
    editableContent,
    setEditableContent,
  } = hook

  const [artifacts, setArtifacts] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState<ViewTab>('rendered')

  const stage = taskState?.stages.find(s => s.stage_number === stageNum)
  const isCompleted = stage?.status === 'completed'
  const isFailed = stage?.status === 'failed'
  const isNotStarted = stage?.status === 'pending'

  useEffect(() => {
    if (isCompleted && taskId) {
      fetchStageContent(stageNum).then(content => {
        if (content?.output_files) setArtifacts(content.output_files)
      })
    }
  }, [isCompleted, taskId, fetchStageContent, stageNum])

  const getFileName = (path: string) => path.split('/').pop() || path

  const handleDownload = useCallback(async (path: string) => {
    try {
      const resp = await fetch(getApiUrl(`/api/files/download?path=${encodeURIComponent(path)}`))
      if (!resp.ok) throw new Error('Download failed')
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = getFileName(path)
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      // fallback: open in new tab
      window.open(getApiUrl(`/api/files/download?path=${encodeURIComponent(path)}`), '_blank')
    }
  }, [])

  // Not started — show run button
  if (isNotStarted && !isExecuting) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <div
          className="p-6 rounded-mars-lg text-center"
          style={{ backgroundColor: 'var(--mars-color-surface)' }}
        >
          <FileText className="w-10 h-10 mx-auto mb-3" style={{ color: 'var(--mars-color-text-tertiary)' }} />
          <h3 className="text-base font-semibold mb-1" style={{ color: 'var(--mars-color-text)' }}>
            Final Report & PDF Generation
          </h3>
          <p className="text-sm mb-4" style={{ color: 'var(--mars-color-text-secondary)' }}>
            Compile all research and analysis into a professional executive intelligence report.
          </p>
          <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm">
            <Play className="w-3.5 h-3.5 mr-1.5" />
            Generate Final Report
          </Button>
        </div>
        <div className="flex items-center justify-start">
          <Button onClick={onBack} variant="secondary" size="sm">
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back
          </Button>
        </div>
      </div>
    )
  }

  // Running
  if (isExecuting || stage?.status === 'running') {
    return (
      <div className="max-w-3xl mx-auto">
        <ExecutionProgress
          consoleOutput={consoleOutput}
          isExecuting={isExecuting}
          stageName="Final Report & PDF"
        />
        <div className="mt-4">
          <Button onClick={onBack} variant="secondary" size="sm" disabled>
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back
          </Button>
        </div>
      </div>
    )
  }

  // Failed
  if (isFailed) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <div
          className="p-4 rounded-mars-md text-sm"
          style={{
            backgroundColor: 'var(--mars-color-danger-subtle)',
            color: 'var(--mars-color-danger)',
            border: '1px solid var(--mars-color-danger)',
          }}
        >
          Stage failed: {stage?.error || 'Unknown error'}
        </div>
        <div className="flex gap-3">
          <Button onClick={onBack} variant="secondary" size="sm">
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back
          </Button>
          <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm">
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Retry
          </Button>
        </div>
      </div>
    )
  }

  // Completed — show artifacts & preview
  const pdfFiles = artifacts.filter(f => f.endsWith('.pdf'))
  const mdFiles = artifacts.filter(f => f.endsWith('.md'))

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Success banner */}
      <div
        className="flex items-center gap-3 p-4 rounded-mars-md"
        style={{
          backgroundColor: 'var(--mars-color-success-subtle, rgba(34,197,94,0.1))',
          border: '1px solid var(--mars-color-success)',
        }}
      >
        <CheckCircle className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--mars-color-success)' }} />
        <div className="flex-1">
          <p className="text-sm font-medium" style={{ color: 'var(--mars-color-text)' }}>
            Report generated successfully!
          </p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--mars-color-text-secondary)' }}>
            {pdfFiles.length > 0
              ? 'Your executive intelligence report is ready as PDF and Markdown.'
              : 'Your executive intelligence report is ready. Install weasyprint for PDF output.'}
          </p>
        </div>
        {/* Inline download buttons */}
        <div className="flex gap-2 flex-shrink-0">
          {pdfFiles.map((path) => (
            <Button
              key={path}
              onClick={() => handleDownload(path)}
              variant="primary"
              size="sm"
            >
              <Download className="w-3.5 h-3.5 mr-1" />
              PDF
            </Button>
          ))}
          {mdFiles.map((path) => (
            <Button
              key={path}
              onClick={() => handleDownload(path)}
              variant="secondary"
              size="sm"
            >
              <Download className="w-3.5 h-3.5 mr-1" />
              Markdown
            </Button>
          ))}
        </div>
      </div>

      {/* Download all artifacts */}
      {artifacts.length > 2 && (
        <div>
          <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--mars-color-text)' }}>
            All Report Files
          </h3>
          <div className="space-y-2">
            {artifacts.map((path) => (
              <div
                key={path}
                className="flex items-center justify-between p-3 rounded-mars-md border"
                style={{
                  borderColor: 'var(--mars-color-border)',
                  backgroundColor: 'var(--mars-color-surface)',
                }}
              >
                <div className="flex items-center gap-3">
                  <FileText className="w-4 h-4" style={{ color: path.endsWith('.pdf') ? 'var(--mars-color-danger)' : 'var(--mars-color-primary)' }} />
                  <div>
                    <p className="text-sm font-medium" style={{ color: 'var(--mars-color-text)' }}>
                      {getFileName(path)}
                    </p>
                    <p className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                      {path.endsWith('.pdf') ? 'PDF Report' : 'Markdown Report'}
                    </p>
                  </div>
                </div>
                <Button
                  onClick={() => handleDownload(path)}
                  variant="secondary"
                  size="sm"
                >
                  <Download className="w-3.5 h-3.5 mr-1" />
                  Download
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Report preview with tabs */}
      {editableContent && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium" style={{ color: 'var(--mars-color-text)' }}>
              Report Preview
            </h3>
            <div
              className="flex rounded-mars-sm overflow-hidden border"
              style={{ borderColor: 'var(--mars-color-border)' }}
            >
              <button
                onClick={() => setActiveTab('rendered')}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 transition-colors"
                style={{
                  backgroundColor: activeTab === 'rendered'
                    ? 'var(--mars-color-primary)'
                    : 'var(--mars-color-surface-overlay)',
                  color: activeTab === 'rendered'
                    ? '#fff'
                    : 'var(--mars-color-text-secondary)',
                }}
              >
                <Eye className="w-3 h-3" />
                Rendered
              </button>
              <button
                onClick={() => setActiveTab('raw')}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 transition-colors"
                style={{
                  backgroundColor: activeTab === 'raw'
                    ? 'var(--mars-color-primary)'
                    : 'var(--mars-color-surface-overlay)',
                  color: activeTab === 'raw'
                    ? '#fff'
                    : 'var(--mars-color-text-secondary)',
                }}
              >
                <Code className="w-3 h-3" />
                Markdown
              </button>
            </div>
          </div>
          <div
            className="border rounded-mars-md overflow-auto"
            style={{
              borderColor: 'var(--mars-color-border)',
              backgroundColor: activeTab === 'rendered' ? 'var(--mars-color-bg, #fff)' : 'var(--mars-color-surface)',
              maxHeight: '75vh',
            }}
          >
            {activeTab === 'rendered' ? (
              <div
                className="p-6 md:p-10 prose prose-sm md:prose-base max-w-none
                           prose-headings:font-semibold
                           prose-h1:text-2xl prose-h1:border-b-2 prose-h1:pb-3
                           prose-h2:text-xl prose-h2:border-b prose-h2:pb-2 prose-h2:mt-8
                           prose-h4:text-base
                           prose-table:text-sm
                           prose-blockquote:border-l-4 prose-blockquote:not-italic
                           prose-hr:my-6"
                style={{
                  color: 'var(--mars-color-text)',
                  '--tw-prose-headings': 'var(--mars-color-text)',
                  '--tw-prose-links': 'var(--mars-color-primary, #0f3460)',
                  '--tw-prose-bold': 'var(--mars-color-text)',
                  '--tw-prose-quotes': 'var(--mars-color-text-secondary)',
                  '--tw-prose-quote-borders': 'var(--mars-color-primary, #0f3460)',
                  '--tw-prose-th-borders': 'var(--mars-color-border)',
                  '--tw-prose-td-borders': 'var(--mars-color-border)',
                  '--tw-prose-hr': 'var(--mars-color-border)',
                } as React.CSSProperties}
              >
                <MarkdownRenderer content={editableContent} />
              </div>
            ) : (
              <pre
                className="p-4 text-xs font-mono whitespace-pre-wrap leading-relaxed"
                style={{ color: 'var(--mars-color-text)' }}
              >
                {editableContent}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* Back */}
      <div className="flex items-center justify-start">
        <Button onClick={onBack} variant="secondary" size="sm">
          <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back
        </Button>
      </div>
    </div>
  )
}
