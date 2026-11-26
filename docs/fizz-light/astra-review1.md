No critical or high issues found.

1. **Medium — [firmware/src/params_nvs.h:90](/home/aadod/_PROJECTS/watches/firmware/src/params_nvs.h:90): interrupted v35 migrations lose recovery.**  
   A complete 732-byte v35 blob under a v34 CRC (`0x44a578ad`) results when migration writes the blob but fails before updating the CRC. If v36 boots next, it expects 728 bytes and rejects the saved settings, loading defaults; the next save overwrites them. Reproduced: baseline recovers this state, v36 rejects it.  
   **Smallest fix:** recognize a complete v35 blob with `v == 35` under a known older CRC, then run only v35 → v36 and save.

2. **Medium — [firmware/src/fizz_light.h:147](/home/aadod/_PROJECTS/watches/firmware/src/fizz_light.h:147), mirrored in [sim/src/fizzLight.ts:116](/home/aadod/_PROJECTS/watches/sim/src/fizzLight.ts:116): zero-width lid rows retain tilted ray intersections.**  
   `B == 0` disables lid clearance and viewing geometry, but all five incident rays still use `invS` built with `tan(tau)`. This occurs when the liquid reaches the closed time-end glass: lid width becomes zero while the frame’s lid flag remains true. Rays incorrectly hit a tilted dark end, dimming the ring. Reproduction: `R=20, r=3, x=97, S=100, SL=0, y=z=B=0, transparency=1, upX=0.87758256, light=0, tau=-0.5, exposed=0, tone=1`. The kernel produces `K=0.206327`; the specified axial boundary gives `K=0.618980`.  
   **Smallest fix:** precompute axial surface reciprocals alongside the lid reciprocals and select them whenever the per-bubble `lid` condition is false, for both ring and key rays.