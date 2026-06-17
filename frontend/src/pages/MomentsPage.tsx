import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAppStore } from '../store/useAppStore'
import MomentCard from '../components/MomentCard'
import ProgressBar from '../components/ProgressBar'
import {
  Scissors,
  AlertTriangle,
  Search,
  ArrowRight,
  ArrowLeft,
  RefreshCw,
  CheckSquare,
  Square,
} from 'lucide-react'

export default function MomentsPage() {
  const navigate = useNavigate()
  const {
    currentVideo,
    moments,
    setMoments,
    selectedMomentIds,
    toggleMoment,
    setSelectedMoments,
  } = useAppStore()

  const [detecting, setDetecting] = useState(false)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!currentVideo) {
      navigate('/download')
      return
    }
    if (moments.length === 0) {
      startDetection()
    }
  }, [])

  const startDetection = async () => {
    if (!currentVideo) return

    setDetecting(true)
    setError('')
    setProgress(0)
    setStatus('Starting moment detection…')

    try {
      const { data } = await axios.post('/api/moments/detect', {
        video_id: currentVideo.id,
      })
      const jobId = data.job_id

      // Connect directly to backend port 8000 (bypass Vite proxy for WebSocket)
      const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const wsHost = window.location.hostname
      const ws = new WebSocket(`${wsProtocol}://${wsHost}:8000/ws/moments/${jobId}`)

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data)

        if (message.status === 'analyzing') {
          setProgress(message.progress * 100)
          setStatus(message.message)
        } else if (message.status === 'completed') {
          setProgress(100)
          setStatus('Detection complete!')
          setMoments(message.moments)
          setSelectedMoments(message.moments.map((m: any) => m.id))
          ws.close()
          setDetecting(false)
        } else if (message.status === 'error') {
          setError(message.message)
          ws.close()
          setDetecting(false)
        }
      }

      ws.onerror = () => {
        setError('Connection error. Make sure the backend is running.')
        setDetecting(false)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start detection')
      setDetecting(false)
    }
  }

  const toggleAll = () => {
    if (selectedMomentIds.length === moments.length) {
      setSelectedMoments([])
    } else {
      setSelectedMoments(moments.map(m => m.id))
    }
  }

  const allSelected = moments.length > 0 && selectedMomentIds.length === moments.length

  return (
    <div className="p-8 max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 text-accent text-xs font-semibold uppercase tracking-widest mb-2">
          <span className="w-4 h-px bg-accent" />
          Step 2 of 5
        </div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Scissors size={22} className="text-accent" />
          Interesting Moments
        </h1>
        <p className="text-slate-500 mt-1 text-sm">
          AI detects the most engaging 30–90 second clips. Review and select which to process.
        </p>
      </div>

      {/* Detecting progress */}
      {detecting && (
        <div className="card mb-6">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-4 h-4 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
            <span className="text-sm font-medium text-slate-300">Analyzing video…</span>
          </div>
          <ProgressBar progress={progress} message={status} />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="card border-danger/30 bg-danger/5 mb-6">
          <div className="flex items-start gap-3 text-danger">
            <AlertTriangle size={18} className="shrink-0 mt-0.5" />
            <div>
              <div className="font-medium text-sm">Detection failed</div>
              <div className="text-xs text-danger/80 mt-0.5">{error}</div>
            </div>
          </div>
          <button
            onClick={startDetection}
            className="btn btn-secondary mt-3 text-sm"
          >
            <RefreshCw size={14} />
            Retry
          </button>
        </div>
      )}

      {/* Moments list */}
      {moments.length > 0 && (
        <>
          <div className="flex justify-between items-center mb-4">
            <button
              onClick={toggleAll}
              className="btn btn-secondary text-sm"
            >
              {allSelected ? <Square size={14} /> : <CheckSquare size={14} />}
              {allSelected ? 'Deselect All' : 'Select All'}
            </button>
            <span className="text-xs text-slate-500">
              <span className="text-accent font-semibold">{selectedMomentIds.length}</span>
              {' '}of {moments.length} selected
            </span>
          </div>

          <div className="space-y-3 mb-6">
            {moments.map((moment) => (
              <MomentCard
                key={moment.id}
                moment={moment}
                isSelected={selectedMomentIds.includes(moment.id)}
                onToggle={() => toggleMoment(moment.id)}
              />
            ))}
          </div>

          {/* Navigation */}
          <div className="flex justify-between items-center">
            <button
              onClick={() => navigate('/download')}
              className="btn btn-secondary"
            >
              <ArrowLeft size={15} />
              Back
            </button>
            <button
              onClick={() => navigate('/effects')}
              disabled={selectedMomentIds.length === 0}
              className="btn btn-primary px-6 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              Effects ({selectedMomentIds.length} clips)
              <ArrowRight size={15} />
            </button>
          </div>
        </>
      )}

      {/* No moments */}
      {!detecting && moments.length === 0 && !error && (
        <div className="card text-center py-14 border-dashed">
          <Search size={40} className="text-slate-700 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-slate-300 mb-1">No moments detected yet</h3>
          <p className="text-slate-500 text-sm mb-6">
            Start detection to find the best clips in your video
          </p>
          <button onClick={startDetection} className="btn btn-primary mx-auto">
            <Search size={15} />
            Start Detection
          </button>
        </div>
      )}
    </div>
  )
}
