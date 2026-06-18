import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAppStore } from '../store/useAppStore'
import ProgressBar from '../components/ProgressBar'
import {
  Cpu,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  RefreshCw,
  Clock,
} from 'lucide-react'

export default function ProcessPage() {
  const navigate = useNavigate()
  const { selectedMomentIds, globalEffects, setClips } = useAppStore()

  const [processing, setProcessing] = useState(false)
  const [currentClip, setCurrentClip] = useState(0)
  const [totalClips, setTotalClips] = useState(0)
  const [clipProgress, setClipProgress] = useState(0)
  const [clipMessage, setClipMessage] = useState('')
  const [overallMessage, setOverallMessage] = useState('')
  const [error, setError] = useState('')
  const [completed, setCompleted] = useState(false)

  useEffect(() => {
    if (selectedMomentIds.length === 0) {
      navigate('/moments')
    }
  }, [selectedMomentIds])

  const startProcessing = async () => {
    setProcessing(true)
    setError('')
    setCompleted(false)
    setCurrentClip(0)
    setClipProgress(0)

    try {
      const { data } = await axios.post('/api/process', {
        moment_ids: selectedMomentIds,
        effects: globalEffects,
      })

      const jobId = data.job_id
      setTotalClips(data.total_clips)

      // Connect directly to backend port 8000 (bypass Vite proxy for WebSocket)
      const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const wsHost = window.location.hostname
      const ws = new WebSocket(`${wsProtocol}://${wsHost}:8000/api/ws/process/${jobId}`)

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data)

        if (message.status === 'processing') {
          setCurrentClip(message.current_clip)
          setTotalClips(message.total_clips)
          setClipProgress(message.clip_progress * 100)
          setClipMessage(message.clip_message)
          setOverallMessage(
            `Processing clip ${message.current_clip} of ${message.total_clips}…`
          )
        } else if (message.status === 'completed') {
          setClipProgress(100)
          setCompleted(true)
          setProcessing(false)
          setClips(message.clips)
          ws.close()
        } else if (message.status === 'error') {
          setError(message.message)
          setProcessing(false)
          ws.close()
        }
      }

      ws.onerror = () => {
        setError('Connection error. Make sure the backend is running.')
        setProcessing(false)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start processing')
      setProcessing(false)
    }
  }

  const overallProgress = totalClips > 0
    ? ((currentClip - 1) / totalClips) * 100 + clipProgress / totalClips
    : 0

  return (
    <div className="max-w-xl mx-auto p-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 text-accent text-xs font-semibold uppercase tracking-widest mb-2">
          <span className="w-4 h-px bg-accent" />
          Step 4 of 5
        </div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Cpu size={22} className="text-accent" />
          Process Clips
        </h1>
        <p className="text-slate-500 mt-1 text-sm">
          FFmpeg applies all selected effects to your{' '}
          <span className="text-slate-300 font-medium">{selectedMomentIds.length} clip{selectedMomentIds.length !== 1 ? 's' : ''}</span>{' '}
          — all locally, no cloud.
        </p>
      </div>

      {/* Start button */}
      {!processing && !completed && (
        <div className="card text-center py-10 mb-6 border-dashed">
          <Cpu size={42} className="text-slate-700 mx-auto mb-4" />
          <h3 className="font-semibold text-slate-200 mb-1">Ready to process</h3>
          <p className="text-slate-500 text-sm mb-6">
            {selectedMomentIds.length} clip{selectedMomentIds.length !== 1 ? 's' : ''} · ~30–60s each
          </p>
          <button onClick={startProcessing} className="btn btn-primary mx-auto">
            <Cpu size={15} />
            Start Processing
          </button>
        </div>
      )}

      {/* Processing */}
      {processing && (
        <div className="space-y-4 mb-6">
          {/* Overall */}
          <div className="card">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-4 h-4 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
              <span className="text-sm font-medium text-slate-300">{overallMessage || 'Processing…'}</span>
            </div>
            <ProgressBar
              progress={overallProgress}
              message={`Overall — ${currentClip} of ${totalClips} clips`}
            />
          </div>

          {/* Current clip */}
          {clipMessage && (
            <div className="card bg-surface-2">
              <div className="flex items-center gap-2 mb-2">
                <Clock size={13} className="text-slate-500" />
                <span className="text-xs text-slate-400 font-medium">Current clip</span>
              </div>
              <ProgressBar progress={clipProgress} message={clipMessage} />
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="card border-danger/30 bg-danger/5 mb-6">
          <div className="flex items-start gap-3 text-danger">
            <AlertTriangle size={18} className="shrink-0 mt-0.5" />
            <div>
              <div className="font-medium text-sm">Processing failed</div>
              <div className="text-xs text-danger/80 mt-0.5">{error}</div>
            </div>
          </div>
          <button onClick={startProcessing} className="btn btn-secondary mt-3 text-sm">
            <RefreshCw size={14} />
            Retry
          </button>
        </div>
      )}

      {/* Completed */}
      {completed && (
        <>
          <div className="card border-success/30 bg-success/5 mb-6">
            <div className="flex items-center gap-3">
              <CheckCircle2 size={24} className="text-success shrink-0" />
              <div>
                <div className="font-semibold text-success">Processing complete!</div>
                <div className="text-xs text-slate-400 mt-0.5">
                  All clips are ready to preview and publish
                </div>
              </div>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              onClick={() => navigate('/publish')}
              className="btn btn-primary px-6"
            >
              Publish Clips
              <ArrowRight size={15} />
            </button>
          </div>
        </>
      )}
    </div>
  )
}
