## Product Context

This project aims to integrate TCL air conditioners into Home Assistant using the Home Assistant Community Store (HACS).

### Problems Solved

*   Allows users to control their TCL AC units directly from Home Assistant.
*   Provides a centralized platform for managing smart home devices.
*   Enables automation scenarios involving TCL AC units.

### How it Should Work

The integration should:

*   Discover TCL AC units associated with the user's account.
*   Allow users to control basic functions such as power, mode, and temperature.
*   Provide real-time status updates on the AC unit's current state.

### User Experience Goals

*   Seamless integration with Home Assistant.
*   Intuitive and easy-to-use interface.
*   Reliable and responsive control of AC units.

### API Interactions

The integration interacts with the TCL API to retrieve device information and send control commands.

#### Example API Request and Response

This is an example of the raw request and response for getting all data for one AC unit:

**Request:**

```
GET /things/C6BS4xFAAAE/shadow HTTP/1.1
Host: a2qjkbbsk6qn2u-ats.iot.eu-central-1.amazonaws.com
Content-Type: application/x-amz-json-1.0
X-Amz-Security-Token: IQoJb3JpZ2luX2VjEBAaDGV1LWNlbnRyYWwtMSJHMEUCIQChDNaIPoYAEvY/iZxGhgRycZrrTDjihD7dA9Hp1f0ZugIgHv40hKVWjq0tF9rGyCY+UNnpGLuyKT3te6eg3BFDsS0qjgQI2f//////////ARACGgw0MjA1MjA0MDkzODkiDGQt/o0dlG07ag9CiSriA1H9VDRIFpDSsQat+R8KOHo+q/obSxtP+rd53vzHy9xn83FozyKfOhkUpLTtiQdjeEJt+BqSIxORoeWT6ABfDRyduEz29AsrscK4AcgtbZsVRQRnuzFvK/UMoHzRSnRg5Z6U4SNgrQJwdHr7YP4tklzqrdQHa7wvtL3jHTb81w8s/hIBF/14su2oJDcU2hJiLiic57JJ0oXkKiv4r08nnaDJeFD9q5znwAWNnu9wFm5e53eWxDuUsyJnzkprXTG4Q+OlZBH1H+HwfIOzJSohXvYvNxXjht+rQTFFqIamY/+6Dr6d1pJy+tibfNkmChs1KNNwpCdUqDmKIZn5rhjcsY3lCkCg7RXsf2VAT/63vcUyEK9yRCBdyprmQdMS6/x3g3tyD2Y2zmNwQ/n0gu4oqIU4RCNr/pNp2ISM6BtL1mui2aVKdDkRs6bzJaM4cVDgHc4b8JDyUq7+gwoUu4NXtrs8mmUT311hEFBQGD5gSLzNi5/mGi4w4tTaPZjAY/oaxpmUCkpbtg/7omVa8zlroF7ZtadO2jzW6svNzHFES4l/0s/XmT+yeClsaTi16kc8NY2k58bnbm4g9Yo9+D5It2Uok+7UpnVdelUieyVE4KRqT2q2qnRtTHC/inzzxgg8dy8UMLjq8cEGOoQCFIAKezOpFON6zz31sIcTz1HtIjQTOPnJX+szZD6HjP5z0n6Gd+iqmYfRYxEY5Tmaa2x020k5JmKHoriFC9r9ZRYo3LUOhBtSXrSLl4f3L7NmOalVv30PrUnXyCTi85w09meGEA4bw72j+SXKH+XphBNMLzdlaX+jwCLCguYg/YM4lLbErX/0Xq1KN6FzB0fofy3QFF/H5226sgQI7UATu2r0dk7wekFfW721VqgYAZbHUDIhEIdtNh0h5dkr5Kg1ZfeuwMHHHaw9HLvWxdi62IiG896bxlTonCWa/axuI31GVBKppN45Y49nMNSTrl2swW3Y3NSVHGuGvtmObP9ggUhfIgo=
Accept-Encoding: gzip, deflate, br
Connection: keep-alive
Accept: */*
User-Agent: aws-sdk-iOS/2.26.2 iOS/18.5 en_RO
Authorization: AWS4-HMAC-SHA256 Credential=ASIAWD2HYHEWY3MKVLAU/20250601/eu-central-1/iotdata/aws4_request, SignedHeaders=content-type;host;user-agent;x-amz-date;x-amz-security-token, Signature=830cbeb98280c68091089674db922d3f9888a409d62545ecf94be527196a6cba
Accept-Language: en-GB,en;q=0.9
X-Amz-Date: 20250601T154735Z
content-length: 0
```

**Response:**

```
HTTP/1.1 200 OK
content-type: application/json
content-length: 6520
date: Sun, 01 Jun 2025 15:47:35 GMT
x-amzn-RequestId: 28184f5c-9f78-2b9b-8555-4ae23a338a54
connection: keep-alive

{"state":{"desired":{"currentTemperature":25.1,"internalUnitCoilTemperature":17,"externalUnitExhaustTemperature":40,"externalUnitVoltage":217,"sensorTVOC":{"level":4,"value":6.97},"powerSwitch":1,"targetTemperature":31,"temperatureType":0,"windSpeed7Gear":0,"verticalWind":0,"horizontalWind":0,"horizontalDirection":8,"verticalDirection":8,"workMode":0,"ECO":0,"selfClean":0,"screen":0,"lightSense":1,"sleep":0,"beepSwitch":0,"softWind":0,"antiMoldew":0,"generatorMode":1,"filterBlockStatus":0,"errorCode":[],"internalUnitFanSpeed":728,"PTCStatus":0,"internalUnitFanCurrentGear":2,"externalUnitTemperature":25,"externalUnitCoilTemperature":22,"externalUnitFanGear":0,"externalUnitFanSpeed":0,"compressorFrequency":0,"fourWayValveStatus":0,"externalUnitElectricCurrent":0,"expansionValve":480,"newWindSwitch":1,"lightSenserStatus":0,"newWindPercentage":0,"newWindAutoSwitch":1,"windSpeedPercentage":0,"windSpeedAutoSwitch":1,"selfCleanStatus":6,"FreshAirStatus":0,"newWindStrength":0,"newWindSetMode":2,"newWindRunMode":3,"newWindAntiCondensation":0},"reported":{"authFlag":{"alexa":true,"google":true},"currentTemperature":25.1,"internalUnitCoilTemperature":17,"externalUnitExhaustTemperature":40,"externalUnitVoltage":217,"sensorTVOC":{"level":4,"value":6.97},"powerSwitch":1,"targetTemperature":31,"temperatureType":0,"windSpeed7Gear":0,"verticalWind":0,"horizontalWind":0,"horizontalDirection":8,"verticalDirection":8,"workMode":0,"ECO":0,"selfClean":0,"screen":0,"lightSense":1,"sleep":0,"beepSwitch":0,"softWind":0,"antiMoldew":0,"generatorMode":1,"filterBlockStatus":0,"errorCode":[],"internalUnitFanSpeed":728,"PTCStatus":0,"internalUnitFanCurrentGear":2,"externalUnitTemperature":25,"externalUnitCoilTemperature":22,"externalUnitFanGear":0,"externalUnitFanSpeed":0,"compressorFrequency":0,"fourWayValveStatus":0,"externalUnitElectricCurrent":0,"expansionValve":480,"newWindSwitch":1,"lightSenserStatus":0,"newWindPercentage":0,"newWindAutoSwitch":1,"windSpeedPercentage":0,"windSpeedAutoSwitch":1,"selfCleanStatus":6,"FreshAirStatus":0,"newWindStrength":0,"newWindSetMode":2,"newWindRunMode":3,"newWindAntiCondensation":0}},"metadata":{"desired":{"currentTemperature":{"timestamp":1748792759},"internalUnitCoilTemperature":{"timestamp":1748792839},"externalUnitExhaustTemperature":{"timestamp":1748792843},"externalUnitVoltage":{"timestamp":1748792824},"sensorTVOC":{"level":{"timestamp":1748792825},"value":{"timestamp":1748792825}},"powerSwitch":{"timestamp":1748791936},"targetTemperature":{"timestamp":1748792784},"temperatureType":{"timestamp":1748769704},"windSpeed7Gear":{"timestamp":1748769704},"verticalWind":{"timestamp":1748769704},"horizontalWind":{"timestamp":1748769704},"horizontalDirection":{"timestamp":1748769704},"verticalDirection":{"timestamp":1748769704},"workMode":{"timestamp":1748769704},"ECO":{"timestamp":1748769704},"selfClean":{"timestamp":1748769704},"screen":{"timestamp":1748769704},"lightSense":{"timestamp":1748769704},"sleep":{"timestamp":1748769704},"beepSwitch":{"timestamp":1748769704},"softWind":{"timestamp":1748769704},"antiMoldew":{"timestamp":1748769704},"generatorMode":{"timestamp":1748769704},"filterBlockStatus":{"timestamp":1748769704},"errorCode":[],"internalUnitFanSpeed":{"timestamp":1748792689},"PTCStatus":{"timestamp":1748769704},"internalUnitFanCurrentGear":{"timestamp":1748792687},"externalUnitTemperature":{"timestamp":1748792849},"externalUnitCoilTemperature":{"timestamp":1748792855},"externalUnitFanGear":{"timestamp":1748769704},"externalUnitFanSpeed":{"timestamp":1748792826},"compressorFrequency":{"timestamp":1748792792},"fourWayValveStatus":{"timestamp":1748769704},"externalUnitElectricCurrent":{"timestamp":1748792793},"expansionValve":{"timestamp":1748792826},"newWindSwitch":{"timestamp":1748791862},"lightSenserStatus":{"timestamp":1748769704},"newWindPercentage":{"timestamp":1748769704},"newWindAutoSwitch":{"timestamp":1748769704},"windSpeedPercentage":{"timestamp":1748769704},"windSpeedAutoSwitch":{"timestamp":1748769704},"selfCleanStatus":{"timestamp":1748769704},"FreshAirStatus":{"timestamp":1748769704},"newWindStrength":{"timestamp":1748769704},"newWindSetMode":{"timestamp":1748769704},"newWindRunMode":{"timestamp":1748791864},"newWindAntiCondensation":{"timestamp":1748769704}}},"version":256646,"timestamp":1748792855}
