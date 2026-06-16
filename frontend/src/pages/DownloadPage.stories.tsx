import type { Meta, StoryObj } from '@storybook/react-vite'
import DownloadPage from './DownloadPage'
import { withClipForge, mockVideo } from '../stories/mocks'

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
