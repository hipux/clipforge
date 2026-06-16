import React, { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import Layout from './Layout'
import DownloadPage from '../pages/DownloadPage'
import MomentsPage from '../pages/MomentsPage'
import EffectsPage from '../pages/EffectsPage'
import ProcessPage from '../pages/ProcessPage'
import PublishPage from '../pages/PublishPage'
import { useAppStore } from '../store/useAppStore'
import { mockVideo, mockMoments, mockClips, type StoreSeed } from '../stories/mocks'

const defaultEffects = {
  subtitles: true,
  blur_background: true,
  mirror: false,
  color_correction: true,
}

/** Renders the real Layout sidebar + the full 5-page route tree. */
function AppShell({ seed, path }: { seed: StoreSeed; path: string }) {
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
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route path="download" element={<DownloadPage />} />
          <Route path="moments" element={<MomentsPage />} />
          <Route path="effects" element={<EffectsPage />} />
          <Route path="process" element={<ProcessPage />} />
          <Route path="publish" element={<PublishPage />} />
        </Route>
      </Routes>
    </MemoryRouter>
  )
}

const meta = {
  title: 'App/Layout',
  component: Layout,
  parameters: { layout: 'fullscreen' },
} satisfies Meta<typeof Layout>

export default meta
type Story = StoryObj<typeof meta>

const fullProgress: StoreSeed = {
  currentVideo: mockVideo,
  moments: mockMoments,
  selectedMomentIds: mockMoments.map((m) => m.id),
  processedClips: mockClips,
}

export const DownloadStep: Story = {
  name: 'Sidebar + Download Page',
  render: () => <AppShell seed={fullProgress} path="/download" />,
}

export const MomentsStep: Story = {
  name: 'Sidebar + Moments Page',
  render: () => <AppShell seed={fullProgress} path="/moments" />,
}

export const EffectsStep: Story = {
  name: 'Sidebar + Effects Page',
  render: () => <AppShell seed={fullProgress} path="/effects" />,
}

export const ProcessStep: Story = {
  name: 'Sidebar + Process Page',
  render: () => <AppShell seed={fullProgress} path="/process" />,
}

export const PublishStep: Story = {
  name: 'Sidebar + Publish Page',
  render: () => <AppShell seed={fullProgress} path="/publish" />,
}
