from io import BytesIO
from PIL import Image
from flask import Flask, request, send_file, render_template_string, redirect, url_for

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

MAGIC = b"STEG"

# --------------------- CORE UTILS ---------------------

def bytes_to_bits(data: bytes):
    for byte in data:
        for i in range(7, -1, -1):
            yield (byte >> i) & 1

def bits_to_bytes(bits):
    out = bytearray()
    acc = 0
    cnt = 0
    for bit in bits:
        acc = (acc << 1) | (bit & 1)
        cnt += 1
        if cnt == 8:
            out.append(acc)
            acc = 0
            cnt = 0
    return bytes(out)

def xor_bytes(data: bytes, key: str | None) -> bytes:
    if not key:
        return data
    k = key.encode("utf-8")
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
        raise ValueError("Message too large for this image. Use a larger image or shorter message.")

    out_chans = chans[:]
    for i, bit in enumerate(bits):
        out_chans[i] = (out_chans[i] & ~1) | bit

    stego_img = channel_list_to_image(img, out_chans)
    buf = BytesIO()
    stego_img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def decode_image_bytes(image_bytes: bytes, key: str | None = None) -> str:
    img = Image.open(BytesIO(image_bytes))
    img, chans = image_to_channel_list(img)

    header_bits = [(chans[i] & 1) for i in range(64)]
    header = bits_to_bytes(header_bits)
    if len(header) < 8 or header[:4] != MAGIC:
        raise ValueError("This image doesn’t appear to contain hidden data.")

    payload_len = int.from_bytes(header[4:8], "big")
    payload_bits = [(chans[i] & 1) for i in range(64, 64 + payload_len * 8)]
    payload = bits_to_bytes(payload_bits)
    payload = xor_bytes(payload, key)
    return payload.decode("utf-8", errors="strict")

# --------------------- STYLESHEET & PAGES ---------------------

BASE_CSS = """
<style>
body {
  margin: 0; padding: 0;
  background: #0f172a;
  color: #e5e7eb;
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  display: flex; justify-content: center; align-items: center; min-height: 100vh;
}
.container {
  background: #111827;
  padding: 30px;
  border-radius: 18px;
  box-shadow: 0 25px 60px rgba(0,0,0,0.45);
  width: min(700px, 90%);
}
h1 {
  color: #a5b4fc;
  text-align: center;
  margin-bottom: 10px;
}
p.sub { text-align: center; color: #9ca3af; margin-bottom: 25px; }
a.btn, button {
  background: linear-gradient(90deg, #6366f1, #4f46e5);
  border: none; color: white;
  padding: 12px 20px; border-radius: 12px;
  font-weight: 600; cursor: pointer; text-decoration: none;
  display: inline-block; margin: 10px;
  box-shadow: 0 10px 25px rgba(99,102,241,0.35);
}
a.btn:hover, button:hover { box-shadow: 0 14px 30px rgba(99,102,241,0.45); }
label { display: block; font-size: 0.9rem; color: #9ca3af; margin-bottom: 6px; }
input, textarea {
  width: 100%; padding: 10px;
  border: 1px solid #374151; border-radius: 10px;
  background: #0b1220; color: #e5e7eb;
  font-size: 0.95rem;
}
.result, .error {
  margin-top: 20px; padding: 14px; border-radius: 12px;
  white-space: pre-wrap;
}
.result {
  background: rgba(99,102,241,0.12);
  border: 1px solid rgba(99,102,241,0.3);
}
.error {
  background: rgba(239,68,68,0.12);
  border: 1px solid rgba(239,68,68,0.25);
  color: #fca5a5;
}
</style>
"""

HOME_PAGE = BASE_CSS + """
<div class="container" style="text-align:center;">
  <h1>🧩 Image Steganography</h1>
  <p class="sub">Choose what you’d like to do</p>
  <a class="btn" href="{{ url_for('encode_page') }}">🔐 Encode Message</a>
  <a class="btn" href="{{ url_for('decode_page') }}">🕵️‍♂️ Decode Message</a>
</div>
"""

ENCODE_PAGE = BASE_CSS + """
<div class="container">
  <h1>🔐 Encode Message</h1>
  <p class="sub">Hide a secret message inside an image (output will be PNG)</p>
  {% if error %}
    <div class="error">{{ error }}</div>
  {% endif %}
  <form method="post" enctype="multipart/form-data">
    <label>Cover Image (PNG/JPG)</label>
    <input type="file" name="image" accept=".png,.jpg,.jpeg" required>
    <label style="margin-top:12px;">Message to Hide</label>
    <textarea name="message" rows="4" required></textarea>
    <label style="margin-top:12px;">Optional Key</label>
    <input type="password" name="key" placeholder="Leave blank to skip">
    <label style="margin-top:12px;">Output Filename</label>
    <input type="text" name="filename" value="stego.png">
    <div style="text-align:center;">
      <button type="submit">Encrypt & Download</button>
    </div>
  </form>
  <div style="text-align:center;margin-top:15px;">
    <a href="{{ url_for('home') }}" class="btn" style="background:#374151;">⬅ Back Home</a>
  </div>
</div>
"""

DECODE_PAGE = BASE_CSS + """
<div class="container">
  <h1>🕵️‍♂️ Decode Message</h1>
  <p class="sub">Upload a stego image to reveal its hidden message</p>
  {% if error %}
    <div class="error">{{ error }}</div>
  {% elif message %}
    <div class="result"><strong>Extracted Message:</strong><br>{{ message }}</div>
  {% endif %}
  <form method="post" enctype="multipart/form-data">
    <label>Stego Image (PNG)</label>
    <input type="file" name="image" accept=".png,.jpg,.jpeg" required>
    <label style="margin-top:12px;">Decryption Key (if any)</label>
    <input type="password" name="key" placeholder="Leave blank if none">
    <div style="text-align:center;">
      <button type="submit">Decrypt Message</button>
    </div>
  </form>
  <div style="text-align:center;margin-top:15px;">
    <a href="{{ url_for('home') }}" class="btn" style="background:#374151;">⬅ Back Home</a>
  </div>
</div>
"""

# --------------------- ROUTES ---------------------

@app.get("/")
def home():
    return render_template_string(HOME_PAGE)

@app.get("/encode")
def encode_page():
    return render_template_string(ENCODE_PAGE)

@app.post("/encode")
def encode_post():
    try:
        if "image" not in request.files or request.files["image"].filename == "":
            return render_template_string(ENCODE_PAGE, error="Please upload an image.")
        image_bytes = request.files["image"].read()
        message = (request.form.get("message") or "").strip()
        if not message:
            return render_template_string(ENCODE_PAGE, error="Message cannot be empty.")
        key = (request.form.get("key") or "").strip() or None
        filename = (request.form.get("filename") or "stego.png").strip()
        if not filename.lower().endswith(".png"):
            filename += ".png"
        stego_buf = encode_image_bytes(image_bytes, message, key)
        return send_file(stego_buf, mimetype="image/png", as_attachment=True, download_name=filename)
    except Exception as e:
        return render_template_string(ENCODE_PAGE, error=str(e))

@app.get("/decode")
def decode_page():
    return render_template_string(DECODE_PAGE)

@app.post("/decode")
def decode_post():
    try:
        if "image" not in request.files or request.files["image"].filename == "":
            return render_template_string(DECODE_PAGE, error="Please upload an image.")
        image_bytes = request.files["image"].read()
        key = (request.form.get("key") or "").strip() or None
        msg = decode_image_bytes(image_bytes, key)
        return render_template_string(DECODE_PAGE, message=msg)
    except Exception as e:
        return render_template_string(DECODE_PAGE, error=str(e))

# --------------------- MAIN ---------------------

if __name__ == "__main__":
    app.run(debug=True)
