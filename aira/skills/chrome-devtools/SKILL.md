# Chrome DevTools Protocol (CDP)

Programmatic browser automation via CDP.

## Launch Headless Chrome
```python
import subprocess, json, websocket

# Launch Chrome with CDP
chrome = subprocess.Popen([
    'chrome', '--headless', '--remote-debugging-port=9222',
    '--no-sandbox', '--disable-gpu'
])

# Connect via websocket
import requests
ws_url = requests.get('http://localhost:9222/json/version').json()['webSocketDebuggerUrl']
ws = websocket.create_connection(ws_url)
```

## Key CDP Commands
```python
def send_cmd(ws, method, params=None):
    msg = {'id': 1, 'method': method, 'params': params or {}}
    ws.send(json.dumps(msg))
    return json.loads(ws.recv())

# Navigate
send_cmd(ws, 'Page.navigate', {'url': 'https://example.com'})

# Screenshot
result = send_cmd(ws, 'Page.captureScreenshot')
with open('screenshot.png', 'wb') as f:
    f.write(bytes(result['result']['data']))

# Evaluate JS
result = send_cmd(ws, 'Runtime.evaluate', {'expression': 'document.title'})
print(result['result']['result']['value'])

# Get DOM
result = send_cmd(ws, 'DOM.getDocument')
print(result['result']['root']['nodeId'])
```

## Available Domains
- `Page.*` - Navigation, screenshots, print-to-PDF
- `DOM.*` - DOM querying and modification
- `Network.*` - Request interception, HAR export
- `Runtime.*` - JavaScript evaluation
- `Performance.*` - Tracing, metrics
- `Audits.*` - Lighthouse runs
