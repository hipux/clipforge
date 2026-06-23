import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAppStore } from '../store/useAppStore'
import SessionResume from './SessionResume'
import {
  Download,
  Scissors,
  Sliders,
  Cpu,
  Upload,
  Check,
  Clapperboard,
  Zap,
} from 'lucide-react'

const steps = [
  { id: 1, name: 'Download', path: '/download', icon: Download },
  { id: 2, name: 'Moments', path: '/moments', icon: Scissors },
  { id: 3, name: 'Effects', path: '/effects', icon: Sliders },
  { id: 4, name: 'Process', path: '/process', icon: Cpu },
  { id: 5, name: 'Publish', path: '/publish', icon: Upload },
]

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const currentVideo = useAppStore(state => state.currentVideo)
  const moments = useAppStore(state => state.moments)
  const processedClips = useAppStore(state => state.processedClips)

  const canAccessStep = (stepId: number) => {
    if (stepId === 1) return true
    if (stepId === 2) return currentVideo !== null
    if (stepId === 3) return moments.length > 0
    if (stepId === 4) return moments.length > 0
    if (stepId === 5) return processedClips.length > 0
    return false
  }

  const isStepComplete = (stepId: number) => {
    if (stepId === 1) return currentVideo !== null
    if (stepId === 2) return moments.length > 0
    if (stepId === 3) return moments.some(m => m.approved)
    if (stepId === 4) return processedClips.length > 0
    return false
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside
        className="w-60 flex flex-col border-r border-slate-800/80 shrink-0"
        style={{ background: 'linear-gradient(180deg, #0d0d14 0%, #10101a 100%)' }}
      >
        {/* Logo */}
        <div className="px-5 py-5 border-b border-slate-800/80">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
              <Clapperboard size={16} className="text-violet-400" />
            </div>
            <div>
              <h1
                className="text-base font-bold leading-tight"
                style={{ background: 'linear-gradient(90deg, #7c3aed, #a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}
              >
                ClipForge
              </h1>
              <p className="text-[10px] text-slate-500 leading-tight">Video Clip Tool</p>
            </div>
          </div>
        </div>

        {/* Steps nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-widest px-3 mb-2">Workflow</p>
          {steps.map((step) => {
            const isCurrent = location.pathname === step.path
            const isComplete = isStepComplete(step.id)
            const isAccessible = canAccessStep(step.id)
            const Icon = step.icon

            let cls = 'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-150 text-sm '
            if (isCurrent) {
              cls += 'step-active font-medium'
            } else if (!isAccessible) {
              cls += 'step-locked opacity-40'
            } else if (isComplete) {
              cls += 'step-complete'
            } else {
              cls += 'step-available'
            }

            return (
              <button
                key={step.id}
                onClick={() => isAccessible && navigate(step.path)}
                disabled={!isAccessible}
                className={cls}
              >
                <Icon size={16} className={isCurrent ? 'text-violet-400' : ''} />
                <span className="flex-1 text-left">{step.name}</span>
                {isComplete && !isCurrent && (
                  <Check size={13} className="text-success shrink-0" />
                )}
                {isCurrent && (
                  <div className="w-1.5 h-1.5 rounded-full bg-violet-500 shrink-0" />
                )}
              </button>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-slate-800/80">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-600">
            <Zap size={11} className="text-violet-400/60" />
            <span>100% Free · No API Costs</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto bg-background">
        <SessionResume />
        <Outlet />
      </main>
    </div>
  )
}
