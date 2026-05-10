import { renderHook, act, waitFor } from '@testing-library/react'
import { useSpeechRecognition } from '../useSpeechRecognition'

// Mock Web Speech API
const mockRecognition = {
    start: jest.fn(),
    stop: jest.fn(),
    abort: jest.fn(),
    continuous: false,
    interimResults: true,
    lang: 'en-US',
    onstart: null,
    onresult: null,
    onend: null,
    onerror: null,
}

beforeEach(() => {
    jest.clearAllMocks()
    window.SpeechRecognition = jest.fn(() => mockRecognition)
    window.webkitSpeechRecognition = undefined
})

describe('useSpeechRecognition', () => {
    describe('browser support', () => {
        it('returns isSupported: false when SpeechRecognition not available', () => {
            window.SpeechRecognition = undefined
            window.webkitSpeechRecognition = undefined

            const { result } = renderHook(() => useSpeechRecognition({}))

            expect(result.current.isSupported).toBe(false)
        })

        it('returns isSupported: true when SpeechRecognition available', () => {
            const { result } = renderHook(() => useSpeechRecognition({}))

            expect(result.current.isSupported).toBe(true)
        })
    })

    describe('listening state', () => {
        it('starts listening when startListening is called', () => {
            const { result } = renderHook(() => useSpeechRecognition({}))

            act(() => {
                result.current.startListening()
            })

            expect(mockRecognition.start).toHaveBeenCalled()
        })

        it('stops listening when stopListening is called', () => {
            const { result } = renderHook(() => useSpeechRecognition({}))

            act(() => {
                result.current.startListening()
            })

            act(() => {
                result.current.stopListening()
            })

            expect(mockRecognition.stop).toHaveBeenCalled()
        })

        it('updates isListening state on onstart/onend events', () => {
            const { result } = renderHook(() => useSpeechRecognition({}))

            act(() => {
                result.current.startListening()
                // Simulate onstart
                mockRecognition.onstart()
            })

            expect(result.current.isListening).toBe(true)

            act(() => {
                // Simulate onend
                mockRecognition.onend()
            })

            expect(result.current.isListening).toBe(false)
        })
    })

    describe('interim results', () => {
        it('updates interimTranscript on interim results', () => {
            const { result } = renderHook(() => useSpeechRecognition({}))

            act(() => {
                result.current.startListening()
                mockRecognition.onstart()

                // Simulate interim result
                mockRecognition.onresult({
                    resultIndex: 0,
                    results: [
                        [{ transcript: 'Hello', confidence: 0.8, isFinal: false }],
                    ],
                })
            })

            expect(result.current.interimTranscript).toBe('Hello')
        })

        it('updates finalTranscript on final results', () => {
            const { result } = renderHook(() => useSpeechRecognition({}))

            act(() => {
                result.current.startListening()
                mockRecognition.onstart()

                // Simulate final result
                mockRecognition.onresult({
                    resultIndex: 0,
                    results: [
                        [{ transcript: 'Hello world', confidence: 0.95, isFinal: true }],
                    ],
                })
            })

            expect(result.current.finalTranscript).toBe('Hello world')
            expect(result.current.confidence).toBe(0.95)
        })
    })

    describe('confidence gate', () => {
        it('calls onConfidencePass with skipConfirmation: true for confidence > 90%', () => {
            const onConfidencePass = jest.fn()
            const { result } = renderHook(() =>
                useSpeechRecognition({ onConfidencePass })
            )

            act(() => {
                result.current.startListening()
                mockRecognition.onstart()

                mockRecognition.onresult({
                    resultIndex: 0,
                    results: [
                        [{ transcript: 'Who scored', confidence: 0.95, isFinal: true }],
                    ],
                })
            })

            // Wait for onend to trigger confidence gate
            act(() => {
                mockRecognition.onend()
            })

            expect(onConfidencePass).toHaveBeenCalledWith({
                transcript: 'Who scored',
                confidence: 0.95,
                skipConfirmation: true,
            })
        })

        it('calls onConfidencePass with skipConfirmation: false for confidence 70-90%', () => {
            const onConfidencePass = jest.fn()
            const { result } = renderHook(() =>
                useSpeechRecognition({ onConfidencePass })
            )

            act(() => {
                result.current.startListening()
                mockRecognition.onstart()

                mockRecognition.onresult({
                    resultIndex: 0,
                    results: [
                        [{ transcript: 'Who scored', confidence: 0.82, isFinal: true }],
                    ],
                })
            })

            act(() => {
                mockRecognition.onend()
            })

            expect(onConfidencePass).toHaveBeenCalledWith({
                transcript: 'Who scored',
                confidence: 0.82,
                skipConfirmation: false,
            })
        })

        it('calls onConfidenceReject for confidence < 70%', () => {
            const onConfidenceReject = jest.fn()
            const { result } = renderHook(() =>
                useSpeechRecognition({ onConfidenceReject })
            )

            act(() => {
                result.current.startListening()
                mockRecognition.onstart()

                mockRecognition.onresult({
                    resultIndex: 0,
                    results: [
                        [{ transcript: '', confidence: 0.5, isFinal: true }],
                    ],
                })
            })

            act(() => {
                mockRecognition.onend()
            })

            expect(onConfidenceReject).toHaveBeenCalledWith({
                transcript: '',
                confidence: 0.5,
            })
        })
    })

    describe('15-second timeout', () => {
        beforeEach(() => {
            jest.useFakeTimers()
        })

        afterEach(() => {
            jest.useRealTimers()
        })

        it('forces stop after 15 seconds', () => {
            const { result } = renderHook(() => useSpeechRecognition({}))

            act(() => {
                result.current.startListening()
                mockRecognition.onstart()
            })

            // Fast-forward to 15 seconds
            act(() => {
                jest.advanceTimersByTime(15000)
            })

            expect(mockRecognition.stop).toHaveBeenCalled()
        })

        it('clears timeout on natural onend', () => {
            const { result } = renderHook(() => useSpeechRecognition({}))

            act(() => {
                result.current.startListening()
                mockRecognition.onstart()
            })

            // Simulate natural stop before 15s
            act(() => {
                mockRecognition.onend()
            })

            // Fast-forward to 15 seconds
            act(() => {
                jest.advanceTimersByTime(15000)
            })

            // Should only have called stop once (not from timeout)
            expect(mockRecognition.stop).toHaveBeenCalledTimes(1)
        })
    })

    describe('consecutive failures', () => {
        it('increments consecutiveFailures on low confidence', () => {
            const { result } = renderHook(() => useSpeechRecognition({}))

            // First failure
            act(() => {
                result.current.startListening()
                mockRecognition.onstart()
                mockRecognition.onresult({
                    resultIndex: 0,
                    results: [[{ transcript: '', confidence: 0.5, isFinal: true }]],
                })
                mockRecognition.onend()
            })

            expect(result.current.consecutiveFailures).toBe(1)

            // Second failure
            act(() => {
                result.current.startListening()
                mockRecognition.onstart()
                mockRecognition.onresult({
                    resultIndex: 0,
                    results: [[{ transcript: '', confidence: 0.6, isFinal: true }]],
                })
                mockRecognition.onend()
            })

            expect(result.current.consecutiveFailures).toBe(2)
        })

        it('resets consecutiveFailures on high confidence', () => {
            const { result } = renderHook(() => useSpeechRecognition({}))

            // First, cause two failures
            act(() => {
                result.current.startListening()
                mockRecognition.onstart()
                mockRecognition.onresult({
                    resultIndex: 0,
                    results: [[{ transcript: '', confidence: 0.5, isFinal: true }]],
                })
                mockRecognition.onend()
            })

            act(() => {
                result.current.startListening()
                mockRecognition.onstart()
                mockRecognition.onresult({
                    resultIndex: 0,
                    results: [[{ transcript: '', confidence: 0.6, isFinal: true }]],
                })
                mockRecognition.onend()
            })

            expect(result.current.consecutiveFailures).toBe(2)

            // Now success
            act(() => {
                result.current.startListening()
                mockRecognition.onstart()
                mockRecognition.onresult({
                    resultIndex: 0,
                    results: [[{ transcript: 'test', confidence: 0.95, isFinal: true }]],
                })
                mockRecognition.onend()
            })

            expect(result.current.consecutiveFailures).toBe(0)
        })
    })

    describe('reset', () => {
        it('resets all state to initial values', () => {
            const { result } = renderHook(() => useSpeechRecognition({}))

            // Set some state
            act(() => {
                result.current.startListening()
                mockRecognition.onstart()
                mockRecognition.onresult({
                    resultIndex: 0,
                    results: [[{ transcript: 'test', confidence: 0.5, isFinal: true }]],
                })
                mockRecognition.onend()
            })

            expect(result.current.consecutiveFailures).toBe(1)

            // Reset
            act(() => {
                result.current.reset()
            })

            expect(result.current.interimTranscript).toBe('')
            expect(result.current.finalTranscript).toBe('')
            expect(result.current.confidence).toBe(null)
            expect(result.current.error).toBe(null)
            expect(result.current.consecutiveFailures).toBe(0)
        })
    })
})
