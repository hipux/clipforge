import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAppStore } from '../store/useAppStore'
import VideoCard from '../components/VideoCard'
import ProgressBar from '../components/ProgressBar'
import { Download, AlertTriangle, ArrowRight, Play, Tv, Video, Link, Zap, Clock, HardDrive } from 'lucide-react'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1)} ${sizes[i]}`
}

export default function DownloadPage() {
  const navigate = useNavigate()
  const { currentVideo, setVideo } = useAppStore()
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [speed, setSpeed] = useState('')
  const [eta, setEta] = useState('')
  const [downloadedBytes, setDownloadedBytes] = useState(0)
  const [totalBytes, setTotalBytes] = useState(0)
  const [fragmentIndex, setFragmentIndex] = useState<number | null>(null)
  const [fragmentCount, setFragmentCount] = useState<number | null>(null)

  const handleDownload = async () => {
    if (!url.trim()) {
      setError('Please enter a video URL')
      return
    }

    setLoading(true)
    setError('')
    setProgress(0)
    setStatus('Starting download...')
    setSpeed('')
    setEta('')
    setDownloadedBytes(0)
    setTotalBytes(0)
    setFragmentIndex(null)
    setFragmentCount(null)

    try {
      const { data } = await axios.post('/api/download', { url })
      const jobId = data.job_id

      // Connect directly to backend port 8000 (bypass Vite proxy for WebSocket)
      const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const wsHost = window.location.hostname
      const ws = new WebSocket(`${wsProtocol}://${wsHost}:8000/api/ws/download/${jobId}`)

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data)

        if (message.status === 'downloading' && message.progress) {
          setProgress(message.progress.percent || 0)
          setSpeed(message.progress.speed || '')
          setEta(message.progress.eta || '')
          setDownloadedBytes(message.progress.downloaded_bytes || 0)
          setTotalBytes(message.progress.total_bytes || 0)
          setFragmentIndex(message.progress.fragment_index || null)
          setFragmentCount(message.progress.fragment_count || null)
          setStatus('Downloading...')
        } else if (message.status === 'processing') {
          setProgress(95)
          setStatus('Processing video...')
        } else if (message.status === 'completed') {
          setProgress(100)
          setStatus('Download complete!')
          setVideo(message.video)
          ws.close()
          setLoading(false)
        } else if (message.status === 'error') {
          setError(message.message)
          ws.close()
          setLoading(false)
        }
      }

      ws.onerror = () => {
        setError('Connection error. Make sure the backend is running.')
        setLoading(false)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start download')
      setLoading(false)
    }
  }

  return (
    <div className="p-8 max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 text-accent text-xs font-semibold uppercase tracking-widest mb-2">
          <span className="w-4 h-px bg-accent" />
          Step 1 of 5
        </div>
        <h1 className="text-2xl font-bold text-slate-100">Download Video</h1>
        <p className="text-slate-500 mt-1 text-sm">
          Paste a link from YouTube, Rutube or VK Video to get started.
        </p>
      </div>

      {/* URL Input */}
      <div className="card mb-5">
        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
          Video URL
        </label>
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Link size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && !loading && handleDownload()}
              placeholder="https://youtube.com/watch?v=…"
              className="input w-full pl-9"
              disabled={loading}
            />
          </div>
          <button
            onClick={handleDownload}
            disabled={loading}
            className="btn btn-primary px-6 shrink-0 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Downloading…
              </>
            ) : (
              <>
                <Download size={15} />
                Download
              </>
            )}
          </button>
        </div>

        {/* Platform badges */}
        <div className="flex items-center gap-4 mt-4 pt-4 border-t border-slate-800">
          <span className="text-[11px] text-slate-600 uppercase tracking-wider font-semibold">Supported</span>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-xs text-slate-400 bg-surface-2 px-2.5 py-1 rounded-md border border-slate-700/50">
              <Play size={11} className="text-red-400" /> YouTube
            </span>
            <span className="flex items-center gap-1.5 text-xs text-slate-400 bg-surface-2 px-2.5 py-1 rounded-md border border-slate-700/50">
              <Tv size={11} className="text-orange-400" /> Rutube
            </span>
            <span className="flex items-center gap-1.5 text-xs text-slate-400 bg-surface-2 px-2.5 py-1 rounded-md border border-slate-700/50">
              <Video size={11} className="text-blue-400" /> VK Video
            </span>
          </div>
        </div>
      </div>

      {/* Progress */}
      {loading && (
        <div className="card mb-5">
          <ProgressBar progress={progress} message={status} />
          
          {/* Rich Progress Stats */}
          {(speed || eta || totalBytes > 0 || fragmentCount) && (
            <div className="grid grid-cols-2 gap-3 mt-4 pt-4 border-t border-slate-800">
              {/* Speed */}
              {speed && (
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center shrink-0">
                    <Zap size={14} className="text-cyan-400" />
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Speed</div>
                    <div className="text-sm font-semibold text-cyan-400 mt-0.5">{speed}</div>
                  </div>
                </div>
              )}
              
              {/* ETA */}
              {eta && (
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-slate-700/30 border border-slate-700/50 flex items-center justify-center shrink-0">
                    <Clock size={14} className="text-slate-400" />
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">ETA</div>
                    <div className="text-sm font-semibold text-slate-300 mt-0.5">{eta}</div>
                  </div>
                </div>
              )}
              
              {/* Downloaded / Total */}
              {totalBytes > 0 && (
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-slate-700/30 border border-slate-700/50 flex items-center justify-center shrink-0">
                    <HardDrive size={14} className="text-slate-400" />
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Size</div>
                    <div className="text-sm font-semibold text-slate-300 mt-0.5">
                      {formatBytes(downloadedBytes)} / {formatBytes(totalBytes)}
                    </div>
                  </div>
                </div>
              )}
              
              {/* Fragments (HLS/Rutube) */}
              {fragmentCount && fragmentIndex !== null && (
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-orange-500/10 border border-orange-500/20 flex items-center justify-center shrink-0">
                    <Download size={14} className="text-orange-400" />
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Fragments</div>
                    <div className="text-sm font-semibold text-orange-400 mt-0.5">
                      {fragmentIndex} / {fragmentCount}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="card border-danger/30 bg-danger/5 mb-5">
          <div className="flex items-start gap-3 text-danger">
            <AlertTriangle size={18} className="shrink-0 mt-0.5" />
            <div>
              <div className="font-medium text-sm">Download failed</div>
              <div className="text-xs text-danger/80 mt-0.5">{error}</div>
            </div>
          </div>
        </div>
      )}

      {/* Video Info */}
      {currentVideo && !loading && (
        <>
          <VideoCard video={currentVideo} />
          <div className="mt-5 flex justify-end">
            <button
              onClick={() => navigate('/moments')}
              className="btn btn-primary px-6"
            >
              Continue to Moments
              <ArrowRight size={15} />
            </button>
          </div>
        </>
      )}
    </div>
  )
}
