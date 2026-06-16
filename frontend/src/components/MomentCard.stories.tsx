import type { Meta, StoryObj } from '@storybook/react-vite'
import MomentCard from './MomentCard'
import { mockMoments } from '../stories/mocks'

const meta = {
  title: 'Components/MomentCard',
  component: MomentCard,
  parameters: { layout: 'padded' },
  args: { onToggle: () => {} },
} satisfies Meta<typeof MomentCard>

export default meta
type Story = StoryObj<typeof meta>

export const Selected: Story = {
  args: { moment: mockMoments[0], isSelected: true },
}

export const Unselected: Story = {
  args: { moment: mockMoments[1], isSelected: false },
}
