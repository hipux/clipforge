import type { Meta, StoryObj } from '@storybook/react-vite'
import BannerUpload from './BannerUpload'
import {
  withClipForge,
  mockVideo,
  mockMomentsWithThumbnail,
  mockMomentThumbnail9x16,
} from '../stories/mocks'

const meta = {
  title: 'Components/BannerUpload',
  component: BannerUpload,
  parameters: { layout: 'padded' },
} satisfies Meta<typeof BannerUpload>

export default meta
type Story = StoryObj<typeof meta>

// A small self-contained banner/watermark logo (SVG data URI) used for the
// overlay in the live preview.
const bannerLogo =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="160" height="48" viewBox="0 0 160 48">
      <rect width="160" height="48" rx="10" fill="#06b6d4"/>
      <text x="80" y="31" font-family="Arial, sans-serif" font-size="22" font-weight="bold" fill="#0a0a0f" text-anchor="middle">CLIPFORGE</text>
    </svg>`,
  )

/**
 * Active banner: the 9:16 vertical live preview shows the moment thumbnail as
 * the background with the uploaded watermark overlaid at the chosen position.
 */
export const WithBannerPreview: Story = {
  name: 'Banner Preview (9:16 Vertical)',
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
          banner: {
            enabled: true,
            banner_id: 'bnr_1',
            url: bannerLogo,
            position: 'top-right',
            size: 24,
            opacity: 90,
          },
        },
      },
      '/effects',
    ),
  ],
}

/**
 * Banner positioned at the bottom-center with reduced opacity, still over the
 * 9:16 moment-thumbnail preview.
 */
export const BannerBottomCenter: Story = {
  name: 'Banner Bottom-Center',
  decorators: [
    withClipForge(
      {
        currentVideo: { ...mockVideo, thumbnail_url: mockMomentThumbnail9x16 },
        moments: mockMomentsWithThumbnail,
        globalEffects: {
          subtitles: true,
          blur_background: true,
          mirror: false,
          color_correction: true,
          banner: {
            enabled: true,
            banner_id: 'bnr_2',
            url: bannerLogo,
            position: 'bottom-center',
            size: 35,
            opacity: 60,
          },
        },
      },
      '/effects',
    ),
  ],
}

/**
 * Empty upload state: no banner uploaded yet, so the dashed upload dropzone is
 * shown.
 */
export const UploadEmpty: Story = {
  name: 'Empty (Upload Prompt)',
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
          banner: {
            enabled: false,
            position: 'top-right',
            size: 20,
            opacity: 80,
          },
        },
      },
      '/effects',
    ),
  ],
}
