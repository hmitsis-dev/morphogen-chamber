# morphogen-chamber

A live Gray-Scott reaction-diffusion simulation. Two virtual chemicals
(U, V) diffuse across a wrapped grid and react with each other according
to two numbers - feed rate and kill rate. Nothing about the resulting
pattern is designed: depending on where those two numbers land, the
system settles into spots, stripes, mazes, slow mitosis-like splitting
blobs, chaotic waves, or dies out entirely. This is the same reaction
Alan Turing used in 1952 to explain a leopard's spots and a zebra's
stripes as one chemical process with no plan for either.

No build step, no dependencies - native ES modules throughout. Serve
the directory with any static file server and open it:

```sh
python3 -m http.server 8080
```

(Opening `index.html` directly via `file://` mostly works too, but some
browsers restrict WebGL a bit more strictly there - serving it is safer,
and it's how this is actually deployed, via GitHub Pages.)

## Theory

Two species, U and V, react by:

```
U + 2V → 3V      (V is autocatalytic: it consumes U to make more of itself)
V → P            (V decays into an inert product P)
```

That single fact - V catalyzing its own production while also decaying -
is the entire mechanism. Written as PDEs:

$$\frac{\partial u}{\partial t} = D_u \nabla^2 u - uv^2 + F(1 - u)$$

$$\frac{\partial v}{\partial t} = D_v \nabla^2 v + uv^2 - (F + K)v$$

- `uv²` is the reaction itself (mass-action kinetics for `U + 2V → 3V`):
  it consumes U and produces V, at a rate proportional to `u` and to
  `v²`.
- `F(1 - u)` is the **feed**: U is continuously replenished toward a
  concentration of 1, at rate `F`. Without this term the reaction would
  simply consume all the U and stop.
- `(F + K)v` is the **removal**: V is drained away at combined rate
  `F + K`, where `K` is the parameter this file calls "kill rate."
- `D_u∇²u` and `D_v∇²v` are ordinary diffusion - each species spreading
  down its own concentration gradient.

The counterintuitive part is that diffusion, which normally *erases*
differences and smooths everything toward uniformity, is exactly what
*creates* the pattern here. A perfectly uniform mixture of U and V is
stable on its own - nothing happens. But because U diffuses faster than
V (`D_u = 1.0`, `D_v = 0.5` in this file - a 2:1 ratio), a small random
fluctuation stops smoothing away and instead grows: V briefly
concentrates, consumes nearby U faster than U can diffuse back in to
replace it, and a stable spot or stripe is born. This is a **Turing
instability** - diffusion-driven pattern formation - and it's the exact
mechanism Alan Turing proposed in his 1952 paper *"The Chemical Basis
of Morphogenesis"* for how a spatially uniform embryo ends up with
spots, stripes, or segments, with no template or blueprint anywhere in
the system telling it what shape to become.

## Structure

```
index.html          canvas + control rail markup, loads src/main.js as a module
src/style.css        all styling
src/shaders.js        GLSL ES 3.00 sources (vertex, step, render)
src/gl-utils.js        generic WebGL2 helpers - no Gray-Scott-specific knowledge,
                        reusable for any GPU ping-pong simulation
src/gray-scott.js       the GrayScott class: owns the GL context, compiled
                         programs, ping-ponging simulation state, params, presets
src/ui.js             wires the DOM (sliders, presets, pointer injection) to a
                       GrayScott instance
src/main.js           entry point: creates the simulation, wires the UI, runs
                       the render loop
```

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
  reagent at that point on every subsequent step while held. The seven
  presets are real named regions from the commonly-referenced Gray-Scott
  parameter map, not arbitrary points.

## References

1. P. Gray and S. K. Scott, *Chemical Oscillations and Instabilities:
   Non-linear Chemical Kinetics*, v. 21 of International Series of
   Monographs on Chemistry, 1994.
2. L. N. Trefethen and K. Embree, editors, article 23 on "The
   Gray-Scott equations," *The (Unfinished) PDE Coffee Table Book*,
   https://people.maths.ox.ac.uk/trefethen/pdectb.html.
3. H. Montanelli and N. Bootland, *Solving periodic semilinear stiff
   PDEs in 1D, 2D and 3D with exponential integrators*, submitted,
   2016.
