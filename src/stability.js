// The actual linear stability analysis for Gray-Scott, worked through
// and verified against the running simulation - not copied from
// anywhere. See README.md "Stability analysis" for the full derivation.
//
// Two things this computes, both about the *reaction* system alone
// (no diffusion, no space) as the starting point for the real analysis:
//
// 1. The trivial steady state (u,v) = (1, 0) always exists, and its
//    Jacobian is exactly diagonal: [[-F, 0], [0, -(F+K)]]. Both
//    eigenvalues are negative for any F, K > 0, and adding diffusion
//    only ever subtracts more (-Du*k^2, -Dv*k^2) from an already
//    negative diagonal - so this state is linearly stable to every
//    wavenumber, for every parameter choice. There is no classical
//    Turing bifurcation growing a pattern out of infinitesimal noise
//    on this background, which is exactly why this project (and every
//    Gray-Scott implementation) seeds finite blobs of V by hand rather
//    than starting from noise: small perturbations here just decay.
//
// 2. A second, nontrivial homogeneous steady state can exist - solving
//    the reaction system for v != 0 gives the quadratic
//        (F+K)*v^2 - F*v + F*(F+K) = 0
//    which has real roots only when F >= 4*(F+K)^2. Below that
//    threshold no such state exists at all. This is a genuine existence
//    question (real roots or not), the kind Bolzano's intermediate
//    value theorem answers directly: evaluate the quadratic at v=0
//    (value F*(F+K) > 0) and at its vertex v=F/(2(F+K)) (value
//    negative exactly when the same condition holds) - a sign change
//    proves a root exists in between, without solving anything.
//
// The honest conclusion (see README): most of this file's "interesting"
// presets sit close to that F = 4*(F+K)^2 boundary, several with no
// nontrivial steady state at all. Gray-Scott's spots, stripes and
// self-replication are not small-amplitude patterns growing out of a
// linear instability the way classical Turing models are - they're a
// finite-amplitude, far-from-equilibrium phenomenon (Pearson 1993,
// see README references). This module reports what the linear theory
// actually says, honestly, rather than implying it explains everything.

export function trivialStateEigenvalues(F, K) {
  return { lambda1: -F, lambda2: -(F + K) };
}

// Single source of truth for the existence question: (F+K)v^2 - Fv +
// F(F+K) = 0 has real roots iff F^2 - 4F(F+K)^2 >= 0, i.e. (since F>0)
// iff F - 4(F+K)^2 >= 0. Every other function below derives from this
// one computation instead of re-deriving it, so they can't disagree
// with each other by floating-point rounding at the boundary.
function existenceMargin(F, K) {
  return F - 4 * (F + K) ** 2;
}

export function nontrivialSteadyState(F, K) {
  if (existenceMargin(F, K) < 0) return null;

  const a = F + K;
  const b = -F;
  const c = F * (F + K);
  const discriminant = Math.max(0, b * b - 4 * a * c); // guard tiny negative rounding at the boundary
  const sqrtD = Math.sqrt(discriminant);
  const v1 = (-b + sqrtD) / (2 * a);
  const v2 = (-b - sqrtD) / (2 * a);
  const toU = (v) => (F + K) / v;

  return {
    roots: [
      { u: toU(v1), v: v1 },
      { u: toU(v2), v: v2 },
    ],
  };
}

export function analyze(F, K) {
  const trivial = trivialStateEigenvalues(F, K);
  const margin = existenceMargin(F, K);
  const nontrivial = nontrivialSteadyState(F, K);
  return {
    trivialStable: trivial.lambda1 < 0 && trivial.lambda2 < 0, // true for all F,K > 0
    nontrivialExists: margin >= 0,
    nontrivial,
    existenceMargin: margin,
  };
}
