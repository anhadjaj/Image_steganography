# from PIL import Image

# MAGIC = b"STEG"

# def bytes_to_bits(data: bytes):
#     for byte in data:
#         for i in range(7, -1, -1):
#             yield (byte >> i) & 1

# def xor_bytes(data: bytes, key: str | None) -> bytes:
#     if not key:
#         return data
#     k = key.encode("utf-8")
#     return bytes(b ^ k[i % len(k)] for i, b in enumerate(data))

# def image_to_channel_list(img: Image.Image):
#     if img.mode != "RGB":
#         img = img.convert("RGB")
#     pixels = list(img.getdata())
#     chans = []
#     for r, g, b in pixels:
#         chans.extend((r, g, b))
#     return img, chans

# def channel_list_to_image(img: Image.Image, chans: list[int]):
#     it = iter(chans)
#     pixels = [(next(it), next(it), next(it)) for _ in range(img.width * img.height)]
#     out = Image.new("RGB", img.size)
#     out.putdata(pixels)
#     return out

# def encode(input_path: str, output_path: str, message: str, key: str | None = None):
#     img = Image.open(input_path)
#     img, chans = image_to_channel_list(img)

#     payload = xor_bytes(message.encode("utf-8"), key)
#     header = MAGIC + len(payload).to_bytes(4, "big")
#     all_bytes = header + payload
#     bits = list(bytes_to_bits(all_bytes))

#     if len(bits) > len(chans):
#         raise ValueError("Reduce message size.")

#     out_chans = chans[:]
#     for i, bit in enumerate(bits):
#         out_chans[i] = (out_chans[i] & ~1) | bit

#     stego_img = channel_list_to_image(img, out_chans)
#     stego_img.save(output_path, format="PNG")
#     print(f"Message embedded into '{output_path}'")

# if __name__ == "__main__":
#     input_path = input("Enter input image path: ").strip()
#     output_path = input("Enter output image path (e.g., stego.png): ").strip()
#     message = input("Enter the message to hide: ").strip()
#     key = input("Enter an optional key : ").strip() or None

#     encode(input_path, output_path, message, key)


# app.py
from io import BytesIO
from PIL import Image
from flask import Flask, request, send_file, render_template_string

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload limit

MAGIC = b"STEG"

# --- Stego utilities (from your script, adapted) ---

def bytes_to_bits(data: bytes):
    for byte in data:
        for i in range(7, -1, -1):
            yield (byte >> i) & 1

def xor_bytes(data: bytes, key: str | None) -> bytes:
    if not key:
        return data
    k = key.encode("utf-8")
    if not k:
        return data
    return bytes(b ^ k[i % len(k)] for i, b in enumerate(data))

def image_to_channel_list(img: Image.Image):
    if img.mode != "RGB":
        img = img.convert("RGB")
    pixels = list(img.getdata())
    chans = []
    for r, g, b in pixels:
        chans.extend((r, g, b))
    return img, chans

def channel_list_to_image(img: Image.Image, chans: list[int]):
    it = iter(chans)
    pixels = [(next(it), next(it), next(it)) for _ in range(img.width * img.height)]
    out = Image.new("RGB", img.size)
    out.putdata(pixels)
    return out

def encode_image_bytes(image_bytes: bytes, message: str, key: str | None):
    img = Image.open(BytesIO(image_bytes))
    img, chans = image_to_channel_list(img)

    payload = xor_bytes(message.encode("utf-8"), key)
    header = MAGIC + len(payload).to_bytes(4, "big")
    all_bytes = header + payload
    bits = list(bytes_to_bits(all_bytes))

    if len(bits) > len(chans):
        raise ValueError(
            f"Message too large for this image. Need {len(bits)} bits, have {len(chans)} bits "
            f"(~{len(chans)//8} bytes). Try a larger image or shorter message."
        )

    out_chans = chans[:]
    for i, bit in enumerate(bits):
        out_chans[i] = (out_chans[i] & ~1) | bit

    stego_img = channel_list_to_image(img, out_chans)

    buf = BytesIO()
    stego_img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# --- UI ---

PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Image Steganography — Encoder</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {
      --bg: #0f172a;        /* slate-900 */
      --card: #111827;      /* gray-900 */
      --muted: #94a3b8;     /* slate-400 */
      --text: #e5e7eb;      /* gray-200 */
      --accent: #6366f1;    /* indigo-500 */
      --accent-2: #4f46e5;  /* indigo-600 */
      --success: #22c55e;   /* green-500 */
      --danger: #ef4444;    /* red-500 */
      --border: #1f2937;    /* gray-800 */
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; padding: 0;
      background: radial-gradient(1200px 800px at 20% -10%, rgba(99,102,241,0.15), transparent 60%),
                  radial-gradient(1000px 500px at 120% 10%, rgba(34,197,94,0.10), transparent 60%),
                  var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Inter, "Helvetica Neue", Arial, "Apple Color Emoji","Segoe UI Emoji";
      min-height: 100vh;
      display: grid;
      place-items: center;
    }
    .wrap {
      width: min(720px, 92vw);
      background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.02));
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: 0 30px 80px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.05);
      padding: 28px;
      backdrop-filter: blur(10px);
    }
    h1 {
      margin: 0 0 6px;
      letter-spacing: 0.5px;
      font-size: 1.5rem;
    }
    p.sub {
      margin: 0 0 22px;
      color: var(--muted);
      font-size: 0.95rem;
    }
    form {
      display: grid;
      gap: 14px;
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }
    .field {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 14px;
    }
    .field label {
      display: block;
      font-size: 0.82rem;
      color: var(--muted);
      margin-bottom: 6px;
    }
    .field input[type="text"],
    .field input[type="password"],
    .field textarea {
      width: 100%;
      background: transparent;
      border: none;
      color: var(--text);
      font-size: 0.98rem;
      outline: none;
      resize: vertical;
    }
    .filebox {
      display: grid; gap: 8px;
    }
    .filebox input[type="file"] {
      width: 100%;
      padding: 10px;
      background: #0b1220;
      border: 1px dashed #334155;
      border-radius: 10px;
      color: var(--muted);
    }
    .btnrow {
      display: flex;
      gap: 10px;
      justify-content: flex-end;
      margin-top: 6px;
    }
    button {
      appearance: none; border: none; cursor: pointer;
      padding: 10px 16px; border-radius: 12px; font-weight: 600;
      background: linear-gradient(180deg, var(--accent), var(--accent-2));
      color: white; letter-spacing: 0.2px;
      box-shadow: 0 10px 25px rgba(99,102,241,0.35);
      transition: transform 0.05s ease, box-shadow 0.2s ease;
    }
    button:hover { box-shadow: 0 14px 30px rgba(99,102,241,0.45); }
    button:active { transform: translateY(1px); }
    .hint {
      font-size: 0.85rem; color: var(--muted);
      margin-top: 4px;
    }
    .note {
      margin-top: 10px; padding: 10px 12px; border-radius: 10px;
      background: rgba(34,197,94,0.12); color: #c8facc; border: 1px solid rgba(34,197,94,0.25);
    }
    .error {
      margin-top: 10px; padding: 10px 12px; border-radius: 10px;
      background: rgba(239,68,68,0.12); color: #ffd1d1; border: 1px solid rgba(239,68,68,0.25);
    }
    .footer {
      margin-top: 18px;
      color: var(--muted);
      font-size: 0.8rem;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>🔐 Image Steganography — Encoder</h1>
    <p class="sub">Hide a text message inside an image. Output is saved as a PNG for lossless integrity.</p>

    {% if error %}
      <div class="error">{{ error }}</div>
    {% elif ok %}
      <div class="note">Success! Your file is downloading… If it didn’t, click the button again.</div>
    {% endif %}

    <form id="encodeForm" method="post" action="/" enctype="multipart/form-data" target="_blank">
      <div class="field filebox">
        <label for="image">Cover Image (PNG or JPG)</label>
        <input id="image" name="image" type="file" accept=".png,.jpg,.jpeg" required />
        <div class="hint">Tip: bigger images allow longer messages (capacity ≈ width×height×3 / 8 bytes).</div>
      </div>

      <div class="field">
        <label for="message">Message to hide</label>
        <textarea id="message" name="message" rows="4" placeholder="Type your secret message…" required></textarea>
      </div>

      <div class="grid">
        <div class="field">
          <label for="key">Optional key (XOR obfuscation)</label>
          <input id="key" name="key" type="password" placeholder="Leave blank to skip" />
        </div>
        <div class="field">
          <label for="filename">Output filename</label>
          <input id="filename" name="filename" type="text" placeholder="stego.png" value="stego.png" />
        </div>
      </div>

      <div class="btnrow">
        <button type="submit">Encrypt & Download</button>
      </div>
      <div class="footer">Note: The key provides light obfuscation (XOR). For strong security, encrypt first, then embed.</div>
    </form>
  </div>
</body>
</html>
"""

# Routes

@app.get("/")
def index_get():
    return render_template_string(PAGE)

@app.post("/")
def index_post():
    try:
        if "image" not in request.files or request.files["image"].filename == "":
            return render_template_string(PAGE, error="Please choose an image (PNG/JPG).")

        file = request.files["image"]
        if not allowed_file(file.filename):
            return render_template_string(PAGE, error="Unsupported file type. Use PNG or JPG/JPEG.")

        message = (request.form.get("message") or "").strip()
        if not message:
            return render_template_string(PAGE, error="Message cannot be empty.")

        key = (request.form.get("key") or "").strip() or None
        out_name = (request.form.get("filename") or "stego.png").strip()
        if not out_name.lower().endswith(".png"):
            out_name += ".png"

        img_bytes = file.read()
        stego_buffer = encode_image_bytes(img_bytes, message, key)

        # prompt the file download
        return send_file(
            stego_buffer,
            mimetype="image/png",
            as_attachment=True,
            download_name=secure_filename(out_name),
        )
    except Exception as e:
        return render_template_string(PAGE, error=str(e))

def allowed_file(name: str) -> bool:
    name = name.lower()
    return name.endswith(".png") or name.endswith(".jpg") or name.endswith(".jpeg")

def secure_filename(name: str) -> str:
    # very small sanitizer; good enough for client downloads
    name = name.strip().replace("\\", "/").split("/")[-1]
    if not name:
        return "stego.png"
    # remove weird chars
    safe = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_", ".", " "))
    return safe or "stego.png"

if __name__ == "__main__":
    # For local dev only. In production, use a proper WSGI server.
    app.run(debug=True)

