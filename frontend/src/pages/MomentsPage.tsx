import { useState, useEffect, useRef } from 'react'
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
    setCurrentStep,
    detectionSettings,
    updateDetectionSettings,
  } = useAppStore()

  const [detecting, setDetecting] = useState(false)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const detectingRef = useRef(false)

  useEffect(() => {
    if (!currentVideo) {
      navigate('/download')
      return
    }
    // Only auto-start if no moments exist and not already detecting
    if (moments.length === 0 && !detectingRef.current) {
      startDetection()
    }
  }, [currentVideo])

  const startDetection = async () => {
    if (!currentVideo || detectingRef.current) return

    detectingRef.current = true
    setDetecting(true)
    setError('')
    setProgress(0)
    setStatus('Starting moment detection…')

    try {
      const { data } = await axios.post('/api/moments/detect', {
        video_id: currentVideo.id,
        min_duration: detectionSettings.minDuration,
        max_duration: detectionSettings.maxDuration,
        max_moments: detectionSettings.maxMoments,
      })

      // Check if moments already exist
      if (data.status === 'completed' && data.moments) {
        setMoments(data.moments)
        setSelectedMoments(data.moments.map((m: any) => m.id))
        setDetecting(false)
        detectingRef.current = false
        return
      }
      
      const jobId = data.job_id

      // Connect directly to backend port 8000 (bypass Vite proxy for WebSocket)
      const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const wsHost = window.location.hostname
      const ws = new WebSocket(`${wsProtocol}://${wsHost}:8000/api/ws/moments/${jobId}`)

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
          setCurrentStep(2) // Save that we're on step 2 (moments)
          ws.close()
          setDetecting(false)
          detectingRef.current = false
        } else if (message.status === 'error') {
          setError(message.error || message.message || 'Detection failed')
          ws.close()
          setDetecting(false)
          detectingRef.current = false
        }
      }

      ws.onerror = () => {
        setError('Connection error. Make sure the backend is running.')
        setDetecting(false)
        detectingRef.current = false
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start detection')
      setDetecting(false)
      detectingRef.current = false
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

      {/* Error */}
      {error && (
        <div className="card border-red-900/50 bg-red-950/30 mb-6">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-red-300 mb-1">Detection failed</h3>
              <p className="text-sm text-red-400">{error}</p>
              <button
                onClick={startDetection}
                className="btn btn-secondary mt-3"
              >
                <RefreshCw size={15} />
                Try Again
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Detecting */}
      {detecting && (
        <div className="card mb-6">
          <div className="flex items-center gap-3 mb-3">
            <Search size={18} className="text-accent animate-pulse" />
            <span className="font-semibold text-slate-300">{status}</span>
          </div>
          <ProgressBar progress={progress} />
          <p className="text-xs text-slate-500 mt-2">
            This may take a few minutes depending on video length…
          </p>
        </div>
      )}

      {/* Moments list */}
      {!detecting && moments.length > 0 && (
        <>
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={toggleAll}
              className="flex items-center gap-2 text-sm text-slate-400 hover:text-accent transition-colors"
            >
              {allSelected ? (
                <CheckSquare size={16} className="text-accent" />
              ) : (
                <Square size={16} />
              )}
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

      {/* Detection Settings */}
      {moments.length === 0 && !detecting && !error && (
        <div className="card mb-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Detection Settings</h3>
          
          <div className="space-y-4">
            {/* Min Duration */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-xs text-slate-400">Min clip duration</label>
                <span className="text-xs font-semibold text-accent">{detectionSettings.minDuration}s</span>
              </div>
              <input
                type="range"
                min="15"
                max="60"
                step="5"
                value={detectionSettings.minDuration}
                onChange={(e) => updateDetectionSettings({ minDuration: parseInt(e.target.value) })}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-accent"
              />
            </div>
            
            {/* Max Duration */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-xs text-slate-400">Max clip duration</label>
                <span className="text-xs font-semibold text-accent">{detectionSettings.maxDuration}s</span>
              </div>
              <input
                type="range"
                min="30"
                max="120"
                step="5"
                value={detectionSettings.maxDuration}
                onChange={(e) => updateDetectionSettings({ maxDuration: parseInt(e.target.value) })}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-accent"
              />
            </div>
            
            {/* Max Moments */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-xs text-slate-400">Max moments</label>
                <span className="text-xs font-semibold text-accent">{detectionSettings.maxMoments}</span>
              </div>
              <input
                type="range"
                min="5"
                max="30"
                step="1"
                value={detectionSettings.maxMoments}
                onChange={(e) => updateDetectionSettings({ maxMoments: parseInt(e.target.value) })}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-accent"
              />
            </div>
          </div>
        </div>
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
