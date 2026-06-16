import type { Meta, StoryObj } from '@storybook/react-vite'
import PublishPage from './PublishPage'
import { withClipForge, mockVideo, mockMoments, mockClips } from '../stories/mocks'

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
