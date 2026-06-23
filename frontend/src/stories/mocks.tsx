import React, { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import axios from "axios";
import type { Decorator } from "@storybook/react-vite";
import {
  useAppStore,
  type VideoInfo,
  type MomentCandidate,
  type ProcessedClip,
  type EffectSettings,
} from "../store/useAppStore";

export const mockVideo: VideoInfo = {
  id: "vid_1",
  title: "How I Built a Video Tool in a Weekend (Full Tutorial)",
  duration: 743,
  thumbnail_url: "",
  file_path: "/downloads/vid_1.mp4",
  platform: "youtube",
};

export const mockMoments: MomentCandidate[] = [
  {
    id: "m1",
    video_id: "vid_1",
    start: 12,
    end: 47,
    score: 92,
    reason: "High energy intro hook",
    thumbnail_url: "",
    approved: true,
  },
  {
    id: "m2",
    video_id: "vid_1",
    start: 128,
    end: 156,
    score: 87,
    reason: "Surprising reveal moment",
    thumbnail_url: "",
    approved: false,
  },
  {
    id: "m3",
    video_id: "vid_1",
    start: 310,
    end: 352,
    score: 78,
    reason: "Key tip viewers replay",
    thumbnail_url: "",
    approved: false,
  },
  {
    id: "m4",
    video_id: "vid_1",
    start: 503,
    end: 528,
    score: 71,
    reason: "Funny aside / laughter",
    thumbnail_url: "",
    approved: false,
  },
];

const defaultEffects: EffectSettings = {
  subtitles: true,
  blur_background: true,
  mirror: false,
  color_correction: true,
};

// file_path is now just the filename (served from /files/<filename>), matching
// the backend fix in video_processor.py — no leading directory.
export const mockClips: ProcessedClip[] = [
  {
    id: "c1",
    moment_id: "m1",
    file_path: "clip_1.mp4",
    status: "done",
    effects: defaultEffects,
  },
  {
    id: "c2",
    moment_id: "m2",
    file_path: "clip_2.mp4",
    status: "done",
    effects: defaultEffects,
  },
];

// A self-contained 9:16 (portrait) thumbnail used by stories to show the
// blurred-background moment preview in SubtitleStylePicker / BannerUpload.
// Encoded as an SVG data URI so no static asset / backend is required.
export const mockMomentThumbnail9x16 =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="360" height="640" viewBox="0 0 360 640">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#1a1a2e"/>
          <stop offset="0.5" stop-color="#16213e"/>
          <stop offset="1" stop-color="#0f3460"/>
        </linearGradient>
      </defs>
      <rect width="360" height="640" fill="url(#bg)"/>
      <ellipse cx="180" cy="230" rx="90" ry="90" fill="#94a3b8" opacity="0.35"/>
      <path d="M40 640 Q180 360 320 640 Z" fill="#94a3b8" opacity="0.35"/>
      <circle cx="300" cy="90" r="40" fill="#06b6d4" opacity="0.4"/>
    </svg>`,
  );

// Moments whose thumbnail_url points at the 9:16 portrait preview above, so the
// vertical preview surfaces (SubtitleStylePicker / BannerUpload read moments[0]).
export const mockMomentsWithThumbnail: MomentCandidate[] = mockMoments.map(
  (m) => ({
    ...m,
    thumbnail_url: mockMomentThumbnail9x16,
  }),
);

export interface StoreSeed {
  currentVideo?: VideoInfo | null;
  moments?: MomentCandidate[];
  selectedMomentIds?: string[];
  processedClips?: ProcessedClip[];
  globalEffects?: EffectSettings;
}

/**
 * Seeds the zustand store at render time (via a useState initializer, which runs
 * once per mount BEFORE children render) and wraps the story in a MemoryRouter.
 * Seeding at render time — not at module load — ensures each story re-applies its
 * own state when switched, since all stories share the same global store.
 */
export function withClipForge(
  seed: StoreSeed = {},
  initialPath = "/download",
): Decorator {
  const Wrapper: Decorator = (Story) => {
    useState(() => {
      useAppStore.setState({
        currentVideo: seed.currentVideo ?? null,
        moments: seed.moments ?? [],
        selectedMomentIds: seed.selectedMomentIds ?? [],
        processedClips: seed.processedClips ?? [],
        globalEffects: seed.globalEffects ?? defaultEffects,
      });
      return null;
    });

    return (
      <MemoryRouter initialEntries={[initialPath]}>
        <Story />
      </MemoryRouter>
    );
  };
  return Wrapper;
}

/**
 * Intercepts the YouTube auth status check so PublishPage renders the
 * "Connected to YouTube" state instead of firing a real (404) request.
 * Also serves the per-clip full-path endpoint that the "Copy Path" button
 * fetches (`GET /api/export/<clipId>/path` -> `{ file_path }`), so the
 * copy-path success feedback works without a backend.
 * Patches axios.get for those endpoints only; all other calls pass through.
 */
export function withMockAuth(authenticated = true): Decorator {
  const Wrapper: Decorator = (Story) => {
    useState(() => {
      const realGet = axios.get.bind(axios);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (axios as any).get = (url: string, ...rest: any[]) => {
        if (typeof url === "string" && url.includes("/api/auth/youtube")) {
          return Promise.resolve({
            data: authenticated
              ? { authenticated: true }
              : {
                  authenticated: false,
                  auth_url:
                    "https://accounts.google.com/o/oauth2/v2/auth?mock=1",
                },
          });
        }
        // Copy Path: backend returns the absolute file path for a clip.
        const exportMatch =
          typeof url === "string" && url.match(/\/api\/export\/([^/]+)\/path/);
        if (exportMatch) {
          const clipId = exportMatch[1];
          return Promise.resolve({
            data: { file_path: `/home/user/clipforge/output/${clipId}.mp4` },
          });
        }
        return realGet(url, ...rest);
      };
      return null;
    });
    return <Story />;
  };
  return Wrapper;
}

export interface ProcessingStep {
  current_clip: number;
  total_clips: number;
  clip_progress: number;
  clip_message: string;
}

/**
 * Drives ProcessPage into its live "processing" state without a backend.
 *
 * It mocks axios.post('/api/process') to return a job id, then replaces the
 * global WebSocket with a fake that replays a scripted sequence of progress
 * messages. The script crosses a clip boundary so the "current clip" progress
 * resets to 0% with the "Starting..." message — exactly the behaviour under test.
 * The sequence stops mid-stream (no "completed") so the UI stays on the
 * processing view for the screenshot.
 */
export function withProcessingState(steps?: ProcessingStep[]): Decorator {
  const script: ProcessingStep[] = steps ?? [
    {
      current_clip: 1,
      total_clips: 3,
      clip_progress: 0.0,
      clip_message: "Starting...",
    },
    {
      current_clip: 1,
      total_clips: 3,
      clip_progress: 0.45,
      clip_message: "Applying subtitles…",
    },
    {
      current_clip: 1,
      total_clips: 3,
      clip_progress: 0.9,
      clip_message: "Encoding…",
    },
    // Clip boundary — progress resets to 0% with "Starting..."
    {
      current_clip: 2,
      total_clips: 3,
      clip_progress: 0.0,
      clip_message: "Starting...",
    },
    {
      current_clip: 2,
      total_clips: 3,
      clip_progress: 0.3,
      clip_message: "Blurring background…",
    },
  ];

  const Wrapper: Decorator = (Story) => {
    useState(() => {
      // 1) Mock the POST that kicks off processing.
      const realPost = axios.post.bind(axios);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (axios as any).post = (url: string, ...rest: any[]) => {
        if (typeof url === "string" && url.includes("/api/process")) {
          return Promise.resolve({
            data: {
              job_id: "mock-job",
              total_clips: script[script.length - 1].total_clips,
            },
          });
        }
        return realPost(url, ...rest);
      };

      // 2) Replace WebSocket with a scripted fake that emits progress messages.
      class MockWebSocket {
        onmessage: ((ev: { data: string }) => void) | null = null;
        onerror: (() => void) | null = null;
        onopen: (() => void) | null = null;
        onclose: (() => void) | null = null;
        constructor() {
          let i = 0;
          const tick = () => {
            if (i >= script.length) return;
            this.onmessage?.({
              data: JSON.stringify({ status: "processing", ...script[i] }),
            });
            i += 1;
            setTimeout(tick, 600);
          };
          setTimeout(tick, 150);
        }
        send() {}
        close() {}
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).WebSocket = MockWebSocket as any;
      return null;
    });

    // Auto-click "Start Processing" once the story has mounted so the
    // processing UI is visible without a play function.
    React.useEffect(() => {
      const id = setInterval(() => {
        const btn = Array.from(document.querySelectorAll("button")).find((b) =>
          /start processing/i.test(b.textContent || ""),
        );
        if (btn) {
          (btn as HTMLButtonElement).click();
          clearInterval(id);
        }
      }, 100);
      return () => clearInterval(id);
    }, []);

    return <Story />;
  };
  return Wrapper;
}

export interface DownloadProgress {
  percent: number;
  speed: string;
  eta: string;
  downloaded_bytes: number;
  total_bytes: number;
  fragment_index: number | null;
  fragment_count: number | null;
}

/**
 * Drives DownloadPage into its live "downloading" state without a backend.
 *
 * It mocks axios.post('/api/download') to return a job id, then replaces the
 * global WebSocket with a fake that replays a scripted sequence of
 * `{ status: 'downloading', progress: {...} }` messages. The final message
 * leaves the page populated with rich progress stats — speed (cyan), ETA,
 * downloaded / total size, and an HLS fragment counter (orange) — and the
 * script stops mid-stream (no `completed`) so the progress card stays on
 * screen for the screenshot. The decorator auto-fills the URL field and
 * clicks "Download" so the loading UI appears without a play function.
 */
export function withDownloadingState(steps?: DownloadProgress[]): Decorator {
  const script: DownloadProgress[] = steps ?? [
    {
      percent: 18,
      speed: "2.41 MiB/s",
      eta: "01:12",
      downloaded_bytes: 18 * 1024 * 1024,
      total_bytes: 104 * 1024 * 1024,
      fragment_index: 24,
      fragment_count: 142,
    },
    {
      percent: 47,
      speed: "4.08 MiB/s",
      eta: "00:38",
      downloaded_bytes: 49 * 1024 * 1024,
      total_bytes: 104 * 1024 * 1024,
      fragment_index: 67,
      fragment_count: 142,
    },
    // Final message — stays on screen with all four stat cells populated.
    {
      percent: 63,
      speed: "3.72 MiB/s",
      eta: "00:24",
      downloaded_bytes: 66 * 1024 * 1024,
      total_bytes: 104 * 1024 * 1024,
      fragment_index: 89,
      fragment_count: 142,
    },
  ];

  const Wrapper: Decorator = (Story) => {
    useState(() => {
      // 1) Mock the POST that kicks off the download.
      const realPost = axios.post.bind(axios);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (axios as any).post = (url: string, ...rest: any[]) => {
        if (typeof url === "string" && url.includes("/api/download")) {
          return Promise.resolve({ data: { job_id: "mock-download-job" } });
        }
        return realPost(url, ...rest);
      };

      // 2) Replace WebSocket with a scripted fake that emits progress messages.
      class MockWebSocket {
        onmessage: ((ev: { data: string }) => void) | null = null;
        onerror: (() => void) | null = null;
        onopen: (() => void) | null = null;
        onclose: (() => void) | null = null;
        constructor() {
          let i = 0;
          const tick = () => {
            if (i >= script.length) return;
            this.onmessage?.({
              data: JSON.stringify({
                status: "downloading",
                progress: script[i],
              }),
            });
            i += 1;
            setTimeout(tick, 600);
          };
          setTimeout(tick, 150);
        }
        send() {}
        close() {}
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).WebSocket = MockWebSocket as any;
      return null;
    });

    // Auto-fill the URL input and click "Download" once mounted so the
    // downloading UI (and the rich stats grid) is visible without a play fn.
    React.useEffect(() => {
      const id = setInterval(() => {
        const input =
          document.querySelector<HTMLInputElement>('input[type="text"]');
        const btn = Array.from(document.querySelectorAll("button")).find((b) =>
          /^\s*download\s*$/i.test(b.textContent || ""),
        );
        if (input && btn) {
          const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype,
            "value",
          )?.set;
          setter?.call(input, "https://youtube.com/watch?v=dQw4w9WgXcQ");
          input.dispatchEvent(new Event("input", { bubbles: true }));
          // Let React flush the controlled value before clicking.
          setTimeout(() => (btn as HTMLButtonElement).click(), 50);
          clearInterval(id);
        }
      }, 100);
      return () => clearInterval(id);
    }, []);

    return <Story />;
  };
  return Wrapper;
}

/**
 * Keeps MomentsPage on its pre-detection view so the Detection Settings card
 * (min / max clip duration + max moments sliders) and the "No moments detected
 * yet" empty state are visible for a screenshot.
 *
 * MomentsPage auto-starts detection on mount whenever a video is present and no
 * moments exist. This decorator mocks axios.post('/api/moments/detect') to
 * return a never-resolving promise, so the request is issued but no job id ever
 * comes back — detection never actually flips the UI into the "detecting"
 * progress state, leaving the settings card on screen. The global WebSocket is
 * also stubbed so no real socket is opened.
 */
export function withDetectionBlocked(): Decorator {
  const Wrapper: Decorator = (Story) => {
    useState(() => {
      const realPost = axios.post.bind(axios);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (axios as any).post = (url: string, ...rest: any[]) => {
        if (typeof url === "string" && url.includes("/api/moments/detect")) {
          // Resolve immediately as an already-"completed" detection that found
          // zero moments. MomentsPage flips detecting back off and keeps the
          // moments list empty, so it renders the Detection Settings card and
          // the "No moments detected yet" empty state for the screenshot —
          // never entering the live progress view.
          return Promise.resolve({
            data: { status: "completed", moments: [] },
          });
        }
        return realPost(url, ...rest);
      };

      class MockWebSocket {
        onmessage: ((ev: { data: string }) => void) | null = null;
        onerror: (() => void) | null = null;
        onopen: (() => void) | null = null;
        onclose: (() => void) | null = null;
        send() {}
        close() {}
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).WebSocket = MockWebSocket as any;
      return null;
    });

    return <Story />;
  };
  return Wrapper;
}

export interface GpuStatusSeed {
  device?: string;
  is_gpu?: boolean;
  vram_usage?: {
    allocated_gb: number;
    reserved_gb: number;
    total_gb: number;
    free_gb: number;
  };
  nvenc_available?: boolean;
  loaded_models?: string[];
}

/**
 * Mocks `GET /api/gpu/status` so both the GPUStatusIndicator (reads
 * is_gpu / vram_usage / nvenc_available) and MomentsPage (reads
 * cuda_available to enable the LLM instructions field) render their
 * GPU-active state without a backend. All other axios.get calls pass through.
 *
 * Used by the MomentsPage settings-card story so the new GPU status indicator
 * shows a green pulsing dot + VRAM bar and the LLM instructions textarea is
 * enabled rather than dimmed.
 */
export function withGpuStatusMock(seed: GpuStatusSeed = {}): Decorator {
  const status = {
    device: seed.device ?? "cuda:0 (NVIDIA RTX 4060 Ti)",
    is_gpu: seed.is_gpu ?? true,
    cuda_available: seed.is_gpu ?? true,
    vram_usage: seed.vram_usage ?? {
      allocated_gb: 1.8,
      reserved_gb: 2.1,
      total_gb: 8,
      free_gb: 5.9,
    },
    nvenc_available: seed.nvenc_available ?? true,
    loaded_models: seed.loaded_models ?? ["whisper-distil-large-v3"],
  };

  const Wrapper: Decorator = (Story) => {
    useState(() => {
      const realGet = axios.get.bind(axios);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (axios as any).get = (url: string, ...rest: any[]) => {
        if (typeof url === "string" && url.includes("/api/gpu/status")) {
          return Promise.resolve({ data: status });
        }
        return realGet(url, ...rest);
      };
      return null;
    });
    return <Story />;
  };
  return Wrapper;
}

/**
 * Drives MomentsPage into its live "detecting" progress view without a backend.
 *
 * Strategy:
 * 1. Replace WebSocket with a fake that emits a scripted sequence of stage-1
 *    and stage-2 progress messages every ~800 ms, then stops (no "complete"),
 *    so the UI stays frozen mid-detection for the screenshot.
 * 2. After mount, auto-click the "Start Detection" button via a polling
 *    useEffect — this transitions the view from 'setup' → 'detecting' so the
 *    progress panel is visible.
 */
export function withDetectingProgress(): Decorator {
  const script = [
    // Stage 1 — Whisper
    { status: "progress", stage: 1, step: "transcription", progress: 0.05, detail: null },
    { status: "progress", stage: 1, step: "transcription", progress: 0.15, detail: null },
    { status: "progress", stage: 1, step: "whisper_done",  progress: 0.30, detail: { words: 5714, segments: 1011 } },
    // Stage 1 — YOLO
    { status: "progress", stage: 1, step: "face_detection", progress: 0.35, detail: null },
    { status: "progress", stage: 1, step: "face_detection", progress: 0.42, detail: null },
    { status: "progress", stage: 1, step: "yolo_done",      progress: 0.50, detail: { faces: 32 } },
    // Stage 1 — Audio
    { status: "progress", stage: 1, step: "audio_analysis", progress: 0.55, detail: null },
    { status: "progress", stage: 1, step: "audio_done",     progress: 0.60, detail: { peaks: 3709 } },
    // Stage 2 — Context + LLM chunks
    { status: "progress", stage: 2, step: "context_building", progress: 0.65, detail: null },
    { status: "progress", stage: 2, step: "llm_analysis",     progress: 0.70, detail: null },
    { status: "progress", stage: 2, step: "llm_chunk",        progress: 0.78, detail: { chunk: 1, total: 3 } },
    { status: "progress", stage: 2, step: "llm_chunk",        progress: 0.86, detail: { chunk: 2, total: 3 } },
    // Stopped here — UI stays in "detecting" for the screenshot
  ];

  const Wrapper: Decorator = (Story) => {
    useState(() => {
      let i = 0;
      class MockWebSocket {
        onmessage: ((ev: { data: string }) => void) | null = null;
        onerror: (() => void) | null = null;
        onopen: (() => void) | null = null;
        onclose: (() => void) | null = null;

        constructor() {
          // Fire onopen so MomentsPage knows the socket is live
          setTimeout(() => {
            this.onopen?.();
            const tick = () => {
              if (i >= script.length) return;
              this.onmessage?.({ data: JSON.stringify(script[i]) });
              i += 1;
              setTimeout(tick, 800);
            };
            setTimeout(tick, 300);
          }, 50);
        }
        send() {}
        close() {}
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).WebSocket = MockWebSocket as any;
      return null;
    });

    // Auto-click the "Start Detection" button once the setup view has mounted
    React.useEffect(() => {
      const id = setInterval(() => {
        const btn = Array.from(document.querySelectorAll("button")).find((b) =>
          /start\s*detection/i.test(b.textContent || ""),
        );
        if (btn) {
          (btn as HTMLButtonElement).click();
          clearInterval(id);
        }
      }, 100);
      return () => clearInterval(id);
    }, []);

    return <Story />;
  };
  return Wrapper;
}
