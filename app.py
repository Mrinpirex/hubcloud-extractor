import re
import base64
import os
from html import unescape
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, quote
import requests
from flask import Flask, request, render_template_string, jsonify, redirect

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REDIRECT_TYPES = {
    "fsl": "FSL",
    "gpdl": "GPDL",
    "pd": "PD (Pixeldrain Direct)",
    "pixeldrain": "Pixeldrain",
    "direct": "Direct Download",
    "hbplay": "HBPlay",
    "watch": "Watch",
    "pixel": "Pixel Server",
}

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Multi URL Link Extractor</title>
<style>
:root {
    --bg:#0f1117;
    --card:#1a1d27;
    --accent:#4fc3f7;
    --green:#81c784;
    --orange:#ffb74d;
    --text:#e8eaed;
    --muted:#9aa0a6;
    --border:#303541;
}
* {box-sizing:border-box}
body {
    margin:0;
    padding:24px 14px;
    background:var(--bg);
    color:var(--text);
    font-family:system-ui,Arial,sans-serif;
}
.container {max-width:950px;margin:auto}
h1 {color:var(--accent);font-size:1.7rem}
.subtitle {color:var(--muted);line-height:1.5}
.panel,.result {
    background:var(--card);
    border:1px solid var(--border);
    border-radius:12px;
    padding:16px;
    margin:16px 0;
}
label {display:block;font-weight:600;margin-bottom:8px}
textarea {
    width:100%;
    min-height:150px;
    resize:vertical;
    background:var(--bg);
    color:var(--text);
    border:1px solid var(--border);
    border-radius:8px;
    padding:12px;
    font:inherit;
}
button {
    border:0;
    border-radius:7px;
    padding:11px 12px;
    font-weight:600;
    cursor:pointer;
}
button:disabled {opacity:.6;cursor:wait}
.submit {
    width:100%;
    margin-top:12px;
    background:var(--accent);
    color:#111;
    padding:13px;
    font-size:1rem;
}
.copy-grid {
    display:flex;
    flex-direction:column;
    gap:9px;
    margin:15px 0;
}
.copy-grid button {
    width:100%;
    min-height:43px;
    background:var(--green);
    color:#111;
}
.copy-grid .all {background:var(--accent)}
.copy-grid .redirects {background:var(--orange)}
.result h3 {color:var(--accent);overflow-wrap:anywhere}
.meta {font-size:.78rem;color:var(--muted);margin:10px 0 5px}
.url {overflow-wrap:anywhere;word-break:break-word;font-size:.88rem}
a {color:var(--accent);text-decoration:none}
a:hover {text-decoration:underline}
.redirect-link {color:var(--orange)}
.actions {display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.mini {background:var(--bg);color:var(--text);border:1px solid var(--border)}
hr {border:0;border-top:1px solid var(--border);margin:15px 0}
.error {
    color:#ff9d9d;
    background:#321c20;
    padding:12px;
    border-radius:8px;
    white-space:pre-wrap;
    overflow-wrap:anywhere;
}
#status {color:var(--green);min-height:20px}
footer {color:var(--muted);text-align:center;margin:28px 0;font-size:.8rem}
</style>
</head>
<body>
<div class="container">
<h1>Multi URL Link Extractor</h1>
<p class="subtitle">
Paste multiple HubCloud URLs, one per line. Extract links and copy
only the redirect type you need.
</p>
<form method="post" action="/" id="extract-form" class="panel">
<label for="hub_urls">HubCloud URLs</label>
<textarea id="hub_urls" name="hub_urls"
placeholder="https://hubcloud.ist/drive/link1&#10;https://hubcloud.ist/drive/link2"
required>{{ hub_urls or '' }}</textarea>
<button class="submit" id="submit-btn">Extract All URLs</button>
</form>
{% if error %}
<div class="error">{{ error }}</div>
{% endif %}
{% if sources %}
<div class="panel">
<h3>Copy Specific Redirect Types</h3>
<p class="subtitle">
Each button copies that redirect type for all submitted source URLs.
Every copied URL is separated by a real newline.
</p>
<div class="copy-grid">
{% for key, label in redirect_types.items() %}
<button type="button"
onclick="copyType('{{ key }}', this)">
Copy {{ label }} Redirects
</button>
{% endfor %}
<button type="button" class="all"
onclick="copyAllDirect(this)">Copy All Direct Links</button>
<button type="button" class="all"
onclick="copyAllLabeled(this)">Copy All Links + Labels</button>
<button type="button" class="redirects"
onclick="copyAllRedirects(this)">Copy All Redirect Types</button>
</div>
<div id="status" aria-live="polite"></div>
</div>
{% for source in sources %}
<div class="result">
<h3>Source {{ loop.index }}</h3>
<div class="meta">HubCloud URL</div>
<div class="url">{{ source.url }}</div>
{% if source.error %}
<hr>
<div class="error">{{ source.error }}</div>
{% endif %}
{% if source.links %}
<hr>
{% for link in source.links %}
<div class="meta">{{ link.name }}</div>
<div class="url">
<a href="{{ link.url }}" target="_blank" rel="noopener noreferrer">
{{ link.url }}
</a>
</div>
<div class="actions">
<button class="mini" type="button"
onclick='copyText({{ link.url|tojson }}, this)'>Copy Direct</button>
<a href="{{ link.url }}" target="_blank"
rel="noopener noreferrer">Open</a>
</div>
{% endfor %}
{% endif %}
<hr>
<div class="meta">Redirect links for this source</div>
{% for key, label in redirect_types.items() %}
<div class="meta">{{ label }}</div>
<div class="url">
<a class="redirect-link" href="{{ source.redirects[key] }}"
target="_blank" rel="noopener noreferrer">
{{ source.redirects[key] }}
</a>
</div>
<div class="actions">
<button class="mini" type="button"
onclick='copyText({{ source.redirects[key]|tojson }}, this)'>
Copy {{ label }}
</button>
</div>
{% endfor %}
</div>
{% endfor %}
<script>
const sources = {{ sources|tojson }};
const redirectTypes = {{ redirect_types|tojson }};
function setStatus(message) {
    document.getElementById("status").textContent = message;
}
async function copyText(text, button) {
    try {
        await navigator.clipboard.writeText(text);
        if (button) {
            const original = button.textContent;
            button.textContent = "Copied!";
            setTimeout(() => {
                button.textContent = original;
            }, 1200);
        }
        setStatus("Copied successfully.");
    } catch (error) {
        window.prompt("Copy the text below:", text);
    }
}
async function copyType(type, button) {
    const links = sources
        .map(source => source.redirects[type])
        .filter(Boolean);
    if (!links.length) {
        setStatus("No URLs available.");
        return;
    }
    // Actual newline separator, not the literal characters backslash+n.
    await copyText(links.join("\n"), button);
    setStatus(
        "Copied " + (redirectTypes[type] || type) +
        " redirects: " + links.length
    );
}
async function copyAllRedirects(button) {
    const lines = [];
    sources.forEach(source => {
        Object.entries(source.redirects).forEach(([type, url]) => {
            lines.push(type.toUpperCase() + ": " + url);
        });
    });
    await copyText(lines.join("\n"), button);
    setStatus("Copied all redirect types.");
}
async function copyAllLabeled(button) {
    const lines = [];
    sources.forEach(source => {
        lines.push("SOURCE: " + source.url);
        (source.links || []).forEach(link => {
            lines.push(link.name + ": " + link.url);
        });
        Object.entries(source.redirects).forEach(([type, url]) => {
            lines.push(type.toUpperCase() + " REDIRECT: " + url);
        });
        lines.push("");
    });
    await copyText(lines.join("\n"), button);
    setStatus("Copied all links with labels.");
}
async function copyAllDirect(button) {
    const lines = [];
    sources.forEach(source => {
        (source.links || []).forEach(link => {
            lines.push(link.url);
        });
    });
    if (!lines.length) {
        setStatus("No direct links available.");
        return;
    }
    await copyText(lines.join("\n"), button);
    setStatus("Copied extracted direct links.");
}
document.getElementById("extract-form").addEventListener("submit", () => {
    const button = document.getElementById("submit-btn");
    button.disabled = true;
    button.textContent = "Extracting...";
});
</script>
{% endif %}
<footer>Flask · Multi URL Link Extractor</footer>
</div>
</body>
</html>
"""


def direct_googleusercontent_url(url):
    """Extract a direct Googleusercontent URL from a wrapped URL."""
    if not url:
        return None
    url = unescape(url.strip())
    parsed = urlparse(url)

    # cryptonewz.online/dl.php?link=... (and similar wrappers)
    if parsed.path.lower().endswith("/dl.php") or "dl.php" in parsed.path.lower():
        wrapped = parse_qs(parsed.query).get("link", [None])[0]
        if wrapped:
            url = wrapped

    match = re.search(
        r'https?://video-downloads\.googleusercontent\.com/[^&\s<>"\']+',
        url,
        re.I,
    )
    return match.group(0).rstrip(").,") if match else None


def make_hbplay_link(
    video_url,
    filename="video.mp4",
    mime_type="video/mp4",
):
    return "https://hbplay.pages.dev/?" + urlencode({
        "u": base64.b64encode(video_url.encode()).decode(),
        "m": base64.b64encode(mime_type.encode()).decode(),
        "t": base64.b64encode(filename.encode()).decode(),
    })


def add_result(results, name, url):
    if url and not any(existing_url == url for _, existing_url in results):
        results.append((name, url))


def follow_for_googleusercontent(session, server_url, referer, results):
    """Follow gpdl/pixel (or similar) and extract Direct Googleusercontent + HBPlay."""
    try:
        resp = session.get(
            server_url,
            headers={"Referer": referer},
            timeout=30,
            allow_redirects=True,
        )
        direct_url = direct_googleusercontent_url(resp.url)

        if not direct_url:
            direct_url = direct_googleusercontent_url(resp.text[:5000])

        if not direct_url and resp.history:
            for h in resp.history:
                direct_url = direct_googleusercontent_url(h.url)
                if direct_url:
                    break

        if direct_url:
            add_result(results, "Direct Googleusercontent Download", direct_url)

            filename = "video.mp4"
            title_match = re.search(r"<title>([^<]+)</title>", resp.text, re.I)
            if title_match:
                raw = unescape(title_match.group(1)).strip()
                raw = re.sub(r'[\\/:*?"<>|]+', "_", raw)
                if raw and len(raw) < 200:
                    if not raw.lower().endswith((".mp4", ".mkv", ".avi", ".webm")):
                        raw += ".mkv"
                    filename = raw

            add_result(
                results,
                "HBPlay Player Link",
                make_hbplay_link(direct_url, filename=filename),
            )
            return direct_url
    except requests.RequestException:
        pass
    return None


def extract_links(hub_url):
    session = requests.Session()
    session.headers.update(HEADERS)

    response = session.get(hub_url, timeout=20)
    response.raise_for_status()
    html1 = response.text

    generate_url = None
    match = re.search(
        r'<[^>]*\bid=["\']download["\'][^>]*\bhref=["\']([^"\']+)["\']',
        html1,
        re.I,
    )
    if match:
        generate_url = urljoin(response.url, unescape(match.group(1)))

    if not generate_url:
        match = re.search(
            r'https?://gamerxyt\.com/hubcloud\.php\?[^"\'\s<>]+',
            html1,
            re.I,
        )
        if match:
            generate_url = unescape(match.group(0))

    if not generate_url:
        match = re.search(
            r'hubcloud\.php\?host=hubcloud[^"\'\s<>]+',
            html1,
            re.I,
        )
        if match:
            generate_url = urljoin(response.url, unescape(match.group(0)))

    if not generate_url:
        raise ValueError("Generate Download Link not found.")

    response2 = session.get(
        generate_url,
        headers={"Referer": hub_url},
        timeout=30,
        allow_redirects=True,
    )
    response2.raise_for_status()
    html2 = response2.text

    results = []
    gpdl_url = None
    pixel_url = None

    # FSL / R2
    fsl = re.search(
        r'https://[^"\'\s<>]+r2\.cloudflarestorage\.com[^"\'\s<>]*',
        html2,
        re.I,
    )
    if fsl:
        add_result(results, "FSL Server (R2)", unescape(fsl.group(0)))

    # GPDL
    gpdl = re.search(
        r'https://gpdl\.hubcloud\.ist/\?id=[^"\'\s<>]+',
        html2,
        re.I,
    )
    if gpdl:
        gpdl_url = unescape(gpdl.group(0))
        add_result(results, "Server 10Gbps (GPDL)", gpdl_url)

    # Pixel server
    pixel = re.search(
        r'https://pixel\.hubcloud\.ist/\?id=[^"\'\s<>]+',
        html2,
        re.I,
    )
    if pixel:
        pixel_url = unescape(pixel.group(0))
        add_result(results, "Server 10Gbps (Pixel)", pixel_url)

    # Pixeldrain IDs
    pd_ids = []
    js_pd = re.search(
        r'var\s+pxl\s*=\s*["\']https?://[^"\']*pixeldrain[^"\']*/'
        r'(?:u|api/file)/([A-Za-z0-9_-]+)',
        html2,
        re.I,
    )
    if js_pd:
        pd_ids.append(js_pd.group(1))

    for match in re.finditer(
        r'https?://(?:www\.)?'
        r'(?:pixeldrain\.(?:com|dev|net|nl|biz|tech)|pixeldra\.in)'
        r'/(?:u|api/file)/([A-Za-z0-9_-]+)',
        html2,
        re.I,
    ):
        pd_id = match.group(1)
        if pd_id not in pd_ids:
            pd_ids.append(pd_id)

    for index, pd_id in enumerate(pd_ids):
        label = "Pixeldrain" if index == 0 else f"Pixeldrain ({index + 1})"
        add_result(
            results,
            label,
            f"https://pixeldrain.com/u/{pd_id}",
        )
        add_result(
            results,
            label + " Direct Download",
            f"https://pixeldrain.com/api/file/{pd_id}?download",
        )

    # Watch link (pre-built hbplay if present)
    watch = re.search(
        r'https://hbplay\.pages\.dev/\?u=[^"\'\s<>]+',
        html2,
        re.I,
    )
    if watch:
        add_result(results, "Watch Online", unescape(watch.group(0)))

    # Follow gpdl (preferred) and/or pixel to get Direct Googleusercontent
    direct_url = None
    for server_url in (gpdl_url, pixel_url):
        if server_url and not direct_url:
            direct_url = follow_for_googleusercontent(
                session,
                server_url,
                referer=response2.url,
                results=results,
            )

    if not results:
        raise ValueError("No download links found on the generate page.")

    return results


TYPE_ALIASES = {
    "fsl": ("FSL Server (R2)",),
    "r2": ("FSL Server (R2)",),
    "gpdl": ("Server 10Gbps (GPDL)",),
    "pixel": ("Server 10Gbps (Pixel)",),
    "pixeldrain": ("Pixeldrain",),
    "pd": ("Pixeldrain Direct Download",),
    "pixeldrain_direct": ("Pixeldrain Direct Download",),
    "direct": ("Direct Googleusercontent Download",),
    "google": ("Direct Googleusercontent Download",),
    "googleusercontent": ("Direct Googleusercontent Download",),
    "hbplay": ("HBPlay Player Link",),
    "watch": ("Watch Online",),
}


def pick_result(results, type_param=None):
    if not results:
        return None

    if not type_param:
        preferred = (
            "Direct Googleusercontent Download",
            "FSL Server (R2)",
            "Pixeldrain Direct Download",
            "Server 10Gbps (GPDL)",
            "Server 10Gbps (Pixel)",
            "Pixeldrain",
            "HBPlay Player Link",
            "Watch Online",
        )
        for target in preferred:
            for name, url in results:
                if name == target:
                    return url
        return results[0][1]

    key = type_param.strip().lower()
    targets = TYPE_ALIASES.get(key, (key,))

    for target in targets:
        for name, url in results:
            if name.lower() == target.lower():
                return url

    for target in targets:
        for name, url in results:
            if target.lower() in name.lower():
                return url

    return None


def build_redirects(source_url):
    base = request.host_url.rstrip("/")
    encoded_source = quote(source_url, safe="")
    return {
        key: (
            f"{base}/url?url={encoded_source}"
            f"&type={quote(key, safe='')}"
        )
        for key in REDIRECT_TYPES
    }


@app.route("/", methods=["GET", "POST"])
def index():
    hub_urls = ""
    sources = None
    error = None

    if request.method == "POST":
        hub_urls = (request.form.get("hub_urls") or "").strip()
        urls = list(dict.fromkeys(
            line.strip()
            for line in hub_urls.splitlines()
            if line.strip()
        ))

        if not urls:
            error = "Enter at least one HubCloud URL."
        else:
            sources = []
            errors = []

            for source_url in urls:
                parsed = urlparse(source_url)
                source = {
                    "url": source_url,
                    "links": [],
                    "redirects": build_redirects(source_url),
                    "error": None,
                }

                if (
                    parsed.scheme not in ("http", "https")
                    or not parsed.netloc
                ):
                    source["error"] = "Invalid HTTP/HTTPS URL."
                    errors.append(source_url + " — Invalid URL.")
                else:
                    try:
                        extracted = extract_links(source_url)
                        source["links"] = [
                            {"name": name, "url": url}
                            for name, url in extracted
                        ]
                    except Exception as exc:
                        source["error"] = str(exc)
                        errors.append(f"{source_url} — {exc}")

                sources.append(source)

            if errors:
                error = "Some URLs could not be processed:\n" + "\n".join(errors)

    return render_template_string(
        HTML,
        hub_urls=hub_urls,
        sources=sources,
        error=error,
        redirect_types=REDIRECT_TYPES,
    )


@app.route("/api", methods=["POST"])
def api():
    data = request.get_json(silent=True) or {}
    raw_urls = data.get("hub_urls") or data.get("hub_url") or ""

    if isinstance(raw_urls, list):
        urls = [
            str(url).strip()
            for url in raw_urls
            if str(url).strip()
        ]
    else:
        urls = [
            line.strip()
            for line in str(raw_urls).splitlines()
            if line.strip()
        ]

    if not urls:
        return jsonify({"error": "hub_urls is required"}), 400

    output = []
    for source_url in urls:
        try:
            links = extract_links(source_url)
            output.append({
                "source": source_url,
                "links": [
                    {"name": name, "url": url}
                    for name, url in links
                ],
                "redirects": build_redirects(source_url),
            })
        except Exception as exc:
            output.append({
                "source": source_url,
                "error": str(exc),
            })

    return jsonify({"results": output})


@app.route("/url", methods=["GET"])
def url_redirect():
    hub_url = (request.args.get("url") or "").strip()
    type_param = (
        request.args.get("type")
        or request.args.get("server")
        or ""
    ).strip()

    if not hub_url:
        return jsonify({
            "error": "Missing url query parameter",
            "types": list(REDIRECT_TYPES),
        }), 400

    parsed = urlparse(hub_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return jsonify({"error": "Invalid HTTP/HTTPS URL"}), 400

    try:
        results = extract_links(hub_url)
    except requests.RequestException as exc:
        return jsonify({"error": f"Network error: {exc}"}), 502
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": f"Extraction error: {exc}"}), 500

    target = pick_result(results, type_param or None)
    if not target:
        return jsonify({
            "error": f"No matching link for type={type_param!r}",
            "available": [
                {"name": name, "url": url}
                for name, url in results
            ],
            "types": list(REDIRECT_TYPES),
        }), 404

    return redirect(target, code=302)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
    )
