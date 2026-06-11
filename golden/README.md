# Golden Dataset

Hand-labeled ground truth for the eval harness. Q1 target: 100+ filings.

## Redistribution rule (enforced)

Raw filing PDFs are **never** committed here — they live only in the private
Cloud Storage bucket. Each label file references its filing by
**ticker + announcement date + ASX announcement ID**, so anyone can reconstruct
the dataset from public sources without this repo republishing documents.

## Layout

```
golden/
└── labels/
    └── <TICKER>_<YYYY-MM-DD>_<announcement-id>.json   # one label file per filing
```

Label files contain: the filing reference keys, the announcement type, the
hand-labeled field values (the same shape as the extraction schema), and
labeling metadata (who, when, dataset version).
