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

export const Empty: Story = {
  name: 'Empty (URL input)',
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
