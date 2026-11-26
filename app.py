from dataclasses import replace
from pathlib import Path

import streamlit as st

from jobhelper import (
    DEMO_CHECK, DEMO_JOBS, DEMO_SKILLS, DEMO_SOURCES, STATUSES,
    Application, Tracker, duplicate_candidates, match_skills, new_application, search_demo,
)


st.set_page_config(page_title="JobHelper", page_icon="🗂", layout="wide")
st.title("JobHelper")
st.caption("Compare your skills with a job description and keep track of applications locally.")

with st.sidebar:
    st.header("Workspace")
    demo = st.radio("Data mode", ("Demo", "My applications")) == "Demo"
    st.caption("Demo changes reset when you close the session." if demo else "Applications are stored in a local SQLite file.")

if demo:
    if "demo_records" not in st.session_state:
        st.session_state.demo_records = [
            Application(index, company, title, description, status, "2026-01-15")
            for index, (company, title, description, status) in enumerate(DEMO_JOBS, 1)
        ]
    records = st.session_state.demo_records
else:
    tracker = Tracker(Path(__file__).resolve().parent / "data" / "applications.sqlite3")
    records = tracker.list()

prefix = "demo" if demo else "local"
draft_keys = [f"{prefix}_{field}" for field in ("company", "title", "description")]
defaults = DEMO_CHECK if demo else ("", "", "")
for key, value in zip(draft_keys, defaults):
    st.session_state.setdefault(key, value)

search_tab, match_tab, tracker_tab = st.tabs(("Job search demo", "Match a job", "Application tracker"))

with search_tab:
    st.subheader("Search sample postings")
    st.info("Simulated search. All postings are fictional. Job boards are not contacted.")
    with st.form("sample_search"):
        filters = st.columns(3)
        source = filters[0].selectbox("Source", ("All sources", *DEMO_SOURCES), index=1)
        query = filters[1].text_input("Keywords", placeholder="Data Engineer")
        location = filters[2].text_input("Location", placeholder="Berlin")
        if st.form_submit_button("Search sample jobs", type="primary"):
            st.session_state.sample_filters = (source, query, location)

    results = search_demo(*st.session_state.get("sample_filters", ("StepStone", "", "")))
    st.caption(f"{len(results)} sample results")
    for index, posting in enumerate(results):
        with st.container(border=True):
            info, action = st.columns([4, 1], vertical_alignment="center")
            info.subheader(posting.title)
            info.text(f"{posting.company} · {posting.location} · {posting.source} (simulated)")
            info.text(posting.description)
            if action.button("Use in demo", key=f"sample_{index}", disabled=not demo):
                st.session_state.update(dict(zip(draft_keys, (posting.company, posting.title, posting.description))))
                st.success("Sample copied. Open Match a job to review it.")
    if not demo:
        st.caption("Switch to Demo mode to copy a sample into the matcher.")

with match_tab:
    st.subheader("Compare a job with your skills")
    inputs, analysis = st.columns([3, 2])
    company = inputs.text_input("Company", key=draft_keys[0])
    title = inputs.text_input("Job title", key=draft_keys[1])
    description = inputs.text_area("Job description", key=draft_keys[2], height=140)
    skills = inputs.text_input("Your skills (comma-separated)", value=DEMO_SKILLS if demo else "", key=f"{prefix}_skills")
    match = match_skills(skills, description)
    if description.strip() and (match.matched or match.unmentioned):
        analysis.metric("Listed skills mentioned", f"{match.percent}%")
        analysis.text("Matched: " + ", ".join(match.matched) if match.matched else "Matched: None")
        analysis.text("Not mentioned: " + ", ".join(match.unmentioned) if match.unmentioned else "Not mentioned: None")
        analysis.caption("Keyword overlap only. Review the full job description before applying.")

    duplicates = duplicate_candidates(company, title, records)
    if duplicates:
        analysis.warning("Possible duplicate at the same company.")
        for record in duplicates:
            analysis.text(f"{record.title} · {record.status}")
    confirmed = inputs.checkbox("Save as a separate opening", key=f"{prefix}_duplicate_override") if duplicates else True
    if inputs.button("Save application", type="primary", disabled=not confirmed, key=f"{prefix}_save"):
        try:
            if demo:
                new_id = max((record.id for record in records), default=0) + 1
                records.insert(0, new_application(company, title, description, new_id))
            else:
                new_id = tracker.add(company, title, description)
            st.session_state[f"{prefix}_record"] = new_id
            st.session_state[f"{prefix}_saved"] = True
            st.rerun()
        except ValueError as error:
            inputs.error(str(error))
    if st.session_state.pop(f"{prefix}_saved", False):
        inputs.success("Application saved.")

with tracker_tab:
    st.subheader("Application tracker")
    if not records:
        st.info("Save a job from the matcher to start tracking it.")
    else:
        st.dataframe([{"Company": record.company, "Role": record.title, "Status": record.status,
                       "Added": record.added_on} for record in records], hide_index=True)
        by_id = {record.id: record for record in records}
        selected = st.selectbox("Application", list(by_id), format_func=lambda item: f"#{item} · {by_id[item].title} at {by_id[item].company}", key=f"{prefix}_record")
        record = by_id[selected]
        status = st.selectbox("Status", STATUSES, index=STATUSES.index(record.status), key=f"{prefix}_status_{selected}")
        if st.button("Update status", disabled=status == record.status, key=f"{prefix}_update"):
            if demo:
                records[records.index(record)] = replace(record, status=status)
            else:
                tracker.set_status(selected, status)
            st.rerun()
