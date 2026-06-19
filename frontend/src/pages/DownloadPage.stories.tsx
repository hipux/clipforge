import type { Meta, StoryObj } from '@storybook/react-vite'
import DownloadPage from './DownloadPage'
import { withClipForge, withDownloadingState, mockVideo } from '../stories/mocks'

const meta = {
  title: 'Pages/DownloadPage',
  component: DownloadPage,
  parameters: { layout: 'fullscreen' },
} satisfies Meta<typeof DownloadPage>

export default meta
type Story = StoryObj<typeof meta>

/**
 * Default URL-input view. The "Supported" platform badges row sits under the
 * URL field, now including the new Twitch badge (purple/violet Tv icon)
 * alongside YouTube, Rutube and VK Video.
 */
export const Empty: Story = {
  name: 'Empty (URL input)',
  decorators: [withClipForge({}, '/download')],
}

/**
 * Focuses on the supported-platforms badges row. Same default URL-input view —
 * scroll target is the four badges below the input: YouTube (red), Rutube
 * (orange), VK Video (blue) and the new Twitch badge (purple/violet).
 */
export const PlatformBadges: Story = {
  name: 'Platform Badges (Twitch)',
  decorators: [withClipForge({}, '/download')],
}

export const WithDownloadedVideo: Story = {
  name: 'Video Downloaded',
  decorators: [withClipForge({ currentVideo: mockVideo }, '/download')],
}

/**
 * Live download in progress. A mock WebSocket replays scripted progress so the
 * rich stats grid below the progress bar is populated: download Speed (cyan,
 * Zap icon), ETA (clock icon), Size downloaded / total (HardDrive icon), and an
 * HLS Fragments counter (orange, Download icon). The decorator auto-fills the
 * URL field and clicks "Download" to enter the state.
 */
export const Downloading: Story = {
  name: 'Downloading (rich progress stats)',
  decorators: [withDownloadingState(), withClipForge({}, '/download')],
}
