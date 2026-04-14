'use client'

import React, { useEffect, useCallback } from 'react'
import { ArrowLeft, Square, Trash2 } from 'lucide-react'
import { Button } from '@/components/core'
import Stepper from '@/components/core/Stepper'
import type { StepperStep } from '@/components/core/Stepper'
import { useNewsPulseTask } from '@/hooks/useNewsPulseTask'
import { NEWSPULSE_STEP_LABELS, NP_WIZARD_STEP_TO_STAGE } from '@/types/newspulse'
import type { NewsPulseWizardStep } from '@/types/newspulse'
import NpSetupPanel from '@/components/newspulse/NpSetupPanel'
import NpReviewPanel from '@/components/newspulse/NpReviewPanel'
import NpReportPanel from '@/components/newspulse/NpReportPanel'

interface NewsPulseTaskProps {
  onBack: () => void
  resumeTaskId?: string | null
}

export default function NewsPulseTask({ onBack, resumeTaskId }: NewsPulseTaskProps) {
  const hook = useNewsPulseTask()
  const {
    taskId,
    taskState,
    currentStep,
    isLoading,
    error,
    isExecuting,
    setCurrentStep,
    resumeTask,
    stopTask,
    deleteTask,
    clearError,
  } = hook

  // Resume on mount
  useEffect(() => {
    if (resumeTaskId) {
      resumeTask(resumeTaskId)
    }
  }, [resumeTaskId, resumeTask])

  // Build stepper steps
  const stepperSteps: StepperStep[] = NEWSPULSE_STEP_LABELS.map((label, idx) => {
    const stageNum = NP_WIZARD_STEP_TO_STAGE[idx]
    let status: StepperStep['status'] = 'pending'

    if (idx === currentStep) {
      status = 'active'
    } else if (idx < currentStep) {
      status = 'completed'
    }

    if (taskState && stageNum) {
      const stage = taskState.stages.find(s => s.stage_number === stageNum)
      if (stage) {
        if (stage.status === 'completed') status = 'completed'
        else if (stage.status === 'failed') status = 'failed'
        else if (stage.status === 'running') status = 'active'
      }
    }

    return { id: `step-${idx}`, label, status }
  })

  const goNext = useCallback(() => {
    if (currentStep < 3) {
      setCurrentStep((currentStep + 1) as NewsPulseWizardStep)
    }
  }, [currentStep, setCurrentStep])

  const goBack = useCallback(() => {
    if (currentStep > 0 && !isExecuting) {
      setCurrentStep((currentStep - 1) as NewsPulseWizardStep)
    }
  }, [currentStep, isExecuting, setCurrentStep])

  const handleStop = useCallback(async () => {
    await stopTask()
  }, [stopTask])

  const handleDelete = useCallback(async () => {
    if (!confirm('Delete this task? This will remove all data and files.')) return
    await deleteTask()
    onBack()
  }, [deleteTask, onBack])

  // Handle "Continue to next stage" — execute next stage
  const handleContinueToAnalysis = useCallback(async () => {
    if (!taskId) return
    // Move to step 2 (Deep Analysis) and execute stage 3
    goNext()
    await hook.executeStage(3)
  }, [taskId, hook, goNext])

  const handleContinueToFinalReport = useCallback(async () => {
    if (!taskId) return
    // Move to step 3 (Final Report) and execute stage 4
    goNext()
    await hook.executeStage(4)
  }, [taskId, hook, goNext])

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={onBack}
          className="p-2 rounded-mars-md transition-colors hover:bg-[var(--mars-color-surface-overlay)]"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h2
            className="text-2xl font-semibold"
            style={{ color: 'var(--mars-color-text)' }}
          >
            Industry News & Sentiment Pulse
          </h2>
          <p
            className="text-sm mt-0.5"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            AI-powered industry news research and sentiment analysis
          </p>
        </div>
        {taskState?.total_cost_usd != null && taskState.total_cost_usd > 0 && (
          <div
            className="ml-auto text-xs px-3 py-1.5 rounded-mars-md"
            style={{
              backgroundColor: 'var(--mars-color-surface-overlay)',
              color: 'var(--mars-color-text-secondary)',
            }}
          >
            Cost: ${taskState.total_cost_usd.toFixed(4)}
          </div>
        )}
        {taskId && (
          <div className={`flex items-center gap-2 ${taskState?.total_cost_usd ? '' : 'ml-auto'}`}>
            {isExecuting && (
              <Button onClick={handleStop} variant="secondary" size="sm">
                <Square className="w-3.5 h-3.5 mr-1" /> Stop
              </Button>
            )}
            <Button onClick={handleDelete} variant="secondary" size="sm" disabled={isExecuting}>
              <Trash2 className="w-3.5 h-3.5 mr-1" /> Delete
            </Button>
          </div>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div
          className="mb-4 p-3 rounded-mars-md flex items-center justify-between text-sm"
          style={{
            backgroundColor: 'var(--mars-color-danger-subtle)',
            color: 'var(--mars-color-danger)',
            border: '1px solid var(--mars-color-danger)',
          }}
        >
          <span>{error}</span>
          <button onClick={clearError} className="ml-2 font-medium underline">Dismiss</button>
        </div>
      )}

      {/* Stepper */}
      <div className="mb-8">
        <Stepper steps={stepperSteps} orientation="horizontal" size="sm" />
      </div>

      {/* Panel content */}
      <div>
        {currentStep === 0 && (
          <NpSetupPanel hook={hook} onNext={goNext} />
        )}
        {currentStep === 1 && (
          <NpReviewPanel
            hook={hook}
            stageNum={2}
            stageName="News Discovery"
            sharedKey="news_collection"
            onNext={handleContinueToAnalysis}
            onBack={goBack}
            allowRerun={true}
            nextLabel="Continue to Deep Analysis"
          />
        )}
        {currentStep === 2 && (
          <NpReviewPanel
            hook={hook}
            stageNum={3}
            stageName="Deep Analysis"
            sharedKey="deep_analysis"
            onNext={handleContinueToFinalReport}
            onBack={goBack}
            allowRerun={true}
            nextLabel="Generate Final Report"
          />
        )}
        {currentStep === 3 && (
          <NpReportPanel
            hook={hook}
            stageNum={4}
            onBack={goBack}
          />
        )}
      </div>
    </div>
  )
}
