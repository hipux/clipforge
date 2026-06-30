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
  Users as UsersIcon,
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
  const currentStep = useAppStore(state => state.currentStep)
  const selectedMomentIds = useAppStore(state => state.selectedMomentIds)

  const canAccessStep = (stepId: number) => {
    if (stepId === 1) return true
    if (stepId === 2) return currentVideo !== null
    // Effects and Process require the operator to have actually picked
    // moments on the /moments page. Just having detected moments isn't
    // enough — those steps are pointless if you haven't chosen what to
    // process. Shown as a disabled step in the top-bar by the renderer.
    if (stepId === 3 || stepId === 4) return selectedMomentIds.length > 0
    if (stepId === 5) return processedClips.length > 0
    return false
  }

  // Index of the step matching the current route (0-based). Used as a
  // high-water mark so any step we've moved *past* is shown as complete,
  // regardless of transient data state.
  const currentIndex = steps.findIndex(s => s.path === location.pathname)

  const isStepComplete = (stepId: number) => {
    // We've actually gone past this step in the URL at some point OR
    // the persisted high-water step is beyond this one. Each page calls
    // setCurrentStep(N) on mount, so currentStep tells us how far the
    // operator has actually walked.
    const movedPast = (currentIndex !== -1 && currentIndex + 1 >= stepId) || currentStep >= stepId

    // Step 3 (Effects) was previously marked green the moment you
    // ticked any moment on /moments. Selecting a moment ≠ having
    // configured effects. Mark Effects complete only when you've
    // actually opened the Effects page (currentStep >= 3) or moved
    // past it.
    if (stepId === 3) return movedPast && currentStep >= 3

    // Step 4 (Process): true completion = we actually ran processing.
    let dataComplete = false
    if (stepId === 1) dataComplete = currentVideo !== null
    else if (stepId === 2) dataComplete = moments.length > 0
    else if (stepId === 4) dataComplete = processedClips.length > 0
    return dataComplete || movedPast
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* Top bar */}
      <header className="h-16 shrink-0 border-b border-slate-200 bg-white/90 backdrop-blur-md px-5 sm:px-8 grid grid-cols-[1fr_auto_1fr] items-center gap-6 z-20">
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center shadow-btn">
            <Clapperboard size={18} className="text-white" />
          </div>
          <span className="text-lg font-bold tracking-tight hidden sm:block" style={{ color: '#4f46e5' }}>ClipForge</span>
        </div>

        {/* Stepper (truly centered, no connector lines) */}
        <nav className="flex items-center gap-1 justify-self-center">
          {steps.map((step) => {
            const isCurrent = location.pathname === step.path
            const isComplete = isStepComplete(step.id)
            const isAccessible = canAccessStep(step.id)
            const Icon = step.icon

            let btn = 'group flex items-center gap-2 pl-1.5 pr-3 py-1.5 rounded-full transition-all duration-150 '
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
              <button
                key={step.id}
                onClick={() => isAccessible && navigate(step.path)}
                disabled={!isAccessible}
                className={btn}
              >
                <span className={dot}>
                  {isComplete && !isCurrent ? <Check size={14} strokeWidth={3} /> : <Icon size={14} />}
                </span>
                <span className="text-sm font-medium hidden lg:block">{step.name}</span>
              </button>
            )
          })}
        </nav>

        {/* Right-side utility buttons: Accounts (multi-channel #5) + Analytics */}
        <div className="flex items-center gap-2 justify-self-end">
          <button
            onClick={() => navigate('/accounts')}
            className={'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all ' + (location.pathname === '/accounts' ? 'bg-indigo-600 text-white shadow-btn' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800 border border-slate-200')}
          >
            <UsersIcon size={15} />
            <span className="hidden md:block">Accounts</span>
          </button>
          <button
            onClick={() => navigate('/analytics')}
            className={'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all ' + (location.pathname === '/analytics' ? 'bg-indigo-600 text-white shadow-btn' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800 border border-slate-200')}
          >
            <BarChart3 size={15} />
            <span className="hidden md:block">Analytics</span>
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-auto bg-background">
        <SessionResume />
        <Outlet />
      </main>
    </div>
  )
}