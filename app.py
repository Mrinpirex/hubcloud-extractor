import re
import base64
from html import unescape
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

import requests
from flask import Flask, request, render_template_string, jsonify

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HubCloud Link Extractor</title>
  <style>
    :root {
      --bg: #0f1117;
      --card: #1a1d27;
      --accent: #4fc3f7;
      --accent2: #81c784;
      --text: #e8eaed;
      --muted: #9aa0a6;
      --border: #2d3139;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 2rem 1rem;
    }
    .container { max-width: 720px; margin: 0 auto; }
    h1 {
      font-size: 1.75rem;
      margin-bottom: 0.25rem;
      background: linear-gradient(90deg, var(--accent), var(--accent2));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .subtitle { color: var(--muted); margin-bottom: 2rem; font-size: 0.95rem; }
    form {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }
    label { display: block; margin-bottom: 0.5rem; font-weight: 600; font-size: 0.9rem; }
    input[type="url"] {
      width: 100%;
      padding: 0.75rem 1rem;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--bg);
      color: var(--text);
      font-size: 1rem;
      outline: none;
      transition: border-color 0.2s;
    }
    input[type="url"]:focus { border-color: var(--accent); }
    button {
      margin-top: 1rem;
      width: 100%;
      padding: 0.85rem;
      border: none;
      border-radius: 8px;
      background: linear-gradient(135deg, #4fc3f7, #29b6f6);
      color: #0f1117;
      font-weight: 700;
      font-size: 1rem;
      cursor: pointer;
      transition: opacity 0.2s;
    }
    button:hover { opacity: 0.9; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    .error {
      background: #3b1a1a;
      border: 1px solid #e57373;
      color: #ef9a9a;
      padding: 1rem;
      border-radius: 8px;
      margin-bottom: 1.5rem;
    }
    .results { margin-top: 0.5rem; }
    .result-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem 1.25rem;
      margin-bottom: 0.75rem;
    }
    .result-card h3 {
      font-size: 0.85rem;
      color: var(--accent);
      margin-bottom: 0.4rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .result-card a {
      color: var(--text);
      word-break: break-all;
      font-size: 0.9rem;
      text-decoration: none;
    }
    .result-card a:hover { color: var(--accent); text-decoration: underline; }
    .copy-bar {
      display: flex;
      gap: 0.75rem;
      margin-bottom: 1.25rem;
      flex-wrap: wrap;
    }
    .copy-btn {
      flex: 1;
      min-width: 140px;
      padding: 0.7rem 1rem;
      border: none;
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
      font-size: 0.9rem;
    }
    .copy-all { background: var(--accent); color: #0f1117; }
    .copy-labeled { background: var(--accent2); color: #0f1117; }
    footer {
      margin-top: 3rem;
      text-align: center;
      color: var(--muted);
      font-size: 0.8rem;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>HubCloud Link Extractor</h1>
    <p class="subtitle">Paste a HubCloud drive link to extract direct download &amp; player URLs.</p>

    <form method="POST" action="/" id="extract-form">
      <label for="hub_url">HubCloud URL</label>
      <input
        type="url"
        id="hub_url"
        name="hub_url"
        placeholder="https://hubcloud.ist/drive/..."
        value="{{ hub_url or '' }}"
        required
      >
      <button type="submit" id="submit-btn">Extract Links</button>
    </form>

    {% if error %}
    <div class="error">{{ error }}</div>
    {% endif %}

    {% if results %}
    <div class="copy-bar">
      <button class="copy-btn copy-all" onclick="copyLinks(false)">Copy All Links</button>
      <button class="copy-btn copy-labeled" onclick="copyLinks(true)">Copy with Labels</button>
    </div>
    <div class="results">
      {% for name, link in results %}
      <div class="result-card">
        <h3>{{ name }}</h3>
        <a href="{{ link }}" target="_blank" rel="noopener">{{ link }}</a>
      </div>
      {% endfor %}
    </div>
    <script>
      const results = {{ results | tojson }};
      function copyLinks(labeled) {
        const text = labeled
          ? results.map(([n, u]) => n + ": " + u).join("\\n")
          : results.map(([, u]) => u).join("\\n");
        navigator.clipboard.writeText(text).then(() => {
          const btn = event.target;
          const orig = btn.textContent;
          btn.textContent = "Copied!";
          setTimeout(() => btn.textContent = orig, 1500);
        });
      }
    </script>
    {% endif %}

    <footer>Deployed on Heroku · Not affiliated with HubCloud</footer>
  </div>
</body>
</html>
"""


def direct_googleusercontent_url(url: str) -> str | None:
    """Extract a direct Googleusercontent URL from a wrapped URL."""
    if not url:
        return None

    url = unescape(url.strip())
    parsed = urlparse(url)

    if parsed.path.lower().endswith("/dl.php"):
        wrapped = parse_qs(parsed.query).get("link", [None])[0]
        if wrapped:
            url = wrapped

    match = re.search(
        r'https?://video-downloads\.googleusercontent\.com/[^&\s<>"\']+',
        url,
        re.I,
    )
    if match:
        return match.group(0).rstrip(").,")
    return None


def make_hbplay_link(
    video_url: str,
    filename: str = "video.mp4",
    mime_type: str = "video/mp4",
) -> str:
    """Build an HBPlay URL using Base64-encoded parameters."""
    encoded_url = base64.b64encode(video_url.encode("utf-8")).decode("ascii")
    encoded_mime = base64.b64encode(mime_type.encode("utf-8")).decode("ascii")
    encoded_filename = base64.b64encode(filename.encode("utf-8")).decode("ascii")
    return "https://hbplay.pages.dev/?" + urlencode(
        {"u": encoded_url, "m": encoded_mime, "t": encoded_filename}
    )


def add_result(results: list, name: str, url: str | None) -> None:
    if url and not any(existing == url for _, existing in results):
        results.append((name, url))


def extract_links(hub_url: str) -> list[tuple[str, str]]:
    """
    Core extraction logic.
    Returns a list of (label, url) tuples.
    Raises ValueError / requests.RequestException on failure.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    # STEP 1: Fetch HubCloud page
    res1 = session.get(hub_url, timeout=20)
    res1.raise_for_status()
    html1 = res1.text

    generate_url = None

    match = re.search(
        r'<[^>]*\bid=["\']download["\'][^>]*\bhref=["\']([^"\']+)["\']',
        html1,
        re.I,
    )
    if match:
        generate_url = urljoin(res1.url, unescape(match.group(1)))

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
            generate_url = urljoin(res1.url, unescape(match.group(0)))

    if not generate_url:
        raise ValueError("Generate Download Link not found on the page.")

    # STEP 2: Fetch Generate page
    res2 = session.get(
        generate_url,
        headers={"Referer": hub_url},
        timeout=30,
        allow_redirects=True,
    )
    res2.raise_for_status()
    html2 = res2.text

    results: list[tuple[str, str]] = []
    pixel_url = None

    # FSL / Cloudflare R2
    fsl = re.search(
        r'https://[^"\'\s<>]+r2\.cloudflarestorage\.com[^"\'\s<>]*',
        html2,
        re.I,
    )
    if fsl:
        add_result(results, "FSL Server (R2)", unescape(fsl.group(0)))

    # GPDL server
    gpdl = re.search(
        r'https://gpdl\.hubcloud\.ist/\?id=[^"\'\s<>]+',
        html2,
        re.I,
    )
    if gpdl:
        add_result(results, "Server 10Gbps (gpdl)", unescape(gpdl.group(0)))

    # Pixel server
    pixel = re.search(
        r'https://pixel\.hubcloud\.ist/\?id=[^"\'\s<>]+',
        html2,
        re.I,
    )
    if pixel:
        pixel_url = unescape(pixel.group(0))
        add_result(results, "Server 10Gbps (pixel)", pixel_url)

    # Pixeldrain — page often has a stale HTML link + the real ID in JS (var pxl = "...")
    # Prefer the JS variable; fall back to all unique IDs found.
    pd_ids: list[str] = []

    # 1) JS variable (most reliable)
    js_pd = re.search(
        r'var\s+pxl\s*=\s*["\']https?://[^"\']*pixeldrain[^"\']*/(?:u|api/file)/([A-Za-z0-9_-]+)',
        html2,
        re.I,
    )
    if js_pd:
        pd_ids.append(js_pd.group(1))

    # 2) All other pixeldrain links on the page
    for m in re.finditer(
        r'https?://(?:www\.)?(?:pixeldrain\.(?:com|dev|net|nl|biz|tech)|pixeldra\.in)'
        r'/(?:u|api/file)/([A-Za-z0-9_-]+)',
        html2,
        re.I,
    ):
        if m.group(1) not in pd_ids:
            pd_ids.append(m.group(1))

    for i, pd_id in enumerate(pd_ids):
        label = "Pixeldrain" if i == 0 else f"Pixeldrain ({i + 1})"
        pd_page = f"https://pixeldrain.com/u/{pd_id}"
        pd_direct = f"https://pixeldrain.com/api/file/{pd_id}?download"
        add_result(results, label, pd_page)
        add_result(results, f"{label} Direct Download", pd_direct)

    # Watch Online (already present)
    watch = re.search(
        r'https://hbplay\.pages\.dev/\?u=[^"\'\s<>]+',
        html2,
        re.I,
    )
    if watch:
        add_result(results, "Watch Online", unescape(watch.group(0)))

    # STEP 3: Follow Pixel → direct Googleusercontent
    if pixel_url:
        pixel_response = session.get(
            pixel_url,
            headers={"Referer": res2.url},
            timeout=30,
            allow_redirects=True,
        )
        direct_url = direct_googleusercontent_url(pixel_response.url)
        if direct_url:
            add_result(results, "Direct Googleusercontent Download", direct_url)
            player_url = make_hbplay_link(direct_url)
            add_result(results, "HBPlay Player Link", player_url)

    if not results:
        raise ValueError("No download links found on the generate page.")

    return results


@app.route("/", methods=["GET", "POST"])
def index():
    hub_url = ""
    results = None
    error = None

    if request.method == "POST":
        hub_url = (request.form.get("hub_url") or "").strip()
        if not hub_url:
            error = "Please enter a HubCloud URL."
        else:
            try:
                results = extract_links(hub_url)
            except requests.RequestException as e:
                error = f"Network error: {e}"
            except ValueError as e:
                error = str(e)
            except Exception as e:
                error = f"Unexpected error: {e}"

    return render_template_string(
        HTML_TEMPLATE,
        hub_url=hub_url,
        results=results,
        error=error,
    )


@app.route("/api", methods=["POST"])
def api():
    """JSON API endpoint for programmatic use."""
    data = request.get_json(silent=True) or {}
    hub_url = (data.get("hub_url") or request.form.get("hub_url") or "").strip()

    if not hub_url:
        return jsonify({"error": "hub_url is required"}), 400

    try:
        results = extract_links(hub_url)
        return jsonify(
            {
                "success": True,
                "links": [{"name": name, "url": url} for name, url in results],
            }
        )
    except requests.RequestException as e:
        return jsonify({"error": f"Network error: {e}"}), 502
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
