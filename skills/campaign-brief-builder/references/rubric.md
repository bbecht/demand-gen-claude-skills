# The rubric for checks 5 to 10

Claude judges these six checks. The script owns checks 1 to 4. Each check has one pass test, stated so two readers reach the same call. Judge the strategy as written, not what the user meant. When a check is not a Pass, the fix names the exact line to add or change.

A Fail is for a problem that stops the campaign from reaching its buyers or from being measured. A Flag is a real gap that does not stop it.

Write to `rubric.json`:

```json
{"checks": {
  "5": {"state": "pass", "reason": "...", "fix": ""},
  "6": {"state": "flag", "reason": "...", "fix": "..."}
}}
```

All six checks, every time. State is `pass`, `flag` or `fail`. A reason always. A fix whenever the state is not `pass`. No numbers in a reason that the strategy or the script did not produce.

## 5. Audience specific enough to target

**Pass test:** a media buyer could build the target list without asking a question.

- **Pass:** names all four: an industry or a named account list, a size band, a region or country, and the buying roles by title. Other filters (tech stack, a trigger) help but do not replace any of the four.
- **Flag:** one of the four is missing, so the list needs one question.
- **Fail:** no list can be built. "B2B companies", "SMBs", "anyone who needs faster payments", "decision makers".

## 6. Offer fits the audience

**Pass test:** the offer answers a problem the named buying roles own, and the call to action is one action.

- **Pass:** at least one named role would recognize the problem as theirs, and the CTA asks for one thing.
- **Flag:** the offer is a sales meeting with no value stated for the buyer ("Book a demo"), or the CTA asks for two things.
- **Fail:** the offer serves a role that is not in the audience, or there is no offer beyond "learn more".

## 7. One provable message

**Pass test:** one claim, one proof point, and the swap test. Put a competitor's name in place of the company. If the sentence still reads true, it fails.

- **Pass:** one specific claim, a proof point, and the claim turns false with a competitor's name in it. A specific result backed by the company's own customers or data turns false: the competitor has not got that proof.
- **Flag:** passes the swap test but gives no proof point, or makes two unrelated claims. A claim and its direct result ("cuts approval to 2 days, so the books close on day 4") is one claim.
- **Fail:** still reads true with a competitor's name in it. "We help companies grow faster", "the leading platform", "AI-powered efficiency".

## 8. Channels reach the named buying roles

**Pass test:** each channel says how it reaches the named roles.

- **Pass:** every channel names the targeting, list, keywords, partner or outlet that puts it in front of at least one named role. Channels do not each have to reach every role.
- **Flag:** one or more channels say nothing about how they reach the roles.
- **Fail:** a channel reaches a different audience than the one named, or no channel says how it reaches anyone.

## 9. Tracking to pipeline defined

**Pass test:** the strategy says how an opportunity gets credited to this campaign.

- **Pass:** names the CRM campaign, the rule that credits an opportunity (first touch, primary campaign source, a window), or both.
- **Flag:** names UTMs or a lead source, but not how an opportunity gets credited.
- **Fail:** says nothing about tracking. The campaign cannot be tied to pipeline.

## 10. Risks named

**Pass test:** the strategy names at least one single point of failure, each with an owner.

- **Pass:** risks named, each with an owner.
- **Flag:** risks named without owners, or no risk named at all.
- Check 10 never fails. A missing risk list is a gap in the plan, not a reason the campaign cannot run.

## What the rubric does not judge

Creative taste, tone, brand fit, or whether the idea is clever. The rubric checks that the strategy can reach its buyers and be measured. Nothing else.
