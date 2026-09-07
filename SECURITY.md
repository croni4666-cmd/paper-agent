# Security Policy

## Reporting a Vulnerability

Please report security vulnerabilities privately through
[GitHub private vulnerability reporting](https://github.com/croni4666-cmd/paper-agent/security/advisories/new).
Do not publish exploitable details in a public issue before a fix is available.

## Scope

This policy covers the released source code, command-line interfaces, default
configuration, search providers, and PDF download channels. It does not cover
third-party services or user-managed credentials and local data.

## Credential Handling

- Keep API keys in an untracked .env file or environment variables.
- Never commit .env, private keys, browser cookies, or proxy credentials.
- Do not include credentials in issue reports or terminal captures.
- Rotate a credential if it may have appeared in an external log or commit.

## Network and Proxy Handling

All paper-agent network paths use the shared HTTP layer for proxy checks.

- Local HTTP and SOCKS proxies are permitted with a warning because their
  hostname handshake can be visible on the local network path.
- Remote HTTP and SOCKS proxies are refused by default. Set
  PAPER_AGENT_ALLOW_REMOTE_PROXY=1 only when the proxy and network are
  trusted.
- HTTPS proxies are preferred because their CONNECT handshake is encrypted.
- Proxy URLs are redacted in paper-agent status messages, warnings, and
  validation errors. Do not rely on this to protect credentials from shell
  history; use environment variables where practical.

## Known Limitations

- OpenAlex may require an API key in its URL query string, as specified by its
  public API. The connection uses standard HTTPS certificate verification.
- The project relies on the operating system's trusted CA store and does not
  implement certificate pinning.
- Third-party PDF sources can change or return invalid content. Check a
  downloaded PDF before relying on it in a research workflow.
- A repository maintainer can improve protection by enabling GitHub branch
  protection and secret scanning.

## Response Targets

The maintainer aims to acknowledge reports within seven days, assess them
within fourteen days, and publish a fix or mitigation according to severity.

## Audit History

The 2026-09 security audit added proxy credential redaction, routed download
channels through the shared proxy validator, and removed process-global proxy
installation from JATS figure downloads.
