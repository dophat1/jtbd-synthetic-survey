"""
persona_survey.py
-----------------
Runs the 67-question satisfaction/importance survey for each persona
using the OpenAI API, then saves results to CSV or JSON.
 
Usage:
    python persona_survey.py --personas personas.json --out results.csv
    python persona_survey.py --personas personas.json --out results.json --format json
    python persona_survey.py --personas personas.json --out results.csv --limit 50 --batch 3
    python persona_survey.py --personas personas.json --out results.csv --runs 3  # 3x variance runs per persona
"""
 
import os, sys, json, time, csv, argparse, random
from openai import OpenAI
 
# ── Survey questions (1-67) ────────────────────────────────────────────────────
QUESTIONS = [
    "Ich spiele im Verein, weil ich Spaß haben will",
    "Ich spiele im Verein, weil ich mit meinen Freunden spielen will",
    "Ich spiele im Verein, weil ich neue Freunde finden will",
    "Ich spiele im Verein, weil ich regelmäßig spielen will",
    "Ich spiele im Verein, weil ich besser spielen will",
    "Ich spiele im Verein, weil ich Teil einer Gruppe sein will",
    "Ich spiele im Verein, weil ich Tricks lernen will",
    "Ich spiele im Verein, weil ich Wettbewerbe spielen will",
    "Ich spiele im Verein, weil ich Pokale/Preise gewinnen will",
    "Von meinem Trainer: mich respektvoll behandeln",
    "Von meinem Trainer: mir gegenüber aufmerksam sein",
    "Von meinem Trainer: mich für gute Leistung loben",
    "Von meinem Trainer: mir ehrliches Feedback geben",
    "Von meinem Trainer: mir klar zeigen, wie ich mich verbessern kann",
    "Von meinem Trainer: mich genauso wie meine Mitspieler behandeln",
    "Von meinem Trainer: Regeln im Training durchsetzen",
    "Von meinem Trainer: mich nicht bei Fehlern vor allen kritisieren",
    "Von meinem Trainer: dem Team zeigen, wie wir Spiele gewinnen",
    "Von meinem Trainer: sich nicht mit anderen Trainern widersprechen",
    "Von meinem Trainer: nicht seine schlechte Laune an mir auslassen",
    "Von meinem Trainer: mich nicht anschreien",
    "Von meinen Mitspielern: mich respektvoll behandeln",
    "Von meinen Mitspielern: mir Fehler verzeihen",
    "Von meinen Mitspielern: auch bei Niederlagen gute Laune zeigen",
    "Von meinen Mitspielern: mit mir gut zusammenspielen",
    "Von meinen Mitspielern: fair spielen",
    "Von meinen Mitspielern: gemeinsame Rituale pflegen",
    "Von meinen Mitspielern: Anerkennung für gute Aktionen geben",
    "Von meinen Mitspielern: Erfolge bejubeln",
    "Von meinen Mitspielern: Siege gemeinsam feiern",
    "Im Training: konzentriert trainieren",
    "Im Training: Technik verbessern",
    "Im Training: Tricks lernen",
    "Im Training: als Team Spielzüge lernen",
    "Im Training: aktive Spielzeit",
    "Im Training: Abwechslung zwischen Übungen",
    "Im Training: sehr wenig Wartezeit",
    "Im Training: Kondition aufbauen",
    "Im Training: Kraft aufbauen",
    "Bei Wettbewerben: möglichst viele Spiele gewinnen",
    "Bei Wettbewerben: möglichst wenig Spiele hoch verlieren",
    "Bei Wettbewerben: möglichst viele zählbare Erfolge",
    "Bei Wettbewerben: eine Aufstellung nach klaren Kriterien",
    "Bei Wettbewerben: in einem möglichst starken Team spielen",
    "Bei Wettbewerben: gegen Gegner auf gleichem Niveau spielen",
    "Bei Wettbewerben: schöne Trikots haben",
    "Bei Wettbewerben: Zuschauer aus meiner Familie",
    "Im Vereinsheim: nach dem Training zusammensitzen",
    "Im Vereinsheim: nach Heimspielen zusammensitzen",
    "Im Vereinsheim: Mannschaftssitzungen abhalten",
    "Im Vereinsheim: Vereinsfeiern",
    "Im Vereinsheim: Bewirtung durch einen Wirt",
    "Im Vereinsheim: vom Wirt freundlich behandelt werden",
    "Im Vereinsheim: ohne Wirt etwas zu trinken kaufen",
    "Im Vereinsheim: ohne Wirt etwas zu essen kaufen",
    "Im Vereinsheim: Sport im Fernsehen anschauen",
    "Im Vereinsheim: private Feiern machen",
    "Im Vereinsheim: einen Ort zum chillen",
    "Im Vereinsheim: analoge Spiele spielen",
    "Im Vereinsheim: E-Sports-Veranstaltungen",
    "Auf dem Vereinsgelände: anderen Mannschaften zuschauen",
    "Auf dem Vereinsgelände: Fußball mit Freunden spielen (Bolzen)",
    "Auf dem Vereinsgelände: andere Sportarten spielen",
    "Auf dem Vereinsgelände: vereinsinterne gemischte Turniere",
    "Bei Saisonwechsel: gemeinsame Feier mit meiner Mannschaft",
    "Bei Saisonwechsel: die gleichen Trainer behalten",
    "Bei Saisonwechsel: mit den gleichen Spielern bleiben",
]
 
SYSTEM_PROMPT = """You are a research simulation engine for a youth football (soccer) club study.
Your role is to realistically simulate how a specific child would answer a satisfaction and importance survey,
based on their full psychological and social profile.
 
Key behavioral rules:
- Introverted children (low extraversion) rate social/clubhouse questions lower in importance
- Neurotic children (high neuroticism) rate coach-related satisfaction lower when under stress
- Children with bullying experience rate teammate satisfaction significantly lower
- Highly agreeable children tend to give slightly higher satisfaction scores overall, but not uniformly
- Performance-focused family expectation raises importance of competition questions
- Low parent support + high stress = lower satisfaction across the board
- Recent match losses reduce competition satisfaction but may raise improvement importance
- Conscientiousness drives training-related importance scores up
- Openness drives variety/tricks/new-experiences importance up
 
Do NOT average everything out. Be differentiated. A child who is isolated from teammates
should rate teammate questions very differently from a child with strong teammate bonds.
 
Always respond with valid JSON only — no explanation, no markdown."""
 
 
def interpret_big_five(p: dict) -> str:
    """Convert raw Big Five scores into behavioral interpretation hints for the prompt."""
    bf = p["psychology_big_five"]
    traits = []
 
    o = bf["openness"]
    if o >= 70:
        traits.append("highly curious, loves variety, values learning tricks and new exercises")
    elif o <= 40:
        traits.append("prefers routine over novelty, not driven by learning new tricks")
 
    c = bf["conscientiousness"]
    if c >= 70:
        traits.append("disciplined, values structured training and fair rules strongly")
    elif c <= 40:
        traits.append("less focused on structure, may not care much about training quality details")
 
    e = bf["extraversion"]
    if e >= 70:
        traits.append("very social, places high importance on group events, clubhouse, team rituals")
    elif e <= 40:
        traits.append("introverted, low interest in social/clubhouse activities, prefers playing over socializing")
 
    a = bf["agreeableness"]
    if a >= 70:
        traits.append("cooperative, values fair play and respectful treatment highly")
    elif a <= 40:
        traits.append("competitive and self-focused, less concerned with team harmony")
 
    n = bf["neuroticism"]
    if n >= 70:
        traits.append("emotionally sensitive, stress amplifies dissatisfaction, especially with coaches and losses")
    elif n <= 40:
        traits.append("emotionally stable, not easily rattled by losses or social friction")
 
    return "; ".join(traits) if traits else "balanced personality with no extreme traits"
 
 
def interpret_recent_results(results: list) -> str:
    wins = results.count("win")
    losses = results.count("loss")
    draws = results.count("draw")
    if losses >= 3:
        return "mostly losing recently — competition satisfaction is likely low, improvement motivation may be high"
    elif wins >= 3:
        return "on a winning streak — competition satisfaction is elevated"
    elif losses >= 2 and wins >= 2:
        return "mixed results — neutral competition mood with some frustration"
    else:
        return "average recent form"
 
 
def build_prompt(batch: list[dict], scale: int, run_index: int = 0) -> str:
    persona_blocks = []
    for p in batch:
        recent_event = p["emotional_state"].get("recent_event", "none")
        results_summary = interpret_recent_results(p["emotional_state"]["recent_results"])
        big_five_interp = interpret_big_five(p)
 
        block = f"""PERSONA {p['persona_id']}:
- Age: {p['identity']['age']}, Team: {p['team_context']['age_group_team']}, Position: {p['team_context']['position']}
- Skill level: {p['team_context']['skill_level']}, Playing time: {p['team_context']['playing_time']}
- Coach relationship: {p['social_context']['coach_relationship']}
- Teammate relationship: {p['social_context']['teammate_relationship']}
- Bullying experience: {p['social_context']['bullying_experience']}
- Friendship importance: {p['social_context']['friendship_importance']}
- Peer influence: {p['social_context']['peer_influence']}
- Parent support: {p['family_context']['parent_support']}, Parent pressure: {p['family_context']['parent_pressure']}
- Sports expectation: {p['family_context']['sports_expectation']}
- Big Five — Openness:{p['psychology_big_five']['openness']} Conscientiousness:{p['psychology_big_five']['conscientiousness']} Extraversion:{p['psychology_big_five']['extraversion']} Agreeableness:{p['psychology_big_five']['agreeableness']} Neuroticism:{p['psychology_big_five']['neuroticism']}
- Personality interpretation: {big_five_interp}
- Current mood: {p['emotional_state']['current_mood']}, Stress level: {p['emotional_state']['stress_level']}/100
- Recent results summary: {results_summary}
- Recent notable event: {recent_event}
- Overall club satisfaction: {p['satisfaction']}/100"""
        persona_blocks.append(block)
 
    questions_text = "\n".join(f"Q{i+1}: {q}" for i, q in enumerate(QUESTIONS))
 
    # Variance instruction: nudges the model to produce slightly different responses
    # across runs for the same persona without changing persona meaning
    variance_nudge = (
        "Answer as if this is the child's authentic response on a typical day. "
        "Use natural human variability in how they express their ratings."
        if run_index == 0
        else f"Answer as if this child is filling out the survey on a different day (run {run_index+1}). "
             "Introduce small, realistic variation in scores — ±1 on some questions — "
             "as a real person would if asked twice. Core patterns should remain consistent."
    )
 
    return f"""For each persona below, answer all 67 survey questions with TWO integer scores on a 1-{scale} scale:
- satisfaction: how satisfied is this persona with this aspect right now (1=very dissatisfied, {scale}=very satisfied)
- importance: how important is this aspect to this persona (1=not important at all, {scale}=extremely important)
 
{variance_nudge}
 
Critical: ratings must reflect the persona's specific situation. A child with frequent bullying experience
should give LOW satisfaction on teammate questions. A child with low extraversion should give LOW importance
to clubhouse/social questions. Do not inflate scores uniformly.
 
{"".join(chr(10)+b for b in persona_blocks)}
 
SURVEY QUESTIONS:
{questions_text}
 
Respond ONLY with this JSON structure (no markdown, no text outside JSON):
{{
  "child_X": {{"Q1": {{"satisfaction": N, "importance": N}}, "Q2": {{"satisfaction": N, "importance": N}}, ...}},
  "child_Y": {{...}}
}}"""
 
 
def call_openai(client: OpenAI, batch: list[dict], scale: int, model: str,
                run_index: int = 0, retries: int = 3) -> dict:
    prompt = build_prompt(batch, scale, run_index)
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=8000,
                temperature=1.0,        # Higher temp for realistic human variance
                top_p=0.95,             # Slight nucleus sampling for diversity
                response_format={"type": "json_object"},
            )
            text = resp.choices[0].message.content
            return json.loads(text)
        except Exception as e:
            print(f"  ⚠ Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return {}
 
 
def save_csv(results: list[dict], path: str, scale: int, multi_run: bool = False):
    q_nums = list(range(1, len(QUESTIONS) + 1))
    base_headers = [
        "persona_id", "run_index", "age", "age_group_team", "position", "skill_level", "playing_time",
        "coach_relationship", "teammate_relationship", "bullying_experience",
        "friendship_importance", "parent_support", "parent_pressure",
        "sports_expectation", "overall_satisfaction", "current_mood", "stress_level",
    ]
    headers = base_headers + [f"Q{n}_satisfaction" for n in q_nums] + [f"Q{n}_importance" for n in q_nums]
 
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in results:
            p = r["persona"]
            a = r["answers"]
            row = {
                "persona_id":            p["persona_id"],
                "run_index":             r.get("run_index", 0),
                "age":                   p["identity"]["age"],
                "age_group_team":        p["team_context"]["age_group_team"],
                "position":              p["team_context"]["position"],
                "skill_level":           p["team_context"]["skill_level"],
                "playing_time":          p["team_context"]["playing_time"],
                "coach_relationship":    p["social_context"]["coach_relationship"],
                "teammate_relationship": p["social_context"]["teammate_relationship"],
                "bullying_experience":   p["social_context"]["bullying_experience"],
                "friendship_importance": p["social_context"]["friendship_importance"],
                "parent_support":        p["family_context"]["parent_support"],
                "parent_pressure":       p["family_context"]["parent_pressure"],
                "sports_expectation":    p["family_context"]["sports_expectation"],
                "overall_satisfaction":  p["satisfaction"],
                "current_mood":          p["emotional_state"]["current_mood"],
                "stress_level":          p["emotional_state"]["stress_level"],
            }
            for n in q_nums:
                q = a.get(f"Q{n}", {})
                row[f"Q{n}_satisfaction"] = q.get("satisfaction", "")
                row[f"Q{n}_importance"]   = q.get("importance", "")
            w.writerow(row)
 
 
def save_json(results: list[dict], path: str):
    out = []
    for r in results:
        p = r["persona"]
        out.append({
            "persona_id":     p["persona_id"],
            "run_index":      r.get("run_index", 0),
            "persona":        p,
            "survey_answers": r["answers"],
        })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
 
 
def run(personas_path: str, out_path: str, fmt: str, limit: int,
        batch_size: int, scale: int, model: str, api_key: str, runs: int = 1):
 
    with open(personas_path, encoding="utf-8") as f:
        all_personas = json.load(f)
 
    subset = all_personas[:limit] if limit else all_personas
    total  = len(subset)
    print(f"\n🚀 Processing {total} personas × {runs} run(s) = {total * runs} total responses")
    print(f"   batch={batch_size} | scale=1-{scale} | model={model} | temperature=1.0\n")
 
    client  = OpenAI(api_key=api_key)
    results = []
    done    = 0
    errors  = 0
    calls   = 0
 
    for run_idx in range(runs):
        if runs > 1:
            print(f"── Run {run_idx + 1}/{runs} ────────────────────────────────")
 
        for i in range(0, total, batch_size):
            batch = subset[i : i + batch_size]
            ids   = ", ".join(p["persona_id"] for p in batch)
            print(f"  [{done+1}-{min(done+batch_size, total * runs)}/{total * runs}] {ids} ...", end=" ", flush=True)
 
            raw = call_openai(client, batch, scale, model, run_index=run_idx)
            calls += 1
 
            for p in batch:
                pid     = p["persona_id"]
                answers = raw.get(pid) or raw.get(pid.replace("child_", ""))
                if answers:
                    results.append({"persona": p, "answers": answers, "run_index": run_idx})
                    print("✓", end=" ", flush=True)
                else:
                    errors += 1
                    print("✗", end=" ", flush=True)
                done += 1
 
            print()
 
            if done % 50 == 0:
                _save(results, out_path, fmt, scale)
                print(f"  💾 Checkpoint saved ({done} done)\n")
 
            time.sleep(0.3)
 
    _save(results, out_path, fmt, scale)
 
    print(f"\n✅ Done!")
    print(f"   Total responses    : {done}")
    print(f"   Successful         : {done - errors}")
    print(f"   Errors             : {errors}")
    print(f"   API calls made     : {calls}")
    print(f"   Output saved to    : {out_path}\n")
 
 
def _save(results, path, fmt, scale):
    if fmt == "json":
        save_json(results, path)
    else:
        save_csv(results, path, scale)
 
 
def main():
    parser = argparse.ArgumentParser(description="Run persona survey simulation with OpenAI")
    parser.add_argument("--personas", required=True,  help="Path to personas JSON file")
    parser.add_argument("--out",      required=True,  help="Output file path (e.g. results.csv)")
    parser.add_argument("--format",   default="csv",  choices=["csv", "json"], help="Output format (default: csv)")
    parser.add_argument("--limit",    type=int, default=0,  help="Max personas to process (0 = all)")
    parser.add_argument("--batch",    type=int, default=1,  help="Personas per API call (default: 1)")
    parser.add_argument("--scale",    type=int, default=10, choices=[5, 10], help="Rating scale 5 or 10 (default: 10)")
    parser.add_argument("--model",    default="gpt-4o-mini", help="OpenAI model (default: gpt-4o-mini)")
    parser.add_argument("--runs",     type=int, default=1,  help="Number of response runs per persona for variance (default: 1)")
    parser.add_argument("--api-key",  default="", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    args = parser.parse_args()
 
    api_key = args.api_key or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("❌ No API key. Use --api-key sk-... or set OPENAI_API_KEY environment variable.")
        sys.exit(1)
 
    run(
        personas_path = args.personas,
        out_path      = args.out,
        fmt           = args.format,
        limit         = args.limit,
        batch_size    = args.batch,
        scale         = args.scale,
        model         = args.model,
        api_key       = api_key,
        runs          = args.runs,
    )
 
if __name__ == "__main__":
    main()
 