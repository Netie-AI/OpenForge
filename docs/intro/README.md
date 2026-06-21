# OpenForge intro animation

A self-contained, dependency-free cinematic intro for OpenForge. It tells the
"prompt → silicon" story in four scenes:

1. **Prompt** — a chat bar types `Hey Forge, create a low-power analog MAC`.
2. **Pixelated transistor city** — a blurred, heavily pixelated skyline of
   transistor "buildings" resolves (de-pixelates) into a clean view.
3. **Virtuoso-style layout** — a Cadence-Virtuoso-like analog layout with metal
   layers, a fine grid, and gold orthogonal routing wires.
4. **Tape-out** — the layout is encapsulated into a chip package, a `TAPE-OUT`
   stamp lands, and the `OpenForge` wordmark + repo URL appear.

The animation loops (~16.5 s per cycle).

## View it

It is one HTML file with no build step or dependencies — just open it:

```bash
# directly
xdg-open docs/intro/openforge_intro.html      # or: open ... on macOS

# or via a local static server
python3 -m http.server 8090
# then browse to http://127.0.0.1:8090/docs/intro/openforge_intro.html
```

Click **Replay** (bottom of the page) to restart from scene 1.

## Export to a video file

The canvas is 1280×720. To turn it into an `.mp4`/`.gif` for a README or social
post, screen-record one full loop (e.g. with OBS, QuickTime, or a browser
capture extension) and trim to ~16 s starting from the typing prompt.
