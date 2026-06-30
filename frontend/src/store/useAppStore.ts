import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

export interface VideoInfo {
  id: string
  title: string
  duration: number
  thumbnail_url: string
  file_path: string
  platform: string
}

export interface MomentCandidate {
  id: string
  video_id: string
  start: number
  end: number
  score: number
  reason: string
  thumbnail_url: string
  approved: boolean
}

export interface EffectSettings {
  subtitles: boolean
  blur_background: boolean
  mirror: boolean
  color_correction: boolean
  subtitle_style?: string
  banner?: {
    enabled: boolean
    banner_id?: string
    url?: string
    position: string
    size: number
    opacity: number
  }
}

export interface ScoreBreakdown {
  overall: number         // 0-100
  hook: number            // 0-1
  self_contained: number  // 0-1
  pacing: number          // 0-1
  content_type: string
  content_icon: string    // lucide-react icon name resolved by <IconByName/>
  reason: string
  speakers: string[]
}

export interface ProcessedClip {
  id: string
  moment_id: string
  file_path: string
  status: string
  effects?: EffectSettings
  score?: ScoreBreakdown  // null-safe, present for clips created after #2
}

export interface Account {
  id: string
  name: string
  platform: string
  cookies_path: string | null
  proxy: string | null
  preferred_preset: string
  last_used_at: string | null
  created_at: string | null
}

export interface DetectionSettings {
  minDuration: number
  maxDuration: number
  maxMoments: number
  presetId: string            // #4 — content preset id (default|films_anime|streams|youtube_cuts)
}

interface AppState {
  // Current video
  currentVideo: VideoInfo | null
  setVideo: (video: VideoInfo | null) => void
  
  // Detected moments
  moments: MomentCandidate[]
  setMoments: (moments: MomentCandidate[]) => void
  
  // Selected moments for processing
  selectedMomentIds: string[]
  toggleMoment: (momentId: string) => void
  setSelectedMoments: (ids: string[]) => void
  
  // Global effect settings
  globalEffects: EffectSettings
  updateGlobalEffects: (effects: Partial<EffectSettings>) => void
  
  // Processed clips
  processedClips: ProcessedClip[]
  setClips: (clips: ProcessedClip[]) => void
  
  // Detection settings
  detectionSettings: DetectionSettings
  updateDetectionSettings: (settings: Partial<DetectionSettings>) => void

  // Active publishing account (#5 multi-account). Persisted so the same
  // account is used across page reloads. 'default' falls back to the
  // seeded row (legacy behaviour).
  activeAccountId: string
  setActiveAccountId: (id: string) => void
  
  // LLM Instructions
  llmInstructions: string
  setLlmInstructions: (v: string) => void
  
  // Navigation state
  currentStep: number
  setCurrentStep: (step: number) => void

  // In-flight job markers — let the frontend ask the server to resume a
  // download / detection / processing after a page reload instead of losing it.
  activeDownload: { jobId: string; url: string } | null
  setActiveDownload: (v: { jobId: string; url: string } | null) => void
  activeDetectionVideoId: string | null
  setActiveDetectionVideoId: (v: string | null) => void
  activeProcessingJobId: string | null
  setActiveProcessingJobId: (v: string | null) => void
}

export const useAppStore = create<AppState>()(persist((set) => ({
  // Initial state
  currentVideo: null,
  moments: [],
  selectedMomentIds: [],
  globalEffects: {
    subtitles: true,
    blur_background: true,
    mirror: false,
    color_correction: true,
    subtitle_style: 'karaoke',
    banner: {
      enabled: false,
      position: 'top-right',
      size: 20,
      opacity: 80,
    },
  },
  processedClips: [],
  detectionSettings: {
    minDuration: 30,
    maxDuration: 90,
    maxMoments: 15,
    presetId: 'default',
  },
  llmInstructions: '',
  currentStep: 1,
  activeDownload: null,
  activeDetectionVideoId: null,
  activeProcessingJobId: null,
  activeAccountId: 'default',
  
  // Actions
  setVideo: (video) => set({ currentVideo: video }),
  
  setMoments: (moments) => set({ moments }),
  
  toggleMoment: (momentId) => set((state) => {
    const isSelected = state.selectedMomentIds.includes(momentId)
    return {
      selectedMomentIds: isSelected
        ? state.selectedMomentIds.filter(id => id !== momentId)
        : [...state.selectedMomentIds, momentId]
    }
  }),
  
  setSelectedMoments: (ids) => set({ selectedMomentIds: ids }),
  
  updateGlobalEffects: (effects) => set((state) => ({
    globalEffects: { ...state.globalEffects, ...effects }
  })),
  
  setClips: (clips) => set({ processedClips: clips }),
  
  setCurrentStep: (step) => set({ currentStep: step }),
  
  updateDetectionSettings: (settings) => set((state) => ({
    detectionSettings: { ...state.detectionSettings, ...settings }
  })),
  
  setLlmInstructions: (v) => set({ llmInstructions: v }),

  setActiveDownload: (v) => set({ activeDownload: v }),
  setActiveDetectionVideoId: (v) => set({ activeDetectionVideoId: v }),
  setActiveProcessingJobId: (v) => set({ activeProcessingJobId: v }),
  setActiveAccountId: (id) => set({ activeAccountId: id }),
}), {
  name: 'clipforge-session',
  // localStorage: state survives page refresh AND tab/window close.
  // It is invalidated by server-id mismatch (see SessionGuard) when the backend
  // restarts, i.e. when the project/console is closed and reopened.
  storage: createJSONStorage(() => localStorage),
  partialize: (state) => ({
    currentVideo: state.currentVideo,
    moments: state.moments,
    selectedMomentIds: state.selectedMomentIds,
    globalEffects: state.globalEffects,
    processedClips: state.processedClips,
    detectionSettings: state.detectionSettings,
    llmInstructions: state.llmInstructions,
    currentStep: state.currentStep,
    activeDownload: state.activeDownload,
    activeDetectionVideoId: state.activeDetectionVideoId,
    activeProcessingJobId: state.activeProcessingJobId,
  }),
}))