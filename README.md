# Skipera

**Skipera** is a powerful automation tool designed to help you breeze through mandatory Coursera courses. It automatically handles video watching, reading materials, and even uses AI to solve assessments, saving you hours of repetitive work.

## Features

- **Automated Video Watching**: Automatically marks videos as completed.
- **Reading Material Skipping**: Instantly completes reading assignments.
- **AI-Powered Quiz Solver**: Uses Gemini or Perplexity LLMs to solve graded and ungraded quizzes with high accuracy.
- **Sequential Processing**: Follows the course syllabus strictly to handle prerequisites and locked items.
- **Browser Cookie Integration**: Automatically fetches authentication cookies from your browser (Chrome, Firefox, or Edge).
- **Draft Resumption**: Resumes existing quiz attempts seamlessly.

## Installation

### Prerequisites

- Python 3.10 or higher
- A Google Gemini or Perplexity API key (optional, for quiz solving)

### Install via Pip

```bash
pip install coursera-bypass
```

### Install from Source

```bash
git clone https://github.com/Ashshar6055/Coursera-Bypass.git
cd Coursera-Bypass
pip install -e .
```

## Quick Start

1.  **Login**: Log into Coursera in your preferred web browser.
2.  **Configure API Key**:
    On first run, the tool creates a configuration file at `~/.coursera-bypass/config.json`. Add your Gemini API key there:
    ```json
    {
      "gemini_api_key": "YOUR_API_KEY",
      "cookies": {}
    }
    ```
3.  **Run**:
    Find the course slug (the part of the URL after `coursera.org/learn/`) and run:
    ```bash
    coursera-bypass course-slug --llm
    ```

## Example

To bypass the "Introduction to Psychology" course:
```bash
coursera-bypass introduction-psychology --llm
```

## Disclaimer

This tool is for educational purposes only. Use it responsibly and ensure you are complying with Coursera's Terms of Service.

## License

MIT License. See [LICENSE](LICENSE) for details.
