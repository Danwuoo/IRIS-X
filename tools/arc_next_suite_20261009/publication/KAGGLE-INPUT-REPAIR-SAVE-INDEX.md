# IRIS-X prerequisite-input repair: verified Kaggle saves

N9-N14 are saved and verified as version 3 on their original private notebook IDs. N5-N8 were not modified. Manual start, GPU, TPU and Internet remain off; no model run was started.

[Private N6/N7 prerequisite Dataset, version 1](https://www.kaggle.com/datasets/danielwuu/iris-arc-next-prerequisites-20261010) has all 871 files verified after a provider round-trip. Kaggle extracted N6/, N7/ and dataset-manifest.json directly into its root.

- [IRIS-X N9 Object Perception](https://www.kaggle.com/code/danielwuu/iris-x-n9-object-perception): version 3, existing ID 137914884; approved source and settings verified.
- [IRIS-X N10 Demo Feedback](https://www.kaggle.com/code/danielwuu/iris-x-n10-demo-feedback): version 3, existing ID 137914952; approved source and settings verified.
- [IRIS-X N11 Candidate Memory](https://www.kaggle.com/code/danielwuu/iris-x-n11-candidate-memory): version 3, existing ID 137915031; approved source and settings verified.
- [IRIS-X N12 Neural Cpu Search](https://www.kaggle.com/code/danielwuu/iris-x-n12-neural-cpu-search): version 3, existing ID 137915103; approved source and settings verified.
- [IRIS-X N13 Program Curriculum](https://www.kaggle.com/code/danielwuu/iris-x-n13-program-curriculum): version 3, existing ID 137915159; approved source and settings verified.
- [IRIS-X N14 Agent Consolidation](https://www.kaggle.com/code/danielwuu/iris-x-n14-agent-consolidation): version 3, existing ID 137916650; approved source and settings verified.

N9-N12 use the attached, verified N6/N7 evidence automatically after the owner starts them. N13 remains CPU-only without prerequisite scanning. N14 still needs valid N9/N10/N11 results; its gate remains closed until those exist.

Scientific sources and the five original asset pins are unchanged. Existing N9 competition metadata is preserved without reading or using competition data. Original notebook versions and prior receipts are retained.

See kaggle-input-repair-publication-status.json for exact hashes and provider readback limitations. Notebook metadata returns bare Dataset identities; exact version-qualified submissions, selected-run inventory pins and scientific-contract validation are verified separately. The whole Dataset wrapper manifest is recorded as provenance, not checked at runtime.
