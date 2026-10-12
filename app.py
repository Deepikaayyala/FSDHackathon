import os
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///fixfirst.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

CATEGORIES = [
    "Roads & sidewalks",
    "Waste & cleanliness",
    "Street lighting",
    "Water & drainage",
    "Parks & public spaces",
    "Other",
]
STATUSES = {"open", "in_progress", "resolved"}


class Issue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(40), nullable=False)
    location = db.Column(db.String(160), nullable=False)
    severity = db.Column(db.Integer, nullable=False)
    people_affected = db.Column(db.Integer, nullable=False)
    reporter_name = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    participants = db.relationship(
        "Participant", backref="issue", cascade="all, delete-orphan"
    )
    reports = db.relationship(
        "IssueReport", backref="issue", cascade="all, delete-orphan"
    )


class Participant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey("issue.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    joined_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("issue_id", "name", name="uq_issue_participant"),)


class IssueReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey("issue.id"), nullable=False)
    reporter_name = db.Column(db.String(80), nullable=False)
    normalized_name = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("issue_id", "normalized_name", name="uq_issue_reporter"),
    )


def normalize_key(value):
    return " ".join(value.casefold().split())


def priority_score(issue, now=None):
    """Score severity, reach, and how long the issue has been waiting (0–100)."""
    now = now or datetime.utcnow()
    hours_open = max((now - issue.created_at).total_seconds() / 3600, 0)
    severity_points = issue.severity / 5 * 50
    reach_points = min(len(issue.reports), 1000) / 1000 * 30
    age_points = min(hours_open, 30 * 24) / (30 * 24) * 20
    return round(severity_points + reach_points + age_points)


def issue_to_dict(issue, now=None):
    return {
        "id": issue.id,
        "title": issue.title,
        "description": issue.description,
        "category": issue.category,
        "location": issue.location,
        "severity": issue.severity,
        "people_affected": len(issue.reports),
        "reporter_name": issue.reporter_name,
        "reporters": [report.reporter_name for report in issue.reports],
        "status": issue.status,
        "created_at": issue.created_at.replace(tzinfo=timezone.utc).isoformat(),
        "priority_score": priority_score(issue, now),
        "participants": [participant.name for participant in issue.participants],
    }


def clean_text(value, field, max_length):
    if not isinstance(value, str):
        raise ValueError(f"{field} is required.")
    value = value.strip()
    if not value:
        raise ValueError(f"{field} is required.")
    if len(value) > max_length:
        raise ValueError(f"{field} must be {max_length} characters or fewer.")
    return value


@app.get("/")
def index():
    return render_template("index.html", categories=CATEGORIES)


@app.get("/api/issues")
def list_issues():
    issues = (
        Issue.query.filter(Issue.status != "resolved")
        .order_by(Issue.created_at.desc())
        .all()
    )
    now = datetime.utcnow()
    response = jsonify(
        sorted(
            (issue_to_dict(issue, now) for issue in issues),
            key=lambda issue: (
                -issue["people_affected"],
                -issue["priority_score"],
                issue["created_at"],
            ),
        )
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/api/issues")
def create_issue():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object."), 400
    try:
        title = clean_text(data.get("title"), "Title", 120)
        description = clean_text(data.get("description"), "Description", 2000)
        category = clean_text(data.get("category"), "Category", 40)
        location = clean_text(data.get("location"), "Location", 160)
        reporter_name = clean_text(data.get("reporter_name"), "Your name", 80)
        severity = int(data.get("severity", 0))
        if category not in CATEGORIES:
            raise ValueError("Choose a valid category.")
        if not 1 <= severity <= 5:
            raise ValueError("Severity must be between 1 and 5.")
    except (TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400

    matching_issue = next(
        (
            existing
            for existing in Issue.query.filter_by(category=category)
            .filter(Issue.status != "resolved")
            .all()
            if normalize_key(existing.location) == normalize_key(location)
        ),
        None,
    )
    if matching_issue is not None:
        normalized_name = normalize_key(reporter_name)
        if any(report.normalized_name == normalized_name for report in matching_issue.reports):
            return jsonify(error="You have already reported this issue."), 409
        matching_issue.reports.append(
            IssueReport(
                reporter_name=reporter_name,
                normalized_name=normalized_name,
            )
        )
        matching_issue.people_affected = len(matching_issue.reports)
        matching_issue.severity = max(matching_issue.severity, severity)
        db.session.commit()
        response = issue_to_dict(matching_issue)
        response["merged_report"] = True
        return jsonify(response), 200

    issue = Issue(
        title=title,
        description=description,
        category=category,
        location=location,
        severity=severity,
        people_affected=1,
        reporter_name=reporter_name,
    )
    issue.reports.append(
        IssueReport(
            reporter_name=reporter_name,
            normalized_name=normalize_key(reporter_name),
        )
    )
    db.session.add(issue)
    db.session.commit()
    response = issue_to_dict(issue)
    response["merged_report"] = False
    return jsonify(response), 201


@app.post("/api/issues/<int:issue_id>/join")
def join_issue(issue_id):
    issue = db.session.get(Issue, issue_id)
    if issue is None:
        return jsonify(error="Issue not found."), 404
    if issue.status == "resolved":
        return jsonify(error="This issue has already been resolved."), 409
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object."), 400
    try:
        name = clean_text(data.get("name"), "Your name", 80)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    db.session.add(Participant(issue_id=issue.id, name=name))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="You have already joined this initiative."), 409
    return jsonify(issue_to_dict(issue)), 201


@app.patch("/api/issues/<int:issue_id>/status")
def update_issue_status(issue_id):
    issue = db.session.get(Issue, issue_id)
    if issue is None:
        return jsonify(error="Issue not found."), 404
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object."), 400
    try:
        name = clean_text(data.get("name"), "Your name", 80)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    status = data.get("status")
    if not isinstance(status, str) or status not in STATUSES:
        return jsonify(error="Choose a valid status."), 400
    normalized_name = normalize_key(name)
    is_reporter = any(
        report.normalized_name == normalized_name for report in issue.reports
    )
    is_participant = any(
        participant.name.casefold() == name.casefold()
        for participant in issue.participants
    )
    if not (is_reporter or is_participant):
        return jsonify(error="Join this initiative before updating its status."), 403
    if status == "resolved":
        db.session.delete(issue)
        db.session.commit()
        return jsonify(id=issue_id, status="resolved", deleted=True)
    issue.status = status
    db.session.commit()
    return jsonify(issue_to_dict(issue))


with app.app_context():
    db.create_all()
    for issue in Issue.query.all():
        if not issue.reports:
            issue.reports.append(
                IssueReport(
                    reporter_name=issue.reporter_name,
                    normalized_name=normalize_key(issue.reporter_name),
                )
            )
            issue.people_affected = 1
    db.session.commit()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
