const SAMPLE_NOTES = [
    { category: 'form', text: 'Manchester City — 4W 1D in last 5. Haaland on a 6-game scoring streak.' },
    { category: 'stats', text: 'Arsenal top xG in Premier League this season (2.3/game). Saka leads assists (12).' },
    { category: 'h2h', text: 'Last 5 H2H: City 3W, Arsenal 2W. Arsenal unbeaten at home vs City since 2021.' },
    { category: 'tactics', text: 'Arteta favors 4-3-3 high press. City counters with quick transitions via De Bruyne.' },
]

export default function MatchNotes({ notes, loading }) {
    const displayNotes = notes.length > 0 ? notes : []

    return (
        <div className="match-notes">
            <div className="notes-header">
                <div className="notes-title">📋 Commentator's Brief</div>
                {loading && <span className="spinner" style={{ color: 'var(--accent-blue)' }} />}
            </div>

            {displayNotes.length === 0 && !loading && (
                <div className="notes-empty">
                    <span style={{ fontSize: 28 }}>📋</span>
                    <span>Build Match Notes to populate the brief.</span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        Enter teams above and click "Build Notes"
                    </span>
                </div>
            )}

            {loading && (
                <>
                    {SAMPLE_NOTES.map((n, i) => (
                        <div key={i} className="note-card" style={{ opacity: 0.3 }}>
                            <span className={`note-category ${n.category}`}>{n.category}</span>
                            <div className="note-text" style={{ height: 14, background: 'var(--border)', borderRadius: 4, marginTop: 6 }} />
                        </div>
                    ))}
                </>
            )}

            {displayNotes.map((note, i) => (
                <div key={i} className="note-card">
                    <span className={`note-category ${note.category || 'stats'}`}>
                        {note.category || 'Research'}
                    </span>
                    <div className="note-text">{note.text}</div>
                </div>
            ))}
        </div>
    )
}
