# Data that ships vs data that does not

Deliverable #8 requires raw benchmark data in the reproduction bundle:
sensor logs, tape/laser ground truth, and incumbent-app exports.

## Commit (our work)

- `data/raw/<our_capture>/` — every capture we record for the benchmark
  (photos, video, LiDAR), including the multi-room set and the repeat pair
- `data/ground_truth/` — laser/tape measurements, room IDs, notes
- later: incumbent app exports used in the head-to-head table

## Do not commit (vendor)

- Drive sample zips and the three Stray hash folders they unpack to
- Local symlinks named `single_room`, `floor_only`, `with_ceiling`
  (machine-specific paths into Downloads)
- `single_room_photos/` — stills ripped from the vendor video for local debugging,
  not a real photo-tier capture
- `downloads_sane/` — local filter dump from `~/Downloads`; not a protocol folder

Those vendor names are gitignored on purpose. Anything else under
`data/raw/` or `data/ground_truth/` is tracked. If you are about to add
`data/raw/*` to `.gitignore`, stop — that is the hour-44 failure mode.
