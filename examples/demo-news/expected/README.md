# Demo News Expected Output

Run:

```bash
npm run demo:news
```

The demo should finish without external network access or API keys. It writes generated artifacts to `examples/demo-news/output/`, including:

- `facts.json`
- `script.generated.json`
- `script.edited.json`
- `voice_segments/*.wav`
- `final.mp3` when ffmpeg is available, otherwise `final.wav`
- `audio_report.json`
- `feed.xml`
- `episode.json`
- `run_report.json`
- `dist/episodes/demo_morning_news_001/`

When `publish.public_base_url` is not provided, RSS is local-preview only and the run report records that warning.
