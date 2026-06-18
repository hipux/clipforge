import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { RotateCcw, X } from 'lucide-react'
import { useAppStore } from '../store/useAppStore'

export default function SessionResume() {
  const navigate = useNavigate()
  const location = useLocation()
  const { currentVideo, currentStep } = useAppStore()
  const [show, setShow] = useState(false)
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    if (checked) return

    // Check if there's a stored session (currentVideo means we have a session)
    // Only show if we're on /download and have a saved session
    if (currentVideo && currentStep > 1 && location.pathname === '/download') {
      setShow(true)
    }
    setChecked(true)
  }, [currentVideo, currentStep, location.pathname, checked])

  const handleRestore = () => {
    // Navigate to the saved step
    const steps = ['download', 'download', 'moments', 'effects', 'process', 'publish']
    const path = `/${steps[currentStep] || 'download'}`
    navigate(path)
    setShow(false)
  }

  const handleDismiss = () => {
    setShow(false)
  }

  if (!show) return null

  const stepNames = ['', 'Download', 'Moments', 'Effects', 'Process', 'Publish']
  const stepName = stepNames[currentStep] || 'Download'

  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 w-full max-w-md px-4">
      <div className="bg-gradient-to-r from-accent/20 to-accent/10 backdrop-blur-sm border border-accent/30 rounded-2xl shadow-xl p-4 flex items-center gap-3 animate-in fade-in slide-in-from-top duration-300">
        <div className="w-10 h-10 rounded-full bg-accent/20 flex items-center justify-center flex-shrink-0">
          <RotateCcw size={20} className="text-accent" />
        </div>
        <div className="flex-1">
          <div className="font-semibold text-slate-100 text-sm mb-0.5">
            Resume previous session?
          </div>
          <div className="text-slate-400 text-xs">
            Continue from <span className="text-slate-300 font-medium">{stepName}</span> step
          </div>
        </div>
        <div className="flex gap-2 flex-shrink-0">
          <button
            onClick={handleRestore}
            className="px-4 py-2 rounded-lg bg-accent hover:bg-accent-hover text-white text-sm font-medium transition-colors"
          >
            Restore
          </button>
          <button
            onClick={handleDismiss}
            className="w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors"
            aria-label="Dismiss"
          >
            <X size={16} className="text-slate-400" />
          </button>
        </div>
      </div>
    </div>
  )
}
