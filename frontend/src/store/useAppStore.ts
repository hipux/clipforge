import { create } from 'zustand'
import { persist } from 'zustand/middleware'

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

export interface ProcessedClip {
  id: string
  moment_id: string
  file_path: string
  status: string
  effects?: EffectSettings
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
  
  // Navigation state
  currentStep: number
  setCurrentStep: (step: number) => void
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
  currentStep: 1,
  
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
}), {
  name: 'clipforge-session',
  partialize: (state) => ({
    currentVideo: state.currentVideo,
    moments: state.moments,
    selectedMomentIds: state.selectedMomentIds,
    globalEffects: state.globalEffects,
    processedClips: state.processedClips,
    currentStep: state.currentStep,
  }),
}))
