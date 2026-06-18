import { useState, useEffect } from 'react'
import axios from 'axios'
import { useAppStore, ProcessedClip } from '../store/useAppStore'
import ProgressBar from '../components/ProgressBar'
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
} from 'lucide-react'

interface ClipPublishState {
  title: string
  description: string
  uploading: boolean
  uploadProgress: number
  success: boolean
  youtubeUrl: string | null
  error: string | null
}

export default function PublishPage() {
  const { processedClips } = useAppStore()
  const [authenticated, setAuthenticated] = useState(false)
  const [authUrl, setAuthUrl] = useState('')
  const [authCode, setAuthCode] = useState('')
  const [checkingAuth, setCheckingAuth] = useState(true)
  const [publishStates, setPublishStates] = useState<Record<string, ClipPublishState>>({})

  useEffect(() => {
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
      }
    })
    setPublishStates(states)
  }, [processedClips])

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

  const copyPath = (path: string) => {
    navigator.clipboard.writeText(path)
  }

  if (processedClips.length === 0) {
    return (
      <div className="max-w-xl mx-auto p-8">
        <div className="card text-center py-14 border-dashed">
          <Upload size={40} className="text-slate-700 mx-auto mb-4" />
          <h3 className="font-semibold text-slate-300 mb-1">No clips to publish</h3>
          <p className="text-slate-500 text-sm">Process some clips first to publish them.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-xl mx-auto p-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 text-accent text-xs font-semibold uppercase tracking-widest mb-2">
          <span className="w-4 h-px bg-accent" />
          Step 5 of 5
        </div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Upload size={22} className="text-accent" />
          Publish Clips
        </h1>
        <p className="text-slate-500 mt-1 text-sm">
          Upload your processed clips to YouTube Shorts or export locally.
        </p>
      </div>

      {/* YouTube Auth */}
      {!checkingAuth && (
        <div className={`card mb-6 ${authenticated ? 'border-success/30 bg-success/5' : 'border-slate-700'}`}>
          {authenticated ? (
            <div className="flex items-center gap-2 text-success text-sm font-medium">
              <CheckCircle2 size={16} />
              Connected to YouTube
            </div>
          ) : (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Play size={16} className="text-red-400" />
                <span className="font-medium text-slate-200 text-sm">Connect YouTube Account</span>
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
      <div className="space-y-4 mb-6">
        {processedClips.map((clip) => {
          const state = publishStates[clip.id]
          if (!state) return null

          return (
            <div key={clip.id} className="card">
              {/* Video preview */}
              <video
                src={`/files/${clip.file_path}`}
                className="w-full rounded-lg mb-4 bg-black"
                style={{ maxHeight: 200 }}
                controls
                preload="metadata"
              />

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
                  onClick={() => copyPath(clip.file_path)}
                  className="btn btn-secondary text-sm"
                  title="Copy local file path"
                >
                  <Copy size={14} />
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

      {/* Local export info */}
      <div className="flex items-start gap-3 px-4 py-3 rounded-xl bg-accent/6 border border-accent/20 text-sm">
        <Info size={15} className="text-accent shrink-0 mt-0.5" />
        <div>
          <div className="font-medium text-slate-200 mb-1">Manual Export</div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Use <span className="text-slate-300">"Copy Path"</span> to get the local file path,
            then drag-and-drop to TikTok, Instagram Reels, VK Clips, etc.
            All clips are 9:16 vertical MP4, ready to upload anywhere.
          </p>
          <button
            onClick={() => axios.get('/api/open-folder').catch(() => {})}
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
