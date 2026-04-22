'use client'

/**
 * useModelConfig — fetches centralized model configuration from /api/models/config.
 *
 * Returns:
 *   availableModels  — list of {value, label} for all UI dropdowns
 *   globalDefaults   — global role -> model name map
 *   workflowDefaults — per-workflow, per-stage model defaults
 *   isLoading        — true on first fetch
 *
 * Model list priority:
 *   1. Provider-filtered models from /api/providers/models/available (if any providers configured)
 *   2. Falls back to /api/models/config available_models
 *   3. Last resort: static AVAILABLE_MODELS from types/deepresearch.ts
 *
 * Module-level cache ensures a single fetch per browser session.
 */

import { useState, useEffect } from 'react'
import { AVAILABLE_MODELS as STATIC_FALLBACK } from '@/types/newspulse'

export interface ModelOption {
  value: string
  label: string
}

export interface ModelConfigResponse {
  available_models: ModelOption[]
  global_defaults: Record<string, string>
  workflow_defaults: Record<string, Record<string, Record<string, string>>>
}

// Module-level cache so all component instances share one fetch
let _cache: ModelConfigResponse | null = null
let _fetchPromise: Promise<ModelConfigResponse | null> | null = null

// Provider-aware model cache
let _providerModelsCache: ModelOption[] | null = null
let _providerFetchPromise: Promise<ModelOption[] | null> | null = null

function fetchConfig(): Promise<ModelConfigResponse | null> {
  if (_fetchPromise) return _fetchPromise
  _fetchPromise = fetch('/api/models/config')
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json() as Promise<ModelConfigResponse>
    })
    .then((data) => {
      _cache = data
      return data
    })
    .catch(() => { _fetchPromise = null; return null }) // reset so retry is possible
  return _fetchPromise
}

function fetchProviderModels(): Promise<ModelOption[] | null> {
  if (_providerFetchPromise) return _providerFetchPromise
  _providerFetchPromise = fetch('/api/providers/models/available')
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json()
    })
    .then((data) => {
      const models: ModelOption[] = (data.models ?? []).map(
        (m: { value: string; label: string }) => ({ value: m.value, label: m.label })
      )
      if (models.length > 0) {
        _providerModelsCache = models
        return models
      }
      return null
    })
    .catch(() => { _providerFetchPromise = null; return null })
  return _providerFetchPromise
}

export function useModelConfig() {
  const [config, setConfig] = useState<ModelConfigResponse | null>(_cache)
  const [providerModels, setProviderModels] = useState<ModelOption[] | null>(_providerModelsCache)
  const [isLoading, setIsLoading] = useState(_cache === null)

  useEffect(() => {
    let mounted = true

    // Fetch both in parallel
    Promise.all([
      _cache ? Promise.resolve(_cache) : fetchConfig(),
      _providerModelsCache ? Promise.resolve(_providerModelsCache) : fetchProviderModels(),
    ]).then(([cfgData, provModels]) => {
      if (!mounted) return
      setConfig(cfgData)
      setProviderModels(provModels)
      setIsLoading(false)
    })

    return () => { mounted = false }
  }, [])

  // Use provider-filtered models if available, otherwise fall back to config/static
  const availableModels: ModelOption[] =
    providerModels ??
    config?.available_models ??
    STATIC_FALLBACK

  return {
    availableModels,
    globalDefaults: config?.global_defaults ?? {},
    workflowDefaults: config?.workflow_defaults ?? {},
    isLoading,
  }
}

/**
 * Helper: resolve the display-default for a specific workflow + stage + model role.
 * Used so the "(default: xxx)" labels shown in the UI stay in sync with the backend YAML.
 */
export function resolveStageDefault(
  workflowDefaults: Record<string, Record<string, Record<string, string>>>,
  workflow: string,
  stage: number | 'default',
  role: string,
  hardcodedFallback: string,
): string {
  const wf = workflowDefaults[workflow]
  if (!wf) return hardcodedFallback
  const stageKey = String(stage)
  return wf[stageKey]?.[role] ?? wf['default']?.[role] ?? hardcodedFallback
}

/** Invalidate both caches — call after provider credentials change. */
export function invalidateModelConfigCache() {
  _cache = null
  _fetchPromise = null
  _providerModelsCache = null
  _providerFetchPromise = null
}
