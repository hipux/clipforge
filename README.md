# ClipForge 🎬

> **💰 100% FREE — No paid services, no subscriptions, no API costs.**

Local video clip processing & publishing tool that lets you download long-form videos from YouTube, Rutube, or VK Video, automatically detect interesting moments using fully local AI models, apply professional video effects, and publish finished clips directly to YouTube Shorts — all from a single web interface running on your machine.

## ✨ Features

- **Video Download** from YouTube, Rutube, VK Video (using yt-dlp)
- **AI Moment Detection** using local analysis:
  - Audio energy peaks (librosa)
  - Scene change detection (OpenCV)
  - Speech content scoring (faster-whisper + keyword heuristics)
- **Video Effects** (FFmpeg):
  - Auto-generated subtitles (faster-whisper AI)
  - Dynamic blurred background (9:16 vertical format)
  - Mirror effect
  - Subtle color enhancement
- **Publishing**:
  - Direct upload to YouTube Shorts (free YouTube Data API v3)
  - Local export for TikTok, Instagram Reels, VK Clips, etc.

## 🆓 Zero-Cost Guarantee

| Component | Tool | Cost |
|-----------|------|------|
| Video download | yt-dlp | Free, open-source |
| Video processing | FFmpeg | Free, open-source |
| Speech-to-text | faster-whisper | Free, runs locally |
| Scene detection | OpenCV + librosa | Free, runs locally |
| Moment scoring | Local keyword engine | Free, no external APIs |
| YouTube publishing | YouTube Data API v3 | **Free tier (10K units/day)** |
| Backend | Python + FastAPI | Free, open-source |
| Frontend | React + Vite + Tailwind | Free, open-source |
| Database | SQLite | Free, open-source |

**YouTube API quota:** 10,000 units/day free. One video upload ≈ 1,600 units → **~6 videos/day for free**. Perfect for personal use!

## 🔧 Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **FFmpeg** (installed via setup script)
- **10+ GB free disk space** (for Whisper models and video files)

## 🪟 Running on Windows

ClipForge runs natively on WSL2 (recommended) or Git Bash:

### Option A: WSL2 (Recommended)
1. Install WSL2: `wsl --install` in PowerShell (as Administrator)
2. Open the Ubuntu terminal from Start Menu
3. Clone this repo and follow the Linux setup instructions below

### Option B: Native Windows
1. Install Python 3.11+ from [python.org](https://www.python.org/downloads/)
2. Install Node.js 18+ from [nodejs.org](https://nodejs.org/)
3. Install FFmpeg: `winget install Gyan.FFmpeg` (or via [chocolatey](https://chocolatey.org/): `choco install ffmpeg`)
4. Use `setup.bat` instead of `setup.sh` (see below)
5. Use `start.bat` instead of `start.sh`

**Windows setup:**
```batch
setup.bat
```

**Windows start:**
```batch
start.bat
```

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <repo>
cd clipforge
chmod +x setup.sh start.sh
./setup.sh
```

The setup script will:
- Install FFmpeg
- Create Python virtual environment
- Install all Python dependencies
- Install frontend dependencies
- Create workspace directories

### 2. (Optional) YouTube API Setup

To upload directly to YouTube Shorts (completely free):

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (no billing required)
3. Enable **YouTube Data API v3**:
   - Go to **APIs & Services → Library**
   - Search "YouTube Data API v3"
   - Click **Enable**
4. Create OAuth 2.0 credentials:
   - Go to **APIs & Services → Credentials**
   - Click **Create Credentials → OAuth 2.0 Client ID**
   - Configure consent screen (External, test mode)
   - Application type: **Desktop app**
5. Download `client_secrets.json` and place in project root (`/home/user/clipforge/client_secrets.json`)

**First-time auth:** When you first upload a video, ClipForge will open a browser window for you to authorize your YouTube account. This is a one-time setup.

### 3. Start ClipForge

```bash
./start.sh
```

This starts:
- Backend API at `http://localhost:8000`
- Frontend UI at `http://localhost:5173` (opens automatically)

## 📖 Usage Guide

### Step 1: Download Video

1. Paste a video URL (YouTube, Rutube, or VK Video)
2. Click "Download"
3. Wait for download to complete (progress shown in real-time)

### Step 2: Detect Moments

1. Click "Continue to Moments" or navigate to Moments tab
2. AI automatically detects 5-15 interesting moments
3. Review candidates (score, timestamps, reason)
4. Select the clips you want (click to toggle)

### Step 3: Configure Effects

1. Toggle effects on/off:
   - **Auto Subtitles**: AI-generated word-by-word subtitles
   - **Blurred Background**: Dynamic blurred background (converts to 9:16 vertical)
   - **Mirror**: Horizontal flip
   - **Color Enhancement**: Subtle brightness/contrast boost
2. Effects apply to all selected clips

### Step 4: Process

1. Click "Start Processing"
2. Watch real-time progress for each clip
3. All effects applied in a single FFmpeg pass (fast!)

### Step 5: Publish

**Option A: YouTube Shorts (direct upload)**
- Connect your YouTube account (one-time OAuth)
- Fill in title and description
- Click "Upload to YouTube Shorts"
- Get direct link to published video

**Option B: Manual export for other platforms**
- Click "Copy File Path" to get local file location
- Clips are already formatted as 9:16 vertical MP4
- Upload manually to TikTok, Instagram Reels, VK Clips, etc.

## 🛠️ Technical Architecture

### Backend (Python + FastAPI)
- `backend/main.py` — FastAPI app with CORS and WebSocket
- `backend/config.py` — Workspace paths and settings
- `backend/db.py` — SQLite database (videos, moments, clips)
- `backend/services/` — Core logic:
  - `downloader.py` — yt-dlp wrapper
  - `scene_detector.py` — Audio energy + scene analysis
  - `speech_scorer.py` — faster-whisper + keyword scoring
  - `video_processor.py` — FFmpeg pipeline
  - `youtube_publisher.py` — YouTube Data API v3 upload
- `backend/api/` — REST + WebSocket endpoints

### Frontend (React + Vite + Tailwind)
- `frontend/src/pages/` — 5 workflow pages
- `frontend/src/components/` — Reusable UI components
- `frontend/src/store/` — Zustand global state
- Dark theme, responsive layout, real-time WebSocket updates

### Workspace Structure
```
workspace/
├── downloads/       # Downloaded source videos
├── output/          # Processed clips (ready to publish)
├── temp/            # Intermediate files (auto-cleaned)
└── clipforge.db     # SQLite database
```

## 🔍 Moment Detection Algorithm

100% local, no paid APIs:

1. **Audio Energy Analysis** (librosa)
   - RMS energy over time
   - Onset detection (sudden changes)
   - Score high-energy segments

2. **Scene Change Detection** (OpenCV)
   - Frame difference analysis
   - Count scene cuts per window
   - Score dynamic segments

3. **Speech Content Scoring** (faster-whisper + local keywords)
   - Transcribe audio locally
   - Detect questions, exclamations
   - Match emotion keywords (amazing, incredible, secret, etc.)
   - Measure speech pace variation
   - NO external LLM API calls

4. **Combined Scoring**
   - Weighted sum: 50% speech + 30% audio + 20% scene
   - Rank all 30-90s windows
   - Return top 15 non-overlapping moments

## 🐛 Troubleshooting

### FFmpeg not found
```bash
sudo apt-get install ffmpeg
```

### faster-whisper installation issues
Make sure you have Python 3.11+. On Ubuntu:
```bash
sudo apt-get install python3.11 python3.11-venv
```

### YouTube upload fails: "Quota exceeded"
Free tier quota: 10,000 units/day. Resets at midnight Pacific Time. If exceeded, wait until tomorrow or export locally and upload manually.

### Download fails: "Video not available"
- Check if the video is public (not private or geo-blocked)
- Try using a VPN if geo-restricted
- Ensure URL format is correct

### Whisper model download slow
First run downloads ~150MB model (base). This is one-time. Use smaller model for faster startup:
```bash
export WHISPER_MODEL=tiny  # or base, small, medium, large
./start.sh
```

## 📊 Performance

- **Moment detection**: 1-3 minutes for 30-minute video (depends on CPU)
- **Video processing**: 30-60 seconds per clip (with all effects)
- **YouTube upload**: 10-30 seconds per clip (depends on internet speed)

## 🤝 Contributing

This is a personal tool, but suggestions and bug reports welcome! Open an issue or submit a PR.

## 📜 License

MIT License — free to use, modify, and distribute.

## 🙏 Credits

Built with these amazing free & open-source tools:
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Video download
- [FFmpeg](https://ffmpeg.org/) — Video processing
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) — Speech-to-text
- [librosa](https://librosa.org/) — Audio analysis
- [OpenCV](https://opencv.org/) — Computer vision
- [FastAPI](https://fastapi.tiangolo.com/) — Web framework
- [React](https://react.dev/) — UI framework
- [Tailwind CSS](https://tailwindcss.com/) — Styling

---

**Made with ❤️ for content creators who want full control and zero API costs.**
