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

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HubCloud Link Extractor</title>
<style>
:root {
  --bg:#0f1117; --card:#1a1d27; --accent:#4fc3f7;
  --green:#81c784; --orange:#ffb74d; --text:#e8eaed;
  --muted:#9aa0a6; --border:#2d3139;
}
* { box-sizing:border-box; margin:0; padding:0; }
body {
  font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  background:var(--bg); color:var(--text);
  min-height:100vh; padding:2rem 1rem;
}
.container { max-width:900px; margin:auto; }
h1 { font-size:1.75rem; margin-bottom:.4rem; color:var(--accent); }
.subtitle { color:var(--muted); margin-bottom:1.5rem; }
form,.result-card,.help,.error {
  background:var(--card); border:1px solid var(--border);
  border-radius:12px; padding:1.2rem; margin-bottom:1rem;
}
label { display:block; margin-bottom:.5rem; font-weight:600; }
textarea {
  width:100%; min-height:150px; resize:vertical;
  padding:.8rem; border:1px solid var(--border);
  border-radius:8px; background:var(--bg);
  color:var(--text); font:inherit;
}
button,.mini-btn {
  border:0; border-radius:7px; padding:.65rem .85rem;
  cursor:pointer; font-weight:600; font-size:.85rem;
}
button:disabled { opacity:.6; cursor:wait; }
.submit {
  width:100%; margin-top:1rem; padding:.9rem;
  background:var(--accent); color:#0f1117; font-size:1rem;
}
.copy-bar {
  display:flex; flex-wrap:wrap; gap:.55rem; margin:1rem 0;
}
.copy-btn { background:var(--accent); color:#101318; }
.copy-labeled { background:var(--green); }
.copy-redirects { background:var(--orange); }
.copy-fsl { background:#80cbc4; }
.copy-gpdl { background:#90caf9; }
.copy-pd { background:#ce93d8; }
.copy-pixeldrain { background:#f48fb1; }
.copy-hbplay { background:#a5d6a7; }
.copy-watch { background:#ffcc80; }
.result-card h3 {
  font-size:.9rem; color:var(--accent);
  overflow-wrap:anywhere; margin-bottom:.8rem;
}
.link-row { margin-bottom:1rem; }
.link-label {
  font-size:.72rem; color:var(--muted);
  text-transform:uppercase; margin-bottom:.25rem;
}
.link-row a {
  color:var(--text); word-break:break-all;
  overflow-wrap:anywhere; font-size:.85rem; text-decoration:none;
}
.link-row a:hover { color:var(--accent); }
.redirect a { color:var(--orange); }
.row-actions { display:flex; gap:.4rem; flex-wrap:wrap; margin-top:.4rem; }
.mini-btn {
  display:inline-block; border:1px solid var(--border);
  background:var(--bg); color:var(--muted); text-decoration:none;
}
.help { color:var(--muted); line-height:1.5; font-size:.85rem; }
.error { color:#ef9a9a; border-color:#e57373; overflow-wrap:anywhere; }
footer { text-align:center; color:var(--muted); margin-top:2rem; font-size:.8rem; }
@media(max-width:550px) {
  body { padding:1rem .6rem; }
  .copy-btn { flex:1 1 44%; }
}
</style>
</head>
<body>
<div class="container">
  <h1>HubCloud Link Extractor</h1>
  <p class="subtitle">Paste multiple HubCloud URLs, one per line.</p>

  <form method="POST" action="/" id="extract-form">
    <label for="hub_urls">HubCloud URLs</label>
    <textarea id="hub_urls" name="hub_urls" required
      placeholder="https://hubcloud.ist/drive/first-link&#10;https://hubcloud.ist/drive/second-link">{{ hub_urls or '' }}</textarea>
    <button class="submit" type="submit" id="submit-btn">
      Extract All Links
    </button>
  </form>

  {% if error %}
    <div class="error">{{ error }}</div>
  {% endif %}

  {% if source_errors %}
    <div class="error">
      <strong>URLs with errors:</strong>
      <ul style="margin:.5rem 0 0 1.2rem">
      {% for item in source_errors %}
        <li>{{ item.hub_url }} — {{ item.error }}</li>
      {% endfor %}
      </ul>
    </div>
  {% endif %}

  {% if results %}
    <div class="help">
      Server-specific buttons copy matching direct links from all submitted
      URLs. Copy All PD means Pixeldrain direct-download URLs.
      Copy All Pixeldrain means Pixeldrain page URLs.
    </div>

    <div class="copy-bar">
      <button type="button" class="copy-btn"
        onclick="copyLinks('direct',this)">Copy All Direct Links</button>
      <button type="button" class="copy-btn copy-labeled"
        onclick="copyLinks('labeled',this)">Copy with Labels</button>
      <button type="button" class="copy-btn copy-redirects"
        onclick="copyLinks('redirect',this)">Copy All Redirects</button>
    </div>

    <h3>Copy by Server Type</h3>
    <div class="copy-bar">
      <button type="button" class="copy-btn copy-fsl"
        onclick="copyLinks('fsl',this)">Copy All FSL</button>
      <button type="button" class="copy-btn copy-gpdl"
        onclick="copyLinks('gpdl',this)">Copy All GPDL</button>
      <button type="button" class="copy-btn copy-pd"
        onclick="copyLinks('pd',this)">Copy All PD</button>
      <button type="button" class="copy-btn copy-pixeldrain"
        onclick="copyLinks('pixeldrain',this)">Copy All Pixeldrain</button>
      <button type="button" class="copy-btn copy-hbplay"
        onclick="copyLinks('hbplay',this)">Copy All HBPlay</button>
      <button type="button" class="copy-btn copy-watch"
        onclick="copyLinks('watch',this)">Copy All Watch</button>
    </div>

    <div class="results">
    {% for item in results %}
      <div class="result-card">
        <h3>{{ item.source_label }} — {{ item.name }}</h3>

        <div class="link-row">
          <div class="link-label">Direct</div>
          <a href="{{ item.url }}" target="_blank"
             rel="noopener noreferrer">{{ item.url }}</a>
          <div class="row-actions">
            <button type="button" class="mini-btn"
              onclick='copyText({{ item.url | tojson }},this)'>Copy</button>
            <a class="mini-btn" href="{{ item.url }}" target="_blank"
              rel="noopener noreferrer">Open</a>
          </div>
        </div>

        <div class="link-row redirect">
          <div class="link-label">Redirect (share this)</div>
          <a href="{{ item.redirect }}" target="_blank"
             rel="noopener noreferrer">{{ item.redirect }}</a>
          <div class="row-actions">
            <button type="button" class="mini-btn"
              onclick='copyText({{ item.redirect | tojson }},this)'>Copy</button>
            <a class="mini-btn" href="{{ item.redirect }}" target="_blank"
              rel="noopener noreferrer">Open Redirect</a>
          </div>
        </div>
      </div>
    {% endfor %}
    </div>

    <script>
    const results = {{ results | tojson }};

    function category(item) {
      const name = (item.name || "").toLowerCase();

      if (name.includes("fsl") || name.includes("(r2)")) {
        return "fsl";
      }
      if (name.includes("gpdl")) {
        return "gpdl";
      }
      if (name.includes("pixeldrain") && name.includes("direct")) {
        return "pd";
      }
      if (name.includes("pixeldrain")) {
        return "pixeldrain";
      }
      if (name.includes("hbplay")) {
        return "hbplay";
      }
      if (name.includes("watch")) {
        return "watch";
      }

      return "";
    }

    async function copyText(text, button) {
      try {
        await navigator.clipboard.writeText(text);
        showCopied(button);
      } catch (e) {
        window.prompt("Copy this text:", text);
      }
    }

    async function copyLinks(mode, button) {
      let selected = results;
      let text = "";

      if (["fsl","gpdl","pd","pixeldrain","hbplay","watch"].includes(mode)) {
        selected = results.filter(item => category(item) === mode);
        text = selected.map(item => item.url).join("\\n");
      } else if (mode === "redirect") {
        text = results.map(item => item.redirect).join("\\n");
      } else if (mode === "labeled") {
        text = results.map(item =>
          item.source_label + " — " + item.name +
          "\\nDirect: " + item.url +
          "\\nRedirect: " + item.redirect
        ).join("\\n\\n");
      } else {
        text = results.map(item => item.url).join("\\n");
      }

      if (!text) {
        alert("No links found for this server type.");
        return;
      }

      await copyText(text, button);
    }

    function showCopied(button) {
      if (!button) return;
      const original = button.textContent;
      button.textContent = "Copied!";
      setTimeout(() => button.textContent = original, 1500);
    }

    document.getElementById("extract-form").addEventListener("submit", () => {
      const button = document.getElementById("submit-btn");
      button.disabled = true;
      button.textContent = "Extracting...";
    });
    </script>
  {% endif %}

  <footer>Deployed on Heroku · Not affiliated with HubCloud</footer>
</div>
</body>
</html>
"""


def direct_googleusercontent_url(url: str) -> str | None:
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

    return match.group(0).rstrip(").,") if match else None


def make_hbplay_link(
    video_url: str,
    filename: str = "video.mp4",
    mime_type: str = "video/mp4",
) -> str:
    return "https://hbplay.pages.dev/?" + urlencode({
        "u": base64.b64encode(video_url.encode()).decode(),
        "m": base64.b64encode(mime_type.encode()).decode(),
        "t": base64.b64encode(filename.encode()).decode(),
    })


def add_result(results: list, name: str, url: str | None) -> None:
    if url and not any(existing == url for _, existing in results):
        results.append((name, url))


def extract_links(hub_url: str) -> list[tuple[str, str]]:
    """Extract links from one HubCloud URL."""
    session = requests.Session()
    session.headers.update(HEADERS)

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

    res2 = session.get(
        generate_url,
        headers={"Referer": hub_url},
        timeout=30,
        allow_redirects=True,
    )
    res2.raise_for_status()
    html2 = res2.text

    results = []
    pixel_url = None

    fsl = re.search(
        r'https://[^"\'\s<>]+r2\.cloudflarestorage\.com[^"\'\s<>]*',
        html2,
        re.I,
    )
    if fsl:
        add_result(results, "FSL Server (R2)", unescape(fsl.group(0)))

    gpdl = re.search(
        r'https://gpdl\.hubcloud\.ist/\?id=[^"\'\s<>]+',
        html2,
        re.I,
    )
    if gpdl:
        add_result(results, "Server 10Gbps (gpdl)", unescape(gpdl.group(0)))

    pixel = re.search(
        r'https://pixel\.hubcloud\.ist/\?id=[^"\'\s<>]+',
        html2,
        re.I,
    )
    if pixel:
        pixel_url = unescape(pixel.group(0))
        add_result(results, "Server 10Gbps (pixel)", pixel_url)

    pd_ids = []

    js_pd = re.search(
        r'var\s+pxl\s*=\s*["\']https?://[^"\']*pixeldrain[^"\']*/(?:u|api/file)/([A-Za-z0-9_-]+)',
        html2,
        re.I,
    )
    if js_pd:
        pd_ids.append(js_pd.group(1))

    for match in re.finditer(
        r'https?://(?:www\.)?(?:pixeldrain\.(?:com|dev|net|nl|biz|tech)|pixeldra\.in)'
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
            f"{label} Direct Download",
            f"https://pixeldrain.com/api/file/{pd_id}?download",
        )

    watch = re.search(
        r'https://hbplay\.pages\.dev/\?u=[^"\'\s<>]+',
        html2,
        re.I,
    )
    if watch:
        add_result(results, "Watch Online", unescape(watch.group(0)))

    if pixel_url:
        pixel_response = session.get(
            pixel_url,
            headers={"Referer": res2.url},
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


def _name_to_type(name: str) -> str:
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


def _build_ui_results(
    hub_url: str,
    results: list[tuple[str, str]],
    source_label: str = "",
) -> list[dict]:
    base = request.host_url.rstrip("/")
    items = []

    for name, url in results:
        result_type = _name_to_type(name)
        redirect_url = (
            f"{base}/url?url={quote(hub_url, safe='')}"
            f"&type={quote(result_type, safe='')}"
        )

        items.append({
            "name": name,
            "url": url,
            "redirect": redirect_url,
            "type": result_type,
            "source_url": hub_url,
            "source_label": source_label or hub_url,
        })

    return items


def _parse_hub_urls(raw_text: str) -> list[str]:
    urls = []
    seen = set()

    for line in (raw_text or "").splitlines():
        url = line.strip()
        if url and url not in seen:
            urls.append(url)
            seen.add(url)

    return urls


def _is_valid_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except ValueError:
        return False


def _extract_many(hub_urls: list[str]) -> tuple[list[dict], list[dict]]:
    combined = []
    sources = []

    for index, hub_url in enumerate(hub_urls, start=1):
        source_label = f"URL {index}: {hub_url}"

        try:
            raw_results = extract_links(hub_url)
            items = _build_ui_results(hub_url, raw_results, source_label)
            combined.extend(items)

            sources.append({
                "index": index,
                "hub_url": hub_url,
                "success": True,
                "count": len(items),
                "error": None,
            })

        except requests.RequestException as exc:
            sources.append({
                "index": index,
                "hub_url": hub_url,
                "success": False,
                "count": 0,
                "error": f"Network error: {exc}",
            })

        except ValueError as exc:
            sources.append({
                "index": index,
                "hub_url": hub_url,
                "success": False,
                "count": 0,
                "error": str(exc),
            })

        except Exception as exc:
            sources.append({
                "index": index,
                "hub_url": hub_url,
                "success": False,
                "count": 0,
                "error": f"Unexpected error: {exc}",
            })

    return combined, sources


@app.route("/", methods=["GET", "POST"])
def index():
    hub_urls_text = ""
    results = None
    error = None
    source_errors = []

    if request.method == "POST":
        hub_urls_text = (
            request.form.get("hub_urls")
            or request.form.get("hub_url")
            or ""
        ).strip()

        hub_urls = _parse_hub_urls(hub_urls_text)

        if not hub_urls:
            error = "Please enter at least one HubCloud URL."
        elif any(not _is_valid_http_url(url) for url in hub_urls):
            error = "Each line must contain a complete HTTP(S) URL."
        else:
            results, source_results = _extract_many(hub_urls)
            source_errors = [
                item for item in source_results if not item["success"]
            ]

            if not results and source_errors:
                error = "No links could be extracted. Check the errors below."

    return render_template_string(
        HTML_TEMPLATE,
        hub_urls=hub_urls_text,
        results=results,
        error=error,
        source_errors=source_errors,
    )


@app.route("/api", methods=["POST"])
def api():
    data = request.get_json(silent=True) or {}

    raw_urls = data.get(
        "hub_urls",
        data.get("urls", request.form.get("hub_urls", "")),
    )
    legacy_url = (
        data.get("hub_url")
        or request.form.get("hub_url")
        or ""
    ).strip()

    if isinstance(raw_urls, list):
        hub_urls = list(dict.fromkeys(
            str(item).strip()
            for item in raw_urls
            if str(item).strip()
        ))
    else:
        hub_urls = _parse_hub_urls(str(raw_urls or ""))

    if not hub_urls and legacy_url:
        hub_urls = [legacy_url]

    if not hub_urls:
        return jsonify({"error": "hub_url or hub_urls is required"}), 400

    invalid_urls = [
        url for url in hub_urls if not _is_valid_http_url(url)
    ]
    if invalid_urls:
        return jsonify({
            "error": "Each URL must be a complete HTTP(S) URL",
            "invalid_urls": invalid_urls,
        }), 400

    all_links = []
    sources = []

    for index, hub_url in enumerate(hub_urls, start=1):
        try:
            extracted = extract_links(hub_url)
            links = [{"name": name, "url": url} for name, url in extracted]

            all_links.extend([
                {
                    **link,
                    "source_url": hub_url,
                    "source_index": index,
                }
                for link in links
            ])

            sources.append({
                "index": index,
                "hub_url": hub_url,
                "success": True,
                "links": links,
            })

        except Exception as exc:
            sources.append({
                "index": index,
                "hub_url": hub_url,
                "success": False,
                "error": str(exc),
            })

    successful = any(source["success"] for source in sources)

    return jsonify({
        "success": successful,
        "sources": sources,
        "links": all_links,
    }), (200 if successful else 502)


TYPE_ALIASES = {
    "fsl": "FSL Server (R2)",
    "r2": "FSL Server (R2)",
    "gpdl": "Server 10Gbps (gpdl)",
    "pixel": "Server 10Gbps (pixel)",
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


def _pick_result(
    results: list[tuple[str, str]],
    type_param: str | None,
) -> str | None:
    if not results:
        return None

    if not type_param:
        preferred_names = (
            "Direct Googleusercontent Download",
            "FSL Server (R2)",
            "Pixeldrain Direct Download",
            "Server 10Gbps (gpdl)",
            "Server 10Gbps (pixel)",
            "Pixeldrain",
            "HBPlay Player Link",
            "Watch Online",
        )

        for preferred in preferred_names:
            for name, url in results:
                if name == preferred:
                    return url

        return results[0][1]

    key = type_param.strip().lower()

    if key in TYPE_ALIASES:
        target = TYPE_ALIASES[key]

        for name, url in results:
            if name == target or name.startswith(target):
                return url

        for name, url in results:
            if target.lower() in name.lower():
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
            "usage": "/url?url=https://hubcloud.ist/drive/xxx&type=direct",
            "types": list(TYPE_ALIASES.keys()),
        }), 400

    if not _is_valid_http_url(hub_url):
        return jsonify({"error": "Invalid HTTP(S) URL"}), 400

    try:
        results = extract_links(hub_url)
    except requests.RequestException as exc:
        return jsonify({"error": f"Network error: {exc}"}), 502
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": f"Unexpected error: {exc}"}), 500

    target = _pick_result(results, type_param or None)

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
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
