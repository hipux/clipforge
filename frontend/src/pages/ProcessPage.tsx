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
  const { selectedMomentIds, globalEffects, setClips, setCurrentStep, activeProcessingJobId, setActiveProcessingJobId, processedClips } = useAppStore()

  const [processing, setProcessing] = useState(false)
  const [currentClip, setCurrentClip] = useState(0)
  const [totalClips, setTotalClips] = useState(0)
  const [clipProgress, setClipProgress] = useState(0)
  const [clipMessage, setClipMessage] = useState('')
  const [overallMessage, setOverallMessage] = useState('')
  const [error, setError] = useState('')
  const [completed, setCompleted] = useState(processedClips.length > 0)
  const [previousClip, setPreviousClip] = useState(0)

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
      setActiveProcessingJobId(jobId)
      connectProcessWs(jobId)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start processing')
      setActiveProcessingJobId(null)
      setProcessing(false)
    }
  }

  // Connect to the processing progress WebSocket (used for a fresh run and for
  // resuming an in-flight run after a page reload).
  const connectProcessWs = (jobId: string) => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsHost = window.location.hostname
    const ws = new WebSocket(`${wsProtocol}://${wsHost}:8000/api/ws/process/${jobId}`)

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)

      if (message.status === 'processing') {
        setProcessing(true)
        if (message.current_clip !== previousClip && message.current_clip > 0) {
          setPreviousClip(message.current_clip)
          setClipProgress(0)
          setClipMessage('Starting...')
        }
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
        setCurrentStep(4)
        setProcessing(false)
        setClips(message.clips)
        setActiveProcessingJobId(null)
        ws.close()
      } else if (message.status === 'error') {
        setError(message.message)
        setProcessing(false)
        setActiveProcessingJobId(null)
        ws.close()
      }
    }

    ws.onerror = () => {
      setError('Connection error. Make sure the backend is running.')
      setProcessing(false)
    }
    return ws
  }

  // Resume an in-flight processing run after a page reload by asking the server.
  useEffect(() => {
    if (!activeProcessingJobId || completed) return
    let cancelled = false
    ;(async () => {
      try {
        const { data } = await axios.get(`/api/process/${activeProcessingJobId}/status`)
        if (cancelled) return
        if (data.status === 'completed') {
          if (data.clips) setClips(data.clips)
          setCompleted(true)
          setCurrentStep(4)
          setActiveProcessingJobId(null)
        } else if (data.status === 'error') {
          setError(data.error || 'Processing failed')
          setActiveProcessingJobId(null)
        } else {
          // still running -> reattach to the live progress stream
          setProcessing(true)
          setTotalClips(data.total_clips || 0)
          setCurrentClip(data.current_clip || 0)
          setOverallMessage('Resuming processing…')
          connectProcessWs(activeProcessingJobId)
        }
      } catch {
        // job unknown (backend restarted) -> clean reset
        if (!cancelled) setActiveProcessingJobId(null)
      }
    })()
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const overallProgress = totalClips > 0
    ? ((currentClip - 1) / totalClips) * 100 + clipProgress / totalClips
    : 0

  return (
    <div className="max-w-2xl mx-auto p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Cpu size={22} className="text-accent" />
          Process Clips
        </h1>
        <p className="text-slate-500 mt-1 text-sm">
          FFmpeg applies all selected effects to your{' '}
          <span className="text-slate-700 font-medium">{selectedMomentIds.length} clip{selectedMomentIds.length !== 1 ? 's' : ''}</span>{' '}
          — all locally, no cloud.
        </p>
      </div>

      {/* Start button */}
      {!processing && !completed && (
        <div className="card text-center py-10 mb-6 border-dashed">
          <Cpu size={42} className="text-slate-700 mx-auto mb-4" />
          <h3 className="font-semibold text-slate-800 mb-1">Ready to process</h3>
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
              <span className="text-sm font-medium text-slate-700">{overallMessage || 'Processing…'}</span>
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
                <span className="text-xs text-slate-500 font-medium">Current clip</span>
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
                <div className="text-xs text-slate-500 mt-0.5">
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