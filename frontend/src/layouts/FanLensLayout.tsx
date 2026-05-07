import React, { useState, useEffect } from 'react'

/**
 * FanLensLayout - Responsive Layout for Fan Lens View
 *
 * Breakpoints:
 * - Desktop (≥1440px): Full layout with all controls visible
 * - Tablet (1024px-1439px): Condensed ControlsTray, smaller trivia cards
 * - Mobile (<1024px): Bottom sheet controls, full-width trivia, repositioned MicButton
 */

interface FanLensLayoutProps {
  children: React.ReactNode
  controlsTray?: React.ReactNode
  triviaCards?: React.ReactNode
  micButton?: React.ReactNode
  questionChips?: React.ReactNode
  splitScreen?: React.ReactNode
}

export function FanLensLayout({
  children,
  controlsTray,
  triviaCards,
  micButton,
  questionChips,
  splitScreen,
}: FanLensLayoutProps) {
  const [isMobile, setIsMobile] = useState(false)
  const [isTablet, setIsTablet] = useState(false)
  const [showControlsSheet, setShowControlsSheet] = useState(false)

  useEffect(() => {
    const checkBreakpoint = () => {
      const width = window.innerWidth
      setIsMobile(width < 1024)
      setIsTablet(width >= 1024 && width < 1440)
    }

    checkBreakpoint()
    window.addEventListener('resize', checkBreakpoint)
    return () => window.removeEventListener('resize', checkBreakpoint)
  }, [])

  return (
    <div className="fan-lens-layout min-h-screen bg-bg-primary relative">
      {/* SplitScreen for Q&A Temporal Navigation (Story 5.8) */}
      {splitScreen}

      {/* Video Canvas Area */}
      <div className="video-canvas-container w-full flex justify-center p-4 md:p-6 lg:p-8">
        <div className="video-wrapper relative w-full max-w-7xl aspect-video">
          {children}
        </div>
      </div>

      {/* Trivia Cards - Desktop/Tablet: bottom-left, Mobile: full-width bottom */}
      <div className={`trivia-cards-container fixed z-20
        ${isMobile
          ? 'bottom-20 left-0 right-0 px-2'
          : 'bottom-24 left-4'
        }`}
      >
        <div className={`
          ${isMobile ? 'w-full max-w-none' : 'max-w-[280px]'}
          ${isTablet ? 'max-w-[240px]' : ''}
        `}>
          {triviaCards}
        </div>
      </div>

      {/* MicButton - Desktop: bottom-right, Mobile: top-right */}
      <div className={`mic-button-container fixed z-30
        ${isMobile
          ? 'top-4 right-4'
          : 'bottom-24 right-4'
        }`}
      >
        {micButton}
      </div>

      {/* Question Chips - Desktop: below video, Mobile: hidden unless tapped */}
      <div className={`question-chips-container fixed bottom-32 left-1/2 -translate-x-1/2 z-20
        ${isMobile ? 'hidden' : 'block'}`}
      >
        {questionChips}
      </div>

      {/* ControlsTray - Desktop: always visible, Mobile: bottom sheet */}
      {isMobile ? (
        <>
          {/* Mobile: Show controls button */}
          <button
            onClick={() => setShowControlsSheet(!showControlsSheet)}
            className="fixed bottom-4 left-1/2 -translate-x-1/2 z-30 px-4 py-2 bg-bg-surface border border-border rounded-md text-text-primary text-sm font-medium"
            aria-label="Toggle controls"
          >
            {showControlsSheet ? 'Hide Controls' : 'Show Controls'}
          </button>

          {/* Mobile: Bottom Sheet */}
          <div className={`controls-sheet fixed inset-x-0 bottom-0 z-40 transform transition-transform duration-300 ease-in-out
            ${showControlsSheet ? 'translate-y-0' : 'translate-y-full'}`}
          >
            <div className="bg-bg-surface border-t border-border rounded-t-lg p-4 max-h-[60vh] overflow-y-auto">
              {controlsTray}
            </div>
          </div>
        </>
      ) : (
        /* Desktop/Tablet: Fixed bottom tray */
        <div className="controls-tray-container fixed bottom-0 left-0 right-0 z-30">
          {controlsTray}
        </div>
      )}
    </div>
  )
}

export default FanLensLayout
