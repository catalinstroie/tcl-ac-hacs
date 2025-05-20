# Tech Context: TCL AC Controller HACS Integration

## Technologies Used
- **Home Assistant**: Target platform for the integration.
- **Python 3.9+**: Primary programming language.
- **HACS (Home Assistant Community Store)**: Distribution and update channel.
- **aiohttp**: Async HTTP client for API communication.
- **requests_aws4auth**, **pyjwt**: For authentication and API requests.

## Development Setup
- Project root contains `custom_components/tcl-ac-hacs` with all integration code.
- Development and testing are performed in a Home Assistant dev environment.
- Version control via Git and GitHub.

## Technical Constraints
- Must comply with Home Assistant and HACS custom integration requirements.
- All dependencies must be installable via pip.
- Async I/O for all network operations.
- No external binaries or compiled code.

## Dependencies
- Listed in `manifest.json` under `requirements`.
- All dependencies are pure Python and compatible with Home Assistant.

## Tool Usage Patterns
- Use of config flow for UI-based configuration.
- Logging via Home Assistant's logger.
- Localization via `strings.json` and `translations/`.
- Documentation maintained in `README.md` and `info.md`.
