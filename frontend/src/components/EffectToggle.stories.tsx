import type { Meta, StoryObj } from '@storybook/react-vite'
import { Captions, Layers, FlipHorizontal, Palette } from 'lucide-react'
import EffectToggle from './EffectToggle'

const meta = {
  title: 'Components/EffectToggle',
  component: EffectToggle,
  parameters: { layout: 'padded' },
  args: { onToggle: () => {} },
} satisfies Meta<typeof EffectToggle>

export default meta
type Story = StoryObj<typeof meta>

export const Enabled: Story = {
  args: {
    icon: <Captions size={18} />,
    label: 'Auto Subtitles',
    description: 'AI-generated subtitles burned into video',
    enabled: true,
  },
}

export const Disabled: Story = {
  args: {
    icon: <FlipHorizontal size={18} />,
    label: 'Mirror Effect',
    description: 'Horizontal flip of the video',
    enabled: false,
  },
}

export const BlurredBackground: Story = {
  args: {
    icon: <Layers size={18} />,
    label: 'Blurred Background',
    description: 'Scale to 9:16 vertical format with blurred background fill',
    enabled: true,
  },
}

export const ColorEnhancement: Story = {
  args: {
    icon: <Palette size={18} />,
    label: 'Color Enhancement',
    description: 'Subtle boost: +1% brightness, +1% contrast, +2% saturation',
    enabled: false,
  },
}
