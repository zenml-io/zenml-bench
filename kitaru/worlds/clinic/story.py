# /// script
# requires-python = ">=3.11"
# ///
"""The clinic world: a veterinary chain's appointment assistant and its recorded history.

One seeded plan produces every session as plain data. No model is called and no agent runs.

    python story.py history --out <dir>     # sessions-<release>.jsonl per release + ground_truth.json

The calendar is frozen: the history runs from 1 June to 20 July 2026 and every task says "this is a
snapshot taken on 20 July 2026".

What is planted (each is listed in ground_truth.json). The diagnosis tasks D1 to D5 all read this one history.

- `wrong_clinic` (D1, D5): from 15 June the scheduling API books two clinics into their similarly named
  neighbours: a booking sent for Harbour Street comes back confirmed at Harbour Square, and Mill Road at
  Millbrook Road, about seven times in ten. The assistant sent the right clinic id; the result names another.
  The reply repeats the clinic the customer asked for. A few customers complain later, in other conversations.
- `search_twice`: in the same period the clinic search lists the neighbour first, so the assistant searches
  a second time. Release 1.3.0 (9 July) fixed that. It did not touch the booking fault, which goes on.
- `partner_referrals` (D2): from 22 June a partner's portal sends new patients. Registering an owner and
  their animals takes three times the model calls of an ordinary conversation, so cost per conversation rises
  by about a third. Release 1.2.0 rolled out over 21 to 25 June, the same days; its conversations cost what
  1.1.0's did, and 1.1.0 served new patients too while it was still live. The changelog must not credit the release
  with the new-patient flow: a first baseline did, and half the large-model trials then named the release.
- `cut_off` (D3): on 1 July a configuration commit lowered `max_tokens` from 400 to 120 with no release.
  From then on any reply that needs more is cut mid-sentence: care advice, and the summary a new patient gets.
- `group_rejected` (D4): from 27 June a litter check-up offer makes customers try to book four or more
  animals at once. The booking tool rejects that, as it always has (three animals at most; groups book by
  phone): a handful of customers asked before the offer and were refused the same way. Nothing is broken. About 2 conversations in 100, all along, have an unrelated timed-out call.
"""
import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

START = datetime(2026, 6, 1, tzinfo=timezone.utc)
DAYS = 50
RELEASES = ["1.1.0", "1.2.0", "1.3.0"]
ROLLOUT = {20: 0.2, 21: 0.4, 22: 0.6, 23: 0.8}  # share of conversations 1.2.0 served on each rollout day; all of them from day 24
HOTFIX_DAY, API_CHANGE_DAY, PARTNER_DAY, GROUP_DAY, CONFIG_DAY = 38, 14, 21, 26, 30
MODEL = "gpt-5.4-mini"
CLINICS = {"hbr-st": ("Harbour Street", "Portmere"), "hbr-sq": ("Harbour Square", "Portmere"), "mill-rd": ("Mill Road", "Ashby"), "millbrook": ("Millbrook Road", "Ashby"),
           "north-pk": ("North Park", "Portmere"), "elm": ("Elm Grove", "Ashby"), "station": ("Station Yard", "Tolworth"), "lakeside": ("Lakeside", "Tolworth"),
           "old-town": ("Old Town", "Portmere"), "west-end": ("West End", "Ashby")}
NEIGHBOUR = {"hbr-st": "hbr-sq", "hbr-sq": "hbr-st", "mill-rd": "millbrook", "millbrook": "mill-rd"}
BOOKED_INTO = {"hbr-st": "hbr-sq", "mill-rd": "millbrook"}  # the API's fault goes one way only
PETS = ["Biscuit", "Mochi", "Otis", "Luna", "Pepper", "Juniper", "Rollo", "Tansy", "Figgy", "Dex", "Nala", "Barley"]
SPECIES = ["cat", "dog", "rabbit", "guinea pig"]
REASONS = ["a booster vaccination", "a dental check", "a limp that has not cleared up", "an ear infection", "a yearly check-up", "an itchy skin problem"]
TOPICS = ["fasting before an operation", "settling a cat after a vaccination", "travelling with a nervous dog", "caring for stitches", "feeding after dental work"]
ADVICE = ["Please keep {pet} indoors and quiet for the rest of the day.", "Offer a small meal in the evening and fresh water at all times.", "Do not give any medicine that the vet has not prescribed.",
          "If {pet} is still unsettled after a day, ring the clinic and ask for the nurse.", "A warm, dark place to rest helps more than anything else.", "Check the area twice a day and keep it clean and dry.",
          "Bring any medicine {pet} already takes, in its packaging, to the appointment.", "Most animals are back to normal within two days.", "If you see swelling or bleeding, come in the same day; no appointment is needed.",
          "Keep other animals in the house away for the first evening.", "Withhold food from eight in the evening before the operation, but leave water out."]
SYSTEM_PROMPT = ("You are the appointment assistant for Fernhill Vets. Find the clinic the customer names, check availability, book, and confirm the clinic, "
                 "the time and the reference. At most three animals per appointment; larger groups book by phone.")


def iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


def phone(clinic: str) -> str:
    return f"01632 9600{10 + list(CLINICS).index(clinic)}"


@dataclass
class Case:
    external_id: str
    started: datetime
    day: int
    release: str
    kind: str  # book | advice | reschedule | hours | complaint | group | new_patient
    source: str
    pet: str
    species: str
    clinic: str  # the clinic the customer asked for
    booked: str | None = None  # the clinic the booking came back confirmed at
    animals: int = 1
    timeout: bool = False
    cut_off: bool = False

    @property
    def wrong_clinic(self) -> bool:
        return self.booked is not None and self.booked != self.clinic


def release_on(day: int, rng: random.Random) -> str:
    if day >= HOTFIX_DAY:
        return "1.3.0"
    if day in ROLLOUT:
        return "1.2.0" if rng.random() < ROLLOUT[day] else "1.1.0"
    return "1.2.0" if day > max(ROLLOUT) else "1.1.0"


def draw_case(rng: random.Random, external_id: str, started: datetime, day: int, partner: bool = False) -> Case:
    kind = "new_patient" if partner else rng.choices(["book", "advice", "reschedule", "hours"], [55, 12, 17, 16])[0]
    roll = rng.random()
    if not partner and day >= API_CHANGE_DAY + 2 and roll < 0.012:
        kind = "complaint"
    elif not partner and (roll < 0.057 if day >= GROUP_DAY else 0.012 <= roll < 0.017):  # before the offer a few customers asked too, and were refused the same way
        kind = "group"
    clinic = rng.choice(["hbr-st", "mill-rd"]) if kind == "complaint" else rng.choices(list(CLINICS), [14, 9, 12, 8, 12, 10, 9, 9, 9, 8])[0]
    case = Case(external_id, started, day, release_on(day, rng), kind, "partner-portal" if partner else rng.choices(["web", "app", "phone-transfer"], [50, 40, 10])[0],
                rng.choice(PETS), rng.choice(SPECIES), clinic, timeout=rng.random() < 0.02)
    fault = rng.random() < 0.7
    if kind in ("book", "new_patient"):
        case.booked = BOOKED_INTO[clinic] if day >= API_CHANGE_DAY and clinic in BOOKED_INTO and fault else clinic
    if kind == "group":
        case.animals = rng.randint(4, 7)
    return case


def to_record(c: Case, rng: random.Random) -> dict[str, Any]:
    """One session in the Kitaru JSONL contract: a root span, then model calls and tool calls."""
    name, city = CLINICS[c.clinic]
    max_tokens = 120 if c.day >= CONFIG_DAY else 400
    slot = iso(c.started.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=rng.randint(1, 9), hours=rng.choice([9, 10, 11, 14, 15, 16]), minutes=rng.choice([0, 20, 40])))
    reference = f"FV-{rng.randrange(100000, 999999)}"
    reason = rng.choice(REASONS)
    message = {"book": f"Hi, I'd like to book {c.pet}, my {c.species}, in for {reason} at your {name} clinic, sometime next week if possible.",
               "advice": f"What should I know about {rng.choice(TOPICS)}? {c.pet} is booked in at {name}.",
               "reschedule": f"I need to move {c.pet}'s appointment {reference} at {name} to another day.",
               "hours": f"When is the {name} clinic open on Saturdays?",
               "complaint": f"You booked {c.pet} in at {CLINICS[BOOKED_INTO[c.clinic]][0]} but I asked for {name}. I turned up at the wrong clinic!" if c.kind == "complaint" else "",
               "group": (f"I'd like to bring my litter of {c.animals} for the litter check-up offer at {name}. Can I book them all in together?" if c.day >= GROUP_DAY
                         else f"I have {c.animals} kittens that all need a first check at {name}. Can I book them all in together?"),
               "new_patient": f"Hello, I'm new to Fernhill Vets. I was sent by the rescue's portal and would like to register and book a first visit at {name}."}[c.kind]
    clock = c.started
    nodes: list[dict[str, Any]] = [{}]
    history: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": message}]

    def tick(seconds: float) -> tuple[str, str]:
        nonlocal clock
        begin, clock = clock, clock + timedelta(seconds=seconds)
        return iso(begin), iso(clock)

    def model_call(output: dict[str, Any], finish: str) -> None:
        begin, end = tick(rng.uniform(0.6, 2.4))
        tokens_in, tokens_out = 180 + 45 * len(history) + rng.randrange(40), max_tokens if finish == "length" else 20 + len(json.dumps(output)) // 4
        nodes.append({"index": len(nodes), "parent_index": 0, "links": [], "external_id": f"{c.external_id}-n{len(nodes)}", "trace_id": c.external_id,
                      "node_type": "llm_call", "name": "booking assistant turn", "status": "completed", "started_at": begin, "ended_at": end,
                      "input_text_selector": f"/{len(history) - 1}/content", "output_text_selector": "/0/content" if output.get("content") else None,
                      "system_prompt_selector": "/0/content", "reasoning_selectors": [], "inputs": list(history), "outputs": [output],
                      "requested_model": MODEL, "model": MODEL, "model_provider": "openai", "model_params": {"temperature": 0.2, "max_tokens": max_tokens},
                      "tokens": {"input_tokens": tokens_in, "output_tokens": tokens_out, "cached_input_tokens": 0, "cache_write_input_tokens": 0, "reasoning_tokens": 0},
                      "cost": f"{(tokens_in * 0.25 + tokens_out * 2.0) / 1_000_000:.6f}", "attributes": {"finish_reason": finish}, "metadata": {}})
        history.append(output)

    def tool(tool_name: str, args: dict[str, Any], result: dict[str, Any], error: str | None = None) -> None:
        model_call({"role": "assistant", "content": None, "tool_calls": [{"name": tool_name, "arguments": args}]}, "tool_calls")
        begin, end = tick(rng.uniform(4.0, 6.0) if error and "timed out" in error else rng.uniform(0.1, 0.7))
        nodes.append({"index": len(nodes), "parent_index": 0, "links": [], "external_id": f"{c.external_id}-n{len(nodes)}", "trace_id": c.external_id,
                      "node_type": "tool_call", "name": tool_name, "tool_name": tool_name, "status": "failed" if error else "completed", "error": error,
                      "started_at": begin, "ended_at": end, "reasoning_selectors": [], "inputs": args, "outputs": result, "attributes": {}, "metadata": {}})
        history.append({"role": "tool", "name": tool_name, "content": json.dumps(result)})

    def hit(clinic: str) -> dict[str, Any]:
        return {"clinic_id": clinic, "name": CLINICS[clinic][0], "city": CLINICS[clinic][1], "phone": phone(clinic)}

    def search() -> None:
        if c.timeout:
            tool("search_clinics", {"query": name}, {"error": "scheduling API timed out", "retryable": True}, error="scheduling API timed out")
        if c.clinic in NEIGHBOUR and c.day >= API_CHANGE_DAY and c.release != "1.3.0":  # the neighbour is listed first; the assistant asks again with the city
            tool("search_clinics", {"query": name}, {"clinics": [hit(NEIGHBOUR[c.clinic]), hit(c.clinic)]})
            tool("search_clinics", {"query": name, "city": city}, {"clinics": [hit(c.clinic)]})
        else:
            tool("search_clinics", {"query": name}, {"clinics": [hit(c.clinic)] + ([hit(NEIGHBOUR[c.clinic])] if c.clinic in NEIGHBOUR else [])})

    def book() -> None:
        tool("check_availability", {"clinic_id": c.clinic, "from": slot[:10]}, {"clinic_id": c.clinic, "slots": [slot]})
        if c.animals > 3:
            why = "at most 3 animals per appointment; group visits are booked by phone"
            tool("book_appointment", {"clinic_id": c.clinic, "pet": c.pet, "species": c.species, "slot": slot, "animals": c.animals}, {"status": 422, "error": why}, error=f"422: {why}")
        else:
            assert c.booked is not None
            tool("book_appointment", {"clinic_id": c.clinic, "pet": c.pet, "species": c.species, "slot": slot, "animals": c.animals},
                 {"booking_id": reference, "status": "confirmed", "clinic_id": c.booked, "clinic_name": CLINICS[c.booked][0], "slot": slot})

    when = f"{slot[:10]} at {slot[11:16]}"
    if c.kind == "book":
        search(); book()
        reply = f"All set: {c.pet} is booked in at Fernhill Vets {name} on {when}. Your reference is {reference}. Please arrive ten minutes early."
    elif c.kind == "group":
        search(); book()
        reply = f"I'm sorry, I can't book more than three animals into one appointment online. For a litter of {c.animals}, please ring {name} on {phone(c.clinic)} and they will arrange a group visit."
    elif c.kind == "advice":
        topic = message.split("about ")[1].split("?")[0]
        text = " ".join(rng.sample(ADVICE, rng.randint(6, 10))).format(pet=c.pet)
        tool("get_care_sheet", {"topic": topic}, {"topic": topic, "text": text})
        reply = f"Here is what our nurses advise on {topic}. {text} The team at {name} can answer anything else on {phone(c.clinic)}."
    elif c.kind == "reschedule":
        if c.timeout:
            tool("lookup_booking", {"booking_id": reference}, {"error": "scheduling API timed out", "retryable": True}, error="scheduling API timed out")
        tool("lookup_booking", {"booking_id": reference}, {"booking_id": reference, "clinic_id": c.clinic, "clinic_name": name, "pet": c.pet})
        tool("reschedule_appointment", {"booking_id": reference, "slot": slot}, {"booking_id": reference, "status": "moved", "slot": slot})
        reply = f"Done: {c.pet}'s appointment {reference} at {name} is now on {when}."
    elif c.kind == "hours":
        search()
        reply = f"Fernhill Vets {name} is open on Saturdays from 09:00 to 13:00. You can reach the clinic on {phone(c.clinic)}."
    elif c.kind == "complaint":
        other = BOOKED_INTO[c.clinic]
        tool("lookup_booking", {"booking_id": reference}, {"booking_id": reference, "clinic_id": other, "clinic_name": CLINICS[other][0], "pet": c.pet})
        reply = f"I'm very sorry. The booking {reference} is recorded at {CLINICS[other][0]}, not {name}. I have passed this to the clinic team, who will ring you today to put it right."
    else:  # new_patient: registration, then a booking
        owner = f"own_{rng.randrange(16**6):06x}"
        tool("register_owner", {"source": "partner-portal", "preferred_clinic": c.clinic}, {"owner_id": owner, "status": "created"})
        animals = [c.pet] + rng.sample([p for p in PETS if p != c.pet], rng.randint(0, 2))
        for animal in animals:
            tool("register_pet", {"owner_id": owner, "name": animal, "species": c.species}, {"pet_id": f"pet_{rng.randrange(16**6):06x}", "status": "created"})
            tool("request_records", {"owner_id": owner, "name": animal}, {"status": "requested", "from": "previous practice"})
        search(); book()
        tool("send_forms", {"owner_id": owner, "forms": ["consent", "history"]}, {"status": "sent"})
        reply = (f"Welcome to Fernhill Vets. I have registered you and {', '.join(animals)}, and asked your previous practice for the records. {c.pet} is booked in at Fernhill Vets {name} on {when}; "
                 f"your reference is {reference}. I have emailed a consent form and a history form: please fill both in before the visit, and bring any medicine in its packaging. "
                 f"A first visit takes about forty minutes. If you need to change anything, reply here or ring {name} on {phone(c.clinic)}.")
    room = (max_tokens - 20) * 4 - 60  # characters of reply that fit under the limit
    c.cut_off = len(reply) > room
    if c.cut_off:
        reply = reply[:room].rstrip(" .,;:")
    model_call({"role": "assistant", "content": reply}, "length" if c.cut_off else "stop")
    start, end = iso(c.started), iso(clock)
    nodes[0] = {"index": 0, "parent_index": None, "links": [], "external_id": f"{c.external_id}-root", "trace_id": c.external_id, "node_type": "span",
                "name": "booking conversation", "status": "completed", "started_at": start, "ended_at": end, "input_text_selector": "/message",
                "output_text_selector": "/reply", "reasoning_selectors": [], "inputs": {"message": message}, "outputs": {"reply": reply}, "attributes": {}, "metadata": {}}
    return {"status": "completed", "name": f"Booking: {c.pet}", "inputs": {"message": message}, "outputs": {"reply": reply}, "started_at": start, "ended_at": end,
            "external_id": c.external_id, "framework": "pydantic-ai", "metadata": {"source": c.source, "agent_release": c.release, "end_reason": "resolved"}, "nodes": nodes}


def build_history(seed: int, per_day: int, partner_per_day: int) -> list[tuple[Case, dict[str, Any]]]:
    rng = random.Random(seed)
    plan = []
    for day in range(DAYS):
        plan += [(day, s, False) for s in (rng.uniform(7 * 3600, 21 * 3600) for _ in range(per_day + rng.randrange(-5, 6)))]
        if day >= PARTNER_DAY:
            plan += [(day, s, True) for s in (rng.uniform(8 * 3600, 20 * 3600) for _ in range(partner_per_day + rng.randrange(-2, 3)))]
    out = []
    for number, (day, s, partner) in enumerate(sorted(plan), start=1):
        case = draw_case(rng, f"cl-{number:05d}", START + timedelta(days=day, seconds=s), day, partner)
        out.append((case, to_record(case, rng)))
    return out


def cost(record: dict[str, Any]) -> float:
    return sum(float(n.get("cost") or 0) for n in record["nodes"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["history"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20260601)
    ap.add_argument("--per-day", type=int, default=60)
    ap.add_argument("--partner-per-day", type=int, default=7)
    ap.add_argument("--plants", default=None, help="unused; accepted so sync_env.sh can call every world the same way")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    pairs = build_history(a.seed, a.per_day, a.partner_per_day)
    for release in RELEASES:
        (a.out / f"sessions-{release}.jsonl").write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for c, r in pairs if c.release == release))
    def ids(wanted) -> list[str]:
        return [c.external_id for c, _ in pairs if wanted(c)]
    def mean(days: range) -> float:
        costs = [cost(r) for c, r in pairs if c.day in days]
        return sum(costs) / len(costs)
    def failed(days: range) -> float:
        rows = [r for c, r in pairs if c.day in days]
        return sum(any(n.get("status") == "failed" for n in r["nodes"]) for r in rows) / len(rows)
    truth = {"snapshot_date": "2026-07-20", "sessions": len(pairs), "by_version": {v: sum(c.release == v for c, _ in pairs) for v in RELEASES},
             "planted": {"wrong_clinic": ids(lambda c: c.wrong_clinic), "wrong_clinic_after_hotfix": ids(lambda c: c.wrong_clinic and c.release == "1.3.0"),
                         "partner_referrals": ids(lambda c: c.kind == "new_patient"), "cut_off": ids(lambda c: c.cut_off), "group_rejected": ids(lambda c: c.kind == "group"),
                         "complaints": ids(lambda c: c.kind == "complaint"), "timeouts": ids(lambda c: c.timeout and c.kind in ("book", "group", "hours", "reschedule", "new_patient"))},
             "facts": {"api_change_date": iso(START + timedelta(days=API_CHANGE_DAY))[:10], "partner_first_date": iso(START + timedelta(days=PARTNER_DAY))[:10],
                       "group_offer_date": iso(START + timedelta(days=GROUP_DAY))[:10], "config_commit_date": iso(START + timedelta(days=CONFIG_DAY))[:10],
                       "release_1_2_0_rollout": [iso(START + timedelta(days=min(ROLLOUT)))[:10], iso(START + timedelta(days=max(ROLLOUT) + 1))[:10]], "release_1_3_0_date": iso(START + timedelta(days=HOTFIX_DAY))[:10],
                       "cost_per_conversation": {"days_13_to_19": round(mean(range(13, 20)), 6), "days_24_to_29": round(mean(range(24, 30)), 6)},
                       "share_with_failed_call": {"days_19_to_25": round(failed(range(19, 26)), 4), "days_26_to_49": round(failed(range(26, 50)), 4)},
                       "mean_cost": {k: round(sum(cost(r) for c, r in pairs if c.kind == k) / max(1, sum(c.kind == k for c, _ in pairs)), 6) for k in ("book", "new_patient", "advice")},
                       "mean_cost_ordinary_by_release": {v: round(sum(cost(r) for c, r in pairs if c.release == v and c.kind != "new_patient" and c.day < CONFIG_DAY) / max(1, sum(c.release == v and c.kind != "new_patient" and c.day < CONFIG_DAY for c, _ in pairs)), 6) for v in RELEASES[:2]}},
             "per_session": {c.external_id: {"started_at": r["started_at"], "release": c.release, "kind": c.kind, "source": c.source, "wrong_clinic": c.wrong_clinic, "cut_off": c.cut_off,
                                             "group_rejected": c.kind == "group", "timeout": c.timeout} for c, r in pairs}}
    (a.out / "ground_truth.json").write_text(json.dumps(truth, indent=1))
    print(json.dumps({"sessions": len(pairs), "by_version": truth["by_version"], "planted": {k: len(v) for k, v in truth["planted"].items()}, "facts": truth["facts"]}, indent=1))


if __name__ == "__main__":
    main()
