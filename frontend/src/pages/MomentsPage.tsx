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

// Terminal-style substep row component
function SubstepRow({ state, label, detail }: {
  state: 'pending' | 'active' | 'done'
  label: string
  detail?: string
}) {
  return (
    <div className="flex items-start gap-2 py-0.5 ml-6">
      <div className="mt-1 flex-shrink-0">
        {state === 'done' && <span className="text-green-400 text-xs">✓</span>}
        {state === 'active' && <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse inline-block mt-0.5" />}
        {state === 'pending' && <span className="w-2 h-2 rounded-full bg-slate-600 inline-block mt-0.5" />}
      </div>
      <span className={`text-sm ${
        state === 'done' ? 'text-slate-400' :
        state === 'active' ? 'text-slate-100 font-medium' :
        'text-slate-600'
      }`}>
        {label}
        {state === 'done' && detail && (
          <span className="text-slate-500 ml-2 font-normal">{detail}</span>
        )}
      </span>
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

        setProgressState(prev => {
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
              s.whisper = 'done'; s.yolo = 'done'; s.audio = 'done'
            }
          }
          
          if (stage === 2) {
            s.stage1 = 'done'
            s.whisper = 'done'; s.yolo = 'done'; s.audio = 'done'
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

      {/* Setup View — Pre-Detection Wizard */}
      {view === 'setup' && (
        <div className="flex items-center justify-center py-12">
          <div className="card max-w-lg w-full">
            <div className="mb-8">
              <h2 className="text-xl font-bold text-slate-200 mb-2 flex items-center gap-2">
                <Scissors size={20} className="text-cyan-400" />
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
                  <span className="w-6 h-6 rounded-full bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-xs font-bold text-cyan-400">
                    1
                  </span>
                  <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                    Detection Settings
                  </h3>
                </div>
                <div className="space-y-4 ml-9">
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
                      className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
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
                      className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
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
                      className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
                    />
                  </div>
                </div>
              </div>

              <div className="border-t border-slate-700/50" />

              {/* Section 2: AI Instructions */}
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <span className="w-6 h-6 rounded-full bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-xs font-bold text-cyan-400">
                    2
                  </span>
                  <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                    AI Instructions
                  </h3>
                </div>
                <p className="text-slate-500 text-xs ml-9 mb-3">
                  Guide the AI to find specific types of moments — emotional peaks, action
                  scenes, dialogue highlights, etc.
                </p>
                <div className="ml-9">
                  <LLMInstructionsInput
                    value={llmInstructions}
                    onChange={setLlmInstructions}
                    isGPU={true}
                  />
                </div>
              </div>

              <div className="border-t border-slate-700/50" />

              {/* Section 3: Launch */}
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <span className="w-6 h-6 rounded-full bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-xs font-bold text-cyan-400">
                    3
                  </span>
                  <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                    Launch
                  </h3>
                </div>
                <div className="ml-9">
                  <button
                    onClick={startDetection}
                    className="w-full py-3.5 rounded-lg bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-white font-semibold text-base transition-all duration-200 flex items-center justify-center gap-2"
                  >
                    <Zap size={18} />
                    Start Detection
                  </button>
                  <p className="text-center text-slate-500 text-xs mt-3">
                    Estimated time: ~{estimatedMin}–{estimatedMin + 3} min on your GPU
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Detecting View — Terminal-Log-Style Detailed Progress */}
      {view === 'detecting' && (
        <div className="flex items-start justify-center py-8">
          <div className="card max-w-2xl w-full">
            <div className="mb-6 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-slate-200 mb-1">Analysing...</h2>
                <p className="text-slate-400 text-sm">{progressState.statusMessage}</p>
              </div>
              <span className="text-slate-400 text-sm">
                {formatElapsed(elapsedSeconds)}
              </span>
            </div>

            {/* Overall progress bar */}
            <div className="mb-8 bg-slate-700 rounded-full h-2 overflow-hidden">
              <div
                className="bg-gradient-to-r from-cyan-500 to-cyan-400 h-full rounded-full transition-all duration-1000 ease-out"
                style={{
                  width: `${Math.min(100, progressState.overallProgress * 100)}%`,
                }}
              />
            </div>

            <div className="space-y-8">
              {/* Stage 1 — Data Collection */}
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      progressState.stage1 === 'done'
                        ? 'bg-green-400'
                        : progressState.stage1 === 'active'
                        ? 'bg-cyan-400 animate-pulse'
                        : 'bg-slate-600'
                    }`}
                  />
                  <h3
                    className={`text-base font-semibold ${
                      progressState.stage1 === 'done'
                        ? 'text-green-400'
                        : progressState.stage1 === 'active'
                        ? 'text-cyan-400'
                        : 'text-slate-600'
                    }`}
                  >
                    Stage 1 — Data Collection
                  </h3>
                </div>

                <SubstepRow
                  state={progressState.whisper}
                  label="🎙️ Whisper transcription"
                  detail={progressState.whisperWords ? `${progressState.whisperWords} words, ${progressState.whisperSegments} segments` : undefined}
                />
                <SubstepRow
                  state={progressState.yolo}
                  label="👤 YOLO face detection"
                  detail={progressState.yoloFaces !== null ? `${progressState.yoloFaces} faces` : undefined}
                />
                <SubstepRow
                  state={progressState.audio}
                  label="🔊 Audio peak analysis"
                  detail={progressState.audioPeaks !== null ? `${progressState.audioPeaks} peaks` : undefined}
                />
              </div>

              {/* Stage 2 — AI Analysis */}
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      progressState.stage2 === 'done'
                        ? 'bg-green-400'
                        : progressState.stage2 === 'active'
                        ? 'bg-cyan-400 animate-pulse'
                        : 'bg-slate-600'
                    }`}
                  />
                  <h3
                    className={`text-base font-semibold ${
                      progressState.stage2 === 'done'
                        ? 'text-green-400'
                        : progressState.stage2 === 'active'
                        ? 'text-cyan-400'
                        : 'text-slate-600'
                    }`}
                  >
                    Stage 2 — AI Analysis
                  </h3>
                </div>

                <SubstepRow
                  state={progressState.contextBuilding}
                  label="🧩 Building context"
                />
                
                <SubstepRow
                  state={progressState.llmTotal && progressState.llmTotal > 0 ? (progressState.llmChunksDone > 0 ? 'active' : 'pending') : 'pending'}
                  label="🧠 Qwen3 analysis"
                  detail={progressState.llmTotal && progressState.llmTotal > 0 ? `${progressState.llmChunksDone}/${progressState.llmTotal} chunks` : undefined}
                />

                {/* Dynamic chunk lines when llmTotal > 0 */}
                {progressState.llmTotal && progressState.llmTotal > 0 && (
                  <div className="ml-8 space-y-0.5">
                    {Array.from({ length: progressState.llmTotal }).map((_, i) => {
                      const chunkNum = i + 1
                      const chunkState = chunkNum < progressState.llmChunksDone ? 'done' :
                                        chunkNum === progressState.llmChunksDone ? 'active' :
                                        'pending'
                      return (
                        <div key={i} className="flex items-center gap-2 py-0.5 text-xs">
                          <div className="w-1.5 h-1.5 rounded-full" style={{
                            backgroundColor: chunkState === 'done' ? 'rgb(74 222 128)' :
                                           chunkState === 'active' ? 'rgb(34 211 238)' :
                                           'rgb(71 85 105)'
                          }} />
                          <span className={
                            chunkState === 'done' ? 'text-slate-500' :
                            chunkState === 'active' ? 'text-cyan-400' :
                            'text-slate-600'
                          }>
                            Chunk {chunkNum}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                )}

                <SubstepRow
                  state={progressState.llmConsolidating}
                  label="🔀 Consolidating results"
                />
              </div>
            </div>

            {/* Progress percentage + elapsed */}
            <div className="mt-6 pt-6 border-t border-slate-700">
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
