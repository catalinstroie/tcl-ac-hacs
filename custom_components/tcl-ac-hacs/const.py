# custom_components/tcl_ac_controller/const.py
DOMAIN = "tcl_ac_controller"
PLATFORMS = ["climate"]

# Configuration
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SELECTED_DEVICES = "selected_devices"

# API Endpoints and Constants from your script
CLIENT_ID = "54148614"
ACCOUNT_LOGIN_URL = "https://pa.account.tcl.com/account/login?clientId={}"
USER_AGENT = "Android" # Or a more HA specific one if preferred
CONTENT_TYPE = "application/json; charset=UTF-8"
GET_THINGS_URL = "https://prod-eu.aws.tcljd.com/v3/user/get_things"
TH_PLATFORM = "android"
TH_VERSION = "4.8.1"
TH_APPBUILD = "830" # Note: original script had "th_appbulid" - typo?
REFRESH_TOKENS_URL = "https://prod-eu.aws.tcljd.com/v3/auth/refresh_tokens"
APP_ID = "wx6e1af3fa84fbe523"
AWS_COGNITO_URL = "https://cognito-identity.eu-central-1.amazonaws.com/"
AWS_IOT_REGION = "eu-central-1"
AWS_IOT_ENDPOINT = "a2qjkbbsk6qn2u-ats.iot.eu-central-1.amazonaws.com"

HARDCODED_IDENTITY_ID = "eu-central-1:61e8f839-2d72-c035-a2bf-7ef50a856ddd"
# IDENTITY_POOL_ID = "eu-central-1:83840aed-13f2-4c1d-8eaf-9df7f2daaee3" # Not used in active code

DEFAULT_SCAN_INTERVAL = 60 # seconds for polling