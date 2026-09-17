# Security Policy

## Reporting a vulnerability

Please do not open a public issue for a suspected security vulnerability.

Report security issues privately to the repository owner through the contact method listed on the GitHub profile. Include a clear description, affected component, reproduction steps, and potential impact.

## Security design goals

ForgeAI is designed to keep external integrations behind adapters, validate upstream data before analysis, avoid logging credentials, and fail closed when required review inputs are malformed.

The project is a portfolio and engineering research implementation. Do not use it as an automated production merge authority without an independent security review and appropriate GitHub permissions controls.
