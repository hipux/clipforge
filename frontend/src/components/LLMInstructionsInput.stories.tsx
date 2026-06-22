import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { LLMInstructionsInput } from './LLMInstructionsInput'

/**
 * LLMInstructionsInput is a controlled component. This harness holds the value
 * in local state so the textarea is interactive in Storybook.
 */
function ControlledLLMInstructionsInput({
  initialValue = '',
  isGPU,
}: {
  initialValue?: string
  isGPU: boolean
}) {
  const [value, setValue] = useState(initialValue)
  return (
    <div className="w-[480px]">
      <LLMInstructionsInput value={value} onChange={setValue} isGPU={isGPU} />
    </div>
  )
}

const meta = {
  title: 'Components/LLMInstructionsInput',
  component: LLMInstructionsInput,
  parameters: { layout: 'padded' },
  render: (args) => (
    <ControlledLLMInstructionsInput
      initialValue={args.value}
      isGPU={args.isGPU}
    />
  ),
} satisfies Meta<typeof LLMInstructionsInput>

export default meta
type Story = StoryObj<typeof meta>

/**
 * GPU available — the AI instructions textarea is enabled and editable, with a
 * hint placeholder and the 0/500 character counter.
 */
export const GpuEnabled: Story = {
  name: 'GPU Enabled',
  args: {
    isGPU: true,
    value:
      'Выбирай только смешные моменты, избегай технических объяснений и длинных пауз.',
  },
}

/**
 * GPU unavailable — the field is disabled (dimmed) and shows the
 * "GPU недоступен — ИИ-анализ отключен" warning badge.
 */
export const GpuDisabled: Story = {
  name: 'GPU Disabled',
  args: {
    isGPU: false,
    value: '',
  },
}
