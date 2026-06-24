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
  AlertTriangle, ArrowRight, RotateCcw, Scissors, Clock
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
        {status === 'done' && <CheckCircle2 size={15} className="text-green-600" />}
        {status === 'active' && <Loader2 size={15} className="text-indigo-600 animate-spin" />}
        {status === 'pending' && <Circle size={15} className="text-slate-300" />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={`text-sm ${
            status === 'done' ? 'text-slate-500' :
            status === 'active' ? 'text-slate-800 font-medium' :
            'text-slate-600'
          }`}>
            {substep.label}
          </span>
          {status !== 'pending' && (
            <span className={`${
              status === 'done' ? 'text-slate-600' : 'text-indigo-400'
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
  durationLabel,
}: {
  stageNum: number
  activeStage: number
  activeStep: string
  stagesDone: Set<number>
  progress: ProgressState
  substepDetail?: string
  chunkInfo?: string
  durationLabel?: string
}) {
  const substeps = STAGE_SUBSTEPS[stageNum] || []
  const isDone = stagesDone.has(stageNum)
  const isActive = stageNum === activeStage && !isDone
  const isPending = stageNum > activeStage && !isDone

  return (
    <div className={`rounded-xl border p-4 transition-all duration-300 ${
      isActive
        ? 'bg-indigo-50/60 border-indigo-200'
        : isDone
          ? 'bg-surface border-slate-200 opacity-70'
          : 'bg-surface border-slate-200 opacity-40'
    }`}>
      <div className="flex items-center gap-2 mb-3">
        <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
          isDone ? 'bg-green-100 text-green-600' :
          isActive ? 'bg-violet-500/20 text-indigo-600' :
          'bg-white text-slate-600'
        }`}>
          {isDone ? <CheckCircle2 size={12} /> : stageNum}
        </div>
        <span className={`text-sm font-semibold ${
          isDone ? 'text-green-600' :
          isActive ? 'text-accent' :
          'text-slate-600'
        }`}>
          {STAGE_NAMES[stageNum]}
        </span>
        <div className="ml-auto flex items-center gap-2">
          {durationLabel && (
            <span className="text-[11px] font-medium tabular-nums text-slate-400 flex items-center gap-1">
              <Clock size={11} />{durationLabel}
            </span>
          )}
          {isActive && <Loader2 size={13} className="text-indigo-600 animate-spin" />}
          {isDone && <CheckCircle2 size={13} className="text-green-600" />}
        </div>
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
  const { currentVideo, moments, setMoments, selectedMomentIds, toggleMoment, setSelectedMoments, llmInstructions, setLlmInstructions, detectionSettings, updateDetectionSettings, activeDetectionVideoId, setActiveDetectionVideoId } = useAppStore()

  const [view, setView] = useState<'setup' | 'detecting' | 'results' | 'error'>('setup')
  const [progressState, setProgressState] = useState<ProgressState>({
    stage: 1, step: '', progress: 0
  })
  const [stagesDone, setStagesDone] = useState<Set<number>>(new Set())
  const progressStateRef = useRef<ProgressState>({ stage: 1, step: '', progress: 0 })
  const [substepDetails, setSubstepDetails] = useState<Record<string, string>>({})
  const [chunkInfo, setChunkInfo] = useState<string>('')
  const [errorMessage, setErrorMessage] = useState('')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [stageDurations, setStageDurations] = useState<Record<number, number>>({})
  const stageStartRef = useRef<Record<number, number>>({})
  const [minDuration, setMinDuration] = useState(detectionSettings.minDuration)
  const [maxDuration, setMaxDuration] = useState(detectionSettings.maxDuration)
  const [maxMoments, setMaxMoments] = useState(detectionSettings.maxMoments)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef<number>(0)
  const completedRef = useRef<boolean>(false)
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

  // Resume an in-flight (or just-finished) detection after a page reload by
  // asking the server. The detection WebSocket is keyed by video_id, so simply
  // reconnecting re-attaches to the live job or replays the persisted result.
  useEffect(() => {
    if (!currentVideo) return
    if (activeDetectionVideoId !== currentVideo.id) return
    if (moments.length > 0 || view !== 'setup') return
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(`/api/moments/detect-status/${currentVideo.id}`)
        if (!res.ok) throw new Error('status ' + res.status)
        const data = await res.json()
        if (cancelled) return
        if (data.state === 'running' || data.state === 'completed') {
          setView('detecting')
          setProgressState({ stage: data.stage || 1, step: data.step || '', progress: data.progress || 0.02 })
          completedRef.current = false
          connectWs()
        } else {
          setActiveDetectionVideoId(null)
        }
      } catch {
        if (!cancelled) setActiveDetectionVideoId(null)
      }
    })()
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Track how long each detection stage takes.
  useEffect(() => {
    if (view !== 'detecting') return
    const st = progressState.stage
    if (st >= 1 && stageStartRef.current[st] === undefined) {
      stageStartRef.current[st] = Date.now()
    }
    setStageDurations(prev => {
      let changed = false
      const next = { ...prev }
      stagesDone.forEach(n => {
        if (next[n] === undefined && stageStartRef.current[n] !== undefined) {
          const end = stageStartRef.current[n + 1] ?? Date.now()
          next[n] = Math.max(0, Math.round((end - stageStartRef.current[n]) / 1000))
          changed = true
        }
      })
      return changed ? next : prev
    })
  }, [progressState.stage, stagesDone, view])

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

    setActiveDetectionVideoId(currentVideo.id)
    setView('detecting')
    setProgressState({ stage: 1, step: 'transcription', progress: 0.02 })
    setStagesDone(new Set())
    setSubstepDetails({})
    setChunkInfo('')
    setElapsedSeconds(0)
    setStageDurations({})
    stageStartRef.current = { 1: Date.now() }
    completedRef.current = false
    reconnectAttemptsRef.current = 0
    startTimer()
    connectWs()
  }

  // Detection keeps running on the backend even if the socket blips (e.g. the
  // event loop was briefly busy, or the network hiccuped). Rather than failing
  // immediately, transparently reconnect a few times before giving up. The
  // backend re-attaches the WebSocket to the in-flight job and resumes streaming
  // progress, so the user sees a brief pause instead of "Detection Failed".
  const connectWs = () => {
    if (!currentVideo) return
    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsHost = window.location.hostname
    const ws = new WebSocket(
      `${wsProtocol}://${wsHost}:8000/api/moments/detect_ws?video_id=${currentVideo.id}&min_duration=${minDuration}&max_duration=${maxDuration}&max_moments=${maxMoments}&user_instructions=${encodeURIComponent(llmInstructions || '')}`
    )
    wsRef.current = ws

    ws.onopen = () => {
      reconnectAttemptsRef.current = 0
    }

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
        progressStateRef.current = newProgress

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
        completedRef.current = true
        stopTimer()
        setActiveDetectionVideoId(null)
        setMoments(data.moments || [])
        if ((data.moments || []).length > 0) {
          setView('results')
        } else {
          setErrorMessage('No moments detected. Try adjusting duration settings or AI instructions.')
          setView('error')
        }
        ws.close()
      } else if (data.status === 'error') {
        completedRef.current = true
        stopTimer()
        setActiveDetectionVideoId(null)
        setErrorMessage(data.message || 'Detection failed')
        setView('error')
        ws.close()
      }
    }

    // Don't surface errors here — onclose decides whether to reconnect or fail.
    ws.onerror = () => {}

    ws.onclose = () => {
      // Clean finish (completed/error already handled) — nothing to do.
      if (completedRef.current) return
      const MAX_RECONNECTS = 5
      if (reconnectAttemptsRef.current < MAX_RECONNECTS) {
        reconnectAttemptsRef.current += 1
        const delay = Math.min(2000 * reconnectAttemptsRef.current, 8000)
        setSubstepDetails(prev => ({
          ...prev,
          [progressStateRef.current.step]:
            `Reconnecting… (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECTS})`,
        }))
        reconnectRef.current = setTimeout(connectWs, delay)
      } else {
        stopTimer()
        setErrorMessage('Lost connection to the backend after several retries. The detection may still be running — click Try Again to reconnect.')
        setView('error')
      }
    }
  }

  const resetDetection = () => {
    completedRef.current = true
    if (reconnectRef.current) clearTimeout(reconnectRef.current)
    if (wsRef.current) wsRef.current.close()
    stopTimer()
    setView('setup')
    setMoments([])
    setProgressState({ stage: 1, step: '', progress: 0 })
    setStagesDone(new Set())
    setSubstepDetails({})
    setChunkInfo('')
    setElapsedSeconds(0)
    setStageDurations({})
    stageStartRef.current = {}
    setActiveDetectionVideoId(null)
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
            <h1 className="text-xl font-bold text-slate-900">Moment Detection</h1>
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
              <div className="w-7 h-7 rounded-lg bg-indigo-50 flex items-center justify-center border border-indigo-100">
                <SlidersHorizontal size={14} className="text-accent" />
              </div>
              <span className="text-sm font-semibold text-slate-800">Detection Settings</span>
            </div>
            <div className="space-y-4 pl-1">
              <div>
                <div className="flex justify-between items-baseline mb-3">
                  <label className="text-sm font-medium text-slate-700">Clip duration</label>
                  <span className="text-xs text-indigo-600 font-semibold tabular-nums bg-indigo-50 px-2 py-0.5 rounded-full">{minDuration}–{maxDuration}s</span>
                </div>
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between mb-1.5">
                      <span className="text-xs text-slate-500">Minimum length</span>
                      <span className="text-xs text-slate-700 font-medium tabular-nums">{minDuration}s</span>
                    </div>
                    <input type="range" min={10} max={120} value={minDuration}
                      onChange={e => setMinDuration(Number(e.target.value))}
                      className="range w-full" />
                  </div>
                  <div>
                    <div className="flex justify-between mb-1.5">
                      <span className="text-xs text-slate-500">Maximum length</span>
                      <span className="text-xs text-slate-700 font-medium tabular-nums">{maxDuration}s</span>
                    </div>
                    <input type="range" min={30} max={300} value={maxDuration}
                      onChange={e => setMaxDuration(Number(e.target.value))}
                      className="range w-full" />
                  </div>
                </div>
              </div>
              <div>
                <div className="flex justify-between items-baseline mb-3">
                  <label className="text-sm font-medium text-slate-700">Max moments</label>
                  <span className="text-xs text-indigo-600 font-semibold tabular-nums bg-indigo-50 px-2 py-0.5 rounded-full">{maxMoments}</span>
                </div>
                <input type="range" min={3} max={30} value={maxMoments}
                  onChange={e => setMaxMoments(Number(e.target.value))}
                  className="range w-full" />
              </div>
            </div>
          </div>

          <div className="border-t border-slate-200" />

          {/* Section 2: AI instructions */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg bg-indigo-50 flex items-center justify-center border border-indigo-100">
                <Sparkles size={14} className="text-accent" />
              </div>
              <span className="text-sm font-semibold text-slate-800">AI Instructions</span>
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

          <div className="border-t border-slate-200" />

          {/* Section 3: Launch */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg bg-indigo-50 flex items-center justify-center border border-indigo-100">
                <Play size={14} className="text-accent" />
              </div>
              <span className="text-sm font-semibold text-slate-800">Launch</span>
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
        <div className="mb-6">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h1 className="text-xl font-bold text-slate-900">Detecting Moments</h1>
              <p className="text-slate-500 text-sm mt-0.5 truncate">{currentVideo.title}</p>
            </div>
            <div className="shrink-0 flex items-center gap-3">
              <div className="flex items-center gap-1.5 text-sm bg-surface border border-slate-200 rounded-lg px-2.5 py-1">
                <Clock size={14} className="text-slate-400" />
                <span className="tabular-nums font-medium text-slate-700">{formatTime(elapsedSeconds)}</span>
              </div>
              <GPUStatusIndicator />
            </div>
          </div>
        </div>

        <div className="space-y-3">
          {[1, 2, 3].map(stageNum => {
            const start = stageStartRef.current[stageNum]
            let durationLabel: string | undefined
            if (stageDurations[stageNum] !== undefined) {
              durationLabel = formatTime(stageDurations[stageNum])
            } else if (start !== undefined && stageNum <= stage && !stagesDone.has(stageNum)) {
              durationLabel = formatTime(Math.max(0, Math.round((Date.now() - start) / 1000)))
            }
            return (
              <StageCard
                key={stageNum}
                stageNum={stageNum}
                activeStage={stage}
                activeStep={step}
                stagesDone={stagesDone}
                progress={progressState}
                substepDetail={substepDetails[step]}
                chunkInfo={chunkInfo}
                durationLabel={durationLabel}
              />
            )
          })}
        </div>

        {/* Overall progress */}
        <div className="mt-6 card">
          <div className="flex justify-between items-end mb-2.5">
            <span className="text-sm font-semibold text-slate-800">Overall progress</span>
            <span className="text-lg font-bold text-indigo-600 tabular-nums leading-none">{overallPct}%</span>
          </div>
          <div className="w-full h-2.5 bg-slate-200 rounded-full overflow-hidden ring-1 ring-slate-300/60">
            <div
              className="h-full bg-gradient-to-r from-indigo-500 to-indigo-600 rounded-full transition-all duration-1000"
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
          <h2 className="text-lg font-bold text-slate-800 mb-2">Detection Failed</h2>
          <p className="text-slate-500 text-sm mb-6 max-w-sm mx-auto">{errorMessage}</p>
          <button onClick={resetDetection} className="btn btn-secondary mx-auto">
            <RotateCcw size={14} />
            Try Again
          </button>
        </div>
      </div>
    )
  }

  // ── RESULTS VIEW ─────────────────────────────────────────────────────────
  const allSelected = moments.length > 0 && selectedMomentIds.length === moments.length
  return (
    <div className="flex flex-col min-h-full max-w-5xl mx-auto w-full">
      <div className="px-6 pt-6 pb-4">
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Detected Moments</h1>
            <p className="text-slate-500 text-sm mt-1">
              We found <span className="font-semibold text-slate-700">{moments.length}</span> moments worth clipping. Pick the ones you like.
            </p>
          </div>
          <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-full px-1.5 py-1 shadow-soft">
            <span className="px-3 text-sm text-slate-500">
              <span className="font-semibold text-accent">{selectedMomentIds.length}</span> selected
            </span>
            <button
              onClick={() => setSelectedMoments(allSelected ? [] : moments.map(m => m.id))}
              className="px-3 py-1.5 text-sm font-medium rounded-full text-slate-700 hover:bg-slate-100 transition-colors"
            >
              {allSelected ? 'Clear all' : 'Select all'}
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 px-6 pb-28">
        {moments.length === 0 ? (
          <div className="card text-center py-12 mt-4">
            <Scissors size={32} className="text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500">No moments detected yet.</p>
            <button onClick={() => setView('setup')} className="btn btn-secondary mx-auto mt-4">
              Configure Detection
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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

      <div className="sticky bottom-0 left-0 right-0 border-t border-slate-200 bg-white/85 backdrop-blur-md">
        <div className="px-6 py-3.5 flex items-center justify-between">
          <button onClick={resetDetection} className="btn btn-secondary text-sm">
            <RotateCcw size={14} />
            Re-detect
          </button>
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-400 hidden sm:block">
              {selectedMomentIds.length} clip{selectedMomentIds.length === 1 ? '' : 's'} ready
            </span>
            <button
              onClick={() => navigate('/effects')}
              disabled={selectedMomentIds.length === 0}
              className="btn btn-primary"
            >
              Continue to Effects
              <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}