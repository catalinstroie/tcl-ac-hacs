# System Patterns: TCL AC Controller HACS Integration

## System Architecture
- Follows Home Assistant custom component structure under `custom_components/tcl-ac-hacs`.
- Uses a config flow for UI-based configuration.
- Communicates with TCL's cloud API for device control and status.

## Key Technical Decisions
- Domain, folder, and repository names are aligned for HACS compliance.
- All metadata and documentation fields are set for HACS validation.
- Integration is designed for cloud polling (`iot_class: cloud_polled`).

## Design Patterns
- Separation of concerns: API communication, device logic, and Home Assistant integration are modularized.
- Uses Home Assistant's async patterns for I/O operations.
- Configuration and setup handled via config_flow.py for user-friendly onboarding.

## Component Relationships
- `__init__.py`: Initializes the integration and sets up platforms.
- `api.py`: Handles communication with TCL's cloud API.
- `climate.py`: Implements the Home Assistant climate platform for TCL AC devices.
- `config_flow.py`: Manages the configuration flow for UI setup.
- `const.py`: Stores constants used throughout the integration.
- `manifest.json`: Metadata for HACS and Home Assistant.
- `strings.json` and `translations/`: Provide localization support.

## Critical Implementation Paths
- User installs via HACS → Adds integration in Home Assistant UI → Config flow authenticates and discovers devices → Devices are added as climate entities → API polling keeps state updated.
