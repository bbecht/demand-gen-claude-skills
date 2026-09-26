# The campaign strategy template

Part 1 is the blank template to hand a user who is starting from zero. Part 2 is how Claude maps any strategy, in any form, into `strategy.json` for the script.

## Part 1. The blank template

Copy this, fill it in, and paste it back. Nine parts are required. The rest sharpen the check.

```
CAMPAIGN NAME:

1. PIPELINE TARGET (required)
   Pipeline in dollars:
   Due date (the day the pipeline has to exist):

2. AUDIENCE (required)
   Accounts (industry or named list, size, region, any other filter):
   Buying roles (titles):

3. OFFER (required)
   What the buyer gets:
   The one action you want them to take:

4. CORE MESSAGE (required)
   One sentence:
   The proof behind it:

5 and 6. CHANNELS AND BUDGET BY CHANNEL (required)
   For each channel: name, type, budget, and how it reaches the buying roles
   Total budget:

7. TIMING (required)
   Launch date:
   Run length (weeks, months, or an end date):

8. FUNNEL NUMBERS (required, from your own CRM)
   Average deal size:
   Share of leads that become opportunities:
   Days from lead to opportunity:

9. COST PER LEAD BY CHANNEL (required, from your own results)
   For each channel:

OPTIONAL
   Sales capacity: reps who will work these opportunities, and new opportunities each can take a month
   Win rate and sales cycle in days (dates the closed revenue projection)
   Owner for each function: ads, PR, content, operations, sales enablement, creative
   How an opportunity gets credited to this campaign in the CRM
   Risks: single points of failure, each with an owner
   Your UTM naming convention, if you have one
```

No funnel numbers or cost per lead? Pull them from the CRM, or run Pipeline Leak Finder or Revenue by Channel first. With no real number, type your best assumption and mark it as one. The check then reads Untested until week one replaces it.

## Part 2. Mapping into strategy.json

Claude writes this file. Rules:

- **Copy each number and date as the user wrote it, without the words around it.** "CPL is running $220" becomes "$220". "$90k" stays "$90k". "8" stays "8". "the end of May (May 31) 2027" becomes "May 31, 2027" only because the user named the day. The script parses each value and notes how it read it. Claude never converts, sums or rounds.
- **Hedges are not assumptions.** "About $300" is the user's number: copy "about $300" or "$300". A number is an assumption only when the user calls it a guess, an estimate with no data, or a channel they have never run. Then add its key to `assumptions`.
- **Blank stays blank.** "TBD", "not sure" and "ask the events team" are blank. Never fill a field the user did not give. The script asks for it.
- **Claude never adds a channel budget or a total.** If the user gives only a total, leave channel budgets blank and the script asks.
- **Show the user the mapping** before the first check: a short table, one row per part of the strategy, as written.

```json
{
 "campaign": {"name": "", "id": "", "objective": "pipeline"},
 "target": {"pipeline": "", "due_date": ""},
 "audience": {"accounts": "", "roles": [], "tag": ""},
 "offer": {"offer": "", "cta": "", "asset": false},
 "message": {"claim": "", "proof": ""},
 "channels": [
  {"name": "", "type": "", "platform": "", "budget": "", "cost_per_lead": "", "reach": ""}
 ],
 "budget_total": "",
 "launch": {"date": "", "run": ""},
 "funnel": {"avg_deal": "", "lead_to_opp_rate": "", "lead_to_opp_days": ""},
 "sales": {"reps": "", "opps_per_rep_month": ""},
 "revenue": {"win_rate": "", "sales_cycle_days": ""},
 "owners": {"ads": "", "pr": "", "content": "", "operations": "", "sales": "", "creative": ""},
 "tracking": "",
 "risks": [{"risk": "", "owner": ""}],
 "utm_convention": null,
 "assumptions": []
}
```

### Field notes

| Field | Note |
|---|---|
| `campaign.id` | The CRM campaign ID, wherever the user names it, including inside the tracking line. Blank: the script makes one from the name |
| `audience.roles` | One title per entry. "Ops and logistics directors" is two roles: "Ops director", "Logistics director" |
| `audience.tag` | A short label for UTMs, like "cfo-mfg". Set it when the first role is long. Blank: the script uses the first role |
| `offer.asset` | true when the buyer gets a thing someone has to build: a report, benchmark, calculator, assessment, guide or recording. A session that hands back a written result counts. false for a plain meeting or demo. It turns on the Content section |
| `channels[].name` | Two to four words: "LinkedIn ads", "CISO roundtables", "Breach report PR". The rest of the user's sentence goes in `reach` |
| `channels[].type` | One of: paid_social, paid_search, display, syndication, webinar, event, email, organic_social, content, direct_mail, partner, pr, outbound. The type decides which brief sections fill. Pick by format: a webinar with a partner is `webinar`; `partner` is co-marketing with no format of its own |
| `channels[].platform` | LinkedIn, Google, the vendor, partner, tool or outlet the user names. Becomes utm_source. Two or more named: the first. None named: leave blank and the script uses the channel name |
| `channels[].reach` | How the channel reaches the buying roles, in the user's words. Check 8 reads it |
| `channels[].budget` | "$0" for a channel with no spend. It buys no leads, and check 3 flags it |
| `launch.run` | "10 weeks", "3 months", or an end date |
| `funnel.lead_to_opp_days` | Days, or "3 weeks" |
| `tracking` | How an opportunity gets credited, in the user's words. Check 9 reads it |
| `sales.reps`, `sales.opps_per_rep_month` | The count as written: "2 AEs" or "2". The script reads the leading number |
| `utm_convention` | Only if the user gives one. Keys `source`, `medium`, `campaign`, `content`, with placeholders `{platform}`, `{medium}`, `{channel}`, `{campaign_id}`, `{objective}`, `{audience}`, `{yyyymm}`, `{req_id}` |
| `assumptions` | Numbers the user typed as a guess. Only these keys: `funnel.avg_deal`, `funnel.lead_to_opp_rate`, `funnel.lead_to_opp_days`, `channels.<channel name>.cost_per_lead` |

### Which channel types fill which brief sections

| Type | Sections it fills |
|---|---|
| paid_social, paid_search, display | Ads, Creative |
| syndication | Ads, Content |
| webinar, event, email, organic_social, direct_mail | Content, Creative |
| content, partner | Content |
| pr | PR |
| outbound | None beyond the two every campaign gets |

Content also fills when `offer.asset` is true. Operations and Sales enablement are always in the brief. A section nothing calls for reads "Not in this campaign".
