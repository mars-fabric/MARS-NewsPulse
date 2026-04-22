'use client'

import React, { useState } from 'react'
import type { CredentialField, ProviderTestResult } from '@/types/providers'

interface ProviderCredentialFormProps {
  providerName: string
  fields: CredentialField[]
  onTest: (creds: Record<string, string>) => Promise<ProviderTestResult>
  onSave: (creds: Record<string, string>) => Promise<{ status: string; message: string }>
  onCancel: () => void
}

export default function ProviderCredentialForm({
  providerName,
  fields,
  onTest,
  onSave,
  onCancel,
}: ProviderCredentialFormProps) {
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {}
    fields.forEach((f) => {
      init[f.name] = ''
    })
    return init
  })
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testResult, setTestResult] = useState<ProviderTestResult | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    setSaveError(null)
    try {
      const result = await onTest(values)
      setTestResult(result)
    } catch (err) {
      setTestResult({
        success: false,
        message: `Test failed: ${err instanceof Error ? err.message : String(err)}`,
      })
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      await onSave(values)
      // onSave closes the form on success; nothing more to do.
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  const hasRequiredFields = fields
    .filter((f) => f.required)
    .every((f) => values[f.name]?.trim())

  return (
    <div
      className="rounded-xl border p-5 space-y-4"
      style={{
        backgroundColor: 'var(--mars-color-surface)',
        borderColor: 'var(--mars-color-border)',
      }}
    >
      <div className="flex items-center justify-between">
        <h3
          className="text-sm font-bold"
          style={{ color: 'var(--mars-color-text)' }}
        >
          Configure {providerName}
        </h3>
        <button
          onClick={onCancel}
          className="text-xs px-2 py-1 rounded hover:bg-[var(--mars-color-bg-hover)] transition-colors"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          Cancel
        </button>
      </div>

      <div className="space-y-3">
        {fields.map((field) => (
          <div key={field.name}>
            <label
              className="block text-xs font-medium mb-1"
              style={{ color: 'var(--mars-color-text-secondary)' }}
            >
              {field.display_name}
              {field.required && (
                <span className="text-red-400 ml-0.5">*</span>
              )}
            </label>
            <p
              className="text-[10px] mb-1 opacity-60"
              style={{ color: 'var(--mars-color-text-tertiary)' }}
            >
              {field.description}
            </p>

            {field.field_type === 'select' ? (
              <select
                value={values[field.name] ?? ''}
                onChange={(e) =>
                  setValues((prev) => ({ ...prev, [field.name]: e.target.value }))
                }
                className="w-full rounded border px-2 py-1.5 text-xs outline-none transition-colors"
                style={{
                  backgroundColor: 'var(--mars-color-surface)',
                  borderColor: 'var(--mars-color-border)',
                  color: 'var(--mars-color-text)',
                }}
              >
                <option value="">— select —</option>
                {field.options.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            ) : field.field_type === 'textarea' ? (
              <textarea
                value={values[field.name] ?? ''}
                onChange={(e) =>
                  setValues((prev) => ({ ...prev, [field.name]: e.target.value }))
                }
                placeholder={field.placeholder}
                rows={3}
                className="w-full rounded border px-2 py-1.5 text-xs outline-none transition-colors font-mono"
                style={{
                  backgroundColor: 'var(--mars-color-surface)',
                  borderColor: 'var(--mars-color-border)',
                  color: 'var(--mars-color-text)',
                }}
              />
            ) : (
              <input
                type={field.field_type === 'password' ? 'password' : 'text'}
                value={values[field.name] ?? ''}
                onChange={(e) =>
                  setValues((prev) => ({ ...prev, [field.name]: e.target.value }))
                }
                placeholder={field.placeholder}
                className="w-full rounded border px-2 py-1.5 text-xs outline-none transition-colors"
                style={{
                  backgroundColor: 'var(--mars-color-surface)',
                  borderColor: 'var(--mars-color-border)',
                  color: 'var(--mars-color-text)',
                }}
              />
            )}
          </div>
        ))}
      </div>

      {/* Test Result */}
      {testResult && (
        <div
          className="rounded-lg px-3 py-2 text-xs"
          style={{
            backgroundColor: testResult.success
              ? 'rgba(34,197,94,0.08)'
              : 'rgba(239,68,68,0.08)',
            color: testResult.success ? '#22c55e' : '#ef4444',
            border: `1px solid ${testResult.success ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
          }}
        >
          <div className="font-medium">{testResult.message}</div>
          {testResult.latency_ms != null && (
            <div className="opacity-70 mt-0.5">
              Latency: {testResult.latency_ms.toFixed(0)}ms
            </div>
          )}
          {testResult.error_details && (
            <div className="mt-1 opacity-70 font-mono text-[10px] break-all">
              {testResult.error_details}
            </div>
          )}
        </div>
      )}

      {/* Save Error */}
      {saveError && (
        <div
          role="alert"
          className="rounded-lg px-3 py-2 text-xs"
          style={{
            backgroundColor: 'rgba(239,68,68,0.08)',
            color: '#ef4444',
            border: '1px solid rgba(239,68,68,0.2)',
          }}
        >
          <div className="font-medium">Failed to save credentials</div>
          <div className="mt-0.5 opacity-80 break-all">{saveError}</div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={handleTest}
          disabled={!hasRequiredFields || testing}
          className="px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors
            disabled:opacity-40 disabled:cursor-not-allowed
            hover:bg-[var(--mars-color-bg-hover)]"
          style={{
            borderColor: 'var(--mars-color-border)',
            color: 'var(--mars-color-text)',
          }}
        >
          {testing ? 'Testing...' : 'Test Connection'}
        </button>
        <button
          onClick={handleSave}
          disabled={!hasRequiredFields || saving}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white transition-all
            disabled:opacity-40 disabled:cursor-not-allowed
            hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]"
          style={{
            background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
          }}
        >
          {saving ? 'Saving...' : 'Save & Connect'}
        </button>
      </div>

      <p
        className="text-[10px] opacity-50 flex items-center gap-1"
        style={{ color: 'var(--mars-color-text-tertiary)' }}
      >
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
        Credentials are encrypted and stored locally. Never sent to external
        services.
      </p>
    </div>
  )
}
