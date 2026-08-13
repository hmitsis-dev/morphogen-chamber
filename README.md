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

## Stability analysis

`src/stability.js` derives, from `F` and `K` alone, what linear theory
actually predicts about a uniform background - worked through and
checked against the running simulation, not asserted.

**The trivial state.** `(u, v) = (1, 0)` - pure U, no V anywhere - is
always a steady state of the reaction terms, for any `F, K`. Its
Jacobian, evaluated directly from `f = F(1-u) - uv^2` and
`g = uv^2 - (F+K)v`, comes out exactly diagonal:

$$J\Big|_{(1,0)} = \begin{pmatrix} -F & 0 \\ 0 & -(F+K) \end{pmatrix}$$

Both eigenvalues are negative for any `F, K > 0` (verified numerically
against a finite-difference Jacobian in the commit history, not just by
hand). Adding diffusion perturbs a Fourier mode `e^{ikx+\sigma t}` by
subtracting `D_u k^2` and `D_v k^2` from an already-negative diagonal -
so `σ(k) < 0` for *every* wavenumber `k`, for every parameter choice.
**There is no classical Turing bifurcation growing a pattern out of
infinitesimal noise on this background.** That's not a simplification -
it's why this project, like every other Gray-Scott implementation,
seeds finite blobs of V by hand (`gray-scott.js`'s `makeSeed`) instead
of starting from random noise: small perturbations here just decay.

**The nontrivial state.** Solving the reaction system for `v ≠ 0` gives

$$(F+K)v^2 - Fv + F(F+K) = 0$$

which has real solutions only when `F ≥ 4(F+K)²` - an existence
question with a sign change at its boundary, the kind Bolzano's
intermediate value theorem answers directly (evaluate the quadratic at
`v=0`, where it's `F(F+K) > 0`, and at its vertex, where it's negative
exactly when this same condition holds - a sign change proves a root
sits between them). Checked against every preset in this file:

| Preset | F | K | Nontrivial state exists? |
| :--- | ---: | ---: | :--- |
| Spots | 0.035 | 0.065 | no |
| Coral | 0.058 | 0.065 | no |
| Mitosis | 0.028 | 0.062 | no |
| Worms | 0.078 | 0.061 | **yes** |
| Waves | 0.014 | 0.045 | **yes** |
| Solitons | 0.030 | 0.057 | no (barely) |
| Rolls | 0.040 | 0.060 | no (exactly at the boundary) |

**The honest conclusion**: most of these presets sit close to that
existence boundary, and several of the most visually striking ones
(Spots, Mitosis) have no nontrivial homogeneous state at all. Gray-
Scott's spots, stripes, and self-replicating blobs are not small-
amplitude patterns growing out of a linear instability the way
classical Turing models are commonly taught - they're a finite-
amplitude, far-from-equilibrium phenomenon (Pearson 1993, see
references). This module reports exactly what the linear theory says,
honestly, rather than implying it explains everything the simulation
does.

## Structure

```
index.html          canvas + control rail markup, loads src/main.js as a module
src/style.css        all styling
src/shaders.js        GLSL ES 3.00 sources (vertex, step, render)
src/gl-utils.js        generic WebGL2 helpers - no Gray-Scott-specific knowledge,
                        reusable for any GPU ping-pong simulation
src/gray-scott.js       the GrayScott class: owns the GL context, compiled
                         programs, ping-ponging simulation state, params, presets
src/stability.js        the linear stability analysis - pure math, no GL,
                         no DOM - see "Stability analysis" below
src/ui.js             wires the DOM (sliders, presets, pointer injection, the
                       live stability readout) to a GrayScott instance
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
4. J. E. Pearson, "Complex Patterns in a Simple System," *Science*,
   vol. 261, 1993 - the paper that popularized Gray-Scott's pattern
   zoo and the `F`/`k` parameter map this project's presets (other than
   Rolls) are drawn from.
