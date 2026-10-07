# Datasets

## In use: Ultralytics Construction-PPE

| Field | Value |
|---|---|
| Name | Construction-PPE (v1.0.0, January 2025) |
| Authors | Mrunmayee Dalvi, Niyati Singh, Sahil Bhingarde, Ketaki Chalke (published by Ultralytics) |
| Docs page | https://docs.ultralytics.com/datasets/detect/construction-ppe/ |
| Download | https://github.com/ultralytics/assets/releases/download/v0.0.0/construction-ppe.zip (178.4 MB) |
| SHA-256 of the zip we used | `bef8dcb599aa4e9d9f5e602cb6fa7143d3c84d7f6a0ff40463d7f2a4c2632ccc` |
| Licence | **AGPL-3.0** (a `LICENSE` file with the full AGPL-3.0 text ships inside the zip). The docs page describes it as supporting "open-source research and commercial applications with proper attribution". |
| Splits (counted after extraction) | train 1,132 images (1,142 label files: 10 have no matching image and are ignored by Ultralytics), val 143, test 141 |
| Classes (11) | 0 helmet, 1 gloves, 2 vest, 3 boots, 4 goggles, 5 none, 6 Person, 7 no_helmet, 8 no_goggle, 9 no_gloves, 10 no_boots |
| Checked | 2026-10-06 |

**Why this one:** it has helmet **and** vest, plus explicit *missing-PPE* classes (`no_helmet`, ...), a ready test split, and a licence that allows use in a public competition demo with attribution. It has **no harness class** (that gap is for Sprint 1).

**What AGPL-3.0 means for us (plain words, not legal advice):** we may use the data and show results publicly; credit the dataset (citation below). If we later *distribute* the software, or let other people use a modified version of it over a network, we must offer them the corresponding source under AGPL-3.0. Ultralytics (the training/inference library) is AGPL-3.0 too, so this condition applies to the code anyway; Ultralytics sells an Enterprise licence for closed-source products. Whether trained weights count as a covered work is not settled here ✍️. Also confirm with the organisers whether the hackathon has any IP or licence rules for submitted prototypes ✍️.

**The photos themselves may carry other rights.** The AGPL-3.0 label comes from Ultralytics, but the images were collected from the web. Some test images show third-party marks, for example a "creative commons global summit 2011" overlay (`image1120`) and a "flickr.com/photos/..." watermark (`image1235`). Many show identifiable people. So **do not reuse dataset images in the PDF or slides**; show results on our own footage or the Pexels clips instead.

Citation (from the docs page):

```
@dataset{Dalvi_Construction_PPE_Dataset_2025,
  author = {Mrunmayee Dalvi and Niyati Singh and Sahil Bhingarde and Ketaki Chalke},
  title = {Construction-PPE: Personal Protective Equipment Detection Dataset},
  month = {January}, year = {2025}, version = {1.0.0}, license = {AGPL-3.0},
  url = {https://docs.ultralytics.com/datasets/detect/construction-ppe},
  publisher = {Ultralytics}
}
```

## Considered, not used (Sprint 0)

| Dataset | Why not now |
|---|---|
| SH17 (https://github.com/ahmadmughees/SH17dataset), 8,099 images, 17 classes incl. helmet + safety-vest | Licence **CC BY-NC-SA 4.0** (non-commercial). Risky for a competition with cash prizes and a possible product later. |
| Roboflow "Hard Hat Workers" | Head / helmet / person only; no vest. Licence not re-checked this sprint ✍️. |

## Also used: COCO-pretrained YOLO11s (person detection for tracking)

`yolo11s.pt` from Ultralytics (trained on COCO; AGPL-3.0 like the rest of Ultralytics). Used unchanged for the `person` class only.
