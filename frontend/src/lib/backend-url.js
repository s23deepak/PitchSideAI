const BACKEND_BASE = import.meta.env.VITE_BACKEND_URL || import.meta.env.VITE_API_URL || ''

export function backendUrl(path) {
    return `${BACKEND_BASE}${path}`
}

export function backendWsUrl(path) {
    if (BACKEND_BASE) {
        return `${BACKEND_BASE.replace(/^http/, 'ws')}${path}`
    }
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${protocol}://${window.location.host}${path}`
}
