import json
import sys
from pathlib import Path

from loguru import logger

CONFIG_DIR = Path.home() / ".coursera-bypass"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "cookies": {},
    "perplexity_api_key": "",
    "gemini_api_key": "",
    "groq_api_key": "",
    "perplexity_model": "sonar-pro",
    "gemini_model": "gemini-2.5-pro",
    "groq_model": "llama-3.3-70b-versatile",
    "free_keys_enabled": True,
    "free_keys_preferred_model": "gemini-2.5-pro"
}


def fetch_browser_cookies() -> dict:
    try:
        import browser_cookie3
    except ImportError:
        logger.error("browser-cookie3 not installed. Run: pip install browser-cookie3")
        return {}

    browsers = [
        ("Chrome", browser_cookie3.chrome),
        ("Firefox", browser_cookie3.firefox),
        ("Edge", browser_cookie3.edge),
    ]

    for name, browser_fn in browsers:
        try:
            cj = browser_fn(domain_name=".coursera.org")
            cookies = {c.name: c.value for c in cj}
            if "CAUTH" in cookies:
                logger.success(f"Fetched Coursera cookies from {name}")
                return cookies
        except Exception:
            continue

    logger.warning("Could not find Coursera cookies in any browser. Make sure you're logged into Coursera.")
    return {}


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2))

    config = json.loads(CONFIG_FILE.read_text())

    if not config.get("cookies"):
        logger.info("No cookies in config — attempting to fetch from browser...")
        cookies = fetch_browser_cookies()
        if cookies:
            config["cookies"] = cookies
            CONFIG_FILE.write_text(json.dumps(config, indent=2))
            logger.info(f"Cookies saved to {CONFIG_FILE}")
        else:
            logger.error(f"No cookies found. Log into Coursera in your browser and retry, or manually edit {CONFIG_FILE}")
            sys.exit(1)

    return config


_config = load_config()

# URLs (constant, not user-configurable)
BASE_URL = "https://www.coursera.org/api/"
GRAPHQL_URL = "https://www.coursera.org/graphql-gateway"
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# User-configurable
COOKIES = _config["cookies"]
PERPLEXITY_API_KEY = _config.get("perplexity_api_key", "")
GEMINI_API_KEY = _config.get("gemini_api_key", "")
GROQ_API_KEY = _config.get("groq_api_key", "")
PERPLEXITY_MODEL = _config.get("perplexity_model", "sonar-pro")
GEMINI_MODEL = _config.get("gemini_model", "gemini-2.5-pro")
GROQ_MODEL = _config.get("groq_model", "llama-3.3-70b-versatile")
FREE_KEYS_ENABLED = _config.get("free_keys_enabled", True)
FREE_KEYS_PREFERRED_MODEL = _config.get("free_keys_preferred_model", "gpt-5.4")

SYSTEM_PROMPT = (
    "You are a world-class academic expert with deep knowledge across all university subjects "
    "including computer science, cybersecurity, networking, ethical hacking, data science, "
    "business, mathematics, engineering, and all Coursera course domains. "
    "You have a PhD-level understanding of every topic and NEVER guess — you reason precisely.\n\n"

    "TASK: Answer the provided multiple-choice quiz questions with 100% accuracy.\n\n"

    "INPUT FORMAT:\n"
    "- Questions are in a JSON dict. Each key is a question_id.\n"
    "- Each value contains: 'Question' (the question text), 'Options' (list of option dicts "
    "with 'option_id' and 'value'), and 'Type' ('Single-Choice' or 'Multi-Choice').\n"
    "- Question/option values may contain HTML markup — IGNORE all HTML tags and focus only on text content.\n\n"

    "CRITICAL RULES:\n"
    "1. For 'Single-Choice': Select EXACTLY ONE best answer. Return ONE option_id in the list.\n"
    "2. For 'Multi-Choice': Select ALL correct answers. Return MULTIPLE option_ids. "
    "Do NOT select only one — carefully evaluate EVERY option independently.\n"
    "3. NEVER leave a question unanswered.\n"
    "4. When unsure between two options, use elimination: rule out clearly wrong answers first, "
    "then pick the most technically precise remaining option.\n\n"

    "REASONING METHODOLOGY (follow for EVERY question):\n"
    "Step 1: Read the question carefully. Identify the EXACT concept being tested.\n"
    "Step 2: For EACH option, determine if it is correct or incorrect and WHY.\n"
    "Step 3: Watch for Coursera-style traps:\n"
    "  - 'All of the above' / 'None of the above' — verify EVERY other option before selecting\n"
    "  - Negation words: 'NOT', 'EXCEPT', 'LEAST' — these REVERSE what you're looking for\n"
    "  - Subtle word differences: 'authentication' vs 'authorization', 'encryption' vs 'encoding'\n"
    "  - Absolute words like 'always', 'never' are usually WRONG; qualified statements are usually RIGHT\n"
    "  - Options that are technically true but don't answer the SPECIFIC question asked\n"
    "Step 4: For multi-choice, independently evaluate each option as true/false — don't stop at 2-3.\n"
    "Step 5: Double-check your selections before finalizing.\n\n"

    "ACCURACY IS PARAMOUNT. You must achieve a passing grade. Think deeply before answering."
)

HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
    'x-coursera-application': 'ondemand',
    'x-coursera-version': '3bfd497de04ae0fef167b747fd85a6fbc8fb55df',
    'x-requested-with': 'XMLHttpRequest',
}
