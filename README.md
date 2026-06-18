# ClipForge 🎬

[🇷🇺 Русский](#russian) | [🇬🇧 English](#english)

<a name="russian"></a>

---

> **💰 100% БЕСПЛАТНО — Никаких платных сервисов, подписок, стоимости API.**

Локальный инструмент для обработки и публикации видеоклипов. Скачивайте длинные видео с YouTube, Rutube или VK Video, автоматически находите интересные моменты с помощью локальных AI-моделей, применяйте профессиональные видеоэффекты (субтитры, размытый фон, баннеры, зеркальное отображение, цветокоррекцию) и публикуйте готовые клипы прямо на YouTube Shorts — всё из одного веб-интерфейса, запущенного на вашем компьютере.

## ✨ Возможности

- **Скачивание видео** с YouTube, Rutube, VK Video (используя yt-dlp)
- **AI-определение интересных моментов** с помощью локального анализа (100% бесплатно):
  - Пики энергии аудио (librosa)
  - Определение смены сцен (OpenCV + PySceneDetect)
  - Оценка речевого контента (faster-whisper + эвристика)
- **Видеоэффекты** (FFmpeg):
  - **Автоматические субтитры** (faster-whisper AI, работает локально) — **5 стилей на выбор**:
    - **Karaoke**: 1-2 слова, жёлтая подсветка текущего слова (стиль TikTok)
    - **Bold White**: 2-3 слова, жирный белый текст с толстой обводкой
    - **Neon**: 1-2 слова, голубое свечение с тёмной полупрозрачной рамкой
    - **Minimal**: 3-4 слова, небольшой чистый белый текст, тонкая обводка
    - **Cinematic**: 2-3 слова, буквенный интервал, полупрозрачная чёрная полоса
  - **Динамический размытый фон** (формат 9:16 вертикальный, сильное размытие)
  - **Наложение баннера/водяного знака** (загрузите PNG/JPG, настройте позицию и размер)
  - **Зеркальное отображение** (горизонтальный flip)
  - **Тонкая коррекция цвета** (+1% яркость, +1% контраст, +2% насыщенность)
- **Публикация**:
  - Прямая загрузка на **YouTube Shorts** (бесплатный YouTube Data API v3)
  - Локальный экспорт для TikTok, Instagram Reels, VK Клипы и т.д.
- **Сохранение сессии**: продолжайте работу с того места, где остановились (после перезагрузки страницы)

## 🆓 Гарантия нулевой стоимости

| Компонент | Инструмент | Стоимость |
|-----------|------------|-----------|
| Скачивание видео | yt-dlp | Бесплатно, открытый исходный код |
| Обработка видео | FFmpeg | Бесплатно, открытый исходный код |
| Распознавание речи | faster-whisper | Бесплатно, работает локально (без облака!) |
| Определение сцен | OpenCV + librosa + PySceneDetect | Бесплатно, работает локально |
| Оценка моментов | Локальный движок (эвристика) | Бесплатно, без внешних API |
| Публикация на YouTube | YouTube Data API v3 | **Бесплатный уровень (10,000 единиц/день)** |
| Бэкенд | Python 3.11+ + FastAPI | Бесплатно, открытый исходный код |
| Фронтенд | React + Vite + Tailwind CSS | Бесплатно, открытый исходный код |
| База данных | SQLite | Бесплатно, открытый исходный код |

**Квота YouTube API:** 10,000 единиц/день бесплатно. Одна загрузка видео ≈ 1,600 единиц → **~6 видео/день бесплатно**. Идеально для личного использования!

## 🔧 Требования

- **Python 3.11+** (для бэкенда)
- **Node.js 18+** (для фронтенда)
- **FFmpeg** (устанавливается автоматически скриптом `setup.bat`)
- **10+ ГБ свободного места** (для моделей Whisper и видеофайлов)
- **Windows 10/11** или **Linux** (MacOS не тестировалась, но должна работать)

## 🪟 Запуск на Windows

ClipForge работает нативно в WSL2 (рекомендуется) или Git Bash. Ниже инструкции для **нативного Windows** (самый простой способ).

### Вариант A: Нативный Windows (Рекомендуется для начинающих)

1. **Установите Python 3.11+** с [python.org](https://www.python.org/downloads/)
   - ⚠️ **Важно**: При установке отметьте галочку **"Add Python to PATH"**
2. **Установите Node.js 18+** с [nodejs.org](https://nodejs.org/)
3. **Установите FFmpeg**:
   - **Через winget** (Windows 10 1809+): Откройте PowerShell и выполните:
     ```powershell
     winget install Gyan.FFmpeg
     ```
   - **Или через chocolatey**: Если у вас установлен [Chocolatey](https://chocolatey.org/):
     ```powershell
     choco install ffmpeg
     ```
   - **Вручную**: Скачайте с [ffmpeg.org](https://ffmpeg.org/download.html), распакуйте и добавьте в PATH
4. **Клонируйте репозиторий** (используйте Git Bash или PowerShell):
   ```bash
   git clone https://github.com/hipux/clipforge.git
   cd clipforge
   ```
5. **Запустите установку**:
   ```batch
   setup.bat
   ```
   Этот скрипт:
   - Создаст виртуальное окружение Python
   - Установит все зависимости Python (faster-whisper, FFmpeg-python, FastAPI и т.д.)
   - Установит зависимости фронтенда (React, Vite, Tailwind)
   - Скачает модель Whisper (базовая модель `base`, ~150 МБ)

6. **Запустите приложение**:
   ```batch
   start.bat
   ```
   Этот скрипт:
   - Запустит бэкенд FastAPI на `http://localhost:8000`
   - Запустит фронтенд Vite dev server на `http://localhost:5173`
   - Автоматически откроет браузер

7. **Откройте в браузере**: `http://localhost:5173`

### Вариант Б: WSL2 (Для продвинутых пользователей)

1. Установите WSL2: выполните в PowerShell (от имени Администратора):
   ```powershell
   wsl --install
   ```
2. Откройте терминал Ubuntu из меню Пуск
3. Следуйте инструкциям для Linux ниже

## 🐧 Запуск на Linux

```bash
# Клонирование репозитория
git clone https://github.com/hipux/clipforge.git
cd clipforge

# Сделать скрипты исполняемыми
chmod +x setup.sh start.sh

# Установка (Python, Node, FFmpeg, зависимости)
./setup.sh

# Запуск
./start.sh
```

Откройте в браузере: `http://localhost:5173`

## 🚀 Быстрый старт

### 1. Скачивание видео
- Откройте `http://localhost:5173`
- Вставьте ссылку на видео с YouTube, Rutube или VK Video
- Нажмите **"Download"**
- Дождитесь завершения (прогресс отображается в реальном времени)

### 2. Определение интересных моментов
- После загрузки нажмите **"Detect Moments"**
- AI проанализирует видео и найдёт 5-15 кандидатов (30-90 секунд каждый)
- Просмотрите список моментов с превью
- Выберите те, которые хотите обработать (галочки)
- Нажмите **"Next: Effects"**

### 3. Настройка эффектов
- **Стиль субтитров**: выберите один из 5 стилей (Karaoke, Bold White, Neon, Minimal, Cinematic)
- **Видеоэффекты**: включите/выключите:
  - Blurred Background (размытый фон 9:16)
  - Mirror Effect (зеркало)
  - Color Enhancement (цветокоррекция)
- **Баннер/водяной знак**:
  - Загрузите PNG/JPG (до 5 МБ)
  - Выберите позицию (верх/низ, лево/центр/право)
  - Настройте размер и прозрачность
- Нажмите **"Next: Process"**

### 4. Обработка клипов
- Нажмите **"Process All Clips"**
- Прогресс показывается для каждого клипа
- Обработка занимает ~30-60 секунд на клип (зависит от эффектов)
- После завершения нажмите **"Next: Publish"**

### 5. Публикация на YouTube Shorts или экспорт
- **Для YouTube Shorts**:
  - Нажмите **"Connect YouTube Account"** (первый раз)
  - Авторизуйтесь через OAuth (бесплатно, без платного аккаунта Google Cloud)
  - Для каждого клипа введите название, описание, теги
  - Выберите приватность (Public / Unlisted / Private)
  - Нажмите **"Upload to YouTube"**
  - Готово! Получите ссылку на опубликованное видео
- **Для TikTok / Instagram Reels / VK Клипы**:
  - Клипы уже сохранены локально в `workspace/output/`
  - Нажмите **"Open Output Folder"** чтобы открыть папку
  - Перетащите файлы в TikTok/Instagram/VK вручную

## 📁 Структура проекта

```
clipforge/
├── backend/                 # Python FastAPI бэкенд
│   ├── api/                 # REST API маршруты
│   │   ├── download.py      # POST /api/download (скачивание видео)
│   │   ├── moments.py       # POST /api/moments/detect (AI-определение моментов)
│   │   ├── process.py       # POST /api/process (обработка клипов)
│   │   ├── publish.py       # POST /api/publish/youtube (публикация)
│   │   ├── session.py       # GET /api/session/current (восстановление сессии)
│   │   ├── upload.py        # POST /api/upload/banner (загрузка баннера)
│   │   └── ws_router.py     # WebSocket для прогресса
│   ├── services/
│   │   ├── downloader.py    # yt-dlp обёртка
│   │   ├── scene_detector.py # PySceneDetect + librosa
│   │   ├── speech_scorer.py  # faster-whisper (транскрибация, субтитры, скоринг)
│   │   ├── video_processor.py # FFmpeg pipeline (эффекты, субтитры, баннеры)
│   │   └── youtube_publisher.py # YouTube Data API v3
│   ├── config.py            # Настройки, пути
│   ├── db.py                # SQLite база данных
│   ├── models.py            # Pydantic модели
│   └── main.py              # Точка входа FastAPI
├── frontend/                # React + Vite фронтенд
│   ├── src/
│   │   ├── components/      # React компоненты (EffectToggle, BannerUpload, SubtitleStylePicker и т.д.)
│   │   ├── pages/           # Страницы (DownloadPage, MomentsPage, EffectsPage, ProcessPage, PublishPage)
│   │   ├── store/           # Zustand хранилище (useAppStore.ts — с persist middleware)
│   │   └── App.tsx          # Основной компонент приложения
│   ├── package.json
│   └── vite.config.ts
├── workspace/               # Рабочая директория (создаётся автоматически)
│   ├── downloads/           # Скачанные исходные видео
│   ├── output/              # Обработанные клипы (готовые к публикации)
│   ├── banners/             # Загруженные баннеры/водяные знаки
│   ├── models/              # Модели Whisper (скачиваются один раз)
│   └── clipforge.db         # SQLite база данных
├── setup.bat / setup.sh     # Скрипты установки
├── start.bat / start.sh     # Скрипты запуска
├── requirements.txt         # Python зависимости
└── README.md                # Этот файл
```

## 🔄 Обновление до последней версии

Если вы уже установили ClipForge и хотите обновиться до последней версии:

```bash
# Перейдите в папку проекта
cd clipforge

# Скачайте последние изменения с GitHub
git fetch origin
git reset --hard origin/main

# Переустановите зависимости (на случай новых пакетов)
# Windows:
setup.bat

# Linux:
./setup.sh

# Готово! Запустите как обычно:
# Windows:
start.bat

# Linux:
./start.sh
```

⚠️ **Внимание**: `git reset --hard origin/main` удалит все ваши локальные изменения в коде. Ваши видео и обработанные клипы в папке `workspace/` **не будут затронуты**.

## 🔑 Настройка YouTube API (для публикации на YouTube Shorts)

YouTube API **полностью бесплатен** для личного использования (квота 10,000 единиц/день = ~6 видео/день).

### Шаги настройки (5 минут):

1. **Перейдите в [Google Cloud Console](https://console.cloud.google.com/)**
   - Войдите с вашим Google аккаунтом
2. **Создайте новый проект**:
   - Кликните "Select a project" → "New Project"
   - Название: `ClipForge` (любое)
   - Нажмите "Create"
3. **Включите YouTube Data API v3**:
   - Перейдите в **APIs & Services → Library**
   - Найдите "YouTube Data API v3"
   - Нажмите **Enable**
4. **Создайте OAuth 2.0 Client ID**:
   - Перейдите в **APIs & Services → Credentials**
   - Нажмите **Create Credentials → OAuth 2.0 Client ID**
   - Если просит настроить OAuth consent screen:
     - User Type: **External**
     - App name: `ClipForge`
     - User support email: ваш email
     - Developer contact: ваш email
     - Scopes: оставьте пустым
     - Test users: добавьте свой Google email
     - Нажмите **Save and Continue** до конца
   - Application type: **Desktop app**
   - Name: `ClipForge Desktop`
   - Нажмите **Create**
5. **Скачайте `client_secret.json`**:
   - Нажмите кнопку **Download JSON** рядом с созданным Client ID
   - Переименуйте файл в `client_secret.json`
   - **Поместите его в корень папки `clipforge/`** (рядом с `setup.bat`)
6. **Готово!** При первой публикации видео приложение откроет браузер для авторизации. Авторизуйтесь один раз — токен сохранится локально.

**Примечание**: Вам **не нужен** платный аккаунт Google Cloud Platform. Бесплатная квота более чем достаточна для личного использования.

## 🛠️ Устранение неполадок

### Проблема: `ModuleNotFoundError: No module named 'faster_whisper'`
**Решение**: Запустите `setup.bat` / `setup.sh` повторно. Возможно, установка Python зависимостей не завершилась.

### Проблема: `FFmpeg not found`
**Решение**:
- **Windows**: Установите FFmpeg через `winget install Gyan.FFmpeg` или скачайте вручную и добавьте в PATH
- **Linux**: `sudo apt install ffmpeg` (Ubuntu/Debian) или `sudo yum install ffmpeg` (CentOS/RHEL)
- После установки перезапустите терминал и проверьте: `ffmpeg -version`

### Проблема: WebSocket connection failed / 403 Forbidden
**Решение**: Эта проблема была исправлена в последней версии. Выполните обновление (см. раздел **Обновление**).

### Проблема: Язык субтитров определяется неправильно
**Решение**:
- Откройте `.env.example`, скопируйте его в `.env`
- Добавьте строку: `WHISPER_LANGUAGE=ru` (или `en`, `es`, и т.д.)
- Это принудительно установит язык для всех видео

### Проблема: Скачивание видео с YouTube не работает (yt-dlp warning)
**Решение**:
- Обновите yt-dlp: откройте терминал в папке `clipforge` и выполните:
  ```bash
  # Windows:
  venv\Scripts\python.exe -m pip install --upgrade yt-dlp

  # Linux:
  ./venv/bin/python -m pip install --upgrade yt-dlp
  ```

### Проблема: Приложение не открывается в браузере
**Решение**:
- Проверьте, что порты 8000 и 5173 свободны (не используются другими приложениями)
- Вручную откройте в браузере: `http://localhost:5173`
- Проверьте логи в консоли — возможно, бэкенд или фронтенд не запустились

### Проблема: "Low confidence language detection" для видео с дубляжом (русский + английский)
**Это нормально**. Для видео со смешанными языками (например, русская озвучка + приглушенный английский оригинал):
- Whisper может определить язык с низкой уверенностью
- ClipForge автоматически использует русский язык по умолчанию в таких случаях
- Если хотите принудительно установить язык, добавьте `WHISPER_LANGUAGE=ru` в `.env` (см. выше)

### Проблема: Сессия не восстанавливается после перезагрузки страницы
**Решение**: Сессия сохраняется в localStorage браузера. Если вы очистили кэш браузера, сессия будет потеряна. Также убедитесь, что вы используете последнюю версию (см. раздел **Обновление**).

## 📊 Использование памяти и производительность

- **Модель Whisper (base)**: ~500 МБ RAM при обработке
- **FFmpeg обработка**: ~1-2 ГБ RAM на клип (зависит от длины и эффектов)
- **Скорость обработки**:
  - Определение моментов: ~5-10 минут на 1 час исходного видео
  - Обработка клипов: ~30-60 секунд на клип (зависит от количества эффектов)
- **GPU ускорение**: Не требуется (всё работает на CPU). Если у вас NVIDIA GPU и установлен CUDA, Whisper автоматически использует GPU.

## 🤝 Вклад в проект

Проект находится в активной разработке. Если вы нашли баг или у вас есть идея для улучшения:
- Откройте **Issue** на GitHub: [https://github.com/hipux/clipforge/issues](https://github.com/hipux/clipforge/issues)
- Или отправьте **Pull Request**

## 📄 Лицензия

Этот проект использует только **открытые и бесплатные** компоненты:
- ClipForge код: MIT License (свободно используйте, изменяйте, распространяйте)
- FFmpeg: LGPL / GPL (бесплатно для личного использования)
- faster-whisper: MIT License
- yt-dlp: Unlicense (публичное достояние)
- PySceneDetect: BSD License
- librosa: ISC License

---

<a name="english"></a>

---

# ClipForge 🎬

[🇷🇺 Русский](#russian) | [🇬🇧 English](#english)

> **💰 100% FREE — No paid services, no subscriptions, no API costs.**

A local, browser-based tool for downloading long-form videos from Rutube, YouTube, or VK Video, automatically detecting interesting moments using fully local AI models, applying professional video processing effects (subtitles, blurred background, banner overlay, mirror, color correction), and publishing finished short-form clips directly to YouTube Shorts — all from a single web interface running on your machine.

## ✨ Features

- **Video download** from YouTube, Rutube, VK Video (using yt-dlp)
- **AI-powered moment detection** using 100% local analysis (completely free):
  - Audio energy peaks (librosa)
  - Scene change detection (OpenCV + PySceneDetect)
  - Speech content scoring (faster-whisper + heuristic analysis)
- **Video effects** (FFmpeg):
  - **Auto-generated subtitles** (faster-whisper AI, runs locally) — **5 styles to choose from**:
    - **Karaoke**: 1-2 words, yellow highlight on current word (TikTok style)
    - **Bold White**: 2-3 words, bold white text with thick outline
    - **Neon**: 1-2 words, cyan glow with dark semi-transparent box
    - **Minimal**: 3-4 words, small clean white text, subtle outline
    - **Cinematic**: 2-3 words, letter-spaced text, semi-transparent black bar
  - **Dynamic blurred background** (9:16 vertical format, strong blur)
  - **Banner/watermark overlay** (upload PNG/JPG, configure position & size)
  - **Mirror effect** (horizontal flip)
  - **Subtle color correction** (+1% brightness, +1% contrast, +2% saturation)
- **Publishing**:
  - Direct upload to **YouTube Shorts** (free YouTube Data API v3)
  - Local export for TikTok, Instagram Reels, VK Clips, etc.
- **Session persistence**: Resume your work from where you left off (survives page reload)

## 🆓 Zero-Cost Guarantee

| Component | Tool | Cost |
|-----------|------|------|
| Video download | yt-dlp | Free, open-source |
| Video processing | FFmpeg | Free, open-source |
| Speech-to-text | faster-whisper | Free, runs locally (no cloud!) |
| Scene detection | OpenCV + librosa + PySceneDetect | Free, runs locally |
| Moment scoring | Local heuristic engine | Free, no external APIs |
| YouTube publishing | YouTube Data API v3 | **Free tier (10,000 units/day)** |
| Backend | Python 3.11+ + FastAPI | Free, open-source |
| Frontend | React + Vite + Tailwind CSS | Free, open-source |
| Database | SQLite | Free, open-source |

**YouTube API Quota:** 10,000 units/day free. One video upload ≈ 1,600 units → **~6 videos/day free**. Perfect for personal use!

## 🔧 Requirements

- **Python 3.11+** (for backend)
- **Node.js 18+** (for frontend)
- **FFmpeg** (installed automatically by `setup.bat` / `setup.sh`)
- **10+ GB free disk space** (for Whisper models and video files)
- **Windows 10/11** or **Linux** (macOS not tested, but should work)

## 🪟 Running on Windows

ClipForge works natively on Windows (easiest) or in WSL2. Below are instructions for **native Windows** (recommended for beginners).

### Option A: Native Windows (Recommended for Beginners)

1. **Install Python 3.11+** from [python.org](https://www.python.org/downloads/)
   - ⚠️ **Important**: Check the box **"Add Python to PATH"** during installation
2. **Install Node.js 18+** from [nodejs.org](https://nodejs.org/)
3. **Install FFmpeg**:
   - **Via winget** (Windows 10 1809+): Open PowerShell and run:
     ```powershell
     winget install Gyan.FFmpeg
     ```
   - **Or via chocolatey**: If you have [Chocolatey](https://chocolatey.org/) installed:
     ```powershell
     choco install ffmpeg
     ```
   - **Manually**: Download from [ffmpeg.org](https://ffmpeg.org/download.html), extract, and add to PATH
4. **Clone the repository** (using Git Bash or PowerShell):
   ```bash
   git clone https://github.com/hipux/clipforge.git
   cd clipforge
   ```
5. **Run setup**:
   ```batch
   setup.bat
   ```
   This script will:
   - Create a Python virtual environment
   - Install all Python dependencies (faster-whisper, FFmpeg-python, FastAPI, etc.)
   - Install frontend dependencies (React, Vite, Tailwind)
   - Download the Whisper model (base model, ~150 MB)

6. **Start the application**:
   ```batch
   start.bat
   ```
   This script will:
   - Start the FastAPI backend on `http://localhost:8000`
   - Start the Vite dev server on `http://localhost:5173`
   - Automatically open your browser

7. **Open in browser**: `http://localhost:5173`

### Option B: WSL2 (For Advanced Users)

1. Install WSL2: run in PowerShell (as Administrator):
   ```powershell
   wsl --install
   ```
2. Open the Ubuntu terminal from the Start menu
3. Follow the Linux instructions below

## 🐧 Running on Linux

```bash
# Clone the repository
git clone https://github.com/hipux/clipforge.git
cd clipforge

# Make scripts executable
chmod +x setup.sh start.sh

# Install (Python, Node, FFmpeg, dependencies)
./setup.sh

# Start
./start.sh
```

Open in browser: `http://localhost:5173`

## 🚀 Quick Start

### 1. Download Video
- Open `http://localhost:5173`
- Paste a video URL from YouTube, Rutube, or VK Video
- Click **"Download"**
- Wait for completion (progress is shown in real-time)

### 2. Detect Interesting Moments
- After download, click **"Detect Moments"**
- AI will analyze the video and find 5-15 candidates (30-90 seconds each)
- Review the list of moments with thumbnails
- Select the ones you want to process (checkboxes)
- Click **"Next: Effects"**

### 3. Configure Effects
- **Subtitle Style**: Choose one of 5 styles (Karaoke, Bold White, Neon, Minimal, Cinematic)
- **Video Effects**: Toggle on/off:
  - Blurred Background (9:16 blur)
  - Mirror Effect (horizontal flip)
  - Color Enhancement (color correction)
- **Banner/Watermark**:
  - Upload PNG/JPG (up to 5 MB)
  - Choose position (top/bottom, left/center/right)
  - Adjust size and opacity
- Click **"Next: Process"**

### 4. Process Clips
- Click **"Process All Clips"**
- Progress is shown for each clip
- Processing takes ~30-60 seconds per clip (depends on effects)
- After completion, click **"Next: Publish"**

### 5. Publish to YouTube Shorts or Export
- **For YouTube Shorts**:
  - Click **"Connect YouTube Account"** (first time only)
  - Authorize via OAuth (free, no paid Google Cloud account needed)
  - For each clip, enter title, description, tags
  - Choose privacy (Public / Unlisted / Private)
  - Click **"Upload to YouTube"**
  - Done! Get the link to your published video
- **For TikTok / Instagram Reels / VK Clips**:
  - Clips are already saved locally in `workspace/output/`
  - Click **"Open Output Folder"** to open the folder
  - Drag-and-drop files into TikTok/Instagram/VK manually

## 📁 Project Structure

```
clipforge/
├── backend/                 # Python FastAPI backend
│   ├── api/                 # REST API routes
│   │   ├── download.py      # POST /api/download (video download)
│   │   ├── moments.py       # POST /api/moments/detect (AI moment detection)
│   │   ├── process.py       # POST /api/process (clip processing)
│   │   ├── publish.py       # POST /api/publish/youtube (publishing)
│   │   ├── session.py       # GET /api/session/current (session restore)
│   │   ├── upload.py        # POST /api/upload/banner (banner upload)
│   │   └── ws_router.py     # WebSocket for progress updates
│   ├── services/
│   │   ├── downloader.py    # yt-dlp wrapper
│   │   ├── scene_detector.py # PySceneDetect + librosa
│   │   ├── speech_scorer.py  # faster-whisper (transcription, subtitles, scoring)
│   │   ├── video_processor.py # FFmpeg pipeline (effects, subtitles, banners)
│   │   └── youtube_publisher.py # YouTube Data API v3
│   ├── config.py            # Settings, paths
│   ├── db.py                # SQLite database
│   ├── models.py            # Pydantic models
│   └── main.py              # FastAPI entry point
├── frontend/                # React + Vite frontend
│   ├── src/
│   │   ├── components/      # React components (EffectToggle, BannerUpload, SubtitleStylePicker, etc.)
│   │   ├── pages/           # Pages (DownloadPage, MomentsPage, EffectsPage, ProcessPage, PublishPage)
│   │   ├── store/           # Zustand store (useAppStore.ts — with persist middleware)
│   │   └── App.tsx          # Main app component
│   ├── package.json
│   └── vite.config.ts
├── workspace/               # Working directory (created automatically)
│   ├── downloads/           # Downloaded source videos
│   ├── output/              # Processed clips (ready for publishing)
│   ├── banners/             # Uploaded banners/watermarks
│   ├── models/              # Whisper models (downloaded once)
│   └── clipforge.db         # SQLite database
├── setup.bat / setup.sh     # Setup scripts
├── start.bat / start.sh     # Start scripts
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

## 🔄 Updating to the Latest Version

If you've already installed ClipForge and want to update to the latest version:

```bash
# Navigate to the project folder
cd clipforge

# Fetch the latest changes from GitHub
git fetch origin
git reset --hard origin/main

# Reinstall dependencies (in case of new packages)
# Windows:
setup.bat

# Linux:
./setup.sh

# Done! Start as usual:
# Windows:
start.bat

# Linux:
./start.sh
```

⚠️ **Warning**: `git reset --hard origin/main` will remove all your local code changes. Your videos and processed clips in the `workspace/` folder **will not be affected**.

## 🔑 YouTube API Setup (for YouTube Shorts Publishing)

YouTube API is **completely free** for personal use (quota: 10,000 units/day = ~6 videos/day).

### Setup Steps (5 minutes):

1. **Go to [Google Cloud Console](https://console.cloud.google.com/)**
   - Sign in with your Google account
2. **Create a new project**:
   - Click "Select a project" → "New Project"
   - Name: `ClipForge` (any name)
   - Click "Create"
3. **Enable YouTube Data API v3**:
   - Go to **APIs & Services → Library**
   - Search for "YouTube Data API v3"
   - Click **Enable**
4. **Create OAuth 2.0 Client ID**:
   - Go to **APIs & Services → Credentials**
   - Click **Create Credentials → OAuth 2.0 Client ID**
   - If prompted to configure OAuth consent screen:
     - User Type: **External**
     - App name: `ClipForge`
     - User support email: your email
     - Developer contact: your email
     - Scopes: leave empty
     - Test users: add your Google email
     - Click **Save and Continue** until done
   - Application type: **Desktop app**
   - Name: `ClipForge Desktop`
   - Click **Create**
5. **Download `client_secret.json`**:
   - Click the **Download JSON** button next to the created Client ID
   - Rename the file to `client_secret.json`
   - **Place it in the root of the `clipforge/` folder** (next to `setup.bat`)
6. **Done!** When you publish your first video, the app will open a browser for authorization. Authorize once — the token will be saved locally.

**Note**: You **do NOT need** a paid Google Cloud Platform account. The free quota is more than enough for personal use.

## 🛠️ Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'faster_whisper'`
**Solution**: Run `setup.bat` / `setup.sh` again. The Python dependencies installation may not have completed.

### Issue: `FFmpeg not found`
**Solution**:
- **Windows**: Install FFmpeg via `winget install Gyan.FFmpeg` or download manually and add to PATH
- **Linux**: `sudo apt install ffmpeg` (Ubuntu/Debian) or `sudo yum install ffmpeg` (CentOS/RHEL)
- After installation, restart the terminal and check: `ffmpeg -version`

### Issue: WebSocket connection failed / 403 Forbidden
**Solution**: This issue has been fixed in the latest version. Perform an update (see **Updating** section).

### Issue: Subtitle language detected incorrectly
**Solution**:
- Open `.env.example`, copy it to `.env`
- Add line: `WHISPER_LANGUAGE=ru` (or `en`, `es`, etc.)
- This will force the language for all videos

### Issue: YouTube video download fails (yt-dlp warning)
**Solution**:
- Update yt-dlp: open a terminal in the `clipforge` folder and run:
  ```bash
  # Windows:
  venv\Scripts\python.exe -m pip install --upgrade yt-dlp

  # Linux:
  ./venv/bin/python -m pip install --upgrade yt-dlp
  ```

### Issue: Application doesn't open in browser
**Solution**:
- Check that ports 8000 and 5173 are free (not used by other applications)
- Manually open in browser: `http://localhost:5173`
- Check logs in the console — the backend or frontend may not have started

### Issue: "Low confidence language detection" for dubbed videos (Russian + English)
**This is normal**. For videos with mixed languages (e.g., Russian voiceover + muted English original):
- Whisper may detect the language with low confidence
- ClipForge automatically defaults to Russian in such cases
- If you want to force a language, add `WHISPER_LANGUAGE=ru` to `.env` (see above)

### Issue: Session not restored after page reload
**Solution**: The session is saved in the browser's localStorage. If you cleared the browser cache, the session will be lost. Also ensure you're using the latest version (see **Updating** section).

## 📊 Memory Usage and Performance

- **Whisper model (base)**: ~500 MB RAM during processing
- **FFmpeg processing**: ~1-2 GB RAM per clip (depends on length and effects)
- **Processing speed**:
  - Moment detection: ~5-10 minutes per 1 hour of source video
  - Clip processing: ~30-60 seconds per clip (depends on number of effects)
- **GPU acceleration**: Not required (everything runs on CPU). If you have an NVIDIA GPU with CUDA installed, Whisper will automatically use the GPU.

## 🤝 Contributing

The project is in active development. If you found a bug or have an idea for improvement:
- Open an **Issue** on GitHub: [https://github.com/hipux/clipforge/issues](https://github.com/hipux/clipforge/issues)
- Or submit a **Pull Request**

## 📄 License

This project uses only **open-source and free** components:
- ClipForge code: MIT License (freely use, modify, distribute)
- FFmpeg: LGPL / GPL (free for personal use)
- faster-whisper: MIT License
- yt-dlp: Unlicense (public domain)
- PySceneDetect: BSD License
- librosa: ISC License
