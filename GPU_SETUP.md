# GPU Pipeline Setup Guide

## Обзор

ClipForge теперь использует GPU-first архитектуру для быстрого и точного анализа видео:

- **Этап 1: Сбор данных** (~2.4 GB VRAM)
  - Whisper distil-large-v3 (транскрипция речи)
  - YOLOv8n-face (детекция и трекинг лиц)
  - Librosa (анализ аудио)

- **Этап 2: ИИ-режиссёр** (~4.5 GB VRAM)
  - Qwen2.5-7B-Instruct (анализ контента и генерация инструкций)

- **Этап 3: Рендеринг** (~0.5 GB VRAM)
  - NVENC h264 (аппаратное кодирование)

## Требования

- NVIDIA GPU с поддержкой CUDA 12.1+ (рекомендуется RTX 5060 или выше, минимум 8 GB VRAM)
- NVIDIA Driver 535+
- FFmpeg с поддержкой NVENC

## Установка

### 1. Установка PyTorch с CUDA

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### 2. Установка llama-cpp-python с CUDA

```bash
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python
```

### 3. Установка остальных зависимостей

```bash
pip install -r requirements.txt
```

### 4. Проверка FFmpeg NVENC

```bash
ffmpeg -encoders 2>/dev/null | grep h264_nvenc
```

Если команда ничего не выводит, NVENC недоступен (система автоматически переключится на libx264 CPU-кодек).

## Скачивание моделей

Модели скачиваются автоматически при первом запуске в `<project_root>/models/`:

- `models/qwen2.5-7b-instruct-q4_k_m.gguf` (~4.7 GB)
- `models/yolov8n-face.pt` (~6 MB)
- `models/whisper/` (~1.5 GB кеш faster-whisper)

Директория `models/` автоматически исключена из Git.

## CPU Fallback (аварийный режим)

Если GPU недоступен или CUDA не установлена, ClipForge автоматически переключается на legacy CPU-пайплайн:

- Без face detection
- Без LLM-анализа
- Без NVENC (libx264 CPU-кодек)
- Базовый алгоритм детекции моментов

## Конфигурация через переменные окружения

Все настройки имеют префикс `CLIPFORGE_`:

```bash
# Принудительно отключить GPU (для тестирования CPU-режима)
export CLIPFORGE_USE_GPU=false

# Путь к моделям (по умолчанию: <project_root>/models)
export CLIPFORGE_MODELS_DIR=/path/to/models

# LLM настройки
export CLIPFORGE_QWEN_N_CTX=8192
export CLIPFORGE_QWEN_TEMP=0.3

# Face detection
export CLIPFORGE_FACE_SAMPLE_FPS=2.0

# NVENC настройки
export CLIPFORGE_NVENC_PRESET=p7
export CLIPFORGE_NVENC_CQ=20
```

## Проверка работы GPU

После установки, запустите миграцию БД и проверьте статус GPU:

```bash
# Миграция БД
python backend/migrate_gpu_fields.py

# Запуск сервера
uvicorn backend.main:app --reload

# Проверка GPU status
curl http://localhost:8000/api/gpu/status
```

Ответ должен содержать:
```json
{
  "device": "cuda",
  "is_gpu": true,
  "vram_usage": {
    "total_gb": 8.0,
    "free_gb": 7.5,
    ...
  },
  "nvenc_available": true
}
```

## Использование ИИ-инструкций

В веб-интерфейсе (если GPU доступен) появится поле "🧠 Инструкции для ИИ", где можно указать:

- Предпочтения по типу контента (реакции, шутки, объяснения)
- Критерии выбора моментов
- Что избегать

Примеры:
- "Выбирай только смешные моменты"
- "Избегай технических объяснений"
- "Предпочитай короткие реакции с явными эмоциями"

## Troubleshooting

### CUDA not available

```bash
# Проверить установку CUDA
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
```

### llama-cpp-python ошибка при импорте

Переустановите с правильными флагами:
```bash
pip uninstall llama-cpp-python
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python --no-cache-dir
```

### Out of Memory (OOM)

Если VRAM недостаточно:
1. Убедитесь что других GPU-процессов нет
2. Уменьшите `CLIPFORGE_QWEN_N_CTX` (по умолчанию 8192)
3. В крайнем случае: `export CLIPFORGE_USE_GPU=false`
