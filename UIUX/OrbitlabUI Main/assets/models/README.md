# Optional 3D spacecraft model for the 3D orbit view

`view3d.js` reads one optional file, relative to `UIUX/OrbitlabUI Main/`:

- `assets/models/spacecraft.3ds`

Rules: when the file is missing (or fails to load) the view keeps the
simple white-sphere marker and keeps working — a missing model never
throws. When present, it is loaded with the vendored
`vendor/three/TDSLoader.js`, centred on its bounding box and scaled to a
fixed on-screen size (about 3% of the camera distance), so any reasonable
spacecraft mesh works.

GMAT ships usable `*.3ds` spacecraft models under `data/graphics/models/`
in its source tree (for example the default `DefaultSC.3ds`); they can be
copied here as `assets/models/spacecraft.3ds`. GMAT is Apache 2.0
licensed: keep GMAT's `LICENSE.txt`/`NOTICE` attribution with the copied
file and do not commit a model file unless its licence is compatible.

Do not commit large binary models without checking their licence first.
