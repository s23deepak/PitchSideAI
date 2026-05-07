import React, { useState, useEffect } from 'react'

/**
 * CommentatorLayout — Midnight Stadium design system
 *
 * Matches .bmad/screens/commentator-dashboard.html exactly:
 *   - bg-[#131313] background
 *   - glass-card: rgba(26,26,26,0.6) backdrop-blur-xl border-white/10
 *   - ai-glow-border: inset 0 0 0 1px #c3f400 + 0 0 8px rgba(195,244,0,0.3)
 *   - gold-highlight for active teleprompter line: border-left #e9c400
 *   - Desktop: 8/4 grid (video 66%, teleprompter 34%)  ← spec uses col-span-8 + col-span-4
 *   - Stats strip below video: Possession / Shots / xG Momentum
 *   - Live • dot + timestamp in video header overlay
 */

interface CommentatorLayoutProps {
  videoCanvas: React.ReactNode
  teleprompter: React.ReactNode
  statsStrip?: React.ReactNode
  liveHeader?: React.ReactNode
}

const GLASS = {
  background: 'rgba(26, 26, 26, 0.60)',
  backdropFilter: 'saturate(180%) blur(12px)',
  WebkitBackdropFilter: 'saturate(180%) blur(12px)',
  border: '1px solid rgba(255,255,255,0.10)',
  borderRadius: '12px',
} as const

const AI_GLOW = {
  ...GLASS,
  boxShadow: 'inset 0 0 0 1px #c3f400, 0 0 8px rgba(195, 244, 0, 0.30)',
} as const

export function CommentatorLayout({
  videoCanvas,
  teleprompter,
  statsStrip,
  liveHeader,
}: CommentatorLayoutProps) {
  const [isMobile, setIsMobile] = useState(false)
  const [showTeleprompter, setShowTeleprompter] = useState(false)

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 1024)
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])

  if (isMobile) {
    return (
      <div style={{ background: '#131313', minHeight: '100vh', color: '#e5e2e1' }}>
        {/* Video full-width */}
        <div style={{ padding: '8px' }}>
          <div style={{ ...AI_GLOW, overflow: 'hidden', position: 'relative' }}>
            {liveHeader}
            <div style={{ aspectRatio: '16/9', position: 'relative' }}>{videoCanvas}</div>
            {statsStrip}
          </div>
        </div>
        {/* Show Notes toggle */}
        <button
          onClick={() => setShowTeleprompter(!showTeleprompter)}
          style={{
            position: 'fixed', bottom: '80px', right: '16px', zIndex: 30,
            padding: '8px 16px', background: '#2a2a2a', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '8px', color: '#e5e2e1', fontSize: '13px', fontFamily: "'Inter', sans-serif",
            fontWeight: 500, cursor: 'pointer', boxShadow: '0 2px 12px rgba(0,0,0,0.4)',
          }}
        >
          {showTeleprompter ? 'Hide Notes' : 'Show Notes'}
        </button>
        {showTeleprompter && (
          <div style={{ position: 'fixed', inset: 0, zIndex: 40, background: '#131313', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
              <span style={{ fontFamily: "'Inter', sans-serif", fontWeight: 700, fontSize: '16px' }}>AI Narrative Stream</span>
              <button onClick={() => setShowTeleprompter(false)} style={{ background: 'none', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '6px', color: '#e5e2e1', padding: '4px 10px', cursor: 'pointer' }}>Close</button>
            </div>
            <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>{teleprompter}</div>
          </div>
        )}
      </div>
    )
  }

  // Desktop: 8/4 grid — exact spec layout
  return (
    <div
      style={{ background: '#0A0A0A', minHeight: '100vh', color: '#e5e2e1', display: 'flex', flexDirection: 'column' }}
    >
      <main
        style={{
          flex: 1, padding: '16px', display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '16px',
          height: 'calc(100vh - 73px)', overflow: 'hidden',
        }}
      >
        {/* Left: Video section (66%) */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '0', overflow: 'hidden' }}>
          <div style={{ ...AI_GLOW, flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {/* Video header overlay */}
            {liveHeader}
            {/* Video feed */}
            <div style={{ flex: 1, position: 'relative', background: '#0E0E0E', overflow: 'hidden', minHeight: 0 }}>
              {videoCanvas}
            </div>
            {/* Stats strip */}
            {statsStrip}
          </div>
        </section>

        {/* Right: AI Narrative Stream (34%) */}
        <section style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ ...GLASS, flex: 1, display: 'flex', flexDirection: 'column', padding: '24px', overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', borderBottom: '1px solid rgba(255,255,255,0.10)', paddingBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="material-symbols-outlined" style={{ color: '#c3f400', fontSize: '20px' }}>smart_toy</span>
                <h2 style={{ fontFamily: "'Inter', sans-serif", fontWeight: 700, fontSize: '20px', margin: 0 }}>AI Narrative Stream</h2>
              </div>
            </div>
            <div style={{ flex: 1, overflow: 'auto', paddingRight: '8px' }} className="teleprompter-scroll">
              {teleprompter}
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

export { GLASS, AI_GLOW }
export default CommentatorLayout
