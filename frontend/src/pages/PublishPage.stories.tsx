import React from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import PublishPage from './PublishPage'
import { withClipForge, withMockAuth, mockVideo, mockMoments, mockClips } from '../stories/mocks'

const meta = {
  title: 'Pages/PublishPage',
  component: PublishPage,
  parameters: { layout: 'fullscreen' },
} satisfies Meta<typeof PublishPage>

export default meta
type Story = StoryObj<typeof meta>

export const WithClips: Story = {
  name: 'Clips Ready to Publish',
  decorators: [
    withMockAuth(true),
    withClipForge(
      {
        currentVideo: mockVideo,
        moments: mockMoments,
        selectedMomentIds: ['m1', 'm2'],
        processedClips: mockClips,
      },
      '/publish',
    ),
  ],
}

export const NoClips: Story = {
  name: 'Empty (No Processed Clips)',
  decorators: [withClipForge({}, '/publish')],
}

/**
 * Demonstrates the Copy Path button feedback. After the page mounts, the first
 * clip's "Copy Path" button is clicked automatically; it fetches the full path
 * from the (mocked) `/api/export/<id>/path` endpoint and flips to the green
 * "copied" check state.
 */
export const CopyPathFeedback: Story = {
  name: 'Copy Path — Full-Path Feedback',
  decorators: [
    (Story) => {
      // Auto-click the first "Copy Path" button so the success feedback is
      // visible in the captured screenshot without a play function.
      React.useEffect(() => {
        const id = setInterval(() => {
          const btn = Array.from(document.querySelectorAll('button')).find((b) =>
            /copy path/i.test(b.textContent || ''),
          )
          if (btn) {
            ;(btn as HTMLButtonElement).click()
            clearInterval(id)
          }
        }, 100)
        return () => clearInterval(id)
      }, [])
      return <Story />
    },
    withMockAuth(true),
    withClipForge(
      {
        currentVideo: mockVideo,
        moments: mockMoments,
        selectedMomentIds: ['m1', 'm2'],
        processedClips: mockClips,
      },
      '/publish',
    ),
  ],
}
