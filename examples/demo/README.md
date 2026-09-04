# Export example

An authored grounds-maintenance enquiry and one fictional supplier demonstrate the review
record format. Company names, contact details and the score are illustrative. The `.example`
domains are reserved placeholders. No discovery, website scraping or LLM assessment is performed.

| Tender requirement | Example evidence | Reviewer action |
| --- | --- | --- |
| Mowing and seasonal cleanup | Fictional service description | Check actual service offering |
| Work in Ontario | Illustrative company location | Confirm delivery/service area |
| Appropriate insurance | Not supplied | Request confirmation |

Run `make demo` from the repository root. The real output generator writes JSON, CSV and XLSX
under `outputs/demo/`. The committed [JSON](vendor_matches.json) shows the expected record;
`scoring_method=authored_example` and `match_status=needs_review` prevent it from being confused
with an assessed recommendation.
