import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

function cleanSpeechText(text) {
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

export function useBrowserSpeechSynthesis({
    enabled = true,
    lang = 'en-US',
    rate = 1,
    pitch = 1,
    volume = 1,
} = {}) {
    const [isSupported, setIsSupported] = useState(false)
    const [isSpeaking, setIsSpeaking] = useState(false)
    const voicesRef = useRef([])
    const utteranceRef = useRef(null)

    useEffect(() => {
        if (typeof window === 'undefined' || !window.speechSynthesis || !window.SpeechSynthesisUtterance) {
            setIsSupported(false)
            return undefined
        }

        const synth = window.speechSynthesis
        setIsSupported(true)

        const loadVoices = () => {
            voicesRef.current = synth.getVoices()
        }

        loadVoices()
        synth.addEventListener?.('voiceschanged', loadVoices)

        return () => {
            synth.removeEventListener?.('voiceschanged', loadVoices)
            synth.cancel()
        }
    }, [])

    const voice = useMemo(() => {
        const voices = voicesRef.current
        if (!voices.length) return null
        return (
            voices.find(v => v.lang === lang) ||
            voices.find(v => v.lang?.startsWith(lang.slice(0, 2))) ||
            voices[0]
        )
    }, [lang, isSupported])

    const cancel = useCallback(() => {
        if (typeof window === 'undefined' || !window.speechSynthesis) return
        window.speechSynthesis.cancel()
        utteranceRef.current = null
        setIsSpeaking(false)
    }, [])

    const speak = useCallback((text) => {
        if (!enabled || typeof window === 'undefined' || !window.speechSynthesis || !window.SpeechSynthesisUtterance) {
            return false
        }

        const cleaned = cleanSpeechText(text)
        if (!cleaned) return false

        window.speechSynthesis.cancel()

        const utterance = new window.SpeechSynthesisUtterance(cleaned)
        utterance.lang = lang
        utterance.rate = rate
        utterance.pitch = pitch
        utterance.volume = volume
        if (voice) utterance.voice = voice

        utterance.onstart = () => setIsSpeaking(true)
        utterance.onend = () => {
            utteranceRef.current = null
            setIsSpeaking(false)
        }
        utterance.onerror = () => {
            utteranceRef.current = null
            setIsSpeaking(false)
        }

        utteranceRef.current = utterance
        window.speechSynthesis.speak(utterance)
        return true
    }, [enabled, lang, pitch, rate, voice, volume])

    return {
        isSupported,
        isSpeaking,
        speak,
        cancel,
    }
}

export default useBrowserSpeechSynthesis
