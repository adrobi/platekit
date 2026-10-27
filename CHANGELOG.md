# Changelog

All notable changes to platekit are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[SemVer](https://semver.org/).

## [1.0.0] — 2026-10-27

First feature-complete release: interactive PCR/sequencing plate designer,
Master Mix calculator, DNA normalization tool, step-by-step pipetting assistant
and instrument layout exporter/importer.

### Added
- Interactive plate designer supporting 96-well (`8×12`), 384-well (`16×24`),
  8/12-well PCR strips, and Rotor-Gene rotors (`36`, `72`, `100` positions)
- Smart Fill auto-layout (samples × assays × replicates, row-wise or
  column-wise, automatic `POS` / `NTC` controls) and serial standards (`STD`)
  generator
- Full editing workflow with rubber-band selection, row/column header selection,
  copy/paste well blocks, and unlimited Undo/Redo
- Master Mix calculator with built-in and editable protocol presets (Standard
  Taq PCR, qPCR SYBR Green, qPCR TaqMan Probe, PCR-RFLP digest, Sanger BigDye
  v3.1) and three dead-volume modes (`+%`, `+N reactions`, multichannel)
- DNA concentration normalization (`C₁V₁ = C₂V₂` dilution plate mode and fixed
  ng/reaction template mode) with automated pipetting QC flags (`OK`,
  `TOO_CONCENTRATED` with pre-dilution factor suggestion, `TOO_DILUTE`)
- Step-by-step interactive bench pipetting assistant (single-well, 8-channel
  column, and 12-channel row modes) with keyboard navigation
- Printable A4 HTML Bench Sheet and multi-sheet colored Excel (`.xlsx`) export
- Instrument layout export/import for Bio-Rad CFX, ABI QuantStudio / StepOne,
  Qiagen Rotor-Gene Q, and ABI 3130/3500 Sanger sequencers (`ab1kit` compatible)
- Automatic OS language detection (RU / EN with fallback to English), dark and
  light themes, JSON project persistence (`.platekit.json`), and CLI batch flags
