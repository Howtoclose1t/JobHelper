from dataclasses import replace
from pathlib import Path

import streamlit as st

from jobhelper import (
    DEMO_CHECK, DEMO_JOBS, DEMO_SKILLS, DEMO_SOURCES, STATUSES,
    Application, Tracker, duplicate_candidates, match_skills, new_application, search_demo,
)


st.set_page_config(page_title="JobHelper", page_icon="🗂", layout="wide")
st.title("JobHelper")
st.caption("Find sample jobs, review matches, and prepare and track applications locally.")

with st.sidebar:
    st.header("Run settings")
    demo = st.radio("Data mode", ("Demo", "My applications")) == "Demo"
    st.caption("Demo changes reset when you close the session." if demo else "Applications are stored in a local SQLite file.")
    min_score = st.slider("Minimum match score", 0, 100, 60)
    queue_limit = st.number_input("Maximum prepared in queue", 1, 300, 25)
    st.selectbox("Application browser", ("Local preview",), disabled=True)
    st.error("Submission mode: Manual review required")

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

def change_status(record: Application, status: str) -> None:
    if demo:
        records[records.index(record)] = replace(record, status=status)
    else:
        tracker.set_status(record.id, status)


def show_records(items: list[Application]) -> None:
    st.dataframe([{"Company": item.company, "Role": item.title, "Status": item.status,
                   "Added": item.added_on} for item in items], hide_index=True)


overview, search_tab, listings, research, match_tab, tracker_tab, history, gmail, questions, profile = st.tabs((
    "Overview", "Search Jobs", "Job Listings", "Research Jobs", "Prepare Application", "Review & Track",
    "Application History", "Gmail Status", "Common Questions", "Candidate Profile",
))

with profile:
    st.subheader("Candidate profile")
    st.caption("Enter the skills you want to compare with job descriptions. Demo mode provides sample skills.")
    skills = st.text_input("Your skills (comma-separated)", value=DEMO_SKILLS if demo else "", key=f"{prefix}_skills")

with overview:
    all_samples = search_demo("All sources", "", "") if demo else []
    history_records = [item for item in records if item.status in {"Applied", "Interview", "Offer", "Rejected", "Withdrawn"}]
    prepared = [item for item in records if item.status == "Prepared"]
    metrics = st.columns(4)
    metrics[0].metric("Jobs discovered", len(all_samples) if demo else len(records))
    metrics[1].metric(f"Match score {min_score}+", sum(match_skills(skills, item.description).percent >= min_score for item in (all_samples if demo else records)))
    metrics[2].metric("Prepared applications", len(prepared))
    metrics[3].metric("Application history", len(history_records))
    st.subheader("Safety controls")
    st.write("Review each application yourself. JobHelper uses a local preview for preparation and records submission status when you update it.")
    st.subheader("Queue for manual submission")
    if prepared:
        st.write(f"{len(prepared)} applications ready for review.")
        actions = st.columns(2)
        if actions[0].button("Preview current application", type="primary", key="overview_preview"):
            st.session_state[f"{prefix}_preview"] = prepared[0].id
        if actions[1].button("Skip current application", key="overview_skip"):
            change_status(prepared[0], "Skipped")
            st.rerun()
        if st.session_state.get(f"{prefix}_preview") == prepared[0].id:
            st.text(f"{prepared[0].title} · {prepared[0].company}\n\n{prepared[0].description}")
    else:
        st.info("Prepare a job in Prepare Application to add it to this queue.")
    st.subheader("Manual application candidates")
    candidates = [item for item in records if item.status == "Saved"]
    if candidates:
        show_records(candidates)
    else:
        st.info("Saved applications will appear here.")
    st.subheader("Review later")
    later = [item for item in records if item.status == "Later"]
    if later:
        show_records(later)
    else:
        st.caption("Move an application to Later in Review & Track to see it here.")

with search_tab:
    st.subheader("Job search")
    for column, label in zip(st.columns(len(DEMO_SOURCES)), DEMO_SOURCES):
        if column.button(label, key=f"source_{label}", width="stretch"):
            st.session_state.selected_source = label
            st.session_state.sample_filters = (label, "", "")
    st.info("Simulated search. All postings are fictional. Job boards are not contacted.")
    with st.form("sample_search"):
        filters = st.columns(3)
        source = st.session_state.get("selected_source", "StepStone")
        filters[0].text(f"Source: {source}")
        query = filters[1].text_input("Keywords", placeholder="Data Engineer", key="search_keywords")
        location = filters[2].text_input("Location", placeholder="Berlin", key="search_location")
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
                st.success("Sample copied. Open Prepare Application to review it.")
    if not demo:
        st.caption("Switch to Demo mode to try application preparation with a fictional posting.")

with listings:
    st.subheader("Job listings")
    if demo:
        scored = [(item, match_skills(skills, item.description).percent) for item in all_samples]
        visible = [{"Role": item.title, "Company": item.company, "Location": item.location,
                    "Source": item.source, "Match score": score} for item, score in scored if score >= min_score]
        if visible:
            st.dataframe(visible, hide_index=True)
        else:
            st.info("No sample jobs meet the current match threshold.")
    elif records:
        show_records(records)
    else:
        st.info("Add a job in Prepare Application to start your list.")

with research:
    st.subheader("Research jobs")
    if demo:
        st.dataframe([{"Role": "Research Software Engineer", "Institution": "Example Institute for Computing",
                       "Topic": "Reproducible Python workflows", "Location": "Berlin", "Source": "Fictional example"}], hide_index=True)
    else:
        st.info("The research jobs panel shows a fictional research listing in Demo mode.")

with match_tab:
    st.subheader("Prepare a job application")
    inputs, analysis = st.columns([3, 2])
    company = inputs.text_input("Company", key=draft_keys[0])
    title = inputs.text_input("Job title", key=draft_keys[1])
    description = inputs.text_area("Job description", key=draft_keys[2], height=140)
    inputs.caption("Edit your skills in Candidate Profile.")
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
    prepare = inputs.checkbox("Add to the prepared queue", key=f"{prefix}_prepare")
    if inputs.button("Save application", type="primary", disabled=not confirmed, key=f"{prefix}_save"):
        try:
            if prepare and len(prepared) >= queue_limit:
                raise ValueError("The prepared queue is at its configured limit.")
            if demo:
                new_id = max((record.id for record in records), default=0) + 1
                records.insert(0, new_application(company, title, description, new_id))
                if prepare:
                    change_status(records[0], "Prepared")
            else:
                new_id = tracker.add(company, title, description)
                if prepare:
                    tracker.set_status(new_id, "Prepared")
            st.session_state[f"{prefix}_record"] = new_id
            st.session_state[f"{prefix}_saved"] = True
            st.rerun()
        except ValueError as error:
            inputs.error(str(error))
    if st.session_state.pop(f"{prefix}_saved", False):
        inputs.success("Application saved.")

with tracker_tab:
    st.subheader("Review and track applications")
    if not records:
        st.info("Save a job from the matcher to start tracking it.")
    else:
        show_records(records)
        by_id = {record.id: record for record in records}
        selected = st.selectbox("Application", list(by_id), format_func=lambda item: f"#{item} · {by_id[item].title} at {by_id[item].company}", key=f"{prefix}_record")
        record = by_id[selected]
        with st.expander("Application preview"):
            st.text(record.description)
        status = st.selectbox("Status", STATUSES, index=STATUSES.index(record.status), key=f"{prefix}_status_{selected}")
        if st.button("Update status", disabled=status == record.status, key=f"{prefix}_update"):
            change_status(record, status)
            st.rerun()

with history:
    st.subheader("Application history")
    query = st.text_input("Find a company or role", key="history_query").strip().casefold()
    matching_history = [item for item in history_records if query in f"{item.company} {item.title}".casefold()]
    if matching_history:
        show_records(matching_history)
    else:
        st.info("Applications marked Applied or with a later outcome appear here.")

with gmail:
    st.subheader("Gmail application status")
    st.info("Email status preview. This edition does not connect to Gmail.")
    if demo:
        st.dataframe([{"Subject": "Interview invitation (fictional)", "Company": "Harbor Example Analytics",
                       "Detected status": "Interview"}], hide_index=True)

with questions:
    st.subheader("Common application questions")
    st.dataframe([
        {"Question": "Are you authorized to work here?", "Handling": "Confirm yourself"},
        {"Question": "What is your earliest start date?", "Handling": "Confirm yourself"},
        {"Question": "Why are you interested in this role?", "Handling": "Write a role-specific answer"},
    ], hide_index=True)
