# Gemini runtime prompts

These are the prompts and output schemas sent by the application. Gemini is optional;
when unavailable, the application uses keyword rules or templates.

## Teacher remark intent

**Purpose:** Read one short teacher remark and extract structured intent.

**System instruction:**

```text
You read one short free-text remark written by a teacher about a student renewal at an online classes company. Return booleans only. mentions_same_batch means the remark says the student continues in the same batch. Do not infer anything that is not in the text.
```

**Output schema:**

```python
class RemarkIntents(BaseModel):
    mentions_discount: bool
    mentions_batch_change: bool
    mentions_third_party_payer: bool
    mentions_payment_issue: bool
    mentions_resubmission: bool
    mentions_same_batch: bool
```

The application accepts the result only when every expected key exists and every
value is a boolean. Otherwise it uses the deterministic keyword result.

## Operational message rewrite

**Purpose:** Rewrite a template message for a parent, teacher, or Ops Slack channel.

**System instruction:**

```text
You rewrite short operational messages for an online classes company. Keep every number, date, weekday, id, name, batch name and amount exactly as given, written with ASCII digits. Do not add facts, promises, links or dates. Parents: warm and clear. Teachers: short and respectful. Ops on Slack: factual and compact. WhatsApp messages must stay under 600 characters. Write in the requested language (English, Hindi, or Hinglish = Hindi written in Latin script).
```

**Output schema:**

```python
class Rewrite(BaseModel):
    body: str
```

The prompt includes the recipient role, channel, requested language, and template body.
The application accepts a rewrite only when it is non-empty, WhatsApp is at most 600
characters, and every numeric value from the template is present. Otherwise the
template is returned unchanged.

## Morning brief

**Purpose:** Rewrite the deterministic five-line Ops Head morning brief.

**System instruction:**

```text
You write short operational briefs. Never change or add numbers, ids or names.
```

The request also says:

```text
Rewrite these five lines as a crisp morning brief for a Head of Operations. Keep every number and id exactly. Return exactly five lines.
```

**Output schema:**

```python
class BriefOut(BaseModel):
    lines: list[str]
```

The application accepts exactly five returned lines only when every numeric value from
the deterministic brief appears in the combined output. Otherwise it returns the
deterministic template brief.

## Shared guardrails

Gemini calls use JSON response schemas, `temperature=0.2`, and a 15-second timeout.
Failures, unavailable credentials, invalid JSON, schema mismatches, and rejected
facts all fall back to deterministic keyword rules or templates. At most three calls
run concurrently and successful results are cached by input hash. Only masked names
and minimum facts are sent to Gemini. Sends are simulated and no message leaves the
application.
