import { useState } from 'react'

export default function CommentaryNotesViewer({ data }) {
    const [activeTab, setActiveTab] = useState('markdown') // 'markdown' or 'json'

    if (!data) return null

    const {
        match,
        markdown_notes,
        json_structure,
        preparation_time_ms,
        agents_completed,
        errors,
        warnings,
    } = data

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
                    className={`tab-btn ${activeTab === 'json' ? 'active' : ''}`}
                    onClick={() => setActiveTab('json')}
                >
                    📊 Structured Data
                </button>
            </div>

            {/* Markdown View */}
            {activeTab === 'markdown' && (
                <div className="commentary-content">
                    <div className="markdown-preview">
                        {markdown_notes.split('\n').map((line, idx) => {
                            if (line.startsWith('# ')) {
                                return (
                                    <h1 key={idx} className="md-h1">
                                        {line.replace('# ', '')}
                                    </h1>
                                )
                            }
                            if (line.startsWith('## ')) {
                                return (
                                    <h2 key={idx} className="md-h2">
                                        {line.replace('## ', '')}
                                    </h2>
                                )
                            }
                            if (line.startsWith('### ')) {
                                return (
                                    <h3 key={idx} className="md-h3">
                                        {line.replace('### ', '')}
                                    </h3>
                                )
                            }
                            if (line.startsWith('- ')) {
                                return (
                                    <li key={idx} className="md-list-item">
                                        {line.replace('- ', '')}
                                    </li>
                                )
                            }
                            if (line.startsWith('| ')) {
                                return (
                                    <div key={idx} className="md-table-row">
                                        {line}
                                    </div>
                                )
                            }
                            if (line.startsWith('**') || line.includes('**')) {
                                return (
                                    <p key={idx} className="md-bold">
                                        {line.replace(/\*\*/g, '')}
                                    </p>
                                )
                            }
                            if (line.trim().length > 0) {
                                return (
                                    <p key={idx} className="md-paragraph">
                                        {line}
                                    </p>
                                )
                            }
                            return <div key={idx} className="md-spacing" />
                        })}
                    </div>

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
