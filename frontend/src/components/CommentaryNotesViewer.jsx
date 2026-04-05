import { useState } from 'react'

function renderInlineFormatting(text) {
    const segments = text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean)

    return segments.map((segment, index) => {
        if (segment.startsWith('**') && segment.endsWith('**')) {
            return <strong key={`${segment}-${index}`}>{segment.slice(2, -2)}</strong>
        }
        return <span key={`${segment}-${index}`}>{segment}</span>
    })
}

function renderMarkdown(markdown) {
    const lines = markdown.split('\n')
    const blocks = []
    let index = 0

    const isSpecialLine = (line) => {
        const trimmed = line.trim()
        return (
            trimmed.startsWith('#') ||
            trimmed.startsWith('- ') ||
            trimmed.startsWith('|') ||
            /^---+$/.test(trimmed)
        )
    }

    while (index < lines.length) {
        const rawLine = lines[index]
        const trimmed = rawLine.trim()

        if (!trimmed) {
            index += 1
            continue
        }

        if (/^---+$/.test(trimmed)) {
            blocks.push(<hr key={`rule-${index}`} className="md-rule" />)
            index += 1
            continue
        }

        const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/)
        if (headingMatch) {
            const level = headingMatch[1].length
            const text = headingMatch[2]
            const Tag = `h${Math.min(level, 6)}`
            blocks.push(
                <Tag key={`heading-${index}`} className={`md-heading md-h${level}`}>
                    {renderInlineFormatting(text)}
                </Tag>
            )
            index += 1
            continue
        }

        if (trimmed.startsWith('|')) {
            const tableLines = []
            while (index < lines.length && lines[index].trim().startsWith('|')) {
                tableLines.push(lines[index].trim())
                index += 1
            }

            const rows = tableLines
                .map((line) => line.split('|').map((cell) => cell.trim()).filter(Boolean))
                .filter((row) => row.length > 0)

            const header = rows[0] || []
            const body = rows.slice(1).filter(
                (row) => !row.every((cell) => /^:?-{3,}:?$/.test(cell))
            )

            blocks.push(
                <div key={`table-${index}`} className="md-table-wrapper">
                    <table className="md-table">
                        {header.length > 0 && (
                            <thead>
                                <tr>
                                    {header.map((cell, cellIndex) => (
                                        <th key={`th-${cellIndex}`}>{renderInlineFormatting(cell)}</th>
                                    ))}
                                </tr>
                            </thead>
                        )}
                        {body.length > 0 && (
                            <tbody>
                                {body.map((row, rowIndex) => (
                                    <tr key={`tr-${rowIndex}`}>
                                        {row.map((cell, cellIndex) => (
                                            <td key={`td-${rowIndex}-${cellIndex}`}>
                                                {renderInlineFormatting(cell)}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        )}
                    </table>
                </div>
            )
            continue
        }

        if (trimmed.startsWith('- ')) {
            const items = []
            while (index < lines.length && lines[index].trim().startsWith('- ')) {
                items.push(lines[index].trim().slice(2))
                index += 1
            }

            blocks.push(
                <ul key={`list-${index}`} className="md-list">
                    {items.map((item, itemIndex) => (
                        <li key={`item-${itemIndex}`} className="md-list-item">
                            {renderInlineFormatting(item)}
                        </li>
                    ))}
                </ul>
            )
            continue
        }

        const paragraphLines = [trimmed]
        index += 1
        while (index < lines.length && lines[index].trim() && !isSpecialLine(lines[index])) {
            paragraphLines.push(lines[index].trim())
            index += 1
        }

        blocks.push(
            <p key={`paragraph-${index}`} className="md-paragraph">
                {renderInlineFormatting(paragraphLines.join(' '))}
            </p>
        )
    }

    return blocks
}

export default function CommentaryNotesViewer({ data, liveDetection }) {
    const [activeTab, setActiveTab] = useState('markdown') // 'markdown' | 'tactical' | 'json'

    if (!data) return null

    const {
        match,
        markdown_notes,
        json_structure,
        preparation_time_ms,
        agents_completed,
        errors = [],
        warnings = [],
    } = data

    const tacticalBrief = json_structure?.tactical_brief
    const qualityMetrics = json_structure?.quality_metrics

    return (
        <div className="commentary-viewer">
            {/* Header */}
            <div className="commentary-header">
                <div className="commentary-title">
                    <span className="title-icon">📝</span>
                    <h2>Professional Commentary Notes</h2>
                    <span className="title-match">{match}</span>
                </div>
                <div className="commentary-stats">
                    <div className="stat">
                        <span className="stat-label">Generated in</span>
                        <span className="stat-value">{(preparation_time_ms / 1000).toFixed(1)}s</span>
                    </div>
                    <div className="stat">
                        <span className="stat-label">Agents</span>
                        <span className="stat-value">{agents_completed}</span>
                    </div>
                </div>
            </div>

            {/* Tab Selector */}
            <div className="commentary-tabs">
                <button
                    className={`tab-btn ${activeTab === 'markdown' ? 'active' : ''}`}
                    onClick={() => setActiveTab('markdown')}
                >
                    📄 Markdown
                </button>
                <button
                    className={`tab-btn ${activeTab === 'tactical' ? 'active' : ''}`}
                    onClick={() => setActiveTab('tactical')}
                >
                    🎯 Tactical Brief
                </button>
                <button
                    className={`tab-btn ${activeTab === 'json' ? 'active' : ''}`}
                    onClick={() => setActiveTab('json')}
                >
                    📊 Structured Data
                </button>
            </div>

            {/* Markdown View */}
            {activeTab === 'markdown' && (
                <div className="commentary-content">
                    <div className="markdown-preview">{renderMarkdown(markdown_notes)}</div>

                    {/* Export Button */}
                    <div className="commentary-actions">
                        <button
                            className="btn btn-secondary"
                            onClick={() => {
                                const element = document.createElement('a')
                                element.setAttribute(
                                    'href',
                                    'data:text/plain;charset=utf-8,' +
                                        encodeURIComponent(markdown_notes)
                                )
                                element.setAttribute('download', `commentary-${Date.now()}.md`)
                                element.style.display = 'none'
                                document.body.appendChild(element)
                                element.click()
                                document.body.removeChild(element)
                            }}
                        >
                            ⬇️ Download Markdown
                        </button>
                        <button
                            className="btn btn-secondary"
                            onClick={() => navigator.clipboard.writeText(markdown_notes)}
                        >
                            📋 Copy to Clipboard
                        </button>
                    </div>
                </div>
            )}

            {/* Tactical View */}
            {activeTab === 'tactical' && (
                <div className="commentary-content">
                    <div className="tactical-brief-grid">
                        <section className="tactical-panel tactical-panel-hero">
                            <div className="tactical-panel-label">Match Shape</div>
                            <h3>{tacticalBrief?.summary || 'Tactical brief unavailable for this match.'}</h3>
                            {qualityMetrics && (
                                <div className="tactical-meta-row">
                                    <span className="tactical-pill">Completeness {Math.round((qualityMetrics.data_completeness || 0) * 100)}%</span>
                                    <span className="tactical-pill">Sources {qualityMetrics.sources_used || 0}</span>
                                </div>
                            )}
                        </section>

                        {liveDetection && (
                            <section className="tactical-panel">
                                <div className="tactical-panel-label">Live Frame Read</div>
                                <h4>{liveDetection.tactical_label}</h4>
                                <p>{liveDetection.key_observation || 'No live observation available.'}</p>
                                <div className="tactical-panel-footnote">
                                    {liveDetection.confidence != null
                                        ? `${Math.round(liveDetection.confidence * 100)}% confidence`
                                        : 'Confidence unavailable'}
                                </div>
                                {liveDetection.actionable_insight && (
                                    <p className="tactical-inline-note">{liveDetection.actionable_insight}</p>
                                )}
                            </section>
                        )}

                        <section className="tactical-panel">
                            <div className="tactical-panel-label">Zone Edges</div>
                            <ul className="tactical-list">
                                {(tacticalBrief?.zone_edges || ['Zone-level edge unavailable.']).map((item) => (
                                    <li key={item}>{item}</li>
                                ))}
                            </ul>
                        </section>

                        <section className="tactical-panel">
                            <div className="tactical-panel-label">Pressure Points</div>
                            <ul className="tactical-list">
                                {(tacticalBrief?.pressure_points || ['No verified pressure points yet.']).map((item) => (
                                    <li key={item}>{item}</li>
                                ))}
                            </ul>
                        </section>

                        <section className="tactical-panel">
                            <div className="tactical-panel-label">Home Plan</div>
                            <p>{tacticalBrief?.home_plan || 'Home-side plan unavailable.'}</p>
                        </section>

                        <section className="tactical-panel">
                            <div className="tactical-panel-label">Away Plan</div>
                            <p>{tacticalBrief?.away_plan || 'Away-side plan unavailable.'}</p>
                        </section>

                        <section className="tactical-panel tactical-panel-wide">
                            <div className="tactical-panel-label">Commentary Angles</div>
                            <ul className="tactical-list">
                                {(tacticalBrief?.commentary_angles || ['No prepared angles available.']).map((item) => (
                                    <li key={item}>{item}</li>
                                ))}
                            </ul>
                        </section>
                    </div>
                </div>
            )}

            {/* JSON View */}
            {activeTab === 'json' && (
                <div className="commentary-content">
                    <div className="json-preview">
                        <pre>{JSON.stringify(json_structure, null, 2)}</pre>
                    </div>

                    {/* Export Button */}
                    <div className="commentary-actions">
                        <button
                            className="btn btn-secondary"
                            onClick={() => {
                                const element = document.createElement('a')
                                element.setAttribute(
                                    'href',
                                    'data:application/json;charset=utf-8,' +
                                        encodeURIComponent(JSON.stringify(json_structure, null, 2))
                                )
                                element.setAttribute('download', `commentary-${Date.now()}.json`)
                                element.style.display = 'none'
                                document.body.appendChild(element)
                                element.click()
                                document.body.removeChild(element)
                            }}
                        >
                            ⬇️ Download JSON
                        </button>
                        <button
                            className="btn btn-secondary"
                            onClick={() => navigator.clipboard.writeText(JSON.stringify(json_structure, null, 2))}
                        >
                            📋 Copy to Clipboard
                        </button>
                    </div>
                </div>
            )}

            {/* Errors & Warnings */}
            {(errors.length > 0 || warnings.length > 0) && (
                <div className="commentary-alerts">
                    {errors.map((err, i) => (
                        <div key={i} className="alert alert-error">
                            ❌ {err}
                        </div>
                    ))}
                    {warnings.map((warn, i) => (
                        <div key={i} className="alert alert-warning">
                            ⚠️ {warn}
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
