# custom_components/tcl_ac_hacs/api.py
import asyncio
import base64
import hashlib
import json
import os
import time
import datetime
import logging
from typing import Any, Dict, Optional

import aiohttp
import jwt # PyJWT
from requests_aws4auth import AWS4Auth # Still using this for simplicity with executor

from .const import (
    ACCOUNT_LOGIN_URL, APP_ID, AWS_COGNITO_URL, AWS_IOT_ENDPOINT, AWS_IOT_REGION,
    CLIENT_ID, CONTENT_TYPE, GET_THINGS_URL, HARDCODED_IDENTITY_ID,
    REFRESH_TOKENS_URL, TH_APPBUILD, TH_PLATFORM, TH_VERSION, USER_AGENT,
    API_PARAM_NEW_WIND_SET_MODE, API_PARAM_NEW_WIND_STRENGTH,
    API_PARAM_NEW_WIND_AUTO_SWITCH, API_PARAM_NEW_WIND_SWITCH,
    API_PARAM_POWER_SWITCH, API_PARAM_VERTICAL_DIRECTION, API_PARAM_HORIZONTAL_DIRECTION,
)

_LOGGER = logging.getLogger(__name__)

class TclApiError(Exception):
    """Generic TCL API error."""
    pass

class TclAuthError(TclApiError):
    """TCL API authentication error."""
    pass

def calculate_md5_hash_bytes(input_string: str) -> str:
    md5_hash = hashlib.md5()
    md5_hash.update(input_string.encode('utf-8'))
    return md5_hash.hexdigest()

class TclAcApi:
    def __init__(self, session: aiohttp.ClientSession, username: str, password: str):
        self._session = session
        self._username = username
        self._password_hash = hashlib.md5(password.encode()).hexdigest()
        
        # Initialize all attributes
        self._access_token = None
        self._country = None
        self._api_username = None
        self._cognito_token = None
        self._saas_token = None
        self._cognito_token_expiry = None
        self._aws_access_key_id = None
        self._aws_secret_key = None
        self._aws_session_token = None
        self._aws_credentials_expiry = None

    async def authenticate(self):
        """Perform authentication with TCL API."""
        await self.ensure_authenticated()

    async def _request(self, method: str, url: str, headers: Dict[str, Any], 
                       json_data: Optional[Dict[str, Any]] = None, 
                       auth: Optional[AWS4Auth] = None, is_aws_iot: bool = False) -> Dict[str, Any]:
        _LOGGER.debug(f"Request: {method} {url}")
        _LOGGER.debug(f"Headers: {headers}")
        _LOGGER.debug(f"Body: {json.dumps(json_data, indent=2) if json_data else '{}'}")

        try:
            # For AWS IoT calls that need AWS4Auth, we might need to run them in executor
            # because requests_aws4auth is synchronous.
            if auth and is_aws_iot:
                # This is a workaround. Ideally, use an async AWS signing library.
                # For now, we use synchronous requests within an executor job for this specific call.
                import requests # Import sync requests here
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,  # Default executor
                    lambda: requests.request(method, url, headers=headers, json=json_data, auth=auth)
                )
                _LOGGER.debug(f"Sync Response Status: {response.status_code}")
                _LOGGER.debug(f"Sync Response Headers: {response.headers}")
                raw_text = response.text
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                
            else: # Standard async request with aiohttp
                async with self._session.request(method, url, headers=headers, json=json_data, auth=None) as response:
                    _LOGGER.debug(f"Async Response Status: {response.status}")
                    _LOGGER.debug(f"Async Response Headers: {response.headers}")
                    raw_text = await response.text()
                    response.raise_for_status() # Raise ClientResponseError for bad responses

            _LOGGER.debug(f"Raw Response Body: {raw_text[:500]}")
            if not raw_text: # Handle empty response body if API can return that for success
                if response.status >= 200 and response.status < 300 :
                     _LOGGER.debug("Empty response body with success status.")
                     return {} 
                else:
                    _LOGGER.error(f"Empty response body with error status: {response.status}")
                    raise TclApiError(f"API returned empty response with status {response.status}")

            try:
                return json.loads(raw_text)
            except json.JSONDecodeError as e:
                _LOGGER.error(f"JSON Decode Error: {e} for response: {raw_text[:500]}")
                raise TclApiError(f"Failed to decode JSON response: {raw_text[:200]}") from e

        except aiohttp.ClientResponseError as e:
            _LOGGER.error(f"API Request Error (aiohttp): {e.status} {e.message} for {url}")
            if e.status in [401, 403]:
                raise TclAuthError(f"Authentication failed: {e.status} {e.message}") from e
            raise TclApiError(f"API request failed: {e.status} {e.message}") from e
        except requests.exceptions.HTTPError as e: # For the sync request
            _LOGGER.error(f"API Request Error (requests): {e.response.status_code} for {url}")
            if e.response.status_code in [401, 403]:
                raise TclAuthError(f"Authentication failed: {e.response.status_code}") from e
            raise TclApiError(f"API request failed: {e.response.status_code}") from e
        except aiohttp.ClientConnectionError as e:
            _LOGGER.error(f"API Connection Error: {e} for {url}")
            raise TclApiError(f"API connection failed: {e}") from e
        except asyncio.TimeoutError:
            _LOGGER.error(f"API request timed out for {url}")
            raise TclApiError("API request timed out")
        except Exception as e:
            _LOGGER.exception(f"Unexpected API error for {url}: {e}")
            raise TclApiError(f"Unexpected API error: {e}") from e


    async def _do_account_auth(self) -> None:
        url = ACCOUNT_LOGIN_URL.format(CLIENT_ID)
        headers = {
            "th_platform": TH_PLATFORM,
            "th_version": TH_VERSION,
            "th_appbuild": TH_APPBUILD, # Corrected key
            "user-agent": USER_AGENT,
            "content-type": CONTENT_TYPE,
        }
        data = {
            "equipment": 2,
            "password": self._password_hash,
            "osType": 1,
            "username": self._username,
            "clientVersion": "4.8.1",
            "osVersion": "6.0",
            "deviceModel": "Android SDK built for x86", # Consider making this generic or HA-specific
            "captchaRule": 2,
            "channel": "app",
        }
        
        _LOGGER.info("Attempting account authentication...")
        response_data = await self._request("POST", url, headers, data)
        
        if not response_data or "token" not in response_data:
            _LOGGER.error(f"Account auth failed. Response: {response_data}")
            raise TclAuthError("Account authentication failed: 'token' not in response.")
        
        self._access_token = response_data["token"]
        self._country = response_data.get("user", {}).get("countryAbbr")
        self._api_username = response_data.get("user", {}).get("username") # Store the username from API

        if not self._access_token or not self._country or not self._api_username:
             _LOGGER.error(f"Account auth partially failed. Missing token, country, or api_username. Response: {response_data}")
             raise TclAuthError("Account auth failed: Missing critical user data in response.")
        _LOGGER.info("Account authentication successful.")


    async def _refresh_tokens(self) -> None:
        if not self._api_username or not self._access_token:
            _LOGGER.error("Cannot refresh tokens without initial auth (api_username or access_token missing).")
            raise TclAuthError("Prerequisites for token refresh not met.")

        headers = {
            "user-agent": USER_AGENT,
            "content-type": CONTENT_TYPE,
            "accept-encoding": "gzip, deflate, br", # aiohttp handles this automatically
        }
        data = {
            "userId": self._api_username, # Use the username from the first auth step
            "ssoToken": self._access_token,
            "appId": APP_ID,
        }
        
        _LOGGER.info("Attempting to refresh tokens (get SaaS and Cognito)...")
        response_data = await self._request("POST", REFRESH_TOKENS_URL, headers, data)
        
        if not response_data or "data" not in response_data or \
           "cognitoToken" not in response_data["data"] or \
           "saasToken" not in response_data["data"]:
            _LOGGER.error(f"Refresh tokens failed. Response: {response_data}")
            raise TclAuthError("Token refresh failed: 'cognitoToken' or 'saasToken' not in response.")
            
        self._cognito_token = response_data["data"]["cognitoToken"]
        self._saas_token = response_data["data"]["saasToken"]

        try:
            decoded_cognito = jwt.decode(self._cognito_token, options={"verify_signature": False})
            self._cognito_token_expiry = datetime.datetime.fromtimestamp(decoded_cognito["exp"], tz=datetime.timezone.utc)
            _LOGGER.debug(f"Cognito token expires at: {self._cognito_token_expiry}")
        except jwt.PyJWTError as e:
            _LOGGER.error(f"Failed to decode Cognito token: {e}")
            raise TclApiError("Could not parse Cognito token expiry.") from e
        
        _LOGGER.info("Token refresh successful.")

    async def _get_aws_credentials(self) -> None:
        if not self._cognito_token:
            _LOGGER.error("Cannot get AWS credentials without Cognito token.")
            raise TclAuthError("Cognito token not available for AWS credential retrieval.")

        if self._cognito_token_expiry and datetime.datetime.now(tz=datetime.timezone.utc) >= self._cognito_token_expiry:
            _LOGGER.warning("Cognito token expired. Need to re-authenticate fully.")
            raise TclAuthError("Cognito token expired.")

        headers = {
            "X-Amz-Target": "AWSCognitoIdentityService.GetCredentialsForIdentity",
            "Content-Type": "application/x-amz-json-1.1",
            "User-Agent": "aws-sdk-iOS/2.26.2 iOS/18.4.1 en_RO", # This can be kept or changed
            "X-Amz-Date": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
            "Accept-Language": "en-GB,en;q=0.9",
        }
        data = {
            "IdentityId": HARDCODED_IDENTITY_ID,
            "Logins": {
                "cognito-identity.amazonaws.com": self._cognito_token
            }
        }
        
        _LOGGER.info("Attempting to get AWS credentials...")
        response_data = await self._request("POST", AWS_COGNITO_URL, headers, data)

        if not response_data or "Credentials" not in response_data or \
           not all(k in response_data["Credentials"] for k in ["AccessKeyId", "SecretKey", "SessionToken", "Expiration"]):
            _LOGGER.error(f"Get AWS credentials failed. Response: {response_data}")
            raise TclAuthError("Failed to get AWS credentials: Malformed response.")

        creds = response_data["Credentials"]
        self._aws_access_key_id = creds["AccessKeyId"]
        self._aws_secret_key = creds["SecretKey"]
        self._aws_session_token = creds["SessionToken"]
        # AWS Expiration is float seconds since epoch
        self._aws_credentials_expiry = datetime.datetime.fromtimestamp(creds["Expiration"]/1000, tz=datetime.timezone.utc) # Milliseconds
        _LOGGER.info(f"AWS credentials obtained. Expires at: {self._aws_credentials_expiry}")


    async def ensure_authenticated(self) -> None:
        """Ensure all necessary tokens are valid, re-authenticating if needed."""
        full_reauth_needed = False

        if not self._access_token or not self._api_username or not self._country:
            _LOGGER.info("Initial tokens missing. Performing full authentication.")
            full_reauth_needed = True
        
        if not self._cognito_token or not self._saas_token:
            _LOGGER.info("SaaS/Cognito tokens missing.")
            full_reauth_needed = True
        elif self._cognito_token_expiry and datetime.datetime.now(tz=datetime.timezone.utc) >= self._cognito_token_expiry:
            _LOGGER.info("Cognito token expired.")
            full_reauth_needed = True

        if full_reauth_needed:
            await self._do_account_auth()
            await self._refresh_tokens()
        
        # Check AWS credentials specifically
        aws_creds_needed = False
        if not self._aws_access_key_id or not self._aws_secret_key or not self._aws_session_token:
            _LOGGER.info("AWS credentials missing.")
            aws_creds_needed = True
        elif self._aws_credentials_expiry and datetime.datetime.now(tz=datetime.timezone.utc) >= self._aws_credentials_expiry:
            _LOGGER.info("AWS credentials expired.")
            aws_creds_needed = True
        
        if aws_creds_needed:
            if full_reauth_needed: # Cognito token was also refreshed
                 _LOGGER.debug("AWS creds needed, and cognito token was just refreshed.")
            elif self._cognito_token_expiry and datetime.datetime.now(tz=datetime.timezone.utc) >= self._cognito_token_expiry:
                _LOGGER.info("AWS creds needed, but cognito token also expired. Re-doing cognito refresh.")
                await self._refresh_tokens() # Refresh cognito first if it expired
            
            await self._get_aws_credentials()


    async def get_devices(self) -> Dict[str, Any]:
        await self.ensure_authenticated() # Make sure we have SaaS token

        if not self._saas_token or not self._country:
             _LOGGER.error("SaaS token or country not available for get_devices.")
             raise TclAuthError("SaaS token or country missing, cannot get devices.")

        timestamp = str(int(time.time() * 1000))
        nonce = os.urandom(16).hex()
        sign = calculate_md5_hash_bytes(timestamp + nonce + self._saas_token)
        
        headers = {
            "platform": TH_PLATFORM,
            "appversion": "5.4.1", # From original script, may need update
            "thomeversion": TH_VERSION,
            "accesstoken": self._saas_token,
            "countrycode": self._country,
            "accept-language": "en",
            "timestamp": timestamp,
            "nonce": nonce,
            "sign": sign,
            "user-agent": USER_AGENT,
            "content-type": CONTENT_TYPE,
        }
        
        _LOGGER.info("Fetching devices...")
        response_data = await self._request("POST", GET_THINGS_URL, headers, json_data={}) # Empty JSON body
        
        if not response_data or "data" not in response_data:
            _LOGGER.error(f"Get devices failed or returned unexpected structure: {response_data}")
            # This might happen if there are no devices
            if response_data.get("code") == 0 and "data" not in response_data: # Success code but no data
                _LOGGER.warning("Get devices returned success code but no 'data' field. Assuming no devices.")
                return {"data": []} # Return empty list of devices
            raise TclApiError("Failed to get devices or malformed response.")
        
        _LOGGER.info(f"Found {len(response_data.get('data',[]))} devices.")
        return response_data


    async def control_device(self, device_id: str, command: Dict[str, Any]) -> Dict[str, Any]:
        await self.ensure_authenticated() # Make sure we have AWS creds

        if not self._aws_access_key_id or not self._aws_secret_key or not self._aws_session_token:
            _LOGGER.error("AWS credentials not available for device control.")
            raise TclAuthError("AWS credentials missing for device control.")

        url = f"https://{AWS_IOT_ENDPOINT}/topics/%24aws/things/{device_id}/shadow/update?qos=0"
        
        # Headers for AWS IoT data plane are slightly different
        # The AWS4Auth will add the Authorization header.
        # X-Amz-Date is also typically added by the signing library or needs to be very current.
        # We are using requests_aws4auth which expects requests.
        
        aws_headers = {
            "Content-Type": "application/x-amz-json-1.0", # Original script used this
            # "X-Amz-Security-Token": self._aws_session_token, # Added by AWS4Auth
            "User-Agent": "aws-sdk-iOS/2.26.2 iOS/18.4.1 en_RO", # As per original
            # "X-Amz-Date": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) # Added by AWS4Auth
        }
        
        auth = AWS4Auth(
            self._aws_access_key_id,
            self._aws_secret_key,
            AWS_IOT_REGION,
            'iotdata', # Service name for IoT Data Plane
            session_token=self._aws_session_token
        )
        
        data = {
            "state": {"desired": command},
            "clientToken": f"mobile_{int(time.time() * 1000)}"
        }
        
        _LOGGER.info(f"Controlling device {device_id} with command: {command}")
        # This call will be run in an executor due to AWS4Auth being synchronous
        return await self._request("POST", url, aws_headers, data, auth=auth, is_aws_iot=True)

    async def set_power(self, device_id: str, power_on: bool) -> Dict[str, Any]:
        """Helper to turn device on or off."""
        if power_on:
            command = {API_PARAM_POWER_SWITCH: 1}
        else:
            command = {
                API_PARAM_POWER_SWITCH: 0,
                API_PARAM_VERTICAL_DIRECTION: 8,   # Default "parked" position from logs
                API_PARAM_HORIZONTAL_DIRECTION: 8, # Default "parked" position from logs
            }
        return await self.control_device(device_id, command)

    async def set_temperature(self, device_id: str, temperature: float) -> Dict[str, Any]:
        """Helper to set target temperature."""
        command = {"targetTemperature": temperature}
        return await self.control_device(device_id, command)

    async def get_device_shadow(self, device_id: str) -> Dict[str, Any]:
        """Get device shadow."""
        await self.ensure_authenticated() # Make sure we have AWS creds

        if not self._aws_access_key_id or not self._aws_secret_key or not self._aws_session_token:
            _LOGGER.error("AWS credentials not available for device control.")
            raise TclAuthError("AWS credentials missing for device control.")

        url = f"https://{AWS_IOT_ENDPOINT}/things/{device_id}/shadow"
        
        # Headers for AWS IoT data plane are slightly different
        # The AWS4Auth will add the Authorization header.
        # X-Amz-Date is also typically added by the signing library or needs to be very current.
        # We are using requests_aws4auth which expects requests.
        
        aws_headers = {
            "Content-Type": "application/x-amz-json-1.0", # Original script used this
            # "X-Amz-Security-Token": self._aws_session_token, # Added by AWS4Auth
            "User-Agent": "aws-sdk-iOS/2.26.2 iOS/18.4.1 en_RO", # As per original
            # "X-Amz-Date": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) # Added by AWS4Auth
        }
        
        auth = AWS4Auth(
            self._aws_access_key_id,
            self._aws_secret_key,
            AWS_IOT_REGION,
            'iotdata', # Service name for IoT Data Plane
            session_token=self._aws_session_token
        )
        
        _LOGGER.info(f"Getting device shadow for {device_id}")
        try:
            # This call will be run in an executor due to AWS4Auth being synchronous
            response_data = await self._request("GET", url, aws_headers, auth=auth, is_aws_iot=True)
            _LOGGER.debug(f"get_device_shadow API response for {device_id}: {response_data}")
            if not response_data:
                _LOGGER.warning(f"Device {device_id} shadow is empty. Returning empty dict")
                return {}
            return response_data
        except Exception as e:
            _LOGGER.error(f"Error getting device shadow for {device_id}: {e}", exc_info=True)
            raise

    async def async_set_fresh_air(
        self,
        device_id: str,
        switch_state: Optional[int] = None,
        mode: Optional[int] = None,
        strength: Optional[int] = None,
        auto_switch: Optional[int] = None
    ) -> Dict[str, Any]:
        """Control the fresh air system of the device."""
        command = {}
        if switch_state is not None:
            command[API_PARAM_NEW_WIND_SWITCH] = switch_state
        
        # Only add mode, strength, auto_switch if not explicitly turning off
        # Or if switch_state is 1 (on) or None (meaning we are just setting mode/speed on an already on device)
        if switch_state != 0: # API might ignore these if switch_state is 0, but being explicit
            if mode is not None:
                command[API_PARAM_NEW_WIND_SET_MODE] = mode
            if strength is not None:
                command[API_PARAM_NEW_WIND_STRENGTH] = strength
            if auto_switch is not None:
                command[API_PARAM_NEW_WIND_AUTO_SWITCH] = auto_switch
            elif strength is not None: # If strength is set manually, ensure auto_switch is off
                command[API_PARAM_NEW_WIND_AUTO_SWITCH] = 0


        if not command:
            _LOGGER.warning(f"No fresh air parameters provided for device {device_id}. No action taken.")
            return {}

        _LOGGER.info(f"Setting fresh air for device {device_id} with command: {command}")
        # Note: The mitmproxy logs showed other parameters like selfClean, verticalDirection, horizontalDirection
        # in some fresh air commands. These are currently omitted as their necessity is unclear.
        # If issues arise, these might need to be conditionally included.
        return await self.control_device(device_id, command)
