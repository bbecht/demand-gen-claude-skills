# How to export your deals with stage history

Goal: every deal from the last 12 to 24 months, won, lost and open, with the date it entered each stage. A deal list with only the current stage is not enough. The skill needs the path each deal took.

## HubSpot

HubSpot keeps a "Date entered" property for every stage in every pipeline. Add those columns to the export.

1. CRM > Deals. Switch to the table view.
2. Filter: Pipeline is the one you want. Create date is in the last 24 months.
3. Edit columns. Include Record ID, Deal Name, Pipeline, Deal Stage, Amount, Create Date, Close Date.
4. Still in Edit columns, search "Date entered". Add the one for every stage in the pipeline, Closed Won and Closed Lost included. They read like `Date entered "Proposal (Sales Pipeline)"`.
5. Export > CSV.

Several pipelines in one file work. The skill reads the pipeline with the most deals and lists the rest it left out. Ask Claude for a different one by name.

## Salesforce

Salesforce records every stage change in Opportunity History. Report on it.

1. Reports > New Report. Choose the **Opportunity History** report type.
2. Filters: Show All Opportunities. Created Date is the last 24 months.
3. Columns: Opportunity ID, Opportunity Name, From Stage, To Stage, Last Modified, Amount, Close Date, Stage, Created Date.
4. Remove any grouping. Run the report.
5. Export > Details Only > CSV.

The report also holds rows for amount and close date edits. The skill skips any row where the stage did not change.

**Using Field History instead.** If your org reports on Opportunity Field History, that works too. Filter Field / Event to Stage. Include Opportunity Name, Old Value, New Value, Edit Date, Stage, Amount, Created Date, Close Date.

## Any other CRM

Pipedrive, Zoho, Close, a spreadsheet. Any file with one row per stage change works:

| Column | What it holds |
|---|---|
| Deal ID | The same ID on every row for a deal |
| Stage | The stage the deal moved into |
| Date entered | The date it moved in |
| Amount | Optional, but needed for revenue figures |

Custom stage names are fine. If Claude cannot tell which stages mean won and lost, it asks.

## Before you upload

- Include lost deals. Every lost deal shows where a deal died.
- Include open deals. They feed the stuck list.
- Leave renewals out, or export them from their own pipeline. A renewal is not a new decision to buy.
- Do not clean the file first. The data check is part of the answer.
- Remove anything you are not allowed to share. Deal names are optional.
