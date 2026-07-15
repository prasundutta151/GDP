#!/usr/bin/env python3
"""
Form dirty and simple CLEAN images from the synthetic uGMRT-like MS and plot:
1. Original foreground image (single-color version of the combined foreground map)
2. Dirty image
3. Simple CLEAN image
4. Angular power spectra C_l for the three images
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from simulate_ugmrt_decl54_ms import (
    MODEL_CACHE,
    MS_NAME,
    PATCH_DEG,
    fft_convolve2d,
    gaussian_kernel,
    generate_model_image,
)


PNG_NAME = "ugmrt_dirty_clean_cl.png"


def load_ms_or_cache(ms_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    cache_path = ms_path.with_name(MODEL_CACHE)
    if cache_path.exists():
        dat = np.load(cache_path)
        model_mk = dat["model_mk"]
        uvw_m = dat["uvw_m"]
        vis = dat["vis"]
        jy_per_pix_per_mk = float(dat["jy_per_pix_per_mk"])
        return model_mk, uvw_m, vis, jy_per_pix_per_mk

    from casatools import table

    tb = table()
    tb.open(str(ms_path))
    uvw_m = tb.getcol("UVW")
    data = tb.getcol("DATA")
    tb.close()
    model_mk, _, jy_per_pix_per_mk = generate_model_image()
    vis = data[0, 0, :]
    return model_mk, uvw_m, vis, jy_per_pix_per_mk


def grid_visibilities(
    vis: np.ndarray,
    uvw_m: np.ndarray,
    shape: tuple[int, int],
    patch_deg: float,
    nu_mhz: float,
) -> tuple[np.ndarray, np.ndarray]:
    ny, nx = shape
    lam = 299_792_458.0 / (nu_mhz * 1e6)
    u = uvw_m[0] / lam
    v = uvw_m[1] / lam
    dl = np.deg2rad(patch_deg / nx)
    dv = np.deg2rad(patch_deg / ny)
    u_grid = np.fft.fftshift(np.fft.fftfreq(nx, d=dl))
    v_grid = np.fft.fftshift(np.fft.fftfreq(ny, d=dv))
    du = u_grid[1] - u_grid[0]
    dv_step = v_grid[1] - v_grid[0]

    uv_sum = np.zeros((ny, nx), dtype=np.complex128)
    uv_wgt = np.zeros((ny, nx), dtype=np.float64)

    def add_samples(usamp: np.ndarray, vsamp: np.ndarray, vs: np.ndarray) -> None:
        ix = np.rint((usamp - u_grid[0]) / du).astype(int)
        iy = np.rint((vsamp - v_grid[0]) / dv_step).astype(int)
        good = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
        ix = ix[good]
        iy = iy[good]
        vals = vs[good]
        np.add.at(uv_sum, (iy, ix), vals)
        np.add.at(uv_wgt, (iy, ix), 1.0)

    add_samples(u, v, vis)
    add_samples(-u, -v, np.conjugate(vis))

    uv_grid = np.zeros_like(uv_sum)
    good = uv_wgt > 0
    uv_grid[good] = uv_sum[good] / uv_wgt[good]
    sampling = (uv_wgt > 0).astype(float)
    return uv_grid, sampling


def make_dirty_image(uv_grid: np.ndarray, sampling: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    dirty = np.real(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(uv_grid))))
    psf = np.real(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(sampling))))
    psf /= np.max(np.abs(psf))
    return dirty, psf


def subtract_shifted(image: np.ndarray, kernel: np.ndarray, y0: int, x0: int, amp: float) -> None:
    ky, kx = kernel.shape
    cy = ky // 2
    cx = kx // 2
    y1 = max(0, y0 - cy)
    x1 = max(0, x0 - cx)
    y2 = min(image.shape[0], y0 - cy + ky)
    x2 = min(image.shape[1], x0 - cx + kx)
    py1 = y1 - (y0 - cy)
    px1 = x1 - (x0 - cx)
    py2 = py1 + (y2 - y1)
    px2 = px1 + (x2 - x1)
    image[y1:y2, x1:x2] -= amp * kernel[py1:py2, px1:px2]


def hogbom_clean(dirty: np.ndarray, psf: np.ndarray, niter: int = 250, gain: float = 0.1) -> np.ndarray:
    residual = dirty.copy()
    comps = np.zeros_like(dirty)
    thresh = 0.01 * np.max(np.abs(dirty))
    for _ in range(niter):
        idx = np.unravel_index(np.argmax(np.abs(residual)), residual.shape)
        peak = residual[idx]
        if np.abs(peak) < thresh:
            break
        amp = gain * peak
        comps[idx] += amp
        subtract_shifted(residual, psf, idx[0], idx[1], amp)
    clean_beam = gaussian_kernel(size=21, sigma_pix=1.6)
    restored = fft_convolve2d(comps, clean_beam) + residual
    return restored


def radial_cl(image_mk: np.ndarray, patch_deg: float, ell_min: float = 1_000.0, ell_max: float = 12_000.0) -> tuple[np.ndarray, np.ndarray]:
    ny, nx = image_mk.shape
    dl = np.deg2rad(patch_deg / nx)
    dm = np.deg2rad(patch_deg / ny)
    omega = (nx * dl) * (ny * dm)
    centered = image_mk - np.mean(image_mk)
    ft = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(centered))) * dl * dm
    power = (np.abs(ft) ** 2) / omega
    u = np.fft.fftshift(np.fft.fftfreq(nx, d=dl))
    v = np.fft.fftshift(np.fft.fftfreq(ny, d=dm))
    uu, vv = np.meshgrid(u, v, indexing="xy")
    ell = 2.0 * np.pi * np.sqrt(uu**2 + vv**2)
    bins = np.geomspace(ell_min, ell_max, 28)
    centers = np.sqrt(bins[:-1] * bins[1:])
    cl = np.full_like(centers, np.nan)
    for i in range(len(centers)):
        mask = (ell >= bins[i]) & (ell < bins[i + 1])
        if np.any(mask):
            cl[i] = np.mean(power[mask])
    good = np.isfinite(cl)
    return centers[good], cl[good]


def extent_deg() -> list[float]:
    half = PATCH_DEG / 2.0
    return [-half, half, -half, half]


def main() -> None:
    ms_path = Path(__file__).resolve().with_name(MS_NAME)
    model_mk, uvw_m, vis, jy_per_pix_per_mk = load_ms_or_cache(ms_path)
    uv_grid, sampling = grid_visibilities(vis, uvw_m, model_mk.shape, PATCH_DEG, 150.0)
    dirty_jy = make_dirty_image(uv_grid, sampling)[0]
    psf = make_dirty_image(uv_grid, sampling)[1]
    clean_jy = hogbom_clean(dirty_jy, psf)

    dirty_mk = dirty_jy / jy_per_pix_per_mk
    clean_mk = clean_jy / jy_per_pix_per_mk

    ell_o, cl_o = radial_cl(model_mk, PATCH_DEG)
    ell_d, cl_d = radial_cl(dirty_mk, PATCH_DEG)
    ell_c, cl_c = radial_cl(clean_mk, PATCH_DEG)

    fig, axes = plt.subplots(2, 2, figsize=(12, 10), constrained_layout=True)

    vlim = np.percentile(np.abs(model_mk), 99.5)
    img_items = [
        (axes[0, 0], model_mk, "Original Foreground Model"),
        (axes[0, 1], dirty_mk, "Dirty Image"),
        (axes[1, 0], clean_mk, "Clean Image"),
    ]
    for ax, img, title in img_items:
        im = ax.imshow(
            img,
            origin="lower",
            extent=extent_deg(),
            cmap="cividis",
            vmin=-vlim,
            vmax=vlim,
            interpolation="nearest",
        )
        ax.set_title(title)
        ax.set_xlabel("deg")
        ax.set_ylabel("deg")
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
        cbar.set_label(r"$\delta T$ [mK]")

    ax = axes[1, 1]
    ax.plot(ell_o, cl_o, lw=3, color="#222222", label="Original")
    ax.plot(ell_d, cl_d, lw=3, color="#1f77b4", label="Dirty")
    ax.plot(ell_c, cl_c, lw=3, color="#d62728", label="Clean")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(1_000.0, 12_000.0)
    ax.grid(True, which="both", alpha=0.25)
    ax.set_xlabel(r"$\ell$")
    ax.set_ylabel(r"$C_\ell(\Delta\nu=0)$ [mK$^2$ sr]")
    ax.set_title("Angular Power Spectrum")
    ax.legend()

    out = Path(__file__).resolve().with_name(PNG_NAME)
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
