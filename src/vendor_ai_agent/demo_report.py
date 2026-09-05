"""Portable, escaped HTML view of a local review run; no scripts or remote assets."""
from html import escape
from pathlib import Path
from string import Template


def render_report(report: dict) -> str:
    def esc(value):
        return escape(str(value), quote=True)

    requirements = report["requirements"]
    headers = "".join(f"<th>{esc(value)}</th>" for value in requirements)
    rows, details = [], []
    for index, candidate in enumerate(report["candidates"], 1):
        cells = "".join(
            '<td><span class="present">Listed</span></td>' if item["listed_service"] is not None
            else '<td><span class="absent">Not listed</span></td>'
            for item in candidate["evidence"]
        )
        rows.append(f'<tr><th scope="row"><a href="#candidate-{index}">{esc(candidate["company_name"])}</a>'
                    f'<small>{esc(candidate["disposition"])}</small></th>{cells}'
                    f'<td class="coverage">{candidate["covered"]}<span> / {len(requirements)}</span></td></tr>')
        evidence = "".join(
            f'<li><span>{esc(item["requirement"])}</span><strong>{esc(item["listed_service"]) if item["listed_service"] is not None else "Not listed in snapshot"}</strong></li>'
            for item in candidate["evidence"]
        )
        requests = "".join(f'<li>{esc(value)}</li>' for value in candidate["follow_up"])
        details.append(f'''<details id="candidate-{index}" {'open' if index == 1 else ''}>
<summary>{esc(candidate['company_name'])}<span>Needs review</span></summary>
<div class="detail-grid"><div><p class="label">Listed service evidence</p><ul class="evidence">{evidence}</ul>
<p class="source">Snapshot reference · {esc(candidate['source_reference'])}</p></div>
<div><p class="label">Before qualification</p><ul class="requests">{requests}<li>Confirm service area and availability</li></ul>
<p class="source">Contact · {esc(candidate['email'] or 'Not supplied')}<br>Deliverability not checked</p></div></div></details>''')
    template = Template((Path(__file__).with_name("demo_data") / "report.html").read_text())
    return template.substitute(
        title=esc(report["title"]), scope=esc(report["scope"]),
        input_count=report["input_count"], unique_count=len(report["candidates"]),
        duplicates=report["duplicates_removed"], requirements_count=len(requirements),
        requirement_headers=headers, rows="".join(rows), details="".join(details),
        location=esc(report["location"]),
    )
