# VW Vehicle Status

Work-in-progress Home Assistant integration for Volkswagen vehicles using [`python_vw_carnet`](https://github.com/dmillerw/python_vw_carnet).

Feedback is welcome and gladly accepted.

## What It Does

Adds one Home Assistant device per vehicle on your VW account and exposes:

- status sensors like last seen, lock status, and last parked time/location
- distance sensors like mileage, estimated range, and maintenance mileage
- EV sensors like charging status, charge power, remaining charge time, and battery percent
- a per-vehicle `Preclimate` switch

## Install With HACS

1. Add this repository as a custom repository in HACS.
2. Install `VW Vehicle Status`.
3. Restart Home Assistant.
4. Add the integration from Settings > Devices & Services.
