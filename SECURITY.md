# Security

## Secrets policy

- **Never** commit API keys, Telegram bot tokens, or chat IDs. Use a local `.env` file (see `.env.example`).
- `config.py` only reads `os.getenv("ENTSOE_API_KEY")`; it does not store secrets.
- If you ever pasted a token into a file that was committed, **rotate that credential immediately** (ENTSO-E portal for API keys; [@BotFather](https://t.me/BotFather) for Telegram tokens). Removing the file from the latest commit does **not** remove it from Git history.

## Past exposure

`admin.txt` previously contained a real ENTSO-E API key and was tracked in Git. That key must be **revoked and replaced** in the [ENTSO-E Transparency Platform](https://newtransparency.entsoe.eu/) even if the file is removed from the repository.

To remove sensitive data from **all** past commits on GitHub, use [GitHub’s guide on removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) or a history-rewriting tool; coordinate with anyone who has cloned the repo.

## Local machine

- Shell history (e.g. `curl` with `bot<TOKEN>`) can leak tokens. Clear or avoid commands that embed secrets, and rotate any token that appeared in history.
- Do not log or print environment variables that hold secrets.

## Reporting

If you find a security issue in this project, open a private advisory or contact the maintainer directly rather than filing a public issue with exploit details.
