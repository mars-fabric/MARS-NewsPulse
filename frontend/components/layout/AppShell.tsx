'use client'

import { ReactNode } from 'react'

interface AppShellProps {
  children: ReactNode
}

/**
 * Thin shell. The actual TopBar + SessionSidebar live inside `app/page.tsx`
 * so the new-session and session-selection state can be co-located with the
 * task-wizard mount point — same pattern as MARS-PaperPulse.
 */
export default function AppShell({ children }: AppShellProps) {
  return (
    <div
      className="h-screen flex flex-col overflow-hidden"
      style={{ backgroundColor: 'var(--mars-color-bg)' }}
    >
      <a href="#mars-main-content" className="mars-skip-link">
        Skip to main content
      </a>

      <main
        id="mars-main-content"
        role="main"
        className="flex-1 min-h-0 overflow-hidden"
        style={{ backgroundColor: 'var(--mars-color-bg)' }}
      >
        {children}
      </main>

      <div aria-live="polite" aria-atomic="true" className="mars-live-region" id="mars-live-announcements" />
    </div>
  )
}
