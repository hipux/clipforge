import type { Meta, StoryObj } from "@storybook/react-vite";
import MomentsPage from "./MomentsPage";
import {
  withClipForge,
  withDetectionBlocked,
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
 * Pre-detection view shown before any moments are detected: the Detection
 * Settings card with three sliders — Min clip duration, Max clip duration and
 * Max moments (store defaults 30s / 90s / 15) — followed by the "No moments
 * detected yet" empty state with a Start Detection button.
 *
 * A video is present (so the page does not redirect to /download), and
 * withDetectionBlocked stubs the /api/moments/detect request so auto-detection
 * never flips the UI into its progress state — keeping the settings card and
 * empty state on screen.
 */
export const SettingsCard: Story = {
  name: "Detection Settings (GPU status + LLM)",
  decorators: [
    withGpuStatusMock(),
    withDetectionBlocked(),
    withClipForge({ currentVideo: mockVideo }, "/moments"),
  ],
};

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
