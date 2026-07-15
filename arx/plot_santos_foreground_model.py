#!/usr/bin/env python3
"""
Plot a Santos-style foreground model at 150 MHz.

Foreground parameterization follows the standard Santos et al. style model used
widely in EoR forecasting:

    C_l(Δν) = A * (1000 / l)^beta * (ν_f / ν)^(2 alpha_bar) * I_l(Δν)

with

    I_l(Δν) = exp[- log^2(1 + Δν / ν) / (2 ξ^2)]

This script uses the commonly adopted parameter set for the four dominant
foreground classes (unresolved point sources, extragalactic free-free,
Galactic synchrotron, Galactic free-free).

For the overplotted 21-cm signal, this script uses a compact fiducial toy model
for visual comparison only. It is intentionally kept sub-dominant relative to
the foregrounds and is not meant to replace a full cosmological calculation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm


@dataclass(frozen=True)
class ForegroundComponent:
    key: str
    label: str
    A_mK2: float
    beta: float
    alpha_bar: float
    xi: float
    cmap: str


NU_MHZ = 150.0
NU_REF_MHZ = 130.0
ELL_MIN = 1_000.0
ELL_MAX = 12_000.0
DELTA_NU_MIN_MHZ = 1.0e-3  # strictly positive because the user requested log x axes
DELTA_NU_MAX_MHZ = 100.0
ELL_SIGNAL_REF = 3_000.0
RNG = np.random.default_rng(7)

COMPONENTS = [
    ForegroundComponent("ps", "Point Sources", 57.0, 1.1, 2.07, 1.0, "magma"),
    ForegroundComponent("eff", "Extragal. Free-Free", 0.014, 1.0, 2.10, 35.0, "cividis"),
    ForegroundComponent("gs", "Galactic Synch.", 700.0, 2.4, 2.80, 4.0, "viridis"),
    ForegroundComponent("gff", "Galactic Free-Free", 0.088, 3.0, 2.15, 35.0, "plasma"),
]


def foreground_cl(component: ForegroundComponent, ell: np.ndarray, delta_nu_mhz: np.ndarray) -> np.ndarray:
    ell = np.asarray(ell, dtype=float)
    delta_nu_mhz = np.asarray(delta_nu_mhz, dtype=float)

    spatial = component.A_mK2 * (1_000.0 / ell) ** component.beta
    spectral = (NU_REF_MHZ / NU_MHZ) ** (2.0 * component.alpha_bar)
    decor = np.exp(-(np.log1p(delta_nu_mhz / NU_MHZ) ** 2) / (2.0 * component.xi**2))
    return spatial * spectral * decor


def signal_cl_21cm(ell: np.ndarray, delta_nu_mhz: np.ndarray) -> np.ndarray:
    """
    A compact fiducial 21-cm fluctuation model for visual comparison.

    Chosen to be several orders below the dominant foregrounds while retaining
    the fast decorrelation expected of the cosmological signal.
    """
    ell = np.asarray(ell, dtype=float)
    delta_nu_mhz = np.asarray(delta_nu_mhz, dtype=float)
    amp = 0.12  # mK^2 at l ~ 1000, illustrative only
    spatial = amp * (1_000.0 / ell) ** 1.8
    decor = np.exp(-((delta_nu_mhz / 0.5) ** 1.35))
    return spatial * decor


def powerlaw_field(shape: tuple[int, int], beta: float) -> np.ndarray:
    ny, nx = shape
    noise = RNG.normal(size=shape)
    ft = np.fft.rfft2(noise)

    ky = np.fft.fftfreq(ny)[:, None]
    kx = np.fft.rfftfreq(nx)[None, :]
    k = np.sqrt(kx**2 + ky**2)
    filt = (k**2 + (1.0 / max(nx, ny)) ** 2) ** (-beta / 4.0)
    filt[0, 0] = 0.0

    field = np.fft.irfft2(ft * filt, s=shape)
    field -= np.mean(field)
    std = np.std(field)
    if std > 0:
        field /= std
    return field


def component_sky_map(component: ForegroundComponent, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    target_sigma = np.sqrt((ELL_MIN * (ELL_MIN + 1.0) * foreground_cl(component, ELL_MIN, 0.0)) / (2.0 * np.pi))
    field = powerlaw_field(lat.shape, component.beta)

    # Modulate the morphology slightly to distinguish Galactic from extragalactic components.
    if "Galactic" in component.label:
        gal_plane = 1.0 + 1.5 * np.exp(-(lat / np.deg2rad(18.0)) ** 2)
        field = field * gal_plane
    else:
        field = field * (1.0 + 0.15 * np.cos(2.0 * lon))

    field -= np.mean(field)
    std = np.std(field)
    if std > 0:
        field /= std
    return target_sigma * field


def add_map(ax: plt.Axes, lon: np.ndarray, lat: np.ndarray, data: np.ndarray, title: str, cmap: str) -> None:
    vabs = np.percentile(np.abs(data), 99.0)
    mesh = ax.pcolormesh(
        lon,
        lat,
        data,
        shading="auto",
        cmap=cmap,
        vmin=-vabs,
        vmax=vabs,
    )
    ax.grid(True, alpha=0.3)
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.set_title(title, fontsize=10)
    cbar = plt.colorbar(mesh, ax=ax, orientation="horizontal", pad=0.05, fraction=0.05)
    cbar.set_label(r"$\delta T$ [mK]", fontsize=8)
    cbar.ax.tick_params(labelsize=7)


def main() -> None:
    ell = np.geomspace(ELL_MIN, ELL_MAX, 300)
    delta_nu = np.geomspace(DELTA_NU_MIN_MHZ, DELTA_NU_MAX_MHZ, 240)

    # Use "ij" indexing so the 2D arrays are [delta_nu, ell].
    dnu_grid, ell_grid = np.meshgrid(delta_nu, ell, indexing="ij")

    component_cls = {comp.key: foreground_cl(comp, ell_grid, dnu_grid) for comp in COMPONENTS}
    total_cl = np.sum(np.stack(list(component_cls.values()), axis=0), axis=0)
    signal_cl = signal_cl_21cm(ell_grid, dnu_grid)

    component_c0 = {comp.key: foreground_cl(comp, ell, 0.0) for comp in COMPONENTS}
    total_c0 = np.sum(np.stack(list(component_c0.values()), axis=0), axis=0)
    signal_c0 = signal_cl_21cm(ell, 0.0)

    component_decor = {
        comp.key: foreground_cl(comp, ELL_SIGNAL_REF, delta_nu) / foreground_cl(comp, ELL_SIGNAL_REF, 0.0)
        for comp in COMPONENTS
    }
    total_decor = total_cl[:, np.argmin(np.abs(ell - ELL_SIGNAL_REF))] / total_c0[np.argmin(np.abs(ell - ELL_SIGNAL_REF))]
    signal_decor = signal_cl_21cm(ELL_SIGNAL_REF, delta_nu) / signal_cl_21cm(ELL_SIGNAL_REF, 0.0)

    # Sky maps
    nlon, nlat = 256, 128
    lon_1d = np.linspace(-np.pi, np.pi, nlon)
    lat_1d = np.linspace(-0.5 * np.pi, 0.5 * np.pi, nlat)
    lon, lat = np.meshgrid(lon_1d, lat_1d)
    component_maps = {comp.key: component_sky_map(comp, lon, lat) for comp in COMPONENTS}
    total_map = np.sum(np.stack(list(component_maps.values()), axis=0), axis=0)

    fig = plt.figure(figsize=(22, 22), constrained_layout=True)
    gs = fig.add_gridspec(nrows=6, ncols=5, height_ratios=[1.25, 1.0, 1.0, 1.0, 1.0, 1.0])

    # Top row: component maps + total.
    for idx, comp in enumerate(COMPONENTS):
        ax = fig.add_subplot(gs[0, idx], projection="mollweide")
        rms = np.std(component_maps[comp.key])
        add_map(ax, lon, lat, component_maps[comp.key], f"{comp.label}\nRMS={rms:.2f} mK", comp.cmap)

    ax_total = fig.add_subplot(gs[0, 4], projection="mollweide")
    add_map(ax_total, lon, lat, total_map, f"Total\nRMS={np.std(total_map):.2f} mK", "coolwarm")

    row_labels = [comp.label for comp in COMPONENTS] + ["Total"]
    cl_mats = [component_cls[comp.key] for comp in COMPONENTS] + [total_cl]
    c0_lines = [component_c0[comp.key] for comp in COMPONENTS] + [total_c0]
    decor_lines = [component_decor[comp.key] for comp in COMPONENTS] + [total_decor]
    cmaps = [comp.cmap for comp in COMPONENTS] + ["coolwarm"]

    heat_norms = [LogNorm(vmin=np.min(mat), vmax=np.max(mat)) for mat in cl_mats]

    for i in range(5):
        # Heatmap: C_l(Δν)
        ax_hm = fig.add_subplot(gs[i + 1, 0])
        hm = ax_hm.pcolormesh(
            ell,
            delta_nu,
            cl_mats[i],
            shading="auto",
            norm=heat_norms[i],
            cmap=cmaps[i],
        )
        ax_hm.set_xscale("log")
        ax_hm.set_yscale("log")
        ax_hm.set_xlim(ELL_MIN, ELL_MAX)
        ax_hm.set_ylim(DELTA_NU_MIN_MHZ, DELTA_NU_MAX_MHZ)
        ax_hm.set_ylabel(rf"{row_labels[i]}" + "\n" + r"$\Delta\nu$ [MHz]")
        if i == 0:
            ax_hm.set_title(r"$C_\ell(\Delta\nu)$", fontsize=11)
        if i == 4:
            ax_hm.set_xlabel(r"$\ell$")
        cbar = fig.colorbar(hm, ax=ax_hm, fraction=0.046, pad=0.02)
        cbar.set_label(r"mK$^2$", fontsize=8)

        # C_l(0)
        ax_c0 = fig.add_subplot(gs[i + 1, 1:3])
        ax_c0.plot(ell, c0_lines[i], lw=2.0, color="#d62728", label=row_labels[i])
        ax_c0.plot(ell, signal_c0, lw=1.5, ls="--", color="black", label="21-cm (fiducial)")
        ax_c0.set_xscale("log")
        ax_c0.set_yscale("log")
        ax_c0.set_xlim(ELL_MIN, ELL_MAX)
        ax_c0.grid(True, which="both", alpha=0.25)
        if i == 0:
            ax_c0.set_title(r"$C_\ell(\Delta\nu=0)$ at 150 MHz", fontsize=11)
        if i == 4:
            ax_c0.set_xlabel(r"$\ell$")
        ax_c0.set_ylabel(r"mK$^2$")
        if i == 0:
            ax_c0.legend(loc="best", fontsize=8)

        # Decorrelation
        ax_dec = fig.add_subplot(gs[i + 1, 3:5])
        ax_dec.plot(delta_nu, decor_lines[i], lw=2.0, color="#1f77b4", label=row_labels[i])
        ax_dec.plot(delta_nu, signal_decor, lw=1.5, ls="--", color="black", label="21-cm (fiducial)")
        ax_dec.set_xscale("log")
        ax_dec.set_yscale("log")
        ax_dec.set_xlim(DELTA_NU_MIN_MHZ, DELTA_NU_MAX_MHZ)
        ax_dec.set_ylim(1.0e-6, 1.2)
        ax_dec.grid(True, which="both", alpha=0.25)
        if i == 0:
            ax_dec.set_title(r"Decorrelation at $\ell=3000$", fontsize=11)
        if i == 4:
            ax_dec.set_xlabel(r"$\Delta\nu$ [MHz]")
        ax_dec.set_ylabel(r"$C_\ell(\Delta\nu)/C_\ell(0)$")
        if i == 0:
            ax_dec.legend(loc="best", fontsize=8)

    fig.suptitle(
        "Santos-Style Foreground Model at 150 MHz\n"
        "Top: synthetic fluctuation maps normalized to model RMS; "
        "Bottom: C_l(Δν), C_l(0), and decorrelation\n"
        "Note: Δν starts at 10^-3 MHz because log-scaled axes cannot include zero.",
        fontsize=14,
    )

    out_path = Path(__file__).resolve().parent / "santos_foreground_model_150MHz.png"
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
