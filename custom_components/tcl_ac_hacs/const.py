from homeassistant.const import CONF_DEVICES

# Core integration constants
DOMAIN = "tcl_ac_hacs"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_REGION = "region"
CONF_DEVICES = "devices"
CONF_SELECTED_DEVICES = "selected_devices"
PLATFORMS = ["climate"]
DEFAULT_SCAN_INTERVAL = 1800  # Default update interval in seconds

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
