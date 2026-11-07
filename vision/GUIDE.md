# Bottle detection: beginner guide

This explains how the vision code works and how to run it with your iPhone as the camera.
Read it top to bottom once; after that, use the **Cheat sheet** at the end.

---

## 1. What the vision part does

It answers one question: **"what is on the platform right now?"** There are three possible answers:

| Answer             | Meaning                                    |
|--------------------|--------------------------------------------|
| `Result.NO_OBJECT` | the platform is empty                      |
| `Result.BOTTLE`    | there is a bottle                          |
| `Result.NO_BOTTLE` | there is something, but it is not a bottle |

The vision part **does not talk to the Arduino and does not decide when to sort**.
That's the job of the control logic (other code on the Mac). The control logic *asks*
vision when it needs an answer. This is called a **pull** design (see section 3).

## 2. How it decides (the idea)

The code asks two separate questions. All of it lives in
[src/tryand_vision/detector.py](src/tryand_vision/detector.py).

### Question 1: "Is there anything there?" → `PresenceDetector`

When the program starts, it takes a picture of the **empty** platform (the *background*).
After that, every new frame is compared to it pixel by pixel:

1. Convert both images to grayscale (we only care about brightness).
2. Blur them (so camera noise does not count as a change).
3. Subtract them (`cv2.absdiff`). Pixels that barely changed become ~0.
4. *Threshold*: every pixel that changed by more than 30 (of 255) becomes white, the rest black.
5. If more than 1 % of the image is white → **an object is present**.

Run with `--show-mask` to see this black/white image live. It's the best way to understand it.

**Pros:** detects *any* object, including crumpled paper that no AI model knows.
**Cons:** the camera must not move, and big lighting changes (sun, someone's shadow)
look like an object. Press `b` to take a new background picture.

### Question 2: "Is it a bottle?" → `BottleDetector`

We use **YOLO**, a neural network that someone else has already trained on a big dataset
called COCO. COCO has 80 classes, and `bottle` is one of them, so it works without training
anything ourselves. YOLO returns boxes like "bottle, 87 % sure, at these pixels".

We use the smallest version (`yolo11n.pt`, "n" = nano) because it's fast on a laptop.
It downloads automatically (~6 MB) on the first run.

### Combining the answers → `decide()`

```
YOLO sees a bottle?                → BOTTLE
otherwise, background changed,
  or YOLO sees some other object?  → NO_BOTTLE
otherwise                          → NO_OBJECT
```

### Smoothing → `Classifier`

A single frame can be wrong (motion blur, a hand passing by). So we keep the last 5 answers
and return the **most common** one (a "majority vote"). The output is more stable, at the
cost of reacting ~5 frames later.

## 3. How the control logic uses it (the pull interface)

The interface is in [src/tryand_vision/vision.py](src/tryand_vision/vision.py).
This is all the control logic needs:

```python
from tryand_vision.vision import Vision, Result

with Vision(camera=1) as vision:          # starts the camera + YOLO in the background
    vision.wait_until_ready()              # camera warm, empty background captured

    while True:
        # ... control logic: wait until an object has landed on the platform ...
        result = vision.wait_for_stable()  # waits until the answer stops changing
        if result == Result.BOTTLE:
            ...                            # e.g. tell the Arduino: flap left
        elif result == Result.NO_BOTTLE:
            ...                            # flap right
        elif result is None:
            ...                            # scene never calmed down (e.g. a hand in view): retry
```

The four methods:

| Method                       | What it does                                                         |
|------------------------------|----------------------------------------------------------------------|
| `wait_until_ready()`         | blocks until the camera has warmed up and the background is captured |
| `classify()`                 | returns the latest answer **instantly**                              |
| `wait_for_stable(frames=8, timeout=3)` | waits until 8 new frames in a row agree, then returns the answer, or `None` after 3 s |
| `recapture_background()`     | takes a new "empty" picture (only call it when the platform is empty!) |

**Why does it run in the background?** Opening the camera and loading YOLO takes seconds,
and the vote needs recent frames. So a **thread** (a second line of work inside the same
program) reads the camera all the time and keeps the newest answer ready. Asking is then instant.

**Why `wait_for_stable` and not `classify`?** When an object has just landed, it may still be
rolling, or a hand may be in view. `wait_for_stable` only counts frames captured *after* you
call it, so you never get an old "empty" answer from before the object arrived.

**If the camera fails**, the next call to any of these raises an error, so the control logic
notices instead of sorting blindly.

## 4. One-time setup

Open the **Terminal** app and run these one at a time.

**a) Go to the project's vision folder**

```bash
cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/tryand/vision
```

**b) Get the right Python.** Your default `python3` (Miniforge) is version 3.14 and built for
*Intel* Macs, so it runs translated (Rosetta) on your M-series chip. That's slower, and PyTorch
(which YOLO needs) doesn't support it. So we make a native Apple Silicon Python 3.12 with conda.
`CONDA_SUBDIR=osx-arm64` means "give me the Apple Silicon version". You only do this once:

```bash
CONDA_SUBDIR=osx-arm64 conda create -y -n py312-arm python=3.12
```

**c) Create a virtual environment** from that Python. That's a private folder holding this
project's libraries, so they don't clash with other projects. Once:

```bash
~/miniforge3/envs/py312-arm/bin/python -m venv ~/.venvs/tryand-vision
```

> ⚠️ **Don't put the virtual environment inside the project folder.** The project is in iCloud
> Drive. iCloud marks files in it as *hidden*, Python then ignores them, and you get
> `ModuleNotFoundError: No module named 'tryand_vision'`. iCloud would also try to sync 1 GB of
> libraries. That's why it lives in `~/.venvs/` (`~` = your home folder).

**d) Activate it.** Do this **every time you open a new Terminal window**. Your prompt will
start with `(tryand-vision)` when it's active.

```bash
source ~/.venvs/tryand-vision/bin/activate
```

**e) Install the libraries** (OpenCV, YOLO/PyTorch, …). This is large and takes a few minutes.
`-e` means "editable": your code changes take effect without reinstalling.

```bash
pip install -e ".[dev]"
```

## 5. Connect the iPhone as a camera

macOS has **Continuity Camera** built in: your iPhone shows up as a normal webcam.

Requirements: the iPhone and Mac use the same Apple ID, with Wi-Fi and Bluetooth turned on.
A USB cable is more reliable. Put the iPhone in landscape on a stand, screen locked or facing away.

**Allow camera access for Terminal:** the first time, macOS will ask. If you clicked "Don't allow",
go to *System Settings → Privacy & Security → Camera* and turn on **Terminal**
(or VS Code, if that's where you run it).

**Find the iPhone's camera number:**

```bash
python -m tryand_vision --list-cameras
```

Example output:

```
camera 0: 1920x1080  preview saved to .../vision/data/camera_0.jpg
camera 1: 1920x1080  preview saved to .../vision/data/camera_1.jpg
```

Open the saved `.jpg` files to see which one is the iPhone. It's usually `1`, but it can change
when you plug devices in or out, so re-check if the wrong camera opens.

## 6. The debug viewer

To set up the camera and tune settings, there's a viewer that shows what vision sees and answers.
It doesn't control anything, it just watches.

```bash
python -m tryand_vision --camera 1 --show-mask
```

- `--camera 1`: the iPhone (use your number from section 5).
- `--show-mask`: opens a second window with the background-difference image.

**Keep the platform empty for the first 2 seconds**, because that's when the background picture is taken.

Keys (click the video window first so it gets your key presses):

| Key | Action                                                       |
|-----|--------------------------------------------------------------|
| `q` | quit                                                         |
| `b` | take a new background picture (empty the platform first!)    |
| `s` | save the current frame to `vision/data/` (to collect examples) |

## 7. Tuning: when it gets things wrong

The same settings exist in code: `Vision(camera=1, confidence=0.4, min_area=0.01)`.

| Problem                                    | Try                                                  |
|--------------------------------------------|------------------------------------------------------|
| Says `NO_BOTTLE` on an empty platform      | press `b`; raise `--min-area 0.03`; avoid moving shadows |
| Misses small trash (says `NO_OBJECT`)      | lower `--min-area 0.005`                             |
| Misses bottles                             | lower `--confidence 0.25`; better light; a plain background |
| Calls other things bottles                 | raise `--confidence 0.6`                             |
| Too slow                                   | that's YOLO; it's already the smallest model        |

**Tips for reliable results:** fixed camera position, even lighting (no direct sun),
a plain, contrasting background under the object.

## 8. Run the tests

Tests are small programs that check your code still does what you expect.
They use fake images, a fake camera and a fake YOLO, so they don't need hardware.
`tests/test_vision.py` is also a good example of how to use `Vision`.

```bash
pytest
```

Change something in `detector.py`, run `pytest` again, and see whether something breaks.
That's how you get the courage to change code.

## 9. Ideas for later (good learning exercises)

1. **Region of interest:** only look at the part of the image where objects land.
   Hint: crop the frame with `frame[y1:y2, x1:x2]` before classifying.
2. **Train your own model:** if YOLO's generic "bottle" isn't good enough for crushed or
   labelless bottles, collect ~200 photos with `s`, label them (e.g. with Roboflow), and
   fine-tune YOLO. Ultralytics makes this one command.
3. **Confidence in the answer:** return how sure YOLO was together with the answer, so the
   control logic can treat unsure cases differently.

## 10. Git basics for this branch

Your work lives on the branch `vision-bottle-detection`, so `main` stays untouched.

```bash
git status
```

```bash
git add -A && git commit -m "Describe what you changed"
```

```bash
git push -u origin vision-bottle-detection
```

Then open a Pull Request on GitHub so your teammates can review and merge it.

---

## Cheat sheet

```bash
cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/tryand/vision
```

```bash
source ~/.venvs/tryand-vision/bin/activate
```

```bash
python -m tryand_vision --camera 1 --show-mask
```
