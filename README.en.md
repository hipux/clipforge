# ClipForge 🎬

[🇷🇺 Русский](https://github.com/hipux/clipforge#readme) | [🇬🇧 English](https://github.com/hipux/clipforge/blob/main/README.en.md)

---

> **💰 100% FREE — No paid services, no subscriptions, no API costs.**

Local video clip processing & publishing tool that lets you download long-form videos from YouTube, Rutube, or VK Video, automatically detect interesting moments using fully local AI models, apply professional video effects, and publish finished clips directly to YouTube Shorts — all from a single web interface running on your machine.

### ✨ Features

- **Video Download** from YouTube, Rutube, VK Video (using yt-dlp)
- **AI Moment Detection** using local analysis:
  - Audio energy peaks (librosa)
  - Scene change detection (OpenCV)
  - Speech content scoring (faster-whisper + keyword heuristics)
- **Video Effects** (FFmpeg):
  - Auto-generated subtitles (faster-whisper AI) — 5 styles to choose from:
    - **Karaoke**: 1-2 words, yellow highlight on current word (TikTok style)
    - **Bold White**: 2-3 words, bold white text with thick outline
    - **Neon**: 1-2 words, cyan glow with dark semi-transparent box
    - **Minimal**: 3-4 words, small clean white text, thin outline
    - **Cinematic**: 2-3 words, letter-spacing, semi-transparent black bar
  - Dynamic blurred background (9:16 vertical format)
  - Mirror effect
  - Subtle color enhancement
  - Banner/watermark overlay
- **Publishing**:
  - Direct upload to YouTube Shorts (free YouTube Data API v3)
  - Local export for TikTok, Instagram Reels, VK Clips, etc.
- **Session Persistence**: Resume your work from where you left off (after page reload)

### 🆓 Zero Cost Guarantee

| Component | Tool | Cost |
|-----------|------|------|
| Video Download | yt-dlp | Free, open-source |
| Video Processing | FFmpeg | Free, open-source |
| Speech Recognition | faster-whisper | Free, runs locally (no cloud!) |
| Scene Detection | OpenCV + librosa + PySceneDetect | Free, runs locally |
| Moment Scoring | Local engine (heuristics) | Free, no external APIs |
| YouTube Publishing | YouTube Data API v3 | **Free tier (10,000 units/day)** |
| Backend | Python 3.11+ + FastAPI | Free, open-source |
| Frontend | React + Vite + Tailwind CSS | Free, open-source |
| Database | SQLite | Free, open-source |

**YouTube API Quota:** 10,000 units/day for free. One video upload ≈ 1,600 units → **~6 videos/day free**. Perfect for personal use!

### 🖥️ System Requirements

#### Minimum Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **OS** | Windows 10 / Ubuntu 20.04 / macOS 12 | Windows 11 / Ubuntu 22.04+ |
| **CPU** | 4 cores, 2.0 GHz | 8 cores, 3.0+ GHz |
| **RAM** | 8 GB | 16 GB |
| **GPU** | Not required | NVIDIA with CUDA (for faster Whisper) |
| **Free disk space** | 10 GB | 30+ GB |
| **Internet** | Required for downloading and publishing | — |

#### Software Dependencies

- **Python 3.11+** (for backend)
- **Node.js 18+** (for frontend)
- **FFmpeg** (installed and available in PATH)
  - On macOS: `brew install ffmpeg`
  - On Ubuntu/Debian: `sudo apt install ffmpeg`
  - On Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)
- **Git** (to clone the repository)
- **YouTube Data API v3 credentials** (optional, only for direct YouTube upload)

#### Supported Operating Systems

| OS | Status |
|----|--------|
| Windows 10 / 11 | ✅ Supported (native and WSL2) |
| Ubuntu / Debian | ✅ Supported |
| macOS 12+ | ⚠️ Not officially tested, should work |

#### GPU Acceleration (Optional)

> Without GPU, everything runs on CPU — just slower. Whisper Base processes ~1 min of video in ~30 sec on a modern CPU.

To enable NVIDIA GPU acceleration:
1. Install [CUDA Toolkit 11.8+](https://developer.nvidia.com/cuda-downloads)
2. Install PyTorch with CUDA:
   ```bash
   pip install torch --index-url https://download.pytorch.org/whl/cu118
   ```
3. ClipForge will automatically detect and use the GPU

### 🪟 Running on Windows

**Option 1: Use WSL2 (recommended)**
1. Install WSL2 with Ubuntu: `wsl --install`
2. Inside WSL2, follow the Linux instructions below

**Option 2: Native Windows**
1. Install Python 3.11+ from [python.org](https://www.python.org/downloads/)
2. Install Node.js 18+ from [nodejs.org](https://nodejs.org/)
3. Install FFmpeg:
   - Download from [ffmpeg.org](https://ffmpeg.org/download.html#build-windows)
   - Extract to `C:\ffmpeg`
   - Add `C:\ffmpeg\bin` to System PATH
   - Verify: `ffmpeg -version` in cmd
4. Clone the repository: `git clone https://github.com/hipux/clipforge.git`
5. Run `setup.bat` (installs dependencies)
6. Run `start.bat` (starts backend + frontend)
7. Open http://localhost:5173

### 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/hipux/clipforge.git
cd clipforge

# 2. Install dependencies (backend + frontend)
./setup.sh  # or setup.bat on Windows

# 3. (Optional) Configure YouTube API
cp .env.example backend/.env
# Edit backend/.env and add your credentials
# (see YouTube API setup below)

# 4. Start the application
./start.sh  # or start.bat on Windows

# The app will open at http://localhost:5173
# Backend API at http://localhost:8000
```

### 🔑 YouTube API Setup (Optional)

To publish clips directly to YouTube Shorts, you need YouTube Data API v3 credentials.

**1. Create a Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project (or select an existing one)
   - Enable **YouTube Data API v3** for this project

**2. Create OAuth 2.0 Credentials**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Application type: **Desktop app**
   - Name: `ClipForge` (or any name)
   - Download the JSON file

**3. Configure ClipForge**
   - Rename the downloaded file to `client_secret.json`
   - Place it in `backend/` directory
   - Or use `.env` file (see `.env.example`)

**4. First Launch**
   - When you first click "Upload to YouTube" in ClipForge:
     - A browser window will open asking you to authorize
     - Sign in with your YouTube account
     - Grant permissions
     - Copy the authorization code and paste it in ClipForge
   - The token will be saved in `backend/token.json` for future use

### 📖 User Guide

#### 1. Download Video
   - Paste a link from YouTube, Rutube, or VK Video
   - Click "Download"
   - The video will be saved locally

#### 2. Find Moments
   - ClipForge will analyze the video using local AI:
     - Audio energy peaks (loud moments, music drops)
     - Scene changes (visual cuts)
     - Speech content (interesting words)
   - Review the automatically detected moments
   - Select the ones you want to turn into clips

#### 3. Configure Effects
   - **Subtitles**: Auto-generated from speech (5 styles available)
     - **Karaoke**: TikTok-style word-by-word yellow highlight
     - **Bold White**: Classic bold white text with black outline
     - **Neon**: Cyan glow with dark semi-transparent background
     - **Minimal**: Small, clean, unobtrusive white text
     - **Cinematic**: Spaced letters on semi-transparent black bar
   - **Blurred Background**: Vertical 9:16 format with strong blur (Shorts-ready)
   - **Banner/Watermark**: Upload your logo/brand image (PNG/JPG), adjust position and size
   - **Mirror Effect**: Horizontal flip for creative look
   - **Color Correction**: Subtle enhancement (+1% brightness, +1% contrast, +2% saturation)

#### 4. Process Clips
   - ClipForge will render all selected clips with chosen effects
   - Progress is shown in real-time
   - All processing happens locally on your machine

#### 5. Publish
   - **YouTube Shorts**: Direct upload with custom title/description
   - **Manual Export**: Copy local file path and upload to any platform (TikTok, Instagram Reels, VK Clips, etc.)

### 🐛 Troubleshooting

#### FFmpeg not found
**Error:** `FFmpeg is not installed or not in PATH`

**Solution:**
- **macOS**: `brew install ffmpeg`
- **Ubuntu/Debian**: `sudo apt install ffmpeg`
- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
- Verify installation: `ffmpeg -version`

#### Python version too old
**Error:** `Python 3.11+ required`

**Solution:**
- **macOS**: `brew install python@3.11`
- **Ubuntu/Debian**: `sudo apt install python3.11`
- **Windows**: Download from [python.org](https://www.python.org/downloads/)
- Verify: `python3 --version` or `python --version`

#### Port already in use
**Error:** `Address already in use: 8000` or `5173`

**Solution:**
```bash
# Find process using the port
lsof -i :8000  # or :5173
# Kill the process
kill -9 <PID>
# Or change the port in start.sh / start.bat
```

#### YouTube authentication failed
**Error:** `Invalid client_secret.json` or `OAuth error`

**Solution:**
1. Verify `client_secret.json` is in `backend/` directory
2. Check that YouTube Data API v3 is enabled in Google Cloud Console
3. Ensure the OAuth client type is "Desktop app" (not "Web application")
4. Delete `backend/token.json` and re-authorize

#### Whisper model download
If this is your first time using faster-whisper, the model will be downloaded automatically on first use. To manually download:
```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-base', local_dir='workspace/models/whisper-base')"
```

#### Multi-language videos / Wrong language detection
If you're working with multi-language videos (e.g., Russian voiceover with English songs), Whisper may incorrectly detect the language, leading to wrong subtitles.

**Solution:** Force the language via `WHISPER_LANGUAGE` environment variable.

**On Windows** (in `start.bat`):
1. Open `start.bat` in a text editor
2. Uncomment the line: `REM set WHISPER_LANGUAGE=ru`
3. Change to: `set WHISPER_LANGUAGE=ru` (or `en` for English)
4. Save and run `start.bat`

**On Linux/Mac** (in terminal):
```bash
export WHISPER_LANGUAGE=ru  # or 'en' for English
./start.sh
```

### 📊 Performance

- **Moment Detection**: 1-3 minutes for a 30-minute video (depends on CPU)
- **Video Processing**: 30-60 seconds per clip (with all effects)
- **YouTube Upload**: 10-30 seconds per clip (depends on internet speed)

### 📜 License

MIT License — free to use, modify, and distribute.

### 🙏 Acknowledgements

Built with these amazing free open-source tools:
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Video download
- [FFmpeg](https://ffmpeg.org/) — Video processing
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) — Speech recognition
- [librosa](https://librosa.org/) — Audio analysis
- [OpenCV](https://opencv.org/) — Computer vision
- [FastAPI](https://fastapi.tiangolo.com/) — Web framework
- [React](https://react.dev/) — UI framework
- [Tailwind CSS](https://tailwindcss.com/) — Styling

---

**Made with ❤️ for content creators who want full control and zero API costs.**
