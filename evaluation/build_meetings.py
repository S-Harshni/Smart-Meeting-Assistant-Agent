"""The labelled meetings used to measure extraction. Written by hand for this project; names and companies are invented.

Each meeting lists the action items a careful reader would write down: task, owner, and the deadline as it was
said. Run this file to regenerate meetings.json, which adds the calendar date for each deadline.
"""
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from actions import resolve_due  # noqa: E402

M = []


def meeting(date, notes, *items):
    M.append({"id": f"m{len(M) + 1:02d}", "date": date, "notes": notes.strip(),
              "action_items": [{"task": t, "owner": o, "due_text": d} for t, o, d in items]})


meeting("2025-03-03", """
Priya: Quick sync on the checkout redesign. Where are we?
Rohan: Designs are final. I'll hand the Figma file to engineering by Wednesday.
Priya: Good. Meera, can you write the API contract for the new payment step?
Meera: Yes, I'll have the API contract drafted by Friday.
Rohan: Should we also redo the order history page?
Priya: Nice idea, but not this quarter. Let's park it.
Priya: I'll book the usability test sessions for next Tuesday.
""", ("Hand the Figma file to engineering", "Rohan", "Wednesday"),
     ("Draft the API contract for the new payment step", "Meera", "Friday"),
     ("Book the usability test sessions", "Priya", "next Tuesday"))

meeting("2025-04-10", """
Daniel: The client escalated the invoice export bug. Who can look at it?
Sara: I can. I'll reproduce the invoice export bug today and send a fix estimate tomorrow.
Daniel: Thanks. Imran, please call the client and tell them we're on it.
Imran: Will do, I'll call them this afternoon.
Sara: We already rolled back the last release, so nothing more to do there.
Daniel: I'll update the status page.
""", ("Reproduce the invoice export bug", "Sara", "today"),
     ("Send a fix estimate for the invoice export bug", "Sara", "tomorrow"),
     ("Call the client about the invoice export bug", "Imran", "today"),
     ("Update the status page", "Daniel", None))

meeting("2025-05-19", """
Anita: Budget review. Marketing overspent by 8 percent last month.
Vikram: Most of that was the conference booth. I'll send a breakdown of the conference costs by end of week.
Anita: Please do. Leila, can you renegotiate the ad agency retainer?
Leila: I'll set up a call with the agency and come back with new terms by May 30.
Vikram: Someone should look at the travel policy too.
Anita: Agreed, but let's leave that for the next review.
""", ("Send a breakdown of the conference costs", "Vikram", "end of week"),
     ("Renegotiate the ad agency retainer and bring new terms", "Leila", "May 30"))

meeting("2025-06-02", """
Tom: Hiring update. We have three backend candidates in the final round.
Grace: I'll schedule the final interviews for Thursday.
Tom: Great. Karthik, you'll prepare the system design question?
Karthik: Yes. I'll write the system design question and share it with the panel by Wednesday.
Grace: I was going to draft the offer letter template, but legal already did it last week.
Tom: Perfect, one less thing. I'll send the candidates a confirmation email tomorrow.
""", ("Schedule the final interviews", "Grace", "Thursday"),
     ("Write the system design question and share it with the panel", "Karthik", "Wednesday"),
     ("Send the candidates a confirmation email", "Tom", "tomorrow"))

meeting("2025-07-14", """
Nadia: Data pipeline incident review. The nightly job failed three times last week.
Omar: Root cause was a schema change upstream. I'll add a schema validation step to the nightly job by next Monday.
Nadia: Good. Can you also add alerting, Chen?
Chen: Sure, I'll set up a pager alert for job failures in two weeks; I'm out this week.
Omar: I'll also write the incident report by Friday.
Nadia: Actually Omar, skip the report, I already sent one to leadership this morning.
Omar: Fine by me.
""", ("Add a schema validation step to the nightly job", "Omar", "next Monday"),
     ("Set up a pager alert for job failures", "Chen", "in two weeks"))

meeting("2025-08-06", """
Elena: Launch planning for the mobile app. The store listing still needs screenshots.
Ravi: I'll produce the store screenshots by August 12.
Elena: And the privacy policy?
Fatima: Legal sent comments. I'll update the privacy policy and get sign-off by the 20th.
Ravi: Do we want a launch video?
Elena: If there's time. Nobody needs to commit to that now.
Elena: I'll submit the build to app review on Friday.
""", ("Produce the store screenshots", "Ravi", "August 12"),
     ("Update the privacy policy and get legal sign-off", "Fatima", "the 20th"),
     ("Submit the build to app review", "Elena", "Friday"))

meeting("2025-09-22", """
Marcus: Customer feedback round-up. The top complaint is slow search.
Aisha: I profiled it. I'll add an index on the product name column this week, by Thursday.
Marcus: Thanks. Julia, can you reply to the five customers who reported it?
Julia: Yes, I'll reply to them tomorrow.
Aisha: We should also think about caching.
Marcus: Let's see how the index does first.
""", ("Add an index on the product name column", "Aisha", "Thursday"),
     ("Reply to the five customers who reported slow search", "Julia", "tomorrow"))

meeting("2025-10-08", """
Sofia: Quarterly planning. We need the roadmap deck before the board meeting.
Arjun: I'll put together the roadmap deck by end of month.
Sofia: Hannah, please collect revenue numbers from finance.
Hannah: I'll collect the revenue numbers from finance by next Wednesday.
Arjun: I can also ask sales for the pipeline forecast.
Sofia: No need, I have it already.
Sofia: I'll send the board the agenda in three days.
""", ("Put together the roadmap deck", "Arjun", "end of month"),
     ("Collect revenue numbers from finance", "Hannah", "next Wednesday"),
     ("Send the board the agenda", "Sofia", "in three days"))

meeting("2025-11-17", """
Ben: Security review follow-up. The audit found two open issues.
Lakshmi: I'll rotate the production API keys today.
Ben: Good. The second issue is the missing access logs.
Diego: I'll enable access logging on the storage buckets by Wednesday.
Ben: Diego, can you also write up the remediation summary for the auditors?
Diego: Yes, I'll send the remediation summary to the auditors by November 28.
Lakshmi: Should we schedule a penetration test?
Ben: Next year's budget. Not now.
""", ("Rotate the production API keys", "Lakshmi", "today"),
     ("Enable access logging on the storage buckets", "Diego", "Wednesday"),
     ("Send the remediation summary to the auditors", "Diego", "November 28"))

meeting("2025-01-13", """
Yuki: Onboarding for the two new analysts starts next week.
Peter: I'll set up their laptops and accounts by Friday.
Yuki: Zara, could you prepare the first-week schedule?
Zara: Sure. I'll prepare the first-week schedule by Thursday.
Peter: We talked about ordering new monitors.
Yuki: They already arrived yesterday.
Yuki: I'll introduce them to the team at Monday's stand-up.
""", ("Set up laptops and accounts for the new analysts", "Peter", "Friday"),
     ("Prepare the first-week schedule", "Zara", "Thursday"),
     ("Introduce the new analysts to the team", "Yuki", "Monday"))

meeting("2025-02-20", """
Carlos: Vendor selection for the CRM. We have two finalists.
Mina: I'll request reference customers from both vendors by next Tuesday.
Carlos: Good. Who is doing the cost comparison?
Owen: Me. I'll build the three-year cost comparison by February 27.
Mina: I could run a trial with the sales team.
Carlos: Yes please, Mina, run a two-week trial with the sales team. No fixed date, start when the sandbox is ready.
""", ("Request reference customers from both vendors", "Mina", "next Tuesday"),
     ("Build the three-year cost comparison", "Owen", "February 27"),
     ("Run a two-week trial with the sales team", "Mina", None))

meeting("2025-03-27", """
Helen: Website migration check-in. DNS cutover is planned for April.
Sanjay: I'll export the redirect map from the old site by tomorrow.
Helen: And testing?
Ines: I'll run the broken-link check on staging in two days.
Sanjay: I planned to back up the old database tonight.
Helen: Do it, that one matters.
Sanjay: OK, I'll back up the old database tonight.
Ines: Should I email the newsletter list about the new site?
Helen: Not yet, we'll decide after cutover.
""", ("Export the redirect map from the old site", "Sanjay", "tomorrow"),
     ("Run the broken-link check on staging", "Ines", "in two days"),
     ("Back up the old database", "Sanjay", "tonight"))

meeting("2025-04-28", """
Kavya: Model review for the churn project. Validation AUC dropped after the last retrain.
Lucas: I suspect label leakage. I'll audit the feature pipeline for leakage by Wednesday.
Kavya: Thanks. Amara, can you rerun the backtest on the last six months?
Amara: Yes, I'll rerun the backtest and share results by next Monday.
Lucas: I'll also document the feature definitions.
Kavya: When?
Lucas: By May 9.
""", ("Audit the feature pipeline for label leakage", "Lucas", "Wednesday"),
     ("Rerun the backtest on the last six months and share results", "Amara", "next Monday"),
     ("Document the feature definitions", "Lucas", "May 9"))

meeting("2025-06-16", """
Farah: Event logistics for the partner summit.
Jonas: The venue needs a head count. I'll confirm the head count with the venue by Thursday.
Farah: Catering?
Mei: I'll collect dietary requirements from attendees by end of week.
Jonas: I was going to print badges, but the venue does that for us.
Farah: Great. I'll send the speaker briefing on June 24.
""", ("Confirm the head count with the venue", "Jonas", "Thursday"),
     ("Collect dietary requirements from attendees", "Mei", "end of week"),
     ("Send the speaker briefing", "Farah", "June 24"))

meeting("2025-08-25", """
Ola: Support backlog review. We have 140 open tickets.
Nikhil: I'll triage the tickets older than 30 days by Wednesday.
Ola: Tara, the macro library is out of date.
Tara: I know. I'll rewrite the refund macros by next Friday.
Nikhil: Could we hire a contractor?
Ola: I'll ask finance whether there is budget for a contractor. No deadline, whenever they reply.
""", ("Triage the tickets older than 30 days", "Nikhil", "Wednesday"),
     ("Rewrite the refund macros", "Tara", "next Friday"),
     ("Ask finance whether there is budget for a contractor", "Ola", None))

meeting("2025-12-01", """
Rahul: Year-end close. The reconciliations are behind.
Emma: I'll finish the bank reconciliations by December 5.
Rahul: Good. Who owns the accruals?
Wei: I do. I'll post the accrual entries by next Wednesday.
Emma: Should I chase the missing vendor invoices?
Rahul: Yes, Emma, chase the missing vendor invoices this week, by Thursday.
Wei: I had planned to update the fixed asset register, but that can wait until January.
Rahul: Agreed, leave it.
""", ("Finish the bank reconciliations", "Emma", "December 5"),
     ("Post the accrual entries", "Wei", "next Wednesday"),
     ("Chase the missing vendor invoices", "Emma", "Thursday"))

meeting("2025-05-07", """
Gita: Research sync. No decisions needed today, just updates.
Paolo: The survey closed with 412 responses. Analysis is already done and in the shared folder.
Gita: Great work. Anything blocking?
Paolo: Nothing.
Gita: Then we're done. Thanks all.
""")

meeting("2025-09-04", """
Irene: Release retro. The deploy took four hours instead of one.
Samir: The migration script was slow. I'll rewrite the migration to run in batches by September 12.
Irene: Can someone own the runbook?
Dee: I'll update the deploy runbook by next Thursday.
Samir: Let me also add a dry-run flag. Actually no, the batch rewrite covers it, forget that.
Irene: I'll share the retro notes with the wider team tomorrow.
""", ("Rewrite the migration to run in batches", "Samir", "September 12"),
     ("Update the deploy runbook", "Dee", "next Thursday"),
     ("Share the retro notes with the wider team", "Irene", "tomorrow"))

for m in M:
    day = dt.date.fromisoformat(m["date"])
    for item in m["action_items"]:
        due = resolve_due(item["due_text"], day)
        assert (due is None) == (item["due_text"] is None), item
        item["due"] = due.isoformat() if due else None

if __name__ == "__main__":
    Path(__file__).with_name("meetings.json").write_text(json.dumps(M, indent=1))
    print(len(M), "meetings,", sum(len(m["action_items"]) for m in M), "action items")
    for m in M:
        d = dt.date.fromisoformat(m["date"])
        print(m["id"], d.strftime("%a %d %b"), [(i["due_text"], dt.date.fromisoformat(i["due"]).strftime("%a %d %b") if i["due"] else None) for i in m["action_items"]])
