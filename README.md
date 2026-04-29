# Coursera-Bypass (Unlimited API Keys Edition)

**Coursera-Bypass** is a powerful automation tool designed to help you breeze through mandatory Coursera courses. It automatically handles video watching, reading materials, and uses AI to solve assessments — all **without needing your own API keys**.

> ⚡ **This branch (`bypass-with-unlimited_api_usage`) uses free, rotating API keys** fetched automatically from the web. You don't need to provide any personal API keys — the tool handles everything for you.

## ✨ Features

- **🔑 Unlimited Free API Keys**: Automatically fetches and rotates free LLM API keys from [alistaitsacle/free-llm-api-keys](https://github.com/alistaitsacle/free-llm-api-keys). No personal API key required!
- **🤖 Multi-Model Support**: Supports 20+ LLM models including GPT-5.4, Claude Opus 4.6, Gemini 2.5 Pro, DeepSeek, and more — automatically picks the best available model.
- **🔄 Auto Key Rotation**: If a key hits rate limits or expires, it seamlessly rotates to the next available key (up to 15 retries per request).
- **📹 Automated Video Watching**: Automatically marks videos as completed.
- **📖 Reading Material Skipping**: Instantly completes reading assignments.
- **🧠 AI-Powered Quiz Solver**: Uses free LLMs to solve graded and ungraded quizzes with high accuracy.
- **📋 Sequential Processing**: Follows the course syllabus strictly to handle prerequisites and locked items.
- **🍪 Browser Cookie Integration**: Automatically fetches authentication cookies from your browser (Chrome, Firefox, or Edge).
- **📝 Draft Resumption**: Resumes existing quiz attempts seamlessly.

## ⚠️ Performance Note

> This version uses **free web-based APIs**, which may be slower than using personal API keys. A single course can take **up to 15 minutes** to process depending on API availability and rate limits. If you need faster processing, switch to the `main` branch and use your own API keys.

## 🚀 Installation

### Prerequisites

- Python 3.10 or higher
- No API keys needed! (optional: you can still add personal Gemini/Perplexity/Groq keys for faster processing)

### Install via Pip

```bash
pip install coursera-bypass
```

### Install from Source

```bash
git clone -b bypass-with-unlimited_api_usage https://github.com/Ashshar6055/Coursera-Bypass.git
cd Coursera-Bypass
pip install -e .
```

## 🏁 Quick Start

1. **Login**: Log into Coursera in your preferred web browser (Chrome, Firefox, or Edge).
2. **Run** — that's it! No API key configuration needed:
   ```bash
   coursera-bypass course-slug --llm
   ```
   The tool will automatically:
   - Fetch your Coursera cookies from the browser
   - Download free API keys from GitHub
   - Pick the best available LLM model
   - Solve all quizzes and complete all materials

### Optional: Personal API Keys

If you want faster processing, you can add your own API keys in `~/.coursera-bypass/config.json`:
```json
{
  "gemini_api_key": "YOUR_GEMINI_KEY",
  "groq_api_key": "YOUR_GROQ_KEY",
  "free_keys_enabled": true,
  "cookies": {}
}
```

## 📖 Example

To bypass the "Introduction to Psychology" course:
```bash
coursera-bypass introduction-psychology --llm
```

## 🔑 How the Free API Key System Works

1. On startup, the tool fetches API keys from a public GitHub repository
2. Keys are cached locally (`~/.coursera-bypass/free_keys_cache.json`) and refreshed every hour
3. Keys are sorted by model quality (GPT-5.4 > Claude Opus > Gemini Pro > etc.)
4. If a key fails (rate limited, expired, or budget drained), it auto-rotates to the next one
5. All keys use an OpenAI-compatible gateway (`pekpik.com`)

### Supported Models (auto-selected by priority)

| Priority | Model | Provider |
|----------|-------|----------|
| 🥇 Highest | GPT-5.4, GPT-5.4 Pro | OpenAI |
| 🥈 High | Claude Opus 4.6, Claude Sonnet 4.6 | Anthropic |
| 🥉 Good | Gemini 2.5 Pro, DeepSeek Reasoner | Google / DeepSeek |
| ⭐ Standard | Gemini 2.5 Flash, Mistral Medium, Kimi K2.5 | Various |

## 🔀 Branch Comparison

| Feature | `main` | `bypass-with-unlimited_api_usage` |
|---------|--------|-----------------------------------|
| API Keys Required | ✅ Yes (personal) | ❌ No (auto-fetched) |
| Speed | ⚡ Fast | 🐢 Slower (up to 15 min/course) |
| Cost | 💰 Depends on usage | 🆓 Completely free |
| Reliability | ✅ Stable | ⚠️ Depends on key availability |

## ⚖️ Disclaimer

This tool is for educational purposes only. Use it responsibly and ensure you are complying with Coursera's Terms of Service.

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
