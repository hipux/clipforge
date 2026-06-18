# ClipForge 🎬

[🇷🇺 Русский](#russian) | [🇬🇧 English](#english)

---

<a name="russian"></a>
## 🇷🇺 Русская версия

> **💰 100% БЕСПЛАТНО — Никаких платных сервисов, подписок, стоимости API.**

Локальный инструмент для обработки и публикации видеоклипов. Скачивайте длинные видео с YouTube, Rutube или VK Video, автоматически находите интересные моменты с помощью локальных AI-моделей, применяйте профессиональные видеоэффекты и публикуйте готовые клипы прямо на YouTube Shorts — всё из одного веб-интерфейса, запущенного на вашем компьютере.

### ✨ Возможности

- **Скачивание видео** с YouTube, Rutube, VK Video (используя yt-dlp)
- **AI-определение интересных моментов** с помощью локального анализа:
  - Пики энергии аудио (librosa)
  - Определение смены сцен (OpenCV)
  - Оценка речевого контента (faster-whisper + эвристика)
- **Видеоэффекты** (FFmpeg):
  - Автоматические субтитры (faster-whisper AI) — 5 стилей на выбор
  - Динамический размытый фон (формат 9:16 вертикальный)
  - Зеркальное отображение
  - Тонкая коррекция цвета
  - Наложение баннера/водяного знака
- **Публикация**:
  - Прямая загрузка на YouTube Shorts (бесплатный YouTube Data API v3)
  - Локальный экспорт для TikTok, Instagram Reels, VK Клипы и т.д.
- **Сохранение сессии**: продолжайте работу с того места, где остановились (после перезагрузки страницы)

### 🆓 Гарантия нулевой стоимости

| Компонент | Инструмент | Стоимость |
|-----------|------------|-----------|
| Скачивание видео | yt-dlp | Бесплатно, открытый исходный код |
| Обработка видео | FFmpeg | Бесплатно, открытый исходный код |
| Распознавание речи | faster-whisper | Бесплатно, работает локально |
| Определение сцен | OpenCV + librosa | Бесплатно, работает локально |
| Оценка моментов | Локальный движок | Бесплатно, без внешних API |
| Публикация на YouTube | YouTube Data API v3 | **Бесплатный уровень (10K единиц/день)** |
| Бэкенд | Python + FastAPI | Бесплатно, открытый исходный код |
| Фронтенд | React + Vite + Tailwind | Бесплатно, открытый исходный код |
| База данных | SQLite | Бесплатно, открытый исходный код |

**Квота YouTube API:** 10 000 единиц/день бесплатно. Одна загрузка видео ≈ 1 600 единиц → **~6 видео/день бесплатно**. Идеально для личного использования!

### 🔧 Требования

- **Python 3.11+**
- **Node.js 18+**
- **FFmpeg** (устанавливается скриптом setup)
- **10+ ГБ свободного места** (для моделей Whisper и видеофайлов)

### 🪟 Запуск на Windows

ClipForge работает нативно в WSL2 (рекомендуется) или Git Bash:

**Вариант A: WSL2 (Рекомендуется)**
1. Установите WSL2: `wsl --install` в PowerShell (от имени Администратора)
2. Откройте терминал Ubuntu из меню Пуск
3. Клонируйте этот репозиторий и следуйте инструкциям установки для Linux ниже

**Вариант Б: Нативный Windows**
1. Установите Python 3.11+ с [python.org](https://www.python.org/downloads/)
2. Установите Node.js 18+ с [nodejs.org](https://nodejs.org/)
3. Установите FFmpeg: `winget install Gyan.FFmpeg` (или через [chocolatey](https://chocolatey.org/): `choco install ffmpeg`)
4. Используйте `setup.bat` вместо `setup.sh`
5. Используйте `start.bat` вместо `start.sh`

**Установка на Windows:**
```batch
setup.bat
```

**Запуск на Windows:**
```batch
start.bat
```

### 🚀 Быстрый старт

#### 1. Клонирование и установка

```bash
git clone https://github.com/hipux/clipforge.git
cd clipforge
chmod +x setup.sh start.sh
./setup.sh
```

Скрипт установки:
- Установит FFmpeg
- Создаст виртуальное окружение Python
- Установит все зависимости Python (включая faster-whisper)
- **Скачает AI-модель Whisper (~150МБ, один раз)** — затем работает полностью офлайн
- Установит зависимости фронтенда
- Создаст рабочие директории

#### 2. (Опционально) Настройка YouTube API

Для загрузки напрямую на YouTube Shorts (полностью бесплатно):

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект (платёжный аккаунт не требуется)
3. Включите **YouTube Data API v3**:
   - Перейдите в **APIs & Services → Library**
   - Найдите "YouTube Data API v3"
   - Нажмите **Enable**
4. Создайте учётные данные OAuth 2.0:
   - Перейдите в **APIs & Services → Credentials**
   - Нажмите **Create Credentials → OAuth 2.0 Client ID**
   - Настройте экран согласия (External, test mode)
   - Тип приложения: **Desktop app**
5. Скачайте `client_secrets.json` и поместите в корень проекта

**Первичная авторизация:** При первой загрузке видео ClipForge откроет окно браузера для авторизации вашего YouTube-аккаунта. Это одноразовая настройка.

#### 3. Запуск ClipForge

```bash
./start.sh
```

Запускает:
- Backend API на `http://localhost:8000`
- Frontend UI на `http://localhost:5173` (открывается автоматически)

### 📖 Руководство пользователя

#### Шаг 1: Скачивание видео

1. Вставьте URL видео (YouTube, Rutube или VK Video)
2. Нажмите "Download"
3. Дождитесь завершения загрузки (прогресс показывается в реальном времени)

#### Шаг 2: Определение моментов

1. Нажмите "Continue to Moments" или перейдите на вкладку Moments
2. AI автоматически определит 5-15 интересных моментов
3. Просмотрите кандидатов (оценка, таймкоды, причина)
4. Выберите клипы, которые хотите обработать

#### Шаг 3: Настройка эффектов

1. **Стиль субтитров**: выберите один из 5 стилей (Classic, Karaoke, Box, Outlined, Minimal)
2. **Видеоэффекты**: включите/выключите:
   - **Размытый фон**: динамический размытый фон (преобразует в вертикальный формат 9:16)
   - **Зеркало**: горизонтальное отражение
   - **Коррекция цвета**: тонкое усиление яркости/контраста
3. **Баннер/Водяной знак**: загрузите изображение и настройте позицию, размер, прозрачность
4. Эффекты применяются ко всем выбранным клипам

#### Шаг 4: Обработка

1. Нажмите "Start Processing"
2. Следите за прогрессом в реальном времени для каждого клипа
3. Все эффекты применяются за один проход FFmpeg (быстро!)

#### Шаг 5: Публикация

**Вариант A: YouTube Shorts (прямая загрузка)**
- Подключите ваш YouTube-аккаунт (одноразовая OAuth-авторизация)
- Заполните название и описание
- Нажмите "Upload to YouTube Shorts"
- Получите прямую ссылку на опубликованное видео

**Вариант Б: Ручной экспорт для других платформ**
- Нажмите "Copy File Path" чтобы получить путь к локальному файлу
- Клипы уже отформатированы как вертикальные MP4 9:16
- Загрузите вручную на TikTok, Instagram Reels, VK Клипы и т.д.

### 🐛 Устранение неполадок

#### FFmpeg не найден
```bash
sudo apt-get install ffmpeg
```

#### Проблемы с установкой faster-whisper
Убедитесь, что у вас Python 3.11+. На Ubuntu:
```bash
sudo apt-get install python3.11 python3.11-venv
```

#### Загрузка на YouTube не удалась: "Квота превышена"
Бесплатная квота: 10 000 единиц/день. Обновляется в полночь по тихоокеанскому времени. Если превышена, подождите до завтра или экспортируйте локально.

#### Скачивание не удалось: "Видео недоступно"
- Проверьте, является ли видео публичным (не приватное или с гео-блокировкой)
- Попробуйте использовать VPN если есть гео-ограничения
- Убедитесь, что формат URL правильный

#### Проблемы с моделью Whisper
Модель Whisper (~150МБ) скачивается **один раз при установке** и сохраняется в `workspace/models/whisper-base/`. После этого работает **100% офлайн** — никаких сетевых запросов.

Если установка не смогла скачать модель, она будет скачана при первом использовании. Для ручного скачивания:
```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-base', local_dir='workspace/models/whisper-base')"
```

#### Видео на нескольких языках / Неверное определение языка
Если вы работаете с видео на нескольких языках (например, русская озвучка с английскими песнями), Whisper может неправильно определить язык, что приведёт к некорректным субтитрам.

**Решение:** Принудительно задайте язык через переменную окружения `WHISPER_LANGUAGE`.

**На Windows** (в `start.bat`):
1. Откройте `start.bat` в текстовом редакторе
2. Раскомментируйте строку: `REM set WHISPER_LANGUAGE=ru`
3. Измените на: `set WHISPER_LANGUAGE=ru` (или `en` для английского)
4. Сохраните и запустите `start.bat`

**На Linux/Mac** (в терминале):
```bash
export WHISPER_LANGUAGE=ru  # или 'en' для английского
./start.sh
```

### 📊 Производительность

- **Определение моментов**: 1-3 минуты для 30-минутного видео (зависит от CPU)
- **Обработка видео**: 30-60 секунд на клип (со всеми эффектами)
- **Загрузка на YouTube**: 10-30 секунд на клип (зависит от скорости интернета)

### 📜 Лицензия

MIT License — свободно использовать, изменять и распространять.

### 🙏 Благодарности

Создано с помощью этих замечательных бесплатных инструментов с открытым исходным кодом:
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Скачивание видео
- [FFmpeg](https://ffmpeg.org/) — Обработка видео
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) — Распознавание речи
- [librosa](https://librosa.org/) — Анализ аудио
- [OpenCV](https://opencv.org/) — Компьютерное зрение
- [FastAPI](https://fastapi.tiangolo.com/) — Веб-фреймворк
- [React](https://react.dev/) — UI-фреймворк
- [Tailwind CSS](https://tailwindcss.com/) — Стилизация

---

**Сделано с ❤️ для создателей контента, которые хотят полного контроля и нулевых затрат на API.**

---

<a name="english"></a>
## 🇬🇧 English Version

> **💰 100% FREE — No paid services, no subscriptions, no API costs.**

Local video clip processing & publishing tool that lets you download long-form videos from YouTube, Rutube, or VK Video, automatically detect interesting moments using fully local AI models, apply professional video effects, and publish finished clips directly to YouTube Shorts — all from a single web interface running on your machine.

### ✨ Features

- **Video Download** from YouTube, Rutube, VK Video (using yt-dlp)
- **AI Moment Detection** using local analysis:
  - Audio energy peaks (librosa)
  - Scene change detection (OpenCV)
  - Speech content scoring (faster-whisper + keyword heuristics)
- **Video Effects** (FFmpeg):
  - Auto-generated subtitles (faster-whisper AI) — 5 styles to choose from
  - Dynamic blurred background (9:16 vertical format)
  - Mirror effect
  - Subtle color enhancement
  - Banner/watermark overlay
- **Publishing**:
  - Direct upload to YouTube Shorts (free YouTube Data API v3)
  - Local export for TikTok, Instagram Reels, VK Clips, etc.
- **Session Persistence**: Resume your work from where you left off (after page reload)

### 🆓 Zero-Cost Guarantee

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

### 🔧 Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **FFmpeg** (installed via setup script)
- **10+ GB free disk space** (for Whisper models and video files)

### 🪟 Running on Windows

ClipForge runs natively on WSL2 (recommended) or Git Bash:

**Option A: WSL2 (Recommended)**
1. Install WSL2: `wsl --install` in PowerShell (as Administrator)
2. Open the Ubuntu terminal from Start Menu
3. Clone this repo and follow the Linux setup instructions below

**Option B: Native Windows**
1. Install Python 3.11+ from [python.org](https://www.python.org/downloads/)
2. Install Node.js 18+ from [nodejs.org](https://nodejs.org/)
3. Install FFmpeg: `winget install Gyan.FFmpeg` (or via [chocolatey](https://chocolatey.org/): `choco install ffmpeg`)
4. Use `setup.bat` instead of `setup.sh`
5. Use `start.bat` instead of `start.sh`

**Windows setup:**
```batch
setup.bat
```

**Windows start:**
```batch
start.bat
```

### 🚀 Quick Start

#### 1. Clone and Setup

```bash
git clone https://github.com/hipux/clipforge.git
cd clipforge
chmod +x setup.sh start.sh
./setup.sh
```

The setup script will:
- Install FFmpeg
- Create Python virtual environment
- Install all Python dependencies (including faster-whisper)
- **Download Whisper AI model (~150MB, one-time)** — runs fully offline after this
- Install frontend dependencies
- Create workspace directories

#### 2. (Optional) YouTube API Setup

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
5. Download `client_secrets.json` and place in project root

**First-time auth:** When you first upload a video, ClipForge will open a browser window for you to authorize your YouTube account. This is a one-time setup.

#### 3. Start ClipForge

```bash
./start.sh
```

This starts:
- Backend API at `http://localhost:8000`
- Frontend UI at `http://localhost:5173` (opens automatically)

### 📖 Usage Guide

#### Step 1: Download Video

1. Paste a video URL (YouTube, Rutube, or VK Video)
2. Click "Download"
3. Wait for download to complete (progress shown in real-time)

#### Step 2: Detect Moments

1. Click "Continue to Moments" or navigate to Moments tab
2. AI automatically detects 5-15 interesting moments
3. Review candidates (score, timestamps, reason)
4. Select the clips you want (click to toggle)

#### Step 3: Configure Effects

1. **Subtitle Style**: Choose one of 5 styles (Classic, Karaoke, Box, Outlined, Minimal)
2. **Video Effects**: Toggle on/off:
   - **Blurred Background**: Dynamic blurred background (converts to 9:16 vertical)
   - **Mirror**: Horizontal flip
   - **Color Enhancement**: Subtle brightness/contrast boost
3. **Banner/Watermark**: Upload an image and configure position, size, opacity
4. Effects apply to all selected clips

#### Step 4: Process

1. Click "Start Processing"
2. Watch real-time progress for each clip
3. All effects applied in a single FFmpeg pass (fast!)

#### Step 5: Publish

**Option A: YouTube Shorts (direct upload)**
- Connect your YouTube account (one-time OAuth)
- Fill in title and description
- Click "Upload to YouTube Shorts"
- Get direct link to published video

**Option B: Manual export for other platforms**
- Click "Copy File Path" to get local file location
- Clips are already formatted as 9:16 vertical MP4
- Upload manually to TikTok, Instagram Reels, VK Clips, etc.

### 🐛 Troubleshooting

#### FFmpeg not found
```bash
sudo apt-get install ffmpeg
```

#### faster-whisper installation issues
Make sure you have Python 3.11+. On Ubuntu:
```bash
sudo apt-get install python3.11 python3.11-venv
```

#### YouTube upload fails: "Quota exceeded"
Free tier quota: 10,000 units/day. Resets at midnight Pacific Time. If exceeded, wait until tomorrow or export locally and upload manually.

#### Download fails: "Video not available"
- Check if the video is public (not private or geo-blocked)
- Try using a VPN if geo-restricted
- Ensure URL format is correct

#### Whisper model issues
The Whisper model (~150MB) is downloaded **once during setup** and stored in `workspace/models/whisper-base/`. After that, it runs **100% offline** — no network calls.

If setup failed to download the model, it will be downloaded on first use. To manually download:
```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-base', local_dir='workspace/models/whisper-base')"
```

#### Mixed-language videos / Wrong language detection
If you're working with videos that have mixed languages (e.g., Russian dubbing with English songs), Whisper may auto-detect the wrong language.

**Solution:** Force a specific language by setting the `WHISPER_LANGUAGE` environment variable.

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

- **Moment detection**: 1-3 minutes for 30-minute video (depends on CPU)
- **Video processing**: 30-60 seconds per clip (with all effects)
- **YouTube upload**: 10-30 seconds per clip (depends on internet speed)

### 📜 License

MIT License — free to use, modify, and distribute.

### 🙏 Credits

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
