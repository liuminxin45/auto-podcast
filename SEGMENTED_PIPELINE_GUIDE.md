# Guía de Pipeline Segmentado - Auto-Podcast

## 📋 Resumen de Cambios

Este documento describe la refactorización completa del sistema de generación de podcasts, transformándolo de un flujo "single LLM + single TTS" a un sistema "segmented LLM + segmented TTS + auto-merge".

## 🎯 Objetivos Cumplidos

✅ **Generación por segmentos**: LLM genera 6 segmentos independientes (S0-S5)
✅ **TTS por segmentos**: Cada segmento se convierte a audio independientemente
✅ **Caché inteligente**: Segmentos exitosos se cachean, solo se regeneran los fallidos
✅ **BGM automático**: Inserta transiciones y outro automáticamente
✅ **Metadata estructurada**: manifest.json con toda la información de generación
✅ **Mínima invasión**: Mantiene compatibilidad con el sistema existente
✅ **Retry por segmento**: Cada segmento puede reintentar sin afectar a los demás

## 📁 Archivos Nuevos Creados

### 1. Modelos de Datos
**`src/models/segment.py`**
- `SegmentScript`: Modelo de script por segmento
- `SegmentAudio`: Modelo de audio por segmento
- `EpisodeManifest`: Manifest completo del episodio
- `BGMInsert`: Configuración de inserción de BGM
- Constantes: `SEGMENT_TYPES`, `SEGMENT_ORDER`

### 2. Generador de Segmentos
**`src/llm/segment_generator.py`**
- `SegmentGenerator`: Clase principal para generar scripts por segmento
- `SEGMENT_PROMPTS`: Prompts específicos para cada tipo de segmento
- `generate_all_segments()`: Función helper para generar todos los segmentos

### 3. Adaptador LLM
**`src/llm/client/segment_adapter.py`**
- `LLMClientAdapter`: Adapta MoonshotClient/DeepSeekClient para uso con SegmentGenerator
- Proporciona interfaz `chat()` unificada

### 4. Merger de Audio
**`src/audio/segment_merger.py`**
- `AudioMerger`: Clase para merge de audio con ffmpeg
- `merge_episode_with_bgm()`: Función principal de merge con BGM
- `get_audio_duration()`: Obtiene duración de archivos de audio

### 5. Script Step Segmentado
**`src/app/pipelines/steps/script_step_segmented.py`**
- `ScriptStepSegmented`: Versión segmentada del paso de script
- Genera 6 segmentos: S0 (Opening), S1 (Overview), S2 (History), S3 (Detail News), S4 (Deep Dive), S5 (Closing)

### 6. Audio Step Segmentado
**`src/app/pipelines/steps/audio_step_segmented.py`**
- `AudioStepSegmented`: Versión segmentada del paso de audio
- TTS por segmento con caché
- Merge automático con BGM

## 🏗️ Estructura de Segmentos

### Segmentos Definidos

```
S0: OPENING (15-20s)
    - Saludo
    - Nombre del show
    - Fecha y día de la semana
    
S1: OVERVIEW (30-45s)
    - Resumen de 3-6 noticias principales
    - Introducción al tema profundo
    
S2: HISTORY (20-30s)
    - "Historia del día"
    - 1-2 eventos históricos relevantes
    
S3: DETAIL_NEWS (60-120s)
    - Desarrollo detallado de cada noticia
    - 15-25s por noticia
    
S4: DEEP_DIVE (60-90s)
    - Análisis profundo de un tema
    - Contexto, análisis, opinión
    
S5: CLOSING (15-20s)
    - Resumen final
    - Despedida
```

### Inserción de BGM

```
S0 → S1 → [transition.mp3] → S2 → [transition.mp3] → S3 → [transition.mp3] → S4 → [transition.mp3] → S5 → [outro.mp3]
```

## 📂 Estructura de Directorios de Salida

```
out/runs/{date}/{run_id}/
├── 2_script/
│   ├── segments/
│   │   ├── S0.json
│   │   ├── S1.json
│   │   ├── S2.json
│   │   ├── S3.json
│   │   ├── S4.json
│   │   └── S5.json
│   ├── {date}.segments.json      # Resumen de todos los segmentos
│   └── {date}.full_script.txt    # Script completo para revisión
│
├── 3_tts/
│   ├── segments/
│   │   ├── S0.mp3
│   │   ├── S1.mp3
│   │   ├── S2.mp3
│   │   ├── S3.mp3
│   │   ├── S4.mp3
│   │   └── S5.mp3
│   └── manifest.json             # Manifest completo con metadata
│
└── 4_render/
    └── {date}.final.mp3          # Audio final merged
```

## 🔧 Configuración Requerida

### 1. Assets de BGM

Crear la siguiente estructura de assets:

```bash
mkdir -p assets/bgm
```

Colocar los archivos:
- `assets/bgm/transition.mp3` (0.5-1.2s) - Transición entre segmentos
- `assets/bgm/outro.mp3` (2-3s) - Música de cierre

### 2. Variables de Entorno

Las mismas que el sistema anterior:
```bash
# LLM Provider
LLM_PROVIDER=moonshot  # o deepseek

# Moonshot
MOONSHOT_API_KEY=your_key
MOONSHOT_BASE_URL=https://api.moonshot.cn/v1
MOONSHOT_MODEL=moonshot-v1-8k

# DeepSeek
DEEPSEEK_API_KEY=your_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# TTS (Doubao)
DOUBAO_MODE=tts_v3_http  # o podcast, voiceclone_http, tts_v3_ws
DOUBAO_RESOURCE_ID=your_resource_id
DOUBAO_WS_URL=your_ws_url
```

## 🚀 Cómo Usar el Sistema Segmentado

### Opción 1: Usar los Nuevos Steps (Recomendado)

Modificar el orchestrator para usar los nuevos steps:

```python
# En src/app/orchestrator.py o donde se configure el pipeline

# Importar los nuevos steps
from src.app.pipelines.steps.script_step_segmented import ScriptStepSegmented
from src.app.pipelines.steps.audio_step_segmented import AudioStepSegmented

# Reemplazar en el pipeline
pipeline_steps = [
    FetchStep(),
    SelectionStep(),
    ScriptStepSegmented(),  # ← Nuevo
    AudioStepSegmented(),   # ← Nuevo
    PublishStep(),
]
```

### Opción 2: Crear un Nuevo Pipeline

```python
# src/app/pipelines/segmented_pipeline.py
from src.app.pipelines.steps.fetch_step import FetchStep
from src.app.pipelines.steps.selection_step import SelectionStep
from src.app.pipelines.steps.script_step_segmented import ScriptStepSegmented
from src.app.pipelines.steps.audio_step_segmented import AudioStepSegmented
from src.app.pipelines.steps.publish_step import PublishStep

class SegmentedPipeline:
    def __init__(self):
        self.steps = [
            FetchStep(),
            SelectionStep(),
            ScriptStepSegmented(),
            AudioStepSegmented(),
            PublishStep(),
        ]
    
    def execute(self, ctx):
        for step in self.steps:
            step.execute(ctx)
```

### Opción 3: Switch Configurable

Agregar en `config/settings.yaml`:

```yaml
pipeline:
  mode: segmented  # o "legacy"
```

Y en el código:

```python
if config.get("pipeline", {}).get("mode") == "segmented":
    script_step = ScriptStepSegmented()
    audio_step = AudioStepSegmented()
else:
    script_step = ScriptStep()
    audio_step = AudioStep()
```

## 🔄 Cómo Funciona el Caché

### Caché de Scripts
Los scripts se guardan en `2_script/segments/{segment_id}.json`. Si el archivo existe, se puede reutilizar.

### Caché de Audio
Los archivos de audio se guardan en `3_tts/segments/{segment_id}.mp3`. Si existe:
- Se marca como `cached: true` en el manifest
- No se llama al TTS
- Se usa directamente en el merge

### Regenerar un Segmento Específico

```bash
# Borrar el script y audio de un segmento específico
rm out/runs/{date}/{run_id}/2_script/segments/S3.json
rm out/runs/{date}/{run_id}/3_tts/segments/S3.mp3

# Volver a ejecutar el pipeline
python run.py
```

## 📊 Manifest.json

El archivo `manifest.json` contiene toda la metadata:

```json
{
  "episode_id": "life-consumer:2025-12-30",
  "segments": [
    {
      "segment_id": "S0",
      "mp3_path": "/path/to/S0.mp3",
      "duration_ms": 18000,
      "gen_ms": 2500,
      "tts_ms": 2500,
      "cached": false
    },
    ...
  ],
  "bgm": [
    {
      "name": "transition",
      "path": "/path/to/transition.mp3",
      "insert_after": "S1"
    },
    ...
  ],
  "final_path": "/path/to/final.mp3",
  "created_at": "2025-12-30T10:30:00",
  "total_duration_ms": 300000
}
```

## 🔍 Debugging

### Ver Logs por Segmento

Los logs incluyen el `segment_id`:

```
INFO: 生成段落 S0 (OPENING)
INFO: ✓ S0 生成成功: 18秒
INFO: 生成 S0 TTS...
INFO: ✓ S0 TTS完成: 18.5秒, 耗时 2500ms
```

### Verificar un Segmento Específico

```bash
# Ver el script
cat out/runs/{date}/{run_id}/2_script/segments/S3.json

# Reproducir el audio
ffplay out/runs/{date}/{run_id}/3_tts/segments/S3.mp3

# Ver el manifest
cat out/runs/{date}/{run_id}/3_tts/manifest.json | jq
```

## 🔙 Rollback al Sistema Anterior

### Opción 1: Usar Git

```bash
# Ver los archivos modificados
git status

# Revertir cambios
git checkout src/app/pipelines/steps/script_step.py
git checkout src/app/pipelines/steps/audio_step.py

# Borrar archivos nuevos
git clean -fd src/models/
git clean -fd src/llm/segment_generator.py
git clean -fd src/audio/segment_merger.py
```

### Opción 2: Renombrar Archivos

Los archivos originales no fueron modificados. Los nuevos steps son:
- `script_step_segmented.py` (nuevo)
- `audio_step_segmented.py` (nuevo)

Simplemente no los uses y el sistema funcionará como antes.

### Opción 3: Backup Manual

Si modificaste el orchestrator, restaura desde backup:

```bash
cp src/app/orchestrator.py.backup src/app/orchestrator.py
```

## ⚠️ Limitaciones Conocidas

1. **Dependencia de ffmpeg**: Requiere ffmpeg instalado en el sistema
2. **Prompts fijos**: Los prompts están hardcoded en `segment_generator.py`
3. **Sin paralelización**: TTS se ejecuta secuencialmente (puede optimizarse)
4. **BGM obligatorio**: Si no hay BGM, se salta pero se registra warning

## 🎨 Personalización

### Modificar Prompts

Editar `src/llm/segment_generator.py`, sección `SEGMENT_PROMPTS`:

```python
SEGMENT_PROMPTS = {
    "S0": {
        "system": "Tu prompt personalizado...",
        "user_template": "Template con {variables}..."
    },
    ...
}
```

### Cambiar Duración de Segmentos

Los prompts incluyen la duración sugerida. Modificar en cada prompt:

```python
"user_template": """...
要求：
- 30-45秒  # ← Cambiar aquí
...
"""
```

### Agregar Nuevos Segmentos

1. Agregar en `src/models/segment.py`:
```python
SEGMENT_TYPES = {
    ...
    "S6": "NEW_SEGMENT_TYPE",
}

SEGMENT_ORDER = ["S0", "S1", "S2", "S3", "S4", "S5", "S6"]
```

2. Agregar prompt en `segment_generator.py`:
```python
SEGMENT_PROMPTS["S6"] = {
    "system": "...",
    "user_template": "..."
}
```

3. Actualizar merge logic en `audio_step_segmented.py`

## 📈 Mejoras Futuras

- [ ] Paralelización de TTS (asyncio/ThreadPool)
- [ ] Prompts configurables desde YAML
- [ ] Validación de audio (duración, calidad)
- [ ] Retry inteligente con backoff exponencial
- [ ] Dashboard web para monitoreo
- [ ] Soporte para múltiples voces por segmento
- [ ] A/B testing de diferentes prompts

## 🆘 Troubleshooting

### Error: "ffmpeg not found"
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Descargar de https://ffmpeg.org/download.html
```

### Error: "Segment S0 generation failed"
- Verificar API keys de LLM
- Revisar logs para ver el error específico
- Intentar regenerar solo ese segmento

### Error: "TTS timeout"
- Aumentar `timeout_seconds` en config
- Verificar conectividad con servicio TTS
- Reducir longitud del texto del segmento

### Audio final vacío o corrupto
- Verificar que todos los segmentos se generaron
- Revisar `manifest.json` para ver qué falló
- Verificar permisos de escritura en directorios

## 📞 Soporte

Para problemas o preguntas:
1. Revisar logs en `out/runs/{date}/{run_id}/`
2. Verificar `manifest.json` para metadata
3. Revisar este documento para configuración
4. Contactar al equipo de desarrollo

---

**Versión**: 1.0.0  
**Fecha**: 2025-12-30  
**Autor**: Auto-Podcast Team
