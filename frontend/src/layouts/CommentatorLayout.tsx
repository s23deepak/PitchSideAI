import React, { useState, useEffect } from 'react'

/**
 * CommentatorLayout - Responsive Layout for Commentator Dashboard
 *
 * Breakpoints:
 * - Desktop (≥1440px): 60/40 split (video 60%, teleprompter 40%)
 * - Tablet (1024px-1439px): Stacked (video 100%, teleprompter below)
 * - Mobile (<1024px): Video only, teleprompter accessible via "Show Notes" button
 */

interface CommentatorLayoutProps {
  videoCanvas: React.ReactNode
  teleprompter: React.ReactNode
  controlsTray?: React.ReactNode
}

export function CommentatorLayout({
  videoCanvas,
  teleprompter,
  controlsTray,
}: CommentatorLayoutProps) {
  const [isMobile, setIsMobile] = useState(false)
  const [isTablet, setIsTablet] = useState(false)
  const [showTeleprompter, setShowTeleprompter] = useState(false)

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

  // Desktop: 60/40 split
  if (!isMobile && !isTablet) {
    return (
      <div className="commentator-layout-desktop min-h-screen bg-bg-primary">
        <div className="grid grid-cols-10 h-screen">
          {/* Video Canvas - 60% (6/10 cols) */}
          <div className="col-span-6 video-container p-6 flex items-center justify-center">
            <div className="w-full aspect-video">
              {videoCanvas}
            </div>
          </div>

          {/* Teleprompter - 40% (4/10 cols) */}
          <div className="col-span-4 teleprompter-container border-l border-border bg-bg-surface overflow-hidden">
            {teleprompter}
          </div>
        </div>

        {/* ControlsTray - Full width bottom */}
        {controlsTray && (
          <div className="controls-tray fixed bottom-0 left-0 right-0 z-30">
            {controlsTray}
          </div>
        )}
      </div>
    )
  }

  // Tablet: Stacked layout
  if (isTablet) {
    return (
      <div className="commentator-layout-tablet min-h-screen bg-bg-primary">
        {/* Video Canvas - Full width */}
        <div className="video-container p-4">
          <div className="w-full aspect-video">
            {videoCanvas}
          </div>
        </div>

        {/* Teleprompter - Below video */}
        <div className="teleprompter-container border-t border-border bg-bg-surface h-[50vh] overflow-hidden">
          {teleprompter}
        </div>

        {/* ControlsTray */}
        {controlsTray && (
          <div className="controls-tray fixed bottom-0 left-0 right-0 z-30">
            {controlsTray}
          </div>
        )}
      </div>
    )
  }

  // Mobile: Video only, teleprompter toggle
  return (
    <div className="commentator-layout-mobile min-h-screen bg-bg-primary">
      {/* Video Canvas - Full width */}
      <div className="video-container p-2">
        <div className="w-full aspect-video">
          {videoCanvas}
        </div>
      </div>

      {/* Show Notes Button */}
      <button
        onClick={() => setShowTeleprompter(!showTeleprompter)}
        className="fixed bottom-20 right-4 z-30 px-4 py-2 bg-bg-surface border border-border rounded-md text-text-primary text-sm font-medium shadow-lg"
        aria-label={showTeleprompter ? 'Hide notes' : 'Show notes'}
      >
        {showTeleprompter ? 'Hide Notes' : 'Show Notes'}
      </button>

      {/* Teleprompter Modal */}
      {showTeleprompter && (
        <div className="fixed inset-0 z-40 bg-bg-primary flex flex-col">
          <div className="flex items-center justify-between p-4 border-b border-border">
            <h2 className="text-lg font-semibold text-text-primary">Commentary Notes</h2>
            <button
              onClick={() => setShowTeleprompter(false)}
              className="px-3 py-1 text-text-secondary hover:text-text-primary border border-border rounded-md"
              aria-label="Close notes"
            >
              Close
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {teleprompter}
          </div>
        </div>
      )}

      {/* ControlsTray */}
      {controlsTray && (
        <div className="controls-tray fixed bottom-0 left-0 right-0 z-30">
            {controlsTray}
          </div>
      )}
    </div>
  )
}

export default CommentatorLayout
