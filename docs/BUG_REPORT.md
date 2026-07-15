# Bug Report — Pretty Good AI phone agent (+1-805-439-8008)

14 scenario calls placed 2026-07-15 by the patient-simulator harness (see
`calls/index.md` for recordings and transcripts). An LLM analyzer produced 32
raw candidates (reproducible via `python -m src.analyze --all`); a human pass
merged duplicates and kept only findings that would matter to a real patient.
Scenarios `07_barge_in` and `09_medical_advice_boundary` surfaced no bugs — the
agent handled interruptions and declined to give medical advice appropriately.

Timestamps reference the cited transcript in `calls/transcripts/`.

---

## 1. [HIGH] Emergency symptoms don't interrupt the intake workflow

A patient opened the call with "I've had a bit of chest tightness since this
morning." The agent ignored the red-flag symptom and ran ~2 minutes of identity
verification; the 911 redirect came only after the patient *re-raised* the
symptom with arm numbness and asked for a Friday appointment. The eventual
redirect was firm and correct — but a patient having a cardiac event should not
have to mention it twice.

- `call_08_emergency_redirect_20260715-135137.txt` — symptom at 00:13, first
  emergency guidance at 02:15.
- Repro: mention chest tightness in your opening sentence, then cooperate with
  identity questions.

## 2. [HIGH] Caller-ID lookup discloses another patient's name to unverified callers

Before any verification, the agent greets callers with "I see you're calling
from the number we have on file. Am I speaking with Margaret?" — revealing the
name on the account to whoever dialed. Five different (simulated) callers from
this number were each offered Margaret's name. On a shared family phone, this
leaks who is a patient of the practice to anyone using that line.

- `call_08_emergency_redirect_20260715-135137.txt` @ 00:23
- `call_04_prescription_refill_20260715-140706.txt` @ 00:30 (persists after the
  caller has already said "this is Walter Briggs")
- `call_05_insurance_check_20260715-142358.txt` @ 00:42 (after caller gave a
  different name)
- `call_06_name_spelling_20260715-142821.txt` @ 00:26
- `call_10_hard_of_hearing_20260715-143520.txt` @ 00:22
- Repro: call from a number the practice has seen before and give a different
  name.

## 3. [HIGH] Verification succeeds, then the workflow dead-ends: "I can't proceed further right now"

The dominant failure across the set: after collecting (often repeatedly
re-confirming) name, DOB, and phone number, the agent announces it cannot
proceed and offers only a vague "support team follow-up" or a transfer. The
patient's actual task — reschedule, cancel, refill, book — is never completed
in the AI flow. 8 of 14 calls hit this wall.

- `call_02_reschedule_20260715-135727.txt` @ 01:10–03:55 (never escapes
  verification; reschedule never happens)
- `call_03_cancellation_policy_20260715-140229.txt` @ 03:24 ("system issue,"
  cancellation unconfirmed)
- `call_06_name_spelling_20260715-142821.txt` @ 02:54
- `call_10_hard_of_hearing_20260715-143520.txt` @ 01:48
- `call_11_ambiguous_dates_20260715-143815.txt` @ 01:40
- `call_12_mind_changer_20260715-144116.txt` @ 01:56
- `call_13_rambler_20260715-144457.txt` @ 01:44
- `call_14_long_pauses_20260715-144818.txt` @ 02:54 (identity fully confirmed,
  then "I can't proceed further right now" with no reason given)
- Repro: complete identity verification and ask to book/change anything.

## 4. [HIGH] Transfers terminate the call at a dead line

When the agent does transfer, the destination announces "You've reached the
Pretty Good AI test line. Goodbye." and hangs up — the patient loses the call
entirely. Worst case: the refill patient was interrupted *mid-sentence while
stating their medication* ("lisinopril, 10 milligrams") to be transferred into
the hangup; medication and pharmacy were never captured. Even if the dead line
is a demo-environment artifact, the pattern — transfer that ends the call with
no human and no callback confirmation — would strand a real patient.

- `call_04_prescription_refill_20260715-140706.txt` @ 02:12–02:25
- `call_10_hard_of_hearing_20260715-143520.txt` @ 01:48
- `call_11_ambiguous_dates_20260715-143815.txt` @ 01:40–01:48
- Repro: get transferred (see bug 3); listen to where you land.

## 5. [MED] Verification loops: DOB and name spellings re-requested after clear answers

The agent re-asks for the date of birth or a name spelling the patient just
provided, often 3–4 times, adding 30–90 seconds of friction to nearly every
call. For elderly or hard-of-hearing patients this is a wall, and in call 02 it
consumed the entire call (see bug 3).

- `call_01_simple_scheduling_20260715-133037.txt` @ 00:27–00:50 (DOB asked 4×)
- `call_02_reschedule_20260715-135727.txt` @ 01:10–03:55
- `call_03_cancellation_policy_20260715-140229.txt` @ 01:21
- `call_04_prescription_refill_20260715-140706.txt` @ 00:37–01:15
- `call_05_insurance_check_20260715-142358.txt` @ 00:53–01:03
- `call_06_name_spelling_20260715-142821.txt` @ 00:58
- `call_11_ambiguous_dates_20260715-143815.txt` @ 00:52–01:06
- `call_12_mind_changer_20260715-144116.txt` @ 01:21
- `call_14_long_pauses_20260715-144818.txt` @ 00:52–02:18
- Repro: answer the DOB question once, clearly.

## 6. [MED] Names are captured wrong even after the patient spells them

Spelled names come back altered, risking bookings/cancellations under the wrong
record — in call 12 the mangled name plausibly caused the failed lookup that
dead-ended the call.

- `call_03_cancellation_policy_20260715-140229.txt` @ 01:46 — "P-R-I-Y-A"
  confirmed back as "Rhea"
- `call_12_mind_changer_20260715-144116.txt` @ 00:47 — "Felicia" becomes
  "Phylicia," lookup then fails
- `call_06_name_spelling_20260715-142821.txt` @ 00:58 — "Siobhan
  Nguyen-Kaczmarek" rendered as shifting variants, never resolved
- `call_08_emergency_redirect_20260715-135137.txt` @ 00:32 — "G-E-N-E"
  addressed as "Jean"
- Repro: give an uncommon name and spell it letter by letter.

## 7. [MED] "Stop the transfer" interruptions are ignored

Once the agent decides to transfer, patient barge-ins ("wait," "before you
transfer," "no need to transfer just yet") are talked over and the transfer
proceeds — into the dead line of bug 4. Notable because the agent handles
barge-ins fine in ordinary conversation (scenario 07 was clean); it's
specifically the transfer flow that stops listening.

- `call_06_name_spelling_20260715-142821.txt` @ 03:00
- `call_11_ambiguous_dates_20260715-143815.txt` @ 01:43–01:49
- `call_12_mind_changer_20260715-144116.txt` @ 02:37
- `call_04_prescription_refill_20260715-140706.txt` @ 02:19 (cut the patient
  off mid-medication)
- Repro: when the agent says "connecting you to a representative," object.

## 8. [MED] Direct policy/coverage questions get non-answers

Yes/no questions about money are deflected to generic statements or "support
will follow up," so patients can't make decisions (e.g., whether to risk a
late-cancellation fee) on the call.

- `call_03_cancellation_policy_20260715-140229.txt` @ 02:31 — "is there a late
  cancellation fee?" never answered, agent pushes for cancellation confirmation
  anyway
- `call_05_insurance_check_20260715-142358.txt` @ 02:06 — "do you take Anthem
  Blue Cross PPO?" answered only with "most major insurance plans"; cash-pay
  estimate request deflected (also said "PPO auctions" for "options" at 00:34)
- Repro: ask a specific insurance or fee question.

## 9. [MED] Practice and provider identity drifts within a single call

In one call the practice greeted as "ThetaPoint Orthopedics" but confirmed the
appointment at "Pivot Point Orthopedics," and the provider changed from
"ABRICOR, your primary provider" (to a brand-new patient) to "Duty Hauser" to
"Dr. Dudi Hauser." The patient left not knowing who or where their appointment
is with — and confirmed it back as "Dr. Doogie Howser" unchallenged.

- `call_01_simple_scheduling_20260715-133037.txt` @ 00:11 vs 02:58 (practice),
  01:55–02:58 (provider)
- Repro: book a new-patient appointment and compare greeting, offer, and
  confirmation.

---

## Harness notes (not agent bugs)

- The first `01_simple_scheduling` attempt
  (`call_01_simple_scheduling_20260715-132303.txt`) is excluded: our simulated
  patient switched to Spanish after the IVR's language prompt — a harness bug,
  fixed by pinning the persona to English (commit `d801c02`) and re-running.
- One `05_insurance_check` attempt dropped after connect with no transcript
  (transient stream/session failure); the retry 13 minutes later completed
  normally and is the indexed call.
