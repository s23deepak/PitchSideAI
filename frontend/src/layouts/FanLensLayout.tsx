import React, { useState, useEffect } from 'react'

/**
 * FanLensLayout — Midnight Stadium design system
 *
 * Matches .bmad/screens/fan-lens-broadcast.html exactly:
 * - bg-[#121212] full-bleed background
 * - Full-screen video main area with vignette overlay
 * - Scoreboard pill + language toggle floating over video (top)
 * - Trivia card w-80 floating bottom-left
 * - Broadcast Engine w-72 glass card + Mic button floating bottom-right
 * - SplitScreen for Q&A renders as an absolute overlay
 */

interface FanLensLayoutProps {
  children: React.ReactNode          // Video element
  videoOverlays?: React.ReactNode   // Scoreboard + language toggle
  triviaCards?: React.ReactNode     // Bottom-left AI insight card
  broadcastEngine?: React.ReactNode // Bottom-right glass card (sliders + upload + mic)
  splitScreen?: React.ReactNode     // Full-screen Q&A split overlay
}

export function FanLensLayout({
  children,
  videoOverlays,
  triviaCards,
  broadcastEngine,
  splitScreen,
}: FanLensLayoutProps) {
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768)
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])

  return (
    <div
      className="fan-lens-root"
      style={{
        background: '#121212',
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* SplitScreen overlay — renders on top when Q&A answer arrives */}
      {splitScreen}

      {/* Main live stream canvas — full viewport minus nav */}
      <main style={{ position: 'relative', flex: 1, width: '100%', background: '#0E0E0E' }}>

        {/* Cinematic video background */}
        <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
          {children}
        </div>

        {/* Vignette — from-background via-transparent to-background/40 (spec) */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'linear-gradient(to top, #121212 0%, transparent 30%, transparent 70%, rgba(18,18,18,0.4) 100%)',
            pointerEvents: 'none',
            zIndex: 1,
          }}
        />

        {/* Positioned UI overlays (scoreboard pill, language toggle) — z-index 10 */}
        <div style={{ position: 'absolute', inset: 0, zIndex: 10, pointerEvents: 'none' }}>
          {videoOverlays}
        </div>

        {/* Bottom overlay container — spec: bottom-margin left-margin right-margin */}
        <div
          style={{
            position: 'absolute',
            bottom: isMobile ? '12px' : '24px',
            left: isMobile ? '8px' : '24px',
            right: isMobile ? '8px' : '24px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-end',
            zIndex: 20,
            pointerEvents: 'none',
          }}
        >
          {/* Bottom-left: Trivia card w-80 */}
          <div style={{ pointerEvents: 'auto', width: isMobile ? '100%' : '320px', maxWidth: '320px' }}>
            {triviaCards}
          </div>

          {/* Bottom-right: Broadcast Engine + Mic */}
          <div style={{ pointerEvents: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '12px' }}>
            {broadcastEngine}
          </div>
        </div>
      </main>
    </div>
  )
}

export default FanLensLayout
