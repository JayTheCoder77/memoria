# Memoria Cloud CLI

```bash
pip install memoria-cloud-cli
```

```bash
export MEMORY_API_KEY=mem_...
memoria-cloud recall "what test runner do we use?"
memoria-cloud remember "We prefer pytest" --session s1
```

The recall argument is the search question in plain language (sent as `q`).
`--session` is a label you invent; required on remember/emit.

Config file: `~/.config/memoria-cloud/config.toml` (`memoria-cloud config --api-key mem_...`).
Flags `--api-key` / `--url` override env, which overrides the config file.

Full argument list: website `/docs/cli`.
