/**
 * useVideoQA — Video Clip Q&A hook
 *
 * Abstracts the StreamingVLM → vLLM fallback chain
 * behind a single "upload a clip, get an answer" interface.
 *
 * Users never see backend selection, FPS settings, chunk sizes, or model names.
 * The backend auto-selects the best available level:
 *   Level 1: StreamingVLM  (needs 40GB+ VRAM — OOMs locally, falls through)
 *   Level 2: vLLM frame-by-frame (always active with vLLM at localhost:8000)
 */
import { useState, useCallback, useRef } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function cleanAnswerText(text) {
    if (!text) return ''
    let cleaned = String(text).trim()
    try {
        const parsed = JSON.parse(cleaned)
        if (parsed && typeof parsed === 'object') {
            cleaned = parsed.answer || parsed.commentary || parsed.key_observation || parsed.analysis || parsed.text || cleaned
        }
    } catch {
        const match = cleaned.match(/"(?:answer|commentary|key_observation|analysis|text)"\s*:\s*"([^"]+)/s)
        if (match) cleaned = match[1]
    }
    return cleaned
        .replace(/\\n/g, ' ')
        .replace(/\\"/g, '"')
        .replace(/^\s*(?:answer|commentary|analysis|text)\s*:\s*/i, '')
        .replace(/",?\s*\d+\s*:\s*.*$/s, '')
        .replace(/^[\s{}[\],'"]+|[\s{}[\],'"]+$/g, '')
        .replace(/\s+/g, ' ')
        .trim()
}

/**
 * @typedef {Object} VideoQAState
 * @property {boolean}  isAnalyzing     - True while the backend is processing
 * @property {string}   answer          - Streaming answer text (grows as SSE arrives)
 * @property {string|null} error        - Error message if analysis failed
 * @property {number}   backendLevel    - Which fallback level actually ran (1/2/4)
 * @property {string|null} videoPreview - Object URL for the uploaded clip preview
 * @property {Function} analyzeClip     - Call with (File, query?) to start analysis
 * @property {Function} reset           - Clear all state
 */

export function useVideoQA() {
    const [isAnalyzing, setIsAnalyzing] = useState(false)
    const [answer, setAnswer] = useState('')
    const [error, setError] = useState(null)
    const [backendLevel, setBackendLevel] = useState(null)
    const [videoPreview, setVideoPreview] = useState(null)
    const abortRef = useRef(null)

    const reset = useCallback(() => {
        // Abort any in-flight request
        if (abortRef.current) {
            abortRef.current.abort()
            abortRef.current = null
        }
        setIsAnalyzing(false)
        setAnswer('')
        setError(null)
        setBackendLevel(null)
        if (videoPreview) {
            URL.revokeObjectURL(videoPreview)
        }
        setVideoPreview(null)
    }, [videoPreview])

    /**
     * Upload a video clip and stream the Q&A answer back.
     *
     * @param {File} file         - The video file from <input type="file">
     * @param {string} [query]    - Optional text question. Defaults to tactical analysis prompt.
     * @param {string} [sport]    - Sport context. Defaults to "soccer".
     */
    const analyzeClip = useCallback(async (file, query = '', sport = 'soccer') => {
        if (!file) return

        // Create preview URL for left panel
        const previewUrl = URL.createObjectURL(file)
        setVideoPreview(previewUrl)
        setIsAnalyzing(true)
        setAnswer('')
        setError(null)
        setBackendLevel(null)

        const controller = new AbortController()
        abortRef.current = controller

        try {
            const formData = new FormData()
            formData.append('video', file)
            formData.append('query', query || 'Analyze this football clip. Describe the tactical situation, key players, and what is likely to happen next.')
            formData.append('sport', sport)
            // Backend decides level — no user-facing selection

            const response = await fetch(`${API_BASE}/api/v1/video/qa`, {
                method: 'POST',
                body: formData,
                signal: controller.signal,
            })

            if (!response.ok) {
                const text = await response.text()
                throw new Error(`Analysis failed (${response.status}): ${text.slice(0, 200)}`)
            }

            // SSE stream — read level from first meta event, then accumulate text
            const reader = response.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ''

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n')
                buffer = lines.pop() ?? '' // Keep incomplete line

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue
                    const data = line.slice(6).trim()
                    if (data === '[DONE]') break

                    try {
                        const event = JSON.parse(data)
                        if (event.type === 'meta') {
                            setBackendLevel(event.backend_level ?? null)
                        } else if (event.type === 'token') {
                            setAnswer(prev => cleanAnswerText(prev + (event.text ?? '')))
                        } else if (event.type === 'error') {
                            throw new Error(event.message)
                        }
                    } catch (parseErr) {
                        // Non-JSON line — treat as raw token text
                        if (data && data !== '[DONE]') {
                            setAnswer(prev => cleanAnswerText(prev + data))
                        }
                    }
                }
            }
        } catch (err) {
            if (err.name === 'AbortError') return // User cancelled
            console.error('[useVideoQA] Analysis failed:', err)
            setError(err.message ?? 'Analysis failed. Please try again.')
        } finally {
            setIsAnalyzing(false)
            abortRef.current = null
        }
    }, [])

    return { isAnalyzing, answer, error, backendLevel, videoPreview, analyzeClip, reset }
}
