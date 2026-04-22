'use client'

/**
 * useProviders — manages LLM provider state: list, configure, test, remove.
 *
 * Returns:
 *   providers          — all registered providers with status + credential schema
 *   configuredProviders — only those with credentials (status != 'not_configured')
 *   availableModels    — models from configured providers (for UI dropdowns)
 *   activeProvider     — the primary active provider ID
 *   isLoading          — true on first fetch
 *   error              — last fetch/mutation error (or null)
 *   testProvider()     — test credentials without storing
 *   saveCredentials()  — store credentials (vault + registry sync); throws on failure
 *   removeCredentials() — remove stored credentials; throws on failure
 *   refreshProviders() — force refresh from backend
 */

import { useState, useEffect, useCallback } from 'react'
import type {
  Provider,
  ProviderTestResult,
  ProvidersListResponse,
} from '@/types/providers'
import { invalidateModelConfigCache } from '@/hooks/useModelConfig'
import { apiFetchWithRetry } from '@/lib/fetchWithRetry'

// Module-level cache for the provider list (one fetch per browser session)
let _providersCache: ProvidersListResponse | null = null

async function extractErrorMessage(resp: Response): Promise<string> {
  try {
    const text = await resp.text()
    if (!text) return `HTTP ${resp.status}`
    try {
      const parsed = JSON.parse(text)
      return parsed.detail || parsed.message || parsed.error || text
    } catch {
      return text
    }
  } catch {
    return `HTTP ${resp.status}`
  }
}

export function useProviders() {
  const [data, setData] = useState<ProvidersListResponse | null>(_providersCache)
  const [isLoading, setIsLoading] = useState(_providersCache === null)
  const [error, setError] = useState<string | null>(null)

  const fetchProviders = useCallback(async () => {
    try {
      const resp = await apiFetchWithRetry('/api/providers')
      if (!resp.ok) {
        const msg = await extractErrorMessage(resp)
        throw new Error(msg)
      }
      const json: ProvidersListResponse = await resp.json()
      _providersCache = json
      setData(json)
      setError(null)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      console.error('Failed to fetch providers:', err)
      setError(msg)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (_providersCache) {
      setData(_providersCache)
      setIsLoading(false)
      return
    }
    fetchProviders()
  }, [fetchProviders])

  const testProvider = useCallback(
    async (
      providerId: string,
      credentials: Record<string, string>
    ): Promise<ProviderTestResult> => {
      try {
        const resp = await apiFetchWithRetry(
          `/api/providers/${encodeURIComponent(providerId)}/test`,
          {
            method: 'POST',
            body: JSON.stringify({ credentials }),
          }
        )
        if (!resp.ok) {
          const msg = await extractErrorMessage(resp)
          return { success: false, message: `HTTP ${resp.status}: ${msg}` }
        }
        return (await resp.json()) as ProviderTestResult
      } catch (err) {
        return {
          success: false,
          message: `Network error: ${err instanceof Error ? err.message : String(err)}`,
        }
      }
    },
    []
  )

  const saveCredentials = useCallback(
    async (
      providerId: string,
      credentials: Record<string, string>
    ): Promise<{ status: string; message: string }> => {
      const resp = await apiFetchWithRetry(
        `/api/providers/${encodeURIComponent(providerId)}/credentials`,
        {
          method: 'POST',
          body: JSON.stringify({ credentials }),
        }
      )
      if (!resp.ok) {
        const msg = await extractErrorMessage(resp)
        throw new Error(msg)
      }
      const json = await resp.json()
      // Invalidate both provider and model caches, then refresh
      _providersCache = null
      invalidateModelConfigCache()
      await fetchProviders()
      return {
        status: json.status ?? 'success',
        message: json.provider?.message ?? '',
      }
    },
    [fetchProviders]
  )

  const removeCredentials = useCallback(
    async (providerId: string): Promise<void> => {
      const resp = await apiFetchWithRetry(
        `/api/providers/${encodeURIComponent(providerId)}/credentials`,
        { method: 'DELETE' }
      )
      if (!resp.ok) {
        const msg = await extractErrorMessage(resp)
        throw new Error(msg)
      }
      _providersCache = null
      invalidateModelConfigCache()
      await fetchProviders()
    },
    [fetchProviders]
  )

  const refreshProviders = useCallback(async () => {
    _providersCache = null
    setIsLoading(true)
    setError(null)
    await fetchProviders()
  }, [fetchProviders])

  const providers: Provider[] = data?.providers ?? []
  const configuredProviders = providers.filter(
    (p) => p.status !== 'not_configured'
  )

  // Build available models from configured providers
  const availableModels = configuredProviders.flatMap((p) =>
    p.models.map((m) => ({
      value: m.model_id,
      label: m.display_name,
      provider: p.provider_id,
    }))
  )

  // Deduplicate by model_id (Azure and OpenAI share model names)
  const seen = new Set<string>()
  const dedupedModels = availableModels.filter((m) => {
    if (seen.has(m.value)) return false
    seen.add(m.value)
    return true
  })

  return {
    providers,
    configuredProviders,
    availableModels: dedupedModels,
    activeProvider: data?.active_provider ?? null,
    isLoading,
    error,
    testProvider,
    saveCredentials,
    removeCredentials,
    refreshProviders,
  }
}
