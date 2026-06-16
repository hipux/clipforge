import type { Meta, StoryObj } from '@storybook/react-vite'
import MomentsPage from './MomentsPage'
import { withClipForge, mockVideo, mockMoments } from '../stories/mocks'

const meta = {
  title: 'Pages/MomentsPage',
  component: MomentsPage,
  parameters: { layout: 'fullscreen' },
} satisfies Meta<typeof MomentsPage>

export default meta
type Story = StoryObj<typeof meta>

export const WithMoments: Story = {
  name: 'Detected Moments',
  decorators: [
    withClipForge(
      {
        currentVideo: mockVideo,
        moments: mockMoments,
        selectedMomentIds: mockMoments.map((m) => m.id),
      },
      '/moments',
    ),
  ],
}

export const PartialSelection: Story = {
  name: 'Partial Selection',
  decorators: [
    withClipForge(
      {
        currentVideo: mockVideo,
        moments: mockMoments,
        selectedMomentIds: ['m1', 'm3'],
      },
      '/moments',
    ),
  ],
}
