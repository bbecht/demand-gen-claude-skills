# Lead times

Due dates count back from launch. Each function's pre-launch work is due this many days before launch. These are a starting point, not a benchmark. Show the table to the user and have them confirm or edit every line before the brief sets dates. The brief prints which lines were edited and which were kept as shipped.

| Function | Days before launch | What is due by then |
|---|---|---|
| Creative | 21 | Concepts approved, final files in every size the channels need |
| Content | 21 | The offer asset finished, supporting assets drafted |
| PR | 14 | Angle, spokesperson and outlet list confirmed |
| Operations | 10 | CRM campaign, forms, routing and UTMs tested end to end |
| Ads | 7 | Campaigns built, targeting and settings checked, waiting to go live |
| Sales enablement | 5 | Talk track, sequences and follow-up rules in reps' hands |

To change a line, write the edits to `lead_times.json` and pass it to the brief:

```json
{"creative": 28, "ads": 10}
```

Keys: `creative`, `content`, `pr`, `operations`, `ads`, `sales`. Days, or "4 weeks".

Requirements marked `launch` are due on launch day. Requirements marked `ongoing` run from launch to the end date. The script adds a task to replace each Assumption: an assumed cost per lead is due at the end of week one, when the first spend reports. An assumed deal size, rate or lag is due the day the first opportunities land, since it cannot be measured sooner.
