from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from LimerickAgent import run_limerick_agent
import uvicorn

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Corporate Limerick Generator</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            #result { margin-top: 20px; font-size: 1.2em; }
        </style>
    </head>
    <body>
        <h1>Corporate Limerick Generator</h1>
        <form id="limerickForm">
            <label for="company">Enter company name:</label>
            <input type="text" id="company" name="company" required>
            <button type="submit">Generate Limerick</button>
        </form>
        <div id="result"></div>
        <script>
        document.getElementById('limerickForm').onsubmit = async function(e) {
            e.preventDefault();
            const company = document.getElementById('company').value;
            document.getElementById('result').innerText = 'Generating...';
            const resp = await fetch('/limerick?company=' + encodeURIComponent(company));
            const data = await resp.json();
            document.getElementById('result').innerText = data.limerick || 'No limerick returned.';
        };
        </script>
    </body>
    </html>
    """

@app.get("/limerick")
def get_limerick(company: str):
    limerick = run_limerick_agent(company)
    return JSONResponse({"limerick": limerick})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

