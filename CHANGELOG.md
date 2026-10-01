## v0.4.0 (2026-10-01)

### Feat

- **webapp**: a board composing the photos, with details in a side panel
- **webapp**: highlight on hover with masks hidden, garments grouped by kind
- **webapp**: interactive React front end
- **webapp**: FastAPI backend with a JSON API, URL uploads, garment colors and cutouts

### Perf

- **webapp**: multi-stage image without uv or pip, run as non-root

## v0.3.0 (2026-09-30)

### Feat

- **release**: multi-arch images named fashion-serving-{inference,webapp}

## v0.2.0 (2026-09-30)

### Feat

- **model**: serve the torchvision Mask R-CNN (fashion-seg-train v0.8.0, model v20)

### Fix

- **model**: import model v20 through fashion-seg-train v0.8.1
- **dvc**: service-account logins to Google Drive
- **model**: deploy fashion-seg-train@dd4b279 (model v14)

### Refactor

- **webapp**: the composition root in its own module
- **webapp**: use cases behind ports, routes and wiring apart
- **webapp**: build requests with fashion_seg_contract.request

## v0.1.1 (2026-09-27)

### Refactor

- **webapp**: use the fashion-seg-contract package

## v0.1.0 (2026-09-27)

### Feat

- serving stack for the fashion segmentation model
