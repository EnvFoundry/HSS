# Working on HSS

HSS is a composable humanities and social sciences research environment. Keep research resources, installation and host interfaces coherent.

Read `README.md`, then the relevant source and examples. The catalogue lives in `src/hss/data/catalog.json`; field and direction entries reference shared module IDs. A module's computation, external software and research guidance are distinct fields. Register only capabilities that are actually implemented.

Browsing creates no files. Preparation acts on explicit selections and reuses compatible interpreters. Projects own their material, analysis and manuscripts. The host owns accounts, execution jobs and model calls. Keep CLI stdout as JSON and progress on stderr; keep imports of numerical libraries out of the catalogue path.

Write concrete research guidance. Interpret statistical results in terms of the study design. Preserve exact source passages and actual data values. Do not invent observations, transcripts, references, results or completed host integrations. Expose missing inputs directly and keep unsupported methods available through their real upstream software.

Use relevant examples and tests when changing installation, numerical calculations, study execution or interfaces. Run `python -m unittest discover -s tests`; TypeScript changes also need `npm run build` and `npm test` in `packages/client`. Keep generated client JavaScript aligned with its TypeScript source.
