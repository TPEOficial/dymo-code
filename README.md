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

### Use

1. First, download the latest version of Dymo Code from the [releases](https://github.com/TPEOficial/dymo-code/releases).

2. Go to the folder where you want to initialize the project.

3. If the binary has been correctly set in the PATH, you can run it as `dymo-code`. Otherwise, you will have to do it manually if you prefer.

4. Enter the empty or existing project you created and run `dymo-code` or the binary path or command if you defined it in the PATH.

5A. If this is your first time doing this, most providers will ask you for an API key. In Dymo Code, run the command `/getapikey <provider>`.

5B. If this is your first time, for most providers you will need an API Key. Once you have it, in Dymo Code, run the command `/setapikey <provider> <apikey>`.

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
| AI Chat                                       | In development      |   ✅   |
| Parallel Multi-Agent	                        | Active              |   ✅   |
| Support for multiple AI providers             | In development      |   ⚠️   |
| Jailbreak Mode                                | In development      |   ⚠️   |
| MCP Support                                   | In BETA Phase       |   ⚠️   |
| Multi-Key Pool System                         | Active              |   ✅   |
| Theme System                                  | Active              |   ✅   |
| Search engine with bypass                     | Active              |   ✅   |
| Command Permission System                     | Active              |   ✅   |
| Advanced History Management System            | Active              |   ✅   |

<details>
  <summary>Other features</summary>
  
| Name                                          | Status              | Active |
|-----------------------------------------------|---------------------|--------|
| Command Correction System                     | Active              |   ✅   |
| Scanning URLs before opening them             | In development      |   ⚠️   |
| Automatic API Key change when credits run out | Active              |   ✅   |
| Task Management System                        | Active              |   ✅   |

</details>

### Supported AI Models

| Provider                       | Models (Assorted)                             | Execution   | Rating  |
|--------------------------------|-----------------------------------------------|-------------|---------|
| Anthropic (Coming Soon)        | To be specified shortly                       | API         | None    |
| TPEOficial (Coming Soon)       | To be specified shortly                       | API         | None    |
| Google (Coming Soon)           | To be specified shortly                       | API         | None    |
| Groq (Recommended \| Default)  | To be specified shortly                       | API         | None    |
| Meta (Coming Soon)             | To be specified shortly                       | API         | None    |
| Ollama (Coming Soon)           | To be specified shortly                       | Local       | None    |
| OpenAI (Coming Soon)           | To be specified shortly                       | API         | None    |
| OpenRouter (Coming Soon)       | To be specified shortly                       | API         | None    |
| Perplexity (Coming Soon)       | To be specified shortly                       | API         | None    |

And coming soon...

# Frequently Asked Questions

<details>
  <summary>What is the Multi-Key Pool System?</summary>
  
  Multi-Key Pool is a system that automatically manages all the API keys from providers that you define internally in order to try to avoid rate limits and credit consumption.

  This system automatically consumes the different API keys and providers that you define in order to avoid consumption limitations from external providers.

  You can view your API Keys by running the command `/apikeys`.
</details>

<details>
  <summary>Which is the best provider?</summary>
  
  The best provider is undoubtedly Anthropic with Claude in its latest version, but this option is the most expensive and limited of all.

  As an alternative option to avoid having to run it locally, we recommend **Groq**, which allows up to ~14,500K on average depending on the model per day, being quite fast and free.
</details>

#### Author
 - FJRG007
 - Email: [fjrg2007@tpeoficial.com](mailto:fjrg2007@tpeoficial.com)

#### License
The founder of the project, [TPEOficial](https://github.com/TPEOficial/), reserves the right to modify the license at any time.
This project is licensed under the terms of the [GNU Affero General Public License](./LICENSE).

<p align="right"><a href="#top">Back to top 🔼</a></p>