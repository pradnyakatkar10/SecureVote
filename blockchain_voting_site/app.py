"""
app.py
------
Blockchain-Based Voting System — full site with real, server-enforced
access control: every page that requires being logged in (as a voter or
as an admin) checks the session on the server and redirects if it's
missing. There is no page that merely *hides* behind a tab in the
browser — visiting a protected URL directly, with no session, always
redirects to a login page.

Run with:
    python3 app.py
Then open:
    http://127.0.0.1:5000

Default admin login (change/remove for anything beyond a class demo):
    Student ID: admin
    Password:   admin123
"""

import functools
import os
import time
import uuid

from flask import Flask, flash, redirect, render_template, request, session, url_for
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash

from blockchain.ethereum import ethereum
from database.db import get_conn, init_db, voter_hash_for

APP_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(APP_DIR, ".env"))

app = Flask(__name__)
app.secret_key = "dev-only-secret-key-change-before-any-real-deployment"

init_db()


# =========================================================
# Auth decorators — the actual access-control enforcement
# =========================================================
def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "err")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin login required.", "err")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


def current_user(conn):
    uid = session.get("user_id")
    if not uid:
        return None
    return conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def get_active_election(conn):
    return conn.execute(
        "SELECT * FROM elections WHERE status='active' ORDER BY id DESC LIMIT 1"
    ).fetchone()


# =========================================================
# Public entry points
# =========================================================
@app.route("/")
def index():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id") or session.get("is_admin"):
        return redirect(url_for("index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        student_id = request.form.get("student_id", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not all([name, student_id, email, password]):
            flash("All fields are required.", "err")
            return render_template("register.html", form=request.form)

        conn = get_conn()
        clash = conn.execute(
            "SELECT id FROM users WHERE student_id=? OR email=?", (student_id, email)
        ).fetchone()
        if clash:
            conn.close()
            flash("A voter with that Student ID or Email is already registered.", "err")
            return render_template("register.html", form=request.form)

        conn.execute(
            "INSERT INTO users (name, student_id, email, password_hash, voter_hash, is_admin) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (name, student_id, email, generate_password_hash(password), voter_hash_for(student_id)),
        )
        conn.commit()
        conn.close()
        flash("Registration successful. Please log in below.", "ok")
        return redirect(url_for("login"))

    return render_template("register.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        password = request.form.get("password", "")
        conn = get_conn()
        user = conn.execute(
            "SELECT * FROM users WHERE student_id=? AND is_admin=0", (student_id,)
        ).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["is_admin"] = False
            session["name"] = user["name"]
            flash(f"Welcome back, {user['name']}.", "ok")
            return redirect(url_for("dashboard"))
        flash("Invalid Student ID or password.", "err")

    return render_template("login.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        password = request.form.get("password", "")
        conn = get_conn()
        user = conn.execute(
            "SELECT * FROM users WHERE student_id=? AND is_admin=1", (student_id,)
        ).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["is_admin"] = True
            session["name"] = user["name"]
            flash("Welcome, Administrator.", "ok")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "err")

    return render_template("admin_login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "ok")
    return redirect(url_for("login"))


# =========================================================
# Voter area
# =========================================================
@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_conn()
    user = current_user(conn)
    if session.get("is_admin"):
        conn.close()
        return redirect(url_for("admin_dashboard"))

    election = get_active_election(conn)
    candidates = []
    has_voted = False
    if election:
        candidates = conn.execute(
            "SELECT * FROM candidates WHERE election_id=?", (election["id"],)
        ).fetchall()
        voted = conn.execute(
            "SELECT 1 FROM votes WHERE user_id=? AND election_id=?", (user["id"], election["id"])
        ).fetchone()
        has_voted = bool(voted)
    conn.close()
    return render_template(
        "voter_dashboard.html", user=user, election=election, candidates=candidates, has_voted=has_voted
    )


@app.route("/vote", methods=["POST"])
@login_required
def vote():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))

    candidate_id = request.form.get("candidate_id")
    conn = get_conn()
    user = current_user(conn)
    election = get_active_election(conn)

    if not election:
        conn.close(); flash("There is no active election right now.", "err"); return redirect(url_for("dashboard"))
    if not candidate_id:
        conn.close(); flash("Select a candidate first.", "err"); return redirect(url_for("dashboard"))

    candidate = conn.execute(
        "SELECT * FROM candidates WHERE id=? AND election_id=?", (candidate_id, election["id"])
    ).fetchone()
    if not candidate or not candidate["contract_candidate_id"]:
        conn.close(); flash("This candidate is not yet registered on the blockchain.", "err"); return redirect(url_for("dashboard"))

    already = conn.execute(
        "SELECT 1 FROM votes WHERE user_id=? AND election_id=?", (user["id"], election["id"])
    ).fetchone()
    if already:
        conn.close(); flash("You have already cast your vote.", "err"); return redirect(url_for("dashboard"))

    try:
        if ethereum.has_voted(user["voter_hash"]):
            conn.close(); flash("This voter already has an on-chain vote.", "err"); return redirect(url_for("dashboard"))
        tx_hash = ethereum.vote(user["voter_hash"], candidate["contract_candidate_id"])
    except Exception as exc:
        conn.close(); flash(f"Blockchain transaction failed: {exc}", "err"); return redirect(url_for("dashboard"))

    conn.execute(
        "INSERT INTO votes (user_id, election_id, blockchain_tx_hash) VALUES (?, ?, ?)",
        (user["id"], election["id"], tx_hash),
    )
    conn.commit(); conn.close()
    flash(f"Your vote was recorded on the Ethereum-compatible blockchain. TX: {tx_hash[:12]}…", "ok")
    return redirect(url_for("dashboard"))


# =========================================================
# Shared (voter + admin): Results, Ledger, Verify
# =========================================================
@app.route("/results")
@login_required
def results():
    conn = get_conn()
    election = get_active_election(conn) or conn.execute(
        "SELECT * FROM elections ORDER BY id DESC LIMIT 1"
    ).fetchone()
    candidates = []
    counts = {}
    total_voters = conn.execute("SELECT COUNT(*) c FROM users WHERE is_admin=0").fetchone()["c"]
    total_votes = 0
    if election:
        candidates = conn.execute(
            "SELECT * FROM candidates WHERE election_id=?", (election["id"],)
        ).fetchall()
        counts = {}
        try:
            onchain = ethereum.results()
            mapped = conn.execute("SELECT id, contract_candidate_id FROM candidates WHERE election_id=?", (election["id"],)).fetchall()
            for row in mapped:
                cid = row["contract_candidate_id"]
                counts[row["id"]] = onchain[cid - 1][1] if cid and 0 < cid <= len(onchain) else 0
            total_votes = sum(counts.values())
        except Exception:
            total_votes = 0
    conn.close()
    return render_template(
        "results.html",
        election=election,
        candidates=candidates,
        counts=counts,
        total_voters=total_voters,
        total_votes=total_votes,
    )


@app.route("/blockchain")
@login_required
def blockchain_view():
    conn = get_conn()
    election = get_active_election(conn) or conn.execute("SELECT * FROM elections ORDER BY id DESC LIMIT 1").fetchone()
    txs = conn.execute("SELECT blockchain_tx_hash FROM votes WHERE blockchain_tx_hash IS NOT NULL ORDER BY id DESC").fetchall()
    conn.close()
    ready = ethereum.ready()
    state = None
    results = []
    try:
        if ready:
            state = ethereum.status()
            results = ethereum.results()
    except Exception:
        pass
    return render_template("blockchain.html", election=election, ready=ready, state=state, results=results, txs=txs, contract_address=ethereum.contract_address, rpc_url=ethereum.rpc_url)


@app.route("/verify")
@login_required
def verify():
    if ethereum.ready():
        flash("The voting records are stored as blockchain transactions and can be independently checked using their transaction hashes.", "ok")
    else:
        flash("Ethereum/Ganache is not configured yet.", "err")
    return redirect(url_for("blockchain_view"))


# =========================================================
# Admin area
# =========================================================
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    conn = get_conn()
    elections = conn.execute("SELECT * FROM elections ORDER BY id DESC").fetchall()
    current = conn.execute(
        "SELECT * FROM elections WHERE status IN ('pending','active') ORDER BY id DESC LIMIT 1"
    ).fetchone()
    candidates = []
    if current:
        candidates = conn.execute(
            "SELECT * FROM candidates WHERE election_id=?", (current["id"],)
        ).fetchall()
    conn.close()
    return render_template(
        "admin_dashboard.html", elections=elections, current=current, candidates=candidates
    )


@app.route("/admin/election/create", methods=["POST"])
@admin_required
def admin_create_election():
    name = request.form.get("name", "").strip()
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()
    if not name:
        flash("Election name is required.", "err")
        return redirect(url_for("admin_dashboard"))

    conn = get_conn()
    open_one = conn.execute(
        "SELECT id FROM elections WHERE status IN ('pending','active')"
    ).fetchone()
    if open_one:
        conn.close()
        flash("There is already a pending or active election. End it before creating a new one.", "err")
        return redirect(url_for("admin_dashboard"))

    try:
        ethereum.create_election(name)
    except Exception as exc:
        conn.close(); flash(f"Could not create the election on blockchain: {exc}", "err"); return redirect(url_for("admin_dashboard"))

    conn.execute(
        "INSERT INTO elections (name, start_time, end_time, status) VALUES (?, ?, ?, 'pending')",
        (name, start_time, end_time),
    )
    conn.commit()
    conn.close()
    flash("Election created. Add at least two candidates, then start it.", "ok")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/candidate/add", methods=["POST"])
@admin_required
def admin_add_candidate():
    election_id = request.form.get("election_id")
    name = request.form.get("name", "").strip()
    party = request.form.get("party", "").strip()
    if not name or not election_id:
        flash("Candidate name is required.", "err")
        return redirect(url_for("admin_dashboard"))

    conn = get_conn()
    election = conn.execute("SELECT * FROM elections WHERE id=?", (election_id,)).fetchone()
    if not election or election["status"] != "pending":
        conn.close()
        flash("Candidates can only be added before the election starts.", "err")
        return redirect(url_for("admin_dashboard"))

    conn.execute(
        "INSERT INTO candidates (election_id, name, party) VALUES (?, ?, ?)",
        (election_id, name, party),
    )
    conn.commit()
    conn.close()
    flash("Candidate added.", "ok")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/candidate/remove/<int:cid>", methods=["POST"])
@admin_required
def admin_remove_candidate(cid):
    conn = get_conn()
    cand = conn.execute(
        "SELECT c.*, e.status AS election_status FROM candidates c "
        "JOIN elections e ON c.election_id = e.id WHERE c.id=?",
        (cid,),
    ).fetchone()
    if not cand or cand["election_status"] != "pending":
        conn.close()
        flash("Candidates can only be removed before the election starts.", "err")
        return redirect(url_for("admin_dashboard"))
    conn.execute("DELETE FROM candidates WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    flash("Candidate removed.", "ok")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/election/start", methods=["POST"])
@admin_required
def admin_start_election():
    election_id = request.form.get("election_id")
    conn = get_conn()
    count = conn.execute(
        "SELECT COUNT(*) c FROM candidates WHERE election_id=?", (election_id,)
    ).fetchone()["c"]
    if count < 2:
        conn.close()
        flash("Add at least two candidates before starting the election.", "err")
        return redirect(url_for("admin_dashboard"))
    candidates = conn.execute("SELECT * FROM candidates WHERE election_id=? ORDER BY id", (election_id,)).fetchall()
    try:
        for idx, c in enumerate(candidates, start=1):
            ethereum.add_candidate(c["name"], c["party"] or "")
            conn.execute("UPDATE candidates SET contract_candidate_id=? WHERE id=?", (idx, c["id"]))
        ethereum.start_election()
    except Exception as exc:
        conn.close(); flash(f"Could not start the blockchain election: {exc}", "err"); return redirect(url_for("admin_dashboard"))
    conn.execute("UPDATE elections SET status='active' WHERE id=?", (election_id,))
    conn.commit()
    conn.close()
    flash("Election started. Voters can now cast their vote.", "ok")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/election/end", methods=["POST"])
@admin_required
def admin_end_election():
    election_id = request.form.get("election_id")
    conn = get_conn()
    try:
        ethereum.end_election()
    except Exception as exc:
        conn.close(); flash(f"Could not end the blockchain election: {exc}", "err"); return redirect(url_for("admin_dashboard"))
    conn.execute("UPDATE elections SET status='ended' WHERE id=?", (election_id,))
    conn.commit()
    conn.close()
    flash("Election ended. Results are now final.", "ok")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/voters")
@admin_required
def admin_voters():
    conn = get_conn()
    voters = conn.execute("SELECT * FROM users WHERE is_admin=0 ORDER BY id").fetchall()
    conn.close()
    return render_template("admin_voters.html", voters=voters)




if __name__ == "__main__":
    app.run(debug=True, port=5000)
