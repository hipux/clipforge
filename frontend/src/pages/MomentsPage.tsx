import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAppStore } from '../store/useAppStore'
import MomentCard from '../components/MomentCard'
import { GPUStatusIndicator } from '../components/GPUStatusIndicator'
import { LLMInstructionsInput } from '../components/LLMInstructionsInput'
import {
  Scissors,
  AlertTriangle,
  Search,
  RefreshCw,
  Zap,
  CheckCircle2,
  Circle,
  Loader2,
  Mic,
  ScanFace,
  AudioWaveform,
  Brain,
  Layers,
  GitMerge,
  SlidersHorizontal,
  Sparkles,
  Play,
} from 'lucide-react'

type ViewState = 'setup' | 'detecting' | 'results'

interface ProgressState {
  overallProgress: number
  stage1: 'pending' | 'active' | 'done'
  stage2: 'pending' | 'active' | 'done'
  // Stage 1 substeps:
  whisper: 'pending' | 'active' | 'done'
  whisperWords: number | null
  whisperSegments: number | null
  yolo: 'pending' | 'active' | 'done'
  yoloFaces: number | null
  audio: 'pending' | 'active' | 'done'
  audioPeaks: number | null
  // Stage 2 substeps:
  contextBuilding: 'pending' | 'active' | 'done'
  llmTotal: number | null
  llmChunksDone: number
  llmConsolidating: 'pending' | 'active' | 'done'
  statusMessage: string
}

// Helper to render status icon based on state
function StatusIcon({ state }: { state: 'pending' | 'active' | 'done' }) {
  if (state === 'done')
    return <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />
  if (state === 'active')
    return <Loader2 size={14} className="text-violet-400 animate-spin shrink-0" />
  return <Circle size={14} className="text-slate-600 shrink-0" />
}

// Premium substep row component
function SubstepRow({
  state,
  icon: Icon,
  label,
  detail,
}: {
  state: 'pending' | 'active' | 'done'
  icon: typeof Mic
  label: string
  detail?: string
}) {
  const textColor =
    state === 'done'
      ? 'text-emerald-400'
      : state === 'active'
      ? 'text-violet-300'
      : 'text-slate-500'

  return (
    <div className="flex items-center gap-3 py-1.5">
      <StatusIcon state={state} />
      <Icon size={14} className={`shrink-0 ${textColor}`} />
      <span className={`text-sm ${textColor}`}>{label}</span>
      {state === 'done' && detail && (
        <span className="text-xs text-slate-500 ml-auto">{detail}</span>
      )}
    </div>
  )
}

export default function MomentsPage() {
  const navigate = useNavigate()
  const {
    currentVideo,
    moments,
    setMoments,
    selectedMomentIds,
    toggleMoment,
    llmInstructions,
    setLlmInstructions,
    detectionSettings,
    updateDetectionSettings,
  } = useAppStore()

  const [view, setView] = useState<ViewState>('setup')
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [momentKeySeq, setMomentKeySeq] = useState(0)
  const wsConnectionRef = useRef<WebSocket | null>(null)
  const detectStartRef = useRef<number>(0)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)

  const [progressState, setProgressState] = useState<ProgressState>({
    overallProgress: 0,
    stage1: 'pending',
    stage2: 'pending',
    whisper: 'pending',
    whisperWords: null,
    whisperSegments: null,
    yolo: 'pending',
    yoloFaces: null,
    audio: 'pending',
    audioPeaks: null,
    contextBuilding: 'pending',
    llmTotal: null,
    llmChunksDone: 0,
    llmConsolidating: 'pending',
    statusMessage: '',
  })

  useEffect(() => {
    if (!currentVideo) {
      navigate('/videos')
    } else if (moments.length > 0) {
      setView('results')
    }
  }, [currentVideo, moments.length, navigate])

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null
    if (view === 'detecting') {
      interval = setInterval(() => {
        setElapsedSeconds(Math.floor((Date.now() - detectStartRef.current) / 1000))
      }, 1000)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [view])

  const formatElapsed = (seconds: number): string => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}m ${s}s`
  }

  const startDetection = async () => {
    if (!currentVideo) return

    setMoments([])
    setProgressState({
      overallProgress: 0,
      stage1: 'pending',
      stage2: 'pending',
      whisper: 'pending',
      whisperWords: null,
      whisperSegments: null,
      yolo: 'pending',
      yoloFaces: null,
      audio: 'pending',
      audioPeaks: null,
      contextBuilding: 'pending',
      llmTotal: null,
      llmChunksDone: 0,
      llmConsolidating: 'pending',
      statusMessage: 'Initializing...',
    })
    setView('detecting')
    detectStartRef.current = Date.now()
    setElapsedSeconds(0)
    setUploadError(null)

    const wsHost = axios.defaults.baseURL?.replace('http', 'ws') || 'ws://localhost:8000'
    const wsUrl = `${wsHost}/api/moments/detect_ws?video_id=${currentVideo.id}&min_duration=${detectionSettings.minDuration}&max_duration=${detectionSettings.maxDuration}&max_moments=${detectionSettings.maxMoments}&user_instructions=${encodeURIComponent(llmInstructions)}`

    const ws = new WebSocket(wsUrl)
    wsConnectionRef.current = ws

    ws.onopen = () => {
      console.log('WebSocket connected')
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.status === 'progress') {
        const { stage, step, progress, detail } = data

        setProgressState((prev) => {
          const s = { ...prev, overallProgress: progress || 0 }

          if (stage === 1) {
            s.stage1 = 'active'
            if (step === 'transcription') s.whisper = 'active'
            if (step === 'whisper_done') {
              s.whisper = 'done'
              s.whisperWords = detail?.words ?? null
              s.whisperSegments = detail?.segments ?? null
            }
            if (step === 'face_detection') {
              s.whisper = s.whisper === 'pending' ? 'done' : s.whisper
              s.yolo = 'active'
            }
            if (step === 'yolo_done') {
              s.yolo = 'done'
              s.yoloFaces = detail?.faces ?? null
            }
            if (step === 'audio_analysis') {
              s.yolo = s.yolo === 'pending' ? 'done' : s.yolo
              s.audio = 'active'
            }
            if (step === 'audio_done') {
              s.audio = 'done'
              s.audioPeaks = detail?.peaks ?? null
            }
            if (step === 'done') {
              s.stage1 = 'done'
              s.whisper = 'done'
              s.yolo = 'done'
              s.audio = 'done'
            }
          }

          if (stage === 2) {
            s.stage1 = 'done'
            s.whisper = 'done'
            s.yolo = 'done'
            s.audio = 'done'
            s.stage2 = 'active'
            if (step === 'context_building') s.contextBuilding = 'active'
            if (step === 'llm_analysis') s.contextBuilding = 'done'
            if (step === 'llm_chunk') {
              s.contextBuilding = 'done'
              s.llmChunksDone = detail?.chunk ?? prev.llmChunksDone
              s.llmTotal = detail?.total ?? prev.llmTotal
              s.llmConsolidating = 'pending'
            }
            if (step === 'llm_consolidate') {
              s.llmConsolidating = 'active'
              s.llmTotal = detail?.total ?? prev.llmTotal
              s.llmChunksDone = s.llmTotal ?? prev.llmChunksDone
            }
            if (step === 'done') {
              s.stage2 = 'done'
              s.contextBuilding = 'done'
              s.llmConsolidating = 'done'
              if (s.llmTotal) s.llmChunksDone = s.llmTotal
            }
          }

          if (stage === 3) {
            s.stage1 = 'done'
            s.stage2 = 'done'
          }

          return s
        })
      } else if (data.status === 'complete') {
        const receivedMoments = data.moments.map((m: any, idx: number) => ({
          ...m,
          keySeq: momentKeySeq + idx,
        }))
        setMoments(receivedMoments)
        setMomentKeySeq((prev) => prev + receivedMoments.length)
        setView('results')

        if (ws.readyState === WebSocket.OPEN) {
          ws.close()
        }
      } else if (data.status === 'error') {
        setUploadError(data.error || 'Detection failed')
        setView('setup')

        if (ws.readyState === WebSocket.OPEN) {
          ws.close()
        }
      }
    }

    ws.onerror = () => {
      setUploadError('WebSocket connection failed')
      setView('setup')
    }

    ws.onclose = () => {
      console.log('WebSocket disconnected')
      wsConnectionRef.current = null
    }
  }

  if (!currentVideo) {
    return null
  }

  const videoDurationMin = Math.round(currentVideo.duration / 60)
  const estimatedMin = Math.round(videoDurationMin * 0.06) + 3

  // Helper to render stage header colors
  const stageHeaderColor = (state: 'pending' | 'active' | 'done') => {
    if (state === 'done') return 'text-emerald-400'
    if (state === 'active') return 'text-white'
    return 'text-slate-600'
  }

  const stageDotColor = (state: 'pending' | 'active' | 'done') => {
    if (state === 'done') return 'bg-emerald-400'
    if (state === 'active') return 'bg-violet-400 animate-pulse'
    return 'bg-slate-600'
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4 mb-8">
        <div className="flex items-center gap-4">
          {currentVideo.thumbnail_url ? (
            <img
              src={currentVideo.thumbnail_url}
              alt=""
              className="w-20 h-12 rounded-lg object-cover flex-shrink-0 border border-slate-700"
            />
          ) : (
            <div className="w-20 h-12 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center flex-shrink-0">
              <Search size={18} className="text-slate-600" />
            </div>
          )}
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-slate-100 mb-0.5">AI Moment Detection</h1>
            <p className="text-slate-400 text-sm truncate max-w-xs">{currentVideo.title}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <GPUStatusIndicator />
        </div>
      </div>

      {uploadError && (
        <div className="mb-6 rounded-lg bg-red-900/20 border border-red-700/30 p-4 flex items-start gap-3">
          <AlertTriangle className="text-red-400 mt-0.5" size={20} />
          <div className="flex-1">
            <h4 className="text-red-400 font-medium text-sm mb-1">Detection Failed</h4>
            <p className="text-red-300 text-sm">{uploadError}</p>
          </div>
        </div>
      )}

      {/* Setup View */}
      {view === 'setup' && (
        <div className="flex items-center justify-center py-12">
          <div className="card max-w-lg w-full">
            <div className="mb-8">
              <h2 className="text-xl font-bold text-slate-200 mb-2 flex items-center gap-2.5">
                <Scissors size={20} className="text-violet-400" />
                Configure Detection
              </h2>
              <p className="text-slate-400 text-sm">
                Set up your AI analysis before launching detection
              </p>
            </div>

            <div className="space-y-8">
              {/* Section 1: Detection Settings */}
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-9 h-9 rounded-xl bg-violet-500/20 border border-violet-500/30 flex items-center justify-center">
                    <SlidersHorizontal size={16} className="text-violet-400" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
                    Detection Settings
                  </h3>
                </div>
                <div className="space-y-4 ml-12">
                  <div>
                    <div className="flex justify-between text-sm mb-2">
                      <span className="text-slate-400">Min clip duration</span>
                      <span className="text-slate-300 font-medium">
                        {detectionSettings.minDuration}s
                      </span>
                    </div>
                    <input
                      type="range"
                      min="15"
                      max="60"
                      step="5"
                      value={detectionSettings.minDuration}
                      onChange={(e) =>
                        updateDetectionSettings({ minDuration: parseInt(e.target.value) })
                      }
                      className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-violet-500"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-sm mb-2">
                      <span className="text-slate-400">Max clip duration</span>
                      <span className="text-slate-300 font-medium">
                        {detectionSettings.maxDuration}s
                      </span>
                    </div>
                    <input
                      type="range"
                      min="30"
                      max="180"
                      step="10"
                      value={detectionSettings.maxDuration}
                      onChange={(e) =>
                        updateDetectionSettings({ maxDuration: parseInt(e.target.value) })
                      }
                      className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-violet-500"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-sm mb-2">
                      <span className="text-slate-400">Max moments</span>
                      <span className="text-slate-300 font-medium">
                        {detectionSettings.maxMoments}
                      </span>
                    </div>
                    <input
                      type="range"
                      min="5"
                      max="30"
                      step="5"
                      value={detectionSettings.maxMoments}
                      onChange={(e) =>
                        updateDetectionSettings({ maxMoments: parseInt(e.target.value) })
                      }
                      className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-violet-500"
                    />
                  </div>
                </div>
              </div>

              <div className="border-t border-slate-700/50" />

              {/* Section 2: AI Instructions */}
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-9 h-9 rounded-xl bg-violet-500/20 border border-violet-500/30 flex items-center justify-center">
                    <Sparkles size={16} className="text-violet-400" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
                    AI Instructions
                  </h3>
                </div>
                <p className="text-slate-500 text-xs ml-12 mb-3">
                  Guide the AI to find specific types of moments — emotional peaks, action scenes,
                  dialogue highlights, etc.
                </p>
                <div className="ml-12">
                  <LLMInstructionsInput
                    value={llmInstructions}
                    onChange={setLlmInstructions}
                    placeholder="e.g. Focus on emotional dialogue scenes and dramatic reveals..."
                  />
                </div>
              </div>

              <div className="border-t border-slate-700/50" />

              {/* Section 3: Launch */}
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-9 h-9 rounded-xl bg-violet-500/20 border border-violet-500/30 flex items-center justify-center">
                    <Play size={16} className="text-violet-400" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
                    Launch
                  </h3>
                </div>
                <div className="ml-12">
                  <button
                    onClick={startDetection}
                    className="w-full py-3.5 rounded-lg bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-white font-semibold text-base transition-all duration-200 flex items-center justify-center gap-2.5"
                  >
                    <Play size={18} />
                    Start Detection
                  </button>
                  <p className="text-center text-slate-500 text-xs mt-3 flex items-center justify-center gap-1">
                    <Zap size={12} />
                    Estimated time: ~{estimatedMin} min on your GPU
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Detecting View */}
      {view === 'detecting' && (
        <div className="flex items-start justify-center py-8">
          <div className="card max-w-2xl w-full">
            <div className="mb-6">
              <h2 className="text-xl font-bold text-slate-200 mb-1">Detection in Progress</h2>
              <p className="text-slate-400 text-sm">{progressState.statusMessage}</p>
            </div>

            <div className="space-y-6">
              {/* Stage 1: Collecting Data */}
              <div className="rounded-xl border border-slate-700/50 bg-slate-800/30 p-5">
                <div className="flex items-center gap-3 mb-3">
                  <div className={`w-3 h-3 rounded-full ${stageDotColor(progressState.stage1)}`} />
                  <h3
                    className={`text-sm font-semibold uppercase tracking-wider ${stageHeaderColor(progressState.stage1)}`}
                  >
                    Stage 1 — Data Collection
                  </h3>
                  {progressState.stage1 === 'active' && (
                    <Zap size={14} className="text-violet-400 ml-1" />
                  )}
                  {progressState.stage1 === 'done' && (
                    <span className="text-slate-500 text-xs ml-auto">
                      {formatElapsed(elapsedSeconds)}
                    </span>
                  )}
                </div>

                <div className="mb-4 bg-slate-700/50 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-600 ease-out bg-gradient-to-r from-violet-500 to-purple-500"
                    style={{
                      width: `${progressState.stage1 === 'done' ? 100 : progressState.overallProgress < 0.6 ? (progressState.overallProgress / 0.6) * 100 : 100}%`,
                    }}
                  />
                </div>

                <div className="space-y-2">
                  <SubstepRow
                    state={progressState.whisper}
                    icon={Mic}
                    label="Speech transcription"
                    detail={
                      progressState.whisperWords
                        ? `${progressState.whisperWords} words`
                        : undefined
                    }
                  />
                  <SubstepRow
                    state={progressState.yolo}
                    icon={ScanFace}
                    label="Face detection"
                    detail={
                      progressState.yoloFaces ? `${progressState.yoloFaces} faces` : undefined
                    }
                  />
                  <SubstepRow
                    state={progressState.audio}
                    icon={AudioWaveform}
                    label="Audio peak analysis"
                    detail={
                      progressState.audioPeaks ? `${progressState.audioPeaks} peaks` : undefined
                    }
                  />
                </div>
              </div>

              {/* Stage 2: AI Analysis */}
              <div className="rounded-xl border border-slate-700/50 bg-slate-800/30 p-5">
                <div className="flex items-center gap-3 mb-3">
                  <div className={`w-3 h-3 rounded-full ${stageDotColor(progressState.stage2)}`} />
                  <h3
                    className={`text-sm font-semibold uppercase tracking-wider ${stageHeaderColor(progressState.stage2)}`}
                  >
                    Stage 2 — AI Analysis
                  </h3>
                  {progressState.stage2 === 'active' && (
                    <Zap size={14} className="text-violet-400 ml-1" />
                  )}
                </div>

                <div className="mb-4 bg-slate-700/50 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-600 ease-out bg-gradient-to-r from-violet-500 to-purple-500"
                    style={{
                      width: `${progressState.stage2 === 'done' ? 100 : progressState.overallProgress >= 0.6 && progressState.overallProgress < 0.9 ? ((progressState.overallProgress - 0.6) / 0.3) * 100 : progressState.stage2 === 'active' ? 10 : 0}%`,
                    }}
                  />
                </div>

                <div className="space-y-2">
                  <SubstepRow
                    state={progressState.contextBuilding}
                    icon={Layers}
                    label="Building context"
                  />
                  <SubstepRow
                    state={
                      progressState.llmChunksDone > 0 && progressState.llmTotal
                        ? progressState.llmChunksDone >= progressState.llmTotal
                          ? 'done'
                          : 'active'
                        : progressState.contextBuilding === 'done'
                        ? 'active'
                        : 'pending'
                    }
                    icon={Brain}
                    label="Qwen3 analysis"
                    detail={
                      progressState.llmTotal
                        ? `${progressState.llmChunksDone}/${progressState.llmTotal} chunks`
                        : undefined
                    }
                  />
                  <SubstepRow
                    state={progressState.llmConsolidating}
                    icon={GitMerge}
                    label="Consolidating moments"
                  />
                </div>
              </div>
            </div>

            {/* Overall progress bar + elapsed */}
            <div className="mt-6 pt-5 border-t border-slate-700/50">
              <div className="mb-3 bg-slate-700/50 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-violet-500 to-purple-500 h-full rounded-full transition-all duration-1000 ease-out"
                  style={{ width: `${Math.min(100, progressState.overallProgress * 100)}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">
                  {Math.round(progressState.overallProgress * 100)}% complete
                </span>
                <span className="text-slate-400">
                  Elapsed:{' '}
                  <span className="text-slate-300 font-medium">
                    {formatElapsed(elapsedSeconds)}
                  </span>
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Results View — Unchanged */}
      {view === 'results' && (
        <div>
          {moments.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-300">
                  Found {moments.length} moment{moments.length !== 1 ? 's' : ''}
                </h2>
                <button
                  onClick={() => setView('setup')}
                  className="btn btn-secondary flex items-center gap-2"
                >
                  <RefreshCw size={15} />
                  Re-detect
                </button>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                {moments.map((moment) => (
                  <MomentCard key={moment.keySeq ?? moment.id} moment={moment} />
                ))}
              </div>
            </div>
          )}

          {moments.length === 0 && (
            <div className="card text-center py-14 border-dashed">
              <Search size={40} className="text-slate-700 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-slate-300 mb-1">No moments detected</h3>
              <p className="text-slate-500 text-sm mb-6">
                The detection completed but found no moments matching the criteria
              </p>
              <button onClick={() => setView('setup')} className="btn btn-primary mx-auto">
                <RefreshCw size={15} />
                Try Again
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
