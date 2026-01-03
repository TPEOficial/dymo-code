"""
Project Initialization for Dymo Code
Creates .dmcode folder and AGENTS.md file for AI agent guidance
Based on the AGENTS.md open format specification (https://agents.md/)
"""

import os
import json
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from datetime import datetime


def detect_project_type() -> Dict[str, Any]:
    """
    Detect project type and characteristics by analyzing files in current directory.
    Returns a dictionary with project information.
    """
    cwd = Path(os.getcwd())
    project_info = {
        "name": cwd.name,
        "type": "unknown",
        "language": None,
        "framework": None,
        "package_manager": None,
        "has_tests": False,
        "has_docs": False,
        "has_ci": False,
        "build_commands": [],
        "test_commands": [],
        "lint_commands": [],
    }

    # Detect by configuration files
    config_files = {
        # Python
        "pyproject.toml": {"language": "Python", "package_manager": "pip/poetry"},
        "setup.py": {"language": "Python", "package_manager": "pip"},
        "requirements.txt": {"language": "Python", "package_manager": "pip"},
        "Pipfile": {"language": "Python", "package_manager": "pipenv"},
        # JavaScript/TypeScript
        "package.json": {"language": "JavaScript/TypeScript", "package_manager": "npm/yarn"},
        "yarn.lock": {"package_manager": "yarn"},
        "pnpm-lock.yaml": {"package_manager": "pnpm"},
        "bun.lockb": {"package_manager": "bun"},
        # Rust
        "Cargo.toml": {"language": "Rust", "package_manager": "cargo"},
        # Go
        "go.mod": {"language": "Go", "package_manager": "go"},
        # Java/Kotlin
        "pom.xml": {"language": "Java", "package_manager": "maven"},
        "build.gradle": {"language": "Java/Kotlin", "package_manager": "gradle"},
        "build.gradle.kts": {"language": "Kotlin", "package_manager": "gradle"},
        # Ruby
        "Gemfile": {"language": "Ruby", "package_manager": "bundler"},
        # PHP
        "composer.json": {"language": "PHP", "package_manager": "composer"},
        # .NET
        "*.csproj": {"language": "C#", "package_manager": "dotnet"},
        "*.fsproj": {"language": "F#", "package_manager": "dotnet"},
    }

    for config_file, info in config_files.items():
        if "*" in config_file:
            # Glob pattern
            pattern = config_file
            if list(cwd.glob(pattern)):
                project_info.update(info)
                break
        elif (cwd / config_file).exists():
            project_info.update(info)
            break

    # Detect framework from package.json
    package_json = cwd / "package.json"
    if package_json.exists():
        try:
            with open(package_json, "r", encoding="utf-8") as f:
                pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                # Detect frameworks
                if "next" in deps:
                    project_info["framework"] = "Next.js"
                elif "react" in deps:
                    project_info["framework"] = "React"
                elif "vue" in deps:
                    project_info["framework"] = "Vue.js"
                elif "svelte" in deps:
                    project_info["framework"] = "Svelte"
                elif "angular" in deps or "@angular/core" in deps:
                    project_info["framework"] = "Angular"
                elif "express" in deps:
                    project_info["framework"] = "Express.js"
                elif "fastify" in deps:
                    project_info["framework"] = "Fastify"

                # Detect TypeScript
                if "typescript" in deps:
                    project_info["language"] = "TypeScript"

                # Get scripts
                scripts = pkg.get("scripts", {})
                if "build" in scripts:
                    project_info["build_commands"].append("npm run build")
                if "test" in scripts:
                    project_info["test_commands"].append("npm test")
                    project_info["has_tests"] = True
                if "lint" in scripts:
                    project_info["lint_commands"].append("npm run lint")

                # Get project name
                if "name" in pkg:
                    project_info["name"] = pkg["name"]

        except (json.JSONDecodeError, IOError):
            pass

    # Detect Python framework
    if project_info["language"] == "Python":
        requirements_files = ["requirements.txt", "pyproject.toml", "setup.py"]
        for req_file in requirements_files:
            req_path = cwd / req_file
            if req_path.exists():
                try:
                    content = req_path.read_text(encoding="utf-8").lower()
                    if "django" in content:
                        project_info["framework"] = "Django"
                    elif "flask" in content:
                        project_info["framework"] = "Flask"
                    elif "fastapi" in content:
                        project_info["framework"] = "FastAPI"
                    elif "pytorch" in content or "torch" in content:
                        project_info["framework"] = "PyTorch"
                    elif "tensorflow" in content:
                        project_info["framework"] = "TensorFlow"
                    break
                except IOError:
                    pass

        # Default Python commands
        if not project_info["build_commands"]:
            project_info["build_commands"].append("pip install -e .")
        if not project_info["test_commands"]:
            if (cwd / "pytest.ini").exists() or (cwd / "tests").exists():
                project_info["test_commands"].append("pytest")
                project_info["has_tests"] = True
        if not project_info["lint_commands"]:
            project_info["lint_commands"].append("ruff check .")

    # Detect test directories
    test_dirs = ["tests", "test", "spec", "__tests__", "specs"]
    for test_dir in test_dirs:
        if (cwd / test_dir).is_dir():
            project_info["has_tests"] = True
            break

    # Detect documentation
    doc_indicators = ["docs", "documentation", "README.md", "CONTRIBUTING.md"]
    for doc in doc_indicators:
        if (cwd / doc).exists():
            project_info["has_docs"] = True
            break

    # Detect CI/CD
    ci_indicators = [".github/workflows", ".gitlab-ci.yml", "Jenkinsfile", ".circleci", ".travis.yml"]
    for ci in ci_indicators:
        if (cwd / ci).exists():
            project_info["has_ci"] = True
            break

    return project_info


def generate_agents_md(project_info: Dict[str, Any]) -> str:
    """
    Generate AGENTS.md content based on project information.
    Follows the AGENTS.md open format specification.
    """
    lines = [
        "# AGENTS.md",
        "",
        f"<!-- Generated by Dymo Code on {datetime.now().strftime('%Y-%m-%d')} -->",
        f"<!-- AGENTS.md format: https://agents.md/ -->",
        "",
        "## Project Overview",
        "",
        f"**Project Name:** {project_info['name']}",
    ]

    if project_info["language"]:
        lines.append(f"**Language:** {project_info['language']}")

    if project_info["framework"]:
        lines.append(f"**Framework:** {project_info['framework']}")

    if project_info["package_manager"]:
        lines.append(f"**Package Manager:** {project_info['package_manager']}")

    lines.extend([
        "",
        "## Build and Test Commands",
        "",
    ])

    if project_info["build_commands"]:
        lines.append("### Build")
        lines.append("```bash")
        for cmd in project_info["build_commands"]:
            lines.append(cmd)
        lines.append("```")
        lines.append("")

    if project_info["test_commands"]:
        lines.append("### Test")
        lines.append("```bash")
        for cmd in project_info["test_commands"]:
            lines.append(cmd)
        lines.append("```")
        lines.append("")

    if project_info["lint_commands"]:
        lines.append("### Lint")
        lines.append("```bash")
        for cmd in project_info["lint_commands"]:
            lines.append(cmd)
        lines.append("```")
        lines.append("")

    lines.extend([
        "## Code Style Guidelines",
        "",
        "<!-- Add your code style guidelines here -->",
        "- Follow existing code patterns in the codebase",
        "- Use meaningful variable and function names",
        "- Add comments for complex logic",
        "- Keep functions focused and small",
        "",
        "## Testing Instructions",
        "",
    ])

    if project_info["has_tests"]:
        lines.extend([
            "This project has tests. When making changes:",
            "1. Run existing tests to ensure nothing breaks",
            "2. Add new tests for new functionality",
            "3. Update tests if behavior changes intentionally",
            "",
        ])
    else:
        lines.extend([
            "<!-- Add testing instructions here -->",
            "- No test suite detected",
            "- Consider adding tests for new features",
            "",
        ])

    lines.extend([
        "## Security Considerations",
        "",
        "- Never commit secrets, API keys, or credentials",
        "- Validate all user inputs",
        "- Use parameterized queries for database operations",
        "- Follow OWASP security guidelines",
        "",
        "## Development Environment",
        "",
    ])

    if project_info["package_manager"]:
        lines.append(f"- Use `{project_info['package_manager']}` for dependency management")

    lines.extend([
        "- Follow the project's existing configuration",
        "- Check for `.env.example` for required environment variables",
        "",
        "## PR Instructions",
        "",
        "When creating pull requests:",
        "- Write clear, descriptive commit messages",
        "- Reference related issues when applicable",
        "- Ensure all tests pass before submitting",
        "- Update documentation if needed",
        "",
        "---",
        "",
        "*This file guides AI coding agents working on this project.*",
        "*Edit it to add project-specific instructions and context.*",
    ])

    return "\n".join(lines)


def initialize_project() -> Tuple[bool, str]:
    """
    Initialize .dmcode folder and create AGENTS.md file.

    Returns:
        Tuple of (success: bool, message: str)
    """
    cwd = Path(os.getcwd())
    dmcode_dir = cwd / ".dmcode"
    agents_file = dmcode_dir / "AGENTS.md"

    try:
        # Create .dmcode directory if it doesn't exist
        if not dmcode_dir.exists():
            dmcode_dir.mkdir(parents=True)

        # Check if AGENTS.md already exists
        if agents_file.exists():
            return False, f"AGENTS.md already exists at {agents_file}"

        # Detect project information
        project_info = detect_project_type()

        # Generate AGENTS.md content
        content = generate_agents_md(project_info)

        # Write the file
        agents_file.write_text(content, encoding="utf-8")

        # Also add .dmcode to .gitignore if git repo
        gitignore = cwd / ".gitignore"
        if (cwd / ".git").exists():
            if gitignore.exists():
                existing = gitignore.read_text(encoding="utf-8")
                if ".dmcode" not in existing:
                    with open(gitignore, "a", encoding="utf-8") as f:
                        if not existing.endswith("\n"):
                            f.write("\n")
                        f.write("\n# Dymo Code configuration\n.dmcode/\n")
            else:
                gitignore.write_text("# Dymo Code configuration\n.dmcode/\n", encoding="utf-8")

        return True, f"Initialized .dmcode folder with AGENTS.md at {agents_file}"

    except PermissionError:
        return False, f"Permission denied: Cannot create {dmcode_dir}"
    except Exception as e:
        return False, f"Failed to initialize: {str(e)}"


def get_agents_md_content() -> Optional[str]:
    """
    Read AGENTS.md content if it exists.

    Returns:
        Content of AGENTS.md or None if not found
    """
    cwd = Path(os.getcwd())

    # Check multiple possible locations
    locations = [
        cwd / ".dmcode" / "AGENTS.md",
        cwd / "AGENTS.md",
        cwd / ".github" / "AGENTS.md",
    ]

    for location in locations:
        if location.exists():
            try:
                return location.read_text(encoding="utf-8")
            except IOError:
                continue

    return None
