/**
 * FanLensBroadcast — matches .bmad/screens/fan-lens-broadcast.html exactly
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
import { useVideoQA } from '@/hooks/useVideoQA'
import SplitScreen from '@/components/SplitScreen'
import VideoCanvas from '@/components/VideoCanvas'
import MicButton from '@/components/MicButton'

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
    liveCommentary, isConnected,
    sendTacticalDetection, sendQuery,
    updateSettings, updateLanguage,
    addCommentaryItem, updateDetection,
  } = useLiveSession()

  // Settings sliders
  const [bias, setBias] = useState(50)
  const [excitement, setExcitement] = useState(90)
  const [knowledge, setKnowledge] = useState(65)

  // Language
  const [language, setLanguage] = useState('en')

  // Live score derived from WS messages
  const [homeScore, setHomeScore] = useState(0)
  const [awayScore, setAwayScore] = useState(0)
  const [matchMinute, setMatchMinute] = useState(null)

  // SplitScreen Q&A state
  const [splitActive, setSplitActive] = useState(false)
  const [qaAnswer, setQaAnswer] = useState(null)
  const [isDismissing, setIsDismissing] = useState(false)

  // Video Q&A hook — hides all backend complexity
  const { isAnalyzing, answer: videoAnswer, error: videoError, videoPreview, analyzeClip, reset: resetVideoQA } = useVideoQA()

  // File input ref for upload button
  const fileInputRef = useRef(null)

  // Sync settings to WS
  const pushSettings = useCallback((b, e, k) => {
    updateSettings({
      bias: (b - 50) / 50,          // -1..+1
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
      setQaAnswer(e.detail)
      setSplitActive(true)
    }
    window.addEventListener('pitchai:qa_answer', handle)
    return () => window.removeEventListener('pitchai:qa_answer', handle)
  }, [isDismissing])

  // When videoAnswer arrives from clip upload, also open split screen
  useEffect(() => {
    if (videoAnswer && !splitActive) {
      setQaAnswer({ text: videoAnswer, source: 'video_qa' })
      setSplitActive(true)
    }
  }, [videoAnswer])

  const handleDismiss = useCallback(() => {
    setIsDismissing(true)
    setSplitActive(false)
    setQaAnswer(null)
    resetVideoQA()
    window.dispatchEvent(new CustomEvent('pitchai:split_resolved', { detail: { dismissed: true } }))
    setTimeout(() => setIsDismissing(false), 300)
  }, [resetVideoQA])

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    analyzeClip(file, '', sport)
    // Preview opens split screen while analyzing
    setSplitActive(true)
    setQaAnswer({ text: '', source: 'video_qa', analyzing: true })
    e.target.value = '' // Reset so same file can be re-selected
  }

  const shortName = (t, n) => (t || n).slice(0, 3).toUpperCase()

  return (
    <FanLensLayout
      splitScreen={
        <SplitScreen
          answer={qaAnswer}
          isActive={splitActive}
          onDismiss={handleDismiss}
          videoPreview={videoPreview}
          isAnalyzing={isAnalyzing}
        />
      }
      videoOverlays={
        <>
          {/* ── Scoreboard pill — center top ── */}
          <div
            role="status"
            aria-label={`Score: ${homeTeam} ${homeScore} - ${awayScore} ${awayTeam}`}
            style={{
              ...glass,
              position: 'absolute', top: '24px', left: '50%', transform: 'translateX(-50%)',
              padding: '10px 24px', display: 'flex', alignItems: 'center', gap: '16px',
              whiteSpace: 'nowrap', pointerEvents: 'none', borderRadius: '999px',
              boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
            }}
          >
            <span style={{ color: T.onSurface, fontFamily: T.fontMono, fontSize: '14px', fontWeight: 700, letterSpacing: '0.05em' }}>
              {shortName(homeTeam, 'HME')}
            </span>
            <span style={{ color: T.primaryContainer, fontFamily: T.fontMono, fontSize: '24px', fontWeight: 700, lineHeight: 1 }}>
              {homeScore}
            </span>
            <div style={{ width: '1px', height: '20px', background: 'rgba(255,255,255,0.2)' }} />
            <span style={{ color: T.primaryContainer, fontFamily: T.fontMono, fontSize: '14px', opacity: 0.85 }}>
              {matchMinute != null ? `${matchMinute}'` : '—'}
            </span>
            <div style={{ width: '1px', height: '20px', background: 'rgba(255,255,255,0.2)' }} />
            <span style={{ color: T.onSurface, fontFamily: T.fontMono, fontSize: '24px', fontWeight: 700, lineHeight: 1 }}>
              {awayScore}
            </span>
            <span style={{ color: T.onSurface, fontFamily: T.fontMono, fontSize: '14px', fontWeight: 700, letterSpacing: '0.05em' }}>
              {shortName(awayTeam, 'AWY')}
            </span>
          </div>

          {/* ── Language toggle pill — top right ── */}
          <div
            role="group"
            aria-label="Commentary language"
            style={{
              ...glass, borderRadius: '999px',
              position: 'absolute', top: '24px', right: '24px',
              padding: '4px', display: 'flex', alignItems: 'center',
              pointerEvents: 'auto',
            }}
          >
            {['en', 'es'].map((lang) => (
              <button
                key={lang}
                aria-pressed={language === lang}
                aria-label={lang === 'en' ? 'English' : 'Spanish'}
                onClick={() => {
                  setLanguage(lang)
                  updateLanguage(lang)
                }}
                style={{
                  padding: '6px 16px', borderRadius: '999px', border: 'none', cursor: 'pointer',
                  background: language === lang ? T.primaryContainer : 'transparent',
                  color: language === lang ? T.onPrimary : T.onSurfaceVar,
                  fontFamily: T.fontMono, fontSize: '12px', fontWeight: 700, letterSpacing: '0.1em',
                  textTransform: 'uppercase', transition: 'color 0.15s, background 0.15s',
                }}
              >
                {lang.toUpperCase()}
              </button>
            ))}
          </div>
        </>
      }
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: T.primaryContainer }}>
            <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>lightbulb</span>
            <span style={{ fontFamily: T.fontMono, fontSize: '12px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase' }}>AI INSIGHT</span>
          </div>
          {liveCommentary[0]?.text ? (
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
          ) : (
            <p style={{ color: T.onSurfaceVar, fontFamily: T.fontUI, fontSize: '14px', lineHeight: '20px', margin: 0 }}>
              Waiting for match events…
            </p>
          )}
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
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: T.onSurfaceVar, borderBottom: `1px solid ${T.borderDim}`, paddingBottom: '10px' }}>
              <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>tune</span>
              <span style={{ fontFamily: T.fontMono, fontSize: '12px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase' }}>BROADCAST ENGINE</span>
            </div>

            {/* Sliders */}
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

            {/* Divider */}
            <div style={{ width: '100%', height: '1px', background: T.borderDim }} />

            {/* Video Q&A Upload */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <span style={{ fontFamily: T.fontMono, fontSize: '11px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: T.onSurfaceVar }}>ASK AI ABOUT A CLIP</span>
              <label
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                  padding: '8px 12px', borderRadius: '8px', cursor: 'pointer',
                  border: `1px dashed rgba(195,244,0,${isAnalyzing ? '0.6' : '0.35'})`,
                  background: isAnalyzing ? 'rgba(195,244,0,0.06)' : 'transparent',
                  transition: 'border-color 0.2s, background 0.2s',
                }}
                onMouseEnter={e => { if (!isAnalyzing) e.currentTarget.style.borderColor = 'rgba(195,244,0,0.7)' }}
                onMouseLeave={e => { if (!isAnalyzing) e.currentTarget.style.borderColor = 'rgba(195,244,0,0.35)' }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: '18px', color: T.primaryContainer }}>
                  {isAnalyzing ? 'hourglass_top' : 'upload_file'}
                </span>
                <span style={{ fontFamily: T.fontMono, fontSize: '12px', fontWeight: 600, color: T.primaryContainer }}>
                  {isAnalyzing ? 'Analyzing…' : 'Upload Clip for Q&A'}
                </span>
                <input
                  ref={fileInputRef}
                  type="file" accept="video/*"
                  style={{ display: 'none' }}
                  onChange={handleFileChange}
                  disabled={isAnalyzing}
                />
              </label>
              {videoError && (
                <p style={{ color: '#ffb4ab', fontFamily: T.fontUI, fontSize: '11px', margin: 0 }}>
                  {videoError}
                </p>
              )}
            </div>
          </div>

          {/* ── Mic button row — "Hold to Ask AI" pill + mic ── */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', justifyContent: 'flex-end' }}>
            {/* Pill label */}
            <div style={{
              ...glass, borderRadius: '999px',
              padding: '8px 16px', color: T.primaryContainer,
              fontFamily: T.fontMono, fontSize: '12px', fontWeight: 700, letterSpacing: '0.1em',
              textTransform: 'uppercase', whiteSpace: 'nowrap',
              boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
            }}>
              Hold to Ask AI
            </div>

            {/* Mic button */}
            <MicButton
              onQuestionSubmit={({ text }) => sendQuery(text)}
              isAiReady={isConnected}
              isSplitScreenActive={splitActive}
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
        onTacticalDetection={(analysis) => {
          updateDetection(analysis)
          sendTacticalDetection(analysis)
        }}
        onCommentary={(msg) => {
          if (msg.type === 'commentary') addCommentaryItem(msg)
        }}
      />
    </FanLensLayout>
  )
}
