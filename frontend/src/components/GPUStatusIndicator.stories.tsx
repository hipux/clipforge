import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import type { Decorator } from '@storybook/react-vite'
import axios from 'axios'
import { GPUStatusIndicator } from './GPUStatusIndicator'

interface VRAMUsage {
  allocated_gb: number
  reserved_gb: number
  total_gb: number
  free_gb: number
}

interface GPUStatus {
  device: string
  is_gpu: boolean
  vram_usage: VRAMUsage
  nvenc_available: boolean
  loaded_models: string[]
}

/**
 * GPUStatusIndicator polls `GET /api/gpu/status` every 5s and renders nothing
 * until the first response arrives. This decorator patches axios.get for that
 * endpoint to return a fixed GPUStatus, so the indicator renders deterministically
 * without a backend. All other requests pass through.
 */
function withGpuStatus(status: GPUStatus): Decorator {
  const Wrapper: Decorator = (Story) => {
    useState(() => {
      const realGet = axios.get.bind(axios)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ;(axios as any).get = (url: string, ...rest: any[]) => {
        if (typeof url === 'string' && url.includes('/api/gpu/status')) {
          return Promise.resolve({ data: status })
        }
        return realGet(url, ...rest)
      }
      return null
    })
    return <Story />
  }
  return Wrapper
}

const gpuActive: GPUStatus = {
  device: 'cuda:0 (NVIDIA RTX 4060 Ti)',
  is_gpu: true,
  vram_usage: { allocated_gb: 1.8, reserved_gb: 2.1, total_gb: 8, free_gb: 5.9 },
  nvenc_available: true,
  loaded_models: ['whisper-distil-large-v3'],
}

const gpuHighVram: GPUStatus = {
  device: 'cuda:0 (NVIDIA RTX 4060 Ti)',
  is_gpu: true,
  vram_usage: { allocated_gb: 6.4, reserved_gb: 6.9, total_gb: 8, free_gb: 1.1 },
  nvenc_available: true,
  loaded_models: ['qwen2.5-7b-instruct'],
}

const cpuFallback: GPUStatus = {
  device: 'cpu',
  is_gpu: false,
  vram_usage: { allocated_gb: 0, reserved_gb: 0, total_gb: 0, free_gb: 0 },
  nvenc_available: false,
  loaded_models: [],
}

const meta = {
  title: 'Components/GPUStatusIndicator',
  component: GPUStatusIndicator,
  parameters: { layout: 'padded' },
} satisfies Meta<typeof GPUStatusIndicator>

export default meta
type Story = StoryObj<typeof meta>

/**
 * GPU active: green pulsing dot, "GPU режим", a VRAM bar at 2.1 / 8 GB and the
 * NVENC ✓ badge.
 */
export const GpuActive: Story = {
  name: 'GPU Active (VRAM 2.1/8GB)',
  decorators: [withGpuStatus(gpuActive)],
}

/**
 * GPU under heavy load — VRAM bar turns red above 80% usage (6.9 / 8 GB).
 */
export const GpuHighVram: Story = {
  name: 'GPU High VRAM (red bar)',
  decorators: [withGpuStatus(gpuHighVram)],
}

/**
 * CPU fallback: yellow dot, "CPU режим", no VRAM bar and no NVENC badge.
 */
export const CpuFallback: Story = {
  name: 'CPU Fallback Mode',
  decorators: [withGpuStatus(cpuFallback)],
}
