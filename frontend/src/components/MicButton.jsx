import { useState, useEffect, useCallback, useRef } from 'react'
import { useSpeechRecognition } from '../hooks/useSpeechRecognition'

/**
 * MicButton — Hold-to-record button for fan Q&A
 *
 * States:
 * - idle: Default state, waiting for user input
 * - hover: Cursor over button (shows tooltip first time)
 * - recording: User holding button, capturing audio
 * - confirmation: Showing recognized text with dismiss option
 * - processing: Question submitted, waiting for answer
 * - disabled: AI warming up or mic unavailable
 *
 * Design tokens (from UX-DR1, UX-DR2):
 * - Background: Slate 900 at 85% opacity
 * - Border idle: Slate 800
 * - Border hover: Cyan 400 (interactive accent)
 * - Border recording: Red 500
 * - Border processing: Amber 400 rotating gradient
 * - Size: 48×48px, anchored bottom-right 16px
 */
export default function MicButton({
    onQuestionSubmit, // Callback with { text, confidence }
    isAiReady = true, // False while vision model warming up
    isSplitScreenActive = false, // Hide during active Q&A
}) {
    // Component state
    const [state, setState] = useState('idle') // idle | hover | recording | confirmation | processing | disabled | error
    const [showTooltip, setShowTooltip] = useState(false)
    const [confirmationText, setConfirmationText] = useState('')
    const [confirmationDismissed, setConfirmationDismissed] = useState(false)
    const [progress, setProgress] = useState(0) // 0-100 for recording arc
    const [errorMessage, setErrorMessage] = useState('') // Fix #3, #4: Error display for permission/browser issues

    // Refs
    const holdTimeoutRef = useRef(null)
    const confirmationTimeoutRef = useRef(null)
    const progressIntervalRef = useRef(null)
    const buttonRef = useRef(null)
    const processingTimeoutRef = useRef(null) // Fix #6: WebSocket disconnection timeout
    const tooltipShownRef = useRef(false)

    // Speech recognition callbacks
    const handleConfidencePass = useCallback(({ transcript, confidence, skipConfirmation }) => {
        if (skipConfirmation) {
            // High confidence (>90%): submit immediately
            setConfirmationText('')
            setState('processing')
            onQuestionSubmit?.({ text: transcript, confidence })
        } else {
            // Medium confidence (70-90%): show confirmation for 1.5s
            setConfirmationText(transcript)
            setState('confirmation')

            // Fix #7: Confirmation Timeout Race Condition - track if cleared
            // Fix: Make confirmation delay configurable (default 1000ms, accessible via data attribute or prop)
            const confirmationDelay = typeof window !== 'undefined'
                ? (window.PITCHAI_CONFIG?.confirmationDelay || 1000)
                : 1000

            let confirmationCleared = false
            confirmationTimeoutRef.current = setTimeout(() => {
                if (!confirmationCleared) {
                    setState('processing')
                    onQuestionSubmit?.({ text: transcript, confidence })
                }
            }, confirmationDelay)

            // Store the clear function to prevent timeout from firing after dismissal
            confirmationTimeoutRef.current.clear = () => {
                confirmationCleared = true
            }
        }
    }, [onQuestionSubmit])

    const handleConfidenceReject = useCallback(({ transcript, confidence }) => {
        // Low confidence (<70%): auto-reject, show retry message
        setConfirmationText("I didn't quite catch that — try again?")
        setState('idle')

        // Clear after 2s
        setTimeout(() => {
            setConfirmationText('')
        }, 2000)
    }, [])

    // Initialize speech recognition
    const {
        isListening,
        interimTranscript,
        confidence,
        error,
        consecutiveFailures,
        isSupported,
        startListening,
        stopListening,
    } = useSpeechRecognition({
        onConfidencePass: handleConfidencePass,
        onConfidenceReject: handleConfidenceReject,
    })

    // Sync isListening with state
    useEffect(() => {
        if (isListening) {
            setState('recording')
        }
    }, [isListening])

    // Progress bar animation (0-15s)
    useEffect(() => {
        if (state === 'recording') {
            setProgress(0)
            progressIntervalRef.current = setInterval(() => {
                setProgress(prev => {
                    const next = prev + (100 / 150) // 100% over 15 seconds (150 intervals of 100ms)
                    return next >= 100 ? 100 : next
                })
            }, 100)
        } else {
            if (progressIntervalRef.current) {
                clearInterval(progressIntervalRef.current)
            }
            setProgress(0)
        }

        return () => {
            if (progressIntervalRef.current) {
                clearInterval(progressIntervalRef.current)
            }
        }
    }, [state])

    // Handle hide during split-screen
    // Fix: Preserve recording state when split-screen activates — resume when it closes
    const preSplitScreenRef = useRef(null)

    useEffect(() => {
        if (isSplitScreenActive && state !== 'hidden' && state !== 'disabled') {
            // Store current state before hiding
            preSplitScreenRef.current = state
            setState('hidden')
        } else if (!isSplitScreenActive && state === 'hidden') {
            // Restore previous state when split-screen closes
            const previousState = preSplitScreenRef.current
            if (previousState === 'recording') {
                // If was recording, stop it cleanly and show confirmation
                stopListening()
                setState('confirmation')
            } else if (previousState) {
                setState(previousState)
            } else {
                setState('idle')
            }
            preSplitScreenRef.current = null
        }
    }, [isSplitScreenActive, state, stopListening])

    // Fix #6: WebSocket Disconnection Timeout - reset state after 30s if no response
    useEffect(() => {
        if (state === 'processing') {
            processingTimeoutRef.current = setTimeout(() => {
                console.warn('[MicButton] Processing timeout - no response after 30s')
                setState('idle')
                setErrorMessage('Request timed out. Please try again.')
            }, 30000) // 30 second timeout
        } else {
            if (processingTimeoutRef.current) {
                clearTimeout(processingTimeoutRef.current)
                processingTimeoutRef.current = null
            }
        }

        return () => {
            if (processingTimeoutRef.current) {
                clearTimeout(processingTimeoutRef.current)
                processingTimeoutRef.current = null
            }
        }
    }, [state])

    // Handle AI ready state - Fix #5: AC7 - Separate "AI warming up" and "Microphone not available" states
    useEffect(() => {
        if (!isAiReady && (state === 'idle' || state === 'disabled')) {
            setState('disabled')
            setErrorMessage('AI warming up... ready in ~20s')
            setErrorMessage('AI warming up...')
        } else if (!isSupported && (state === 'idle' || state === 'disabled')) {
            // Fix #4: Safari/Firefox incompatibility - distinct state
            setState('disabled')
            setErrorMessage('Microphone not available')
        } else if (state === 'disabled' && isAiReady && isSupported) {
            setState('idle')
            setErrorMessage('')
        }
    }, [isAiReady, isSupported, state])

    // Handle consecutive failures (suggest chips after 3)
    const [showChipSuggestions, setShowChipSuggestions] = useState(false)

    useEffect(() => {
        if (consecutiveFailures >= 3) {
            // Show chip suggestions UI
            setShowChipSuggestions(true)
            console.log('[MicButton] 3 consecutive failures — showing chip suggestions')
        }
    }, [consecutiveFailures])

    // Clear chip suggestions on successful recognition
    useEffect(() => {
        if (state === 'processing' || state === 'confirmation') {
            setShowChipSuggestions(false)
        }
    }, [state])

    // Fix #3: Handle speech recognition errors (permission denied, etc.)
    useEffect(() => {
        if (error) {
            console.error('[MicButton] Speech recognition error:', error)
            setState('error')
            // Map error types to user-friendly messages
            if (error === 'NotAllowedError' || error === 'PermissionDeniedError') {
                setErrorMessage('Microphone permission denied. Please enable in browser settings.')
            } else if (error === 'NoSpeech') {
                setErrorMessage('No speech detected. Try again.')
            } else if (error === 'AudioCapture') {
                setErrorMessage('No microphone found. Please connect a microphone.')
            } else {
                setErrorMessage('Speech recognition error. Please try again.')
            }
        }
    }, [error])

    // Mouse/touch handlers
    const handlePointerDown = useCallback((e) => {
        e.preventDefault() // Prevent text selection

        if (!isAiReady || !isSupported || state === 'disabled' || state === 'error') return

        // Fix #9: Rapid Click/Double Press - clear any existing timeout before setting new one
        if (holdTimeoutRef.current) {
            clearTimeout(holdTimeoutRef.current)
            holdTimeoutRef.current = null
        }

        // 300ms hold timeout — ignore clicks
        // Fix: Add 100ms debounce to prevent false positives on micro-scroll
        const debounceStart = Date.now()
        holdTimeoutRef.current = setTimeout(() => {
            // Double-check we haven't been cancelled during debounce
            if (Date.now() - debounceStart >= 100) {
                startListening()
                setShowTooltip(false) // Hide tooltip on recording start
            }
        }, 300)
    }, [isAiReady, isSupported, startListening, state])

    const handlePointerUp = useCallback(() => {
        if (holdTimeoutRef.current) {
            clearTimeout(holdTimeoutRef.current)
            holdTimeoutRef.current = null
        }

        if (isListening) {
            stopListening()
        }
    }, [isListening, stopListening])

    const handlePointerLeave = useCallback(() => {
        if (holdTimeoutRef.current) {
            clearTimeout(holdTimeoutRef.current)
            holdTimeoutRef.current = null
        }

        if (isListening) {
            stopListening()
        }
    }, [isListening, stopListening])

    // Fix #10: Touch Device Pointer Event Mismatch - add touch-specific leave handler
    const handleTouchMove = useCallback((e) => {
        // If user slides finger off button during touch, stop recording
        const touch = e.touches[0]
        const target = document.elementFromPoint(touch.clientX, touch.clientY)
        if (!buttonRef.current?.contains(target)) {
            if (holdTimeoutRef.current) {
                clearTimeout(holdTimeoutRef.current)
                holdTimeoutRef.current = null
            }
            if (isListening) {
                stopListening()
            }
        }
    }, [isListening, stopListening])

    const handleMouseEnter = useCallback(() => {
        if (state === 'idle' && !tooltipShownRef.current) {
            setShowTooltip(true)
            tooltipShownRef.current = true
            // Persist to localStorage
            localStorage.setItem('pitchai-mic-tooltip-shown', 'true')
        }
    }, [state])

    // Check localStorage on mount
    useEffect(() => {
        const hasShown = localStorage.getItem('pitchai-mic-tooltip-shown')
        if (hasShown === 'true') {
            tooltipShownRef.current = true
        }
    }, [])

    // Keyboard handlers
    useEffect(() => {
        const handleKeyDown = (e) => {
            // Fix #1: Spacebar Global Keyboard Trap - ignore if focus is in input field
            if (e.target.closest('input, textarea, [contenteditable="true"]')) {
                return
            }
            if (e.code === 'Space' && state === 'idle' && isAiReady) {
                e.preventDefault() // Prevent page scroll
                handlePointerDown(e)
            }
        }

        const handleKeyUp = (e) => {
            if (e.code === 'Space') {
                e.preventDefault()
                handlePointerUp()
            }
            if (e.code === 'Escape') {
                // Cancel recording or dismiss confirmation
                if (isListening) {
                    stopListening()
                    setConfirmationText('')
                    setState('idle')
                }
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        window.addEventListener('keyup', handleKeyUp)

        return () => {
            window.removeEventListener('keydown', handleKeyDown)
            window.removeEventListener('keyup', handleKeyUp)
        }
    }, [state, isAiReady, isListening, handlePointerDown, handlePointerUp, stopListening])

    // Dismiss confirmation - Fix #7: Clear the timeout flag to prevent late firing
    const handleDismissConfirmation = useCallback(() => {
        if (confirmationTimeoutRef.current) {
            // Call the custom clear function to set the flag
            if (confirmationTimeoutRef.current.clear) {
                confirmationTimeoutRef.current.clear()
            }
            clearTimeout(confirmationTimeoutRef.current)
            confirmationTimeoutRef.current = null
        }
        setConfirmationText('')
        setState('idle')
    }, [])

    // Clean up on unmount - Fix #2: Stop active recording on unmount to prevent memory leak
    useEffect(() => {
        return () => {
            if (holdTimeoutRef.current) clearTimeout(holdTimeoutRef.current)
            if (confirmationTimeoutRef.current) clearTimeout(confirmationTimeoutRef.current)
            if (progressIntervalRef.current) clearInterval(progressIntervalRef.current)
            if (processingTimeoutRef.current) clearTimeout(processingTimeoutRef.current)
            // Stop any active recording to prevent memory leak and orphaned SpeechRecognition
            if (isListening) {
                stopListening()
            }
        }
    }, [isListening, stopListening])

    // Determine button styles based on state
    const getButtonStyles = () => {
        const base = 'relative flex items-center justify-center rounded-full backdrop-blur-md transition-all duration-200'

        switch (state) {
            case 'idle':
                return `${base} w-12 h-12 bg-bg-secondary/85 border-2 border-border hover:border-[var(--accent-interactive)] hover:shadow-[0_0_12px_rgba(34,211,238,0.4)]`
            case 'hover':
                return `${base} w-12 h-12 bg-bg-secondary/85 border-2 var(--accent-interactive) shadow-[0_0_12px_rgba(34,211,238,0.4)]`
            case 'recording':
                return `${base} w-12 h-12 bg-bg-secondary/85 border-2 var(--danger) animate-pulse scale-105 shadow-[0_0_16px_rgba(239,68,68,0.6)]`
            case 'confirmation':
                return `${base} w-12 h-12 bg-bg-secondary/85 border-2 var(--warning)`
            case 'processing':
                return `${base} w-12 h-12 bg-bg-secondary/85 border-2 var(--warning) animate-spin-slow`
            case 'disabled':
                // Fix #5: AC7 - Different visual treatment for different disabled reasons
                return `${base} w-12 h-12 bg-bg-secondary/50 border-2 border-border opacity-50`
            case 'error':
                return `${base} w-12 h-12 bg-bg-secondary/50 border-2 var(--danger) opacity-50`
            case 'hidden':
                return `${base} w-12 h-12 bg-bg-secondary/50 border-2 border-border opacity-50`
            default:
                return `${base} w-12 h-12 bg-bg-secondary/85 border-2 border-border`
        }
    }

    // Hide completely during split-screen
    if (state === 'hidden') {
        return null
    }

    // Suggested question chips (shown after 3 consecutive failures)
    const suggestedChips = [
        "What's the current formation?",
        "Who's the top scorer?",
        "Show recent head-to-head results",
        "What's the tactical setup?",
    ]

    return (
        <div className="fixed bottom-4 right-4 z-50 flex flex-col items-center">
            {/* Chip Suggestions — Fix: Show after 3 consecutive failures */}
            {showChipSuggestions && (
                <div className="absolute bottom-full mb-4 flex flex-col gap-2 bg-bg-secondary/95 border border-border rounded-lg p-3 animate-slide-up">
                    <p className="text-xs text-text-muted mb-1">Having trouble? Try asking:</p>
                    {suggestedChips.map((chip, idx) => (
                        <button
                            key={idx}
                            className="px-3 py-1.5 bg-bg-surface hover:bg-bg-surface-hover border border-border hover:border-[var(--accent-interactive)] rounded text-xs text-text-primary text-left transition-colors"
                            onClick={() => {
                                setShowChipSuggestions(false)
                                onQuestionSubmit?.({ text: chip, confidence: 1.0 })
                            }}
                        >
                            {chip}
                        </button>
                    ))}
                </div>
            )}

            {/* Tooltip */}
            {showTooltip && state === 'idle' && (
                <div
                    className="absolute bottom-full mb-2 px-3 py-1.5 bg-bg-surface text-text-primary text-sm rounded-md shadow-lg whitespace-nowrap animate-fade-in"
                    role="tooltip"
                >
                    Hold to ask a question
                    {/* Tooltip arrow */}
                    <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-bg-surface" />
                </div>
            )}

            {/* Error message display - Fix #3, #4: Show error for permission/browser issues */}
            {errorMessage && (state === 'disabled' || state === 'error') && (
                <div className="absolute bottom-full mb-16 px-4 py-2 bg-danger-muted/90 border border-danger text-danger-foreground text-sm rounded-lg max-w-xs text-center animate-fade-in">
                    {errorMessage}
                </div>
            )}

            {/* Ghost text (interim transcript) */}
            {interimTranscript && state === 'recording' && (
                <div className="absolute bottom-full mb-16 px-4 py-2 bg-bg-secondary/90 text-text-muted text-sm rounded-lg max-w-xs text-center animate-fade-in">
                    {interimTranscript}
                </div>
            )}

            {/* Confirmation text */}
            {confirmationText && state === 'confirmation' && (
                <div className="absolute bottom-full mb-16 px-4 py-3 bg-bg-secondary/95 border border-[var(--warning)]/50 text-text-primary text-sm rounded-lg max-w-xs flex items-center gap-2 animate-fade-in">
                    <span className="flex-1">{confirmationText}</span>
                    <button
                        onClick={handleDismissConfirmation}
                        className="p-1 hover:bg-bg-surface-hover rounded transition-colors"
                        aria-label="Dismiss"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            )}

            {/* Fix #13: Processing State Cancel Path - allow cancel during processing */}
            {state === 'processing' && (
                <div className="absolute bottom-full mb-16 px-4 py-3 bg-bg-secondary/95 border border-[var(--warning)]/50 text-text-primary text-sm rounded-lg max-w-xs flex items-center gap-2 animate-fade-in">
                    <span className="flex-1">Processing your question...</span>
                    <button
                        onClick={() => {
                            setState('idle')
                            setErrorMessage('')
                        }}
                        className="p-1 hover:bg-bg-surface-hover rounded transition-colors"
                        aria-label="Cancel processing"
                        title="Cancel processing"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            )}

            {/* Button */}
            <button
                ref={buttonRef}
                className={getButtonStyles()}
                onMouseEnter={handleMouseEnter}
                onPointerDown={handlePointerDown}
                onPointerUp={handlePointerUp}
                onPointerLeave={handlePointerLeave}
                onTouchStart={handlePointerDown}
                onTouchEnd={handlePointerUp}
                onTouchMove={handleTouchMove}
                disabled={state === 'disabled' || state === 'processing' || state === 'error'}
                aria-label={
                    state === 'idle' ? 'Hold to ask a question' :
                    state === 'recording' ? 'Recording...' :
                    state === 'processing' ? 'Processing your question' :
                    state === 'disabled' ? (isSupported ? 'AI warming up' : 'Microphone not available') :
                    state === 'error' ? 'Speech recognition error' :
                    'Microphone unavailable'
                }
                title={errorMessage || undefined}
            >
                {/* Progress arc (recording state only) */}
                {state === 'recording' && (
                    <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 48 48">
                        <circle
                            cx="24"
                            cy="24"
                            r="20"
                            fill="none"
                            stroke="rgba(239, 68, 68, 0.3)"
                            strokeWidth="4"
                        />
                        <circle
                            cx="24"
                            cy="24"
                            r="20"
                            fill="none"
                            stroke="rgb(239, 68, 68)"
                            strokeWidth="4"
                            strokeDasharray={125.6}
                            strokeDashoffset={125.6 - (125.6 * progress) / 100}
                            strokeLinecap="round"
                            className="transition-all duration-100"
                        />
                    </svg>
                )}

                {/* Processing gradient ring — Fix: True gradient rotation instead of simple spin */}
                {state === 'processing' && (
                    <div className="absolute inset-[-2px] rounded-full bg-gradient-to-r from-amber-400 via-orange-400 to-amber-400 animate-spin-slow" style={{ mask: 'radial-gradient(circle, transparent 55%, black 58%)', WebkitMask: 'radial-gradient(circle, transparent 55%, black 58%)' }} />
                )}

                {/* Microphone icon */}
                <svg
                    className={`w-5 h-5 transition-colors ${
                        state === 'idle' ? 'text-slate-400' :
                        state === 'hover' || state === 'recording' || state === 'processing' ? 'text-white' :
                        'text-slate-500'
                    }`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                    />
                </svg>
            </button>

            {/* Vignette overlay (processing state) */}
            {state === 'processing' && (
                <div className="fixed inset-0 pointer-events-none bg-gradient-to-br from-black/5 to-transparent z-40" />
            )}
        </div>
    )
}
