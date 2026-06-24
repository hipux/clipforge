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
  BarChart3,
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
    <div className="flex flex-col h-screen overflow-hidden">
      {/* Top bar */}
      <header className="h-16 shrink-0 border-b border-slate-200 bg-white/90 backdrop-blur-md px-5 sm:px-8 flex items-center justify-between gap-6 z-20">
        {/* Logo */}
        <div className="flex items-center gap-2.5 shrink-0">
          <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center shadow-btn">
            <Clapperboard size={18} className="text-white" />
          </div>
          <span className="text-lg font-bold tracking-tight hidden sm:block" style={{ color: '#4f46e5' }}>ClipForge</span>
        </div>

        {/* Stepper */}
        <nav className="flex items-center">
          {steps.map((step, i) => {
            const isCurrent = location.pathname === step.path
            const isComplete = isStepComplete(step.id)
            const isAccessible = canAccessStep(step.id)
            const Icon = step.icon

            let btn = 'group flex items-center gap-2 pl-1.5 pr-2.5 py-1.5 rounded-full transition-all duration-150 '
            if (isCurrent) btn += 'bg-indigo-50 text-indigo-700'
            else if (isComplete) btn += 'text-green-700 hover:bg-slate-50'
            else if (isAccessible) btn += 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'
            else btn += 'text-slate-300 cursor-not-allowed'

            let dot = 'w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold border transition-all duration-150 '
            if (isCurrent) dot += 'bg-indigo-600 text-white border-indigo-600 shadow-btn'
            else if (isComplete) dot += 'bg-green-500 text-white border-green-500'
            else if (isAccessible) dot += 'bg-white text-slate-400 border-slate-300 group-hover:border-indigo-400'
            else dot += 'bg-slate-50 text-slate-300 border-slate-200'

            return (
              <div key={step.id} className="flex items-center">
                <button
                  onClick={() => isAccessible && navigate(step.path)}
                  disabled={!isAccessible}
                  className={btn}
                >
                  <span className={dot}>
                    {isComplete && !isCurrent ? <Check size={14} strokeWidth={3} /> : <Icon size={14} />}
                  </span>
                  <span className="text-sm font-medium hidden lg:block">{step.name}</span>
                </button>
                {i < steps.length - 1 && (
                  <div className={`w-4 sm:w-7 h-px mx-0.5 ${isComplete ? 'bg-green-300' : 'bg-slate-200'}`} />
                )}
              </div>
            )
          })}
        </nav>

        {/* Analytics tab */}
        <button
          onClick={() => navigate('/analytics')}
          className={'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all shrink-0 ' + (location.pathname === '/analytics' ? 'bg-indigo-600 text-white shadow-btn' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800 border border-slate-200')}
        >
          <BarChart3 size={15} />
          <span className="hidden md:block">Analytics</span>
        </button>

        <div className="w-9 shrink-0" />
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-auto bg-background">
        <SessionResume />
        <Outlet />
      </main>
    </div>
  )
}