import * as React from 'react'
import axios from 'axios'

// SessionGuard: persists UI state across refresh and tab close (localStorage),
// but invalidates it when the backend restarts (project/console closed) by
// comparing a per-boot server id.
const SERVER_ID_KEY = 'clipforge-server-id'
const PERSIST_KEY = 'clipforge-session'

export default function SessionGuard() {
  const done = React.useRef(false)
  React.useEffect(() => {
    if (done.current) return
    done.current = true
    let cancelled = false
    axios
      .get('/api/session/server-id')
      .then(({ data }) => {
        if (cancelled) return
        const current: string | undefined = data?.server_id
        if (!current) return
        const seen = localStorage.getItem(SERVER_ID_KEY)
        if (seen && seen !== current) {
          localStorage.removeItem(PERSIST_KEY)
          localStorage.setItem(SERVER_ID_KEY, current)
          window.location.reload()
          return
        }
        localStorage.setItem(SERVER_ID_KEY, current)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  return null
}
