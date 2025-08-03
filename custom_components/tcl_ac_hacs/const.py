from homeassistant.const import CONF_DEVICES

# Core integration constants
DOMAIN = "tcl_ac_hacs"
API_PARAM_POWER_SWITCH = "powerSwitch"
API_PARAM_VERTICAL_DIRECTION = "verticalDirection"
API_PARAM_HORIZONTAL_DIRECTION = "horizontalDirection"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_REGION = "region"
CONF_DEVICES = "devices"
CONF_SELECTED_DEVICES = "selected_devices"

# Fresh Air API parameters
API_PARAM_NEW_WIND_SET_MODE = "newWindSetMode"
API_PARAM_NEW_WIND_STRENGTH = "newWindStrength"
API_PARAM_NEW_WIND_AUTO_SWITCH = "newWindAutoSwitch"
API_PARAM_NEW_WIND_SWITCH = "newWindSwitch" # For master on/off of fresh air
API_PARAM_SELF_CLEAN = "selfClean" # Added based on new log

# Fresh Air Modes (for newWindSetMode)
API_FRESH_AIR_MODE_FRESH = 1
API_FRESH_AIR_MODE_BREATHING = 2
API_FRESH_AIR_MODE_EXHAUST = 3
API_FRESH_AIR_MODE_PURIFICATION = 4
# It might be useful to have a "OFF" or "Disabled" mode if the API supports it
# or if not sending newWindSetMode effectively turns it off.
# For now, we'll assume turning off is handled by strength or a specific command.

# Fresh Air Speeds (for newWindStrength) - numerical 1, 2, 3
# These will be mapped to HA fan speeds (e.g., low, medium, high)

# Fresh Air Auto Switch (for newWindAutoSwitch)
API_FRESH_AIR_AUTO_OFF = 0
API_FRESH_AIR_AUTO_ON = 1

# Fan entity presets mapping
PRESET_FRESH_AIR_FRESH = "Fresh Air"
PRESET_FRESH_AIR_BREATHING = "Breathing"
PRESET_FRESH_AIR_EXHAUST = "Exhaust"
PRESET_FRESH_AIR_PURIFICATION = "Purification"

# Fan entity speed mapping (example, can be adjusted)
FAN_SPEED_LOW = "low"
FAN_SPEED_MEDIUM = "medium"
FAN_SPEED_HIGH = "high"
FAN_SPEED_AUTO = "auto"
PLATFORMS = ["climate", "fan"]
DEFAULT_SCAN_INTERVAL = 180  # Default update interval in seconds

# API constants
ACCOUNT_LOGIN_URL = "https://pa.account.tcl.com/account/login?clientId=54148614"
REFRESH_TOKENS_URL = "https://prod-eu.aws.tcljd.com/v3/auth/refresh_tokens"
GET_THINGS_URL = "https://prod-eu.aws.tcljd.com/v3/user/get_things"
APP_ID = "wx6e1af3fa84fbe523"
CLIENT_ID = "54148614"
TH_PLATFORM = "android"
TH_VERSION = "4.8.1" 
TH_APPBUILD = "830"
USER_AGENT = "Android"
CONTENT_TYPE = "application/json"
AWS_COGNITO_URL = "https://cognito-identity.eu-central-1.amazonaws.com/"
AWS_IOT_ENDPOINT = "a2qjkbbsk6qn2u-ats.iot.eu-central-1.amazonaws.com"
AWS_IOT_REGION = "eu-central-1"
HARDCODED_IDENTITY_ID = "eu-central-1:61e8f839-2d72-c035-a2bf-7ef50a856ddd"
CONF_SELECTED_DEVICES = "selected_devices"
