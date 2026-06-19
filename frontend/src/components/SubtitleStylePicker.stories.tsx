import type { Meta, StoryObj } from '@storybook/react-vite'
import SubtitleStylePicker from './SubtitleStylePicker'
import {
  withClipForge,
  mockVideo,
  mockMoments,
  mockMomentsWithThumbnail,
} from '../stories/mocks'

const meta = {
  title: 'Components/SubtitleStylePicker',
  component: SubtitleStylePicker,
  parameters: { layout: 'padded' },
} satisfies Meta<typeof SubtitleStylePicker>

export default meta
type Story = StoryObj<typeof meta>

/**
 * Default state: the 9:16 vertical preview uses the first moment's blurred
 * thumbnail as the background for each subtitle-style card.
 */
export const WithMomentThumbnail: Story = {
  name: 'Moment Thumbnail (9:16 Vertical)',
  decorators: [
    withClipForge(
      {
        currentVideo: mockVideo,
        moments: mockMomentsWithThumbnail,
        globalEffects: {
          subtitles: true,
          blur_background: true,
          mirror: false,
          color_correction: true,
          subtitle_style: 'karaoke',
        },
      },
      '/effects',
    ),
  ],
}

/**
 * Fallback state: no moment thumbnails available, so each 9:16 preview shows
 * the gradient + silhouette placeholder behind the subtitle sample.
 */
export const GradientFallback: Story = {
  name: 'Gradient Fallback (No Thumbnail)',
  decorators: [
    withClipForge(
      {
        currentVideo: mockVideo,
        moments: mockMoments,
        globalEffects: {
          subtitles: true,
          blur_background: true,
          mirror: false,
          color_correction: true,
          subtitle_style: 'neon',
        },
      },
      '/effects',
    ),
  ],
}
