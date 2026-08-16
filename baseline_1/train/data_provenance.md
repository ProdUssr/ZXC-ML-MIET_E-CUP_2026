# Data provenance

The only training/validation source in Phase 0 is the organisers-provided `data/data.csv` and its accompanying `data/images.zip`. Rule triggers and explanation templates were written manually from the published competition rubric, then checked against the organiser train data. Rule scores are deliberately coarse evidence bands; the `0.50` decision thresholds separate negative/prior and positive evidence and are not presented as continuous-model calibration or grid search. No external API, proprietary-model explanation, scraped text, or generated training label is used.

Images are inspected only to establish the supplied file layout in Phase 0. The shipped `submission/` contains neither the dataset nor any images.
