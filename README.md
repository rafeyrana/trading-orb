# Trading Bot

## Overview

The Trading Bot is an automated tool designed to help traders efficiently monitor stocks for **Opening Range Breakouts (ORB)**. It uses the Alpha Vantage API for market data and is designed to run continuously, checking for opportunities during market hours.

This project uses `uv` for environment and package management, `ruff` for linting and formatting, and `mypy` for static type checking.

## Features

*   Monitors predefined ticker symbols for ORB strategy.
*   Operates based on EST market hours.
*   Logs alerts to the console.
*   Modular design (data fetching, strategy, alerting, scheduling, configuration).
*   Configuration via `.env` file and `config.py`.

## Setup and Installation

This project requires **Python 3.10 or newer**.

This project uses `uv` for fast environment and package management.

1.  **Install `uv`**:
    If you don't have `uv` installed, follow the instructions at [astral.sh/uv](https://astral.sh/uv) (e.g., `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`).

2.  **Clone the Repository**:
    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

3.  **Create and Activate Virtual Environment using `uv`**:
    It's recommended to create a virtual environment for the project.
    ```bash
    uv venv .venv  # Creates a virtual environment named .venv
    source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
    ```
    Alternatively, `uv sync` or `uv pip install` can often create and manage the environment implicitly if one isn't active, but explicit creation is good practice.

4.  **Install Dependencies using `uv`**:
    Dependencies are defined in `pyproject.toml`. Install them using:
    ```bash
    uv pip install -e .[dev]
    ```
    This command installs the main dependencies, plus the development dependencies (like `pytest`, `mypy`, `ruff`). The `-e .` installs the current project in editable mode.

5.  **Set up Environment Variables**:
    Copy the example environment file and fill in your API key:
    ```bash
    cp .env.example .env
    ```
    Now, edit the `.env` file to add your `ALPHA_VANTAGE_API_KEY`. You can get a free API key from [Alpha Vantage](https://www.alphavantage.co/support/#api-key).

## Running the Bot

Once the setup is complete and your `.env` file is configured, you can run the bot:

```bash
python main.py
```

The bot will start logging its activity to the console.

## Development

### Linting and Formatting

This project uses `ruff` for linting and formatting.

*   **Format code**:
    ```bash
    ruff format .
    ```
*   **Check for linting errors and auto-fix where possible**:
    ```bash
    ruff check --fix .
    ```
*   **Check without fixing**:
    ```bash
    ruff check .
    ```
    Configuration for `ruff` is in `pyproject.toml`.

### Static Type Checking

This project uses `mypy` for static type checking.

*   **Run type checker**:
    ```bash
    mypy .
    ```
    Configuration for `mypy` is in `pyproject.toml`.

### Running Tests

This project uses `pytest` for unit and integration tests.

*   **Run all tests**:
    ```bash
    pytest
    ```
*   **Run unit tests only**:
    ```bash
    pytest tests/unit
    ```
*   **Run integration tests only**:
    ```bash
    pytest tests/integration
    ```
    Test configuration is in `pyproject.toml`.

## Disclaimer

This trading bot is for educational and experimental purposes only. Trading stocks involves substantial risk of loss and is not suitable for every investor. The developers are not responsible for any financial losses incurred by using this software. Always do your own research and consider professional financial advice.
