import json, sys, subprocess, urllib.parse, urllib.request, time, os, glob

job = json.load(open(sys.argv[1]))
vertical = job["format"] == "short"
W, H = (1080, 1920) if vertical else (1920, 1080)
os.makedirs("work", exist_ok=True)
clips = []

def dur(path):
    out = subprocess.check_output(["ffprobe","-v","error","-show_entries",
        "format=duration","-of","csv=p=0",path])
    return float(out)

for i, s in enumerate(job["scenes"], 1):
    img, aud, clip = f"work/{i}.png", f"work/{i}.mp3", f"work/{i}.mp4"

    # image (retry on failure)
    url = ("https://image.pollinations.ai/prompt/"
           + urllib.parse.quote(s["image_prompt"])
           + f"?width={W}&height={H}&seed={i}&nologo=true")
    for attempt in range(5):
        try:
            urllib.request.urlretrieve(url, img); break
        except Exception:
            time.sleep(10)

    # voice
    subprocess.run(["edge-tts","--voice","en-US-GuyNeural",
        "--text", s["narration"], "--write-media", aud], check=True)

    # clip length: narration + small pad, never under 15s
    d = max(15, round(dur(aud) + 0.7, 1))
    frames = int(d * 30)
    vf = (f"scale={W*2}:{H*2},zoompan=z='min(zoom+0.0005,1.15)'"
          f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":d={frames}:s={W}x{H}:fps=30,format=yuv420p")
    subprocess.run(["ffmpeg","-y","-i",img,"-i",aud,"-vf",vf,
        "-af","apad","-t",str(d),"-c:v","libx264","-preset","medium",
        "-crf","20","-c:a","aac","-ar","44100",clip], check=True)
    clips.append(clip)

with open("work/list.txt","w") as f:
    for c in clips: f.write(f"file '{os.path.basename(c)}'\n")

name = os.path.splitext(os.path.basename(sys.argv[1]))[0]
os.makedirs("out", exist_ok=True)
subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i","work/list.txt",
    "-c","copy",f"out/{name}.mp4"], check=True)
