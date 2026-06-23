import type { Meta, StoryObj } from "@storybook/react-vite";
import MomentsPage from "./MomentsPage";
import {
  withClipForge,
  withDetectionBlocked,
  withDetectingProgress,
  withGpuStatusMock,
  mockVideo,
  mockMoments,
} from "../stories/mocks";

const meta = {
  title: "Pages/MomentsPage",
  component: MomentsPage,
  parameters: { layout: "fullscreen" },
} satisfies Meta<typeof MomentsPage>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Pre-detection setup wizard: AI Instructions textarea, Detection Settings
 * sliders (min/max duration, max moments), and the Launch button with
 * estimated time. GPU status indicator is shown green.
 */
export const SettingsCard: Story = {
  name: "Setup Wizard",
  decorators: [
    withGpuStatusMock(),
    withDetectionBlocked(),
    withClipForge({ currentVideo: mockVideo }, "/moments"),
  ],
};

/**
 * Live progress view — Stage 1 (Whisper ✓, YOLO ✓, Audio ✓) complete,
 * Stage 2 (Qwen LLM) actively analyzing chunk 2/3. The WebSocket is replaced
 * with a fake that emits a scripted progress sequence so the view stays
 * mid-detection for the screenshot.
 */
export const DetectingProgress: Story = {
  name: "Live Detection Progress",
  decorators: [
    withGpuStatusMock(),
    withDetectingProgress(),
    withClipForge({ currentVideo: mockVideo }, "/moments"),
  ],
};

/**
 * Results view with all moments selected.
 */
export const WithMoments: Story = {
  name: "Detected Moments",
  decorators: [
    withClipForge(
      {
        currentVideo: mockVideo,
        moments: mockMoments,
        selectedMomentIds: mockMoments.map((m) => m.id),
      },
      "/moments",
    ),
  ],
};

/**
 * Results view with only two moments selected.
 */
export const PartialSelection: Story = {
  name: "Partial Selection",
  decorators: [
    withClipForge(
      {
        currentVideo: mockVideo,
        moments: mockMoments,
        selectedMomentIds: ["m1", "m3"],
      },
      "/moments",
    ),
  ],
};
