# Memoria Cloud CLI

```bash
pip install memoria-cloud-cli
```

```bash
export MEMORY_API_KEY=mem_...
memoria-cloud recall "pytest"
memoria-cloud remember "We prefer pytest" --session s1
```

Config file: `~/.config/memoria-cloud/config.toml` (`memoria-cloud config --api-key mem_...`).
Flags `--api-key` / `--url` override env, which overrides the config file.
