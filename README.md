# Auto-Podcast Studio

AI-powered podcast generation with Electron desktop app.

## Features

- 🎨 **Electron Desktop App**: Single `npm start` to launch
- 📊 **Visual Workflow**: Real-time node execution monitoring  
- 🎯 **Modular Nodes**: Each processing step is independent
- � **Simple Setup**: One command installs everything

## Quick Start

```bash
# Install all dependencies (Node.js + Python)
npm install

# Launch the app
npm start
```

## Project Structure

```
auto-podcast/
├── package.json           # Dependencies & scripts
├── electron/              # Electron main process
│   ├── main.js           # Python subprocess orchestration
│   └── preload.js        # IPC bridge
├── src/                   # React frontend
│   ├── App.tsx
│   └── components/       # WorkflowCanvas, NodeDetailPanel, LogPanel
├── nodes/                 # Python processing nodes
│   ├── fetch/            # Fetch content from RSS/web
│   ├── preprocess/       # Clean & deduplicate
│   ├── research/         # Web search & fact-check
│   ├── topic_selection/  # Cluster & select topic
│   ├── script/           # Generate dialogue script
│   ├── stages/           # Segment & assign speakers
│   ├── tts/              # Text-to-speech
│   ├── audio_postprocess/# Combine & normalize audio
│   ├── assets/           # Generate cover art
│   ├── store/            # Save to storage
│   └── publish/          # Generate RSS feed
└── protocol/              # Shared state schema
    ├── state.py
    └── config_base.py
```

## Configuration

Create `.env` file:

```bash
OPENAI_API_KEY=your-api-key
OPENAI_API_BASE=https://api.openai.com/v1
```

Edit `config.example.yaml` for node settings:

```yaml
fetch:
  sources:
    - type: rss
      url: "https://hnrss.org/frontpage"

script:
  llm_model: "gpt-4o"
  temperature: 0.7

tts:
  voice_mapping:
    Host A: "zh-CN-XiaoxiaoNeural"
    Host B: "zh-CN-YunxiNeural"
```

## Development

```bash
npm run dev             # Dev mode with hot reload
npm run build           # Build React frontend
npm run build:electron  # Package as desktop app
```

## Documentation

- [Architecture](./docs/ARCHITECTURE.md) - 架构规范
- [UI/UX Design](./docs/UI_UX_DESIGN.md) - 界面设计

## License

MIT
