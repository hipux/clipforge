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
  ArrowRight,
  ArrowLeft,
  RefreshCw,
  CheckSquare,
  Square,
} from 'lucide-react'

type ViewState = 'setup' | 'detecting' | 'results'

interface ProgressState {
  stage1: 'pending' | 'active' | 'done'
  stage1Step: 'transcription' | 'face_detection' | 'audio_analysis' | null
  stage2: 'pending' | 'active' | 'done'
  stage2Step: 'context_building' | 'llm_analysis' | null
  stage3: 'pending' | 'active' | 'done'
  overallProgress: number
  statusMessage: string
  stage1Progress: number
  stage2Progress: number
  stage3Progress: number
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
    stage1: 'pending',
    stage1Step: null,
    stage2: 'pending',
    stage2Step: null,
    stage3: 'pending',
    overallProgress: 0,
    statusMessage: '',
    stage1Progress: 0,
    stage2Progress: 0,
    stage3Progress: 0,
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
      stage1: 'pending',
      stage1Step: null,
      stage2: 'pending',
      stage2Step: null,
      stage3: 'pending',
      overallProgress: 0,
      statusMessage: 'Initializing...',
      stage1Progress: 0,
      stage2Progress: 0,
      stage3Progress: 0,
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
        const { stage, step, progress, message } = data

        setProgressState((prev) => {
          const newState: ProgressState = { ...prev }

          newState.overallProgress = progress || 0
          newState.statusMessage = message || ''

          if (stage === 1) {
            if (step === 'done') {
              newState.stage1 = 'done'
              newState.stage1Step = 'audio_analysis'
              newState.stage1Progress = 1.0
            } else {
              newState.stage1 = 'active'
              newState.stage1Step = step as any
              newState.stage1Progress = ((progress || 0) / 0.6) * 1.0
            }
            newState.stage2 = 'pending'
            newState.stage2Step = null
            newState.stage3 = 'pending'
          } else if (stage === 2) {
            newState.stage1 = 'done'
            newState.stage1Step = 'audio_analysis'
            newState.stage1Progress = 1.0

            if (step === 'done') {
              newState.stage2 = 'done'
              newState.stage2Step = 'llm_analysis'
              newState.stage2Progress = 1.0
            } else {
              newState.stage2 = 'active'
              newState.stage2Step = step as any
              const stage2Start = 0.6
              const stage2End = 0.9
              newState.stage2Progress =
                ((progress || 0) - stage2Start) / (stage2End - stage2Start)
            }
            newState.stage3 = 'pending'
          } else if (stage === 3) {
            newState.stage1 = 'done'
            newState.stage1Step = 'audio_analysis'
            newState.stage1Progress = 1.0
            newState.stage2 = 'done'
            newState.stage2Step = 'llm_analysis'
            newState.stage2Progress = 1.0

            if (step === 'done') {
              newState.stage3 = 'done'
              newState.stage3Progress = 1.0
            } else {
              newState.stage3 = 'active'
              const stage3Start = 0.9
              newState.stage3Progress = ((progress || 0) - stage3Start) / (1.0 - stage3Start)
            }
          }

          return newState
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
  const estimatedTimeMin = Math.max(6, Math.min(9, Math.ceil(videoDurationMin * 0.3)))

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">AI Moment Detection</h1>
          <p className="page-description">{currentVideo.title}</p>
        </div>
        <div className="flex items-center gap-3">
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
            <div className="mb-6">
              <h2 className="text-xl font-bold text-slate-200 mb-2">Configure Detection</h2>
              <p className="text-slate-400 text-sm">
                Set up AI analysis parameters before starting
              </p>
            </div>

            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  🧀 AI Instructions
                </label>
                <LLMInstructionsInput
                  value={llmInstructions}
                  onChange={setLlmInstructions}
                  placeholder="Optional: tell the AI what kind of moments to look for..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-3">
                  ⚙ḯ Detection Settings
                </label>
                <div className="space-y-4">
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
                      className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-purple-500"
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
                      className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-purple-500"
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
                      className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-purple-500"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-8 pt-6 border-t border-slate-700">
              <button
                onClick={startDetection}
                className="btn btn-primary w-full py-3 text-base font-semibold"
              >
                🚀 Start Detection
              </button>
              <p className="text-center text-slate-500 text-xs mt-3">
                Estimated time: ~{estimatedTimeMin}–{estimatedTimeMin + 3} min (your RTX 5060 GPU
  </p>
            </div>
          </div>
        </div>
      )}

      {/* Detecting View - Progress Timeline */}
      {view === 'detecting' && (
        <div className="flex items-start justify-center py-8">
          <div className="card max-w-2xl w-full">
            <div className="mb-6">
              <h2 className="text-xl font-bold text-slate-200 mb-1">Detection in Progress</h2>
              <p className="text-slate-400 text-sm">{progressState.statusMessage}</p>
            </div>

            <div className="space-y-8">
              {/* Stage 1: Collecting Data */}
              <div>
                <div className="flex items-center gap-3 mb-3">
                  <div
                    className={`w-4 h-4 rounded-full ${
                      progressState.stage1 === 'done'
                        ? 'bg-green-400'
                        : progressState.stage1 === 'active'
                        ? 'bg-yellow-400 animate-pulse'
                        : 'bg-slate-600'
                    }`}
                  />
                  <h3
                    className={`text-base font-semibold ${
                      progressState.stage1 === 'done'
                        ? 'text-green-400'
                        : progressState.stage1 === 'active'
                        ? 'text-yellow-400'
                        : 'text-slate-600'
                    }`}
                  >
                    Stage 1: Collecting Data
                  </h3>
                  {progressState.stage1 !== 'pending' && (
                    <span className="text-slate-500 text-sm ml-auto">
                      {progressState.stage1 === 'done' ? formatElapsed(elapsedSeconds) : ''}
                    </span>
                  )}
                </div>

                <div className="mb-3 bg-slate-700 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-purple-500 h-full transition-all duration-300"
                    style={{
                      width: `${Math.min(100, progressState.stage1Progress * 100)}%`,
                    }}
                  />
                </div>

                <div className="ml-7 space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    {progressState.stage1 === 'done' ||
                    (progressState.stage1 === 'active' &&
                      progressState.stage1Step !== 'transcription') ? (
                      <CheckSquare size={14} className="text-green-400" />
                    ) : progressState.stage1 === 'active' &&
                      progressState.stage1Step === 'transcription' ? (
                      <RefreshCw size={14} className="text-yellow-400 animate-spin" />
                    ) : (
                      <Square size={14} className="text-slate-600" />
                    )}
                    <span
                      className={
                        progressState.stage1 === 'done' ||
                        (progressState.stage1 === 'active' &&
                          progressState.stage1Step !== 'transcription')
                          ? 'text-green-400'
                          : progressState.stage1 === 'active' &&
                            progressState.stage1Step === 'transcription'
                          ? 'text-yellow-400'
                          : 'text-slate-600'
                      }
                    >
                      🍙️  Whisper transcription
                    </span>
                  </div>

                  <div className="flex items-center gap-2 text-sm">
                    {progressState.stage1 === 'done' ||
                    (progressState.stage1 === 'active' &&
                      progressState.stage1Step === 'audio_analysis') ? (
                      <CheckSquare size={14} className="text-green-400" />
                    ) : progressState.stage1 === 'active' &&
                      progressState.stage1Step === 'face_detection' ? (
                      <RefreshCw size={14} className="text-yellow-400 animate-spin" />
                    ) : (
                      <Square size={14} className="text-slate-600" />
                    )}
                    <span
                      className={
                        progressState.stage1 === 'done' ||
                        (progressState.stage1 === 'active' &&
                          progressState.stage1Step === 'audio_analysis')
                          ? 'text-green-400'
                          : progressState.stage1 === 'active' &&
                            progressState.stage1Step === 'face_detection'
                          ? 'text-yellow-400'
                          : 'text-slate-600'
                      }
                    >
                      👤 YOLO face detection
                    </span>
                  </div>

                  <div className="flex items-center gap-2 text-sm">
                    {progressState.stage1 === 'done' ? (
                      <CheckSquare size={14} className="text-green-400" />
                    ) : progressState.stage1 === 'active' &&
                      progressState.stage1Step === 'audio_analysis' ? (
                      <RefreshCw size={14} className="text-yellow-400 animate-spin" />
                    ) : (
                      <Square size={14} className="text-slate-600" />
                    )}
                    <span
                      className={
                        progressState.stage1 === 'done'
                          ? 'text-green-400'
                          : progressState.stage1 === 'active' &&
                            progressState.stage1Step === 'audio_analysis'
                          ? 'text-yellow-400'
                          : 'text-slate-600'
                      }
                    >
                      🔊 Audio peak analysis
                    </span>
                  </div>
                </div>
              </div>

              {/* Stage 2: AI Analysis */}
              <div>
                <div className="flex items-center gap-3 mb-3">
                  <div
                    className={`w-4 h-4 rounded-full ${
                      progressState.stage2 === 'done'
                        ? 'bg-green-400'
                        : progressState.stage2 === 'active'
                        ? 'bg-yellow-400 animate-pulse'
                        : 'bg-slate-600'
                    }`}
                  />
                  <h3
                    className={`text-base font-semibold ${
                      progressState.stage2 === 'done'
                        ? 'text-green-400'
                        : progressState.stage2 === 'active'
                        ? 'text-yellow-400'
                        : 'text-slate-600'
                    }`}
                  >
                    Stage 2: AI Analysis
                  </h3>
                </div>

                <div className="mb-3 bg-slate-700 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-purple-500 h-full transition-all duration-300"
                    style={{
                      width: `${Math.min(100, progressState.stage2Progress * 100)}%`,
                    }}
                  />
                </div>

                <div className="ml-7 space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    {progressState.stage2 === 'done' ||
                    (progressState.stage2 === 'active' &&
                      progressState.stage2Step === 'llm_analysis') ? (
                      <CheckSquare size={14} className="text-green-400" />
                    ) : progressState.stage2 === 'active' &&
                      progressState.stage2Step === 'context_building' ? (
                      <RefreshCw size={14} className="text-yellow-400 animate-spin" />
                    ) : (
                      <Square size={14} className="text-slate-600" />
                    )}
                    <span
                      className={
                        progressState.stage2 === 'done' ||
                        (progressState.stage2 === 'active' &&
                          progressState.stage2Step === 'llm_analysis')
                          ? 'text-green-400'
                          : progressState.stage2 === 'active' &&
                            progressState.stage2Step === 'context_building'
                          ? 'text-yellow-400'
                          : 'text-slate-600'
                      }
                    >
                      🧩 Building context chunks
                    </span>
                  </div>

                  <div className="flex items-center gap-2 text-sm">
                    {progressState.stage2 === 'done' ? (
                      <CheckSquare size={14} className="text-green-400" />
                    ) : progressState.stage2 === 'active' &&
                      progressState.stage2Step === 'llm_analysis' ? (
                      <RefreshCw size={14} className="text-yellow-400 animate-spin" />
                    ) : (
                      <Square size={14} className="text-slate-600" />
                    )}
                    <span
                      className={
                        progressState.stage2 === 'done'
                          ? 'text-green-400'
                          : progressState.stage2 === 'active' &&
                            progressState.stage2Step === 'llm_analysis'
                          ? 'text-yellow-400'
                          : 'text-slate-600'
                      }
                    >
                      🧰 Qwen3 — analyzing chunks
                    </span>
                  </div>

                  <div className="flex items-center gap-2 text-sm">
                    {progressState.stage2 === 'done' ? (
                      <CheckSquare size={14} className="text-green-400" />
                    ) : (
                      <Square size={14} className="text-slate-600" />
                    )}
                    <span
                      className={
                        progressState.stage2 === 'done' ? 'text-green-400' : 'text-slate-600'
                      }
                    >
                      🔀 Consolidating moments
                    </span>
                  </div>
                </div>
              </div>

              {/* Stage 3: Finalizing */}
              <div>
                <div className="flex items-center gap-3 mb-3">
                  <div
                    className={`w-4 h-4 rounded-full ${
                      progressState.stage3 === 'done'
                        ? 'bg-green-400'
                        : progressState.stage3 === 'active'
                        ? 'bg-yellow-400 animate-pulse'
                        : 'bg-slate-600'
                    }`}
                  />
                  <h3
                    className={`text-base font-semibold ${
                      progressState.stage3 === 'done'
                        ? 'text-green-400'
                        : progressState.stage3 === 'active'
                        ? 'text-yellow-400'
                        : 'text-slate-600'
                    }`}
                  >
                    Stage 3: Finalizing
                  </h3>
                </div>

                <div className="mb-3 bg-slate-700 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-purple-500 h-full transition-all duration-300"
                    style={{
                      width: `${Math.min(100, progressState.stage3Progress * 100)}%`,
                    }}
                  />
                </div>

                <div className="ml-7 space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    {progressState.stage3 === 'done' ? (
                      <CheckSquare size={14} className="text-green-400" />
                    ) : progressState.stage3 === 'active' ? (
                      <RefreshCw size={14} className="text-yellow-400 animate-spin" />
                    ) : (
                      <Square size={14} className="text-slate-600" />
                    )}
                    <span
                      className={
                        progressState.stage3 === 'done'
                          ? 'text-green-400'
                          : progressState.stage3 === 'active'
                          ? 'text-yellow-400'
                          : 'text-slate-600'
                      }
                    >
                       💾 Saving results
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-6 pt-6 border-t border-slate-700 text-center">
              <p className="text-slate-400 text-sm">
                Elapsed: <span className="text-slate-300 font-medium">{formatElapsed(elapsedSeconds)}</span>
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Results View */}
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
