# Transaction Monitoring Tuning Memo

**To:** Financial Crime Compliance Committee
**Subject:** Performance of the three monitoring rules and proposed threshold changes
**Scope:** 5 000 retail customers, 120 days, 339 384 transactions (simulated, see Data below)

## 1. Summary

The three rules raise 208 alerts (41.6 per 1 000 customers) and catch 90 of the 100 suspicious customers. 57% of alerts are false positives, and almost all of them come from two legitimate customer groups: stokvels and cash heavy small businesses.

I recommend:

1. **Structuring:** require 4 near threshold deposits in 7 days instead of 3. Precision rises from 61% to 84% and alerts fall by 30%, for the loss of 1 of 39 structurers.
2. **Pass through:** keep the 8 sender threshold, and add the alert triage model so stokvel alerts are ranked to the bottom of the queue rather than suppressed.
3. **Second line review:** each month, review the 200 most unusual customers who did not alert. In this data that recovers all 10 mules the rules missed.

## 2. Rule Performance

| Rule | Alerts | True positives | Precision | Recall on target typology |
| --- | ---: | ---: | ---: | ---: |
| Structuring | 64 | 39 | 61% | 100% |
| Pass through | 124 | 32 | 26% | 75% |
| Dormant reactivation | 23 | 21 | 91% | 100% |
| **All rules (unique customers)** | **208** | **90** | **43%** | **90%** |

### Where The False Positives Come From

| Rule | Small business | Stokvel | Low activity |
| --- | ---: | ---: | ---: |
| Structuring | 25 | 0 | 0 |
| Pass through | 15 | 77 | 0 |
| Dormant reactivation | 0 | 0 | 2 |

- **Stokvels** collect contributions from 8 to 30 members and pay out within days. On flows alone this matches a mule account. 53% of all stokvel customers in the book raised a pass through alert.
- **Small businesses** such as spaza shops deposit large amounts of cash, and some round their deposits to amounts just under the threshold.
- **Low activity customers** who receive a pension or property payout look like dormant account reactivation.

These are ordinary South African banking patterns. Alerting on them costs investigator time and, if accounts are restricted, damages trust with customers who are already underserved.

## 3. Threshold Testing

### Structuring (80% floor)

| Deposits in 7 days | Alerts | Precision | Recall |
| ---: | ---: | ---: | ---: |
| 2 | 129 | 30% | 100% |
| 3 (current) | 64 | 61% | 100% |
| **4 (proposed)** | **45** | **84%** | **97%** |

Raising the floor to 90% instead looks attractive on precision but loses recall fast (77% at 3 deposits, 33% at 4), because structurers do not always deposit right up to the limit.

### Pass Through

| Minimum senders | Alerts | Precision | Recall |
| ---: | ---: | ---: | ---: |
| 6 | 220 | 20% | 88% |
| 8 (current) | 124 | 26% | 75% |
| 10 | 104 | 25% | 63% |
| 12 | 93 | 20% | 48% |

Changing the sender count does not fix this rule. Large stokvels keep alerting at any threshold, while small mule rings drop out. The issue needs a different signal, which is why the triage model is proposed rather than a threshold change.

## 4. Alert Triage Model

A gradient boosted model trained on the outcome of past alerts ranks each new alert by how likely it is to be suspicious. It does not suppress alerts; it orders the queue.

| Alerts worked, in triage order | Share of suspicious cases found |
| ---: | ---: |
| 40 | 44% |
| 80 | 88% |
| 100 | 99% |
| 208 (all) | 100% |

Working the queue in triage order, investigators would reach 99% of suspicious cases after 100 of the 208 alerts.

**Caveat.** This result is too good to expect in production. Simulated cases separate more cleanly than real ones, and real investigation outcomes are noisy labels. Before any use, the model would need to be validated on historical alert outcomes, monitored for drift, and explainable for each alert, so that a closed alert can be justified to the regulator.

## 5. Second Line Anomaly Review

An isolation forest scores every customer on how unusual they are. On its own it is a poor alerting tool: the most unusual customers are mostly innocent low activity accounts. Applied only to customers the rules did not alert:

| Customers reviewed | Missed mules found (of 10) |
| ---: | ---: |
| 50 | 2 |
| 100 | 4 |
| 200 | 10 |

Each mule found this way should be fed back into rule design, for example a lower sender threshold for accounts under six months old.

## 6. Data And Limitations

- **Simulated data.** No labelled laundering data is public. Customers, transactions and three typologies were simulated with known labels, so precision and recall are exact. The flip side is that the planted cases are cleaner than real ones.
- **Three typologies only.** Trade based laundering, cross border flows, cash intensive business fronts and crypto off ramps are not covered.
- **Customer level.** Alerts are de-duplicated per customer. A production system would also link related accounts and counterparties.
- **Threshold.** R49 999.99 is the section 28 cash threshold reporting level set by regulation 22B, in force since 14 November 2022 (it was R24 999.99 before). The same amendment means the aggregation provisions previously in regulation 24 no longer apply, so a run of deposits each just under the threshold is not caught by threshold reporting. Picking it up is a monitoring job, which is the gap the structuring rule covers.

## 7. Next Steps

1. Approve the structuring change and run it in parallel with the current rule for one month.
2. Pilot the triage model on historical alerts with known outcomes before it touches live queues.
3. Start the monthly second line anomaly review with a 200 customer sample.
