# Codex Skill Check

Check which skills a local Codex installation can see in a specific workspace. After installing or updating a skill pack, run the checker before starting a chat. A missing or disabled skill gives a failing exit code you can use in a setup script.

This standalone Python tool grew out of a local validation script for a Roblox development setup. That script checked a fixed list of 32 expected skills and searched for an associated command hook. This version accepts the names and command fragments on the command line.

## Quick start

You need Python 3.8 or later and a local Codex CLI with the app-server protocol. The checker uses only the Python standard library. From the directory containing `skill_check.py`, list enabled skill names for the current workspace:

```sh
python skill_check.py
```

Use `python3` if that is your Python launcher. To inspect a different workspace, pass its path with `--cwd`. Pick an exact skill name from its listing, then check for it by name:

```sh
python skill_check.py --cwd "../my-project"
python skill_check.py --cwd "../my-project" --skill release-notes
```

For a workspace with an enabled skill named `release-notes`, the second command prints:

```text
OK  skill release-notes
```

If the skill is disabled or absent, the same command prints `MISSING  skill release-notes` and exits with code 1. The example skill name stands for one from your installation.

## Check a skill pack

```sh
python skill_check.py --cwd "../my-project" --skill release-notes --skill changelog-review --hook-contains check-changelog
```

Each requested skill must be enabled. Each hook fragment must occur in at least one enabled command hook in that workspace. Hook matching is case-insensitive. The checker only inspects hook configuration. A match does not establish trust, execute the hook, or prove it will succeed at runtime.

| Exit code | Meaning |
| --- | --- |
| 0 | Discovery succeeded and every requested check passed. With no checks, listing succeeded. |
| 1 | Discovery succeeded and at least one requested item was missing or disabled. |
| 2 | Invalid arguments, unavailable executable, incompatible protocol, timeout, or discovery error. |

## How discovery works

The tool launches `codex app-server` over standard input/output, initializes a connection, and calls `skills/list` with a forced reload. It requests `hooks/list` only when you supply `--hook-contains`. It sends no model prompt. Codex reads the configuration available to the current user and workspace. The checker gives the server a temporary SQLite directory for the duration of the check.

Tested with Codex CLI `0.171.0-alpha.13` on Windows. The hook protocol is experimental. If discovery fails at startup, verify that `codex --version` and `codex app-server --help` work in the same terminal. Use `--codex` with an absolute executable path if Codex is installed outside your PATH.

## License

MIT. See [LICENSE](LICENSE).
