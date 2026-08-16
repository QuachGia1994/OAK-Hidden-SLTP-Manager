# Rider-Waite-Smith Tarot artwork

These local images are sourced from the [metabismuth/tarot-json repository](https://github.com/metabismuth/tarot-json), which contains 78 Rider-Waite-Smith scans in `cards/` and publishes an explicit [MIT LICENSE](https://github.com/metabismuth/tarot-json/blob/e6414a098acc87831a8953bca7576b033b2fda54/LICENSE). The repository README identifies the scans as Rider-Waite-Smith artwork by Pamela Colman Smith, published in 1910, with public-domain provenance.

The asset preparation script validates the exact 78-card inventory, records the pinned upstream commit and source path in `sources.json`. Each 350×600 source is bounded to 420×630 without upscaling, so it remains 350×600, and is then encoded as WebP at quality 82. Runtime code serves only these local WebP files; it does not hotlink upstream sources.

The underlying RWS artwork is identified as public domain in the United States and United Kingdom. The repository's MIT license applies to its project code and packaging; public-domain status can vary by jurisdiction, so verify local law before reusing the artwork elsewhere.

The verbatim upstream project license is preserved in [UPSTREAM_LICENSE.txt](./UPSTREAM_LICENSE.txt).
