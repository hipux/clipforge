import type { Meta, StoryObj } from '@storybook/react-vite'
import VideoCard from './VideoCard'
import { mockVideo } from '../stories/mocks'

const meta = {
  title: 'Components/VideoCard',
  component: VideoCard,
  parameters: { layout: 'padded' },
} satisfies Meta<typeof VideoCard>

export default meta
type Story = StoryObj<typeof meta>

export const YouTube: Story = {
  args: { video: mockVideo },
}

export const VKVideo: Story = {
  args: { video: { ...mockVideo, platform: 'vk', title: 'VK Clip: Best Moments', duration: 95 } },
}
