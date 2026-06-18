import type { Meta, StoryObj } from '@storybook/react-vite'
import ProcessPage from './ProcessPage'
import { withClipForge, withProcessingState, mockVideo, mockMoments } from '../stories/mocks'

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

/**
 * Live processing state. A mock WebSocket replays scripted progress that crosses
 * a clip boundary, so the "Current clip" bar resets to 0% with "Starting..."
 * between clips. The decorator auto-clicks "Start Processing" to enter the state.
 */
export const Processing: Story = {
  name: 'Processing (clip progress resets between clips)',
  decorators: [
    withProcessingState(),
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
