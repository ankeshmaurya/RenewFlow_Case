"""Batch validation. Same-batch renewals are seat-neutral; changes need a matching batch with a free seat."""
from ..models import CaseCheck, Severity
from .normalize import days_set, hhmm


def build_batches(reference):
    out = {}
    for r in reference:
        if r.deleted_at is not None or r.current_classbatch_id is None:
            continue
        out.setdefault(r.current_classbatch_id, dict(
            id=r.current_classbatch_id, name=r.classbatch_name, class_id=r.class_id, class_name=r.class_name,
            category_id=r.category_id, days=days_set(r.batch_days), days_text=r.batch_days, time=hhmm(r.batch_start_time),
            active=r.active_students_count or 0, max=r.max_batch_size or 0, educator=r.educator_name))
    return out


def _minutes(t):
    try:
        h, m = t.split(":")[:2]
        return int(h) * 60 + int(m)
    except Exception:
        return 0


def batch_checks(case, batches):
    form, ref, booking = case.primary_form, case.reference, case.booking
    if form is None or ref is None:
        return
    if form.continue_same_batch == "Yes":
        held = ref.current_classbatch_id == form.current_classbatch_id
        rec_ok = held and form.class_id == ref.class_id and form.educator_id == ref.educator_id
        case.add(CaseCheck(code="BATCH_RECORD_MISMATCH", name="Form batch, class and educator match the student's record",
                           stage="BATCH", severity=Severity.warn, passed=rec_ok,
                           detail="Matches." if rec_ok else
                           f"Form batch {form.current_classbatch_id}/class {form.class_id}/educator {form.educator_id} vs record "
                           f"{ref.current_classbatch_id}/{ref.class_id}/{ref.educator_id}."))
        if rec_ok:
            slot_ok = days_set(form.preferred_days) == days_set(ref.batch_days) and hhmm(form.preferred_time_slot) == hhmm(ref.batch_start_time)
            case.add(CaseCheck(code="BATCH_SLOT_MISMATCH", name="Form days and time equal the batch slot", stage="BATCH",
                               severity=Severity.warn, passed=slot_ok,
                               detail="Same slot." if slot_ok else
                               f"Form {form.preferred_days} {hhmm(form.preferred_time_slot)} vs batch {ref.batch_days} {hhmm(ref.batch_start_time)}."))
        if booking is not None and booking.request_status == "Failed_Batch_Full":
            b = batches.get(form.current_classbatch_id, {})
            case.add(CaseCheck(code="BATCH_FULL_FALSE_POSITIVE", name="Booking was not failed by a false capacity check",
                               stage="BATCH", severity=Severity.notice, passed=not (held and rec_ok),
                               detail=(f"Booking {booking.id} was failed as batch full ({b.get('active')}/{b.get('max')}), but the student already "
                                       f"holds a seat in batch {form.current_classbatch_id}. A renewal needs no new seat.") if (held and rec_ok)
                               else "Genuinely full or record mismatch."))
            if held and rec_ok:
                case.healed_actions.append(f"Corrected false 'batch full' on booking {booking.id}: same-batch renewal is seat-neutral.")
        return

    cur = ref.current_classbatch_id
    want_days, want_time = days_set(form.preferred_days), hhmm(form.preferred_time_slot)
    cands = [b for b in batches.values() if b["class_id"] == ref.class_id and b["id"] != cur and b["days"] == want_days
             and b["time"] == want_time and b["active"] < b["max"]]
    alts = []
    for b in batches.values():
        if b["id"] == cur or b["category_id"] != ref.category_id or b["active"] >= b["max"]:
            continue
        overlap = len(b["days"] & want_days)
        if overlap == 0:
            continue
        same_class = b["class_id"] == ref.class_id
        alts.append(dict(batch_id=b["id"], name=b["name"], class_name=b["class_name"], days=b["days_text"], time=b["time"],
                         seats_left=b["max"] - b["active"], same_class=same_class,
                         exact_slot=(b["days"] == want_days and b["time"] == want_time),
                         caveat=None if same_class else "Different class or level or track: needs teacher and Ops confirmation.",
                         _sort=(abs(_minutes(b["time"]) - _minutes(want_time)), -overlap)))
    alts.sort(key=lambda a: a["_sort"])
    for a in alts:
        a.pop("_sort")
    case.alternatives = [a for a in alts if a["same_class"] and a["exact_slot"]] or alts
    if cands:
        case.add(CaseCheck(code="BATCH_CHANGE_PARENT_SELECTION", name="Batch change has a matching batch", stage="BATCH",
                           severity=Severity.notice, passed=False,
                           detail=f"{len(cands)} matching batch(es) with free seats: " + ", ".join(c["name"] for c in cands) + ". Parent picks."))
    else:
        want = f"{form.preferred_days} {want_time}"
        case.add(CaseCheck(code="BATCH_CHANGE_NO_MATCH", name="Batch change has a matching batch", stage="BATCH",
                           severity=Severity.warn, passed=False,
                           detail=f"No other batch of class {ref.class_name} runs {want} with a free seat. "
                                  f"{len(alts)} nearby alternative(s) in the same category."))
