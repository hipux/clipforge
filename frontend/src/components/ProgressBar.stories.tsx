import type { Meta, StoryObj } from '@storybook/react-vite'
import ProgressBar from './ProgressBar'

const meta = {
  title: 'Components/ProgressBar',
  component: ProgressBar,
  parameters: { layout: 'padded' },
  decorators: [(Story) => <div style={{ width: 480 }}><Story /></div>],
} satisfies Meta<typeof ProgressBar>

export default meta
type Story = StoryObj<typeof meta>

export const Midway: Story = {
  args: { progress: 45, message: 'Downloading... 45%' },
}

export const Complete: Story = {
  args: { progress: 100, message: 'Done!' },
}
