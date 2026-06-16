import React, { useState } from 'react'
import { MemoryRouter } from 'react-router-dom'
import type { Decorator } from '@storybook/react-vite'
import {
  useAppStore,
  type VideoInfo,
  type MomentCandidate,
  type ProcessedClip,
  type EffectSettings,
} from '../store/useAppStore'

export const mockVideo: VideoInfo = {
  id: 'vid_1',
  title: 'How I Built a Video Tool in a Weekend (Full Tutorial)',
  duration: 743,
  thumbnail_url: '',
  file_path: '/downloads/vid_1.mp4',
  platform: 'youtube',
}

export const mockMoments: MomentCandidate[] = [
  { id: 'm1', video_id: 'vid_1', start: 12, end: 47, score: 92, reason: 'High energy intro hook', thumbnail_url: '', approved: true },
  { id: 'm2', video_id: 'vid_1', start: 128, end: 156, score: 87, reason: 'Surprising reveal moment', thumbnail_url: '', approved: false },
  { id: 'm3', video_id: 'vid_1', start: 310, end: 352, score: 78, reason: 'Key tip viewers replay', thumbnail_url: '', approved: false },
  { id: 'm4', video_id: 'vid_1', start: 503, end: 528, score: 71, reason: 'Funny aside / laughter', thumbnail_url: '', approved: false },
]

const defaultEffects: EffectSettings = {
  subtitles: true,
  blur_background: true,
  mirror: false,
  color_correction: true,
}

export const mockClips: ProcessedClip[] = [
  { id: 'c1', moment_id: 'm1', file_path: '/clips/clip_1.mp4', status: 'done', effects: defaultEffects },
  { id: 'c2', moment_id: 'm2', file_path: '/clips/clip_2.mp4', status: 'done', effects: defaultEffects },
]

export interface StoreSeed {
  currentVideo?: VideoInfo | null
  moments?: MomentCandidate[]
  selectedMomentIds?: string[]
  processedClips?: ProcessedClip[]
  globalEffects?: EffectSettings
}

/**
 * Seeds the zustand store at render time (via a useState initializer, which runs
 * once per mount BEFORE children render) and wraps the story in a MemoryRouter.
 * Seeding at render time — not at module load — ensures each story re-applies its
 * own state when switched, since all stories share the same global store.
 */
export function withClipForge(seed: StoreSeed = {}, initialPath = '/download'): Decorator {
  const Wrapper: Decorator = (Story) => {
    useState(() => {
      useAppStore.setState({
        currentVideo: seed.currentVideo ?? null,
        moments: seed.moments ?? [],
        selectedMomentIds: seed.selectedMomentIds ?? [],
        processedClips: seed.processedClips ?? [],
        globalEffects: seed.globalEffects ?? defaultEffects,
      })
      return null
    })

    return (
      <MemoryRouter initialEntries={[initialPath]}>
        <Story />
      </MemoryRouter>
    )
  }
  return Wrapper
}
