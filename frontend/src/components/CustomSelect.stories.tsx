import type { Meta, StoryObj } from '@storybook/react'
import { useState } from 'react'
import CustomSelect from './CustomSelect'
import { Tv, Video, Sparkles, Mic, Gamepad2 } from 'lucide-react'

const meta: Meta<typeof CustomSelect> = {
  title: 'Components/CustomSelect',
  component: CustomSelect,
  decorators: [(Story) => (
    <div className="p-6 max-w-sm"><Story /></div>
  )],
}
export default meta
type Story = StoryObj<typeof CustomSelect>


const platformOptions = [
  { value: 'youtube', label: 'YouTube',
    icon: <Tv size={14} className="text-rose-500" />,
    description: 'Channel via ytb-up cookies' },
  { value: 'tiktok', label: 'TikTok',
    icon: <Video size={14} />,
    description: 'planned — not yet wired',
    disabled: true },
  { value: 'instagram', label: 'Instagram Reels',
    icon: <Sparkles size={14} />,
    description: 'planned — not yet wired',
    disabled: true },
] as const

export const PlatformPicker: Story = {
  render: () => {
    const [v, setV] = useState<string>('youtube')
    return <CustomSelect value={v} onChange={setV} options={platformOptions} />
  },
}

const presetOptions = [
  { value: 'default', label: 'Universal',
    icon: <Sparkles size={14} />,
    description: 'Generic viral clips, balanced' },
  { value: 'youtube_cuts', label: 'YouTube cuts',
    icon: <Mic size={14} />,
    description: 'Long hook + clear payoff' },
  { value: 'films_anime', label: 'Films / Anime',
    icon: <Tv size={14} />,
    description: 'Action / emotional / music beats' },
  { value: 'streams', label: 'Streams / Gaming',
    icon: <Gamepad2 size={14} />,
    description: 'YamNet laugh/shock heavy' },
] as const

export const PresetPicker: Story = {
  render: () => {
    const [v, setV] = useState<string>('youtube_cuts')
    return <CustomSelect value={v} onChange={setV} options={presetOptions} />
  },
}

const tagOptions = [
  { value: 'a', label: 'Action / chase' },
  { value: 'b', label: 'Comedy / fail' },
  { value: 'c', label: 'Dance / music' },
  { value: 'd', label: 'Reaction / shout' },
  { value: 'e', label: 'Tutorial / how-to' },
  { value: 'f', label: 'Story / candid' },
  { value: 'g', label: 'AMA / interview' },
  { value: 'h', label: 'Niche depth note' },
  { value: 'i', label: 'Crosstalk' },
  { value: 'j', label: 'Background noise' },
] as const

export const MultiTagPicker: Story = {
  render: () => {
    const [v, setV] = useState<string[]>(['b', 'd'])
    return (
      <CustomSelect
        multi
        value={v}
        onChange={(vs) => setV(vs)}
        options={tagOptions}
      />
    )
  },
}

export const EmptyPlaceholder: Story = {
  render: () => {
    const [v, setV] = useState<string | null>(null)
    return (
      <CustomSelect
        value={v}
        onChange={(vv) => setV(vv)}
        options={platformOptions}
        placeholder="Channel"
      />
    )
  },
}

export const Disabled: Story = {
  render: () => (
    <CustomSelect
      value={'youtube'}
      onChange={() => {}}
      options={platformOptions}
      disabled
    />
  ),
}
