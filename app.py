"""
app.py — JTBD Synthetic Survey · Streamlit GUI
------------------------------------------------
Four tabs:
  1. Generate  — AI-creates personas via OpenAI API
  2. Configure — Survey model/scale/batch settings
  3. Run       — Execute the survey with live progress
  4. Results   — Explore satisfaction × importance data

Run with:
    pip install streamlit plotly openai pandas
    streamlit run app.py
"""

import streamlit as st
import json, time, os, random, csv, io, re
from pathlib import Path

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="JTBD Synthetic Survey",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Shared state helpers ───────────────────────────────────────────────────────
def ss(key, default=None):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]

ss("personas", [])
ss("results", [])
ss("run_log", [])
ss("run_done", False)

# ── Survey questions ───────────────────────────────────────────────────────────
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

Q_SECTIONS = {
    "Motivation (Q1–9)":     list(range(0, 9)),
    "Coach (Q10–21)":        list(range(9, 21)),
    "Teammates (Q22–30)":    list(range(21, 30)),
    "Training (Q31–39)":     list(range(30, 39)),
    "Competition (Q40–47)":  list(range(39, 47)),
    "Clubhouse (Q48–60)":    list(range(47, 60)),
    "Grounds (Q61–64)":      list(range(60, 64)),
    "Season change (Q65–67)":list(range(64, 67)),
}

# ── Persona generation ─────────────────────────────────────────────────────────
PERSONA_SYSTEM = """You are a research data generator for a youth football (soccer) club study.
Generate realistic, psychologically coherent child personas using the Big Five personality model.

Rules for coherence:
- High neuroticism → higher stress level, lower satisfaction
- Low parent support + high parent pressure → lower satisfaction, higher stress
- Bullying experience frequent → lower teammate relationship quality, lower satisfaction
- High agreeableness → more positive social context
- Performance-focused family + high conscientiousness → more competition-focused
- Emotional state should be consistent with recent match results
- Age must be consistent with age_group_team (U7=5-7, U9=7-9, U11=9-11, U13=11-13, U15=13-15, U17=15-17)
- Big Five scores are 0-100 integers
- stress_level is 0-100 integer
- satisfaction is 0-100 integer

Respond ONLY with a valid JSON array — no markdown, no explanation."""


def build_persona_prompt(n: int, constraints: dict) -> str:
    age_groups = constraints.get("age_groups", ["U7", "U9", "U11", "U13"])
    countries  = constraints.get("countries", ["Germany"])
    roles      = constraints.get("roles", ["player"])
    existing   = constraints.get("existing_count", 0)

    return f"""Generate {n} unique youth football club member personas.

Constraints:
- Age groups to include (distribute evenly): {age_groups}
- Countries: {countries}
- Roles: {roles}
- Start persona_id numbering from: child_{existing}
- Make personas diverse: vary skill levels, social situations, family contexts, personalities
- Include a realistic mix of positive and negative contexts (not everyone is happy)

Each persona must follow this exact schema:
{{
  "persona_id": "child_N",
  "identity": {{"age": INT, "country": "STR", "team_role": "STR"}},
  "team_context": {{
    "age_group_team": "STR",
    "position": "STR (forward/midfielder/defender/goalkeeper)",
    "playing_time": "STR (high/medium/low)",
    "skill_level": "STR (high/medium/low)"
  }},
  "social_context": {{
    "coach_relationship": "STR (good/neutral/poor)",
    "teammate_relationship": "STR (integrated/neutral/isolated)",
    "peer_influence": "STR (high/medium/low)",
    "bullying_experience": "STR (none/occasional/frequent)",
    "friendship_importance": "STR (high/medium/low)"
  }},
  "family_context": {{
    "parent_support": "STR (high/medium/low)",
    "parent_pressure": "STR (high/medium/low)",
    "sports_expectation": "STR (performance_focused/balanced/recreational)"
  }},
  "psychology_big_five": {{
    "openness": INT,
    "conscientiousness": INT,
    "extraversion": INT,
    "agreeableness": INT,
    "neuroticism": INT
  }},
  "emotional_state": {{
    "recent_results": ["win/draw/loss", ...5 items],
    "current_mood": "STR (positive/neutral/negative)",
    "recent_event": "STR (brief description or none)",
    "stress_level": INT
  }},
  "satisfaction": INT
}}

Return a JSON array of {n} persona objects."""


def generate_personas_api(n: int, constraints: dict, api_key: str, model: str) -> list:
    """Call OpenAI API to generate personas."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = build_persona_prompt(n, constraints)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            temperature=1.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": PERSONA_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
        )
        text = resp.choices[0].message.content.strip()
        # Strip any accidental markdown fences
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
        parsed = json.loads(text)
        # The model may wrap the array in a key — unwrap it
        if isinstance(parsed, dict):
            parsed = next(iter(parsed.values()))
        return parsed if isinstance(parsed, list) else []
    except Exception as e:
        st.error(f"Generation failed: {e}")
        return []


# ── Survey execution ───────────────────────────────────────────────────────────
def interpret_big_five(p: dict) -> str:
    bf = p["psychology_big_five"]
    traits = []
    if bf["openness"] >= 70:
        traits.append("highly curious, loves variety and learning tricks")
    elif bf["openness"] <= 40:
        traits.append("prefers routine, not driven by novelty")
    if bf["conscientiousness"] >= 70:
        traits.append("disciplined, values structured training and fair rules")
    elif bf["conscientiousness"] <= 40:
        traits.append("less focused on structure and training quality")
    if bf["extraversion"] >= 70:
        traits.append("very social, places high value on group events and team rituals")
    elif bf["extraversion"] <= 40:
        traits.append("introverted, low interest in social/clubhouse activities")
    if bf["agreeableness"] >= 70:
        traits.append("cooperative, values fair play and respectful treatment")
    elif bf["agreeableness"] <= 40:
        traits.append("competitive and self-focused, less concerned with team harmony")
    if bf["neuroticism"] >= 70:
        traits.append("emotionally sensitive, stress amplifies dissatisfaction with coaches and losses")
    elif bf["neuroticism"] <= 40:
        traits.append("emotionally stable, not easily rattled by losses or social friction")
    return "; ".join(traits) if traits else "balanced personality"


def interpret_results(results: list) -> str:
    wins   = results.count("win")
    losses = results.count("loss")
    if losses >= 3:
        return "mostly losing — competition satisfaction low, improvement motivation may be high"
    elif wins >= 3:
        return "winning streak — competition satisfaction elevated"
    elif losses >= 2 and wins >= 2:
        return "mixed results — neutral mood with some frustration"
    return "average recent form"


SURVEY_SYSTEM = """You are a research simulation engine for a youth football (soccer) club study.
Simulate how a specific child answers a satisfaction/importance survey based on their full psychological profile.

Behavioral rules:
- Introverted children (low extraversion) rate social/clubhouse questions lower in importance
- Neurotic children (high neuroticism) rate coach-related satisfaction lower when under stress
- Children with bullying experience rate teammate satisfaction significantly lower
- Highly agreeable children give slightly higher satisfaction but NOT uniformly
- Performance-focused family expectation raises importance of competition questions
- Low parent support + high stress = lower satisfaction across the board
- Recent losses reduce competition satisfaction but may raise improvement importance
- Conscientiousness drives training-related importance scores up
- Openness drives variety/tricks/new-experiences importance up

Do NOT average everything out. Be psychologically differentiated.
Always respond with valid JSON only — no markdown."""


def build_survey_prompt(persona: dict, scale: int, run_index: int) -> str:
    p = persona
    variance = (
        "Answer as if this is the child's authentic response on a typical day."
        if run_index == 0 else
        f"This is survey run {run_index+1}. Introduce small realistic variation (±1 on some questions) "
        "as a real person would if asked on a different day. Core patterns must stay consistent."
    )
    questions_text = "\n".join(f"Q{i+1}: {q}" for i, q in enumerate(QUESTIONS))
    return f"""For the persona below, answer all 67 survey questions with TWO integer scores on a 1-{scale} scale:
- satisfaction: how satisfied is this persona with this aspect (1=very dissatisfied, {scale}=very satisfied)
- importance: how important is this aspect (1=not important, {scale}=extremely important)

{variance}

PERSONA {p['persona_id']}:
- Age: {p['identity']['age']}, Team: {p['team_context']['age_group_team']}, Position: {p['team_context']['position']}
- Skill: {p['team_context']['skill_level']}, Playing time: {p['team_context']['playing_time']}
- Coach relationship: {p['social_context']['coach_relationship']}
- Teammate relationship: {p['social_context']['teammate_relationship']}
- Bullying: {p['social_context']['bullying_experience']}, Friendship importance: {p['social_context']['friendship_importance']}
- Parent support: {p['family_context']['parent_support']}, Pressure: {p['family_context']['parent_pressure']}
- Sports expectation: {p['family_context']['sports_expectation']}
- Big Five — O:{p['psychology_big_five']['openness']} C:{p['psychology_big_five']['conscientiousness']} E:{p['psychology_big_five']['extraversion']} A:{p['psychology_big_five']['agreeableness']} N:{p['psychology_big_five']['neuroticism']}
- Personality: {interpret_big_five(p)}
- Mood: {p['emotional_state']['current_mood']}, Stress: {p['emotional_state']['stress_level']}/100
- Recent results: {interpret_results(p['emotional_state']['recent_results'])}
- Recent event: {p['emotional_state'].get('recent_event', 'none')}
- Overall satisfaction: {p['satisfaction']}/100

QUESTIONS:
{questions_text}

Respond ONLY with this JSON (no markdown):
{{"{p['persona_id']}": {{"Q1": {{"satisfaction": N, "importance": N}}, "Q2": {{"satisfaction": N, "importance": N}}, ...}}}}"""


def run_survey_persona(persona: dict, scale: int, model: str, api_key: str, run_index: int) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    prompt = build_survey_prompt(persona, scale, run_index)
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SURVEY_SYSTEM},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=8000,
                temperature=1.0,
                top_p=0.95,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
    return {}


# ── Results helpers ────────────────────────────────────────────────────────────
def results_to_df(results: list, scale: int):
    import pandas as pd
    rows = []
    for r in results:
        p = r["persona"]
        a = r["answers"]
        row = {
            "persona_id":            p["persona_id"],
            "run_index":             r.get("run_index", 0),
            "age":                   p["identity"]["age"],
            "age_group":             p["team_context"]["age_group_team"],
            "position":              p["team_context"]["position"],
            "skill_level":           p["team_context"]["skill_level"],
            "coach_relationship":    p["social_context"]["coach_relationship"],
            "teammate_relationship": p["social_context"]["teammate_relationship"],
            "bullying":              p["social_context"]["bullying_experience"],
            "parent_support":        p["family_context"]["parent_support"],
            "current_mood":          p["emotional_state"]["current_mood"],
            "stress_level":          p["emotional_state"]["stress_level"],
            "overall_satisfaction":  p["satisfaction"],
        }
        for i, q in enumerate(QUESTIONS):
            ans = a.get(f"Q{i+1}", {})
            row[f"Q{i+1}_sat"] = ans.get("satisfaction", None)
            row[f"Q{i+1}_imp"] = ans.get("importance", None)
        rows.append(row)
    return pd.DataFrame(rows)


def results_to_csv_bytes(results: list, scale: int) -> bytes:
    df = results_to_df(results, scale)
    return df.to_csv(index=False).encode("utf-8")


def results_to_json_bytes(results: list) -> bytes:
    out = [{"persona_id": r["persona"]["persona_id"], "run_index": r.get("run_index", 0),
            "persona": r["persona"], "survey_answers": r["answers"]} for r in results]
    return json.dumps(out, indent=2, ensure_ascii=False).encode("utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; max-width: 900px; }
    h1 { font-size: 1.4rem !important; font-weight: 600; }
    .stTabs [data-baseweb="tab"] { font-size: 0.875rem; }
    .metric-row { display: flex; gap: 12px; margin-bottom: 1rem; }
    .metric-box { flex: 1; background: #f8f8f8; border-radius: 8px; padding: 12px 16px; }
    .metric-box .label { font-size: 12px; color: #888; margin: 0; }
    .metric-box .value { font-size: 22px; font-weight: 600; margin: 0; }
    .log-box { background: #1a1a1a; color: #aef; font-family: monospace;
               font-size: 12px; padding: 10px; border-radius: 6px;
               height: 180px; overflow-y: auto; white-space: pre-wrap; }
    .persona-card { border: 1px solid #e8e8e8; border-radius: 8px;
                    padding: 12px 16px; margin-bottom: 8px; font-size: 13px; }
    .tag { display: inline-block; font-size: 11px; padding: 2px 8px;
           border-radius: 99px; margin-right: 4px; font-weight: 500; }
    .tag-green  { background: #e6f4ea; color: #2d7a4f; }
    .tag-red    { background: #fde8e8; color: #c0392b; }
    .tag-amber  { background: #fef3e2; color: #a0522d; }
    .tag-blue   { background: #e8f0fe; color: #1a56c4; }
    .tag-gray   { background: #f0f0f0; color: #555; }
</style>
""", unsafe_allow_html=True)

st.markdown("## ⚽ JTBD Synthetic Survey")
st.caption("Generate personas · Configure survey · Run · Analyse results")

tab_gen, tab_cfg, tab_run, tab_res = st.tabs([
    "🧬 Generate personas",
    "⚙️ Configure survey",
    "▶️ Run",
    "📊 Results",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — GENERATE
# ══════════════════════════════════════════════════════════════════════════════
with tab_gen:
    st.markdown("### Generate personas with AI")
    st.caption("GPT generates psychologically coherent personas based on your constraints.")

    col1, col2 = st.columns([1, 1])

    with col1:
        gen_api_key = st.text_input(
            "OpenAI API key", type="password",
            value=os.getenv("OPENAI_API_KEY", ""),
            help="Needed to call OpenAI for persona generation",
        )
        gen_model = st.selectbox(
            "Model",
            ["gpt-4o-mini", "gpt-4o"],
            help="gpt-4o-mini is fast and cheap; gpt-4o gives richer personas",
        )
        n_personas = st.number_input("Number of personas to generate", min_value=1, max_value=50, value=10)

    with col2:
        age_groups = st.multiselect(
            "Age groups to include",
            ["U7", "U9", "U11", "U13", "U15", "U17"],
            default=["U7", "U9", "U11", "U13"],
        )
        countries = st.multiselect(
            "Countries",
            ["Germany", "Austria", "Switzerland", "Netherlands", "France"],
            default=["Germany"],
        )
        roles = st.multiselect(
            "Team roles",
            ["player", "goalkeeper"],
            default=["player"],
        )

    st.divider()

    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
    with col_btn1:
        do_generate = st.button("✨ Generate", type="primary", use_container_width=True)
    with col_btn2:
        do_clear = st.button("🗑️ Clear all", use_container_width=True)
    with col_btn3:
        if st.session_state.personas:
            persona_json = json.dumps(st.session_state.personas, indent=2, ensure_ascii=False)
            st.download_button(
                "💾 Download personas.json",
                data=persona_json.encode("utf-8"),
                file_name="personas.json",
                mime="application/json",
                use_container_width=True,
            )

    if do_clear:
        st.session_state.personas = []
        st.rerun()

    if do_generate:
        if not gen_api_key:
            st.error("Please enter your OpenAI API key.")
        elif not age_groups:
            st.error("Select at least one age group.")
        else:
            constraints = {
                "age_groups": age_groups,
                "countries": countries,
                "roles": roles,
                "existing_count": len(st.session_state.personas),
            }
            with st.spinner(f"Generating {n_personas} personas with {gen_model}..."):
                new_personas = generate_personas_api(n_personas, constraints, gen_api_key, gen_model)
            if new_personas:
                st.session_state.personas.extend(new_personas)
                st.success(f"✅ Generated {len(new_personas)} personas — total: {len(st.session_state.personas)}")
            else:
                st.error("No personas returned. Check your API key and try again.")

    # ── Preview ───────────────────────────────────────────────────────────────
    if st.session_state.personas:
        st.markdown(f"### Persona preview ({len(st.session_state.personas)} total)")

        # Upload existing file to add to pool
        uploaded = st.file_uploader("Or upload an existing personas.json to add to the pool", type="json")
        if uploaded:
            try:
                loaded = json.load(uploaded)
                if isinstance(loaded, list):
                    # avoid duplicates by persona_id
                    existing_ids = {p["persona_id"] for p in st.session_state.personas}
                    added = [p for p in loaded if p["persona_id"] not in existing_ids]
                    st.session_state.personas.extend(added)
                    st.success(f"Added {len(added)} personas from file.")
                    st.rerun()
            except Exception as e:
                st.error(f"Could not parse file: {e}")

        for i, p in enumerate(st.session_state.personas):
            bf = p["psychology_big_five"]
            mood_tag = (
                "tag-green" if p["emotional_state"]["current_mood"] == "positive" else
                "tag-red"   if p["emotional_state"]["current_mood"] == "negative" else
                "tag-gray"
            )
            bully_tag = (
                "tag-red"   if p["social_context"]["bullying_experience"] == "frequent" else
                "tag-amber" if p["social_context"]["bullying_experience"] == "occasional" else
                "tag-green"
            )
            with st.expander(
                f"**{p['persona_id']}** — {p['identity']['age']}y · {p['team_context']['age_group_team']} · "
                f"{p['team_context']['position']} · satisfaction {p['satisfaction']}/100"
            ):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown("**Identity & Team**")
                    st.write(f"Age: {p['identity']['age']} | Country: {p['identity']['country']}")
                    st.write(f"Position: {p['team_context']['position']}")
                    st.write(f"Skill: {p['team_context']['skill_level']} | Time: {p['team_context']['playing_time']}")
                with c2:
                    st.markdown("**Social & Family**")
                    st.write(f"Coach: {p['social_context']['coach_relationship']}")
                    st.write(f"Teammates: {p['social_context']['teammate_relationship']}")
                    st.write(f"Bullying: {p['social_context']['bullying_experience']}")
                    st.write(f"Parent support: {p['family_context']['parent_support']}")
                    st.write(f"Pressure: {p['family_context']['parent_pressure']}")
                with c3:
                    st.markdown("**Big Five**")
                    bf_labels = ["O", "C", "E", "A", "N"]
                    bf_vals   = [bf["openness"], bf["conscientiousness"], bf["extraversion"],
                                 bf["agreeableness"], bf["neuroticism"]]
                    for lbl, val in zip(bf_labels, bf_vals):
                        st.progress(val / 100, text=f"{lbl}: {val}")

                col_del, _ = st.columns([1, 5])
                with col_del:
                    if st.button("Remove", key=f"del_{i}"):
                        st.session_state.personas.pop(i)
                        st.rerun()
    else:
        st.info("No personas yet. Generate some above or upload a personas.json file.")
        uploaded = st.file_uploader("Upload personas.json", type="json")
        if uploaded:
            try:
                loaded = json.load(uploaded)
                if isinstance(loaded, list):
                    st.session_state.personas = loaded
                    st.success(f"Loaded {len(loaded)} personas.")
                    st.rerun()
            except Exception as e:
                st.error(f"Could not parse file: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — CONFIGURE SURVEY
# ══════════════════════════════════════════════════════════════════════════════
with tab_cfg:
    st.markdown("### Survey configuration")

    col1, col2 = st.columns(2)
    with col1:
        survey_api_key = st.text_input(
            "OpenAI API key", type="password",
            value=os.getenv("OPENAI_API_KEY", ""),
            key="survey_api_key",
        )
        survey_model = st.selectbox(
            "Model",
            ["gpt-4o-mini", "gpt-4o"],
            key="survey_model",
        )
        survey_scale = st.selectbox(
            "Rating scale",
            [10, 5],
            format_func=lambda x: f"1–{x}",
            key="survey_scale",
        )

    with col2:
        survey_runs = st.number_input(
            "Runs per persona",
            min_value=1, max_value=5, value=1,
            help="Each run produces a slightly different response set, simulating different days",
            key="survey_runs",
        )
        survey_limit = st.number_input(
            "Limit personas (0 = all)",
            min_value=0, value=0,
            key="survey_limit",
        )
        survey_delay = st.slider(
            "Delay between calls (s)",
            min_value=0.0, max_value=2.0, value=0.3, step=0.1,
            key="survey_delay",
        )

    st.divider()
    st.markdown("**Estimated cost**")
    n_p = len(st.session_state.personas)
    lim = st.session_state.get("survey_limit", 0)
    eff = min(n_p, lim) if lim else n_p
    runs = st.session_state.get("survey_runs", 1)
    total_calls = eff * runs
    # rough estimate: ~2k tokens in, ~1k out per call, gpt-4o-mini pricing
    est_cost = total_calls * 0.0015
    st.info(
        f"{eff} personas × {runs} run(s) = **{total_calls} API calls** · "
        f"Estimated cost: **~${est_cost:.3f}** (gpt-4o-mini)"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — RUN
# ══════════════════════════════════════════════════════════════════════════════
with tab_run:
    st.markdown("### Run survey")

    personas = st.session_state.personas
    api_key  = st.session_state.get("survey_api_key", "")
    model    = st.session_state.get("survey_model", "gpt-4o-mini")
    scale    = st.session_state.get("survey_scale", 10)
    runs     = st.session_state.get("survey_runs", 1)
    limit    = st.session_state.get("survey_limit", 0)
    delay    = st.session_state.get("survey_delay", 0.3)

    subset = personas[:limit] if limit else personas
    total  = len(subset) * runs

    if not personas:
        st.warning("No personas loaded. Go to the Generate tab first.")
    elif not api_key:
        st.warning("No OpenAI API key. Go to the Configure tab.")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Personas", len(subset))
        col2.metric("Total responses", total)
        col3.metric("Existing results", len(st.session_state.results))

        col_start, col_reset = st.columns([1, 1])
        with col_start:
            start = st.button("▶️ Start run", type="primary", use_container_width=True,
                              disabled=st.session_state.run_done and len(st.session_state.results) >= total)
        with col_reset:
            if st.button("🔄 Reset results", use_container_width=True):
                st.session_state.results = []
                st.session_state.run_log = []
                st.session_state.run_done = False
                st.rerun()

        progress_bar  = st.progress(0)
        status_text   = st.empty()
        log_container = st.empty()

        if start:
            st.session_state.results = []
            st.session_state.run_log = []
            st.session_state.run_done = False
            done = 0
            errors = 0

            for run_idx in range(runs):
                for p in subset:
                    pid = p["persona_id"]
                    status_text.markdown(
                        f"**Processing** `{pid}` — run {run_idx+1}/{runs} "
                        f"({done+1}/{total})"
                    )
                    raw = run_survey_persona(p, scale, model, api_key, run_idx)
                    answers = raw.get(pid)
                    if answers:
                        st.session_state.results.append({
                            "persona": p,
                            "answers": answers,
                            "run_index": run_idx,
                        })
                        st.session_state.run_log.append(f"✓ {pid} run={run_idx}")
                    else:
                        errors += 1
                        st.session_state.run_log.append(f"✗ {pid} run={run_idx} — no data")
                    done += 1
                    progress_bar.progress(done / total)
                    log_container.code(
                        "\n".join(st.session_state.run_log[-12:]),
                        language=None,
                    )
                    time.sleep(delay)

            st.session_state.run_done = True
            status_text.success(
                f"✅ Done — {done - errors}/{done} successful, {errors} errors"
            )

        elif st.session_state.run_log:
            log_container.code("\n".join(st.session_state.run_log[-12:]), language=None)
            progress_bar.progress(
                min(len(st.session_state.results) / max(total, 1), 1.0)
            )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — RESULTS
# ══════════════════════════════════════════════════════════════════════════════
with tab_res:
    results = st.session_state.results
    scale   = st.session_state.get("survey_scale", 10)

    if not results:
        st.info("No results yet. Run the survey first.")
    else:
        import pandas as pd

        df = results_to_df(results, scale)

        # ── Overview metrics ──────────────────────────────────────────────────
        sat_cols = [f"Q{i+1}_sat" for i in range(len(QUESTIONS))]
        imp_cols = [f"Q{i+1}_imp" for i in range(len(QUESTIONS))]
        avg_sat  = df[sat_cols].mean().mean()
        avg_imp  = df[imp_cols].mean().mean()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Responses", len(results))
        c2.metric("Unique personas", df["persona_id"].nunique())
        c3.metric("Avg satisfaction", f"{avg_sat:.1f}/{scale}")
        c4.metric("Avg importance",   f"{avg_imp:.1f}/{scale}")

        st.divider()

        # ── Filters ───────────────────────────────────────────────────────────
        st.markdown("### Filters")
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            age_opts = ["All"] + sorted(df["age_group"].unique().tolist())
            f_age = st.selectbox("Age group", age_opts)
        with fc2:
            mood_opts = ["All"] + sorted(df["current_mood"].unique().tolist())
            f_mood = st.selectbox("Mood", mood_opts)
        with fc3:
            coach_opts = ["All"] + sorted(df["coach_relationship"].unique().tolist())
            f_coach = st.selectbox("Coach relationship", coach_opts)
        with fc4:
            bully_opts = ["All"] + sorted(df["bullying"].unique().tolist())
            f_bully = st.selectbox("Bullying experience", bully_opts)

        fdf = df.copy()
        if f_age   != "All": fdf = fdf[fdf["age_group"]          == f_age]
        if f_mood  != "All": fdf = fdf[fdf["current_mood"]        == f_mood]
        if f_coach != "All": fdf = fdf[fdf["coach_relationship"]  == f_coach]
        if f_bully != "All": fdf = fdf[fdf["bullying"]            == f_bully]

        st.caption(f"{len(fdf)} responses after filtering")

        # ── Section averages ──────────────────────────────────────────────────
        st.markdown("### Average scores by section")
        section_rows = []
        for section, idxs in Q_SECTIONS.items():
            s_cols = [f"Q{i+1}_sat" for i in idxs]
            i_cols = [f"Q{i+1}_imp" for i in idxs]
            avg_s = fdf[s_cols].mean().mean()
            avg_i = fdf[i_cols].mean().mean()
            gap   = avg_i - avg_s
            section_rows.append({
                "Section": section,
                "Avg satisfaction": round(avg_s, 2),
                "Avg importance":   round(avg_i, 2),
                "Gap (imp − sat)":  round(gap, 2),
            })
        sec_df = pd.DataFrame(section_rows).sort_values("Gap (imp − sat)", ascending=False)
        st.dataframe(sec_df, use_container_width=True, hide_index=True)

        # ── Top gap questions ─────────────────────────────────────────────────
        st.markdown("### Top 15 questions by importance–satisfaction gap")
        gap_rows = []
        for i, q in enumerate(QUESTIONS):
            s_col = f"Q{i+1}_sat"
            i_col = f"Q{i+1}_imp"
            if s_col in fdf.columns and i_col in fdf.columns:
                avg_s = fdf[s_col].mean()
                avg_i = fdf[i_col].mean()
                gap_rows.append({
                    "Q":             f"Q{i+1}",
                    "Question":      q[:60] + ("…" if len(q) > 60 else ""),
                    "Satisfaction":  round(avg_s, 2),
                    "Importance":    round(avg_i, 2),
                    "Gap":           round(avg_i - avg_s, 2),
                })
        gap_df = pd.DataFrame(gap_rows).sort_values("Gap", ascending=False).head(15)
        st.dataframe(gap_df, use_container_width=True, hide_index=True)

        # ── Scatter chart ─────────────────────────────────────────────────────
        st.markdown("### Satisfaction × Importance scatter (per question)")
        try:
            import plotly.express as px
            all_gap = []
            for i, q in enumerate(QUESTIONS):
                s_col = f"Q{i+1}_sat"
                i_col = f"Q{i+1}_imp"
                if s_col in fdf.columns:
                    all_gap.append({
                        "Question": f"Q{i+1}: {q[:40]}",
                        "Satisfaction": round(fdf[s_col].mean(), 2),
                        "Importance":   round(fdf[i_col].mean(), 2),
                        "Section": next((s for s, idxs in Q_SECTIONS.items() if i in idxs), "Other"),
                    })
            scatter_df = pd.DataFrame(all_gap)
            fig = px.scatter(
                scatter_df,
                x="Satisfaction", y="Importance",
                color="Section", hover_name="Question",
                range_x=[0, scale], range_y=[0, scale],
                width=800, height=500,
                title="Satisfaction vs Importance per question (average across filtered personas)",
            )
            fig.add_shape(type="line", x0=0, y0=0, x1=scale, y1=scale,
                          line=dict(dash="dash", color="gray", width=1))
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.warning("Install plotly for the scatter chart: `pip install plotly`")

        # ── Raw data ──────────────────────────────────────────────────────────
        with st.expander("Raw data table"):
            display_cols = ["persona_id", "run_index", "age_group", "position",
                            "coach_relationship", "bullying", "current_mood",
                            "overall_satisfaction"] + sat_cols[:67] + imp_cols[:67]
            st.dataframe(fdf[display_cols], use_container_width=True, hide_index=True)

        # ── Export ────────────────────────────────────────────────────────────
        st.divider()
        st.markdown("### Export")
        col_csv, col_json, col_personas = st.columns(3)
        with col_csv:
            st.download_button(
                "📥 Download results.csv",
                data=results_to_csv_bytes(results, scale),
                file_name="results.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_json:
            st.download_button(
                "📥 Download results.json",
                data=results_to_json_bytes(results),
                file_name="results.json",
                mime="application/json",
                use_container_width=True,
            )
        with col_personas:
            st.download_button(
                "📥 Download personas.json",
                data=json.dumps(st.session_state.personas, indent=2, ensure_ascii=False).encode(),
                file_name="personas.json",
                mime="application/json",
                use_container_width=True,
            )