# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in the Trust Scorecard project, please report it responsibly:

**DO NOT** open a public issue for security vulnerabilities.

Instead, please use GitHub's private vulnerability reporting mechanism for this
repository (see the repository's **Security** tab and submit a private report
there).

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will respond within 48 hours and work with you to address the issue.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Considerations

This project:
- Fetches data from external benchmark leaderboards
- Stores evaluation results locally in SQLite
- Does NOT handle sensitive user data
- Does NOT require authentication tokens by default

### Best Practices

When using trust-scorecard:
- Do not commit `.env` files or API keys to the repository
- Review benchmark data sources before trusting results
- Use pinned dependency versions in production
- Enable CodeQL scanning in your fork

## Security Features

- **Dependency scanning** via Dependabot
- **Code scanning** via CodeQL
- **Sandboxed execution** - no arbitrary code execution from model cards
- **Input validation** - all claims validated via Pydantic models
