Three contract/fit deviations in the **current revision, changed externally during review**:

1. **Required assembly parts omitted** — [housing.py:66](/home/andrey/_PROJECTS/watches/cad/desk/housing.py:66). `PROTOTYPE=True` removes lid ribs and carrier/light-box exports; `GASKET=0.5` also moves the glass back. The resulting print set cannot implement the specified assembly. Fix: `PROTOTYPE=False`, `GASKET=0.0`, regenerate exports.

2. **Wrong mounting-hole pitch** — [housing.py:152](/home/andrey/_PROJECTS/watches/cad/desk/housing.py:152). Hole rows are **72.85 mm** apart, versus the specified **72.75 mm**. Upper holes sit 0.10 mm too high, consuming screw clearance and misaligning countersinks. Fix: upper row = `PCB_Z0 + NUT_INSET + NUT_DZ` → **Z90.75**, lower row **Z18.00**.

3. **Magnet wall below frozen value** — [housing.py:272](/home/andrey/_PROJECTS/watches/cad/desk/housing.py:272). The updated placement correctly accounts for the chamfer, but leaves **0.612 mm**, versus **0.86 mm** in the frozen notes. To retain 0.86: exclude the four corner arcs from the **0.5 mm** bottom chamfer and restore centres **(±22.46, 2.51)** / **(±22.49, 31.46)**.

No other critical issue found. Exported STEP solids are valid; rerun insertion sweeps pass for the modeled envelopes. I changed no files.