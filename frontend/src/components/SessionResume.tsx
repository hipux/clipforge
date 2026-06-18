import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAppStore } from '../store/useAppStore'
import { RefreshCw, X, Play } from 'lucide-react'

interface SessionState {
  step: number
  video_id: string | null
  moments_count: number
  selected_moments_count: number
  processed_clips_count: number
}

const stepNames = ['Download', 'Moments', 'Effects', 'Process', 'Publish']
const stepPaths = ['/download', '/moments', '/effects', '/process', '/publish']

export default function SessionResume() {
  const [sessionState, setSessionState] = useState<SessionState | null>(null)
  const [dismissed, setDismissed] = useState(false)
  const navigate = useNavigate()
  const { currentStep, setCurrentStep } = useAppStore()

  useEffect(() => {
    // Fetch current session on mount
    fetch('/api/session/current')
      .then(res => res.json())
      .then((data: SessionState) => {
        // Only show resume banner if we have a saved session AND it's different from step 1
        if (data.step > 1 && data.video_id) {
          setSessionState(data)
        }
      })
      .catch(err => console.error('Failed to fetch session state:', err))
  }, [])

  const handleResume = () => {
    if (!sessionState) return
    
    setCurrentStep(sessionState.step)
    navigate(stepPaths[sessionState.step - 1])
    setDismissed(true)
  }

  const handleStartFresh = () => {
    // Clear store and localStorage
    localStorage.removeItem('clipforge-session')
    window.location.reload()
  }

  if (!sessionState || dismissed || currentStep > 1) {
    return null
  }

  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 max-w-xl w-full px-4">
      <div className="card border-accent/30 shadow-xl">
        <div className="flex items-start gap-4">
          {/* Icon */}
          <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center shrink-0">
            <RefreshCw size={20} className="text-accent" />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-slate-100 mb-1">
              Resume Previous Session?
            </h3>
            <p className="text-sm text-slate-400 mb-3">
              You have an in-progress session at step{' '}
              <span className="text-accent font-medium">
                {sessionState.step}: {stepNames[sessionState.step - 1]}
              </span>
            </p>
            
            {/* Stats */}
            <div className="flex items-center gap-4 text-xs text-slate-500 mb-4">
              {sessionState.moments_count > 0 && (
                <span>{sessionState.moments_count} moments detected</span>
              )}
              {sessionState.selected_moments_count > 0 && (
                <span className="text-accent">{sessionState.selected_moments_count} selected</span>
              )}
              {sessionState.processed_clips_count > 0 && (
                <span className="text-green-400">{sessionState.processed_clips_count} clips ready</span>
              )}
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleResume}
                className="btn btn-primary text-sm px-4 py-2 h-auto"
              >
                <Play size={14} />
                Continue
              </button>
              <button
                onClick={handleStartFresh}
                className="btn btn-secondary text-sm px-4 py-2 h-auto"
              >
                Start Fresh
              </button>
            </div>
          </div>

          {/* Dismiss */}
          <button
            onClick={() => setDismissed(true)}
            className="text-slate-500 hover:text-slate-300 transition-colors shrink-0"
          >
            <X size={18} />
          </button>
        </div>
      </div>
    </div>
  )
}
