/**
 * CommentatorDashboard — Midnight Stadium broadcast dashboard
 *
 * Adds to CommentatorLayout:
 *   - Video header: LIVE • dot + match time + score from live game state
 *   - Stats strip: Possession % | Shots (on target) | xG Momentum
 *   - Gold-highlighted active teleprompter line (passed through to Teleprompter)
 */
import { useState, useEffect } from 'react'
import { useLiveSession } from '@/contexts/LiveSessionContext'
import VideoCanvas from '@/components/VideoCanvas'
import Teleprompter from '@/components/Teleprompter'
import { CommentatorLayout } from '../layouts/CommentatorLayout'

const FONT_MONO = "'Space Grotesk', monospace"
const FONT_UI   = "'Inter', system-ui, sans-serif"
const LIME      = '#c3f400'

export default function CommentatorDashboard() {
  const {
    homeTeam, awayTeam, sport, matchSession,
    commentaryData, buildingNotes, buildStatus, buildProgress, prepareNotes,
    liveCommentary, detection,
    sendTacticalDetection, updateSettings, updateLanguage,
    addCommentaryItem, updateDetection,
  } = useLiveSession()

  const [matchTime, setMatchTime] = useState(null)
  const [homeScore, setHomeScore] = useState(0)
  const [awayScore, setAwayScore] = useState(0)

  // Parse score from WS commentary
  useEffect(() => {
    const latest = liveCommentary[0]
    if (!latest) return
    const gs = latest.gameState || latest.game_state
    if (!gs) return
    if (typeof gs.home_score === 'number') setHomeScore(gs.home_score)
    if (typeof gs.away_score === 'number') setAwayScore(gs.away_score)
    if (gs.match_minute != null) setMatchTime(`${gs.match_minute}'`)
  }, [liveCommentary])

  const short = (t, fallback) => (t || fallback).slice(0, 3).toUpperCase()

  // ── Video header overlay (LIVE dot + time + score) ────────────────────────
  const liveHeader = (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '12px 16px', zIndex: 10,
      background: 'linear-gradient(to bottom, rgba(0,0,0,0.80) 0%, transparent 100%)',
    }}>
      {/* LIVE dot + time */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ display: 'flex', position: 'relative', width: '12px', height: '12px' }}>
          <span style={{
            position: 'absolute', inset: 0, borderRadius: '50%',
            background: '#ffb4ab', animation: 'ping 1.5s ease-in-out infinite', opacity: 0.75,
          }} />
          <span style={{ position: 'relative', borderRadius: '50%', background: '#ef4444', width: '12px', height: '12px' }} />
        </span>
        <span style={{ fontFamily: FONT_MONO, fontSize: '12px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#e5e2e1' }}>
          Live
        </span>
        {matchTime && (
          <span style={{ fontFamily: FONT_MONO, fontSize: '14px', color: 'rgba(197,201,174,0.8)', marginLeft: '8px' }}>
            {matchTime}
          </span>
        )}
      </div>

      {/* Score pill */}
      <div style={{
        background: 'rgba(32,32,31,0.80)', backdropFilter: 'blur(8px)',
        border: '1px solid rgba(255,255,255,0.10)', borderRadius: '6px',
        padding: '4px 12px', fontFamily: FONT_MONO, fontSize: '14px', fontWeight: 500,
      }}>
        <span style={{ fontWeight: 700, color: '#e5e2e1' }}>{short(homeTeam, 'HME')}</span>
        <span style={{ color: '#e5e2e1', margin: '0 6px' }}>
          {homeScore ?? 0} - {awayScore ?? 0}
        </span>
        <span style={{ fontWeight: 700, color: '#e5e2e1' }}>{short(awayTeam, 'AWY')}</span>
      </div>
    </div>
  )

  return (
    <CommentatorLayout
      liveHeader={liveHeader}
      videoCanvas={
        <VideoCanvas
          matchSession={matchSession}
          homeTeam={homeTeam}
          awayTeam={awayTeam}
          sport={sport}
          surfaceLabel="Broadcast Studio"
          uploadDescription="Upload footage you have the right to use. Broadcast Studio will pair the clip with generated notes."
          startLabel="Start Broadcast Analysis"
          onTacticalDetection={(analysis) => {
            updateDetection(analysis)
            sendTacticalDetection(analysis)
          }}
          onCommentary={(msg) => {
            if (msg.type === 'commentary') addCommentaryItem(msg)
          }}
        />
      }
      teleprompter={
        <Teleprompter
          notesData={commentaryData}
          buildingNotes={buildingNotes}
          buildProgress={buildProgress}
          buildStatus={buildStatus}
          onGenerateNotes={() => prepareNotes(homeTeam, awayTeam)}
          liveDetection={detection}
          generateLabel="Prepare Broadcast Sheet"
          progressTitle="Preparing Broadcast Sheet"
          emptyKicker="Broadcast Sheet"
          emptyTitle="Prepare the live sheet"
          emptyDescription="Build the compact sheet this studio uses during clip analysis: narrative beats, player context, tactical cues, and lines worth surfacing live."
        />
      }
    />
  )
}
