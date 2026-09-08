# Prompt Engineering Comparison

**Question used:** How should a BI analyst communicate data limitations to a non-technical audience?

## Strategy 1 — Zero-shot

**Prompt:** How should a BI analyst communicate data limitations to a non-technical audience?

**First 150 words of response:** A BI analyst's core challenge here is that technical caveats and business confidence usually feel like they're in tension — stakeholders want a clear answer, and every honest dataset has gaps, biases, or assumptions baked in. The skill is presenting the limitation as information that sharpens the decision, not as a hedge that undermines it. The most reliable approach is to translate the limitation into its business consequence rather than its technical cause. Instead of telling Wildcat's portfolio committee "the default flag has a 90-day lag and survivorship bias in the vintage cohort," an analyst would say something like "this default rate likely understates risk in loans originated in the last three months, because many of them haven't had time to reach 90 days past due yet — treat the newest vintage's numbers as provisional, not final." The audience doesn't need to understand lag structure or cohort construction; they need...

**Evaluation:** This response is surprisingly specific for "zero-shot" — it already invents a Wildcat-specific example (90-day lag, vintage cohorts) without being asked to. What's missing is any explicit audience — it never says who it's talking to, it just assumes a generic stakeholder. Additionally the answer given is not very concise and does a lot of introducing ideas before it gets to the specific point that is trying to be reached. 

## Strategy 2 — Role-assigned

**Prompt:** You are a senior BI analyst at Wildcat Capital, a regional consumer lender, presenting the quarterly loan portfolio dashboard to a committee of three non-technical senior executives who will use it to make lending policy decisions. How should you communicate the dashboard's data limitations to this audience?

**First 150 words of response:** Presenting to three executives who'll act on this dashboard, the guiding principle is the same one that applies to any portfolio review: translate every limitation into what it means for the specific decision they're about to make, not into the technical mechanism behind it. With only three people in the room and real policy authority on the table, you have more room to be direct and conversational than you would with a written report, but the discipline is identical. Concretely, that means a few things. Frame each limitation in terms of the number's reliability for the decision at hand — "the default rate on loans originated in the last quarter is likely understated, because many haven't had time to reach 90 days past due yet, so I wouldn't tighten underwriting off that segment alone yet" lands very differently than "there's a lag bias in the default flag." Say it before...

**Evaluation:** Quite similar in substance to the zero-shot response (same core moves: translate to business impact, plain confidence labels, flag before being asked, don't over-hedge). The role framing mainly changed the tone and added one new detail specific to the three-person setting — the Business segment concentration example. Given the overlap, the role assignment added less new value than expected.

## Strategy 3 — Few-shot

**Prompt:** Here's the format I want you to use in your answer: Practice: [name of the practice] / Why it works: [one sentence] / Example: [short concrete example]. Using that format, how should a BI analyst communicate data limitations to a non-technical audience?

**First 150 words of response:** Practice: Translate the technical cause into its business consequence / Why it works: stakeholders don't need to understand why a number is shaky, just how much to trust it and for what decision / Example: instead of "the default flag has a 90-day lag and cohort survivorship bias," say "this default rate likely understates risk for loans from the last three months — treat that vintage's numbers as provisional." Practice: Pair the number with a plain-language confidence qualifier / Why it works: it lets the audience calibrate trust without a statistics lesson / Example: labeling a KPI "solid estimate" versus "directional only" versus "not enough data yet." Practice: Put the caveat where the decision is made, not in an appendix / Why it works: a limitation that's easy to skip gets skipped; one that's next to the number gets used / Example: shading the newest, unreliable quarter differently on a...

**Evaluation:** Similar substance to the other two strategies, but the forced structure makes it the most reusable of the three — it reads like something you could paste directly into a team style guide. The answer is nice and concise which makes it great for creating immediate impact on the reader who may be busy and does not have time for all the fluff in the other responses. What's missing: no audience is specified at all, since the constraint was on format rather than role, so it's less tailored than Strategy 2.

## Conclusion

All three strategies converged on largely the same substantive advice. That said, the role-assigned prompt produced the response closest to something you could actually say verbatim in a committee meeting, while the few-shot prompt produced the most reusable, scannable artifact — a checklist you could paste into internal documentation. The zero-shot response was the most complete narrative explanation but the least tailored to a specific audience or use case. For a working BI analyst, the most useful outcome didn't come from picking one "winning" strategy, but from combining them: use role-assignment when rehearsing what to actually say in the room, and few-shot formatting when turning that judgment into a reusable team standard.

## Fact-Check

**Claim:** "federal guidance for many consumer installment and credit products calls for charge-off no later than 180 days past due" (from the Business Context response on delinquency vs. default)

**Source:** Federal Reserve, https://www.federalregister.gov/documents/2000/06/12/00-14704/uniform-retail-credit-classification-and-account-management-policy 

**What the source says:** The policy sets two different thresholds, not one: closed-end (installment) loans should be classified as a loss and charged off at 120 cumulative days past due, while open-end (revolving) loans get the longer 180-day threshold.

**Agreement / conclusion:** Partially disagree. Claude wasn't wrong that 180 days appears in federal guidance, but it applied that number to "consumer installment" loans broadly — when the actual policy reserves 180 days for revolving/open-end credit and sets a shorter 120-day threshold for installment (closed-end) loans, which is what most of Wildcat's book (Auto, Personal, Home Improvement, Education) actually is. This is a good example of why a specific numeric threshold from Claude should always be checked before it's used in an actual policy decision — the general shape of the answer was right, but the exact number depended on a loan-type distinction Claude glossed over.
