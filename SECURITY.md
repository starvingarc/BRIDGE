# Security Policy

## Reporting a vulnerability

For security or privacy issues, message the repository owner directly through
the team's existing private chat. Do not put credentials, private data or
vulnerability details in Issues or PRs.

Reports identify the affected BRIDGE commit or Tool Package version, the
smallest safe reproduction, expected impact and whether sensitive material may
have been exposed. Additional protected evidence is handled through the private
reporting channel.

## Supported version

The supported tagged release is `v0.3.0`, a private, single-operator research
release. There is no public stable release qualified by this development
repository's release process; release scope is maintained in [RELEASE](docs/RELEASE.md).
Security fixes target `main` through PRs. This policy does not mean GitHub
branch protection is enabled. Engineering support
does not imply scientific, clinical, safety, potency or GMP validation.

## Internal account testing

Web authentication uses individual accounts for local and internal testing. Session resources require
ownership; administrator cross-account reads are audited and allowlisted. Personal model
credentials remain private and outbound connections reject unapproved private destinations.
Public HTTPS origins require a trusted loopback proxy. Legacy shared tokens cannot log in.
This does not qualify public registration. Deployment and backup boundaries are in the
[Web guide](docs/web-preview.md#internal-multi-user-testing).
