# ClipForge 🎬

[🇷🇺 Русский](README.md) | [🇬🇧 English](README.en.md)

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
3. Дождитесь завершения загрузки (прогресс, скорость, ETA показываются в реальном времени)

#### Шаг 2: Определение моментов

1. Нажмите "Continue to Moments" или перейдите на вкладку Moments
2. AI автоматически определит 5-15 интересных моментов
3. Просмотрите кандидатов (оценка, таймкоды, причина)
4. Выберите клипы, которые хотите обработать

#### Шаг 3: Настройка эффектов

1. **Стиль субтитров**: выберите один из 5 стилей (Karaoke, Bold White, Neon, Minimal, Cinematic)
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
