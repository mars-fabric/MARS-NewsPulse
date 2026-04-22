// components/workflow/WorkflowDashboard.tsx

'use client';

import { WorkflowStateBar } from './WorkflowStateBar';
import { CostSummary, CostTimeSeries } from '@/types/cost';
import { Layers, Timer, DollarSign, Activity, GitBranch } from 'lucide-react';

interface WorkflowDashboardProps {
  status: string;
  dagData: any | null;
  elapsedTime: string;
  branches?: any[];
  currentBranchId?: string;
  workflowHistory?: any[];
  costSummary: CostSummary | null;
  costTimeSeries: CostTimeSeries[];
  filesUpdatedCounter: number;
  onPause: () => void;
  onResume: () => void;
  onCancel: () => void;
  onPlayFromNode?: (nodeId: string) => void;
  onCreateBranch?: (...args: any[]) => void;
  onSelectBranch?: (id: string) => void;
  onViewBranch?: (id: string) => void;
  onCompareBranches?: (a: string, b: string) => void;
  onViewWorkflow?: (w: any) => void;
  onResumeWorkflow?: (w: any) => void;
  onBranchWorkflow?: (w: any) => void;
}

export function WorkflowDashboard({
  status,
  dagData,
  elapsedTime,
  costSummary,
  onPause,
  onResume,
  onCancel,
}: WorkflowDashboardProps) {
  const nodes = dagData?.nodes || [];
  const completedSteps = nodes.filter((n: any) => n.status === 'completed').length;
  const totalSteps = nodes.length;
  const progress = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;

  return (
    <div className="p-4 space-y-4">
      {/* State Bar */}
      <WorkflowStateBar
        status={status}
        progress={progress}
        totalSteps={totalSteps}
        completedSteps={completedSteps}
        totalCost={costSummary?.total_cost || 0}
        elapsedTime={elapsedTime}
        onPause={onPause}
        onResume={onResume}
        onCancel={onCancel}
      />

      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-3">
        <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--mars-color-surface-overlay)', border: '1px solid var(--mars-color-border)' }}>
          <div className="flex items-center gap-2 mb-1">
            <Layers className="w-4 h-4" style={{ color: 'var(--mars-color-primary)' }} />
            <span className="text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>Steps</span>
          </div>
          <div className="text-lg font-semibold" style={{ color: 'var(--mars-color-text)' }}>
            {completedSteps}/{totalSteps}
          </div>
        </div>

        <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--mars-color-surface-overlay)', border: '1px solid var(--mars-color-border)' }}>
          <div className="flex items-center gap-2 mb-1">
            <Timer className="w-4 h-4" style={{ color: 'var(--mars-color-info)' }} />
            <span className="text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>Elapsed</span>
          </div>
          <div className="text-lg font-semibold" style={{ color: 'var(--mars-color-text)' }}>
            {elapsedTime || '0:00'}
          </div>
        </div>

        <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--mars-color-surface-overlay)', border: '1px solid var(--mars-color-border)' }}>
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4" style={{ color: 'var(--mars-color-success)' }} />
            <span className="text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>Cost</span>
          </div>
          <div className="text-lg font-semibold" style={{ color: 'var(--mars-color-text)' }}>
            ${(costSummary?.total_cost || 0).toFixed(4)}
          </div>
        </div>

        <div className="rounded-lg p-3" style={{ backgroundColor: 'var(--mars-color-surface-overlay)', border: '1px solid var(--mars-color-border)' }}>
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-4 h-4" style={{ color: 'var(--mars-color-warning)' }} />
            <span className="text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>Tokens</span>
          </div>
          <div className="text-lg font-semibold" style={{ color: 'var(--mars-color-text)' }}>
            {(costSummary?.total_tokens || 0).toLocaleString()}
          </div>
        </div>
      </div>

      {/* DAG Node List */}
      {nodes.length > 0 && (
        <div className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--mars-color-border)' }}>
          <div className="px-3 py-2 text-xs font-medium" style={{ backgroundColor: 'var(--mars-color-surface-overlay)', color: 'var(--mars-color-text-secondary)' }}>
            Execution Steps
          </div>
          <div className="divide-y" style={{ borderColor: 'var(--mars-color-border-subtle)' }}>
            {nodes.map((node: any, i: number) => (
              <div key={node.id || i} className="flex items-center justify-between px-3 py-2 text-xs">
                <div className="flex items-center gap-2">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{
                      backgroundColor:
                        node.status === 'completed' ? 'var(--mars-color-success)' :
                        node.status === 'executing' ? 'var(--mars-color-primary)' :
                        node.status === 'failed' ? 'var(--mars-color-danger)' :
                        'var(--mars-color-text-tertiary)',
                    }}
                  />
                  <span style={{ color: 'var(--mars-color-text)' }}>{node.label || `Step ${i + 1}`}</span>
                </div>
                <span
                  className="text-[10px] px-1.5 py-0.5 rounded"
                  style={{
                    backgroundColor:
                      node.status === 'completed' ? 'var(--mars-color-success-subtle)' :
                      node.status === 'executing' ? 'var(--mars-color-primary-subtle)' :
                      node.status === 'failed' ? 'var(--mars-color-danger-subtle)' :
                      'var(--mars-color-surface-overlay)',
                    color:
                      node.status === 'completed' ? 'var(--mars-color-success)' :
                      node.status === 'executing' ? 'var(--mars-color-primary)' :
                      node.status === 'failed' ? 'var(--mars-color-danger)' :
                      'var(--mars-color-text-tertiary)',
                  }}
                >
                  {node.status || 'pending'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {nodes.length === 0 && (
        <div className="flex flex-col items-center justify-center py-8" style={{ color: 'var(--mars-color-text-tertiary)' }}>
          <GitBranch className="w-10 h-10 mb-3 opacity-40" />
          <p className="text-sm">No workflow data yet</p>
          <p className="text-xs mt-1">Start a task to see execution progress</p>
        </div>
      )}
    </div>
  );
}
