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
  })

  useEffect(() => {
    if (!currentVideo) {
      navigate('/')
    }
  }, [currentVideo, navigate])

  useEffect(() => {
    if (moments.length > 0) {
      const maxSeq = Math.max(...moments.map((m) => m.keySeq || 0))
      setMomentKeySeq(maxSeq + 1)
      if (view === 'setup') {
        setView('results')
      }
    }
  }, [moments.length])

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null
    if (view === 'detecting') {
      interval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - detectStartRef.current) / 1000)
        setElapsedSeconds(elapsed)
      }, 1000)
    } else {
      setElapsedSeconds(0)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [view])

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}m ${s}s`
  }

  const startDetection = async () => {
    if (!currentVideo) return
    setUploadError(null)
    setMoments([])
    setProgressState({
      stage1: 'pending',
      stage1Step: null,
      stage2: 'pending',
      stage2Step: null,
      stage3: 'pending',
      overallProgress: 0,
      statusMessage: '',
    })
    setView('detecting')
    detectStartRef.current = Date.now()

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.hostname
    const wsUrl = `${protocol}//${host}:8000/api/moments/detect_ws?video_id=${currentVideo.id}&min_duration=${detectionSettings.minDuration}&max_duration=${detectionSettings.maxDuration}&max_moments=${detectionSettings.maxMoments}&user_instructions=${encodeURIComponent(llmInstructions.trim())}`
    const ws = new WebSocket(wsUrl)
    wsConnectionRef.current = ws

    ws.onmessage = async (event) => {
      const data = JSON.parse(event.data)

      if (data.status === 'progress') {
        const stage = data.stage || 1
        const step = data.step || ''
        const progress = data.progress || 0

        setProgressState((prev) => {
          const newState = { ...prev }
          newState.overallProgress = progress
          newState.statusMessage = data.message || ''

          // Stage 1
          if (stage === 1) {
            if (step === 'transcription') {
              newState.stage1 = 'active'
              newState.stage1Step = 'transcription'
            } else if (step === 'face_detection') {
              newState.stage1 = 'active'
              newState.stage1Step = 'face_detection'
            } else if (step === 'audio_analysis') {
              newState.stage1 = 'active'
              newState.stage1Step = 'audio_analysis'
            } else if (step === 'done') {
              newState.stage1 = 'done'
              newState.stage1Step = null
            }
          }

          // Stage 2
          if (stage === 2) {
            newState.stage1 = 'done'
            if (step === 'context_building') {
              newState.stage2 = 'active'
              newState.stage2Step = 'context_building'
            } else if (step === 'llm_analysis') {
              newState.stage2 = 'active'
              newState.stage2Step = 'llm_analysis'
            } else if (step === 'done') {
              newState.stage2 = 'done'
              newState.stage2Step = null
            }
          }

          // Stage 3
          if (stage === 3) {
            newState.stage1 = 'done'
            newState.stage2 = 'done'
            if (step === 'done') {
              newState.stage3 = 'done'
            }
          }

          return newState
        })
      } else if (data.status === 'complete') {
        const detectionMoments = (data.moments || []).map((m: any, idx: number) => {
          const seq = momentKeySeq + idx
          return {
            ...m,
            keySeq: seq,
          }
        })
        setMomentKeySeq(momentKeySeq + (data.moments?.length || 0))
        setMoments(detectionMoments)
        setView('results')
      } else if (data.status === 'error') {
        setUploadError(data.message || 'Detection failed')
        setView('setup')
      }
    }

    ws.onerror = (err) => {
      console.error('WS error:', err)
      setUploadError('Connection error occurred')
      setView('setup')
    }

    ws.onclose = () => {
      wsConnectionRef.current = null
      if (view === 'detecting') {
        setUploadError('Connection closed unexpectedly')
        setView('setup')
      }
    }
  }

  const cancelDetection = () => {
    if (wsConnectionRef.current) {
      wsConnectionRef.current.close()
      wsConnectionRef.current = null
    }
    setView('setup')
    setUploadError(null)
  }

  const exportSelected = async () => {
    if (!currentVideo || selectedMomentIds.size === 0) return

    try {
      const selected = moments.filter((m) => selectedMomentIds.has(m.id))
      const response = await axios.post('http://localhost:8000/api/moments/export',
        { video_id: currentVideo.id, moments: selected },
        { responseType: 'blob' }
      )

      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.download = 'moments.zip'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Failed to export moments:', err)
    }
  }

  const allMomentsSelected = (moments.length > 0 && moments.every((m) => selectedMomentIds.has(m.id)))
  const toggleAllMoments = () => {
    if (allMomentsSelected) {
      moments.forEach((m) => {
        if (selectedMomentIds.has(m.id)) {
          toggleMoment(m.id)
        }
      })
    } else {
      moments.forEach((m) => {
        if (!selectedMomentIds.has(m.id)) {
          toggleMoment(m.id)
        }
      })
    }
  }

  if (!currentVideo) {
    return null
  }

  return (
    <div className="container py-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/')} className="btn btn-secondary flex items-center gap-2">
            <ArrowLeft size={16} />
            Back
          </button>
          <Scissors size={32} className="text-accent" />
          <div>
            <h1 className="text-2xl font-bold text-slate-100">Detect Moments</h1>
            <p className="text-slate-500">{currentVideo.title}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <GPUStatusIndicator />
          {view === 'results' && moments.length > 0 && (
            <button
              onClick={toggleAllMoments}
              className="btn btn-secondary flex items-center gap-2"
            >
              {allMomentsSelected ? <CheckSquare size={15} /> : <Square size={15} />}
              Toggle All
            </button>
          )}
          {selectedMomentIds.size > 0 && (
            <button
              onClick={exportSelected}
              className="btn btn-primary flex items-center gap-2"
            >
              <ArrowRight size={15} />
              Export Selected ({selectedMomentIds.size})
            </button>
          )}
        </div>
      </div>

      {/* Setup View */}
      {view === 'setup' && (
        <div className="max-w-lg mx-auto">
          <div className="card">
            <h2 className="text-xl font-bold text-slate-100 mb-6 text-center">Configure Detection</h2>

            {/* LLM Instructions */}
            <div className="mb-6">
              <h3 className="font-semibold text-slate-300 mb-3">🧠 LLM Instructions</h3>
              <LLMInstructionsInput
                value={llmInstructions}
                onChange={setLlmInstructions}
                heightClass="h-32"
              />
            </div>

            {/* Detection Settings */}
            <div className="mb-6">
              <h3 className="font-semibold text-slate-300 mb-4">⚙️ Detection Settings</h3>
              <div className="space-y-4">
                {/* Min duration */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-slate-400">Min Duration</span>
                    <span className="text-sm font-semibold text-accent">{detectionSettings.minDuration}s</span>
                  </div>
                  <input
                    type="range"
                    min="15"
                    max="90"
                    step="5"
                    value={detectionSettings.minDuration}
                    onChange={(e) => updateDetectionSettings({ minDuration: parseInt(e.target.value) })}
                    className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-accent"
                  />
                </div>
                {/* Max duration */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-slate-400">Max Duration</span>
                    <span className="text-sm font-semibold text-accent">{detectionSettings.maxDuration}s</span>
                  </div>
                  <input
                    type="range"
                    min="60"
                    max="180"
                    step="10"
                    value={detectionSettings.maxDuration}
                    onChange={(e) => updateDetectionSettings({ maxDuration: parseInt(e.target.value) })}
                    className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-accent"
                  />
                </div>
                {/* Max moments */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-slate-400">Max Moments</span>
                    <span className="text-sm font-semibold text-accent">{detectionSettings.maxMoments}</span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="30"
                    step="1"
                    value={detectionSettings.maxMoments}
                    onChange={(e) => updateDetectionSettings({ maxMoments: parseInt(e.target.value) })}
                    className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-accent"
                  />
                </div>
              </div>
            </div>

            {/* Start Button */}
            <button
              onClick={startDetection}
              className="btn btn-primary w-full py-3 text-base font-semibold flex items-center justify-center gap-2"
            >
              🚀 Start Detection
            </button>

            <p className="text-center text-sm text-slate-500 mt-3">
              ~6-9 min (your RTX 5060 GPU)
            </p>

            {uploadError && (
              <div className="mt-6 border-2 border-red-500/50 bg-red-900/20 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <AlertTriangle size={24} className="text-red-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="font-semibold text-red-500 mb-1">Detection Failed</h3>
                    <p className="text-slate-300">{uploadError}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Detecting View - Progress Timeline */}
      {view === 'detecting' && (
        <div className="max-w-2xl mx-auto">
          <div className="card">
            <div className="mb-6">
              <h2 className="text-xl font-bold text-slate-100 mb-2 flex items-center gap-2">
                <RefreshCw size={20} className="animate-spin" />
                Detecting Moments...
              </h2>
              <p className="text-sm text-slate-400">{progressState.statusMessage}</p>
            </div>

            {/* Progress Timeline */}
            <div className="space-y-6">
              {/* Stage 1 */}
              <div>
                <div className="flex items-center gap-3 mb-3">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      progressState.stage1 === 'done'
                        ? 'bg-green-400'
                        : progressState.stage1 === 'active'
                        ? 'bg-yellow-400 animate-pulse'
                        : 'bg-slate-600'
                    }`}
                  />
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span
                        className={`font-semibold ${
                          progressState.stage1 === 'done'
                            ? 'text-green-400'
                            : progressState.stage1 === 'active'
                            ? 'text-yellow-400'
                            : 'text-slate-600'
                        }`}
                      >
                        Stage 1: Collecting Data
                      </span>
                      {progressState.stage1 !== 'pending' && (
                        <span className="text-sm text-slate-400">{formatTime(elapsedSeconds)}</span>
                      )}
                    </div>
                    <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent transition-all duration-300"
                        style={{
                          width: `${
                            progressState.stage1 === 'done'
                              ? 100
                              : progressState.stage1 === 'active'
                              ? Math.min((progressState.overallProgress / 0.6) * 100, 100)
                              : 0
                          }%`,
                        }}
                      />
                    </div>
                  </div>
                </div>

                {/* Sub-steps */}
                <div className="ml-6 space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    {progressState.stage1Step === 'transcription' ? (
                      <RefreshCw size={14} className="animate-spin text-yellow-400" />
                    ) : progressState.stage1 === 'done' || (progressState.stage1 === 'active' && progressState.stage1Step !== 'transcription') ? (
                      <span className="text-green-400">✓</span>
                    ) : (
                      <span className="text-slate-600">○</span>
                    )}
                    <span
                      className={
                        progressState.stage1Step === 'transcription'
                          ? 'text-yellow-400'
                          : progressState.stage1 === 'done' || (progressState.stage1 === 'active' && progressState.stage1Step !== 'transcription')
                          ? 'text-green-400'
                          : 'text-slate-600'
                      }
                    >
                      🎙️ Whisper transcription
                    </span>
                    {progressState.stage1Step === 'transcription' && (
                      <span className="text-slate-500">in progress...</span>
                    )}
                    {(progressState.stage1 === 'done' || (progressState.stage1 === 'active' && progressState.stage1Step !== 'transcription')) && (
                      <span className="text-slate-500">done</span>
                    )}
                    {progressState.stage1 === 'pending' && <span className="text-slate-600">pending</span>}
                  </div>

                  <div className="flex items-center gap-2 text-sm">
                    {progressState.stage1Step === 'face_detection' ? (
                      <RefreshCw size={14} className="animate-spin text-yellow-400" />
                    ) : progressState.stage1 === 'done' || (progressState.stage1 === 'active' && progressState.stage1Step === 'audio_analysis') ? (
                      <span className="text-green-400">✓</span>
                    ) : (
                      <span className="text-slate-600">○</span>
                    )}
                    <span
                      className={
                        progressState.stage1Step === 'face_detection'
                          ? 'text-yellow-400'
                          : progressState.stage1 === 'done' || (progressState.stage1 === 'active' && progressState.stage1Step === 'audio_analysis')
                          ? 'text-green-400'
                          : 'text-slate-600'
                      }
                    >
                      👤 YOLO face detection
                    </span>
                    {progressState.stage1Step === 'face_detection' && (
                      <span className="text-slate-500">in progress...</span>
                    )}
                    {(progressState.stage1 === 'done' || (progressState.stage1 === 'active' && progressState.stage1Step === 'audio_analysis')) && (
                      <span className="text-slate-500">done</span>
                    )}
                    {(progressState.stage1 === 'pending' || progressState.stage1Step === 'transcription') && (
                      <span className="text-slate-600">pending</span>
                    )}
                  </div>

                  <div className="flex items-center gap-2 text-sm">
                    {progressState.stage1Step === 'audio_analysis' ? (
                      <RefreshCw size={14} className="animate-spin text-yellow-400" />
                    ) : progressState.stage1 === 'done' ? (
                      <span className="text-green-400">✓</span>
                    ) : (
                      <span className="text-slate-600">○</span>
                    )}
                    <span
                      className={
                        progressState.stage1Step === 'audio_analysis'
                          ? 'text-yellow-400'
                          : progressState.stage1 === 'done'
                          ? 'text-green-400'
                          : 'text-slate-600'
                      }
                    >
                      🔊 Audio peak analysis
                    </span>
                    {progressState.stage1Step === 'audio_analysis' && (
                      <span className="text-slate-500">in progress...</span>
                    )}
                    {progressState.stage1 === 'done' && <span className="text-slate-500">done</span>}
                    {(progressState.stage1 === 'pending' || (progressState.stage1 === 'active' && progressState.stage1Step !== 'audio_analysis')) && (
                      <span className="text-slate-600">pending</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Stage 2 */}
              <div>
                <div className="flex items-center gap-3 mb-3">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      progressState.stage2 === 'done'
                        ? 'bg-green-400'
                        : progressState.stage2 === 'active'
                        ? 'bg-yellow-400 animate-pulse'
                        : 'bg-slate-600'
                    }`}
                  />
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span
                        className={`font-semibold ${
                          progressState.stage2 === 'done'
                            ? 'text-green-400'
                            : progressState.stage2 === 'active'
                            ? 'text-yellow-400'
                            : 'text-slate-600'
                        }`}
                      >
                        Stage 2: AI Analysis
                      </span>
                      {progressState.stage2 !== 'pending' && (
                        <span className="text-sm text-slate-400">{formatTime(elapsedSeconds)}</span>
                      )}
                    </div>
                    <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent transition-all duration-300"
                        style={{
                          width: `${
                            progressState.stage2 === 'done'
                              ? 100
                              : progressState.stage2 === 'active'
                              ? Math.min(((progressState.overallProgress - 0.6) / 0.3) * 100, 100)
                              : 0
                          }%`,
                        }}
                      />
                    </div>
                  </div>
                </div>

                {/* Sub-steps */}
                <div className="ml-6 space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    {progressState.stage2Step === 'context_building' ? (
                      <RefreshCw size={14} className="animate-spin text-yellow-400" />
                    ) : progressState.stage2 === 'done' || (progressState.stage2 === 'active' && progressState.stage2Step === 'llm_analysis') ? (
                      <span className="text-green-400">✓</span>
                    ) : (
                      <span className="text-slate-600">○</span>
                    )}
                    <span
                      className={
                        progressState.stage2Step === 'context_building'
                          ? 'text-yellow-400'
                          : progressState.stage2 === 'done' || (progressState.stage2 === 'active' && progressState.stage2Step === 'llm_analysis')
                          ? 'text-green-400'
                          : 'text-slate-600'
                      }
                    >
                      🧩 Building context chunks
                    </span>
                    {progressState.stage2Step === 'context_building' && (
                      <span className="text-slate-500">in progress...</span>
                    )}
                    {(progressState.stage2 === 'done' || (progressState.stage2 === 'active' && progressState.stage2Step === 'llm_analysis')) && (
                      <span className="text-slate-500">done</span>
                    )}
                    {progressState.stage2 === 'pending' && <span className="text-slate-600">pending</span>}
                  </div>

                  <div className="flex items-center gap-2 text-sm">
                    {progressState.stage2Step === 'llm_analysis' ? (
                      <RefreshCw size={14} className="animate-spin text-yellow-400" />
                    ) : progressState.stage2 === 'done' ? (
                      <span className="text-green-400">✓</span>
                    ) : (
                      <span className="text-slate-600">○</span>
                    )}
                    <span
                      className={
                        progressState.stage2Step === 'llm_analysis'
                          ? 'text-yellow-400'
                          : progressState.stage2 === 'done'
                          ? 'text-green-400'
                          : 'text-slate-600'
                      }
                    >
                      🧠 Qwen3 — analyzing chunks
                    </span>
                    {progressState.stage2Step === 'llm_analysis' && (
                      <span className="text-slate-500">in progress...</span>
                    )}
                    {progressState.stage2 === 'done' && <span className="text-slate-500">done</span>}
                    {(progressState.stage2 === 'pending' || progressState.stage2Step === 'context_building') && (
                      <span className="text-slate-600">pending</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Stage 3 */}
              <div>
                <div className="flex items-center gap-3 mb-3">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      progressState.stage3 === 'done'
                        ? 'bg-green-400'
                        : progressState.stage3 === 'active'
                        ? 'bg-yellow-400 animate-pulse'
                        : 'bg-slate-600'
                    }`}
                  />
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span
                        className={`font-semibold ${
                          progressState.stage3 === 'done'
                            ? 'text-green-400'
                            : progressState.stage3 === 'active'
                            ? 'text-yellow-400'
                            : 'text-slate-600'
                        }`}
                      >
                        Stage 3: Finalizing
                      </span>
                      {progressState.stage3 !== 'pending' && (
                        <span className="text-sm text-slate-400">{formatTime(elapsedSeconds)}</span>
                      )}
                    </div>
                    <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent transition-all duration-300"
                        style={{
                          width: `${
                            progressState.stage3 === 'done'
                              ? 100
                              : progressState.stage3 === 'active'
                              ? 50
                              : 0
                          }%`,
                        }}
                      />
                    </div>
                  </div>
                </div>

                {/* Sub-steps */}
                <div className="ml-6 space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    {progressState.stage3 === 'active' ? (
                      <RefreshCw size={14} className="animate-spin text-yellow-400" />
                    ) : progressState.stage3 === 'done' ? (
                      <span className="text-green-400">✓</span>
                    ) : (
                      <span className="text-slate-600">○</span>
                    )}
                    <span
                      className={
                        progressState.stage3 === 'active'
                          ? 'text-yellow-400'
                          : progressState.stage3 === 'done'
                          ? 'text-green-400'
                          : 'text-slate-600'
                      }
                    >
                      💾 Saving results
                    </span>
                    {progressState.stage3 === 'active' && (
                      <span className="text-slate-500">in progress...</span>
                    )}
                    {progressState.stage3 === 'done' && <span className="text-slate-500">done</span>}
                    {progressState.stage3 === 'pending' && <span className="text-slate-600">pending</span>}
                  </div>
                </div>
              </div>
            </div>

            <button onClick={cancelDetection} className="btn btn-secondary w-full mt-6">
              Cancel Detection
            </button>
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
