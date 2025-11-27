#!/usr/bin/env python3
"""Build installer artifacts from templates and configuration."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any, Dict

import yaml
from jinja2 import Environment, FileSystemLoader


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file from ``path`` and return a dictionary."""
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``override`` into ``base`` without mutating inputs."""
    merged: Dict[str, Any] = {**base}
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def build_context(default_config: Path, override_config: Path | None) -> Dict[str, Any]:
    """Load configuration files and return a merged context dictionary."""
    config = load_yaml(default_config)
    if override_config:
        overrides = load_yaml(override_config)
        config = deep_merge(config, overrides)
    context: Dict[str, Any] = {**config, "config": config}
    return context


def validate_config(config: Dict[str, Any]) -> None:
    """Perform lightweight validation to ensure required sections exist."""

    if not config:
        raise ValueError("Configuration is empty after loading and merging YAML files.")

    required_sections = [
        "app",
        "installer",
        "docker",
    ]

    missing = [key for key in required_sections if key not in config]
    if missing:
        raise ValueError(f"Missing required configuration sections: {', '.join(missing)}")


def render_templates(
    template_dir: Path, output_dir: Path, context: Dict[str, Any], force: bool
) -> None:
    """Render all Jinja2 templates under ``template_dir`` to ``output_dir``."""
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=False,
        keep_trailing_newline=True,
    )

    templates = env.list_templates(filter_func=lambda name: name.endswith(".j2"))
    rendered_count = 0
    for template_name in templates:
        template = env.get_template(template_name)
        relative_output = Path(template_name[:-3])

        if relative_output.name == "installer.sh":
            relative_output = relative_output.with_name("homelab-install.sh")

        output_path = output_dir / relative_output
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists() and not force:
            raise FileExistsError(
                f"Refusing to overwrite existing artifact: {output_path} (use --force)"
            )

        logging.info("Rendering %s -> %s", template_name, output_path)
        rendered = template.render(**context)
        output_path.write_text(rendered, encoding="utf-8")

        if output_path.suffix == ".sh":
            output_path.chmod(0o755)

        rendered_count += 1

    logging.info("Rendered %s templates to %s", rendered_count, output_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render installer artifacts from templates using configuration defaults.",
    )
    parser.add_argument(
        "--config",
        default=Path("config/defaults.yaml"),
        type=Path,
        help="Path to the base configuration YAML file.",
    )
    parser.add_argument(
        "--override",
        type=Path,
        help="Optional path to an overrides YAML file.",
    )
    parser.add_argument(
        "--templates",
        default=Path("templates"),
        type=Path,
        help="Directory containing Jinja2 templates.",
    )
    parser.add_argument(
        "--output-dir",
        default=Path("build"),
        type=Path,
        help="Directory where rendered artifacts are written.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing artifacts in the output directory.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging for additional build details.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(levelname)s] %(message)s",
    )

    if not args.config.exists():
        raise FileNotFoundError(f"Base configuration not found: {args.config}")
    if args.override and not args.override.exists():
        raise FileNotFoundError(f"Override configuration not found: {args.override}")
    if not args.templates.exists():
        raise FileNotFoundError(f"Templates directory not found: {args.templates}")

    context = build_context(args.config, args.override)
    validate_config(context)
    render_templates(args.templates, args.output_dir, context, args.force)

    logging.info("Build completed. Artifacts available in %s", args.output_dir)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
