/**
 * TypeScript types for the Industry News & Sentiment Pulse wizard.
 *
 * 4-stage pipeline:
 *   1 — Setup & Config (no AI)
 *   2 — News Discovery & Collection (AI research via DDGS)
 *   3 — Deep Sentiment & Analysis (AI research via DDGS)
 *   4 — Final Report + PDF (AI compilation)
 */

export type NewsPulseStageStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface NewsPulseStage {
  stage_number: number
  stage_name: string
  status: NewsPulseStageStatus
  started_at?: string | null
  completed_at?: string | null
  error?: string | null
}

export interface NewsPulseTaskState {
  task_id: string
  task: string
  status: string
  work_dir?: string | null
  created_at?: string | null
  stages: NewsPulseStage[]
  current_stage?: number | null
  progress_percent: number
  total_cost_usd?: number | null
}

export interface NewsPulseStageContent {
  stage_number: number
  stage_name: string
  status: string
  content?: string | null
  shared_state?: Record<string, unknown> | null
  output_files?: string[] | null
}

export interface NewsPulseCreateResponse {
  task_id: string
  work_dir: string
  stages: NewsPulseStage[]
}

export interface NewsPulseRefineResponse {
  refined_content: string
  message: string
}

export interface NewsPulseRefinementMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

/** Wizard step mapping (0-indexed) */
export type NewsPulseWizardStep = 0 | 1 | 2 | 3

export const NEWSPULSE_STEP_LABELS = [
  'Setup & Config',
  'News Discovery',
  'Deep Analysis',
  'Final Report',
] as const

export const NP_WIZARD_STEP_TO_STAGE: Record<number, number | null> = {
  0: 1,  // Setup & Config = Stage 1
  1: 2,  // News Discovery = Stage 2
  2: 3,  // Deep Analysis = Stage 3
  3: 4,  // Final Report + PDF = Stage 4
}

export const NP_STAGE_SHARED_KEYS: Record<number, string> = {
  1: 'user_input_summary',
  2: 'news_collection',
  3: 'deep_analysis',
  4: 'final_report',
}

export const TIME_WINDOW_OPTIONS = [
  { value: '2026', label: '2026 (Current Year)' },
  { value: '2025', label: '2025' },
  { value: '2025-2026', label: '2025–2026' },
  { value: 'Q1 2026', label: 'Q1 2026 (Jan–Mar)' },
  { value: 'Q1 2025', label: 'Q1 2025 (Jan–Mar)' },
  { value: 'Q2 2025', label: 'Q2 2025 (Apr–Jun)' },
  { value: 'Q3 2025', label: 'Q3 2025 (Jul–Sep)' },
  { value: 'Q4 2025', label: 'Q4 2025 (Oct–Dec)' },
  { value: 'H1 2025', label: 'H1 2025 (Jan–Jun)' },
  { value: 'H2 2025', label: 'H2 2025 (Jul–Dec)' },
  { value: 'H1 2026', label: 'H1 2026 (Jan–Jun)' },
  { value: '30d', label: 'Past 30 Days' },
  { value: '90d', label: 'Past 3 Months' },
]

/** Suggested configurations shown in the setup panel */
export const SETUP_SUGGESTIONS = [
  {
    label: 'AI & Tech — Global 2026',
    industry: 'Artificial Intelligence & Technology',
    companies: 'OpenAI, Google, Microsoft, NVIDIA',
    region: 'Global',
    time_window: '2026',
  },
  {
    label: 'Healthcare — US 2025',
    industry: 'Healthcare & Pharmaceuticals',
    companies: 'Pfizer, Johnson & Johnson, UnitedHealth',
    region: 'North America',
    time_window: '2025',
  },
  {
    label: 'FinTech — Europe Q1 2026',
    industry: 'Financial Technology',
    companies: 'Stripe, Revolut, Wise, Adyen',
    region: 'Europe',
    time_window: 'Q1 2026',
  },
  {
    label: 'EV & Clean Energy — Asia 2025',
    industry: 'Electric Vehicles & Clean Energy',
    companies: 'Tesla, BYD, CATL, Rivian',
    region: 'Asia Pacific',
    time_window: '2025',
  },
]

/** Available model options for stage configuration (shared with deep research) */
export interface ModelOption {
  value: string
  label: string
}

export const AVAILABLE_MODELS: ModelOption[] = [
  { value: 'gpt-4.1-2025-04-14', label: 'GPT-4.1' },
  { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
  { value: 'gpt-4o', label: 'GPT-4o' },
  { value: 'gpt-4o-mini-2024-07-18', label: 'GPT-4o Mini' },
  { value: 'gpt-4.5-preview-2025-02-27', label: 'GPT-4.5 Preview' },
  { value: 'gpt-5-2025-08-07', label: 'GPT-5' },
  { value: 'o3-mini-2025-01-31', label: 'o3-mini' },
  { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
  { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
  { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
  { value: 'claude-sonnet-4-20250514', label: 'Claude Sonnet 4' },
  { value: 'claude-3.5-sonnet-20241022', label: 'Claude 3.5 Sonnet' },
]

/** Config overrides for NewsPulse stages */
export interface NewsPulseStageConfig {
  // Shared across stages 2-4
  researcher_model?: string
  planner_model?: string
  plan_reviewer_model?: string
  orchestration_model?: string
  formatter_model?: string
}
