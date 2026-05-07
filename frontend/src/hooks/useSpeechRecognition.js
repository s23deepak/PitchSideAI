import { useState, useRef, useCallback, useEffect } from 'react'

/**
 * useSpeechRecognition — Web Speech API wrapper with confidence gating
 *
 * Features:
 * - Interim results for ghost text updates
 * - Confidence extraction and 3-tier gating (>90%, 70-90%, <70%)
 * - 15-second timeout failsafe for Chrome onend bug
 * - Consecutive failure tracking for chip suggestion fallback
 *
 * Browser support:
 * - Chrome/Edge: Full support via webkitSpeechRecognition
 * - Firefox: Limited support
 * - Safari: No support — returns isSupported: false
 */
export function useSpeechRecognition({
    onConfidencePass, // Called when confidence >= 70% with { transcript, confidence }
    onConfidenceReject, // Called when confidence < 70% with { transcript, confidence }
    language = 'en-US',
}) {
    // State
    const [isListening, setIsListening] = useState(false)
    const [interimTranscript, setInterimTranscript] = useState('')
    const [finalTranscript, setFinalTranscript] = useState('')
    const [confidence, setConfidence] = useState(null) // 0.0-1.0 from SpeechRecognitionEvent
    const [error, setError] = useState(null)
    const [consecutiveFailures, setConsecutiveFailures] = useState(0)

    // Refs
    const recognitionRef = useRef(null)
    const timeoutRef = useRef(null)
    const startTimeRef = useRef(null)

    // Check browser support
    const isSupported = typeof window !== 'undefined' &&
        (window.SpeechRecognition || window.webkitSpeechRecognition)

    // Initialize SpeechRecognition
    useEffect(() => {
        if (!isSupported) {
            setError('Speech recognition not supported in this browser')
            return
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
        const recognition = new SpeechRecognition()

        recognition.continuous = false
        recognition.interimResults = true
        recognition.lang = language

        recognition.onstart = () => {
            setIsListening(true)
            setInterimTranscript('')
            setFinalTranscript('')
            setConfidence(null)
            setError(null)
            startTimeRef.current = Date.now()

            // 15-second timeout failsafe for Chrome onend bug
            timeoutRef.current = setTimeout(() => {
                if (isListening) {
                    console.warn('[useSpeechRecognition] 15s timeout fired — forcing stop')
                    recognition.stop()
                    // Force submit if we have interim results
                    if (interimTranscript) {
                        handleForcedSubmit(interimTranscript)
                    }
                }
            }, 15000)
        }

        recognition.onresult = (event) => {
            let interim = ''
            let final = ''
            let maxConfidence = 0

            for (let i = event.resultIndex; i < event.results.length; i++) {
                const result = event.results[i]
                const transcript = result[0].transcript
                const conf = result[0].confidence || 0

                if (result.isFinal) {
                    final += transcript
                    maxConfidence = Math.max(maxConfidence, conf)
                } else {
                    interim += transcript
                    maxConfidence = Math.max(maxConfidence, conf)
                }
            }

            // Fix: Always update interim transcript (don't accumulate stale data)
            setInterimTranscript(interim || '')
            if (final) {
                setFinalTranscript(final)
                setConfidence(maxConfidence)
            } else if (interim) {
                // Use interim confidence as provisional
                setConfidence(maxConfidence)
            }
        }

        recognition.onend = () => {
            // Clear timeout if it exists
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current)
                timeoutRef.current = null
            }

            setIsListening(false)

            // Only process if we have a final transcript
            if (finalTranscript && confidence !== null) {
                handleConfidenceGate(finalTranscript, confidence)
            }

            // Fix: Clear interim transcript to prevent memory leak
            setInterimTranscript('')
            setFinalTranscript('')
            // Also clear confidence to avoid stale data
            setConfidence(null)
        }

        recognition.onerror = (event) => {
            console.error('[useSpeechRecognition] Error:', event.error)
            setError(event.error)
            setIsListening(false)

            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current)
                timeoutRef.current = null
            }
        }

        recognitionRef.current = recognition

        return () => {
            if (recognitionRef.current) {
                recognitionRef.current.abort()
            }
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current)
            }
        }
    }, [isSupported, language])

    // Handle confidence gate (3-tier logic) - Fix #12: Use >= 0.9 for high confidence threshold
    // Fix: Add exponential backoff for consecutive failures
    const handleConfidenceGate = useCallback((transcript, conf) => {
        if (conf >= 0.9) {
            // High confidence (>=90%): proceed immediately
            setConsecutiveFailures(0)
            onConfidencePass?.({ transcript, confidence: conf, skipConfirmation: true })
        } else if (conf >= 0.7) {
            // Medium confidence (70-89%): show confirmation (1.5s)
            setConsecutiveFailures(0)
            onConfidencePass?.({ transcript, confidence: conf, skipConfirmation: false })
        } else {
            // Low confidence (<70%): auto-reject with exponential backoff
            setConsecutiveFailures(prev => {
                const newFailures = prev + 1
                // Exponential backoff: delay increases with each failure (max 8 seconds)
                const backoffDelay = Math.min(1000 * Math.pow(2, newFailures - 1), 8000)
                console.log(`[useSpeechRecognition] Consecutive failure #${newFailures}, backoff delay: ${backoffDelay}ms`)
                return newFailures
            })
            onConfidenceReject?.({ transcript, confidence: conf })
        }
    }, [onConfidencePass, onConfidenceReject])

    // Handle forced submit from 15s timeout
    const handleForcedSubmit = useCallback((transcript) => {
        const conf = confidence || 0.5 // Assume low confidence on timeout
        handleConfidenceGate(transcript, conf)
    }, [confidence, handleConfidenceGate])

    // Start listening
    const startListening = useCallback(() => {
        if (!isSupported || !recognitionRef.current) return

        try {
            recognitionRef.current.start()
        } catch (err) {
            console.error('[useSpeechRecognition] Failed to start:', err)
            setError(err.message)
        }
    }, [isSupported])

    // Stop listening
    const stopListening = useCallback(() => {
        if (!recognitionRef.current) return

        try {
            recognitionRef.current.stop()
        } catch (err) {
            console.error('[useSpeechRecognition] Failed to stop:', err)
        }
    }, [])

    // Reset state
    const reset = useCallback(() => {
        setInterimTranscript('')
        setFinalTranscript('')
        setConfidence(null)
        setError(null)
        setConsecutiveFailures(0)
    }, [])

    return {
        // State
        isListening,
        interimTranscript,
        finalTranscript,
        confidence,
        error,
        consecutiveFailures,
        isSupported,

        // Actions
        startListening,
        stopListening,
        reset,
    }
}

export default useSpeechRecognition
