from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from LimerickAgent import run_limerick_agent
import uvicorn

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
def index():
    # Centered layout and polished research display with indicators beneath the limerick
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Corporate Limerick Generator</title>
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <style>
            :root{ --bg:#f4f6ff; --card:#ffffff; --accent:#5b6cff; --muted:#6b7280; --up:#16a34a; --down:#ef4444; --same:#2563eb }
            /* Use border-box globally so padding doesn't increase perceived width */
            *, *::before, *::after { box-sizing: border-box; }
            html,body{height:100%;}
            body{margin:0;font-family:Inter,system-ui,-apple-system,'Segoe UI',Roboto,Arial;background:var(--bg);display:flex;align-items:center;justify-content:center;padding:24px}
            .container{width:100%;max-width:880px;background:var(--card);border-radius:14px;padding:28px;box-shadow:0 12px 30px rgba(20,24,48,.08);box-sizing:border-box}
            .header{display:flex;flex-direction:column;align-items:center;text-align:center}
            h1{margin:0;font-size:1.6rem;color:#071036}
            .lead{color:var(--muted);margin-top:8px}
            form{display:flex;gap:10px;justify-content:center;margin-top:18px}
            input[type=text]{flex:1 1 360px;padding:12px 14px;border-radius:10px;border:1px solid #e9eef8;font-size:1rem}
            button{background:linear-gradient(180deg,var(--accent),#3f4fe0);color:#fff;border:none;padding:10px 16px;border-radius:10px;font-weight:600;cursor:pointer;box-shadow:0 8px 20px rgba(91,108,255,0.18)}
            .card{background:linear-gradient(180deg,rgba(91,108,255,0.03),rgba(91,108,255,0.01));border-radius:12px;padding:18px;border:1px solid rgba(91,108,255,0.08);box-shadow:0 6px 18px rgba(13,14,28,0.04);width:100%;box-sizing:border-box;overflow-x:hidden}
            /* center and constrain direct children so internal cards don't exceed the outer backing card */
            .card{display:flex;flex-direction:column;align-items:center}
            /* explicit inner width control: both limerick and research wrappers use the same inner max width */
            .card > .limerickWrap, .card > .researchWrap { max-width:760px; width:100%; box-sizing:border-box }
            .limerickWrap{padding:18px;background:#fff;border-radius:10px;border:1px solid #f1f5ff;box-shadow:0 6px 18px rgba(13,14,28,0.03)}
            .researchWrap{margin-top:18px}
            .research{width:100%;padding:14px;border-radius:12px;background:#fff;border:1px solid #f1f5ff;box-shadow:0 6px 18px rgba(13,14,28,0.03);box-sizing:border-box;overflow:hidden}
            .research h3{margin:0 0 10px 0;font-size:0.95rem}
            .fact{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px dashed #f0f4ff}
            .fact:last-child{border-bottom:none}
            .fact .label{color:var(--muted);font-size:0.85rem}
            .fact .value{font-weight:700;color:#071036}
            pre.limerick{font-family:'Georgia','Times New Roman',serif;font-size:1.25rem;line-height:1.6;color:#071036;white-space:pre-wrap;margin:0}
            .meta{font-size:0.85rem;color:var(--muted);text-align:right;margin-top:12px}
            .placeholder{color:var(--muted);text-align:center;padding:18px 0}
            table{width:100%;border-collapse:collapse}
            th,td{padding:8px 6px;text-align:left;font-size:0.95rem}
            thead th{color:var(--muted);font-size:0.85rem}
            tr.rowSep td{border-top:1px solid #f4f7ff}
            .indicator{font-weight:700;margin-left:8px;display:inline-flex;align-items:center}
            .indicator.up{color:var(--up)}
            .indicator.down{color:var(--down)}
            .indicator.same{color:var(--same)}
            /* Prevent long unbroken strings from widening the table beyond the card */
            table{table-layout:fixed; width:100%; max-width:720px; margin:0 auto; box-sizing:border-box}
            th, td{word-break:break-word; overflow-wrap:anywhere; white-space:normal}
             /* Constrain the market cap column so very long values wrap instead of stretching the table */
             thead th:nth-child(5), tbody td:nth-child(5){max-width:160px}

            @media (max-width:720px){.container{padding:18px}.limerickWrap{padding:12px}.research{padding:12px}}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Corporate Limerick Generator</h1>
                <div class="lead">Type a company name to get a researched limerick — includes key facts used to write it.</div>
            </div>

            <form id="limerickForm" onsubmit="return false">
                <input type="text" id="company" name="company" placeholder="e.g. Globex Corporation" required />
                <button id="generateBtn">Generate</button>
            </form>

            <div class="card" style="margin-top:18px">
                <div id="resultCard" class="limerickWrap" style="display:none">
                    <pre id="result" class="limerick" aria-live="polite"></pre>
                    <div class="meta">Generated by Corporate Limerick Agent</div>
                </div>

                <div id="researchCard" class="researchWrap" style="display:none">
                    <div class="research">
                        <h3>Research summary (past 3 years)</h3>
                        <table id="researchTable" style="margin-top:6px">
                            <thead>
                                <tr>
                                    <th>Year</th>
                                    <th>Share price</th>
                                    <th>P/E</th>
                                    <th>Dividends</th>
                                    <th>Market cap</th>
                                </tr>
                            </thead>
                            <tbody id="researchBody">
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div id="placeholder" class="placeholder">Your limerick and research will appear here.</div>
        </div>

        <script>
            const form = document.getElementById('limerickForm');
            const companyInput = document.getElementById('company');
            const resultCard = document.getElementById('resultCard');
            const resultEl = document.getElementById('result');
            const researchCard = document.getElementById('researchCard');
            const placeholder = document.getElementById('placeholder');
            const btn = document.getElementById('generateBtn');

            function parseNumberForMetric(raw, metric){
                if(raw === null || raw === undefined) return null;
                if(typeof raw === 'number') return raw;
                let s = String(raw).trim();
                // remove commas
                s = s.replace(/,/g, '');
                // detect B/M suffixes for market cap
                const suffixMatch = s.match(/([0-9.+-]+)\s*([BbMm]?)\b/);
                if(suffixMatch){
                    let num = parseFloat(suffixMatch[1]);
                    if(isNaN(num)) return null;
                    const suf = (suffixMatch[2] || '').toUpperCase();
                    if(suf === 'B') return num * 1e9;
                    if(suf === 'M') return num * 1e6;
                    return num;
                }
                // remove currency symbols and percent
                s = s.replace(/[£$€]/g, '').replace(/%/g, '');
                const f = parseFloat(s);
                if(isNaN(f)) return null; return f;
            }

            function compareVals(currentRaw, previousRaw, metric){
                const a = parseNumberForMetric(currentRaw, metric);
                const b = parseNumberForMetric(previousRaw, metric);
                if(a === null || b === null){
                    // try string equality fallback
                    if(currentRaw && previousRaw && String(currentRaw).trim() === String(previousRaw).trim()) return 'same';
                    return 'same'; // default to same when unknown to avoid misleading red/green
                }
                const eps = Math.max(Math.abs(b)*0.0001, 1e-6);
                if(a > b + eps) return 'up';
                if(a < b - eps) return 'down';
                return 'same';
            }

            function indicatorHTML(direction){
                if(direction === 'up') return '<span class="indicator up" aria-hidden="true">▲</span>';
                if(direction === 'down') return '<span class="indicator down" aria-hidden="true">▼</span>';
                return '<span class="indicator same" aria-hidden="true">—</span>';
            }

            function renderResearch(years){
                const tbody = document.getElementById('researchBody');
                tbody.innerHTML = '';
                if(!years || !Array.isArray(years) || years.length === 0){
                    const tr = document.createElement('tr');
                    tr.innerHTML = '<td colspan="5" style="padding:10px 8px;color:var(--muted);text-align:center">No research data available</td>';
                    tbody.appendChild(tr);
                    return;
                }
                // Ensure most-recent first and at most 3 rows
                const rows = years.slice(0,3);
                for(let i=0;i<rows.length;i++){
                    const y = rows[i];
                    const next = (i+1 < rows.length) ? rows[i+1] : null; // previous year (older)
                    const tr = document.createElement('tr');
                    tr.className = 'rowSep';
                    const yr = y.year || '—';
                    const sp = y.share_price ?? y['share price'] ?? '—';
                    const pe = y.pe_ratio ?? y['pe ratio'] ?? '—';
                    const dv = y.dividends ?? '—';
                    const mc = y.market_cap ?? y['market cap'] ?? '—';

                    const spDir = next ? compareVals(sp, next.share_price ?? next['share price'], 'share_price') : 'same';
                    const peDir = next ? compareVals(pe, next.pe_ratio ?? next['pe ratio'], 'pe_ratio') : 'same';
                    const dvDir = next ? compareVals(dv, next.dividends, 'dividends') : 'same';
                    const mcDir = next ? compareVals(mc, next.market_cap ?? next['market cap'], 'market_cap') : 'same';

                    tr.innerHTML = `
                        <td>${yr}</td>
                        <td>${sp} ${indicatorHTML(spDir)}</td>
                        <td>${pe} ${indicatorHTML(peDir)}</td>
                        <td>${dv} ${indicatorHTML(dvDir)}</td>
                        <td>${mc} ${indicatorHTML(mcDir)}</td>
                    `;
                    tbody.appendChild(tr);
                }
            }

            async function generate(){
                const company = companyInput.value.trim();
                if(!company) return;
                placeholder.style.display = 'none';
                resultCard.style.display = 'block';
                researchCard.style.display = 'block';
                resultEl.textContent = 'Generating...';
                btn.disabled = true;
                try{
                    const resp = await fetch('/limerick?company=' + encodeURIComponent(company));
                    if(!resp.ok) throw new Error('Network response was not ok');
                    const data = await resp.json();
                    const text = data.limerick || 'No limerick returned.';
                    resultEl.textContent = text;
                    const r = data.research || {};
                    renderResearch(r.years || []);
                 }catch(err){
                     resultEl.textContent = 'Error generating limerick: ' + err.message;
                     researchCard.style.display = 'none';
                 }finally{
                     btn.disabled = false;
                 }
             }

            form.addEventListener('submit', function(e){ e.preventDefault(); generate(); });
            btn.addEventListener('click', function(e){ e.preventDefault(); generate(); });
            companyInput.addEventListener('keydown', function(e){ if(e.key === 'Enter'){ e.preventDefault(); generate(); } });
        </script>
    </body>
    </html>
    """


@app.get("/limerick")
def get_limerick(company: str):
    output = run_limerick_agent(company)
    # output is expected to be a dict with 'limerick' and 'research'
    return JSONResponse(output)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
