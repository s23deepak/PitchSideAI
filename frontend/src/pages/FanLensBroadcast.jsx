/**
 * FanLensBroadcast — Midnight Stadium broadcast screen
 *
 * Midnight Stadium tokens used directly:
 *   background:           #121212
 *   surface-container-high: #2a2a2a
 *   primary-container:    #c3f400 (lime)
 *   on-surface:           #e5e2e1
 *   on-surface-variant:   #c3c9ae
 *   on-primary-container: #475e00 (dark on lime)
 *
 * Layout (per spec):
 *   Top center:    Scoreboard glass pill (BAR 2 | 78' | RMA 1)
 *   Top right:     Language toggle pill (ESP / ENG)
 *   Bottom left:   Trivia / AI Insight card (w-80)
 *   Bottom right:  Broadcast Engine card (w-72) + Mic button
 *   Overlay:       SplitScreen for Q&A answers
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { useLiveSession } from '@/contexts/LiveSessionContext'
import { FanLensLayout } from '@/layouts/FanLensLayout'
import SplitScreen from '@/components/SplitScreen'
import VideoCanvas from '@/components/VideoCanvas'
import MicButton from '@/components/MicButton'
import { useBrowserSpeechSynthesis } from '@/hooks/useBrowserSpeechSynthesis'

// ── Design tokens (Midnight Stadium) ──────────────────────────────────────────
const T = {
  bg:               '#121212',
  surfaceHigh:      'rgba(42, 42, 42, 0.90)',
  surfaceHighBlur:  'saturate(180%) blur(20px)',
  primaryContainer: '#c3f400',        // Electric Lime
  onPrimary:        '#273500',
  onSurface:        '#e5e2e1',
  onSurfaceVar:     '#c3c9ae',
  border:           'rgba(255,255,255,0.10)',
  borderDim:        'rgba(255,255,255,0.05)',
  fontMono:         "'Space Grotesk', monospace",
  fontUI:           "'Inter', system-ui, sans-serif",
}

// ── Glass card base style ─────────────────────────────────────────────────────
const glass = {
  background: T.surfaceHigh,
  backdropFilter: T.surfaceHighBlur,
  WebkitBackdropFilter: T.surfaceHighBlur,
  border: `1px solid ${T.border}`,
  borderRadius: '12px',
}

// ── Slider row component ──────────────────────────────────────────────────────
function SliderRow({ label, valueLabel, value, onChange }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ color: T.onSurface, fontFamily: T.fontUI, fontSize: '12px', fontWeight: 500 }}>{label}</span>
        <span style={{ color: T.primaryContainer, fontFamily: T.fontMono, fontSize: '12px', fontWeight: 500 }}>{valueLabel}</span>
      </div>
      <input
        type="range" min={0} max={100} value={value}
        onChange={e => onChange(Number(e.target.value))}
        style={{
          width: '100%', height: '4px', borderRadius: '4px',
          background: `linear-gradient(to right, ${T.primaryContainer} ${value}%, rgba(255,255,255,0.15) ${value}%)`,
          appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer', outline: 'none',
          accentColor: T.primaryContainer,
        }}
      />
    </div>
  )
}

export default function FanLensBroadcast() {
  const {
    homeTeam, awayTeam, sport, matchSession,
    commentaryData, buildingNotes, buildStatus, buildProgress,
    liveCommentary, isConnected,
    sendTacticalDetection,
    prepareNotes,
    updateSettings, updateLanguage,
    addCommentaryItem, updateDetection,
  } = useLiveSession()

  // Settings sliders
  const [bias, setBias] = useState(50)
  const [excitement, setExcitement] = useState(90)
  const [knowledge, setKnowledge] = useState(65)
  const [broadcastOpen, setBroadcastOpen] = useState(true)
  const [insightOpen, setInsightOpen] = useState(true)

  // Language
  const [language, setLanguage] = useState('en')
  const [voiceEnabled, setVoiceEnabled] = useState(false)

  // Live score derived from WS messages
  const [homeScore, setHomeScore] = useState(0)
  const [awayScore, setAwayScore] = useState(0)
  const [matchMinute, setMatchMinute] = useState(null)

  // SplitScreen Q&A state
  const [splitActive, setSplitActive] = useState(false)
  const [qaAnswer, setQaAnswer] = useState(null)
  const [isDismissing, setIsDismissing] = useState(false)

  // Text input Q&A state
  const [textInputOpen, setTextInputOpen] = useState(false)
  const [textQuery, setTextQuery] = useState('')

  // Current video URL playing in VideoCanvas (for SplitScreen left panel)
  const [canvasVideoUrl, setCanvasVideoUrl] = useState(null)
  const [canvasVideoTime, setCanvasVideoTime] = useState(0)
  const [streamingStatus, setStreamingStatus] = useState({
    isStreaming: false,
    wsReady: false,
    connectionState: 'disconnected',
    framesSent: 0,
    videoReady: false,
    hasVideo: false,
  })

  const pendingQuestionRef = useRef(null)
  const lastSpokenAnswerRef = useRef(null)
  const browserVoice = useBrowserSpeechSynthesis({
    enabled: voiceEnabled,
    lang: language === 'es' ? 'es-ES' : 'en-US',
    rate: 1,
    pitch: 1,
    volume: 1,
  })

  // Sync settings to WS
  const pushSettings = useCallback((b, e, k) => {
    updateSettings({
      bias: (50 - b) / 50,          // -1 home .. +1 away
      excitement: e / 100,
      knowledge_depth: k / 100,
    })
  }, [updateSettings])

  // Parse game state from latest WS commentary
  useEffect(() => {
    const latest = liveCommentary[0]
    if (!latest) return
    const gs = latest.gameState || latest.game_state
    if (!gs) return
    if (typeof gs.home_score === 'number') setHomeScore(gs.home_score)
    if (typeof gs.away_score === 'number') setAwayScore(gs.away_score)
    if (gs.match_minute != null) setMatchMinute(gs.match_minute)
  }, [liveCommentary])

  // Listen for Q&A answers from WS
  useEffect(() => {
    const handle = (e) => {
      if (isDismissing) return
      const detail = { ...e.detail }
      if (detail.source === 'streaming_vlm') {
        detail.source = 'video_qa'
      }
      if (!detail.question && pendingQuestionRef.current) {
        detail.question = pendingQuestionRef.current
      }
      detail.analyzing = false
      pendingQuestionRef.current = null
      setQaAnswer(detail)
      setSplitActive(true)
      const answerText = detail.text || detail.answer || detail.commentary
      if (answerText && answerText !== lastSpokenAnswerRef.current) {
        lastSpokenAnswerRef.current = answerText
        browserVoice.speak(answerText)
      }
    }
    window.addEventListener('pitchsideai:qa_answer', handle)
    return () => window.removeEventListener('pitchsideai:qa_answer', handle)
  }, [browserVoice, isDismissing])

  const handleDismiss = useCallback(() => {
    setIsDismissing(true)
    setSplitActive(false)
    setQaAnswer(null)
    browserVoice.cancel()
    window.dispatchEvent(new CustomEvent('pitchsideai:split_resolved', { detail: { dismissed: true } }))
    setTimeout(() => setIsDismissing(false), 300)
  }, [browserVoice])

  const submitFanQuestion = useCallback((q) => {
    const text = q.trim()
    if (!text) return
    if (streamingStatus.hasVideo || streamingStatus.videoReady || streamingStatus.wsReady) {
      pendingQuestionRef.current = text
      setQaAnswer({ text: 'Watching the current video moment...', source: 'video_qa', analyzing: true, question: text })
      setSplitActive(true)
      window.dispatchEvent(new CustomEvent('pitchsideai:streaming_query', { detail: { text } }))
      return
    }
    setQaAnswer({
      text: 'Upload your own match footage first so Fan Lens can answer from the video. Team context and broadcast notes can be prepared before upload.',
      source: 'system',
      question: text,
    })
    setSplitActive(true)
  }, [streamingStatus.hasVideo, streamingStatus.videoReady, streamingStatus.wsReady])

  const handleTextQuerySubmit = useCallback(() => {
    const q = textQuery.trim()
    if (!q) return
    submitFanQuestion(q)
    setTextQuery('')
    setTextInputOpen(false)
  }, [textQuery, submitFanQuestion])

  const shortName = (t, n) => (t || n).slice(0, 3).toUpperCase()
  const hasPreparedNotes = buildStatus === 'ready' && Boolean(commentaryData)
  const hasUsableTeams = homeTeam !== 'Home Team' && awayTeam !== 'Away Team'
  const noteProgressValue = Number.parseFloat(buildProgress)
  const noteProgress =
    Number.isFinite(noteProgressValue)
      ? `${(Math.max(0, Math.min(100, noteProgressValue * 100))).toFixed(1)}%`
      : buildProgress || 'Preparing...'
  const fanLensAiReady = isConnected || streamingStatus.wsReady || streamingStatus.hasVideo || streamingStatus.videoReady

  const handlePrepareNotes = () => {
    if (!buildingNotes && hasUsableTeams) {
      prepareNotes(homeTeam, awayTeam)
    }
  }

  const handleVideoReady = useCallback((url) => {
    setCanvasVideoUrl(url)
  }, [])

  const handleStreamingStatus = useCallback((status) => {
    setStreamingStatus(status)
    if (Number.isFinite(status.currentTime)) {
      setCanvasVideoTime(status.currentTime)
    }
  }, [])

  const handleTacticalDetection = useCallback((analysis) => {
    updateDetection(analysis)
    sendTacticalDetection(analysis)
  }, [sendTacticalDetection, updateDetection])

  const handleVideoCommentary = useCallback((msg) => {
    if (msg.type === 'commentary') addCommentaryItem(msg)
  }, [addCommentaryItem])

  return (
    <FanLensLayout
      splitScreen={
        <SplitScreen
          answer={qaAnswer}
          isActive={splitActive}
          onDismiss={handleDismiss}
          liveVideoUrl={canvasVideoUrl}
          isAnalyzing={Boolean(qaAnswer?.analyzing)}
          clipQuestion={qaAnswer?.question || ''}
          liveVideoTime={canvasVideoTime}
        />
      }
      videoOverlays={null}
      triviaCards={
        /* ── AI Insight trivia card — w-80 bottom-left (spec) ── */
        <div
          style={{
            ...glass,
            padding: '16px', width: '320px', display: 'flex', flexDirection: 'column', gap: '8px',
            position: 'relative', overflow: 'hidden',
            boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
          }}
        >
          {/* AI glow border */}
          <div style={{ position: 'absolute', inset: 0, border: `1px solid rgba(195,244,0,0.15)`, borderRadius: '12px', pointerEvents: 'none' }} />
          <div
            onClick={() => setInsightOpen(o => !o)}
            style={{ display: 'flex', alignItems: 'center', gap: '8px', color: T.primaryContainer, cursor: 'pointer', userSelect: 'none' }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>lightbulb</span>
            <span style={{ fontFamily: T.fontMono, fontSize: '12px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', flex: 1 }}>AI INSIGHT</span>
            <span className="material-symbols-outlined" style={{ fontSize: '16px', transition: 'transform 0.2s', transform: insightOpen ? 'rotate(0deg)' : 'rotate(-90deg)' }}>expand_more</span>
          </div>
          {insightOpen && liveCommentary[0]?.text ? (
            <>
              <p style={{ color: T.onSurface, fontFamily: T.fontUI, fontSize: '14px', lineHeight: '20px', margin: 0 }}>
                {liveCommentary[0].text.slice(0, 160)}{liveCommentary[0].text.length > 160 ? '…' : ''}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px' }}>
                <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: T.primaryContainer, animation: 'pulse 2s infinite' }} />
                <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: `rgba(195,244,0,0.4)` }} />
                <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: `rgba(195,244,0,0.4)` }} />
              </div>
            </>
          ) : insightOpen ? (
            <>
              <h3 style={{ color: T.onSurface, fontFamily: T.fontUI, fontSize: '16px', lineHeight: '22px', fontWeight: 700, margin: 0 }}>
                {hasUsableTeams ? `${homeTeam} vs ${awayTeam}` : 'Match context not set'}
              </h3>
              <p style={{ color: T.onSurfaceVar, fontFamily: T.fontUI, fontSize: '13px', lineHeight: '19px', margin: 0 }}>
                {streamingStatus.hasVideo
                  ? 'Footage is loaded. Start commentary to analyze the clip.'
                  : 'Upload footage you have the right to use for video-aware commentary and Q&A.'}
              </p>
              <div style={{ display: 'grid', gap: '6px', marginTop: '4px' }}>
                {[
                  { label: 'Team context', value: hasUsableTeams ? 'Ready' : 'Sample' },
                  { label: 'Broadcast notes', value: hasPreparedNotes ? 'Ready' : buildingNotes ? noteProgress : 'Not generated' },
                  { label: 'Video analysis', value: streamingStatus.hasVideo ? 'Footage loaded' : 'Upload required' },
                ].map((row) => (
                  <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', color: T.onSurfaceVar, fontFamily: T.fontMono, fontSize: '11px' }}>
                    <span>{row.label}</span>
                    <span style={{ color: row.value === 'Ready' || row.value === 'Footage loaded' ? T.primaryContainer : T.onSurfaceVar }}>{row.value}</span>
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={handlePrepareNotes}
                disabled={!hasUsableTeams || buildingNotes || hasPreparedNotes}
                style={{
                  marginTop: '6px',
                  width: '100%',
                  minHeight: '34px',
                  borderRadius: '6px',
                  border: `1px solid ${hasPreparedNotes ? 'rgba(195,244,0,0.35)' : T.border}`,
                  background: hasPreparedNotes ? 'rgba(195,244,0,0.08)' : 'rgba(255,255,255,0.06)',
                  color: hasPreparedNotes ? T.primaryContainer : T.onSurface,
                  fontFamily: T.fontMono,
                  fontSize: '11px',
                  fontWeight: 700,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  cursor: !hasUsableTeams || buildingNotes || hasPreparedNotes ? 'default' : 'pointer',
                  opacity: !hasUsableTeams ? 0.5 : 1,
                  pointerEvents: 'auto',
                }}
              >
                {hasPreparedNotes ? 'Notes Ready' : buildingNotes ? 'Generating Notes' : 'Generate Notes'}
              </button>
            </>
          ) : null}
        </div>
      }
      broadcastEngine={
        <>
          {/* ── Broadcast Engine glass card — w-72 ── */}
          <div
            style={{
              ...glass,
              padding: '16px', width: '288px', display: 'flex', flexDirection: 'column', gap: '14px',
              position: 'relative', overflow: 'hidden',
              boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
            }}
          >
            {/* Subtle AI glow */}
            <div style={{ position: 'absolute', inset: 0, border: `1px solid rgba(195,244,0,0.08)`, borderRadius: '12px', pointerEvents: 'none' }} />

            {/* Header */}
            <div
              onClick={() => setBroadcastOpen(o => !o)}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', color: T.onSurfaceVar, borderBottom: broadcastOpen ? `1px solid ${T.borderDim}` : 'none', paddingBottom: broadcastOpen ? '10px' : '0', cursor: 'pointer', userSelect: 'none' }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>tune</span>
              <span style={{ fontFamily: T.fontMono, fontSize: '12px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', flex: 1 }}>BROADCAST ENGINE</span>
              <span className="material-symbols-outlined" style={{ fontSize: '16px', transition: 'transform 0.2s', transform: broadcastOpen ? 'rotate(0deg)' : 'rotate(-90deg)' }}>expand_more</span>
            </div>

            {/* Sliders */}
            {broadcastOpen && <>
            <SliderRow
              label="Bias" value={bias}
              valueLabel={bias > 60 ? 'Home' : bias < 40 ? 'Away' : 'Neutral'}
              onChange={(v) => { setBias(v); pushSettings(v, excitement, knowledge) }}
            />
            <SliderRow
              label="Excitement" value={excitement}
              valueLabel={excitement > 70 ? 'High' : excitement < 40 ? 'Calm' : 'Balanced'}
              onChange={(v) => { setExcitement(v); pushSettings(bias, v, knowledge) }}
            />
            <SliderRow
              label="Knowledge" value={knowledge}
              valueLabel={knowledge > 70 ? 'Tactical' : knowledge < 40 ? 'Casual' : 'Mixed'}
              onChange={(v) => { setKnowledge(v); pushSettings(bias, excitement, v) }}
            />
            </>}
          </div>

          {/* ── Mic/text button row ── */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
            {/* Pill label */}
            <div style={{
              ...glass, borderRadius: '999px',
              padding: '8px 16px', color: T.primaryContainer,
              fontFamily: T.fontMono, fontSize: '12px', fontWeight: 700, letterSpacing: '0.1em',
              textTransform: 'uppercase', whiteSpace: 'nowrap',
              boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
            }}>
              Ask AI
            </div>

            {/* Text input — shown when toggle is open */}
            {textInputOpen && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', pointerEvents: 'auto' }}>
                <input
                  data-testid="text-query-input"
                  type="text"
                  value={textQuery}
                  onChange={e => setTextQuery(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleTextQuerySubmit() }}
                  placeholder="Ask about the match…"
                  autoFocus
                  aria-label="Type your question"
                  style={{
                    width: '200px',
                    background: 'rgba(255,255,255,0.07)',
                    border: `1px solid ${T.primaryContainer}`,
                    borderRadius: '8px',
                    color: T.onSurface,
                    fontFamily: T.fontUI,
                    fontSize: '13px',
                    padding: '8px 12px',
                    outline: 'none',
                    pointerEvents: 'auto',
                  }}
                />
                <button
                  data-testid="text-query-submit"
                  onClick={handleTextQuerySubmit}
                  aria-label="Send question"
                  disabled={!textQuery.trim()}
                  style={{
                    width: '36px', height: '36px',
                    background: textQuery.trim() ? T.primaryContainer : 'rgba(255,255,255,0.07)',
                    border: 'none', borderRadius: '8px',
                    color: textQuery.trim() ? T.onPrimary : T.onSurfaceVar,
                    cursor: textQuery.trim() ? 'pointer' : 'default',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'background 0.15s, color 0.15s',
                    pointerEvents: 'auto',
                  }}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>send</span>
                </button>
              </div>
            )}

            {/* Keyboard icon toggle */}
            <button
              data-testid="text-query-toggle"
              onClick={() => setTextInputOpen(v => {
                if (v) setTextQuery('')  // clear draft only when closing
                return !v
              })}
              aria-label="Ask AI by text"
              aria-pressed={textInputOpen}
              style={{
                width: '48px', height: '48px',
                borderRadius: '50%',
                background: textInputOpen ? T.primaryContainer : 'rgba(255,255,255,0.08)',
                border: `1px solid ${textInputOpen ? T.primaryContainer : T.border}`,
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'background 0.15s, border-color 0.15s',
                pointerEvents: 'auto',
              }}
            >
              <span className="material-symbols-outlined" style={{
                fontSize: '22px',
                color: textInputOpen ? T.onPrimary : T.onSurface,
              }}>
                keyboard
              </span>
            </button>

            {/* Browser TTS toggle */}
            <button
              data-testid="voice-output-toggle"
              onClick={() => {
                setVoiceEnabled(v => {
                  const next = !v
                  if (!next) browserVoice.cancel()
                  return next
                })
              }}
              aria-label={voiceEnabled ? 'Turn answer voice off' : 'Turn answer voice on'}
              aria-pressed={voiceEnabled}
              disabled={!browserVoice.isSupported}
              title={
                browserVoice.isSupported
                  ? voiceEnabled ? 'Answer voice on' : 'Answer voice off'
                  : 'Speech synthesis is not supported in this browser'
              }
              style={{
                width: '48px', height: '48px',
                borderRadius: '50%',
                background: voiceEnabled ? T.primaryContainer : 'rgba(255,255,255,0.08)',
                border: `1px solid ${voiceEnabled ? T.primaryContainer : T.border}`,
                cursor: browserVoice.isSupported ? 'pointer' : 'not-allowed',
                opacity: browserVoice.isSupported ? 1 : 0.45,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'background 0.15s, border-color 0.15s',
                pointerEvents: 'auto',
              }}
            >
              <span className="material-symbols-outlined" style={{
                fontSize: '22px',
                color: voiceEnabled ? T.onPrimary : T.onSurface,
              }}>
                {browserVoice.isSpeaking ? 'record_voice_over' : voiceEnabled ? 'volume_up' : 'volume_off'}
              </span>
            </button>

            {/* Mic button — inline in the flex row */}
            <MicButton
              onQuestionSubmit={({ text }) => submitFanQuestion(text)}
              isAiReady={fanLensAiReady}
              isSplitScreenActive={splitActive}
              inline
            />
          </div>
        </>
      }
    >
      {/* Video Canvas fills the full video area */}
      <VideoCanvas
        matchSession={matchSession}
        homeTeam={homeTeam}
        awayTeam={awayTeam}
        sport={sport}
        onVideoReady={handleVideoReady}
        onStreamingStatus={handleStreamingStatus}
        onTacticalDetection={handleTacticalDetection}
        onCommentary={handleVideoCommentary}
        startLabel="Start Video Analysis"
      />
    </FanLensLayout>
  )
}
