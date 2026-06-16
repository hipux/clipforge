import type { Meta, StoryObj } from '@storybook/react-vite'
import ProcessPage from './ProcessPage'
import { withClipForge, mockVideo, mockMoments } from '../stories/mocks'

const meta = {
  title: 'Pages/ProcessPage',
  component: ProcessPage,
  parameters: { layout: 'fullscreen' },
} satisfies Meta<typeof ProcessPage>

export default meta
type Story = StoryObj<typeof meta>

export const ReadyToProcess: Story = {
  name: 'Ready to Process',
  decorators: [
    withClipForge(
      {
        currentVideo: mockVideo,
        moments: mockMoments,
        selectedMomentIds: ['m1', 'm2', 'm3'],
      },
      '/process',
    ),
  ],
}
