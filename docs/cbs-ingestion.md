# CBS monthly housing data adapter

Source: CBS StatLine table [85773NED](https://opendata.cbs.nl/CBS/nl/dataset/85773NED/table), licensed [CC BY 4.0](https://data.overheid.nl/dataset/45084-bestaande-koopwoningen--verkoopprijzen-prijsindex-2020-100). Attribute CBS/Kadaster.

The table covers January 1995 onward and includes monthly average transaction prices and the existing-home price index (2020=100). The average sale price is **not** a quality-adjusted measure of price development.

Run `python -m etl.sources.cbs --output data/cbs-housing.csv` to download a local CSV with `date,series,value` columns. This adapter resolves topic field identifiers from CBS DataProperties and filters monthly period codes, excluding quarterly/annual aggregates. It does not write to Cloudflare.

Next: confirm live CBS API response shape, metadata labels and complete 2000-to-current coverage. Do not import into production until that verification and spot checks pass.
