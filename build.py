import json, sys, subprocess, urllib.parse, urllib.request, time, os, shutil

job = json.load(open(sys.argv[1]))
vertical = job["format"] == "short"
W, H = (1080, 1920) if vertical else (1920, 1080)
os.makedirs("work", exist_ok=True)
clips = []
last_good = None

def dur(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "csv=p=0", path])
    return float(out)

def is_image(path):
    try:
        if os.path.getsize(path) < 10000:
            return False
        with open(path, "rb") as f:
            head = f.read(8)
        return head.startswith(b"\x89PNG") or head.startswith(b"\xff\xd8")
    except Exception:
        return False

def fetch_image(prompt, path, base_seed):
    for attempt in range(8):
        seed = base_seed * 100 + attempt
        url = ("https://image.pollinations.ai/prompt/"
               + urllib.parse.quote(prompt)
               + f"?width={W}&height={H}&seed={seed}&nologo=true")
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
                f.write(r.read())
            if is_image(path):
                return True
            print(f"  attempt {attempt+1}: not a valid image")
        except Exception as e:
            print(f"  attempt {attempt+1}: {e}")
        time.sleep(10 + attempt * 10)
    return False

for i, s in enumerate(job["scenes"], 1):
    print(f"--- Scene {i}/{len(job['scenes'])}")
    img, aud, clip = f"work/{i}.png", f"work/{i}.mp3", f"work/{i}.mp4"

    if fetch_image(s["image_prompt"], img, i):
        last_good = img
    elif last_good:
        print(f"  Scene {i}: image failed, reusing previous image")
        shutil.copy(last_good, img)
    else:
        raise SystemExit(f"Scene {i}: image failed and no earlier image to reuse")

    subprocess.run(["edge-tts", "--voice", "en-US-GuyNeural",
        "--text", s["narration"], "--write-media", aud], check=True)

    d = max(15, round(dur(aud) + 0.7, 1))
    frames = int(d * 30)
    vf = (f"scale={W*2}:{H*2},zoompan=z='min(zoom+0.0005,1.15)'"
          f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":d={frames}:s={W}x{H}:fps=30,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-i", img, "-i", aud, "-vf", vf,
        "-af", "apad", "-t", str(d), "-c:v", "libx264", "-preset", "medium",
        "-crf", "20", "-c:a", "aac", "-ar", "44100", clip], check=True)
    clips.append(clip)
    time.sleep(5)

with open("work/list.txt", "w") as f:
    for c in clips:
        f.write(f"file '{os.path.basename(c)}'\n")

name = os.path.splitext(os.path.basename(sys.argv[1]))[0]
os.makedirs("out", exist_ok=True)
subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", "work/list.txt", "-c", "copy", f"out/{name}.mp4"], check=True)
print("Done:", name)
