import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAppStore } from '../store/useAppStore'
import { GPUStatusIndicator } from '../components/GPUStatusIndicator'
import VideoCard from '../components/VideoCard'
import MomentCard from '../components/MomentCard'
import {
  Play, SlidersHorizontal, Sparkles,
  CheckCircle2, Circle, Loader2,
  Mic, ScanFace, AudioWaveform, Brain, Layers, GitMerge, Save,
  AlertTriangle, ArrowRight, RotateCcw, Scissors
} from 'lucide-react'

interface Substep {
  key: string
  label: string
  icon: React.ReactNode
}

interface ProgressState {
  stage: number
  step: string
  progress: number
  substep?: string
  detail?: string
  errorMessage?: string
}

const STAGE1_SUBSTEPS: Substep[] = [
  { key: 'transcription', label: 'Speech transcription', icon: <Mic size={14} /> },
  { key: 'face_detection', label: 'Face detection', icon: <ScanFace size={14} /> },
  { key: 'audio_analysis', label: 'Audio analysis', icon: <AudioWaveform size={14} /> },
]

const STAGE2_SUBSTEPS: Substep[] = [
  { key: 'context', label: 'Building context', icon: <Layers size={14} /> },
  { key: 'llm_analysis', label: 'AI analysis', icon: <Brain size={14} /> },
  { key: 'consolidation', label: 'Consolidating results', icon: <GitMerge size={14} /> },
]

const STAGE3_SUBSTEPS: Substep[] = [
  { key: 'saving', label: 'Saving moments', icon: <Save size={14} /> },
]

const STAGE_SUBSTEPS: Record<number, Substep[]> = {
  1: STAGE1_SUBSTEPS,
  2: STAGE2_SUBSTEPS,
  3: STAGE3_SUBSTEPS,
}

const STAGE_NAMES: Record<number, string> = {
  1: 'Data Collection',
  2: 'AI Analysis',
  3: 'Finalizing',
}

type SubstepStatus = 'pending' | 'active' | 'done'

function getSubstepStatus(
  substep: Substep,
  stageSubsteps: Substep[],
  activeStage: number,
  thisStage: number,
  activeStep: string,
  stagesDone: Set<number>
): SubstepStatus {
  if (stagesDone.has(thisStage)) return 'done'
  if (thisStage > activeStage) return 'pending'
  if (thisStage < activeStage) return 'done'
  // same stage
  const idx = stageSubsteps.findIndex(s => s.key === substep.key)
  const activeIdx = stageSubsteps.findIndex(s => s.key === activeStep)
  if (activeIdx === -1) return 'pending'
  if (idx < activeIdx) return 'done'
  if (idx === activeIdx) return 'active'
  return 'pending'
}

function SubstepRow({
  substep,
  status,
  detail,
  chunkInfo,
}: {
  substep: Substep
  status: SubstepStatus
  detail?: string
  chunkInfo?: string
}) {
  return (
    <div className="flex items-start gap-2.5 py-1.5">
      <div className="mt-0.5 shrink-0">
        {status === 'done' && <CheckCircle2 size={15} className="text-success" />}
        {status === 'active' && <Loader2 size={15} className="text-accent animate-spin" />}
        {status === 'pending' && <Circle size={15} className="text-slate-700" />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={`text-sm ${
            status === 'done' ? 'text-slate-400' :
            status === 'active' ? 'text-slate-200 font-medium' :
            'text-slate-600'
          }`}>
            {substep.label}
          </span>
          {status !== 'pending' && (
            <span className={`${
              status === 'done' ? 'text-slate-600' : 'text-accent/60'
            }`}>
              {substep.icon}
            </span>
          )}
        </div>
        {status === 'active' && (detail || chunkInfo) && (
          <p className="text-xs text-slate-500 mt-0.5">
            {chunkInfo || detail}
          </p>
        )}
        {status === 'done' && detail && (
          <p className="text-xs text-slate-600 mt-0.5">{detail}</p>
        )}
      </div>
    </div>
  )
}

function StageCard({
  stageNum,
  activeStage,
  activeStep,
  stagesDone,
  progress,
  substepDetail,
  chunkInfo,
}: {
  stageNum: number
  activeStage: number
  activeStep: string
  stagesDone: Set<number>
  progress: ProgressState
  substepDetail?: string
  chunkInfo?: string
}) {
  const substeps = STAGE_SUBSTEPS[stageNum] || []
  const isDone = stagesDone.has(stageNum)
  const isActive = stageNum === activeStage && !isDone
  const isPending = stageNum > activeStage && !isDone

  return (
    <div className={`rounded-xl border p-4 transition-all duration-300 ${
      isActive
        ? 'bg-surface-2 border-accent/30'
        : isDone
          ? 'bg-surface border-slate-800 opacity-70'
          : 'bg-surface border-slate-800/50 opacity-40'
    }`}>
      <div className="flex items-center gap-2 mb-3">
        <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
          isDone ? 'bg-success/20 text-success' :
          isActive ? 'bg-accent/20 text-accent' :
          'bg-slate-800 text-slate-600'
        }`}>
          {isDone ? <CheckCircle2 size={12} /> : stageNum}
        </div>
        <span className={`text-sm font-semibold ${
          isDone ? 'text-success' :
          isActive ? 'text-accent' :
          'text-slate-600'
        }`}>
          {STAGE_NAMES[stageNum]}
        </span>
        {isActive && <Loader2 size={13} className="text-accent animate-spin ml-auto" />}
        {isDone && <CheckCircle2 size={13} className="text-success ml-auto" />}
      </div>
      <div className="space-y-0.5 pl-1">
        {substeps.map(sub => (
          <SubstepRow
            key={sub.key}
            substep={sub}
            status={getSubstepStatus(sub, substeps, activeStage, stageNum, activeStep, stagesDone)}
            detail={sub.key === activeStep || stagesDone.has(stageNum) ? substepDetail : undefined}
            chunkInfo={sub.key === 'llm_analysis' ? chunkInfo : undefined}
          />
        ))}
      </div>
    </div>
  )
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function MomentsPage() {
  const navigate = useNavigate()
  const { currentVideo, moments, setMoments, selectedMomentIds, toggleMoment, llmInstructions, setLlmInstructions, detectionSettings, updateDetectionSettings } = useAppStore()

  const [view, setView] = useState<'setup' | 'detecting' | 'results' | 'error'>('setup')
  const [progressState, setProgressState] = useState<ProgressState>({
    stage: 1, step: '', progress: 0
  })
  const [stagesDone, setStagesDone] = useState<Set<number>>(new Set())
  const [substepDetails, setSubstepDetails] = useState<Record<string, string>>({})
  const [chunkInfo, setChunkInfo] = useState<string>('')
  const [errorMessage, setErrorMessage] = useState('')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [minDuration, setMinDuration] = useState(detectionSettings.minDuration)
  const [maxDuration, setMaxDuration] = useState(detectionSettings.maxDuration)
  const [maxMoments, setMaxMoments] = useState(detectionSettings.maxMoments)

  const wsRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const startTimeRef = useRef<number>(0)

  // Redirect if no video
  useEffect(() => {
    if (!currentVideo) navigate('/videos')
  }, [currentVideo])

  // If we have moments already, show results
  useEffect(() => {
    if (moments.length > 0 && view === 'setup') setView('results')
  }, [])

  const startTimer = () => {
    startTimeRef.current = Date.now()
    timerRef.current = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000))
    }, 1000)
  }

  const stopTimer = () => {
    if (timerRef.current) clearInterval(timerRef.current)
  }

  const startDetection = () => {
    if (!currentVideo) return
    
    // Update detection settings in store
    updateDetectionSettings({ minDuration, maxDuration, maxMoments })
    
    setView('detecting')
    setProgressState({ stage: 1, step: 'transcription', progress: 0.02 })
    setStagesDone(new Set())
    setSubstepDetails({})
    setChunkInfo('')
    setElapsedSeconds(0)
    startTimer()

    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsHost = window.location.hostname
    const ws = new WebSocket(
      `${wsProtocol}://${wsHost}:8000/api/moments/detect_ws?video_id=${currentVideo.id}&min_duration=${minDuration}&max_duration=${maxDuration}&max_moments=${maxMoments}&user_instructions=${encodeURIComponent(llmInstructions || '')}`
    )
    wsRef.current = ws

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.status === 'progress') {
        const newProgress: ProgressState = {
          stage: data.stage ?? 1,
          step: data.step ?? '',
          progress: data.progress ?? 0,
          detail: data.detail,
        }
        setProgressState(newProgress)

        // Track substep details
        if (data.step && data.detail) {
          setSubstepDetails(prev => ({ ...prev, [data.step]: data.detail }))
        }

        // Track chunk progress
        if (data.step === 'llm_analysis' && data.detail) {
          setChunkInfo(data.detail)
        }

        // Mark stages as done when we advance
        if (data.stage === 2) {
          setStagesDone(prev => new Set([...prev, 1]))
        } else if (data.stage === 3) {
          setStagesDone(prev => new Set([...prev, 1, 2]))
        }
      } else if (data.status === 'completed') {
        stopTimer()
        setMoments(data.moments || [])
        if ((data.moments || []).length > 0) {
          setView('results')
        } else {
          setErrorMessage('No moments detected. Try adjusting duration settings or AI instructions.')
          setView('error')
        }
        ws.close()
      } else if (data.status === 'error') {
        stopTimer()
        setErrorMessage(data.message || 'Detection failed')
        setView('error')
        ws.close()
      }
    }

    ws.onerror = () => {
      stopTimer()
      setErrorMessage('WebSocket connection failed. Is the backend running?')
      setView('error')
    }
  }

  const resetDetection = () => {
    if (wsRef.current) wsRef.current.close()
    stopTimer()
    setView('setup')
    setMoments([])
    setProgressState({ stage: 1, step: '', progress: 0 })
    setStagesDone(new Set())
    setSubstepDetails({})
    setChunkInfo('')
    setElapsedSeconds(0)
    setErrorMessage('')
  }

  if (!currentVideo) return null

  const videoDurationMin = Math.round(currentVideo.duration / 60)
  const estimatedMin = Math.round(videoDurationMin * 0.07)

  // ── SETUP VIEW ────────────────────────────────────────────────────────────
  if (view === 'setup') {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        {/* Page header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-slate-100">Moment Detection</h1>
            <p className="text-slate-500 text-sm mt-0.5">Find the best clips with AI</p>
          </div>
          <GPUStatusIndicator />
        </div>

        {/* Video card */}
        <div className="mb-6">
          <VideoCard video={currentVideo} />
        </div>

        {/* Config card */}
        <div className="card space-y-6">
          {/* Section 1: Detection settings */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg bg-accent/10 flex items-center justify-center border border-accent/20">
                <SlidersHorizontal size={14} className="text-accent" />
              </div>
              <span className="text-sm font-semibold text-slate-200">Detection Settings</span>
            </div>
            <div className="space-y-4 pl-1">
              <div>
                <div className="flex justify-between mb-1.5">
                  <label className="text-xs text-slate-400">Clip duration</label>
                  <span className="text-xs text-accent font-medium tabular-nums">{minDuration}–{maxDuration}s</span>
                </div>
                <div className="flex items-center gap-3">
                  <input type="range" min={10} max={120} value={minDuration}
                    onChange={e => setMinDuration(Number(e.target.value))}
                    className="flex-1 accent-accent h-1.5" />
                  <span className="text-slate-600 text-xs">to</span>
                  <input type="range" min={30} max={300} value={maxDuration}
                    onChange={e => setMaxDuration(Number(e.target.value))}
                    className="flex-1 accent-accent h-1.5" />
                </div>
              </div>
              <div>
                <div className="flex justify-between mb-1.5">
                  <label className="text-xs text-slate-400">Max moments</label>
                  <span className="text-xs text-accent font-medium tabular-nums">{maxMoments}</span>
                </div>
                <input type="range" min={3} max={30} value={maxMoments}
                  onChange={e => setMaxMoments(Number(e.target.value))}
                  className="w-full accent-accent h-1.5" />
              </div>
            </div>
          </div>

          <div className="border-t border-slate-800" />

          {/* Section 2: AI instructions */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg bg-accent/10 flex items-center justify-center border border-accent/20">
                <Sparkles size={14} className="text-accent" />
              </div>
              <span className="text-sm font-semibold text-slate-200">AI Instructions</span>
              <span className="text-xs text-slate-600">optional</span>
            </div>
            <textarea
              value={llmInstructions}
              onChange={e => setLlmInstructions(e.target.value)}
              placeholder="E.g. Focus on funny moments and emotional reactions..."
              rows={3}
              className="input w-full resize-none text-sm"
            />
          </div>

          <div className="border-t border-slate-800" />

          {/* Section 3: Launch */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg bg-accent/10 flex items-center justify-center border border-accent/20">
                <Play size={14} className="text-accent" />
              </div>
              <span className="text-sm font-semibold text-slate-200">Launch</span>
              <span className="text-xs text-slate-500 ml-auto">~{estimatedMin}–{estimatedMin + 3} min</span>
            </div>
            <button onClick={startDetection} className="btn btn-primary w-full justify-center py-2.5">
              <Play size={15} />
              Start Detection
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── DETECTING VIEW ────────────────────────────────────────────────────────
  if (view === 'detecting') {
    const { stage, step, progress } = progressState
    const overallPct = Math.round(progress * 100)

    return (
      <div className="p-6 max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-slate-100">Detecting Moments</h1>
            <p className="text-slate-500 text-sm mt-0.5">{currentVideo.title}</p>
          </div>
          <GPUStatusIndicator />
        </div>

        <div className="space-y-3">
          {[1, 2, 3].map(stageNum => (
            <StageCard
              key={stageNum}
              stageNum={stageNum}
              activeStage={stage}
              activeStep={step}
              stagesDone={stagesDone}
              progress={progressState}
              substepDetail={substepDetails[step]}
              chunkInfo={chunkInfo}
            />
          ))}
        </div>

        {/* Overall progress */}
        <div className="mt-6 card">
          <div className="flex justify-between items-center mb-2">
            <span className="text-xs text-slate-500">Overall progress</span>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500 tabular-nums">{formatTime(elapsedSeconds)}</span>
              <span className="text-xs text-accent font-semibold tabular-nums">{overallPct}%</span>
            </div>
          </div>
          <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all duration-1000"
              style={{ width: `${overallPct}%` }}
            />
          </div>
        </div>
      </div>
    )
  }

  // ── ERROR VIEW ────────────────────────────────────────────────────────────
  if (view === 'error') {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <div className="card text-center py-8">
          <AlertTriangle size={32} className="text-danger mx-auto mb-3" />
          <h2 className="text-lg font-bold text-slate-200 mb-2">Detection Failed</h2>
          <p className="text-slate-400 text-sm mb-6 max-w-sm mx-auto">{errorMessage}</p>
          <button onClick={resetDetection} className="btn btn-secondary mx-auto">
            <RotateCcw size={14} />
            Try Again
          </button>
        </div>
      </div>
    )
  }

  // ── RESULTS VIEW ─────────────────────────────────────────────────────────
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Detected Moments</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            {moments.length} moments · {selectedMomentIds.length} selected
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={resetDetection} className="btn btn-secondary text-sm">
            <RotateCcw size={13} />
            Re-detect
          </button>
          <button
            onClick={() => navigate('/effects')}
            disabled={selectedMomentIds.length === 0}
            className="btn btn-primary text-sm"
          >
            Continue
            <ArrowRight size={14} />
          </button>
        </div>
      </div>

      {moments.length === 0 ? (
        <div className="card text-center py-12">
          <Scissors size={32} className="text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400">No moments detected yet.</p>
          <button onClick={() => setView('setup')} className="btn btn-secondary mx-auto mt-4">
            Configure Detection
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {moments.map(moment => (
            <MomentCard
              key={moment.id}
              moment={moment}
              isSelected={selectedMomentIds.includes(moment.id)}
              onToggle={() => toggleMoment(moment.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
