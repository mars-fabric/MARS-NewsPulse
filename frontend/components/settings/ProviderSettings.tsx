'use client'

import React from 'react'
import Modal from '@/components/core/Modal'
import { useProviders } from '@/hooks/useProviders'
import ProviderCard from './ProviderCard'

interface ProviderSettingsProps {
  onClose: () => void
}

export default function ProviderSettings({ onClose }: ProviderSettingsProps) {
  const {
    providers,
    configuredProviders,
    availableModels,
    isLoading,
    error,
    testProvider,
    saveCredentials,
    removeCredentials,
    refreshProviders,
  } = useProviders()

  const subtitle =
    configuredProviders.length > 0
      ? `${configuredProviders.length} active provider${
          configuredProviders.length !== 1 ? 's' : ''
        } · ${availableModels.length} models available`
      : 'Configure at least one LLM provider to get started'

  const footer =
    configuredProviders.length === 0 && !isLoading && !error ? (
      <p
        className="text-xs text-center w-full"
        style={{ color: 'var(--mars-color-text-tertiary)' }}
      >
        Click <strong>Configure</strong> on any provider above to add your API
        credentials. Existing <code>.env</code> credentials are detected
        automatically.
      </p>
    ) : undefined

  return (
    <Modal
      open={true}
      onClose={onClose}
      title="LLM Provider Settings"
      size="lg"
      footer={footer}
    >
      <p
        className="text-xs mb-4"
        style={{ color: 'var(--mars-color-text-tertiary)' }}
      >
        {subtitle}
      </p>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div
            className="animate-spin rounded-full h-6 w-6 border-2 border-t-transparent"
            style={{
              borderColor: 'var(--mars-color-border)',
              borderTopColor: 'transparent',
            }}
          />
          <span
            className="ml-3 text-sm"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            Loading providers...
          </span>
        </div>
      ) : error ? (
        <div
          role="alert"
          className="rounded-lg px-4 py-3 text-sm"
          style={{
            backgroundColor: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.2)',
            color: '#ef4444',
          }}
        >
          <div className="font-medium mb-1">Failed to load providers</div>
          <div className="text-xs opacity-80 break-all mb-3">{error}</div>
          <button
            onClick={refreshProviders}
            className="px-3 py-1 rounded text-xs font-medium border transition-colors
              hover:bg-red-500/10"
            style={{ borderColor: 'rgba(239,68,68,0.3)', color: '#ef4444' }}
          >
            Retry
          </button>
        </div>
      ) : providers.length === 0 ? (
        <div
          className="text-center py-12 text-sm"
          style={{ color: 'var(--mars-color-text-tertiary)' }}
        >
          No providers registered.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {providers.map((provider) => (
            <ProviderCard
              key={provider.provider_id}
              provider={provider}
              onTest={testProvider}
              onSave={saveCredentials}
              onRemove={removeCredentials}
            />
          ))}
        </div>
      )}
    </Modal>
  )
}
