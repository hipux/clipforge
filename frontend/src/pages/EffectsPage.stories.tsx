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

export const WithBannerEnabled: Story = {
  name: 'Effects + Banner Enabled',
  decorators: [
    withClipForge(
      {
        currentVideo: mockVideo,
        moments: mockMoments,
        selectedMomentIds: ['m1', 'm2', 'm3'],
        globalEffects: {
          subtitles: true,
          blur_background: true,
          mirror: false,
          color_correction: true,
          subtitle_style: 'neon',
          banner: {
            enabled: true,
            banner_id: 'demo',
            url: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjUwIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbGw9IiMwNmI2ZDQiIG9wYWNpdHk9IjAuOSIgcng9IjgiLz48dGV4dCB4PSI1MCUiIHk9IjUwJSIgZmlsbD0id2hpdGUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIyMCIgZm9udC13ZWlnaHQ9ImJvbGQiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGRvbWluYW50LWJhc2VsaW5lPSJjZW50cmFsIj5NeUJyYW5kPC90ZXh0Pjwvc3ZnPg==',
            position: 'top-right',
            size: 25,
            opacity: 85,
          },
        },
      },
      '/effects',
    ),
  ],
}
