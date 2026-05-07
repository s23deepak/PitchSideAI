/**
 * CommentatorDashboard — matches .bmad/screens/commentator-dashboard.html
 *
 * Adds to CommentatorLayout:
 *   - Video header: LIVE • dot + match time + score (MCI 2 - 1 ARS)
 *   - Stats strip: Possession % | Shots (on target) | xG Momentum
 *   - Gold-highlighted active teleprompter line (passed through to Teleprompter)
 */
import { useState, useEffect } from 'react'
import { useLiveSession } from '@/contexts/LiveSessionContext'
import TopNavBar from '@/components/TopNavBar'
import VideoCanvas from '@/components/VideoCanvas'
import Teleprompter from '@/components/Teleprompter'
import { CommentatorLayout } from '../layouts/CommentatorLayout'

const FONT_MONO = "'Space Grotesk', monospace"
const FONT_UI   = "'Inter', system-ui, sans-serif"
const LIME      = '#c3f400'
const GOLD      = '#e9c400'

export default function CommentatorDashboard() {
  const {
    homeTeam, awayTeam, sport, matchSession,
    commentaryData, buildingNotes, buildStatus, buildProgress, prepareNotes,
    liveCommentary, detection,
    sendTacticalDetection, updateSettings, updateLanguage,
    addCommentaryItem, updateDetection,
  } = useLiveSession()

  const [matchTime, setMatchTime] = useState('67:12')
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
    if (gs.match_minute != null) setMatchTime(`${gs.match_minute}:00`)
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
        <span style={{ fontFamily: FONT_MONO, fontSize: '14px', color: 'rgba(197,201,174,0.8)', marginLeft: '8px' }}>
          {matchTime}
        </span>
      </div>

      {/* Score pill */}
      <div style={{
        background: 'rgba(32,32,31,0.80)', backdropFilter: 'blur(8px)',
        border: '1px solid rgba(255,255,255,0.10)', borderRadius: '6px',
        padding: '4px 12px', fontFamily: FONT_MONO, fontSize: '14px', fontWeight: 500,
      }}>
        <span style={{ fontWeight: 700, color: '#e5e2e1' }}>{short(homeTeam, 'HME')}</span>
        <span style={{ color: '#e5e2e1', margin: '0 6px' }}>{homeScore} - {awayScore}</span>
        <span style={{ fontWeight: 700, color: '#e5e2e1' }}>{short(awayTeam, 'AWY')}</span>
      </div>
    </div>
  )

  // ── Stats strip below video ───────────────────────────────────────────────
  const statsStrip = (
    <div style={{
      height: '56px', background: 'rgba(53,53,53,0.50)',
      borderTop: '1px solid rgba(255,255,255,0.05)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-around', padding: '0 16px',
    }}>
      {[
        { label: 'Possession', value: `${homeScore > awayScore ? 62 : 45}% - ${homeScore > awayScore ? 38 : 55}%` },
        { label: 'Shots (Target)', value: '14(6) - 8(3)' },
        { label: 'xG Momentum', value: homeScore > awayScore ? `${short(homeTeam, 'HME')} Surge` : 'Even', color: GOLD },
      ].map(({ label, value, color }) => (
        <div key={label} style={{ textAlign: 'center' }}>
          <div style={{ fontFamily: FONT_MONO, fontSize: '10px', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'rgba(197,201,174,0.8)', marginBottom: '2px' }}>
            {label}
          </div>
          <div style={{ fontFamily: FONT_MONO, fontSize: '14px', fontWeight: 500, color: color || LIME }}>
            {value}
          </div>
        </div>
      ))}
    </div>
  )

  return (
    <>
      <TopNavBar />
      <CommentatorLayout
        liveHeader={liveHeader}
        statsStrip={statsStrip}
        videoCanvas={
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
        }
        teleprompter={
          <Teleprompter
            notesData={commentaryData}
            buildingNotes={buildingNotes}
            buildProgress={buildProgress}
            buildStatus={buildStatus}
            onGenerateNotes={prepareNotes}
            liveDetection={detection}
          />
        }
      />
    </>
  )
}
