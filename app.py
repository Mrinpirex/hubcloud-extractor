import re
import base64
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

HTML_TEMPLATE = """
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
    --border:#2d3139;
}
* {box-sizing:border-box;margin:0;padding:0}
body {
    font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
    background:var(--bg);
    color:var(--text);
    min-height:100vh;
    padding:24px 14px;
}
.container {max-width:900px;margin:auto}
h1 {
    font-size:1.7rem;
    margin-bottom:8px;
    color:var(--accent);
}
.subtitle {
    color:var(--muted);
    margin-bottom:22px;
    line-height:1.5;
}
form,.card,.help,.error {
    background:var(--card);
    border:1px solid var(--border);
    border-radius:12px;
    padding:18px;
    margin-bottom:16px;
}
label {
    display:block;
    font-weight:600;
    margin-bottom:10px;
}
textarea {
    width:100%;
    min-height:160px;
    resize:vertical;
    padding:12px;
    border:1px solid var(--border);
    border-radius:8px;
    background:var(--bg);
    color:var(--text);
    font:inherit;
}
button {
    cursor:pointer;
    border:0;
    border-radius:7px;
    padding:10px 13px;
    font-weight:600;
}
button:disabled {opacity:.5;cursor:wait}
.submit {
    margin-top:12px;
    width:100%;
    padding:14px;
    background:var(--accent);
    color:#0f1117;
    font-size:1rem;
}
.toolbar {
    display:flex;
    flex-wrap:wrap;
    gap:8px;
    margin-bottom:16px;
}
.toolbar button {flex:1;min-width:150px}
.copy-direct {background:var(--accent);color:#111}
.copy-labeled {background:var(--green);color:#111}
.copy-redirect {background:var(--orange);color:#111}
.card h3 {
    color:var(--accent);
    font-size:.95rem;
    margin-bottom:12px;
    overflow-wrap:anywhere;
}
.small {
    color:var(--muted);
    font-size:.78rem;
    margin-bottom:5px;
}
.source {
    overflow-wrap:anywhere;
    font-size:.85rem;
    margin-bottom:14px;
}
.link {
    padding:12px 0;
    border-top:1px solid var(--border);
}
.link a {
    display:block;
    color:var(--text);
    overflow-wrap:anywhere;
    text-decoration:none;
    font-size:.87rem;
}
.link a:hover {color:var(--accent)}
.link.redirect a {color:var(--orange)}
.actions {
    display:flex;
    flex-wrap:wrap;
    gap:7px;
    margin-top:8px;
}
.mini {
    background:var(--bg);
    color:var(--text);
    border:1px solid var(--border);
    padding:6px 10px;
    font-size:.78rem;
}
.help {color:var(--muted);line-height:1.6}
.error {
    color:#ff9b9b;
    white-space:pre-wrap;
    overflow-wrap:anywhere;
}
.status {
    color:var(--green);
    margin:10px 0;
}
footer {
    text-align:center;
    color:var(--muted);
    font-size:.8rem;
    margin-top:28px;
}
</style>
</head>
<body>
<div class="container">

<h1>Multi URL Link Extractor</h1>
<p class="subtitle">
Paste multiple HubCloud URLs, one per line.
Extract available servers and copy all links together.
</p>

<form method="POST" action="/" id="extract-form">
<label for="hub_url">HubCloud URLs</label>
<textarea id="hub_url" name="hub_url"
placeholder="https://hubcloud.ist/drive/link1
https://hubcloud.ist/drive/link2"
required>{{ hub_url or '' }}</textarea>
<button class="submit" type="submit" id="submit-btn">
Extract All URLs
</button>
</form>

{% if error %}
<div class="error">{{ error }}</div>
{% endif %}

{% if results %}
<div class="help">
<strong>Available link types</strong><br>
FSL / R2, GPDL, Pixel, Pixeldrain, direct download,
HBPlay and Watch links, whenever available.
Redirect links use this application's /url endpoint.
</div>

<div class="toolbar">
<button type="button" class="copy-direct"
onclick="copyLinks('direct',this)">
Copy All Direct Links
</button>
<button type="button" class="copy-labeled"
onclick="copyLinks('labeled',this)">
Copy All Types + Labels
</button>
<button type="button" class="copy-redirect"
onclick="copyLinks('redirect',this)">
Copy All Redirect Links
</button>
</div>

<div id="copy-status" class="status"></div>

{% for item in results %}
<div class="card">
<h3>{{ item.name }}</h3>

<div class="small">Source URL</div>
<div class="source">{{ item.source }}</div>

<div class="link">
<div class="small">Extracted link</div>
<a href="{{ item.url }}" target="_blank" rel="noopener noreferrer">
{{ item.url }}
</a>
<div class="actions">
<button type="button" class="mini"
onclick="copyText({{ item.url|tojson }},this)">
Copy
</button>
<a class="mini" href="{{ item.url }}"
target="_blank" rel="noopener noreferrer">Open</a>
</div>
</div>

<div class="link redirect">
<div class="small">Redirect link — share this</div>
<a href="{{ item.redirect }}"
target="_blank" rel="noopener noreferrer">
{{ item.redirect }}
</a>
<div class="actions">
<button type="button" class="mini"
onclick="copyText({{ item.redirect|tojson }},this)">
Copy
</button>
<a class="mini" href="{{ item.redirect }}"
target="_blank" rel="noopener noreferrer">Open</a>
</div>
</div>
</div>
{% endfor %}

<script>
const results = {{ results|tojson }};

async function copyText(text, button) {
    try {
        await navigator.clipboard.writeText(text);
        if (button) {
            const old = button.textContent;
            button.textContent = "Copied!";
            setTimeout(() => button.textContent = old, 1400);
        }
        return true;
    } catch (err) {
        window.prompt("Copy the text below:", text);
        return false;
    }
}

async function copyLinks(mode, button) {
    let text = "";

    if (mode === "redirect") {
        text = results.map(r => r.redirect).join("\\n");
    } else if (mode === "labeled") {
        text = results.map(r =>
            "Source: " + r.source + "\\n" +
            r.name + ": " + r.url + "\\n" +
            "Redirect: " + r.redirect
        ).join("\\n\\n");
    } else {
        text = results.map(r =>
            r.name + ": " + r.url
        ).join("\\n");
    }

    await copyText(text, button);
    const status = document.getElementById("copy-status");
    if (status) status.textContent = "Copy action completed.";
}

document.getElementById("extract-form").addEventListener("submit", () => {
    const button = document.getElementById("submit-btn");
    button.disabled = true;
    button.textContent = "Extracting URLs...";
});
</script>
{% endif %}

<footer>Flask · Heroku compatible · Multi URL Link Extractor</footer>
</div>
</body>
</html>
"""


def direct_googleusercontent_url(url):
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
    video_url,
    filename="video.mp4",
    mime_type="video/mp4",
):
    encoded_url = base64.b64encode(
        video_url.encode("utf-8")
    ).decode("ascii")

    encoded_mime = base64.b64encode(
        mime_type.encode("utf-8")
    ).decode("ascii")

    encoded_filename = base64.b64encode(
        filename.encode("utf-8")
    ).decode("ascii")

    return "https://hbplay.pages.dev/?" + urlencode({
        "u": encoded_url,
        "m": encoded_mime,
        "t": encoded_filename,
    })


def add_result(results, name, url):
    if url and not any(existing == url for _, existing in results):
        results.append((name, url))


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
        generate_url = urljoin(
            response.url,
            unescape(match.group(1)),
        )

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
            generate_url = urljoin(
                response.url,
                unescape(match.group(0)),
            )

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
    pixel_url = None

    # FSL / R2
    fsl = re.search(
        r'https://[^"\'\s<>]+r2\.cloudflarestorage\.com[^"\'\s<>]*',
        html2,
        re.I,
    )
    if fsl:
        add_result(
            results,
            "FSL Server (R2)",
            unescape(fsl.group(0)),
        )

    # GPDL
    gpdl = re.search(
        r'https://gpdl\.hubcloud\.ist/\?id=[^"\'\s<>]+',
        html2,
        re.I,
    )
    if gpdl:
        add_result(
            results,
            "Server 10Gbps (GPDL)",
            unescape(gpdl.group(0)),
        )

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

    # Existing watch link
    watch = re.search(
        r'https://hbplay\.pages\.dev/\?u=[^"\'\s<>]+',
        html2,
        re.I,
    )
    if watch:
        add_result(
            results,
            "Watch Online",
            unescape(watch.group(0)),
        )

    # Follow Pixel server to Googleusercontent
    if pixel_url:
        pixel_response = session.get(
            pixel_url,
            headers={"Referer": response2.url},
            timeout=30,
            allow_redirects=True,
        )

        direct_url = direct_googleusercontent_url(pixel_response.url)

        if direct_url:
            add_result(
                results,
                "Direct Googleusercontent Download",
                direct_url,
            )

            add_result(
                results,
                "HBPlay Player Link",
                make_hbplay_link(direct_url),
            )

    if not results:
        raise ValueError("No download links found on the generate page.")

    return results


def name_to_type(name):
    n = name.lower()

    if "fsl" in n or "(r2)" in n:
        return "fsl"

    if "gpdl" in n:
        return "gpdl"

    if "pixeldrain" in n and "direct" in n:
        return "pd"

    if "pixeldrain" in n:
        return "pixeldrain"

    if "10gbps (pixel)" in n:
        return "pixel"

    if "googleusercontent" in n or n.startswith("direct google"):
        return "direct"

    if "hbplay" in n:
        return "hbplay"

    if "watch" in n:
        return "watch"

    return re.sub(r"[^a-z0-9]+", "_", n).strip("_")


def build_ui_results(hub_url, extracted):
    base = request.host_url.rstrip("/")
    items = []

    for name, url in extracted:
        link_type = name_to_type(name)

        redirect_url = (
            f"{base}/url?url={quote(hub_url, safe='')}"
            f"&type={quote(link_type, safe='')}"
        )

        items.append({
            "name": name,
            "url": url,
            "redirect": redirect_url,
            "type": link_type,
            "source": hub_url,
        })

    return items


@app.route("/", methods=["GET", "POST"])
def index():
    hub_url = ""
    results = None
    error = None

    if request.method == "POST":
        hub_url = (request.form.get("hub_url") or "").strip()

        urls = list(dict.fromkeys(
            line.strip()
            for line in hub_url.splitlines()
            if line.strip()
        ))

        if not urls:
            error = "Please enter at least one HubCloud URL."
        else:
            results = []
            errors = []

            for source_url in urls:
                try:
                    parsed = urlparse(source_url)

                    if parsed.scheme not in ("http", "https"):
                        raise ValueError("URL must use HTTP or HTTPS.")

                    extracted = extract_links(source_url)
                    results.extend(
                        build_ui_results(source_url, extracted)
                    )

                except requests.RequestException as exc:
                    errors.append(
                        f"{source_url} — Network error: {exc}"
                    )

                except ValueError as exc:
                    errors.append(
                        f"{source_url} — {exc}"
                    )

                except Exception as exc:
                    errors.append(
                        f"{source_url} — Unexpected error: {exc}"
                    )

            if not results:
                results = None

            if errors:
                error = (
                    "Some URLs could not be processed:\n"
                    + "\n".join(errors)
                )

    return render_template_string(
        HTML_TEMPLATE,
        hub_url=hub_url,
        results=results,
        error=error,
    )


@app.route("/api", methods=["POST"])
def api():
    data = request.get_json(silent=True) or {}

    hub_url = (
        data.get("hub_url")
        or request.form.get("hub_url")
        or ""
    ).strip()

    if not hub_url:
        return jsonify({
            "error": "hub_url is required"
        }), 400

    urls = list(dict.fromkeys(
        line.strip()
        for line in hub_url.splitlines()
        if line.strip()
    ))

    all_links = []
    errors = []

    for source_url in urls:
        try:
            extracted = extract_links(source_url)

            all_links.append({
                "source": source_url,
                "links": [
                    {"name": name, "url": url}
                    for name, url in extracted
                ],
            })

        except Exception as exc:
            errors.append({
                "source": source_url,
                "error": str(exc),
            })

    return jsonify({
        "success": bool(all_links),
        "results": all_links,
        "errors": errors,
    }), (200 if all_links else 404)


TYPE_ALIASES = {
    "fsl": "FSL Server (R2)",
    "r2": "FSL Server (R2)",
    "gpdl": "Server 10Gbps (GPDL)",
    "pixel": "Server 10Gbps (Pixel)",
    "pixeldrain": "Pixeldrain",
    "pd": "Pixeldrain Direct Download",
    "pixeldrain_direct": "Pixeldrain Direct Download",
    "direct": "Direct Googleusercontent Download",
    "google": "Direct Googleusercontent Download",
    "googleusercontent": "Direct Googleusercontent Download",
    "hbplay": "HBPlay Player Link",
    "watch": "Watch Online",
    "player": "HBPlay Player Link",
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

        for preferred_name in preferred:
            for name, url in results:
                if name == preferred_name:
                    return url

        return results[0][1]

    key = type_param.strip().lower()
    target = TYPE_ALIASES.get(key)

    if target:
        for name, url in results:
            if name == target or name.startswith(target):
                return url

    for name, url in results:
        if key in name.lower() or key in url.lower():
            return url

    return None


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
            "error": "Missing 'url' query parameter",
            "usage": "/url?url=https://hubcloud.ist/drive/xxx&type=fsl",
            "types": list(TYPE_ALIASES.keys()),
        }), 400

    parsed = urlparse(hub_url)

    if parsed.scheme not in ("http", "https"):
        return jsonify({
            "error": "URL must use HTTP or HTTPS."
        }), 400

    try:
        results = extract_links(hub_url)

    except requests.RequestException as exc:
        return jsonify({
            "error": f"Network error: {exc}"
        }), 502

    except ValueError as exc:
        return jsonify({
            "error": str(exc)
        }), 404

    except Exception as exc:
        return jsonify({
            "error": f"Unexpected error: {exc}"
        }), 500

    target = pick_result(results, type_param or None)

    if not target:
        return jsonify({
            "error": f"No matching link for type={type_param!r}",
            "available": [
                {"name": name, "url": url}
                for name, url in results
            ],
            "types": list(TYPE_ALIASES.keys()),
        }), 404

    return redirect(target, code=302)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(__import__("os").environ.get("PORT", 5000)),
        debug=False,
    )
