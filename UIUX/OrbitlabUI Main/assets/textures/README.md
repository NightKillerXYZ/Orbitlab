# Planet textures for the 3D orbit view

`view3d.js` reads one optional file per central body, relative to
`UIUX/OrbitlabUI Main/`:

- `assets/textures/earth.jpg`
- `assets/textures/moon.jpg`
- `assets/textures/mars.jpg`
- `assets/textures/mercury.jpg`
- `assets/textures/venus.jpg`
- `assets/textures/jupiter.jpg`
- `assets/textures/sun.jpg`

Rules: files must be equirectangular (2:1) JPGs; when a file is missing the
view falls back to a plain shaded sphere in the body's colour and keeps
working — a missing texture never throws.

GMAT ships usable equirectangular textures with author credits in the file
names; suggested sources (credit the authors when you copy them):

- Earth: `earth.jpg` — JPL/Caltech (Blue Marble).
- Moon: `moon.jpg` — Bjorn Jonsson / Celestia Motherlode.
- Mars: `mars.jpg` — JPL/Caltech.
- Mercury/Venus/Jupiter/Sun: matching `*.jpg` from the GMAT texture set or
  Celestia Motherlode (keep the original author credit).

Do not commit large binary textures without checking their licence first.
