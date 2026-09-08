# Business Context Exploration

## Question 1
**Prompt:** Our Wildcat Capital dataset includes credit score, debt-to-income ratio, and annual income for each borrower. In consumer lending, how are these three attributes typically weighed together when assessing credit risk, and can a strong credit score mask risk that would otherwise show up in DTI or income?

**Summary of Claude's response:** Credit score, DTI, and income each measure something different — score is backward-looking (repayment history), DTI measures current capacity to take on new debt, and income scales and bounds DTI and loan size. Lenders typically use score to set the risk tier and rate, DTI as a capacity gate (often capped around 36-43%), and income to validate DTI and cap loan size, sometimes combining all three into one risk score or grid. A strong score can absolutely mask risk because it's backward-looking and slow to react: a borrower who recently took on a large new obligation can show cash-flow strain in DTI or income well before it ever shows up in their score, which is why policies typically require all three factors to clear their own thresholds rather than letting a strong score offset a weak DTI.

**Follow-up question this raised:** Does Wildcat's underwriting policy score these three attributes independently or combine them into one grid, and if independently, which threshold is actually the bottleneck in our approval funnel?

## Question 2
**Prompt:** Wildcat's portfolio spans five loan purposes — Auto, Personal, Home Improvement, Education, and Business — with Business loans typically much larger individually than the other four. What does a portfolio committee usually expect to see in a quarterly review for a lender with this specific mix, and how might reporting differ across these five segments?

**Summary of Claude's response:** A portfolio committee generally expects overall health metrics — outstanding balance and growth, delinquency/default rates (both count- and dollar-weighted), net charge-offs, reserve coverage, yield, and vintage or roll-rate migration — plus segment-level breakdowns, since Wildcat's mix concentrates risk unevenly. Because Business loans are large individually, they typically need count- and dollar-based tracking, sometimes down to single-name detail, while high-volume Auto and Personal loans are usually reported statistically through rate trends and vintage curves. Home Improvement often splits into secured vs. unsecured, and Education usually gets its own repayment-status view (deferred/in-school vs. in-repayment) layered on top of the standard status categories. The underlying goal is the same core metrics everywhere, weighted and drilled into proportionally to each segment's dollar and idiosyncratic risk.

**Follow-up question this raised:** Given how few but how large Wildcat's Business loans are, should the quarterly package include a single-name concentration cap, and what threshold should trigger committee escalation?

## Question 3
**Prompt:** Wildcat tracks four loan statuses: Current, Paid Off, Default, and Delinquent. What's the practical difference between delinquency and default in consumer lending, and at what point does a loan typically move from Delinquent to Default?

**Summary of Claude's response:** Delinquency and default mark different severities of the same core problem — a missed payment. Delinquency starts the moment a payment is late and is staged by days past due (commonly 30/60/90/120 DPD); the loan is still considered active and collectible and can cure back to Current. Default is a more severe, typically policy-defined status signaling the loan is unlikely to be repaid on original terms, triggering charge-off, collections, or legal action, and it's much harder to reverse than delinquency. A common industry convention treats 90+ days past due as serious delinquency, with charge-off or formal default commonly triggered around 120-180 days, depending on loan type and regulatory guidance.

**Follow-up question this raised:** Does Wildcat's "Delinquent" status represent a single bucket for any past-due loan, or does the data distinguish day-past-due bands — and if it's a single bucket, how would we actually model the Delinquent-to-Default transition point?
