# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in paper-agent, please report
it privately via GitHub's private vulnerability reporting:

**https://github.com/croni4666-cmd/paper-agent/security/advisories/new**

Do **NOT** open a public GitHub issue for security vulnerabilities.

## Response Timeline

- **Initial response**: within 7 days
- **Triage and impact assessment**: within 14 days
- **Patch or mitigation**: within 30 days for high-severity issues,
  60 days for medium, 90 days for low

(These are soft targets for a personal hobby project; actual response
time may be longer.)

## Scope

This policy covers:
- Source code under `pa_cli/`, `tools/`, and other top-level Python
- Default configuration and example `.env.example`
- Public APIs and search engines integrated by `pa search`
- PDF download cascade in `pa fetch`

This policy does **not** cover:
- Third-party search engines and PDF sources (Crossref, OpenAlex,
  arXiv, Semantic Scholar, AMiner, CNKI, PubMed, ClinicalTrials.gov,
  Sci-Hub mirrors, Anna's Archive, Unpaywall). Report to those
  services directly.
- User-supplied credentials in `.env` — you are responsible for
  securing your own API keys.
- The user's local `~/.paper-agent/` directory (cross-Mavis-session
  SQLite pool). This contains user-labeled relevance data and is
  gitignored.

## Security Best Practices for Users

### 1. API key handling

- **Never commit `.env`** — it's in `.gitignore` already, but verify.
- **Use free-tier keys** where possible (all engines support keyless
  use; keys just raise rate limit).
- **Rotate keys periodically** if you suspect leakage.
- **Don't paste keys in GitHub issues** — they will be flagged as
  secrets by GitHub's automated scanning.

### 2. Proxy / network

- **Set `HTTPS_PROXY` correctly**. Common values:
  - `http://127.0.0.1:10808` (Clash on Windows after 2026-08-06) — local HTTP proxy, ACCEPTED with warning
  - `socks5://127.0.0.1:10808` (SOCKS5 variant)
  - `https://127.0.0.1:10809` (HTTPS proxy, best, encrypted CONNECT)
- **TLS validation** (v3.9.13.0+): `pa_cli/fetch.py:_validate_proxy_security()`
  - Local HTTP proxy (127.0.0.1, 10.*, 192.168.*, 172.16-31.*, ::1) → WARN but accept
  - Remote HTTP proxy → REFUSE with clear error (set `PAPER_AGENT_ALLOW_REMOTE_PROXY=1` to override)
  - Remote SOCKS5 proxy → REFUSE similarly
  - HTTPS proxy → silent (no leak)
- **Threat model**: HTTP proxy leaks the target hostname in the
  plaintext CONNECT handshake. After CONNECT, the data flow is
  TLS-encrypted to the destination, so API keys in URL (OpenAlex
  `?api_key=...`) are NOT visible to the proxy. Only the target
  hostname is. For local Clash this is acceptable; for REMOTE
  proxy this is a privacy leak.
- **Don't use sci-hub in jurisdictions where it's illegal**. The
  user is responsible for compliance with local laws.

### 3. CNKI cookies

- **Don't commit your `cnki.json`** (it's in `.gitignore`).
- **Re-export cookies every 4-8h** (CNKI session TTL).
- **Never share your cookies** — they identify you personally to
  CNKI.

### 4. Sample pool

- **Treat as user-private data**. The pool contains your
  relevance labels and queries, which may reflect your
  research interests. Don't share `~/.paper-agent/sample_pool/`
  unless you've anonymized it.
- The `pa sample-pool export` command writes to a path you choose
  (not the pool itself), so the export is safe to share if you
  choose to.

### 5. Privacy in your contributions

- **Don't include personal information** (school name, city, real
  name, Windows user path) in PRs, issues, or commits.
- The repo has a sanitize script (`test_output/_pre_github_secret_scan.py`)
  that catches most accidental leaks. Run it before `git push`.

## Known Limitations

These are accepted limitations of the current design, not bugs:

1. **API keys in URL query params** (OpenAlex). This is the official
   OpenAlex API pattern; we don't control it. Mitigation: v3.9.13.0+
   enforces local proxy only, so even if the proxy is logging the
   URL, it's only the user's own proxy (not a third party). API key
   visibility is limited to the user themselves + OpenAlex.

2. **No TLS pinning**. We rely on the system TLS store. Compromise
   of a CA would allow MITM. Acceptable risk for a research tool.

3. **Sci-Hub mirrors may serve arbitrary content**. Last-resort
   channel. We do not validate the integrity of returned PDFs.
   Mitigation: verify checksums for any PDF you intend to use in
   published work.

4. **CNKI proxy IP discovery via redirect**. The example IP
   `120.53.241.46:5888` in `pa_cli/cnki_channel.py` docstring is
   a known endpoint at the time of writing; the actual IP is
   load-balanced. Not a security concern (the connection is over
   user cookies, not auth tokens).

5. **Branch protection on main allows direct push** (no required
   PR reviews) because this is a single-maintainer hobby project.
   If you fork, consider stricter rules.

## Vulnerability Disclosure History

No publicly disclosed vulnerabilities as of 2026-08-14.

## Acknowledgments

Thanks to researchers who report vulnerabilities responsibly.
