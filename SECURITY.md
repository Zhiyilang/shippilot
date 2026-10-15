# Security policy

## Supported versions

Only the latest released minor version receives security fixes.

## Reporting a vulnerability

Open a confidential issue or contact the maintainers directly. Include
reproduction steps, the affected version, and the impact you believe it has.

## Scope note

ShipPilot reports on secrets and dangerous calls, but it is a static inspector.
It will not catch a credential that is assembled at runtime, and a clean run is
not a security audit. Waivers in `.shippilot/waivers.json` are recorded
decisions, not remediation.

## Response target

Acknowledgement within 3 business days; a fix or a documented mitigation within
30 days.
