import { useState, useEffect } from 'react'
import axios from 'axios'
import { useAppStore, ProcessedClip } from '../store/useAppStore'
import ProgressBar from '../components/ProgressBar'
import ScoreBreakdown from '../components/ScoreBreakdown'
import {
  Upload,
  Play,
  Copy,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  FolderOpen,
  Info,
  Link,
  LogIn,
  Maximize2,
  X,
} from 'lucide-react'

interface ClipPublishState {
  title: string
  description: string
  uploading: boolean
  uploadProgress: number
  success: boolean
  youtubeUrl: string | null
  error: string | null
  copyStatus: 'idle' | 'copied' | 'error'
  method: 'browser' | 'official'  // browser = ytb-up cookies (default), official = OAuth API
  account_id: string | null       // future multi-account (#5) hook
  cookies_path: string | null     // override per-clip cookies.json
}

export default function PublishPage() {
  const { processedClips, setCurrentStep, activeAccountId } = useAppStore()
  const [authenticated, setAuthenticated] = useState(false)
  const [authUrl, setAuthUrl] = useState('')
  const [authCode, setAuthCode] = useState('')
  const [checkingAuth, setCheckingAuth] = useState(true)
  const [publishStates, setPublishStates] = useState<Record<string, ClipPublishState>>({})
  const [folderNotification, setFolderNotification] = useState<string | null>(null)
  const [expandedClip, setExpandedClip] = useState<ProcessedClip | null>(null)

  useEffect(() => {
    setCurrentStep(5)
    checkAuth()
    const states: Record<string, ClipPublishState> = {}
    processedClips.forEach(clip => {
      states[clip.id] = {
        title: 'My Clip #Shorts',
        description: 'Created with ClipForge',
        uploading: false,
        uploadProgress: 0,
        success: false,
        youtubeUrl: null,
        error: null,
        copyStatus: 'idle',
        method: 'browser',            // default: ytb-up cookies (looks human)
        account_id: null,
        cookies_path: null,
      }
    })
    setPublishStates(states)
  }, [processedClips])

  useEffect(() => {
    if (folderNotification) {
      const timer = setTimeout(() => setFolderNotification(null), 5000)
      return () => clearTimeout(timer)
    }
  }, [folderNotification])

  const checkAuth = async () => {
    try {
      const { data } = await axios.get('/api/auth/youtube')
      setAuthenticated(data.authenticated)
      if (!data.authenticated) setAuthUrl(data.auth_url)
    } catch (err) {
      // Silently continue if auth check fails
    } finally {
      setCheckingAuth(false)
    }
  }

  const submitAuthCode = async () => {
    try {
      await axios.post('/api/auth/youtube/callback', null, {
        params: { auth_code: authCode },
      })
      setAuthenticated(true)
      setAuthCode('')
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Auth failed')
    }
  }

  const updateState = (clipId: string, update: Partial<ClipPublishState>) => {
    setPublishStates(prev => ({
      ...prev,
      [clipId]: { ...prev[clipId], ...update },
    }))
  }

  const publishClip = async (clip: ProcessedClip) => {
    const state = publishStates[clip.id]
    updateState(clip.id, { uploading: true, error: null, uploadProgress: 0 })

    try {
      const { data } = await axios.post('/api/publish', {
        clip_id: clip.id,
        title: state.title,
        description: state.description,
        method: state.method,                      // 'browser' (default) | 'official'
        cookies_path: state.cookies_path || undefined,
        // Use the global active account — per-clip override falls back to it.
        account_id: state.account_id || activeAccountId || undefined,
      })
      updateState(clip.id, {
        uploading: false,
        success: true,
        youtubeUrl: data.youtube_url,
        uploadProgress: 100,
      })
    } catch (err: any) {
      updateState(clip.id, {
        uploading: false,
        error: err.response?.data?.detail || 'Upload failed',
      })
    }
  }

  const copyPath = async (clipId: string) => {
    updateState(clipId, { copyStatus: 'idle' })
    
    try {
      // Get the full path from backend
      const { data } = await axios.get(`/api/export/${clipId}/path`)
      const fullPath = data.file_path
      
      // Try clipboard API
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(fullPath)
          updateState(clipId, { copyStatus: 'copied' })
          // Reset after 1.5 seconds
          setTimeout(() => updateState(clipId, { copyStatus: 'idle' }), 1500)
        } else {
          // Fallback: show prompt dialog
          prompt('Copy the path below:', fullPath)
          updateState(clipId, { copyStatus: 'copied' })
          setTimeout(() => updateState(clipId, { copyStatus: 'idle' }), 1500)
        }
      } catch (clipboardErr) {
        // Clipboard failed, use prompt fallback
        prompt('Copy the path below:', fullPath)
        updateState(clipId, { copyStatus: 'copied' })
        setTimeout(() => updateState(clipId, { copyStatus: 'idle' }), 1500)
      }
    } catch (err: any) {
      updateState(clipId, { copyStatus: 'error' })
      setTimeout(() => updateState(clipId, { copyStatus: 'idle' }), 2000)
    }
  }

  const openOutputFolder = async () => {
    try {
      const { data } = await axios.get('/api/open-folder')
      if (data.status === 'path_only') {
        // Backend couldn't open folder (headless server, etc.), show the path
        setFolderNotification(`Output folder: ${data.path}`)
      }
    } catch (err) {
      setFolderNotification('Could not open output folder')
    }
  }

  if (processedClips.length === 0) {
    return (
      <div className="max-w-4xl mx-auto p-8">
        <div className="card text-center py-14 border-dashed">
          <Upload size={40} className="text-slate-700 mx-auto mb-4" />
          <h3 className="font-semibold text-slate-700 mb-1">No clips to publish</h3>
          <p className="text-slate-500 text-sm">Process some clips first to publish them.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Upload size={22} className="text-accent" />
          Publish Clips
        </h1>
        <p className="text-slate-500 mt-1 text-sm">
          Upload your processed clips to YouTube Shorts or export locally.
        </p>
      </div>

      {/* Folder notification toast */}
      {folderNotification && (
        <div className="mb-4 flex items-center gap-2 px-4 py-3 rounded-lg bg-accent/10 border border-accent/30 text-accent text-sm">
          <Info size={14} className="shrink-0" />
          <span className="text-xs">{folderNotification}</span>
        </div>
      )}

      {/* Upload method picker — ytb-up cookies (default) vs OAuth API.
          Affects ALL clips at once via the per-clip state default. */}
      <div className="card mb-3 border-slate-200">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Upload method
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <button
            onClick={() => {
              const next: Record<string, Partial<ClipPublishState>> = {}
              Object.keys(publishStates).forEach((k) => { next[k] = { method: 'browser' } })
              setPublishStates((prev) => {
                const cp = { ...prev }
                Object.entries(next).forEach(([k, v]) => { cp[k] = { ...cp[k], ...v } })
                return cp
              })
            }}
            className={`px-3 py-2 rounded-xl border text-left transition-colors ${
              Object.values(publishStates).every((s) => s.method === 'browser')
                ? 'border-accent bg-accent/5 text-slate-800'
                : 'border-slate-200 hover:border-slate-300 text-slate-500'
            }`}
          >
            <div className="font-semibold flex items-center gap-1">
              🦊 Browser (ytb-up)
              <span className="ml-auto text-success">recommended</span>
            </div>
            <div className="text-[11px] mt-1 leading-snug text-slate-500">
              Cookie auth + headless Playwright. Looks like a real uploader,
              no Workspace account needed.
            </div>
          </button>
          <button
            onClick={() => {
              const next: Record<string, Partial<ClipPublishState>> = {}
              Object.keys(publishStates).forEach((k) => { next[k] = { method: 'official' } })
              setPublishStates((prev) => {
                const cp = { ...prev }
                Object.entries(next).forEach(([k, v]) => { cp[k] = { ...cp[k], ...v } })
                return cp
              })
            }}
            className={`px-3 py-2 rounded-xl border text-left transition-colors ${
              Object.values(publishStates).some((s) => s.method === 'official')
                ? 'border-accent bg-accent/5 text-slate-800'
                : 'border-slate-200 hover:border-slate-300 text-slate-500'
            }`}
          >
            <div className="font-semibold">🔌 OAuth Data API</div>
            <div className="text-[11px] mt-1 leading-snug text-slate-500">
              Official Google API. Requires client_secrets.json + Workspace.
              Connection status below.
            </div>
          </button>
        </div>
      </div>

      {/* YouTube Auth */}
      {!checkingAuth && (
        <div className={`card mb-6 ${authenticated ? 'border-success/30 bg-success/5' : 'border-slate-200'}`}>
          {authenticated ? (
            <div className="flex items-center gap-2 text-success text-sm font-medium">
              <CheckCircle2 size={16} />
              Connected to YouTube
            </div>
          ) : (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Play size={16} className="text-red-400" />
                <span className="font-medium text-slate-800 text-sm">Connect YouTube Account</span>
              </div>

              {authUrl && (
                <div className="mb-3">
                  <a
                    href={authUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-secondary text-sm w-full justify-center"
                  >
                    <LogIn size={14} />
                    Authorize on Google
                    <ExternalLink size={12} className="text-slate-500" />
                  </a>
                </div>
              )}

              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Link size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="text"
                    value={authCode}
                    onChange={(e) => setAuthCode(e.target.value)}
                    placeholder="Paste authorization code here…"
                    className="input w-full pl-8 text-sm"
                  />
                </div>
                <button onClick={submitAuthCode} className="btn btn-primary shrink-0 text-sm">
                  Connect
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Clips */}
      <div className="grid sm:grid-cols-2 gap-5 mb-6 items-start">
        {processedClips.map((clip) => {
          const state = publishStates[clip.id]
          if (!state) return null

          return (
            <div key={clip.id} className="card">
              {/* Video preview */}
              <div className="flex justify-center mb-4">
                <div className="relative group">
                  <video
                    src={`/files/${clip.file_path}`}
                    className="h-64 aspect-[9/16] rounded-xl bg-black object-cover shadow-sm"
                    controls
                    preload="metadata"
                  />
                  <button
                    onClick={() => setExpandedClip(clip)}
                    title="Open large preview"
                    className="absolute top-2 right-2 p-1.5 rounded-lg bg-black/55 text-white opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/75"
                  >
                    <Maximize2 size={15} />
                  </button>
                </div>
              </div>

              {/* AI score breakdown — explains why we picked this clip */}
              <div className="mb-4">
                <ScoreBreakdown score={clip.score} />
              </div>

              {/* Form */}
              <div className="space-y-2.5">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Title
                  </label>
                  <input
                    type="text"
                    value={state.title}
                    onChange={(e) => updateState(clip.id, { title: e.target.value })}
                    className="input w-full text-sm"
                    disabled={state.uploading || state.success}
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Description
                  </label>
                  <textarea
                    value={state.description}
                    onChange={(e) => updateState(clip.id, { description: e.target.value })}
                    className="input w-full text-sm resize-none"
                    rows={2}
                    disabled={state.uploading || state.success}
                  />
                </div>
              </div>

              {/* Upload progress */}
              {state.uploading && (
                <div className="mt-3">
                  <ProgressBar progress={state.uploadProgress} message="Uploading to YouTube…" />
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => publishClip(clip)}
                  disabled={!authenticated || state.uploading || state.success}
                  className="btn btn-primary flex-1 text-sm disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                >
                  {state.uploading ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Uploading…
                    </>
                  ) : state.success ? (
                    <>
                      <CheckCircle2 size={14} />
                      Published
                    </>
                  ) : (
                    <>
                      <Play size={14} />
                      Publish to Shorts
                    </>
                  )}
                </button>
                <button
                  onClick={() => copyPath(clip.id)}
                  className="btn btn-secondary text-sm"
                  title="Copy local file path"
                >
                  {state.copyStatus === 'copied' ? (
                    <CheckCircle2 size={14} className="text-success" />
                  ) : state.copyStatus === 'error' ? (
                    <AlertTriangle size={14} className="text-danger" />
                  ) : (
                    <Copy size={14} />
                  )}
                  Copy Path
                </button>
              </div>

              {/* Success */}
              {state.success && state.youtubeUrl && (
                <div className="mt-3 flex items-center gap-2 px-3 py-2 rounded-lg bg-success/8 border border-success/20">
                  <CheckCircle2 size={14} className="text-success shrink-0" />
                  <a
                    href={state.youtubeUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-accent hover:underline flex items-center gap-1"
                  >
                    View on YouTube
                    <ExternalLink size={10} />
                  </a>
                </div>
              )}

              {/* Error */}
              {state.error && (
                <div className="mt-3 flex items-start gap-2 px-3 py-2 rounded-lg bg-danger/8 border border-danger/20 text-danger">
                  <AlertTriangle size={14} className="shrink-0 mt-0.5" />
                  <span className="text-xs">{state.error}</span>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Large preview modal */}
      {expandedClip && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-6"
          onClick={() => setExpandedClip(null)}
        >
          <button
            onClick={() => setExpandedClip(null)}
            className="absolute top-5 right-5 p-2 rounded-lg bg-white/10 text-white hover:bg-white/20"
          >
            <X size={22} />
          </button>
          <video
            src={`/files/${expandedClip.file_path}`}
            className="max-h-[90vh] aspect-[9/16] rounded-2xl bg-black shadow-2xl"
            controls
            autoPlay
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}

      {/* Local export info */}
      <div className="flex items-start gap-3 px-4 py-3 rounded-xl bg-accent/6 border border-accent/20 text-sm">
        <Info size={15} className="text-accent shrink-0 mt-0.5" />
        <div>
          <div className="font-medium text-slate-800 mb-1">Manual Export</div>
          <p className="text-xs text-slate-500 leading-relaxed">
            Use <span className="text-slate-700">"Copy Path"</span> to get the local file path,
            then drag-and-drop to TikTok, Instagram Reels, VK Clips, etc.
            All clips are 9:16 vertical MP4, ready to upload anywhere.
          </p>
          <button
            onClick={openOutputFolder}
            className="btn btn-secondary text-xs mt-2"
          >
            <FolderOpen size={12} />
            Open Output Folder
          </button>
        </div>
      </div>
    </div>
  )
}