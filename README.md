# morphogen-chamber

A live Gray-Scott reaction-diffusion simulation. Two virtual chemicals
(U, V) diffuse across a wrapped grid and react with each other according
to two numbers - feed rate and kill rate. Nothing about the resulting
pattern is designed: depending on where those two numbers land, the
system settles into spots, stripes, mazes, slow mitosis-like splitting
blobs, chaotic waves, or dies out entirely. This is the same reaction
Alan Turing used in 1952 to explain a leopard's spots and a zebra's
stripes as one chemical process with no plan for either.

Single self-contained HTML file, no build step, no dependencies - open
`index.html` in any browser with WebGL2 and floating-point render
targets (every evergreen desktop/mobile browser as of the last several
years).

## How it works

- **Simulation**: a 256&times;256 grid, stepped forward entirely on the
  GPU via WebGL2 fragment shaders - a nine-point discrete Laplacian for
  diffusion, then the Gray-Scott reaction term, written each step to a
  floating-point (RGBA16F) texture. Two textures ping-pong (read one,
  write the other, swap) sixteen times per rendered frame.
- **Rendering**: a second shader maps the V-channel concentration
  through a four-stop gradient (void &rarr; indigo &rarr; teal &rarr;
  warm gold) and draws it to the visible canvas.
- **Interaction**: dragging the Feed/Kill sliders changes the reaction
  live, mid-simulation. Clicking or touching the chamber injects extra
  reagent at that point on every subsequent step while held. The six
  presets are real named regions from the commonly-referenced Gray-Scott
  parameter map (Spots, Coral, Mitosis, Worms, Waves, Solitons), not
  arbitrary points.
