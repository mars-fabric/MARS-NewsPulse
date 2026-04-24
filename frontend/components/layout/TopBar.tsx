'use client'

import { useState } from 'react'
import { Sun, Moon, Plus, Settings, TrendingUp } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'
import ProviderSettings from '@/components/settings/ProviderSettings'

interface TopBarProps {
  onNewSession?: () => void
}

export default function TopBar({ onNewSession }: TopBarProps) {
  const { theme, toggleTheme } = useTheme()
  const [showSettings, setShowSettings] = useState(false)

  return (
    <>
      <header
        className="flex-shrink-0 border-b"
        style={{
          backgroundColor: 'var(--mars-color-surface-raised)',
          borderColor: 'var(--mars-color-border)',
        }}
        role="banner"
      >
        <div
          className="flex items-center justify-between px-5"
          style={{ height: '52px' }}
        >
          {/* Left: brand */}
          <div className="flex items-center gap-3">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #10b981, #14b8a6)' }}
            >
              <TrendingUp className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1
                className="text-sm font-bold tracking-tight"
                style={{ color: 'var(--mars-color-text)', fontFamily: 'var(--mars-font-sans)' }}
              >
                MARS - NewsPulse
              </h1>
              <p className="text-[10px] leading-tight" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                Industry News &amp; Sentiment Analysis
              </p>
            </div>
          </div>

          {/* Right: settings + theme + new */}
          <div className="flex items-center gap-2">

            <button
              onClick={() => setShowSettings(true)}
              className="p-2 rounded-lg transition-colors duration-150 hover:bg-[var(--mars-color-bg-hover)]"
              style={{ color: 'var(--mars-color-text-secondary)' }}
              aria-label="LLM Provider Settings"
              title="LLM Provider Settings"
            >
              <Settings className="w-4 h-4" />
            </button>

            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg transition-colors duration-150 hover:bg-[var(--mars-color-bg-hover)]"
              style={{ color: 'var(--mars-color-text-secondary)' }}
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
              title={`${theme === 'dark' ? 'Light' : 'Dark'} mode`}
            >
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>

            {onNewSession && (
              <button
                onClick={onNewSession}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white transition-all duration-150 hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]"
                style={{ background: 'linear-gradient(135deg, #10b981, #14b8a6)' }}
              >
                <Plus className="w-3.5 h-3.5" />
                New Session
              </button>
            )}
          </div>
        </div>
      </header>

      {showSettings && (
        <ProviderSettings onClose={() => setShowSettings(false)} />
      )}
    </>
  )
}
