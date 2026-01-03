<div align="center">
  <h1>Dymo Code</h1>
  <h3>Dymo Code - Your local open source assistant.</h3>
  <img src="https://img.shields.io/badge/Python-purple?style=for-the-badge&logo=python&logoColor=white"/> 
  <a href="https://github.com/TPEOficial"> <img alt="GitHub" src="https://img.shields.io/badge/GitHub-purple?style=for-the-badge&logo=github&logoColor=white"/></a>
  <a href="https://ko-fi.com/fjrg2007"> <img alt="Kofi" src="https://img.shields.io/badge/Ko--fi-purple?style=for-the-badge&logo=ko-fi&logoColor=white"></a>
  <br />
  <br />
  <a href="#">Quickstart</a>
  <span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
  <a href="https://tpe.li/dsc">Discord</a>
  <span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
  <a href="#main-features">All Features</a>
  <span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
  <a href="#">Requirements</a>
  <span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
  <a href="#">FAQ</a>
  <br />
  <hr />
</div>

![alt text](./docs/images/image.png)

**Dymo Code** is the main alternative to Claude Code on the open-source side and free for users, maintained by the community.

## Quick Install

### Linux / macOS

```bash
curl -fsSL https://raw.githubusercontent.com/TPEOficial/dymo-code/main/scripts/install.sh | bash
```

### Windows (PowerShell)

```powershell
iwr -useb https://raw.githubusercontent.com/TPEOficial/dymo-code/main/scripts/install.ps1 | iex
```

### Install specific version

```bash
# Linux/macOS
curl -fsSL https://raw.githubusercontent.com/TPEOficial/dymo-code/main/scripts/install.sh | bash -s -- --version v1.0.0

# Windows
$env:DYMO_VERSION="v1.0.0"; iwr -useb https://raw.githubusercontent.com/TPEOficial/dymo-code/main/scripts/install.ps1 | iex
```

### Manual Download

Download the latest version from [Releases](https://github.com/TPEOficial/dymo-code/releases).

## Getting Started

1. Run `dymo-code` in your terminal
2. Set your API key: `/setapikey groq YOUR_API_KEY`
3. Start chatting!

> **Get free API keys:**
> - [Groq](https://console.groq.com) (Recommended - Fast & Free)
> - [Google AI Studio](https://aistudio.google.com/apikey) (Gemini)
> - [Cerebras](https://cloud.cerebras.ai) (Recommended - Fast & Free)
> - [OpenRouter](https://openrouter.ai/keys) (100+ models)

### Use (for development)

First clone the repository:
```bash
$ git clone https://github.com/TPEOficial/dymo-code.git
$ cd dymo-code
```

We recommend using it in venv, but it is optional.

Now install the requirements:
```bash
$ pip install -r requirements.txt
```

Then, replace the `.env.example` file to `.env` and fill in the tokens you need.
```bash
# For production.
$ dymo-code
# For development (replace dymo-code with python run.py).
$ python run.py
```

### Main Features

| Name                                          | Status              | Active |
|-----------------------------------------------|---------------------|--------|
| AI Chat                                       | Active              |   ✅   |
| Parallel Multi-Agent	                        | Active              |   ✅   |
| Support for multiple AI providers             | Active              |   ✅   |
| Jailbreak Mode                                | In development      |   ⚠️   |
| MCP Support                                   | In BETA Phase       |   ⚠️   |
| Multi-Key Pool System                         | Active              |   ✅   |
| Theme System                                  | Active              |   ✅   |
| Search engine with bypass                     | Active              |   ✅   |
| Command Permission System                     | Active              |   ✅   |
| Advanced History Management System            | Active              |   ✅   |
| Automatic Prompt Improvement System           | Active              |   ✅   |

<details>
  <summary>Other features</summary>
  
| Name                                          | Status              | Active |
|-----------------------------------------------|---------------------|--------|
| Command Correction System                     | Active              |   ✅   |
| Scanning URLs before opening them             | Active              |   ✅   |
| Automatic API Key change when credits run out | Active              |   ✅   |
| Task Management System                        | Active              |   ✅   |
| Intelligent Self-Repair System                | Active              |   ✅   |

</details>

### Supported AI Models

| Provider                       | Models (Assorted)                             | Execution   | Rating  |
|--------------------------------|-----------------------------------------------|-------------|---------|
| Anthropic (Coming Soon)        | Exec `/models` command                        | API         | None    |
| Cerebras (Recommended)         | Exec `/models` command                        | API         | None    |
| TPEOficial (Coming Soon)       | Exec `/models` command                        | API         | None    |
| Google                         | Exec `/models` command                        | API         | None    |
| Groq (Recommended \| Default)  | Exec `/models` command                        | API         | None    |
| Meta (Coming Soon)             | Exec `/models` command                        | API         | None    |
| Ollama (Coming Soon)           | Exec `/models` command                        | Local       | None    |
| OpenAI (Coming Soon)           | Exec `/models` command                        | API         | None    |
| OpenRouter (Recommended)       | Exec `/models` command                        | API         | None    |
| Perplexity (Coming Soon)       | Exec `/models` command                        | API         | None    |

And coming soon...

## Frequently Asked Questions

<details>
  <summary>What is the Multi-Key Pool System?</summary>
  
  Multi-Key Pool is a system that automatically manages all the API keys from providers that you define internally in order to try to avoid rate limits and credit consumption.

  This system automatically consumes the different API keys and providers that you define in order to avoid consumption limitations from external providers.

  You can view your API Keys by running the command `/apikeys`.

  You can configure the logic of the Multi-Key Pool System using the `/keypool` command.
</details>

<details>
  <summary>Which is the best provider?</summary>
  
  The best provider is undoubtedly Anthropic with Claude in its latest version, but this option is the most expensive and limited of all.

  As an alternative option to avoid having to run it locally, we recommend **Groq**, which allows up to ~14,500K on average depending on the model per day, being quite fast and free.
</details>

<details>
  <summary>How do I enable URL security scanning before opening them?</summary>
  
  The steps to achieve this are quite simple.

  First, register with Dymo [here](https://dymo.tpeoficial.com/oauth).

  Then go to API Keys and create one. You can do this directly from [here](https://tpe.li/new-api-key).

  Now, simply using the command `setapikey dymo <your-api-key>` will configure it by default.

  By default, the URL scanning system is active, but you can disable it with the command `/urlverify off`.
</details>

<details>
  <summary>What is the Intelligent Self-Repair System?</summary>
  
  The Intelligent Self-Repair System manages and controls errors that occur during the use of Dymo Code, and attempts to handle them using tools and AI so that the process and assigned tasks can continue without having to stop execution.
</details>

#### Author
 - FJRG007
 - Email: [fjrg2007@tpeoficial.com](mailto:fjrg2007@tpeoficial.com)

#### License
The founder of the project, [TPEOficial](https://github.com/TPEOficial/), reserves the right to modify the license at any time.
This project is licensed under the terms of the [GNU Affero General Public License](./LICENSE).

<p align="right"><a href="#top">Back to top 🔼</a></p>