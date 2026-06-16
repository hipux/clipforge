import type { Meta, StoryObj } from '@storybook/react-vite'
import EffectsPage from './EffectsPage'
import { withClipForge, mockVideo, mockMoments } from '../stories/mocks'

const meta = {
  title: 'Pages/EffectsPage',
  component: EffectsPage,
  parameters: { layout: 'fullscreen' },
} satisfies Meta<typeof EffectsPage>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  name: 'Configure Effects',
  decorators: [
    withClipForge(
      {
        currentVideo: mockVideo,
        moments: mockMoments,
        selectedMomentIds: ['m1', 'm2', 'm3'],
      },
      '/effects',
    ),
  ],
}
