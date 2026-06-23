import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useAppStore } from '../store/useAppStore'
import MomentCard from '../components/MomentCard'
import ProgressBar from '../components/ProgressBar'
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

export default function MomentsPage() {
  const navigate = useNavigate()
  const {
    currentVideo,
    moments,
    setMoments,
    selectedMomentIds,
    toggleMoment,
    setSelectedMoments,
    setCurrentStep,
    detectionSettings,
    updateDetectionSettings,
  } = useAppStore()

  const [detecting, setDetecting] = useState(false)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [isGPUAvailable, setIsGPUAvailable] = useState(false)
  const [llmInstructions, setLlmInstructions] = useState('')
  const [detectionStage, setDetectionStage] = useState('')
  const detectingRef = useRef(false)

  useEffect(() => {
    // Fetch GPU status on mount
    axios.get('/api/gpu/status')
      .then(r => setIsGPUAvailable(r.data.is_gpu ?? false))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!currentVideo) {
      navigate('/download')
      return
    }
    // Only auto-start if no moments exist and not already detecting
    if (moments.length === 0 && !detectingRef.current) {
      startDetection()
    }
  }, [currentVideo])

  const startDetection = async () => {
    if (!currentVideo || detectingRef.current) return

    detectingRef.current = true
    setDetecting(true)
    setError('')
    setProgress(0)
    setStatus('Starting moment detection…')
    setDetectionStage('')

    try {
      const { data } = await axios.post('/api/moments/detect', {
        video_id: currentVideo.id,
        min_duration: detectionSettings.minDuration,
        max_duration: detectionSettings.maxDuration,
        max_moments: detectionSettings.maxMoments,
        user_instructions: llmInstructions,
      })

      // Check if moments already exist
      if (data.status === 'completed' && data.moments) {
        setMoments(data.moments)
        setSelectedMoments(data.moments.map((m: any) => m.id))
        setDetecting(false)
        detectingRef.current = false
        return
      }

      // WebSocket for real-time progress
      const ws = new WebSocket(
        `${import.meta.env.VITE_WS_URL || 'ws://localhost:8000'}/api/moments/detect_ws?video_id=${currentVideo.id}&min_duration=${detectionSettings.minDuration}&max_duration=${detectionSettings.maxDuration}&max_moments=${detectionSettings.maxMoments}&user_instructions=${encodeURIComponent(llmInstructions)}`
      )

      ws.onmessage = (evt) => {
        const msg = JSON.parse(evt.data)
        if (msg.type === 'progress') {
          setProgress(msg.progress || 0)
          setStatus(msg.message || '')
          
          // Map stages to user-friendly labels
          if (msg.stage) {
            if (msg.stage.includes('stage1') || msg.stage.includes('whisper')) {
              setDetectionStage('Этап 1: Транскрибация (Whisper)')
            } else if (msg.stage.includes('stage2') || msg.stage.includes('llm') || msg.stage.includes('director')) {
              setDetectionStage('Этап 2: ИИ-режиссёр (Qwen3)')
            } else if (msg.stage.includes('stage3') || msg.stage.includes('render')) {
              setDetectionStage('Этап 3: Рендер (NVENC)')
            }
          }
        } else if (msg.type === 'complete') {
          setMoments(msg.moments || [])
          setSelectedMoments((msg.moments || []).map((m: any) => m.id))
          setDetecting(false)
          detectingRef.current = false
          ws.close()
        } else if (msg.type === 'error') {
          setError(msg.message || 'Detection failed')
          setDetecting(false)
          detectingRef.current = false
          ws.close()
        }
      }

      ws.onerror = () => {
        setError('WebSocket connection failed')
        setDetecting(false)
        detectingRef.current = false
      }

      ws.onclose = () => {
        setDetecting(false)
        detectingRef.current = false
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Detection failed')
      setDetecting(false)
      detectingRef.current = false
    }
  }

  const handleSelectAll = () => {
    setSelectedMoments(moments.map(m => m.id))
  }

  const handleDeselectAll = () => {
    setSelectedMoments([])
  }

  const goBack = () => {
    setCurrentStep('download')
    navigate('/download')
  }

  const goNext = () => {
    if (selectedMomentIds.length === 0) {
      alert('Please select at least one moment')
      return
    }
    setCurrentStep('process')
    navigate('/process')
  }

  return (
    <div className="min-h-screen bg-dark text-white px-6 py-8 pb-24">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Scissors size={28} className="text-accent" />
          <h1 className="text-3xl font-bold">Detected Moments</h1>
        </div>
        <p className="text-slate-400 text-sm">
          {currentVideo?.title || 'No video selected'} •{' '}
          {moments.length > 0 ? `${moments.length} moments found` : 'Detecting…'}
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="max-w-7xl mx-auto mb-6">
          <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 flex items-start gap-3">
            <AlertTriangle size={20} className="text-red-500 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-red-300 mb-1">Detection Error</h3>
              <p className="text-red-200 text-sm">{error}</p>
              <button onClick={startDetection} className="btn btn-sm btn-outline mt-3">
                <RefreshCw size={14} />
                Retry
              </button>
            </div>
          </div>
        </div>
      )}

      {/* GPU Status and Settings */}
      {!detecting && moments.length > 0 && (
        <div className="max-w-7xl mx-auto mb-6">
          <div className="card p-6 space-y-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-300">GPU Pipeline Status</h2>
            </div>
            
            {/* GPU Status Indicator */}
            <GPUStatusIndicator />
            
            {/* Settings Sliders */}
            <div className="grid grid-cols-3 gap-6 pt-4 border-t border-slate-800">
              {/* Min Duration */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="text-xs text-slate-400">Min duration</label>
                  <span className="text-xs font-semibold text-accent">{detectionSettings.minDuration}s</span>
                </div>
                <input
                  type="range"
                  min="15"
                  max="60"
                  step="5"
                  value={detectionSettings.minDuration}
                  onChange={(e) => updateDetectionSettings({ minDuration: parseInt(e.target.value) })}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-accent"
                />
              </div>
              
              {/* Max Duration */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="text-xs text-slate-400">Max duration</label>
                  <span className="text-xs font-semibold text-accent">{detectionSettings.maxDuration}s</span>
                </div>
                <input
                  type="range"
                  min="30"
                  max="120"
                  step="5"
                  value={detectionSettings.maxDuration}
                  onChange={(e) => updateDetectionSettings({ maxDuration: parseInt(e.target.value) })}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-accent"
                />
              </div>
              
              {/* Max Moments */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="text-xs text-slate-400">Max moments</label>
                  <span className="text-xs font-semibold text-accent">{detectionSettings.maxMoments}</span>
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
            
            {/* LLM Instructions Input */}
            <div className="pt-4 border-t border-slate-800">
              <LLMInstructionsInput 
                value={llmInstructions}
                onChange={setLlmInstructions}
                isGPU={isGPUAvailable}
              />
            </div>

            <button onClick={startDetection} className="btn btn-primary w-full" disabled={detecting}>
              <RefreshCw size={15} className={detecting ? 'animate-spin' : ''} />
              Re-detect with New Settings
            </button>
          </div>
        </div>
      )}

      {/* Detecting */}
      {detecting && (
        <div className="max-w-7xl mx-auto mb-6">
          <div className="card p-8 text-center">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-accent/10 mb-4">
              <RefreshCw size={24} className="text-accent animate-spin" />
            </div>
            <h3 className="text-lg font-semibold text-slate-300 mb-2">Detecting moments…</h3>
            <p className="text-slate-500 text-sm mb-4">{status}</p>
            
            {/* Stage Indicator */}
            {detectionStage && (
              <div className="mb-4">
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-purple-500/10 border border-purple-500/30">
                  <div className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
                  <span className="text-sm font-medium text-purple-300">{detectionStage}</span>
                </div>
              </div>
            )}
            
            <ProgressBar progress={progress} className="max-w-md mx-auto" />
          </div>
        </div>
      )}

      {/* Moments Grid */}
      {moments.length > 0 && (
        <>
          <div className="max-w-7xl mx-auto mb-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-sm text-slate-400">
                  {selectedMomentIds.length} of {moments.length} selected
                </span>
                <button onClick={handleSelectAll} className="btn-link text-xs flex items-center gap-1">
                  <CheckSquare size={14} />
                  Select All
                </button>
                <button onClick={handleDeselectAll} className="btn-link text-xs flex items-center gap-1">
                  <Square size={14} />
                  Deselect All
                </button>
              </div>
            </div>
          </div>

          <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {moments.map((moment) => (
              <MomentCard
                key={moment.id}
                moment={moment}
                selected={selectedMomentIds.includes(moment.id)}
                onToggle={() => toggleMoment(moment.id)}
              />
            ))}
          </div>
        </>
      )}

      {/* Bottom Nav */}
      <div className="fixed bottom-0 left-0 right-0 bg-dark-card border-t border-slate-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <button onClick={goBack} className="btn btn-outline">
            <ArrowLeft size={16} />
            Back
          </button>
          <button
            onClick={goNext}
            disabled={selectedMomentIds.length === 0}
            className="btn btn-primary"
          >
            Continue
            <ArrowRight size={16} />
          </button>
        </div>
      </div>

      {/* Settings Card (when no moments yet) */}
      {!detecting && moments.length === 0 && !error && (
        <div className="max-w-2xl mx-auto">
          <div className="card p-6 mb-6">
            <h2 className="text-lg font-semibold text-slate-300 mb-4">Detection Settings</h2>
            
            {/* GPU Status */}
            <div className="mb-6">
              <GPUStatusIndicator />
            </div>
            
            {/* LLM Instructions */}
            <div className="mb-6">
              <LLMInstructionsInput 
                value={llmInstructions}
                onChange={setLlmInstructions}
                isGPU={isGPUAvailable}
              />
            </div>
            
            {/* Sliders */}
            <div className="grid grid-cols-1 gap-4">
              {/* Min Duration */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="text-xs text-slate-400">Min duration</label>
                  <span className="text-xs font-semibold text-accent">{detectionSettings.minDuration}s</span>
                </div>
                <input
                  type="range"
                  min="15"
                  max="60"
                  step="5"
                  value={detectionSettings.minDuration}
                  onChange={(e) => updateDetectionSettings({ minDuration: parseInt(e.target.value) })}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-accent"
                />
              </div>
              
              {/* Max Duration */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="text-xs text-slate-400">Max duration</label>
                  <span className="text-xs font-semibold text-accent">{detectionSettings.maxDuration}s</span>
                </div>
                <input
                  type="range"
                  min="30"
                  max="120"
                  step="5"
                  value={detectionSettings.maxDuration}
                  onChange={(e) => updateDetectionSettings({ maxDuration: parseInt(e.target.value) })}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-accent"
                />
              </div>
              
              {/* Max Moments */}
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="text-xs text-slate-400">Max moments</label>
                  <span className="text-xs font-semibold text-accent">{detectionSettings.maxMoments}</span>
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

          {/* No moments */}
          <div className="card text-center py-14 border-dashed">
            <Search size={40} className="text-slate-700 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-slate-300 mb-1">No moments detected yet</h3>
            <p className="text-slate-500 text-sm mb-6">
              Start detection to find the best clips in your video
            </p>
            <button onClick={startDetection} className="btn btn-primary mx-auto">
              <Search size={15} />
              Start Detection
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
