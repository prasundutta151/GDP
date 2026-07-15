#!/usr/bin/env python3
"""
Generate a simple uGMRT-like 150 MHz Measurement Set for an 8-hour track.

This script uses CASA's simulator tool to create the MS structure and uvw
coordinates, then fills the DATA column by Fourier-sampling a synthetic
5 deg x 5 deg foreground field (diffuse components + point sources).

The array layout is an analytic uGMRT-like approximation:
- 12 antennas in a compact central square
- 18 antennas on three arms reaching to ~14 km

Outputs in the current directory:
- ugmrt_dec54_8h.ms
- ugmrt_dec54_8h_model.npz
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

import numpy as np


MS_NAME = "ugmrt_dec54_8h.ms"
MODEL_CACHE = "ugmrt_dec54_8h_model.npz"
NU_MHZ = 150.0
PATCH_DEG = 5.0
PATCH_PIX = 192
RNG = np.random.default_rng(11)
ELL_MIN = 1_000.0
NU_REF_MHZ = 130.0
INTEGRATION_S = 120.0


@dataclass(frozen=True)
class ForegroundComponent:
    key: str
    A_mK2: float
    beta: float
    alpha_bar: float
    xi: float


POINT_SOURCES = ForegroundComponent("ps", 57.0, 1.1, 2.07, 1.0)
DIFFUSE_COMPONENTS = [
    ForegroundComponent("gs", 700.0, 2.4, 2.80, 4.0),
    ForegroundComponent("gff", 0.088, 3.0, 2.15, 35.0),
    ForegroundComponent("eff", 0.014, 1.0, 2.10, 35.0),
]


def foreground_cl(component: ForegroundComponent, ell: np.ndarray, delta_nu_mhz: float = 0.0) -> np.ndarray:
    spatial = component.A_mK2 * (1_000.0 / np.asarray(ell, dtype=float)) ** component.beta
    spectral = (NU_REF_MHZ / NU_MHZ) ** (2.0 * component.alpha_bar)
    decor = np.exp(-(np.log1p(delta_nu_mhz / NU_MHZ) ** 2) / (2.0 * component.xi**2))
    return spatial * spectral * decor


def gaussian_kernel(size: int, sigma_pix: float) -> np.ndarray:
    ax = np.arange(size, dtype=float) - (size - 1) / 2.0
    xx, yy = np.meshgrid(ax, ax, indexing="xy")
    ker = np.exp(-(xx**2 + yy**2) / (2.0 * sigma_pix**2))
    ker /= np.sum(ker)
    return ker


def fft_convolve2d(image: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    shape = image.shape
    fshape = (shape[0] + kernel.shape[0] - 1, shape[1] + kernel.shape[1] - 1)
    img_ft = np.fft.rfftn(image, fshape)
    ker_ft = np.fft.rfftn(kernel, fshape)
    conv = np.fft.irfftn(img_ft * ker_ft, fshape)
    sy = (kernel.shape[0] - 1) // 2
    sx = (kernel.shape[1] - 1) // 2
    return conv[sy:sy + shape[0], sx:sx + shape[1]]


def powerlaw_field(shape: tuple[int, int], beta: float) -> np.ndarray:
    ny, nx = shape
    noise = RNG.normal(size=shape)
    ft = np.fft.rfft2(noise)
    ky = np.fft.fftfreq(ny)[:, None]
    kx = np.fft.rfftfreq(nx)[None, :]
    kval = np.sqrt(kx**2 + ky**2)
    filt = (kval**2 + (1.0 / max(nx, ny)) ** 2) ** (-beta / 4.0)
    filt[0, 0] = 0.0
    field = np.fft.irfft2(ft * filt, s=shape)
    field -= np.mean(field)
    std = np.std(field)
    return field / std if std > 0 else field


def diffuse_patch(component: ForegroundComponent, shape: tuple[int, int]) -> np.ndarray:
    field = powerlaw_field(shape, component.beta)
    yy = np.linspace(-1.0, 1.0, shape[0])[:, None]
    xx = np.linspace(-1.0, 1.0, shape[1])[None, :]
    if component.key == "gs":
        mod = 1.0 + 0.35 * np.cos(2.0 * np.pi * xx) + 0.7 * np.exp(-(yy / 0.45) ** 2)
    elif component.key == "gff":
        mod = 1.0 + 0.25 * np.exp(-((xx / 0.6) ** 2 + (yy / 0.6) ** 2))
    else:
        mod = 1.0 + 0.15 * np.sin(2.0 * np.pi * xx) * np.cos(np.pi * yy)
    field *= mod
    field -= np.mean(field)
    field /= np.std(field)
    target_sigma = np.sqrt((ELL_MIN * (ELL_MIN + 1.0) * foreground_cl(component, ELL_MIN)) / (2.0 * np.pi))
    return target_sigma * field


def point_source_patch(shape: tuple[int, int]) -> np.ndarray:
    image = np.zeros(shape, dtype=float)
    nsrc = 90
    gamma = 1.8
    fluxes = (RNG.pareto(gamma, nsrc) + 1.0) * 0.15
    ys = RNG.integers(0, shape[0], size=nsrc)
    xs = RNG.integers(0, shape[1], size=nsrc)
    for y, x, f in zip(ys, xs, fluxes):
        image[y, x] += f
    smoothed = fft_convolve2d(image, gaussian_kernel(size=25, sigma_pix=2.0))
    smoothed -= np.mean(smoothed)
    smoothed /= np.std(smoothed)
    target_sigma = np.sqrt((ELL_MIN * (ELL_MIN + 1.0) * foreground_cl(POINT_SOURCES, ELL_MIN)) / (2.0 * np.pi))
    return target_sigma * smoothed


def generate_model_image() -> tuple[np.ndarray, np.ndarray, float]:
    shape = (PATCH_PIX, PATCH_PIX)
    diffuse_maps = [diffuse_patch(comp, shape) for comp in DIFFUSE_COMPONENTS]
    point_map = point_source_patch(shape)
    model_mk = np.sum(np.stack(diffuse_maps, axis=0), axis=0) + point_map
    pixel_size_rad = np.deg2rad(PATCH_DEG / PATCH_PIX)
    pixel_solid_angle = pixel_size_rad**2
    k_b = 1.380649e-23
    c = 299_792_458.0
    nu_hz = NU_MHZ * 1e6
    jy_per_sr_per_mk = 1e26 * 2.0 * k_b * 1e-3 * nu_hz**2 / c**2
    jy_per_pix_per_mk = jy_per_sr_per_mk * pixel_solid_angle
    model_jy_pix = model_mk * jy_per_pix_per_mk
    return model_mk, model_jy_pix, jy_per_pix_per_mk


def build_ugmrt_like_layout() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    core_x = np.array([-180, -60, 60, 180] * 3, dtype=float)
    core_y = np.repeat(np.array([-180, 0, 180], dtype=float), 4)

    arm_r_km = np.array([0.9, 2.0, 4.0, 7.0, 10.0, 14.0], dtype=float)
    arm_angles_deg = np.array([90.0, 210.0, 330.0], dtype=float)
    arm_x = []
    arm_y = []
    for ang in arm_angles_deg:
        theta = np.deg2rad(ang)
        arm_x.extend(1_000.0 * arm_r_km * np.sin(theta))
        arm_y.extend(1_000.0 * arm_r_km * np.cos(theta))

    x = np.concatenate([core_x, np.asarray(arm_x)])
    y = np.concatenate([core_y, np.asarray(arm_y)])
    z = np.zeros_like(x)
    return x, y, z


def bilinear_sample_complex(
    grid: np.ndarray,
    xvals: np.ndarray,
    yvals: np.ndarray,
    xq: np.ndarray,
    yq: np.ndarray,
) -> np.ndarray:
    dx = xvals[1] - xvals[0]
    dy = yvals[1] - yvals[0]
    tx = (xq - xvals[0]) / dx
    ty = (yq - yvals[0]) / dy
    ix = np.floor(tx).astype(int)
    iy = np.floor(ty).astype(int)
    good = (ix >= 0) & (ix < len(xvals) - 1) & (iy >= 0) & (iy < len(yvals) - 1)
    out = np.zeros_like(xq, dtype=np.complex128)
    if not np.any(good):
        return out

    fx = tx[good] - ix[good]
    fy = ty[good] - iy[good]
    ix0 = ix[good]
    iy0 = iy[good]
    g00 = grid[iy0, ix0]
    g10 = grid[iy0, ix0 + 1]
    g01 = grid[iy0 + 1, ix0]
    g11 = grid[iy0 + 1, ix0 + 1]
    out[good] = (
        (1.0 - fx) * (1.0 - fy) * g00
        + fx * (1.0 - fy) * g10
        + (1.0 - fx) * fy * g01
        + fx * fy * g11
    )
    return out


def sample_visibilities(model_jy_pix: np.ndarray, uvw_m: np.ndarray) -> np.ndarray:
    lam = 299_792_458.0 / (NU_MHZ * 1e6)
    u = uvw_m[0] / lam
    v = uvw_m[1] / lam
    dl = np.deg2rad(PATCH_DEG / model_jy_pix.shape[1])
    dm = np.deg2rad(PATCH_DEG / model_jy_pix.shape[0])
    ft = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(model_jy_pix)))
    u_grid = np.fft.fftshift(np.fft.fftfreq(model_jy_pix.shape[1], d=dl))
    v_grid = np.fft.fftshift(np.fft.fftfreq(model_jy_pix.shape[0], d=dm))
    return bilinear_sample_complex(ft, u_grid, v_grid, u, v)


def create_ms(ms_path: Path) -> None:
    from casatools import measures, quanta, simulator, table

    qa = quanta()
    me = measures()
    sm = simulator()
    tb = table()

    if ms_path.exists():
        shutil.rmtree(ms_path)

    x, y, z = build_ugmrt_like_layout()
    ant_names = [f"C{i+1:02d}" for i in range(12)] + [f"A{i+1:02d}" for i in range(18)]

    sm.open(str(ms_path))
    sm.setconfig(
        telescopename="GMRT",
        x=x.tolist(),
        y=y.tolist(),
        z=z.tolist(),
        dishdiameter=[45.0] * len(x),
        offset=[0.0] * len(x),
        mount=["ALT-AZ"] * len(x),
        antname=ant_names,
        padname=ant_names,
        coordsystem="local",
        referencelocation=me.observatory("GMRT"),
    )
    src_dir = me.direction("J2000", qa.quantity("12h00m00s"), qa.quantity("54deg"))
    sm.setfield(sourcename="DEC54_FIELD", sourcedirection=src_dir)
    sm.setspwindow(
        spwname="UGMRT150",
        freq=qa.quantity(f"{NU_MHZ}MHz"),
        deltafreq=qa.quantity("0.1MHz"),
        freqresolution=qa.quantity("0.1MHz"),
        nchannels=1,
        stokes="RR LL",
    )
    sm.setfeed(mode="perfect R L", pol=["R", "L"])
    sm.settimes(
        integrationtime=qa.quantity(f"{INTEGRATION_S}s"),
        usehourangle=True,
        referencetime=me.epoch("UTC", "2025/01/01/00:00:00"),
    )
    sm.setvp(dovp=False)
    sm.setoptions(ftmachine="ft")
    sm.observe(
        sourcename="DEC54_FIELD",
        spwname="UGMRT150",
        starttime=qa.quantity("-4h"),
        stoptime=qa.quantity("4h"),
    )
    sm.close()

    model_mk, model_jy_pix, jy_per_pix_per_mk = generate_model_image()

    tb.open(str(ms_path), nomodify=False)
    uvw_m = tb.getcol("UVW")
    vis = sample_visibilities(model_jy_pix, uvw_m).astype(np.complex64)
    data = tb.getcol("DATA")
    for pol_idx in range(data.shape[0]):
        data[pol_idx, 0, :] = vis
    tb.putcol("DATA", data)
    if "CORRECTED_DATA" in tb.colnames():
        tb.putcol("CORRECTED_DATA", data)
    tb.close()

    np.savez(
        ms_path.with_name(MODEL_CACHE),
        model_mk=model_mk.astype(np.float32),
        model_jy_pix=model_jy_pix.astype(np.float32),
        uvw_m=uvw_m.astype(np.float32),
        vis=vis.astype(np.complex64),
        jy_per_pix_per_mk=np.float32(jy_per_pix_per_mk),
        patch_deg=np.float32(PATCH_DEG),
        nu_mhz=np.float32(NU_MHZ),
        integration_s=np.float32(INTEGRATION_S),
    )


def main() -> None:
    out = Path(__file__).resolve().with_name(MS_NAME)
    create_ms(out)
    print(f"Wrote {out}")
    print(f"Wrote {out.with_name(MODEL_CACHE)}")


if __name__ == "__main__":
    main()
